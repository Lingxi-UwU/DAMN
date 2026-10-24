import json,subprocess,threading,unittest
from unittest.mock import Mock,patch
from pathlib import Path
from taxonomy import classify_mod
from category_lookup import resolve_categories
from enrichment import metadata_patch
from ai_agent import merge_materials

class PlatformCategoryTests(unittest.TestCase):
 def test_platform_utility_is_not_overwritten_by_description_or_joke_name(self):
  mod={'name':'Save My Shit Network','aiPurpose':'阻止常见模组联网且不影响其功能，避免因网络问题造成加载缓慢或崩溃。','onlineResearch':[{'platformCategory':['utility']}]}
  self.assertEqual(classify_mod(mod)['category'],'实用工具')
  self.assertEqual(classify_mod(mod)['tags'],[])
  mod['aiPurpose']='加入火炮、存储网络、法术与飞行器。'
  self.assertEqual(classify_mod(mod)['categories'],['实用工具'])
 def test_unsupported_curseforge_numeric_ids_are_not_guessed(self):
  mod={'name':'Example','platformTaxonomy':[{'site':'CurseForge','categoryIds':[412,4843,434],'primaryCategoryId':434,'matched':True}]}
  result=classify_mod(mod)
  self.assertEqual(result['category'],'其他 / 待识别')
  self.assertEqual(result['platformEvidence'],[])
 def test_multiple_flat_official_platform_labels_are_retained(self):
  mod={'name':'Unknown','platformTaxonomy':[{'site':'Modrinth','categories':['technology','equipment'],'matched':True}]}
  result=classify_mod(mod)
  self.assertEqual(result['categories'],['装备工具','科技'])
  self.assertEqual(set(result['platformEvidence'][0]['labels']),{'科技','装备工具'})
 def test_unmatched_search_candidates_do_not_supply_confirmed_categories(self):
  mod={'name':'Unknown','onlineResearch':[{'platformTaxonomy':[{'site':'Modrinth','categories':['library'],'matched':False}],'platformCategory':['library'],'sources':[{'site':'Modrinth','categories':['library'],'matched':False}]}]}
  self.assertEqual(classify_mod(mod)['category'],'其他 / 待识别')
 def test_displayed_summary_and_original_description_both_participate(self):
  self.assertEqual(classify_mod({'name':'Unknown','aiAnnotation':{'summary':'提供便捷操作和提示信息。'}})['category'],'实用工具')
  self.assertEqual(classify_mod({'name':'Unknown','aiPurpose':'为玩家增加更多可用内容。','originalDescription':'An API and library for mods.'})['category'],'开发库')
 def test_metadata_round_trip_does_not_erase_categories(self):
  source={'site':'Modrinth','url':'https://modrinth.com/mod/example','categories':['equipment']}
  first={'subjectIndex':0,'sources':[source],'platformTaxonomy':[{'site':'Modrinth','categories':['equipment']}]}
  second={'subjectIndex':0,'sources':[{'url':source['url'],'excerpt':'Later read'}]}
  info=merge_materials([first],[second])[0]
  mod={'name':'Unknown','kind':'jar'};mod.update(metadata_patch(mod,info))
  self.assertEqual(classify_mod(mod)['category'],'装备工具')
 def test_free_refresh_is_batched_and_never_needs_ai_configuration(self):
  mods=[{'key':str(i),'name':'Example'} for i in range(7)];warm=Mock();lookup=Mock(return_value={'records':[{'site':'Modrinth','categories':['utility'],'matched':True}]})
  result=resolve_categories(mods,lookup=lookup,warm=warm)
  self.assertEqual(result['aiCalls'],0);self.assertEqual(len(result['updates']),7);self.assertEqual(lookup.call_count,7);warm.assert_called_once()
  with self.assertRaises(ValueError):resolve_categories(mods*2,warm=warm)
 def test_known_project_id_fetches_categories_without_a_version_or_name_search(self):
  seen=[]
  def fetch(url,*args,**kwargs):
   seen.append(url)
   self.assertEqual(url,'https://api.modrinth.com/v2/project/Abcd1234')
   return json.dumps({'id':'Abcd1234','title':'Example','slug':'example','categories':['utility']})
  with patch('research.fetch',side_effect=fetch):
   result=resolve_categories([{'key':'one','name':'Example','sha1':'a'*40,'resolutionStatus':'matched','platformInfo':{'projectIds':{'Modrinth':'Abcd1234'}}}],warm=lambda mods:None)
  self.assertEqual(len(seen),1);self.assertEqual(result['updates'][0]['records'][0]['categories'],['utility'])
 def test_python_and_browser_platform_mapping_agree(self):
  mods=[{'name':'Anything','platformTaxonomy':[{'site':'CurseForge','categoryIds':[412,4843,434],'primaryCategoryId':434}]},{'name':'Unknown','onlineResearch':[{'platformCategory':['utility','library']}]},{'name':'Unknown','aiAnnotation':{'summary':'显示地图与玩家状态。'}}]
  js="const c=require('./static/catalog.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(c.damnCategoryInfo))));"
  proc=subprocess.run(['node','-e',js],input=json.dumps(mods),capture_output=True,text=True,encoding='utf-8',check=True)
  self.assertEqual(json.loads(proc.stdout),[classify_mod(m) for m in mods])
 def test_http_refresh_needs_session_but_not_an_ai_key(self):
  from http.server import ThreadingHTTPServer
  from urllib.request import Request,urlopen
  from urllib.error import HTTPError
  from server import Handler
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.token='test-only-category-token';server.settings=Mock();server.settings.read.return_value={}
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   def request(auth):
    headers={'Content-Type':'application/json',**({'X-DAMN-Token':server.token} if auth else {})}
    with urlopen(Request('http://127.0.0.1:'+str(server.server_port)+'/api/categories/resolve',b'{"mods":[{"key":"a","name":"Unknown"}]}',headers),timeout=3) as response:return json.load(response)
   with patch('server.resolve_categories',return_value={'updates':[],'aiCalls':0}),patch('server.ai_request') as ai:
    with self.assertRaises(HTTPError) as error:request(False)
    self.assertEqual(error.exception.code,403);self.assertEqual(request(True)['aiCalls'],0);ai.assert_not_called();server.settings.credentials.assert_not_called()
  finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
