import json,time,threading,unittest
from unittest.mock import patch,Mock
from enrichment import EnrichmentManager
from test_enrichment import Settings,info,chat,finish
import research as r
import ai_agent as a
class ProgressTests(unittest.TestCase):
 def setUp(self):
  # Public bodies are synthetic in these injected-source background tests.
  self.body=patch('ai_agent.fetch',return_value='{}');self.body.start();self.addCleanup(self.body.stop)

 def test_api_added_after_import_continues_same_job(self):
  class Late(Settings):
   configured=False
   def public(self):return {'autoSearch':True,'configured':self.configured,'revision':'saved' if self.configured else 'empty'}
  settings=Late();manager=EnrichmentManager(settings,chat,lambda m,k:info(m),lambda *x:[])
  ident=manager.start([{'key':'a','kind':'manifest'}],'late-request','late-pack')['id']
  for _ in range(100):
   state=manager.snapshot(ident)
   if state['done']==1 and state['waitingForConfig']:break
   time.sleep(.01)
  self.assertEqual(state['status'],'running');self.assertTrue(state['waitingForConfig'])
  settings.configured=True;state=finish(manager,ident)
  self.assertEqual(state['aiDone'],1);self.assertEqual(state['id'],ident)
 def test_repeated_start_is_idempotent(self):
  entered=threading.Event();release=threading.Event()
  def lookup(m,k):entered.set();release.wait(2);return info(m)
  lookup=Mock(side_effect=lookup);manager=EnrichmentManager(Settings(),chat,lookup,lambda *x:[])
  first=manager.start([{'key':'a'}],'request-one','pack');entered.wait(1)
  second=manager.start([{'key':'a'}],'request-one','pack');self.assertEqual(first['id'],second['id']);release.set()
  finish(manager,first['id']);self.assertEqual(lookup.call_count,1)
 def test_reconnect_scope_and_cursor(self):
  manager=EnrichmentManager(Settings(),chat,lambda m,k:info(m),lambda *x:[])
  ident=manager.start([{'key':'a'}],'request-a','pack-a')['id'];finish(manager,ident)
  self.assertIsNone(manager.current('different-pack'));state=manager.current('pack-a',1)
  self.assertEqual(state['id'],ident);self.assertEqual(len(state['updates']),1);self.assertIn('heartbeatAt',state)
 def test_resume_ai_uses_cached_sources_without_repeating_lookup(self):
  model=Mock(side_effect=chat);lookup=Mock(side_effect=AssertionError('should use seed'))
  manager=EnrichmentManager(Settings(),model,lookup,lambda *x:[])
  state=finish(manager,manager.start([{'key':'a','kind':'manifest','enrichmentComplete':True,'onlineResearch':[info({'key':'a'})]}])['id'])
  lookup.assert_not_called();self.assertEqual(state['done'],1);self.assertEqual(state['aiDone'],1)
 def test_translation_starts_before_last_lookup_finishes(self):
  last=threading.Event();model_started=threading.Event()
  def lookup(m,k):
   if m['key']=='last':last.wait(3)
   return info(m)
  def model(p,**kw):model_started.set();return chat(p,**kw)
  manager=EnrichmentManager(Settings(),model,lookup,lambda *x:[])
  ident=manager.start([{'key':'a'},{'key':'last'}])['id']
  self.assertTrue(model_started.wait(1.5));self.assertFalse(manager.snapshot(ident)['lookupComplete']);last.set();finish(manager,ident)
 def test_chinese_translation_and_version_dependency_are_retained(self):
  url='https://modrinth.com/mod/a'
  answer={'summary':'自动化酒馆的附属模组。','descriptionZh':'这是 Create 与 Kaleidoscope Tavern 的附属模组，可用于自动化酒馆。','category':'机械动力与工业','evidence':[url],'relations':[{'target':'Create','kind':'required','source':url,'version':'1.21.1 对应版本'}]}
  value=r.parse_ai_annotation(json.dumps(answer),[{'sources':[{'url':url}]}])
  self.assertIn('酒馆',value['descriptionZh']);self.assertEqual(value['relations'][0]['version'],'1.21.1 对应版本')
 def test_english_translation_is_not_mislabelled_as_chinese(self):
  value=r.parse_ai_annotation(json.dumps({'summary':'说明','descriptionZh':'An English description','evidence':[]}),[])
  self.assertEqual(value['descriptionZh'],'')
 def test_dependency_tool_reads_api_body_and_keeps_sources(self):
  seed=info({'key':'a'});seed['subjectIndex']=0
  with patch.object(a,'fetch',return_value=json.dumps({'title':'A','body':'# Installation\nRequires Create and Tavern.\nInstall matching versions.'})):
   out=a.run_tool('lookup_mod_dependencies',{'subjects':[0]},[{'name':'A'}],'',[seed])
  self.assertIn('Requires Create',out['items'][0]['dependencyText']);self.assertTrue(out['_materials'][0]['sources'])
  self.assertTrue(any('api.modrinth.com' in s['url'] for s in out['_materials'][0]['sources']))
 def test_dependency_tool_rejects_invalid_subjects(self):
  with self.assertRaises(ValueError):a.run_tool('lookup_mod_dependencies',{'subjects':[False]},[{'name':'A'}])
 def test_dependency_tool_is_selected_for_dependency_review(self):
  payload={'question':'核对依赖','context':'{}','dependencyReview':True};model=Mock(return_value={'answer':'完成','usage':{}})
  a.online_analysis(payload,[{'name':'A'}],[],'',model)
  self.assertEqual(model.call_args.kwargs['tool_choice']['function']['name'],'lookup_mod_dependencies')
 def test_slow_trickle_cannot_read_forever(self):
  response=Mock();response.read1.return_value=b'x'
  with patch.object(r.time,'monotonic',side_effect=[0,2]):
   with self.assertRaisesRegex(ValueError,'时限'):r.read_bounded(response,2000,1)
  self.assertEqual(response.read1.call_count,1)
class TranslationConsistencyTests(unittest.TestCase):
 def setUp(self):
  self.body=patch('ai_agent.fetch',return_value='{}');self.body.start();self.addCleanup(self.body.stop)
 def mod_and_info(self):
  mod={'key':'local-description','kind':'jar','name':'Library','description':'A shared library for mod development.','enrichmentComplete':True,'aiReviewStatus':'done','aiAnnotation':{'summary':'一个前置库。'},'components':[],'dependencies':[]}
  data=info(mod);data['identity']['description']='';mod['onlineResearch']=[data]
  return mod,data
 def translated(self,payload,**kwargs):
  result=chat(payload,**kwargs);data=json.loads(result['answer'])
  for item in data['items']:item['descriptionZh']='用于模组开发的共享前置库。'
  result['answer']=json.dumps(data,ensure_ascii=False);return result
 def test_local_english_description_is_translated_once_when_platform_has_none(self):
  mod,data=self.mod_and_info();model=Mock(side_effect=self.translated);manager=EnrichmentManager(Settings(),model,warm=lambda *x:[])
  state=finish(manager,manager.start([mod])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(state['aiBatch'],1);self.assertEqual(state['pipelineRevision'],3)
  for item in state['updates']:mod.update(item['patch'])
  self.assertIn('共享',mod['descriptionZh']);second=finish(manager,manager.start([mod])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(second['aiBatch'],0)
 def test_missing_chinese_response_records_the_attempt_without_claiming_translation(self):
  mod,data=self.mod_and_info();manager=EnrichmentManager(Settings(),chat,warm=lambda *x:[])
  state=finish(manager,manager.start([mod])['id'])
  final=next(row['patch'] for row in state['updates'] if 'translationAttempted' in row['patch'])
  self.assertTrue(final['translationAttempted']);self.assertNotIn('descriptionZh',final)
 def test_old_cache_without_local_description_translation_is_not_accepted(self):
  from ai_cache import AnnotationCache
  mod,data=self.mod_and_info();cache=AnnotationCache();key=cache.key(Settings().credentials(),mod,data)
  cache.put(key,{'annotation':{'summary':'前置库。'},'materials':[data],'aiSearch':{}})
  model=Mock(side_effect=self.translated);manager=EnrichmentManager(Settings(),model,warm=lambda *x:[],cache=cache)
  state=finish(manager,manager.start([mod])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(state['aiCacheHits'],0)
 def test_chinese_local_description_does_not_trigger_another_ai_request(self):
  mod,data=self.mod_and_info();mod['description']='用于模组开发的共享库。';model=Mock()
  manager=EnrichmentManager(Settings(),model,warm=lambda *x:[])
  state=finish(manager,manager.start([mod])['id']);model.assert_not_called();self.assertEqual(state['aiDone'],1)

if __name__=='__main__':unittest.main()
