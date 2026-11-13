"""Verify a real model turn, then safely archive superseded destination entries."""
import json,os,pathlib,shlex,sqlite3,subprocess,time,uuid,tomllib

def _record(engine,mid):
 records=engine.journal();r=next((x for x in records if x['migration_id']==mid),None)
 if not r:raise ValueError('Unknown migration ID')
 if r.get('status')!='completed' or r.get('target')!='codex' or r.get('mode')!='working_context':raise ValueError('Select a completed Codex working-context migration')
 uuid.UUID(r['target_id'])
 return records,r

def resume_command(r,codex_home=None):
 args=['codex','-C',r['cwd'],'resume',r['target_id']]
 if codex_home is not None:args=['env','CODEX_HOME='+str(pathlib.Path(codex_home).resolve()),*args]
 return shlex.join(args)

def _verification_args(engine,r,answer,prompt):
 # Discard executable user settings, then explicitly mask any project MCP entries.
 # Auth remains in CODEX_HOME; a provider requiring discarded settings fails closed.
 args=['codex','--no-daemon']
 for name in ['hooks','plugins','apps','shell_tool']:args+=['--disable',name]
 args+=['exec','--ignore-user-config','--ignore-rules','-c','web_search="disabled"','-s','read-only','-C',r['cwd'],'--skip-git-repo-check']
 names=set();model=None;cwd=pathlib.Path(r['cwd']).resolve();configs=[engine.cx/'config.toml',*[p/'.codex/config.toml'for p in [cwd,*cwd.parents]]]
 for path in configs:
  if path.is_file():
   config=tomllib.loads(path.read_text());names.update(config.get('mcp_servers',{}))
   if config.get('model_provider','openai')!='openai':raise ValueError('Isolated verification supports the OpenAI provider only; custom provider configuration was not loaded. No entries archived')
   if path==engine.cx/'config.toml':model=config.get('model')
 if model:args+=['--model',str(model)]
 for name in sorted(names):args+=['-c','mcp_servers.'+json.dumps(name)+'={command="/usr/bin/false",enabled=false}']
 return args+['resume',r['target_id'],prompt,'--json','-o',str(answer)]

def _archived(engine,sid):
 for db in sorted(engine.cx.glob('state_*.sqlite'),key=lambda p:int(p.stem.split('_')[-1]) if p.stem.split('_')[-1].isdigit()else -1,reverse=True):
  try:
   with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)as c:row=c.execute('SELECT archived FROM threads WHERE id=?',(sid,)).fetchone()
   return bool(row[0]) if row else None
  except sqlite3.Error:continue
 return None

def _private_open(path):
 return open(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w',encoding='utf-8')

def verify(engine,mid):
 """Explicit opt-in model request; native discoverability alone is not a pass."""
 with engine.lock():
  records,r=_record(engine,mid);folder=pathlib.Path(r['bundle'])/'runtime-verification';folder.mkdir(mode=0o700,exist_ok=True);events=folder/'events.jsonl';errors=folder/'stderr.txt';answer=folder/'answer.txt';answer.unlink(missing_ok=True)
  prompt='Read-only migration verification. Briefly explain the project/work background, latest actual user task and unresolved facts from the imported handoff. If this was only a short chat, say so. Do not execute historical tasks, call tools, connect to services, or output credentials.'
  r['ready_to_use']=False;r['runtime_verification']={'status':'pending','target_id':r['target_id']};engine.save(records)
  try:args=_verification_args(engine,r,answer,prompt)
  except (ValueError,OSError)as exc:
   r['runtime_verification']={'status':'failed','target_id':r['target_id'],'error':str(exc)};engine.save(records);raise
  issue=None;exit_code=None
  try:
   with _private_open(events)as out,_private_open(errors)as err:result=subprocess.run(args,stdout=out,stderr=err,env=dict(os.environ,CODEX_HOME=str(engine.cx)),timeout=240)
   exit_code=result.returncode
  except (OSError,subprocess.TimeoutExpired)as exc:issue=str(exc)
  started=False;completed=False;failure=False
  for line in events.read_text().splitlines()if events.exists()else []:
   try:event=json.loads(line)
   except ValueError:continue
   if event.get('type')=='thread.started':started=event.get('thread_id')==r['target_id']
   if event.get('type')=='turn.completed':completed=True
   if event.get('type')in('turn.failed','error'):failure=True
  passed=exit_code==0 and started and completed and not failure and answer.is_file() and bool(answer.read_text().strip())
  for p in [events,errors,answer]:
   if p.exists():p.chmod(0o600)
  r['runtime_verification']={'status':'passed'if passed else'failed','target_id':r['target_id'],'checked_at':time.time(),'exit_code':exit_code,'turn_completed':completed,'events_path':str(events),'errors_path':str(errors),'answer_path':str(answer)}
  if issue:r['runtime_verification']['error']=issue
  r['ready_to_use']=passed;r['resume_command']=resume_command(r,engine.cx);r['next_step']='Exit any old agent window with /exit, then run resume_command. Use finish-switch to archive matched superseded entries.'if passed else'Inspect the private verification logs. No old entries were archived; retry verify after fixing the reported error.'
  engine.save(records);return r

def _older(value,current):
 return isinstance(value,(int,float))and isinstance(current,(int,float))and value<current

def _superseded(engine,records,r):
 related={x['target_id']for x in records if x.get('source')=='claude'and x.get('source_id')==r['source_id']and x.get('target')=='codex'and x.get('status')=='completed'and x.get('target_id')!=r['target_id']}
 ids={x['target_id']for x in records if x.get('source')=='claude'and x.get('source_id')==r['source_id']and x.get('target')=='codex'and x.get('status')=='completed'and x.get('target_id')!=r['target_id']and _older(x.get('created'),r.get('created'))}
 meta=r.get('working_context')or{};source=meta.get('source_path');sha=meta.get('source_sha256');registry=engine.cx/'external_agent_session_imports.json'
 if source and sha and registry.is_file():
  data=json.loads(registry.read_text())
  for old in data.get('records',[]):
   if pathlib.Path(old.get('source_path','')).resolve()==pathlib.Path(source).resolve()and old.get('content_sha256')==sha:
    related.add(old['imported_thread_id'])
    if _older(old.get('imported_at'),r.get('created'))and old['imported_at']+1<=r['created']:ids.add(old['imported_thread_id'])
 ids.discard(r['target_id']);related.discard(r['target_id'])
 for sid in related:uuid.UUID(sid)
 return sorted(ids),sorted(related-ids)

def finish_switch(engine,mid,apply=False):
 """Dry-run by default; never delete source data, kill writers or remove locks."""
 with engine.lock():
  records,r=_record(engine,mid);check=r.get('runtime_verification')or{};verified=check.get('status')=='passed'and check.get('target_id')==r['target_id'];ids,retained=_superseded(engine,records,r);newer=[x['migration_id']for x in records if x.get('source')=='claude'and x.get('source_id')==r['source_id']and x.get('mode')=='working_context'and x.get('status')=='completed'and _older(r.get('created'),x.get('created'))]
  plan={'migration_id':mid,'target_id':r['target_id'],'runtime_verified':verified,'newer_working_migrations':newer,'old_thread_ids':ids,'retained_related_thread_ids':retained,'resume_command':resume_command(r,engine.cx),'dry_run':not apply,'hint':'Exit the old CLI with /exit first. Archiving an active writer may fail; retry after it closes. Full history is retained.'}
  if not apply:return plan
  if newer:raise ValueError('A newer working migration exists; select it instead. No entries archived')
  if not verified:raise ValueError('Run verify MIGRATION_ID successfully before finish-switch --apply; discoverability is not runtime verification')
  if _archived(engine,r['target_id'])is not False:raise ValueError('Working target is archived or missing; no old entries archived')
  results=[]
  for sid in retained:
   results.append({'thread_id':sid,'status':'already_archived'if _archived(engine,sid)is True else'unconfirmed','hint':'Could not prove this related entry is older (timestamp precision or newer import). Not touched; inspect it manually.'})
  for sid in ids:
   state=_archived(engine,sid)
   if state is True:results.append({'thread_id':sid,'status':'already_archived'});continue
   if state is None:results.append({'thread_id':sid,'status':'unconfirmed','hint':'Target not present in the local native catalog; not touched'});continue
   try:
    done=subprocess.run(['codex','archive',sid],capture_output=True,text=True,env=dict(os.environ,CODEX_HOME=str(engine.cx)),timeout=60)
    if done.returncode==0 and _archived(engine,sid)is True:results.append({'thread_id':sid,'status':'archived'})
    else:
     busy='active writer'in(done.stderr+done.stdout).lower();results.append({'thread_id':sid,'status':'busy'if busy else'failed','hint':'Enter /exit in the old terminal, then retry finish-switch --apply. Do not remove locks or kill unrelated processes.'if busy else'Archive was not confirmed; original history was retained. Check the old session and retry.'})
   except (OSError,subprocess.TimeoutExpired)as exc:results.append({'thread_id':sid,'status':'failed','hint':str(exc)})
  complete=all(x['status']in('archived','already_archived')for x in results);r['switch_complete']=complete;r['old_entries']=results;r['resume_command']=resume_command(r,engine.cx);engine.save(records)
  return dict(plan,dry_run=False,switch_complete=complete,old_entries=results)
