import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from scanner import scan
from identity import curseforge_fingerprint

class IdentityScanTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'mods').mkdir()
 def tearDown(self):self.temp.cleanup()
 def jar(self,name,extra=False):
  target=self.root/'mods'/name
  with zipfile.ZipFile(target,'w') as z:
   z.writestr('fabric.mod.json',json.dumps({'schemaVersion':1,'id':'example_identity','name':'Example Identity','version':'1.2.3','depends':{'example_library':'>=1.0'}}))
   if extra:z.writestr('assets/example_identity/lang/zh_cn.json',json.dumps({'damn.test.only':'测试资源'},ensure_ascii=False))
  return target
 def test_numbered_filename_and_resource_change_keep_local_metadata_separate_from_file_identity(self):
  first=self.jar('original.jar');before=scan(self.root)['mods'][0];raw=first.read_bytes()
  first.rename(first.with_name('0001.jar'));renamed=scan(self.root)['mods'][0]
  self.assertEqual(renamed['name'],'Example Identity');self.assertEqual([{k:v for k,v in x.items() if k!='source'} for x in renamed['components']],[{k:v for k,v in x.items() if k!='source'} for x in before['components']]);self.assertEqual([{k:v for k,v in x.items() if k!='source'} for x in renamed['dependencies']],[{k:v for k,v in x.items() if k!='source'} for x in before['dependencies']]);self.assertTrue(all(x['source'].startswith('0001.jar!') for x in renamed['components']));self.assertEqual(renamed['sha256'],before['sha256']);self.assertEqual(renamed['cfFingerprint'],curseforge_fingerprint(raw));self.assertEqual(renamed['sha1'],hashlib.sha1(raw).hexdigest())
  self.jar('0001.jar',True);modified=scan(self.root)['mods'][0]
  self.assertEqual(modified['components'],renamed['components']);self.assertEqual(modified['dependencies'],renamed['dependencies']);self.assertNotEqual(modified['sha1'],renamed['sha1']);self.assertNotEqual(modified['sha256'],renamed['sha256']);self.assertNotEqual(modified['cfFingerprint'],renamed['cfFingerprint'])
 def test_large_file_fingerprint_is_skipped_without_losing_sha_or_local_dependencies(self):
  jar=self.jar('0002.jar');raw=jar.read_bytes()
  with patch('scanner.CF_FINGERPRINT_LIMIT',1),patch('identity.curseforge_fingerprint') as fingerprint:
   result=scan(self.root)
  self.assertEqual(result['errors'],[]);mod=result['mods'][0];fingerprint.assert_not_called();self.assertIsNone(mod['cfFingerprint']);self.assertEqual(mod['sha1'],hashlib.sha1(raw).hexdigest());self.assertEqual(mod['components'][0]['id'],'example_identity');self.assertTrue(mod['dependencies'])

if __name__=='__main__':unittest.main()
