import json,tempfile,threading,time,unittest
from unittest.mock import Mock,patch
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit
import identity
from server import Handler

class IdentityHTTPTests(unittest.TestCase):
 def setUp(self):
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.token='fixture-identity-session';self.server.settings=Mock();self.server.identities=Mock()
  for method in ('start','status','search','confirm','clear','cancel'):getattr(self.server.identities,method).return_value={'id':'identity1','status':'complete','items':[]}
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
 def request(self,route,body=None,auth=True,origin=None):
  headers={'Content-Type':'application/json'}
  if auth:headers['X-DAMN-Token']=self.server.token
  if origin:headers['Origin']=origin
  payload=json.dumps(body).encode() if body is not None else None
  if payload is not None and (not auth or origin):payload=b''
  req=Request('http://127.0.0.1:'+str(self.server.server_port)+route,data=payload,headers=headers)
  with urlopen(req,timeout=3) as response:return json.load(response)
 def test_status_and_all_changes_require_local_session_and_origin(self):
  actions=[('/api/identity/status?id=identity1',None),('/api/identity/check',{'mods':[]}),('/api/identity/search',{'id':'identity1','key':'m0','query':'mod'}),('/api/identity/confirm',{'id':'identity1','key':'m0','candidateId':'candidate'}),('/api/identity/clear',{'id':'identity1','key':'m0'}),('/api/identity/cancel',{'id':'identity1'})]
  for route,body in actions:
   for auth,origin in ((False,None),(True,'https://untrusted.invalid')):
    with self.subTest(route=route,origin=origin),self.assertRaises(HTTPError) as error:self.request(route,body,auth,origin)
    self.assertEqual(error.exception.code,403)
  self.assertFalse(self.server.identities.mock_calls)
 def test_check_is_independent_of_ai_and_other_uploaded_fields(self):
  mods=[{'key':'m0','name':'Example','sha256':'a'*64,'sha1':'b'*40}]
  with patch('server.ai_request') as ai:
   self.assertEqual(self.request('/api/identity/check',{'mods':mods,'apiKey':'not-used','endpoint':'https://untrusted.invalid'})['id'],'identity1');ai.assert_not_called();self.server.settings.credentials.assert_not_called()
  self.server.identities.start.assert_called_once_with(mods)
 def test_search_limits_query_and_platform_and_keeps_candidate_selection_separate(self):
  self.request('/api/identity/search',{'id':'identity1','key':'m0','query':'  corrected title  ','site':'Modrinth'})
  self.server.identities.search.assert_called_once_with('identity1','m0','corrected title','modrinth');self.server.identities.confirm.assert_not_called()
  self.request('/api/identity/search',{'id':'identity1','key':'m0','query':'title','site':'curseforge'});self.assertEqual(self.server.identities.search.call_args.args[-1],'curseforge')
  for bad in ({'query':''},{'query':'a'*501},{'query':{}},{'query':'ok','site':'https://untrusted.invalid'}):
   with self.assertRaises(HTTPError) as error:self.request('/api/identity/search',{'id':'identity1','key':'m0',**bad})
   self.assertEqual(error.exception.code,400)
 def test_confirm_only_forwards_saved_candidate_reference_not_project_url(self):
  self.request('/api/identity/confirm',{'id':'identity1','key':'m0','candidateId':'candidate1','projectId':'injected','url':'https://untrusted.invalid','exact':True,'versionId':'injected'})
  self.server.identities.confirm.assert_called_once_with('identity1','m0','candidate1')
  for bad in ({'id':''},{'key':{}},{'candidateId':{}}):
   with self.assertRaises(HTTPError) as error:self.request('/api/identity/confirm',{'id':'identity1','key':'m0','candidateId':'candidate1',**bad})
   self.assertEqual(error.exception.code,400)
 def test_clear_cancel_and_expired_job(self):
  self.request('/api/identity/clear',{'id':'identity1','key':'m0'});self.server.identities.clear.assert_called_once_with('identity1','m0')
  self.request('/api/identity/cancel',{'id':'identity1'});self.server.identities.cancel.assert_called_once_with('identity1')
  self.server.identities.status.side_effect=ValueError('expired')
  with self.assertRaises(HTTPError) as error:self.request('/api/identity/status?id=unknown')
  self.assertEqual(error.exception.code,400);self.assertEqual(json.load(error.exception)['code'],'job_not_found')

 def enable_real_identity_manager(self):
  """Exercise HTTP validation and real manager validation with an offline API."""
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
  self.identity_fetch=Mock(side_effect=self.fake_identity_fetch)
  fetch_patch=patch.object(identity.research,'fetch',self.identity_fetch);fetch_patch.start();self.addCleanup(fetch_patch.stop)
  self.cf_key_getter=Mock(return_value='')
  self.real_identities=identity.IdentityManager(temp.name,self.cf_key_getter);self.addCleanup(self.real_identities.close)
  self.server.identities=self.real_identities
  mods=[{'key':'m0','name':'Example Mod','file':'renamed.jar','sha1':'a'*40,'sha256':'b'*64,
         'components':[{'id':'example','name':'Example Mod','version':'1.0'}]}]
  state=self.request('/api/identity/check',{'mods':mods})
  self.wait_http_identity(state['id'])
  self.identity_fetch.reset_mock();self.cf_key_getter.reset_mock()
  return state['id']

 @staticmethod
 def fake_identity_fetch(url,key=None,payload=None):
  if key:raise AssertionError('HTTP identity fixtures must never use an API key')
  parsed=urlsplit(url)
  if parsed.hostname not in ('api.modrinth.com','mod.mcimirror.top'):
   raise AssertionError('Unexpected non-fixture identity host: '+url)
  project={'id':'original','title':'Example Mod','project_type':'mod','description':'Fixture project'}
  if parsed.path=='/v2/version_files':return '{}'
  if parsed.path in ('/v2/search','/modrinth/v2/search'):
   return json.dumps({'hits':[{'project_id':'original','title':'Example Mod','project_type':'mod'}]})
  if parsed.path in ('/v2/project/original','/modrinth/v2/project/original'):return json.dumps(project)
  if parsed.path=='/curseforge/v1/mods/search':
   return json.dumps({'data':[{'id':123,'name':'CF Example','slug':'example','gameId':432,'classId':6}]})
  raise AssertionError('Unexpected identity fixture endpoint: '+url)

 def wait_http_identity(self,ident):
  deadline=time.monotonic()+3
  while time.monotonic()<deadline:
   state=self.request('/api/identity/status?id='+ident)
   if state['status']!='running' and not any(row['searching'] for row in state['items']):return state
   time.sleep(.005)
  self.fail('HTTP identity fixture did not finish')

 def test_mcim_case_insensitive_http_search_reaches_real_manager_without_key(self):
  ident=self.enable_real_identity_manager()
  for site in ('MCIM','mCiM'):
   with self.subTest(site=site),patch.object(self.real_identities,'search',wraps=self.real_identities.search) as search:
    self.identity_fetch.reset_mock();self.cf_key_getter.reset_mock()
    self.request('/api/identity/search',{'id':ident,'key':'m0','query':'Example Mod','site':site})
    state=self.wait_http_identity(ident)
    search.assert_called_once_with(ident,'m0','Example Mod','mcim')
    row=state['items'][0]
    self.assertEqual({candidate['site'] for candidate in row['candidates']},{'Modrinth','CurseForge'})
    self.assertTrue(all(candidate['provider']=='MCIM' for candidate in row['candidates']))
    self.assertEqual({urlsplit(call.args[0]).hostname for call in self.identity_fetch.call_args_list},{'mod.mcimirror.top'})
    self.assertTrue(all(not (call.args[1] if len(call.args)>1 else call.kwargs.get('key')) for call in self.identity_fetch.call_args_list))
    self.cf_key_getter.assert_not_called();self.server.settings.credentials.assert_not_called()

 def test_long_valid_official_project_url_passes_http_and_real_manager_untruncated(self):
  ident=self.enable_real_identity_manager()
  prefix='https://modrinth.com/mod/original?source='
  query=prefix+'x'*(500-len(prefix))
  self.assertGreater(len(query),200);self.assertEqual(len(query),500)
  with patch.object(self.real_identities,'search',wraps=self.real_identities.search) as search:
   self.request('/api/identity/search',{'id':ident,'key':'m0','query':query,'site':'Modrinth'})
   state=self.wait_http_identity(ident)
   search.assert_called_once_with(ident,'m0',query,'modrinth')
  row=state['items'][0]
  self.assertEqual(row['query'],query)
  self.assertEqual([candidate['projectId'] for candidate in row['candidates']],['original'])
  self.assertEqual([call.args[0] for call in self.identity_fetch.call_args_list],[identity.MR+'/project/original'])
  self.cf_key_getter.assert_not_called();self.server.settings.credentials.assert_not_called()

 def test_http_and_manager_reject_invalid_urls_lengths_and_platforms_before_fetch(self):
  ident=self.enable_real_identity_manager()
  prefix='https://modrinth.com/mod/original?source='
  invalid=[{'query':'https://modrinth.com.evil.test/mod/original'},
           {'query':'https://user:password@modrinth.com/mod/original'},
           {'query':'https://example.test/mod/original'},
           {'query':'a'*121},
           {'query':prefix+'x'*(501-len(prefix))},
           {'query':'Example Mod','site':'unknown'},
           {'query':'Example Mod','site':['mcim']}]
  for values in invalid:
   with self.subTest(values=values),self.assertRaises(HTTPError) as error:
    self.request('/api/identity/search',{'id':ident,'key':'m0','site':'all',**values})
   self.assertEqual(error.exception.code,400)
  self.identity_fetch.assert_not_called();self.cf_key_getter.assert_not_called()
  self.server.settings.credentials.assert_not_called()

if __name__=='__main__':unittest.main()
