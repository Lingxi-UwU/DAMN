import json,unittest
from urllib.parse import urlsplit,parse_qs
from unittest.mock import Mock,patch
import research as r
from enrichment import EnrichmentManager
from test_enrichment import Settings,finish

class PlatformDependencyTests(unittest.TestCase):
 def setUp(self):
  with r.LOCK:r.CACHE.clear();r.COOLDOWN.clear()
 def material(self):
  return {'sources':[{'site':'Modrinth','url':'https://modrinth.com/mod/example','title':'Example','excerpt':'说明'}],'platformDependencies':[{'target':'Modrinth 项目 Create00','projectId':'Create00','versionId':'Ver00001','kind':'required','source':'https://modrinth.com/mod/example/version/test'}],'identity':{'exact':True,'title':'Example','description':'提供可用的功能与工具。'}}
 def test_batch_project_and_exact_version_resolution_is_cached(self):
  calls=[]
  def fetch(url,api_key=None,payload=None):
   calls.append((url,api_key,payload));self.assertIsNone(api_key)
   if '/versions?' in url:return json.dumps([{'id':'Ver00001','project_id':'Create00','version_number':'6.0.10'}])
   if '/projects?' in url:return json.dumps([{'id':'Create00','slug':'create','title':'Create'}])
   raise AssertionError(url)
  original=self.material()
  with patch.object(r,'fetch',side_effect=fetch):
   result=r.resolve_platform_dependencies(original);again=r.resolve_platform_dependencies(original)
  row=result['platformDependencies'][0]
  self.assertEqual(row['target'],'Create');self.assertEqual(row['version'],'6.0.10');self.assertEqual(row['origin'],'platform');self.assertEqual(row['kind'],'required')
  self.assertEqual(len(calls),2);self.assertEqual(again['platformDependencies'],result['platformDependencies']);self.assertTrue(original['platformDependencies'][0]['target'].startswith('Modrinth 项目'))
 def test_curseforge_uses_only_its_key_and_preserves_dependency_kind(self):
  info={'platformDependencies':[{'target':'CurseForge 项目 123','projectId':123,'kind':'optional','source':'https://www.curseforge.com/minecraft/mc-mods/example/files/1'}]}
  def fetch(url,api_key=None,payload=None):
   self.assertEqual(url,'https://api.curseforge.com/v1/mods');self.assertEqual(api_key,'fake-cf-key');self.assertEqual(payload,{'modIds':[123]})
   return json.dumps({'data':[{'id':123,'name':'Library','links':{'websiteUrl':'https://www.curseforge.com/minecraft/mc-mods/library'}}]})
  with patch.object(r,'fetch',side_effect=fetch) as request:result=r.resolve_platform_dependencies(info,'fake-cf-key')
  self.assertEqual(request.call_count,1);self.assertEqual(result['platformDependencies'][0]['target'],'Library');self.assertEqual(result['platformDependencies'][0]['kind'],'optional')
  self.assertEqual(result['platformDependencies'][0]['version'],'平台未限定具体版本')
 def test_missing_key_or_failed_source_keeps_unknown_ids_without_guessing(self):
  info={'platformDependencies':[{'target':'CurseForge 项目 123','projectId':123,'kind':'required','source':'https://www.curseforge.com/minecraft/mc-mods/example/files/1'}]}
  with patch.object(r,'fetch') as request:result=r.resolve_platform_dependencies(info)
  request.assert_not_called();self.assertEqual(result['platformDependencies'][0]['target'],'CurseForge 项目 123')
  with patch.object(r,'fetch',side_effect=ValueError('offline')):result=r.resolve_platform_dependencies(self.material())
  self.assertTrue(result['platformDependencies'][0]['target'].startswith('Modrinth 项目'));self.assertTrue(result['notes'])
 def test_invalid_source_does_not_trigger_requests_or_gain_platform_provenance(self):
  info={'platformDependencies':[{'target':'Example','projectId':'Create00','source':'https://evil.example/mod/create','kind':'required'}]}
  with patch.object(r,'fetch') as request:result=r.resolve_platform_dependencies(info)
  request.assert_not_called();self.assertNotIn('origin',result['platformDependencies'][0])
 def test_known_chinese_purpose_and_platform_dependencies_need_zero_ai_calls(self):
  model=Mock(side_effect=AssertionError('no AI calls allowed'))
  info=self.material();info['platformDependencies'][0]['target']='Create'
  settings=Settings();manager=EnrichmentManager(settings,model,lookup=lambda m,k:info,warm=lambda *x:[])
  state=finish(manager,manager.start([{'key':'example','name':'Example'}])['id'])
  self.assertEqual(state['status'],'complete');model.assert_not_called()
  metadata=next(update['patch'] for update in state['updates'] if 'onlineResearch' in update['patch'])
  self.assertEqual(metadata['onlineResearch'][0]['platformDependencies'][0]['target'],'Create')
 def test_english_summary_uses_one_plain_request_and_cannot_add_ai_dependencies(self):
  info=self.material();info['identity']['description']='Add useful machines for automation.'
  def model(payload,**kwargs):
   self.assertFalse(kwargs);self.assertTrue(payload.get('summaryOnly'));self.assertNotIn('dependencyReview',payload)
   context=json.loads(payload['context']);self.assertNotIn('dependencies',context['mods'][0]);self.assertNotIn('platformDependencies',json.dumps(context))
   return {'answer':json.dumps({'items':[{'key':'example','purpose':'增加用于自动化加工的机器。','descriptionZh':'增加用于自动化加工的机器。','evidence':['https://modrinth.com/mod/example'],'relations':[{'target':'Invented','kind':'required','source':'https://modrinth.com/mod/example'}]}]})}
  chat=Mock(side_effect=model);manager=EnrichmentManager(Settings(),chat,lookup=lambda m,k:info,warm=lambda *x:[])
  state=finish(manager,manager.start([{'key':'example','name':'Example'}])['id']);self.assertEqual(chat.call_count,1)
  annotation=next(update['patch'] for update in state['updates'] if 'aiAnnotation' in update['patch'])
  self.assertEqual(annotation['aiAnnotation']['relations'],[]);self.assertEqual(annotation['aiSearch']['mode'],'summary')
  self.assertEqual(len(annotation['onlineResearch'][0]['platformDependencies']),1)

if __name__=='__main__':unittest.main()
