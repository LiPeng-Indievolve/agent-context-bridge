import json,tempfile,unittest,stat
from pathlib import Path
from bridge.handoff import prepare,search
class HandoffTests(unittest.TestCase):
 def test_huge_history_is_bounded_and_latest_task_retained(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);p=r/'session.jsonl';records=[{'type':'user','cwd':'/demo','isCompactSummary':True,'message':{'content':'OLD SUMMARY'}}]
   records += [{'type':'assistant','message':{'content':[{'type':'text','text':'old report '+('旧'*10000)},{'type':'tool_result','content':'DO NOT SEED TOOL '+('Z'*100000)}]}} for _ in range(30)]
   records += [{'type':'user','isCompactSummary':True,'message':{'content':'LATEST SUMMARY: offline scanner '+('summary '*9000)}},{'type':'user','message':{'content':'LATEST TASK: implement selective filter'}}]
   p.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in records));d=prepare(p,r/'out',seed='种'*20000);s=Path(d['handoff_path']).read_text();self.assertLessEqual(d['bytes'],49152);self.assertEqual(d['bytes'],len(s.encode()));self.assertIn('LATEST TASK',s);self.assertIn('LATEST SUMMARY',s);self.assertNotIn('OLD SUMMARY',s);self.assertNotIn('DO NOT SEED TOOL',s);self.assertGreater(d['omitted_messages'],0);self.assertEqual(d['cwd'],'/demo');self.assertEqual(len(search(d['index_path'],'DO NOT SEED TOOL',limit=2)),2)
 def test_latest_task_tail_survives_oversized_message(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.jsonl';p.write_text(json.dumps({'type':'user','message':{'content':'start '+('旧'*50000)+' LAST IMPORTANT REQUEST'}}));d=prepare(p,Path(td)/'out');self.assertIn('LAST IMPORTANT REQUEST',Path(d['handoff_path']).read_text());self.assertLessEqual(d['bytes'],49152)
 def test_no_silent_empty_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.jsonl';p.write_text(json.dumps({'type':'assistant','message':{'content':[{'type':'thinking','thinking':'private'}]}}))
   with self.assertRaisesRegex(ValueError,'plain-text'):prepare(p,Path(td)/'out')
 def test_source_unchanged_snapshot_searchable_and_lines_exact(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.jsonl';raw='bad json\n'+json.dumps({'type':'user','cwd':'/safe','message':{'content':'find uniqueNeedle'}})+'\n';p.write_text(raw);d=prepare(p,Path(td)/'out');self.assertEqual(p.read_text(),raw);self.assertEqual(Path(d['archive_path']).read_text(),raw);self.assertEqual(search(d['index_path'],'uniqueNeedle')[0]['source_line'],2);self.assertTrue(d['warnings'])
 def test_budget_and_private_permissions(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.jsonl';p.write_text(json.dumps({'type':'user','message':{'content':'latest task'}}));d=prepare(p,Path(td)/'out',max_bytes=2048);self.assertLessEqual(d['bytes'],2048)
   for name in ('handoff_path','archive_path','index_path','metadata_path'):self.assertEqual(stat.S_IMODE(Path(d[name]).stat().st_mode),0o600)
   with self.assertRaises(ValueError):prepare(p,Path(td)/'too-big',max_bytes=49153)
   with self.assertRaises(ValueError):search(d['index_path'],'')
