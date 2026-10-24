import json,threading,unittest
from unittest.mock import Mock,patch
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from server import Handler
class PrerequisiteHTTPTests(unittest.TestCase):
 def setUp(self):
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.token='fixture-session-token';self.server.settings=Mock();self.server.prerequisites=Mock()
  self.server.prerequisites.start_plan.return_value={'id':'plan1','status':'planning'}
  self.server.prerequisites.install.return_value={'id':'plan1','status':'installing'}
  self.server.prerequisites.cancel.return_value={'id':'plan1','status':'cancelled'}
  self.server.prerequisites.status.return_value={'id':'plan1','status':'ready','items':[]}
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
 def request(self,route,body=None,auth=True,origin=None):
  headers={'Content-Type':'application/json'}
  if auth:headers['X-DAMN-Token']=self.server.token
  if origin:headers['Origin']=origin
  payload=json.dumps(body).encode() if body is not None else None
  # Authentication is rejected before body parsing; no unread upload on Windows.
  if payload is not None and (not auth or origin):payload=b''
  req=Request('http://127.0.0.1:'+str(self.server.server_port)+route,data=payload,headers=headers)
  with urlopen(req,timeout=3) as response:return json.load(response)
 def test_status_and_every_mutation_require_the_local_session(self):
  for route,body in [('/api/prerequisites/status?id=plan1',None),('/api/prerequisites/plan',{'path':'fixture'}),('/api/prerequisites/install',{'id':'plan1','itemIds':['one']}),('/api/prerequisites/cancel',{'id':'plan1'})]:
   with self.subTest(route=route),self.assertRaises(HTTPError) as error:self.request(route,body,False)
   self.assertEqual(error.exception.code,403)
  self.server.prerequisites.start_plan.assert_not_called();self.server.prerequisites.install.assert_not_called()
 def test_plan_is_independent_of_ai_configuration(self):
  with patch('server.ai_request') as ai:
   result=self.request('/api/prerequisites/plan',{'path':'fixture','side':'server','gameVersion':'1.21.1','loader':'NeoForge'})
   self.assertEqual(result['status'],'planning');ai.assert_not_called();self.server.settings.credentials.assert_not_called()
  self.server.prerequisites.start_plan.assert_called_once_with('fixture',side='server',game_version='1.21.1',loader='NeoForge',loader_version='')
 def test_install_only_uses_saved_plan_and_selected_ids(self):
  result=self.request('/api/prerequisites/install',{'id':'plan1','itemIds':['one'],'url':'https://evil.invalid','path':'outside'})
  self.assertEqual(result['status'],'installing');self.server.prerequisites.install.assert_called_once_with('plan1',['one'])
  for ids in [[],['one','one'],[{}],'all']:
   with self.assertRaises(HTTPError) as error:self.request('/api/prerequisites/install',{'id':'plan1','itemIds':ids})
   self.assertEqual(error.exception.code,400)
 def test_status_missing_plan_and_untrusted_origin(self):
  self.server.prerequisites.status.side_effect=ValueError('task not found')
  with self.assertRaises(HTTPError) as error:self.request('/api/prerequisites/status?id=unknown')
  self.assertEqual(error.exception.code,400);self.assertEqual(json.load(error.exception)['code'],'job_not_found')
  with self.assertRaises(HTTPError) as error:self.request('/api/prerequisites/cancel',{'id':'plan1'},origin='https://evil.invalid')
  self.assertEqual(error.exception.code,403)
if __name__=='__main__':unittest.main()
