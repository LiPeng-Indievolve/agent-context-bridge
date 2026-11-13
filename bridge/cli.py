import argparse,json,os,pathlib,sys
from .scan import scan
from .engine import Engine

def main():
 p=argparse.ArgumentParser(description='Local Claude Code ↔ Codex portable context migration')
 p.add_argument('--claude-home',default=os.environ.get('CLAUDE_CONFIG_DIR',str(pathlib.Path.home()/'.claude')))
 p.add_argument('--codex-home',default=os.environ.get('CODEX_HOME',str(pathlib.Path.home()/'.codex')))
 p.add_argument('--state-dir',default=str(pathlib.Path.home()/'.local/share/agent-context-bridge'))
 p.add_argument('--root',action='append',default=[],help='Additional workspace root to scan (depth ≤4)')
 p.add_argument('--include-observers',action='store_true')
 sub=p.add_subparsers(dest='command',required=True);sub.add_parser('scan');sub.add_parser('serve');sub.add_parser('history')
 for cmd in ['preview','migrate']:
  q=sub.add_parser(cmd);q.add_argument('--to',required=True,choices=['claude','codex']);q.add_argument('--id',action='append',default=[]);q.add_argument('--project',action='append',default=[]);q.add_argument('--all',action='store_true');q.add_argument('--apply',action='store_true',help='Actually write; otherwise preview only');q.add_argument('--full-history',action='store_true',help='Archival full replay; may exceed model limits and fail to resume. Default CC to Codex uses bounded working context.')
 q=sub.add_parser('prepare',help='Build a <=48KB working handoff and searchable local archive from Claude JSONL');q.add_argument('--source',required=True);q.add_argument('--output',required=True);q.add_argument('--seed',default='');q.add_argument('--max-bytes',type=int,default=48*1024)
 q=sub.add_parser('search',help='Search a prepared offline index without loading the full history into a model');q.add_argument('--index',required=True);q.add_argument('--query',required=True);q.add_argument('--limit',type=int,default=20)
 q=sub.add_parser('verify',help='Opt-in actual read-only Codex model turn; consumes configured model quota');q.add_argument('migration_id')
 q=sub.add_parser('finish-switch',help='Preview/archive matched old Codex entries after successful runtime verification');q.add_argument('migration_id');q.add_argument('--apply',action='store_true')
 q=sub.add_parser('rollback');q.add_argument('migration_id')
 a=p.parse_args();e=Engine(a.claude_home,a.codex_home,a.state_dir)
 try:
  if a.command=='serve':
   from .web import serve
   serve(a,e);return
  if a.command=='verify':
   from .switching import verify
   result=verify(e,a.migration_id)
  elif a.command=='finish-switch':
   from .switching import finish_switch
   result=finish_switch(e,a.migration_id,a.apply)
  elif a.command=='prepare':
   from .handoff import prepare
   result=prepare(a.source,a.output,seed=a.seed,max_bytes=a.max_bytes)
  elif a.command=='search':
   from .handoff import search
   result=search(a.index,a.query,limit=a.limit)
  elif a.command=='history':result=e.journal()
  elif a.command=='rollback':result=e.rollback(a.migration_id)
  else:
   items=scan(a.claude_home,a.codex_home,a.root,a.include_observers)
   if a.command=='scan':result=items
   else:
    selected=[x for x in items if x['source']!=a.to and (a.all or x['id'] in a.id or x['cwd'] in a.project)]
    if not selected:raise ValueError('Nothing selected: use --id, --project or --all')
    represented={x['cwd'] for x in selected if x['source']!='workspace'};selected=[x for x in selected if x['source']!='workspace' or x['cwd'] not in represented]
    result=[]
    for item in selected:
     try:result.append(e.migrate(item,a.to,a.command=='migrate' and a.apply,full_history=a.full_history))
     except Exception as exc:result.append({'id':item['id'],'status':'failed','error':str(exc)})
  print(json.dumps(result,ensure_ascii=False,indent=2))
  if isinstance(result,list) and any(r.get('status')=='failed' for r in result):sys.exit(1)
  if isinstance(result,dict) and (result.get('runtime_verification',{}).get('status')=='failed' or (result.get('dry_run') is False and result.get('switch_complete') is False)):sys.exit(1)
 except (ValueError,RuntimeError,OSError,TimeoutError) as exc:p.exit(1,str(exc)+'\n')
