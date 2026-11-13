import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from bridge.engine import Engine
from bridge.codec import read_claude
class WorkingMigrationTests(unittest.TestCase):
 def test_default_is_bounded_and_full_history_is_distinct(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);cwd=root/'project';cwd.mkdir();(cwd/'CLAUDE.md').write_text('private architecture '+('memory '*20000));source=root/'source.jsonl'
   source.write_text('\n'.join(json.dumps(x) for x in [{'type':'assistant','message':{'content':[{'type':'tool_result','content':'huge tool output '+('X'*200000)}]}},{'type':'user','message':{'content':'LATEST TASK: implement filter'}}]))
   captures=[]
   class FakeRPC:
    def __init__(self,*a,**kw):pass
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def import_session(self,path,cwd):captures.append(read_claude(path));return 'synthetic-'+str(len(captures))
    def call(self,*a,**kw):return {'thread':{'path':'/synthetic/thread'}}
   engine=Engine(root/'cc',root/'cx',root/'state');item={'source':'claude','id':'fixture','path':str(source),'cwd':str(cwd)}
   with patch('bridge.engine.RPC',FakeRPC),patch('bridge.engine.pathlib.Path.home',return_value=root/'home'):
    normal=engine.migrate(item,'codex',True);self.assertEqual(len(captures[0]['messages']),2);self.assertLess(len(captures[0]['messages'][0]['text']),180);self.assertLessEqual(sum(len(m['text'].encode()) for m in captures[0]['messages']),49152);self.assertIn('LATEST TASK','\n'.join(m['text'] for m in captures[0]['messages']));self.assertNotIn('huge tool output','\n'.join(m['text'] for m in captures[0]['messages']));self.assertEqual(Path(normal['working_context']['archive_path']).read_text(),source.read_text());self.assertTrue(Path(normal['context_index_path']).exists())
    self.assertEqual(engine.migrate(item,'codex',True)['status'],'already_migrated')
    archive=engine.migrate(item,'codex',True,full_history=True);self.assertNotEqual(normal['migration_id'],archive['migration_id']);self.assertGreater(sum(len(m['text'].encode()) for m in captures[1]['messages']),200000);self.assertEqual(archive['mode'],'full_history')

 def test_large_multilingual_context_and_first_line_title_share_budget(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);cwd=root/'project';cwd.mkdir();source=root/'source.jsonl';source.write_text(json.dumps({'type':'user','cwd':str(cwd),'message':{'content':'start '+('旧'*100000)+' LAST REQUEST'}}));captures=[]
   class FakeRPC:
    def __init__(self,*a,**kw):pass
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def import_session(self,path,cwd):captures.append(read_claude(path));return 'synthetic'
    def call(self,*a,**kw):return {'thread':{'path':'/synthetic'}}
   with patch('bridge.engine.RPC',FakeRPC),patch('bridge.engine.pathlib.Path.home',return_value=root/'home'):
    Engine(root/'cc',root/'cx',root/'state').migrate({'source':'claude','id':'fixture','path':str(source),'cwd':str(cwd),'title':'人工标题\n'+('bad title '*1000)},'codex',True)
   messages=captures[0]['messages'];self.assertEqual(messages[0]['text'],'CC → Codex · 人工标题');self.assertIn('LAST REQUEST',messages[1]['text']);self.assertLessEqual(sum(len(m['text'].encode()) for m in messages),49152)
