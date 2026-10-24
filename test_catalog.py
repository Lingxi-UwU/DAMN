import json,unittest
from scanner import classify
from research import parse_ai_annotation
class CatalogTests(unittest.TestCase):
 def test_social_category_uses_emote_evidence(self):
  self.assertEqual(classify('Example adds emotes'),'社交')
 def test_world_generation_uses_flat_category(self):
  self.assertEqual(classify('Worldgen biomes and terrain'),'世界生成')
 def test_legacy_ai_category_keeps_evidence(self):
  source='https://modrinth.com/mod/world'
  annotation=parse_ai_annotation(json.dumps({'summary':'增加探索地形。','category':'世界与探索','evidence':[source]},ensure_ascii=False),[{'sources':[{'url':source}]}])
  self.assertEqual(annotation['category'],'世界生成')
 def test_role_category_requires_real_source(self):
  source='https://modrinth.com/mod/emotes';payload=json.dumps({'summary':'增加表情动作。','category':'社交','evidence':[source]},ensure_ascii=False)
  self.assertIsNone(parse_ai_annotation(payload,[])['category'])
  self.assertEqual(parse_ai_annotation(payload,[{'sources':[{'url':source}]}])['category'],'社交')
if __name__=='__main__':unittest.main()
