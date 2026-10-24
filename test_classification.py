import json,threading,unittest,subprocess
from pathlib import Path
from unittest.mock import Mock,patch
from taxonomy import classify_mod,classification_material,classification_input_stamp

class FreeClassificationTests(unittest.TestCase):
 def test_local_purpose_and_ecosystem_work_without_ai(self):
  for name,desc,expected in [('Create Example','提供机器和工业自动化。','科技'),('Example Transit','提供交通载具与铁路。','交通'),('Example Armory','增加武器和护甲。','装备工具'),('Example Convenience','提供便捷操作与便利功能。','实用工具')]:
   self.assertEqual(classify_mod({'name':name,'description':desc})['category'],expected)
 def test_specific_platform_tag_precedes_ambiguous_name(self):
  mod={'name':'Create Example','description':'An additional feature for Create','onlineResearch':[{'platformCategory':['decoration','technology']}]}
  result=classify_mod(mod);self.assertEqual(result['category'],'建筑装饰');self.assertIn('平台分类',result['source'])
 def test_distinct_flat_platform_labels_are_retained(self):
  mod={'name':'Load My F***ing Tags','description':'Stops a single broken tag entry from invalidating an entire tag.','onlineResearch':[{'platformCategory':['cursed','utility']}]}
  self.assertEqual(classify_mod(mod)['categories'],['怪趣','实用工具'])
 def test_saved_ai_decisions_are_preserved_as_data_but_do_not_classify(self):
  mod={'name':'Create Storage','description':'提供物品存储网络。','aiAnnotation':{'taxonomyVersion':2,'category':'游戏机制','tags':['趣味互动']},'aiCategory':'游戏机制'}
  mod['aiClassification']={'category':'游戏机制','taxonomyVersion':2,'revision':1,'inputStamp':classification_input_stamp(mod)}
  before=json.dumps(mod,sort_keys=True);result=classify_mod(mod)
  self.assertEqual(result['category'],'存储');self.assertNotIn('AI',result['source']);self.assertEqual(json.dumps(mod,sort_keys=True),before)
 def test_server_and_browser_agree_with_platform_and_legacy_ai_data(self):
  mods=json.loads(Path('test_taxonomy_cases.json').read_text(encoding='utf-8'))
  for mod in mods:mod['aiAnnotation']={'taxonomyVersion':2,'category':'游戏机制','tags':['无效标签']}
  result=subprocess.run(['node','-e',"const c=require('./static/catalog.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(c.damnCategoryInfo))));"],input=json.dumps(mods,ensure_ascii=False),capture_output=True,text=True,encoding='utf-8',check=True)
  self.assertEqual(json.loads(result.stdout),[classify_mod(m) for m in mods])
 def test_batch_summary_no_longer_requests_category_schema_or_dictionary(self):
  source=Path('enrichment.py').read_text(encoding='utf-8')
  self.assertNotIn('taxonomy_prompt()',source);self.assertNotIn('"category":"主分类"',source)
  self.assertIn('"purpose":',source);self.assertNotIn('"relations":',source)

class DisabledClassificationHTTPTests(unittest.TestCase):
 def test_cached_pages_cannot_start_or_resume_a_paid_classification_job(self):
  from http.server import ThreadingHTTPServer
  from urllib.request import Request,urlopen
  from urllib.error import HTTPError
  from server import Handler
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.token='test-only-session-token'
  server.settings=Mock();server.settings.credentials.side_effect=AssertionError('no AI credentials should be read')
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  def request(route,body=None,authorized=True):
   req=Request(base+route,json.dumps(body).encode() if body is not None else None,{'Content-Type':'application/json',**({'X-DAMN-Token':server.token} if authorized else {})})
   with urlopen(req,timeout=5) as response:return json.load(response)
  try:
   with patch('server.ai_request') as model:
    with self.assertRaises(HTTPError) as unauthorized:request('/api/classify/current',authorized=False)
    self.assertEqual(unauthorized.exception.code,403)
    for route in ['/api/classify/start','/api/classify/cancel']:
     with self.assertRaises(HTTPError) as disabled:request(route,{'mods':[{'key':'a','description':'用途资料'}],'id':'old-job'})
     self.assertEqual(disabled.exception.code,410)
    self.assertEqual(request('/api/classify/current'),{'job':None,'mode':'local'})
    with self.assertRaises(HTTPError) as gone:request('/api/classify/status?id=old-job')
    self.assertEqual(gone.exception.code,410);model.assert_not_called();server.settings.credentials.assert_not_called()
    self.assertFalse(hasattr(server,'classifier'))
  finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
