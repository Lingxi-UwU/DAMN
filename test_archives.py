import io,json,stat,tempfile,unittest,zipfile
from pathlib import Path
from test_damn import makejar,dep
from archives import scan_archive
class ArchiveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.mods=self.root/'mods';self.mods.mkdir();makejar(self.mods,'base.jar','base');makejar(self.mods,'addon.jar','addon',deps=dep('addon','base'))
 def tearDown(self):self.tmp.cleanup()
 def pack(self,name,entries):
  p=self.root/name
  with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
   for k,v in entries.items():z.writestr(k,v)
  return p
 def jar(self,name='base.jar'):return (self.mods/name).read_bytes()
 def test_full_zip_nested_root(self):
  p=self.pack('full.zip',{'MyPack/.minecraft/mods/base.jar':self.jar(),'MyPack/.minecraft/mods/addon.jar':self.jar('addon.jar'),'MyPack/.minecraft/kubejs/test.js':'const a="base:item";','MyPack/.minecraft/saves/world/region/r.0.0.mca':b'ignored'})
  r=scan_archive(p);self.assertEqual(r['archive']['jarFiles'],2);self.assertEqual(len(r['edges']),1);self.assertEqual(len(r['references']),1);self.assertEqual(r['archive']['extractedFiles'],3)
 def test_multiple_instances_require_choice(self):
  p=self.pack('multi.zip',{'a/mods/base.jar':self.jar(),'b/mods/base.jar':self.jar()});r=scan_archive(p)
  self.assertTrue(r['needsRoot']);self.assertEqual(r['roots'],['a','b']);self.assertEqual(scan_archive(p,root_hint='b')['archive']['jarFiles'],1)
 def test_uppercase_mods_and_extension(self):
  p=self.pack('caps.zip',{'PACK/MODS/BASE.JAR':self.jar()});self.assertEqual(scan_archive(p)['archive']['jarFiles'],1)
 def test_mrpack_manifest_without_jars(self):
  data={'formatVersion':1,'game':'minecraft','name':'Manifest Pack','versionId':'1','dependencies':{'minecraft':'1.21.1','neoforge':'21.1.1'},'files':[{'path':'mods/base.jar','hashes':{'sha1':'abc','sha512':'xyz'},'downloads':['https://example.invalid/base.jar'],'fileSize':100}]}
  p=self.pack('test.mrpack',{'modrinth.index.json':json.dumps(data)});r=scan_archive(p)
  self.assertEqual(r['archive']['jarFiles'],0);self.assertEqual(r['archive']['manifestOnly'],1);self.assertIsNone(r['mods'][0]['enabled']);self.assertFalse(r['edges']);self.assertFalse(any(i['kind']=='missing' for i in r['issues']))
 def test_mrpack_override_layer_and_actual_file(self):
  data={'formatVersion':1,'game':'minecraft','files':[{'path':'mods/base.jar'}],'dependencies':{}}
  p=self.pack('layer.mrpack',{'modrinth.index.json':json.dumps(data),'overrides/mods/base.jar':self.jar(),'overrides/config/test.json':'{"id":"base:old"}','client-overrides/config/test.json':'{"id":"base:new"}'})
  r=scan_archive(p);self.assertEqual(r['archive']['manifestOnly'],0);self.assertIn('base:new',r['references'][0]['snippet'])
 def test_curseforge_manifest_and_overrides(self):
  data={'manifestType':'minecraftModpack','manifestVersion':1,'name':'CF Test','minecraft':{'version':'1.21.1','modLoaders':[{'id':'neoforge-21.1.1','primary':True}]},'files':[{'projectID':123,'fileID':456,'required':True}],'overrides':'overrides'}
  p=self.pack('cf.zip',{'manifest.json':json.dumps(data),'overrides/mods/addon.jar':self.jar('addon.jar')});r=scan_archive(p)
  self.assertEqual(r['archive']['manifestOnly'],1);self.assertEqual(r['archive']['jarFiles'],1);self.assertFalse(any(i['kind']=='missing' for i in r['issues']));self.assertTrue(any(i['kind']=='unresolved' for i in r['issues']))
 def test_mrpack_side_unsupported(self):
  data={'formatVersion':1,'game':'minecraft','files':[{'path':'mods/client.jar','env':{'server':'unsupported'}}]}
  p=self.pack('side.mrpack',{'modrinth.index.json':json.dumps(data)});r=scan_archive(p,'server');self.assertEqual(r['archive']['manifestOnly'],0);self.assertEqual(r['archive']['skippedForSide'],1)
 def test_zip_slip_rejected(self):
  p=self.pack('bad.zip',{'../outside.jar':b'x','mods/base.jar':self.jar()})
  with self.assertRaises(ValueError):scan_archive(p)
 def test_absolute_path_rejected(self):
  p=self.pack('bad.zip',{'C:/bad.jar':b'x'})
  with self.assertRaises(ValueError):scan_archive(p)
 def test_manifest_path_traversal_rejected(self):
  p=self.pack('bad.mrpack',{'modrinth.index.json':json.dumps({'formatVersion':1,'game':'minecraft','files':[{'path':'../mods/a.jar'}]})})
  with self.assertRaises(ValueError):scan_archive(p)
 def test_symlink_rejected(self):
  p=self.root/'link.zip'
  with zipfile.ZipFile(p,'w') as z:
   i=zipfile.ZipInfo('mods/link.jar');i.create_system=3;i.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(i,'../../outside')
  with self.assertRaises(ValueError):scan_archive(p)
 def test_case_collision_rejected(self):
  p=self.pack('duplicate.zip',{'mods/base.jar':self.jar(),'mods/BASE.jar':self.jar()})
  with self.assertRaises(ValueError):scan_archive(p)
 def test_invalid_zip(self):
  p=self.root/'bad.zip';p.write_bytes(b'bad')
  with self.assertRaises(ValueError):scan_archive(p)
if __name__=='__main__':unittest.main()
