import unittest
from bridge.web import allowed_request
class WebTests(unittest.TestCase):
 def test_reject_cross_origin(self):
  self.assertFalse(allowed_request('evil.example','http://evil.example','a','a',8080))
  self.assertFalse(allowed_request('127.0.0.1:8080','http://evil.example','a','a',8080))
 def test_require_token(self):
  self.assertFalse(allowed_request('127.0.0.1:8080',None,'bad','good',8080))
  self.assertTrue(allowed_request('127.0.0.1:8080','http://127.0.0.1:8080','good','good',8080))

class SwitchingRoutes(unittest.TestCase):
 def test_missing_id_and_unknown_action_fail_before_engine(self):
  from bridge.web import switch_action
  with self.assertRaises(ValueError):switch_action(None,'/api/verify',{})
  with self.assertRaises(ValueError):switch_action(None,'/api/unknown',{'id':'x'})
 def test_archive_requires_boolean_apply_and_uses_shared_engine(self):
  from bridge.web import switch_action
  from unittest.mock import patch
  engine=object()
  with patch('bridge.switching.finish_switch',return_value={'dry_run':True})as f:
   switch_action(engine,'/api/finish-switch',{'id':'x','apply':'true'});f.assert_called_once_with(engine,'x',False)
