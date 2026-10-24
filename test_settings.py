import io,json,secrets,tempfile,threading,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from settings import SettingsStore
from server import Handler
from test_damn import AIStub
class SettingsTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.store=SettingsStore(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_skip_persists_onboarding_without_api(self):
  self.assertFalse(self.store.public()['onboarded']);self.store.save({'defer':True})
  self.assertTrue(SettingsStore(self.tmp.name).public()['onboarded']);self.assertFalse(self.store.public()['configured'])
 def test_new_and_legacy_missing_auto_search_default_on(self):
  self.assertTrue(self.store.public()['autoSearch'])
  self.store.save({'defer':True});self.assertTrue(SettingsStore(self.tmp.name).public()['autoSearch'])
  self.store.save({'endpoint':'http://127.0.0.1:1/v1','model':'local'})
  self.assertTrue(SettingsStore(self.tmp.name).public()['autoSearch'])
  legacy=json.loads(self.store.file.read_text());legacy.pop('autoSearch');self.store.file.write_text(json.dumps(legacy))
  self.assertTrue(SettingsStore(self.tmp.name).public()['autoSearch'])
 def test_network_only_save_without_ai_configuration(self):
  with patch.object(self.store,'credentials',side_effect=AssertionError('blank optional AI must not require credentials')):
   saved=self.store.save({'defer':True,'autoSearch':True})
  self.assertTrue(saved['onboarded']);self.assertTrue(saved['autoSearch']);self.assertFalse(saved['configured']);self.assertTrue(saved['revision'])
  self.assertTrue(SettingsStore(self.tmp.name).public()['autoSearch'])
 def test_defer_network_update_preserves_credentials_and_old_skip_preserves_choice(self):
  self.store.save({'endpoint':'https://example.invalid/v1','model':'existing-model','apiKey':'fake-ai-key','curseForgeKey':'fake-cf-key','autoSearch':True})
  before=json.loads(self.store.file.read_text());saved=self.store.save({'defer':True,'autoSearch':False});after=json.loads(self.store.file.read_text())
  self.assertFalse(saved['autoSearch']);self.assertNotEqual(after['revision'],before['revision'])
  for field in ('endpoint','model','encryptedKey','encryptedCurseKey','origin'):self.assertEqual(after[field],before[field])
  self.assertEqual(self.store.credentials()['apiKey'],'fake-ai-key');self.assertEqual(self.store.read()['cfKey'],'fake-cf-key')
  self.store.save({'defer':True});skipped=json.loads(self.store.file.read_text());self.assertFalse(self.store.public()['autoSearch']);self.assertEqual(skipped['revision'],after['revision'])
  self.store.save({'endpoint':'https://example.invalid/v1','model':'another-model'})
  self.assertFalse(self.store.public()['autoSearch'],'a normal save without the switch preserves explicit false')
 def test_key_encrypted_and_not_in_public_response(self):
  key='test-only-not-a-real-api-key';self.store.save({'endpoint':'https://example.invalid/v1','model':'test-model','apiKey':key})
  self.assertNotIn(key,self.store.file.read_text());self.assertNotIn(key,json.dumps(self.store.public()))
  self.assertEqual(SettingsStore(self.tmp.name).credentials()['apiKey'],key)
 def test_unchanged_provider_keeps_key(self):
  self.store.save({'endpoint':'https://example.invalid/v1','model':'one','apiKey':'fake-key'})
  self.store.save({'endpoint':'https://example.invalid/v2','model':'two','apiKey':''})
  self.assertEqual(self.store.credentials()['apiKey'],'fake-key');self.assertEqual(self.store.public()['model'],'two')
 def test_changed_provider_cannot_reuse_key(self):
  self.store.save({'endpoint':'https://one.invalid/v1','model':'one','apiKey':'fake-key'})
  self.assertEqual(self.store.credentials({'endpoint':'https://two.invalid/v1','model':'two'})['apiKey'],'')
  self.store.save({'endpoint':'https://two.invalid/v1','model':'two'});self.assertFalse(self.store.public()['configured'])
 def test_clear_key_and_reconfigure(self):
  self.store.save({'endpoint':'https://example.invalid/v1','model':'one','apiKey':'fake-key'})
  self.store.save({'endpoint':'https://example.invalid/v1','model':'one','clearKey':True});self.assertFalse(self.store.public()['hasKey'])
 def test_corrupt_settings_returns_reconfiguration_state(self):
  self.store.file.write_text('{broken');self.assertFalse(self.store.public()['onboarded']);self.assertTrue(self.store.public()['error'])
 def test_auto_search_setting_persists(self):
  self.store.save({'endpoint':'http://127.0.0.1:1/v1','model':'local','autoSearch':True})
  self.assertTrue(SettingsStore(self.tmp.name).public()['autoSearch'])
  self.store.save({'endpoint':'http://127.0.0.1:1/v1','model':'local','autoSearch':False});self.assertFalse(self.store.public()['autoSearch'])
 def test_curse_key_is_encrypted_and_not_public(self):
  self.store.save({'endpoint':'http://127.0.0.1:1/v1','model':'local','curseForgeKey':'fake-cf-secret','autoSearch':True})
  self.assertNotIn('fake-cf-secret',self.store.file.read_text());self.assertNotIn('fake-cf-secret',json.dumps(self.store.public()))
  self.assertTrue(self.store.public()['hasCurseForgeKey']);self.store.save({'defer':True});self.assertNotIn('fake-cf-secret',self.store.file.read_text())
 def test_platform_key_can_be_saved_without_ai_configuration(self):
  with patch.object(self.store,'credentials',side_effect=AssertionError('AI settings must not be required')):
   public=self.store.save({'platformOnly':True,'curseForgeKey':'fake-platform-only-key'})
  self.assertFalse(public['configured']);self.assertTrue(public['hasCurseForgeKey'])
  self.assertNotIn('fake-platform-only-key',self.store.file.read_text());self.assertNotIn('fake-platform-only-key',json.dumps(public))
  self.assertEqual(SettingsStore(self.tmp.name).read()['cfKey'],'fake-platform-only-key')
 def test_platform_only_save_preserves_existing_ai_settings(self):
  self.store.save({'endpoint':'https://example.invalid/v1','model':'existing-model','apiKey':'fake-ai-key','autoSearch':True})
  before=json.loads(self.store.file.read_text())
  self.store.save({'platformOnly':True,'curseForgeKey':'fake-cf-key','endpoint':'https://ignored.invalid','model':'ignored','apiKey':'ignored'})
  after=json.loads(self.store.file.read_text())
  for field in ('endpoint','model','encryptedKey','origin','autoSearch'):self.assertEqual(after[field],before[field])
  self.store.save({'platformOnly':True,'clearCurseKey':True})
  self.assertFalse(self.store.public()['hasCurseForgeKey']);self.assertEqual(self.store.credentials()['apiKey'],'fake-ai-key')
 def test_oversize_platform_key_does_not_change_saved_configuration(self):
  self.store.save({'defer':True});before=self.store.file.read_bytes()
  with self.assertRaises(ValueError):self.store.save({'platformOnly':True,'curseForgeKey':'x'*4001})
  self.assertEqual(self.store.file.read_bytes(),before)
 def test_hide_ai_setup_default_and_all_save_paths_preserve_choice(self):
  self.assertFalse(self.store.public()['hideAiSetup'])
  self.store.save({'defer':True,'hideAiSetup':True})
  self.assertTrue(SettingsStore(self.tmp.name).public()['hideAiSetup'])
  self.store.save({'endpoint':'https://example.invalid/v1','model':'fixture','apiKey':'fake-secret','autoSearch':False})
  before=json.loads(self.store.file.read_text());self.assertTrue(self.store.public()['hideAiSetup'])
  self.store.save({'platformOnly':True,'curseForgeKey':'fake-platform'})
  self.assertTrue(self.store.public()['hideAiSetup'])
  self.store.save({'defer':True});self.assertTrue(self.store.public()['hideAiSetup'])
  self.store.save({'defer':True,'hideAiSetup':False})
  self.assertFalse(self.store.public()['hideAiSetup']);self.assertFalse(self.store.public()['autoSearch'])
  self.assertEqual(self.store.credentials()['apiKey'],'fake-secret')
  self.assertEqual(self.store.read()['cfKey'],'fake-platform')
  self.assertNotIn('fake-secret',self.store.file.read_text());self.assertNotIn('fake-platform',self.store.file.read_text())
 def test_frozen_runtime_keeps_user_data_outside_extracted_bundle(self):
  from server import data_directory,directory_picker_command
  with patch('server.sys.frozen',True,create=True),patch.dict('server.os.environ',{'LOCALAPPDATA':self.tmp.name}):
   self.assertEqual(data_directory(),Path(self.tmp.name)/'DAMN-Public')
   self.assertEqual(directory_picker_command()[1:],['--choose-directory'])
  self.assertEqual(data_directory(self.tmp.name),Path(self.tmp.name).resolve())
class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.http.token=secrets.token_urlsafe(32);self.http.scan_lock=threading.Lock();self.http.archive_temp=tempfile.TemporaryDirectory();self.http.archive_store={};self.http.settings=SettingsStore(Path(self.tmp.name)/'settings')
  threading.Thread(target=self.http.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.http.server_port)
 def tearDown(self):self.http.shutdown();self.http.server_close();self.http.archive_temp.cleanup();self.tmp.cleanup()
 def request(self,route,body=None,extra=None,auth=True):
  headers={'Content-Type':'application/json'}
  if auth:headers['X-DAMN-Token']=self.http.token
  headers.update(extra or {});data=json.dumps(body).encode() if body is not None and not isinstance(body,bytes) else body
  with urlopen(Request(self.base+route,data,headers),timeout=10) as r:return json.load(r)
 def test_instance_ping_recognizes_running_app(self):
  from server import running_instance
  self.assertTrue(running_instance(self.http.server_port));self.assertEqual(self.request('/api/ping',auth=False)['app'],'DAMN')
 def test_settings_require_token_and_reject_foreign_origin(self):
  with self.assertRaises(HTTPError) as e:self.request('/api/settings',auth=False)
  self.assertEqual(e.exception.code,404)
  with self.assertRaises(HTTPError) as e:self.request('/api/settings',extra={'Origin':'https://example.invalid'})
  self.assertEqual(e.exception.code,403)
 def test_connectivity_test_and_integrated_analysis_use_saved_settings(self):
  stub=ThreadingHTTPServer(('127.0.0.1',0),AIStub);threading.Thread(target=stub.serve_forever,daemon=True).start()
  try:
   draft={'endpoint':'http://127.0.0.1:'+str(stub.server_port)+'/v1','model':'stub','autoSearch':False}
   test=self.request('/api/settings/test',draft);self.assertTrue(test['ok']);self.assertIn('connectivity test',AIStub.received['messages'][1]['content'])
   self.assertFalse(self.http.settings.public()['onboarded'])
   saved=self.request('/api/settings',draft);self.assertTrue(saved['configured'])
   result=self.request('/api/ai',{'question':'解释依赖','context':'{}','endpoint':'https://ignored.invalid','apiKey':'ignored'})
   self.assertEqual(result['answer'],'测试回答');self.assertEqual(AIStub.received['model'],'stub')
  finally:stub.shutdown();stub.server_close()
 def test_auto_search_off_does_not_access_platforms(self):
  self.http.settings.save({'endpoint':'http://127.0.0.1:1/v1','model':'stub','autoSearch':False})
  with patch('server.research') as lookup,patch('server.ai_request',return_value={'answer':'ok','model':'stub'}):
   self.request('/api/ai',{'question':'解释','context':'{}'});lookup.assert_not_called()
 def test_auto_search_on_returns_materials_and_reconciliation(self):
  self.http.settings.save({'endpoint':'http://127.0.0.1:1/v1','model':'stub','autoSearch':True})
  materials={'sources':[{'url':'https://modrinth.com/mod/test','site':'Modrinth'}],'notes':[],'sites':[]}
  with patch('server.research',return_value=materials),patch('server.ai_request',return_value={'answer':'原始回答','model':'stub'}):
   result=self.request('/api/ai',{'question':'解释','context':json.dumps({'mod':{'name':'Test','kind':'manifest'}})})
  self.assertTrue(result['research']);self.assertTrue(result['reconciliation']['unknown']);self.assertEqual(result['aiSearch']['mode'],'review_only')
 def test_upload_manifest_is_analyzed_locally(self):
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:z.writestr('modrinth.index.json',json.dumps({'formatVersion':1,'game':'minecraft','name':'Uploaded','files':[{'path':'mods/demo.jar'}]}))
  result=self.request('/api/upload',buf.getvalue(),{'Content-Type':'application/octet-stream','X-DAMN-FileName':'test.mrpack'})
  self.assertEqual(result['archive']['manifestOnly'],1);self.assertEqual(result['pack'],'Uploaded');self.assertFalse(list(Path(self.http.archive_temp.name).iterdir()))
 def test_upload_malformed_archive_cleans_temporary_file(self):
  with self.assertRaises(HTTPError):self.request('/api/upload',b'bad',{'Content-Type':'application/octet-stream'})
  self.assertFalse(list(Path(self.http.archive_temp.name).iterdir()))
if __name__=='__main__':unittest.main()
