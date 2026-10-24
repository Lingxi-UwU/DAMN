"""Independent flat category schema and classification evidence checks."""
import json, unittest, subprocess, tempfile, zipfile
from unittest.mock import patch
from pathlib import Path
from taxonomy import classify_mod, normalize_tags, normalize_category, taxonomy_prompt, TAXONOMY, CATEGORIES, TAXONOMY_VERSION
from research import parse_ai_annotation


class TaxonomyTests(unittest.TestCase):
 def test_representative_local_examples_cover_every_flat_category(self):
  cases=json.loads(Path('test_taxonomy_cases.json').read_text(encoding='utf-8'))
  self.assertEqual({m['expectedCategory'] for m in cases}, CATEGORIES)
  for mod in cases:
   with self.subTest(category=mod['expectedCategory']):
    result=classify_mod(mod)
    self.assertEqual(result['category'], mod['expectedCategory'])
    self.assertIn(result['category'], result['categories'])
    self.assertLessEqual(len(result['tags']), 3)
 def test_official_slugs_are_flat_and_numeric_dictionary_is_absent(self):
  expected={'adventure','cursed','decoration','economy','equipment','food','game-mechanics','library','magic','management','minigame','mobs','optimization','social','storage','technology','transportation','utility','worldgen'}
  self.assertEqual({slug for c in TAXONOMY['categories'] for slug in c['platform']}, expected)
  self.assertEqual(len(TAXONOMY['categories']), 20)
  self.assertTrue(all(c.get('group')==c['label'] and not c.get('parent') for c in TAXONOMY['categories']))
  self.assertEqual(TAXONOMY.get('platformIds'), {})
 def test_vocabulary_is_unique_and_unknown_tags_are_discarded(self):
  labels=[c['label'] for c in TAXONOMY['categories']];tags=[f['label'] for c in TAXONOMY['categories'] for f in c['features']]
  self.assertEqual(len(labels),len(set(labels)));self.assertEqual(len(tags),len(set(tags)))
  self.assertFalse(set(labels)&set(tags))
  self.assertEqual(normalize_tags(['法术','法术','not-a-tag','仪式','炼金','货币']), ['法术','仪式','炼金'])
  self.assertEqual(normalize_tags(['小地图','自动加工','随便编造']), [])
  self.assertEqual(normalize_category('世界与探索'),'世界生成')
  self.assertEqual(normalize_category('unrecognized'),'其他 / 待识别')
 def test_validated_ai_tags_require_evidence_and_are_bounded(self):
  url='https://modrinth.com/mod/example';payload=json.dumps({'summary':'提供法术和仪式。','category':'魔法','tags':['法术','法术','未知','仪式','炼金','货币'],'evidence':[url]},ensure_ascii=False)
  invalid=parse_ai_annotation(payload,[]);self.assertIsNone(invalid['category']);self.assertEqual(invalid['tags'],[])
  valid=parse_ai_annotation(payload,[{'sources':[{'url':url}]}])
  self.assertEqual(valid['category'],'魔法');self.assertEqual(valid['tags'],['法术','仪式','炼金']);self.assertEqual(valid['taxonomyVersion'],TAXONOMY_VERSION)
 def test_server_and_client_migrate_the_same_synthetic_snapshot(self):
  mods=json.loads(Path('demo.json').read_text(encoding='utf-8'))['mods']
  result=subprocess.run(['node','-e',"const c=require('./static/catalog.js'),d=require('./demo.json');console.log(JSON.stringify(d.mods.map(c.damnCategoryInfo)));"],capture_output=True,text=True,encoding='utf-8',check=True)
  self.assertEqual(json.loads(result.stdout),[classify_mod(m) for m in mods])
 def test_saved_ai_labels_do_not_override_local_storage_evidence(self):
  m={'name':'Example','description':'物品存储网络','aiAnnotation':{'taxonomyVersion':2,'category':'魔法','tags':['法术']}}
  self.assertEqual(classify_mod(m)['category'],'存储');self.assertNotIn('法术',classify_mod(m)['tags'])
  m['aiAnnotation']['taxonomyVersion']=1
  self.assertEqual(classify_mod(m)['category'],'存储')
 def test_better_metadata_reclassifies_previously_scanned_mod(self):
  mod={'name':'Example','description':'工业自动化机器','category':'科技','categoryTaxonomyVersion':2,'tags':['自动加工']}
  self.assertEqual(classify_mod(mod)['category'],'科技')
  mod['aiPurpose']='添加可烹饪和饮用的食物。'
  self.assertEqual(classify_mod(mod)['category'],'饮食');self.assertNotIn('自动加工',classify_mod(mod)['tags'])
 def test_scan_reports_follow_active_category_schema_version(self):
  import scanner
  with tempfile.TemporaryDirectory() as folder:
   mods=Path(folder)/'mods';mods.mkdir()
   metadata={'schemaVersion':1,'id':'example_library','name':'Example Library','version':'1.0','description':'A reusable library and API for mods.'}
   with zipfile.ZipFile(mods/'example.jar','w') as archive:
    archive.writestr('fabric.mod.json',json.dumps(metadata))
   with patch('scanner.TAXONOMY_VERSION',101):report=scanner.scan(folder)
  row=report['mods'][0]
  self.assertEqual(row['category'],'开发库')
  self.assertEqual(row['categoryTaxonomyVersion'],101)
  self.assertEqual(row['categoryEvidence'],'本地用途规则 · 分类方案 v101')
 def test_prompt_describes_current_flat_schema(self):
  prompt=taxonomy_prompt()
  self.assertIn('taxonomyVersion='+str(TAXONOMY_VERSION), prompt)
  self.assertIn('平级类别', prompt)
  for category in TAXONOMY['categories']:self.assertIn(category['label']+'：',prompt)


if __name__=='__main__':unittest.main()
