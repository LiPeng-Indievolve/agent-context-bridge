"""Codex native app-server protocol; never writes Codex SQLite directly."""
import subprocess,json,threading,queue,time,os
class RPC:
 def __init__(self,home,executable='codex',timeout=180,claude_home=None):
  self.timeout=timeout;self.n=0;self.pending=[];self.events=queue.Queue();env=dict(os.environ,CODEX_HOME=str(home))
  if claude_home is not None:env['CLAUDE_CONFIG_DIR']=str(claude_home)
  self.p=subprocess.Popen([executable,'app-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env)
  def pump():
   try:
    for l in self.p.stdout:
     try:self.events.put(json.loads(l))
     except ValueError:pass
   finally:self.events.put(None)
  threading.Thread(target=pump,daemon=True).start()
  try:
   self.call('initialize',{'clientInfo':{'name':'agent_context_bridge','version':'0.2.0'},'capabilities':{'experimentalApi':True}});self.send({'method':'initialized'})
  except BaseException:self.close();raise
 def send(self,o):self.p.stdin.write(json.dumps(o)+'\n');self.p.stdin.flush()
 def receive(self,deadline):
  if time.monotonic()>=deadline:raise TimeoutError('Codex app-server timed out')
  try:o=self.events.get(timeout=max(.01,deadline-time.monotonic()))
  except queue.Empty:raise TimeoutError('Codex app-server timed out')
  if o is None:raise RuntimeError('Codex app-server exited')
  return o
 def call(self,method,params):
  self.n+=1;i=self.n;self.send({'id':i,'method':method,'params':params});deadline=time.monotonic()+self.timeout
  while True:
   o=self.receive(deadline)
   if o.get('id')==i:
    if 'error'in o:raise RuntimeError(str(o['error']))
    return o['result']
   if 'method' in o:self.pending.append(o)
 def import_session(self,path,cwd):
  r=self.call('externalAgentConfig/import',{'migrationItems':[{'itemType':'SESSIONS','description':'Portable context import','cwd':cwd,'details':{'sessions':[{'path':str(path),'cwd':cwd}]}}]});deadline=time.monotonic()+self.timeout
  while True:
   o=self.pending.pop(0) if self.pending else self.receive(deadline)
   if o.get('method')=='externalAgentConfig/import/completed' and o['params'].get('importId')==r['importId']:
    results=o['params']['itemTypeResults'];fail=[f for x in results for f in x['failures']];ok=[s for x in results for s in x['successes']]
    if fail or not ok:raise RuntimeError('Native import failed: '+json.dumps(fail))
    return ok[0]['target']
 def messages(self,thread_id):
  d={'messages':[],'warnings':['Tool calls preserved as historical text; private reasoning omitted'],'cwd':'','id':thread_id}
  meta=self.call('thread/read',{'threadId':thread_id,'includeTurns':False});d['cwd']=meta['thread']['cwd'];cursor=None;seen=set();legacy=False
  while True:
   try:r=self.call('thread/items/list',{'threadId':thread_id,'sortDirection':'asc','limit':100,'cursor':cursor})
   except RuntimeError as exc:
    if cursor is not None or '-32601' not in str(exc) or meta['thread'].get('historyMode')!='legacy':raise
    old=self.call('thread/read',{'threadId':thread_id,'includeTurns':True})
    turns=old['thread'].get('turns',[])
    if any(t.get('itemsView')!='full' for t in turns):raise RuntimeError('Legacy history returned incomplete items')
    r={'data':[{'item':item} for turn in turns for item in turn['items']],'nextCursor':None};legacy=True
   for entry in r['data']:
    item=entry['item'];t=item.get('type')
    if t=='agentMessage':text=item.get('text','');role='assistant'
    elif t=='userMessage':
     from .codec import blocks
     text=blocks(item.get('content',[]),d['warnings']);role='user'
    elif t in ('reasoning','contextCompaction'):continue
    else:text='[Historical '+str(t)+']\n'+json.dumps(item,ensure_ascii=False);role='assistant'
    if text:d['messages'].append({'role':role,'text':text})
   cursor=r.get('nextCursor')
   if not cursor:break
   if cursor in seen:raise RuntimeError('Codex repeated a history cursor; refusing incomplete export')
   seen.add(cursor)
  return d
 def close(self):
  if self.p.poll() is None:
   self.p.terminate()
   try:self.p.wait(timeout=5)
   except subprocess.TimeoutExpired:self.p.kill();self.p.wait()
  for f in [self.p.stdin,self.p.stdout]:
   if f:f.close()
 def __enter__(self):return self
 def __exit__(self,*_):self.close()
