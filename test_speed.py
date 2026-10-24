import copy,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import ai_agent as a
from ai_cache import AnnotationCache
from enrichment import EnrichmentManager
from test_enrichment import Settings,info,chat,finish
from server import APIError

class SpeedTests(unittest.TestCase):
 def setUp(self):
  self.body=patch('ai_agent.fetch',return_value='{"body":"Requires Create.","title":"Library"}');self.body.start();self.addCleanup(self.body.stop)
  with a._SUPPORT_LOCK:a._TOOL_SUPPORT.clear()
 def translated(self,payload,**kwargs):
  result=chat(payload,**kwargs);data=json.loads(result['answer'])
  for row in data['items']:row['descriptionZh']='用于模组开发的共享前置库。'
  result['answer']=json.dumps(data,ensure_ascii=False);return result
 def test_complete_evidence_needs_one_model_request(self):
  model=Mock(side_effect=self.translated);mod={'key':'a','name':'Library'};material={**info(mod),'subjectIndex':0}
  payload={**Settings().credentials(),'question':'核对','context':json.dumps({'mods':[mod]}),'fastBatch':True,'dependencyReview':True}
  result,materials=a.online_analysis(payload,[mod],[material],'',model)
  self.assertEqual(model.call_count,1);self.assertEqual(model.call_args.kwargs['tool_choice'],'auto')
  self.assertIn('Requires Create',model.call_args.kwargs['messages'][1]['content'])
  self.assertEqual(result['aiSearch']['mode'],'prefetched');self.assertFalse(result['aiSearch']['calls'])
 def test_fast_model_can_still_choose_source_lookup(self):
  from test_ai_agent import call,final
  model=Mock(side_effect=[{'tool_calls':[call()]},final()])
  with patch.object(a,'research',return_value=info({'key':'a'})) as lookup:
   result,_=a.online_analysis({'endpoint':'local','model':'x','question':'核对','context':'{}','fastBatch':True},[{'name':'Library'}],[],'',model)
  self.assertEqual(lookup.call_count,2) # Application prepares evidence, then the model requests a lookup.
  self.assertEqual(result['aiSearch']['mode'],'tools');self.assertEqual(model.call_count,2)
  self.assertIsNone(model.call_args.kwargs['tools'])
 def test_unsupported_tools_remembered_but_provider_isolated(self):
  from test_ai_agent import final
  payload={'endpoint':'https://example.com/v1','model':'stub','question':'核对','context':'{}','fastBatch':True}
  model=Mock(side_effect=[APIError('unsupported',400),final(),final()])
  with patch.object(a,'prepare_dependencies',return_value={'items':[],'_materials':[]}):
   a.online_analysis(payload,[],[],'',model);a.online_analysis(payload,[],[],'',model)
  self.assertEqual(model.call_count,3);self.assertIsNone(model.call_args.kwargs['tools'])
  other=Mock(return_value=final())
  with patch.object(a,'prepare_dependencies',return_value={'items':[],'_materials':[]}):a.online_analysis({**payload,'model':'different'},[],[],'',other)
  self.assertTrue(other.call_args.kwargs['tools'])
 def test_parallel_requests_are_bounded_and_ramp_after_first(self):
  active=0;maximum=0;calls=0;lock=threading.Lock();overlap=threading.Event()
  def model(p,**kw):
   nonlocal active,maximum,calls
   with lock:
    calls+=1;active+=1;maximum=max(maximum,active);first=calls==1
    if active==2:overlap.set()
   if not first:overlap.wait(1)
   time.sleep(.03)
   try:return self.translated(p,**kw)
   finally:
    with lock:active-=1
  manager=EnrichmentManager(Settings(),model,lambda m,k:info(m),lambda *x:[])
  state=finish(manager,manager.start([{'key':str(i)} for i in range(41)])['id'])
  self.assertEqual(maximum,2);self.assertEqual(calls,5);self.assertEqual(state['aiDone'],41)
  self.assertEqual(state['aiBatchesCompleted'],5);self.assertEqual(state['aiWorkers'],0)
  self.assertIsNotNone(state['aiLastBatchSeconds']);self.assertNotIn('_aiActive',state)
 def test_authentication_error_stops_before_parallel_ramp(self):
  model=Mock(side_effect=APIError('invalid credentials',401));manager=EnrichmentManager(Settings(),model,lambda m,k:info(m),lambda *x:[])
  state=finish(manager,manager.start([{'key':str(i)} for i in range(41)])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(state['aiDone'],0);self.assertIn('invalid credentials',state['aiError'])
 def test_rate_limit_pauses_new_batches_without_retry_storm(self):
  model=Mock(side_effect=APIError('limit',429));manager=EnrichmentManager(Settings(),model,lambda m,k:info(m),lambda *x:[])
  state=finish(manager,manager.start([{'key':str(i)} for i in range(41)])['id'])
  self.assertEqual(model.call_count,1);self.assertIn('限流',state['aiError'])
 def test_reimport_reuses_validated_translation_across_new_entry_key(self):
  def stable_model(p,**kw):
   result=self.translated(p,**kw);data=json.loads(result['answer'])
   for row in data['items']:row['evidence']=['https://modrinth.com/mod/same-project']
   result['answer']=json.dumps(data,ensure_ascii=False);return result
  model=Mock(side_effect=stable_model);cache=AnnotationCache()
  manager=EnrichmentManager(Settings(),model,lambda m,k:info({'key':'same-project'}),lambda *x:[],cache=cache)
  finish(manager,manager.start([{'key':'entry-a','name':'Library','file':'lib-2.jar'}])['id'])
  second=finish(manager,manager.start([{'key':'entry-b','name':'Library','file':'lib-2.jar'}])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(second['aiCacheHits'],1)
  self.assertTrue(all(x['key']=='entry-b' for x in second['updates']))
 def test_accepted_result_is_cached_and_reconciled_for_current_entry(self):
  cache=AnnotationCache();model=Mock(side_effect=self.translated)
  manager=EnrichmentManager(Settings(),model,lambda m,k:info(m),lambda *x:[],cache=cache)
  mod={'key':'a','name':'Library','file':'lib.jar'}
  finish(manager,manager.start([mod])['id']);state=finish(manager,manager.start([mod])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(state['aiCacheHits'],1);self.assertEqual(state['aiDone'],1)
  result=next(x['patch'] for x in state['updates'] if 'aiAnnotation' in x['patch'])
  self.assertTrue(result['aiSearch']['cached']);self.assertIn('共享',result['descriptionZh'])
 def test_cache_expires_and_ignores_corrupt_file(self):
  with tempfile.TemporaryDirectory() as directory:
   file=Path(directory)/'ai-cache.json';cache=AnnotationCache(file,ttl=10)
   with patch('ai_cache.time.time',return_value=100):cache.put('a',{'annotation':{'summary':'资料'}})
   with patch('ai_cache.time.time',return_value=111):self.assertIsNone(cache.get('a'))
   file.write_text('invalid');self.assertFalse(AnnotationCache(file).entries)
 def test_cache_key_changes_with_model_version_and_evidence_but_not_secret(self):
  cache=AnnotationCache();creds=Settings().credentials();mod={'key':'a','name':'A','version':'1.0'};material=info(mod)
  key=cache.key(creds,mod,material)
  self.assertEqual(key,cache.key({**creds,'apiKey':'changed'},mod,material))
  self.assertEqual(key,cache.key(creds,{**mod,'key':'different'},material))
  self.assertNotEqual(key,cache.key({**creds,'model':'different'},mod,material))
  self.assertNotEqual(key,cache.key({**creds,'endpoint':'https://other.com'},mod,material))
  self.assertNotEqual(key,cache.key(creds,{**mod,'version':'2.0'},material))
  changed=copy.deepcopy(material);changed['identity']['description']='New description'
  self.assertNotEqual(key,cache.key(creds,mod,changed))
 def test_eta_accounts_for_the_remaining_inflight_batch(self):
  manager=EnrichmentManager(Settings(),chat)
  manager.job={'id':'x','updates':[],'status':'running','lookupComplete':True,'aiBatchesCompleted':3,'aiBatchSeconds':24,'aiProcessed':90,'aiStartedAt':time.time()-24,'aiFinishedAt':None,'aiTotal':100,'aiDone':90,'aiError':'','_aiActive':{4:{'names':['tail'],'started':time.time()}}}
  # Snapshot has additional UI fields; fill their defaults without exposing internals.
  fields=('requestId','scope','stage','phase','done','total','matched','candidates','failed','aiBatch','error','notes','createdAt','heartbeatAt','updatedAt','waitingForConfig','configRevision','activeItems','activeAI','aiCacheHits','aiLastBatchSeconds','aiWorkers','aiConcurrency','pipelineRevision')
  for field in fields:manager.job.setdefault(field,0)
  self.assertGreaterEqual(manager.snapshot('x')['aiEtaSeconds'],7)
 def test_disk_cache_contains_no_api_credentials(self):
  with tempfile.TemporaryDirectory() as directory:
   file=Path(directory)/'ai-cache.json';cache=AnnotationCache(file)
   key=cache.key(Settings().credentials(),{'key':'a'},info({'key':'a'}));cache.put(key,{'annotation':{'summary':'中文简介'}})
   raw=file.read_text(encoding='utf-8');self.assertNotIn('fake-secret',raw);self.assertNotIn('endpoint',raw)
   self.assertIsNotNone(AnnotationCache(file).get(key))

if __name__=='__main__':unittest.main()
