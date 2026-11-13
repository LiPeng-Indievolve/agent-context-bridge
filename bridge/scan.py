"""Read-only native inventories plus bounded optional workspace discovery."""
import pathlib,json,sqlite3,os
from .codec import rows,blocks

def scan(claude_home,codex_home,roots,include_observers=False):
 cc=pathlib.Path(claude_home).expanduser();cx=pathlib.Path(codex_home).expanduser();items=[];seen=set()
 for p in (cc/'projects').glob('*/*.jsonl'):
  if not include_observers and 'observer' in p.parent.name:continue
  cwd='';title='';count=0
  try:
   for o in rows(p,[]):
    cwd=o.get('cwd') or cwd
    if o.get('type')=='user':
     v=blocks(o.get('message',{}).get('content'),[])
     if isinstance(v,str) and not v.startswith('<') and not title:title=v[:120].replace('\n',' ')
    count+=1
    if count>=60 and cwd and title:break
   items.append({'source':'claude','id':p.stem,'path':str(p),'cwd':cwd,'title':title or p.stem,'bytes':p.stat().st_size,'updated':p.stat().st_mtime})
  except (OSError,ValueError):continue
 for db in sorted(cx.glob('state_*.sqlite'),key=lambda p:int(p.stem.split('_')[-1]) if p.stem.split('_')[-1].isdigit() else -1,reverse=True):
  try:
   with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as c:
    for sid,path,cwd,title,updated in c.execute('SELECT id,rollout_path,cwd,title,updated_at FROM threads WHERE archived=0'):
     if sid in seen:continue
     seen.add(sid);items.append({'source':'codex','id':sid,'path':path,'cwd':cwd,'title':(title or sid)[:120],'updated':updated,'bytes':pathlib.Path(path).stat().st_size if pathlib.Path(path).is_file() else 0,'native':True})
   break
  except (OSError,sqlite3.Error):continue
 for p in (cx/'sessions').rglob('*.jsonl'):
  try:
   with p.open() as f:o=json.loads(f.readline())
   meta=o.get('payload',{});sid=meta.get('id')
   if not sid or sid in seen:continue
   seen.add(sid);items.append({'source':'codex','id':sid,'path':str(p),'cwd':meta.get('cwd',''),'title':sid,'bytes':p.stat().st_size,'updated':p.stat().st_mtime})
  except (OSError,ValueError):continue
 # Explicit roots discover projects with no sessions without traversing entire home.
 known={x['cwd'] for x in items};skip={'.git','node_modules','.venv','venv','Library','.cache','.codex','.claude'}
 for root in roots:
  root=pathlib.Path(root).expanduser().resolve()
  for directory,dirs,files in os.walk(root):
   is_project='.git' in dirs or '.git' in files or 'CLAUDE.md' in files or 'AGENTS.md' in files
   dirs[:]=[d for d in dirs if d not in skip and not pathlib.Path(directory,d).is_symlink()]
   if len(pathlib.Path(directory).relative_to(root).parts)>=4:dirs[:]=[]
   if is_project and directory not in known:
    known.add(directory);items.append({'source':'workspace','id':directory,'cwd':directory,'title':pathlib.Path(directory).name,'path':directory,'bytes':0,'updated':0})
 return sorted(items,key=lambda x:x['updated'],reverse=True)
