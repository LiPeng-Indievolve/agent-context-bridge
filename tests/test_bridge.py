import unittest,tempfile,json
from pathlib import Path
from bridge.codec import read_claude,read_codex,write_claude
from bridge.scan import scan
from bridge.engine import Engine

class BridgeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.cc=self.root/'claude';self.cx=self.root/'codex';self.state=self.root/'state';self.cwd=self.root/'project';self.cwd.mkdir()
 def tearDown(self):self.tmp.cleanup()
 def fixture(self):
  p=self.cc/'projects'/'-project'/'abc.jsonl';p.parent.mkdir(parents=True)
  p.write_text('\n'.join(json.dumps(o) for o in [{'type':'user','uuid':'u1','cwd':str(self.cwd),'message':{'role':'user','content':'Build scanner; keep old decisions'}},{'type':'assistant','uuid':'a1','parentUuid':'u1','cwd':str(self.cwd),'message':{'role':'assistant','content':[{'type':'text','text':'Use a local index'},{'type':'tool_use','name':'Read','input':{'path':'README.md'}}]}},{'type':'user','uuid':'u2','parentUuid':'a1','cwd':str(self.cwd),'message':{'role':'user','content':[{'type':'tool_result','tool_use_id':'t','content':'Project background'}]}}])+'\n{bad json\n')
  return p
 def test_scan_uses_native_metadata(self):
  self.fixture();items=scan(self.cc,self.cx,[]);self.assertEqual(len(items),1);self.assertEqual(items[0]['cwd'],str(self.cwd));self.assertEqual(items[0]['id'],'abc')
 def test_portable_roundtrip(self):
  p=self.fixture();doc=read_claude(p);self.assertEqual(len(doc['messages']),3);self.assertTrue(doc['warnings']);self.assertIn('Read',doc['messages'][1]['text']);out=self.root/'converted.jsonl';write_claude(doc,out,'new',str(self.cwd));again=read_claude(out);self.assertEqual(doc['messages'],again['messages'])
 def test_codex_ignores_ui_duplicates(self):
  p=self.root/'cx.jsonl';p.write_text('\n'.join(json.dumps(o) for o in [{'type':'session_meta','payload':{'id':'c','cwd':str(self.cwd)}},{'type':'event_msg','payload':{'type':'user_message','message':'duplicate'}},{'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'actual'}]}}]))
  self.assertEqual(read_codex(p)['messages'],[{'role':'user','text':'actual'}])
 def test_transfer_idempotent_and_rollback(self):
  p=self.root/'source.jsonl';p.write_text(json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'remember blue'}]}})+'\n');item={'source':'codex','id':'cx1','path':str(p),'cwd':str(self.cwd),'title':'test'}
  e=Engine(self.cc,self.cx,self.state);r=e.migrate(item,'claude',True);self.assertTrue(Path(r['target_path']).exists());self.assertEqual(e.migrate(item,'claude',True)['status'],'already_migrated');e.rollback(r['migration_id']);self.assertFalse(Path(r['target_path']).exists())
 def test_rollback_refuses_modified_target(self):
  p=self.root/'source.jsonl';p.write_text(json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'x'}]}}));item={'source':'codex','id':'cx1','path':str(p),'cwd':str(self.cwd),'title':'test'};e=Engine(self.cc,self.cx,self.state);r=e.migrate(item,'claude',True);Path(r['target_path']).write_text('changed')
  with self.assertRaises(ValueError):e.rollback(r['migration_id'])
if __name__=='__main__':unittest.main()

class MetadataOnlyScanTests(unittest.TestCase):
 def test_runtime_metadata_is_not_a_conversation(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);p=root/'cc/projects/project/empty.jsonl';p.parent.mkdir(parents=True);p.write_text(json.dumps({'type':'cost-state','cwd':str(root)})+'\n'+json.dumps({'type':'user','message':{'content':42}})+'\n');self.assertEqual(scan(root/'cc',root/'cx',[]),[])
