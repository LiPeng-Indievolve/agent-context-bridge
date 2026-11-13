import unittest
from bridge.web import allowed_request
class WebTests(unittest.TestCase):
 def test_reject_cross_origin(self):
  self.assertFalse(allowed_request('evil.example','http://evil.example','a','a',8080))
  self.assertFalse(allowed_request('127.0.0.1:8080','http://evil.example','a','a',8080))
 def test_require_token(self):
  self.assertFalse(allowed_request('127.0.0.1:8080',None,'bad','good',8080))
  self.assertTrue(allowed_request('127.0.0.1:8080','http://127.0.0.1:8080','good','good',8080))
