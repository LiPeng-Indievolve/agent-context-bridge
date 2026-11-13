import pathlib,sys,json,uuid,tempfile,hashlib,subprocess,time,os,argparse
p=argparse.ArgumentParser(description='Opt-in synthetic native import, model verification and archive smoke test')
p.add_argument('--allow-model-call',action='store_true');a=p.parse_args()
if not a.allow_model_call:p.error('--allow-model-call is required: this test calls your Codex model and uses quota')
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from bridge.codec import write_claude,project_key
from bridge.rpc import RPC
from bridge.engine import Engine
from bridge.switching import verify,finish_switch
home=pathlib.Path.home();root=pathlib.Path(tempfile.mkdtemp(prefix='bridge-switch-e2e-'));cwd=root/'workspace with spaces';cwd.mkdir();cc=root/'claude';cx=pathlib.Path(os.environ.get('CODEX_HOME',str(home/'.codex'))).expanduser().resolve();state=root/'state';sid=str(uuid.uuid4());source=home/'.claude/projects'/project_key(cwd)/(sid+'.jsonl');source.parent.mkdir(parents=True,exist_ok=True);old=None;new=None
# Our own synthetic source only; no personal histories or credentials copied.
doc={'messages':[{'role':'user','text':'合成迁移验收：项目是本地工作区扫描器；最新任务是添加按项目过滤。只读测试，不操作生产。'},{'role':'assistant','text':'历史诊断日志 '+('large historical tool output '*22000)},{'role':'user','text':'保留历史，接着做项目过滤；本次只验证接管背景。'}]}
write_claude(doc,source,sid,str(cwd));source.chmod(0o600);before=hashlib.sha256(source.read_bytes()).hexdigest()
try:
 with RPC(cx)as rpc:old=rpc.import_session(source,str(cwd))
 # Ensure the native second-resolution timestamp is observably earlier. Work below
 # is a real capability-isolation check, not a sleep to hide asynchronous state.
 (cwd/'.codex').mkdir();(cwd/'.codex/config.toml').write_text('[mcp_servers.forbidden_probe]\ncommand="/usr/bin/false"\n')
 subprocess.run(['codex','--version'],check=True,capture_output=True)
 registry=json.loads((cx/'external_agent_session_imports.json').read_text())['records'];import_time=next(x['imported_at']for x in registry if x['imported_thread_id']==old)
 deadline=time.monotonic()+2
 while time.time()<=import_time+1.001 and time.monotonic()<deadline:time.sleep(0.02)
 if time.time()<=import_time+1.001:raise RuntimeError('Native timestamp clock skew prevents proving source order')
 e=Engine(cc,cx,state);item={'source':'claude','id':sid,'path':str(source),'cwd':str(cwd),'title':'Synthetic switch acceptance'};r=e.migrate(item,'codex',True);new=r['target_id'];assert r['ready_to_use']is False
 plan=finish_switch(e,r['migration_id']);print('matched old',old in plan['old_thread_ids'],flush=True)
 # Expose the test if timestamps landed in the same second instead of hiding it.
 if old not in plan['old_thread_ids']:raise RuntimeError('Synthetic old import not observably older at native timestamp precision; explicit recovery needed')
 checked=verify(e,r['migration_id']);assert checked['runtime_verification']['status']=='passed',checked['runtime_verification'];print('actual isolated model turn PASS',flush=True)
 text=pathlib.Path(checked['runtime_verification']['answer_path']).read_text();assert '过滤'in text or 'filter'in text.lower(),text
 done=finish_switch(e,r['migration_id'],True);assert done['switch_complete'],done;assert hashlib.sha256(source.read_bytes()).hexdigest()==before;print('native archive confirmation + source unchanged PASS',flush=True)
 result={'actual_model_verification':'passed','matched_old_archived':'passed','source_unchanged':True,'source_bytes':source.stat().st_size,'staged_text_bytes':r['working_context']['staged_text_bytes'],'private_fixture':str(root)};(root/'smoke-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
finally:
 for target in [old,new]:
  if target:subprocess.run(['codex','archive',target],capture_output=True,text=True,env=dict(os.environ,CODEX_HOME=str(cx)),timeout=60)
 if source.exists()and hashlib.sha256(source.read_bytes()).hexdigest()==before:source.unlink()
 try:source.parent.rmdir()
 except OSError:pass
