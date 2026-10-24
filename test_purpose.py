import json,unittest
from unittest.mock import Mock,patch
from purpose import clean_purpose
from enrichment import EnrichmentManager
from test_enrichment import Settings,finish
class PurposeTests(unittest.TestCase):
 def test_short_function_without_citation_prefix_or_version_tail(self):
  self.assertEqual(clean_purpose('网页描述为增加可放置的啤酒杯，玩家可以饮用。本地声明要求 NeoForge 21.1。'),'增加可放置的啤酒杯，玩家可以饮用。')
  self.assertEqual(clean_purpose('Add placeable beer mug and drink it!'),'')
  self.assertEqual(clean_purpose('网页描述为基于面包军火库的 1.21.1 NeoForge 完整移植版与维护分叉，保留原内容并含兼容性修复。'),'')
 def test_local_english_without_web_results_gets_one_reusable_chinese_summary(self):
  mod={'key':'beer','kind':'jar','name':'DrinkBeer Refill','file':'beer.jar','description':'Add placeable beer mug and drink it!','enrichmentComplete':True,'resolutionStatus':'failed','onlineResearch':[]}
  def chat(payload,**kw):
   self.assertNotIn('tools',kw)
   self.assertIn('description',payload['context'])
   return {'answer':json.dumps({'items':[{'key':'beer','purpose':'添加可放置和饮用的啤酒杯。','summary':'增加饮品互动。','descriptionZh':'添加可放置的啤酒杯并饮用。','evidence':[],'relations':[]}]}),'model':'stub','usage':{}}
  model=Mock(side_effect=chat);manager=EnrichmentManager(Settings(),model,lookup=Mock(side_effect=AssertionError('cached metadata should not be searched again')),warm=lambda *x:[])
  with patch('enrichment.online_analysis',side_effect=AssertionError('no website tools for local-only batch')):
   state=finish(manager,manager.start([mod])['id'])
  self.assertEqual(model.call_count,1);self.assertEqual(state['aiDone'],1)
  for row in state['updates']:mod.update(row['patch'])
  self.assertEqual(mod['aiPurpose'],'添加可放置和饮用的啤酒杯。');self.assertEqual(mod['aiPurposeBasis'],'local');self.assertFalse(mod['aiAnnotation']['evidence']);self.assertFalse(mod['aiAnnotation']['relations'])
  finish(manager,manager.start([mod])['id']);self.assertEqual(model.call_count,1)
 def test_valid_chinese_translation_avoids_rewriting_old_annotation_with_another_paid_request(self):
  mod={'key':'a','name':'Example','kind':'jar','description':'Provides third person camera controls.','enrichmentComplete':True,'onlineResearch':[],'aiAnnotation':{'summary':'网页描述为 1.21.1 移植版本。'},'aiReviewStatus':'done','descriptionZh':'提供第三人称镜头控制。'}
  model=Mock(return_value={'answer':json.dumps({'items':[{'key':'a','purpose':'调整第三人称镜头的位置与瞄准方式。','summary':'镜头控制。','evidence':[],'relations':[]}]}),'model':'stub','usage':{}})
  manager=EnrichmentManager(Settings(),model,warm=lambda *x:[]);state=finish(manager,manager.start([mod])['id'])
  from purpose import clean_purpose
  self.assertEqual(model.call_count,0);self.assertEqual(clean_purpose(mod['descriptionZh']),'提供第三人称镜头控制。');self.assertEqual(state['aiDone'],1)
if __name__=='__main__':unittest.main()
