import io,json,time,unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError
import research

class MirrorSearchTests(unittest.TestCase):
 def setUp(self):
  self.old_cache=dict(research.CACHE);self.old_cooldown=dict(research.COOLDOWN)
  research.CACHE.clear();research.COOLDOWN.clear()
 def tearDown(self):
  research.CACHE.clear();research.CACHE.update(self.old_cache)
  research.COOLDOWN.clear();research.COOLDOWN.update(self.old_cooldown)
 def test_mirror_only_allows_project_search_and_project_ids(self):
  for suffix in ['/modrinth/v2/search?query=test','/modrinth/v2/project/project-slug','/curseforge/v1/mods/search?gameId=432','/curseforge/v1/mods/123456']:
   self.assertTrue(research.permitted('https://mod.mcimirror.top'+suffix),suffix)
  for value in ['http://mod.mcimirror.top/modrinth/v2/search','https://mod.mcimirror.top:444/modrinth/v2/search','https://mod.mcimirror.top:bad/modrinth/v2/search','https://key@mod.mcimirror.top/modrinth/v2/search','https://mod.mcimirror.top.evil.test/modrinth/v2/search','https://mod.mcimirror.top/modrinth/v2/project/a/../../versions','https://mod.mcimirror.top/modrinth/v2/search#secret','https://mod.mcimirror.top/curseforge/v1/mods/name','https://mod.mcimirror.top/modrinth/v2/version/id','https://mod.mcimirror.top/download/file.jar']:
   self.assertFalse(research.permitted(value),value)
 def test_mirror_never_accepts_key_or_payload_even_with_cache(self):
  url='https://mod.mcimirror.top/modrinth/v2/search?query=test'
  research.CACHE[url]=(time.time(),'{}')
  with patch('research.build_opener') as opener:
   with self.assertRaisesRegex(ValueError,'官方 API'):research.fetch(url,'test-secret')
   with self.assertRaisesRegex(ValueError,'公开项目查询'):research.fetch(url,payload={'test':'private'})
   opener.assert_not_called()
 def test_public_search_has_no_auth_and_reuses_cache(self):
  class Response:
   def __init__(self):
    self.headers=Message();self.headers['Content-Type']='application/json';self.stream=io.BytesIO(b'{"hits":[]}')
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read1(self,n):return self.stream.read(n)
  captured=[]
  class Opener:
   def open(self,request,timeout):captured.append(request);return Response()
  url='https://mod.mcimirror.top/modrinth/v2/search?query=public'
  with patch('research.build_opener',return_value=Opener()),patch('research.request_slot'):
   self.assertEqual(json.loads(research.fetch(url)),{'hits':[]});research.fetch(url)
  self.assertEqual(len(captured),1);self.assertIsNone(captured[0].data)
  self.assertFalse(any(key.lower() in ('authorization','x-api-key') for key in captured[0].headers))
 def test_service_unavailable_respects_retry_and_does_not_loop(self):
  url='https://mod.mcimirror.top/curseforge/v1/mods/search?gameId=432'
  headers=Message();headers['Retry-After']='60'
  with patch('research.build_opener') as opener,patch('research.request_slot'):
   opener.return_value.open.side_effect=HTTPError(url,503,'Unavailable',headers,None)
   with self.assertRaisesRegex(ValueError,'HTTP 503'):research.fetch(url)
   with self.assertRaisesRegex(ValueError,'暂缓重试'):research.fetch(url)
   self.assertEqual(opener.return_value.open.call_count,1)
  self.assertGreater(research.COOLDOWN['mod.mcimirror.top'][0],time.time()+55)

if __name__=='__main__':unittest.main()
