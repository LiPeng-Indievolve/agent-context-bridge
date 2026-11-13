import json,sqlite3,tempfile,unittest,uuid,subprocess
from pathlib import Path
from unittest.mock import patch
from bridge.engine import Engine
from bridge.switching import verify,finish_switch

class SwitchingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.cwd=self.root/'project with spaces';self.cwd.mkdir();self.cx=self.root/'codex';self.cx.mkdir();self.state=self.root/'state';self.state.mkdir();self.new=str(uuid.uuid4());self.old=str(uuid.uuid4());self.mid=str(uuid.uuid4());self.source=self.root/'source.jsonl';self.source.write_text('{}\n');self.bundle=self.state/'bundle';self.bundle.mkdir()
  self.r={'migration_id':self.mid,'key':'key','status':'completed','mode':'working_context','source':'claude','source_id':'source-id','target':'codex','target_id':self.new,'cwd':str(self.cwd),'bundle':str(self.bundle),'created':2,'working_context':{'source_path':str(self.source),'source_sha256':'original-hash'}}
  self.e=Engine(self.root/'cc',self.cx,self.state);self.e.save([self.r]);self.db=self.cx/'state_5.sqlite';c=sqlite3.connect(self.db);c.execute('create table threads(id text primary key,archived integer)');c.executemany('insert into threads values(?,?)',[(self.old,0),(self.new,0)]);c.commit();c.close();(self.cx/'external_agent_session_imports.json').write_text(json.dumps({'records':[{'source_path':str(self.source),'content_sha256':'original-hash','imported_thread_id':self.old,'imported_at':1}]}))
 def tearDown(self):self.temp.cleanup()
 def passed(self):
  r=self.e.journal();r[0]['runtime_verification']={'status':'passed','target_id':self.new};self.e.save(r)
 def test_dry_run_does_not_archive_and_apply_requires_real_verification(self):
  p=finish_switch(self.e,self.mid);self.assertEqual(p['old_thread_ids'],[self.old]);self.assertFalse(p['runtime_verified'])
  with self.assertRaisesRegex(ValueError,'verify'):finish_switch(self.e,self.mid,True)
 def test_exit_zero_without_completed_turn_is_not_pass(self):
  def fake(args,**kw):kw['stdout'].write(json.dumps({'type':'thread.started','thread_id':self.new})+'\n');return subprocess.CompletedProcess(args,0)
  with patch('bridge.switching.subprocess.run',side_effect=fake):r=verify(self.e,self.mid)
  self.assertEqual(r['runtime_verification']['status'],'failed');self.assertFalse(r['ready_to_use'])
 def test_real_completed_turn_and_exact_cwd_command(self):
  def fake(args,**kw):
   self.assertIn('--skip-git-repo-check',args);self.assertEqual(args[args.index('-C')+1],str(self.cwd));kw['stdout'].write(json.dumps({'type':'thread.started','thread_id':self.new})+'\n'+json.dumps({'type':'turn.completed'})+'\n');Path(args[args.index('-o')+1]).write_text('Understood the project and latest task.');return subprocess.CompletedProcess(args,0)
  with patch('bridge.switching.subprocess.run',side_effect=fake):r=verify(self.e,self.mid)
  self.assertEqual(r['runtime_verification']['status'],'passed');self.assertIn("'",r['resume_command'])
 def test_busy_old_thread_is_retained_with_exit_hint(self):
  self.passed()
  with patch('bridge.switching.subprocess.run',return_value=subprocess.CompletedProcess([],1,stdout='',stderr='already has an active writer')):r=finish_switch(self.e,self.mid,True)
  self.assertFalse(r['switch_complete']);self.assertIn('/exit',r['old_entries'][0]['hint']);self.assertTrue(self.source.exists())
 def test_archive_uses_cli_and_verifies_persisted_state(self):
  self.passed()
  def fake(args,**kw):
   self.assertEqual(args,['codex','archive',self.old]);self.assertEqual(Path(kw['env']['CODEX_HOME']).resolve(),self.cx.resolve());c=sqlite3.connect(self.db);c.execute('update threads set archived=1 where id=?',(self.old,));c.commit();c.close();return subprocess.CompletedProcess(args,0,stdout='Archived',stderr='')
  with patch('bridge.switching.subprocess.run',side_effect=fake):r=finish_switch(self.e,self.mid,True)
  self.assertTrue(r['switch_complete']);self.assertTrue(self.source.exists())
 def test_stale_or_other_source_registry_is_not_archived(self):
  p=self.cx/'external_agent_session_imports.json';d=json.loads(p.read_text());d['records'][0]['content_sha256']='different';p.write_text(json.dumps(d));self.assertEqual(finish_switch(self.e,self.mid)['old_thread_ids'],[])

 def test_success_exit_without_archive_state_change_is_not_complete(self):
  self.passed()
  with patch('bridge.switching.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='OK',stderr='')):r=finish_switch(self.e,self.mid,True)
  self.assertFalse(r['switch_complete'])
 def test_verification_for_another_target_cannot_archive(self):
  records=self.e.journal();records[0]['runtime_verification']={'status':'passed','target_id':str(uuid.uuid4())};self.e.save(records)
  with self.assertRaises(ValueError):finish_switch(self.e,self.mid,True)

 def test_older_migration_cannot_archive_newer_working_target(self):
  self.passed();records=self.e.journal();newer=dict(records[0],migration_id=str(uuid.uuid4()),target_id=str(uuid.uuid4()),created=3);records.append(newer);self.e.save(records)
  plan=finish_switch(self.e,self.mid);self.assertNotIn(newer['target_id'],plan['old_thread_ids'])
  with self.assertRaisesRegex(ValueError,'newer'):finish_switch(self.e,self.mid,True)
 def test_future_native_import_is_not_archived(self):
  p=self.cx/'external_agent_session_imports.json';d=json.loads(p.read_text());d['records'][0]['imported_at']=3;p.write_text(json.dumps(d));self.assertEqual(finish_switch(self.e,self.mid)['old_thread_ids'],[])
 def test_verify_disables_hooks_plugins_apps_and_configured_mcp(self):
  (self.cx/'config.toml').write_text('[mcp_servers.danger]\ncommand="do-not-run"\n');project=self.cwd/'.codex';project.mkdir();(project/'config.toml').write_text('[mcp_servers.project_tool]\ncommand="do-not-run"\n')
  def fake(args,**kw):
   self.assertIn('--no-daemon',args);self.assertIn('--ignore-user-config',args)
   for name in ['hooks','plugins','apps','shell_tool']:self.assertIn(name,[args[i+1]for i,a in enumerate(args[:-1])if a=='--disable'])
   self.assertIn('mcp_servers."danger"={command="/usr/bin/false",enabled=false}',args);self.assertIn('mcp_servers."project_tool"={command="/usr/bin/false",enabled=false}',args)
   return subprocess.CompletedProcess(args,1)
  with patch('bridge.switching.subprocess.run',side_effect=fake):verify(self.e,self.mid)

 def test_resume_command_preserves_custom_codex_home(self):
  from bridge.switching import resume_command
  import shlex
  args=shlex.split(resume_command(self.r,self.cx));self.assertEqual(args[:2],['env','CODEX_HOME='+str(self.cx.resolve())]);self.assertEqual(args[-1],self.new)

 def test_custom_provider_is_not_silently_verified_as_openai(self):
  (self.cx/'config.toml').write_text('model_provider="custom"\n')
  with patch('bridge.switching.subprocess.run')as run:
   with self.assertRaisesRegex(ValueError,'OpenAI'):verify(self.e,self.mid)
   run.assert_not_called()
 def test_same_second_registry_timestamp_is_not_observably_older(self):
  records=self.e.journal();records[0]['created']=1.5;self.e.save(records);self.assertEqual(finish_switch(self.e,self.mid)['old_thread_ids'],[])

 def test_unconfirmed_related_entry_is_not_reported_as_finished(self):
  self.passed();records=self.e.journal();records[0]['created']=1.5;self.e.save(records)
  with patch('bridge.switching.subprocess.run')as run:r=finish_switch(self.e,self.mid,True);run.assert_not_called()
  self.assertFalse(r['switch_complete']);self.assertEqual(r['old_entries'][0]['status'],'unconfirmed')
 def test_new_failed_attempt_invalidates_older_verification(self):
  self.passed();(self.cx/'config.toml').write_text('model_provider="custom"\n')
  with self.assertRaises(ValueError):verify(self.e,self.mid)
  self.assertEqual(self.e.journal()[0]['runtime_verification']['status'],'failed')

 def test_default_home_is_explicit_even_with_different_ambient_home(self):
  from bridge.switching import resume_command
  import shlex
  with patch.dict('os.environ',{'CODEX_HOME':'/different/store'}):args=shlex.split(resume_command(self.r,Path.home()/'.codex'))
  self.assertEqual(args[1],'CODEX_HOME='+str((Path.home()/'.codex').resolve()))
