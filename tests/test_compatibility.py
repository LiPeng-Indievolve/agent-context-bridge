import json,tempfile,unittest
from pathlib import Path
from bridge.codec import read_claude
from bridge.engine import Engine
from bridge.rpc import RPC

class CompatibilityTests(unittest.TestCase):
 def test_scalar_rows_are_ignored(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'session.jsonl';p.write_text('null\n42\n'+json.dumps({'type':'user','message':{'role':'user','content':'hello'}})+'\n')
   d=read_claude(p);self.assertEqual(d['messages'],[{'role':'user','text':'hello'}]);self.assertTrue(d['warnings'])
 def test_claude_project_encoding(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);project=root/'project.name with_space';project.mkdir();src=root/'src.jsonl';src.write_text(json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'hello'}]}}))
   result=Engine(root/'cc',root/'cx',root/'state').migrate({'source':'codex','id':'x','path':str(src),'cwd':str(project)},'claude',True)
   self.assertNotIn('.',Path(result['target_path']).parent.name);self.assertNotIn(' ',Path(result['target_path']).parent.name);self.assertNotIn('_',Path(result['target_path']).parent.name)
 def test_rpc_full_pagination_and_user_content(self):
  rpc=object.__new__(RPC);seen=[]
  def call(method,params):
   seen.append((method,params))
   if method=='thread/read':return {'thread':{'cwd':'/project'}}
   if not params.get('cursor'):return {'data':[{'item':{'type':'userMessage','content':[{'type':'text','text':'hello'}]},'turnId':'t'}],'nextCursor':'p2'}
   return {'data':[{'item':{'type':'agentMessage','text':'world'},'turnId':'t'}],'nextCursor':None}
  rpc.call=call
  self.assertEqual(rpc.messages('id')['messages'],[{'role':'user','text':'hello'},{'role':'assistant','text':'world'}]);self.assertEqual(seen[-1][1]['cursor'],'p2')
 def test_assistant_shared_message_ids_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.jsonl';p.write_text('\n'.join(json.dumps({'type':'assistant','uuid':str(i),'message':{'id':'shared','role':'assistant','content':[{'type':'text','text':str(i)}]}}) for i in range(2)))
   self.assertEqual(len(read_claude(p)['messages']),2)

class RPCRegressionTests(unittest.TestCase):
 def test_import_completion_before_response_is_not_lost(self):
  rpc=object.__new__(RPC);rpc.n=0;rpc.timeout=1;rpc.pending=[];rpc.send=lambda o:None
  messages=iter([{'method':'externalAgentConfig/import/completed','params':{'importId':'i','itemTypeResults':[{'itemType':'SESSIONS','failures':[],'successes':[{'target':'target'}]}]}},{'id':1,'result':{'importId':'i'}}])
  rpc.receive=lambda deadline:next(messages)
  self.assertEqual(rpc.import_session('/fixture','/project'),'target')
 def test_repeated_cursor_is_rejected(self):
  rpc=object.__new__(RPC)
  rpc.call=lambda method,params: {'thread':{'cwd':'/project'}} if method=='thread/read' else {'data':[],'nextCursor':'repeated'}
  # Stop the unfixed implementation rather than hanging the test process.
  original=rpc.call;calls=[0]
  def bounded(method,params):
   calls[0]+=1
   if calls[0]>5:raise AssertionError('pagination did not stop')
   return original(method,params)
  rpc.call=bounded
  with self.assertRaises(RuntimeError):rpc.messages('id')

class ContextLossTests(unittest.TestCase):
 def test_sidechains_and_branches_are_reported(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.jsonl';rows=[{'type':'user','uuid':'root','message':{'content':'question'}},{'type':'assistant','uuid':'a','parentUuid':'root','message':{'content':'option one'}},{'type':'assistant','uuid':'b','parentUuid':'root','message':{'content':'option two'}},{'type':'assistant','uuid':'sub','isSidechain':True,'message':{'content':'private subagent'}}];p.write_text('\n'.join(json.dumps(x) for x in rows))
   result=read_claude(p);warnings=' '.join(result['warnings']).lower();self.assertIn('branch',warnings);self.assertIn('sidechain',warnings);self.assertEqual(len(result['messages']),3)

class NativeVersionTests(unittest.TestCase):
 def test_legacy_full_read_fallback(self):
  rpc=object.__new__(RPC)
  def call(method,params):
   if method=='thread/items/list':raise RuntimeError("{'code': -32601}")
   if not params['includeTurns']:return {'thread':{'cwd':'/project','historyMode':'legacy'}}
   return {'thread':{'turns':[{'itemsView':'full','items':[{'type':'userMessage','content':[{'type':'text','text':'legacy question'}]}]}]}}
  rpc.call=call;self.assertEqual(rpc.messages('id')['messages'],[{'role':'user','text':'legacy question'}])
 def test_paged_history_never_uses_legacy_fallback(self):
  rpc=object.__new__(RPC)
  def call(method,params):
   if method=='thread/items/list':raise RuntimeError("{'code': -32601}")
   return {'thread':{'cwd':'/project','historyMode':'paginated'}}
  rpc.call=call
  with self.assertRaises(RuntimeError):rpc.messages('id')
 def test_temporary_stage_is_removed_after_import_error(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);project=root/'project';project.mkdir();src=root/'s.jsonl';src.write_text(json.dumps({'type':'user','message':{'content':'question'}}))
   class FailedRPC:
    def __init__(self,*a,**kw):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def import_session(self,path,cwd):
     self.stage=Path(path);assert self.stage.exists();raise RuntimeError('test import failure')
   from bridge.codec import project_key
   existing=root/'home/.claude/projects'/project_key(project.resolve());existing.mkdir(parents=True);original=existing/'original.jsonl';original.write_text('keep original')
   with patch('bridge.engine.RPC',FailedRPC),patch('bridge.engine.pathlib.Path.home',return_value=root/'home'):
    with self.assertRaises(RuntimeError):Engine(root/'cc',root/'cx',root/'state').migrate({'source':'claude','id':'s','path':str(src),'cwd':str(project)},'codex',True)
   self.assertEqual(list((root/'home/.claude').rglob('*.jsonl')),[original]);self.assertEqual(original.read_text(),'keep original');self.assertTrue(src.exists())
