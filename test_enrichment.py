import json,time,threading,unittest
from unittest.mock import Mock,patch
from enrichment import EnrichmentManager,metadata_patch,parse_batch
import research as r
class Settings:
 def public(self):return {'configured':True,'autoSearch':True}
 def credentials(self):return {'endpoint':'http://127.0.0.1:1/v1','model':'stub','apiKey':'fake-secret'}
 def read(self):return {'cfKey':'fake-cf'}
def info(mod):
 key=mod['key'];url='https://modrinth.com/mod/'+key
 return {'identity':{'title':'Resolved '+key,'description':'A library','version':'2.0','loaders':['neoforge'],'projectIds':{'Modrinth':key},'exact':True,'match':'哈希匹配'},'sources':[{'url':url,'site':'Modrinth','title':key,'excerpt':'Library'}],'platformCategory':['library'],'platformDependencies':[],'sites':[],'notes':[]}
def chat(payload,**kwargs):
 rows=json.loads(payload['context'])['mods']
 return {'answer':json.dumps({'items':[{'key':m['key'],'summary':'用于兼容的前置库。','category':'开发库','evidence':['https://modrinth.com/mod/'+m['key']],'relations':[]} for m in rows]},ensure_ascii=False),'model':'stub','usage':{'total_tokens':20}}
def finish(manager,ident):
 for _ in range(200):
  state=manager.snapshot(ident)
  if state['status']!='running':return state
  time.sleep(.01)
 raise AssertionError('background job did not finish')
class EnrichmentTests(unittest.TestCase):
 def setUp(self):
  # Public bodies are synthetic in these injected-source background tests.
  self.body=patch('ai_agent.fetch',return_value='{}');self.body.start();self.addCleanup(self.body.stop)

 def test_entire_manifest_is_processed_and_ai_batched(self):
  lookup=Mock(side_effect=lambda m,k:info(m));model=Mock(side_effect=chat)
  manager=EnrichmentManager(Settings(),model,lookup,lambda *x:[])
  mods=[{'key':'m'+str(i),'kind':'manifest','name':'file.jar','components':[],'dependencies':[]} for i in range(27)]
  state=finish(manager,manager.start(mods)['id'])
  self.assertEqual(state['done'],27);self.assertEqual(state['matched'],27);self.assertEqual(state['aiDone'],27)
  self.assertEqual(lookup.call_count,27);self.assertEqual(model.call_count,3)
  updates=state['updates'];self.assertEqual(sum('aiAnnotation' in x['patch'] for x in updates),27)
  self.assertNotIn('fake-secret',json.dumps(state));self.assertNotIn('fake-cf',json.dumps(state))
 def test_exact_metadata_replaces_filename_but_not_jar_verification(self):
  patch=metadata_patch({'key':'m','kind':'manifest'},info({'key':'m'}))
  self.assertEqual(patch['name'],'Resolved m');self.assertEqual(patch['version'],'2.0')
  self.assertNotIn('dependenciesKnown',patch);self.assertNotIn('components',patch);self.assertNotIn('kind',patch)
 def test_keyword_candidates_do_not_overwrite_identity(self):
  data=info({'key':'m'});data['identity']['exact']=False
  patch=metadata_patch({'kind':'manifest'},data);self.assertEqual(patch['resolutionStatus'],'candidate');self.assertNotIn('name',patch)
 def test_local_jar_identity_is_preserved(self):
  self.assertNotIn('name',metadata_patch({'kind':'jar'},info({'key':'m'})))
 def test_cross_item_citations_are_rejected(self):
  row={'items':[{'key':'a','summary':'x','category':'开发库','evidence':['https://modrinth.com/mod/b']}]}
  out=parse_batch(json.dumps(row),[{'key':'a'}],[{**info({'key':'a'}),'subjectIndex':0}]);self.assertFalse(out)
 def test_api_failure_does_not_retry_every_batch(self):
  model=Mock(side_effect=ValueError('quota error'));manager=EnrichmentManager(Settings(),model,lambda m,k:info(m),lambda *x:[])
  state=finish(manager,manager.start([{'key':str(i)} for i in range(22)])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(state['done'],22);self.assertIn('quota',state['aiError'])
 def test_disabled_switch_rejects_start(self):
  settings=Settings();settings.public=lambda:{'configured':True,'autoSearch':False}
  with self.assertRaises(ValueError):EnrichmentManager(settings,chat).start([{'key':'a'}])
 def test_cancel_stops_queued_items_and_ai(self):
  block=threading.Event();entered=threading.Event()
  def lookup(m,k):entered.set();block.wait(2);return info(m)
  model=Mock(side_effect=chat);manager=EnrichmentManager(Settings(),model,lookup,lambda *x:[])
  ident=manager.start([{'key':str(i)} for i in range(80)])['id'];entered.wait(1);manager.cancel(ident);block.set()
  state=finish(manager,ident);self.assertEqual(state['status'],'cancelled');self.assertLess(state['done'],80);model.assert_not_called()
 def test_invalid_duplicate_keys_rejected(self):
  with self.assertRaises(ValueError):EnrichmentManager(Settings(),chat).start([{'key':'a'},{'key':'a'}])
 def test_status_deltas_are_paginated_without_loss(self):
  manager=EnrichmentManager(Settings(),chat,lambda m,k:info(m),lambda *x:[])
  ident=manager.start([{'key':str(i)} for i in range(115)])['id'];finish(manager,ident)
  cursor=0;items=[]
  while True:
   state=manager.snapshot(ident,cursor);items+=state['updates'];cursor=state['cursor']
   if not state['hasMore']:break
  self.assertEqual(len(items),230);self.assertEqual(len({x['key'] for x in items}),115)
 def test_ai_compaction_keeps_all_platform_dependencies_in_result(self):
  def lookup(mod,key):
   data=info(mod);data['platformDependencies']=[{'target':'dep'+str(i),'kind':'required','source':data['sources'][0]['url']} for i in range(25)]
   return data
  manager=EnrichmentManager(Settings(),chat,lookup,lambda *x:[])
  state=finish(manager,manager.start([{'key':'a','kind':'manifest'}])['id'])
  final=[x['patch'] for x in state['updates'] if 'aiAnnotation' in x['patch']][0]
  self.assertEqual(len(final['onlineResearch'][0]['platformDependencies']),25)
 def test_unknown_manifest_classification_is_addition(self):
  from ai_agent import reconcile
  data=info({'key':'a'});data['subjectIndex']=0
  result=reconcile([{'key':'a','kind':'manifest','name':'a.jar','category':'下载清单 / 待识别'}],[data],{'category':'开发库','relations':[]})
  self.assertFalse(result['conflicts']);self.assertTrue(result['added']);self.assertTrue(result['matched'])
 def test_bulk_prefetch_warms_exact_hash_and_project_caches(self):
  h='a'*128;version={'id':'version1','project_id':'project1','version_number':'1.0','dependencies':[]}
  def fetch(url,api_key=None,payload=None):
   if url.endswith('/version_files'):return json.dumps({h:version})
   if '/projects?' in url:return json.dumps([{'id':'project1','slug':'lib','title':'Library'}])
   raise AssertionError(url)
  with patch.object(r,'fetch',side_effect=fetch):r.warm_modrinth([{'manifest':{'hashes':{'sha512':h}}}])
  self.assertIn('/version_file/'+h,list(r.CACHE)[0] if len(r.CACHE)==1 else ' '.join(r.CACHE))
  self.assertIn('https://api.modrinth.com/v2/project/project1',r.CACHE)
if __name__=='__main__':unittest.main()
