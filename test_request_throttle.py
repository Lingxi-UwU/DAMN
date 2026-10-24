import io,unittest,time
from email.message import Message
from urllib.error import HTTPError
from unittest.mock import Mock,patch
import research as r
class RequestThrottleTests(unittest.TestCase):
 def test_slots_are_shared_by_host_and_stop_at_deadline(self):
  clock=[10.0]
  with patch.dict(r.RATE_NEXT,{},clear=True),patch.object(r.time,'monotonic',side_effect=lambda:clock[0]),patch.object(r.time,'sleep',side_effect=lambda value:clock.__setitem__(0,clock[0]+value)):
   r.request_slot('api.modrinth.com',20);r.request_slot('api.modrinth.com',20)
   self.assertAlmostEqual(clock[0],10.5)
   with self.assertRaises(ValueError):r.request_slot('api.modrinth.com',10.8)
   r.request_slot('api.curseforge.com',20)
   self.assertAlmostEqual(clock[0],10.5)
 def test_cached_data_remains_available_during_server_cooldown(self):
  url='https://api.modrinth.com/v2/project/test'
  with patch.dict(r.CACHE,{url:(time.time(),'cached')},clear=True),patch.dict(r.COOLDOWN,{'api.modrinth.com':(time.time()+120,'limited')},clear=True),patch.object(r,'request_slot') as slot:
   self.assertEqual(r.fetch(url),'cached');slot.assert_not_called()
 def test_rate_limit_headers_and_retry_after_are_respected(self):
  with patch.dict(r.COOLDOWN,{},clear=True),patch.object(r.time,'time',return_value=100):
   r.rate_headers('api.modrinth.com',{'X-Ratelimit-Remaining':'0','X-Ratelimit-Reset':'42'})
   self.assertEqual(r.COOLDOWN['api.modrinth.com'][0],142)
   self.assertEqual(r.retry_seconds({'Retry-After':'45'}),45)
   self.assertEqual(r.retry_seconds({'Retry-After':'Thu, 01 Jan 1970 00:03:20 GMT'}),100)
   self.assertEqual(r.retry_seconds({'Retry-After':'nan'}),120)
 def test_429_is_not_retried_and_does_not_log_credentials(self):
  url='https://api.curseforge.com/v1/mods/123';headers=Message();headers['Retry-After']='30'
  opener=Mock();opener.open.side_effect=HTTPError(url,429,'limited',headers,io.BytesIO())
  with patch.dict(r.CACHE,{},clear=True),patch.dict(r.COOLDOWN,{},clear=True),patch.object(r,'request_slot'),patch.object(r,'build_opener',return_value=opener),patch.object(r.time,'time',return_value=100):
   with self.assertRaises(ValueError) as error:r.fetch(url,'not-a-real-key')
   self.assertIn('429',str(error.exception));self.assertNotIn('not-a-real-key',str(error.exception));self.assertEqual(r.COOLDOWN['api.curseforge.com'][0],130)
   with self.assertRaises(ValueError):r.fetch(url,'not-a-real-key')
   self.assertEqual(opener.open.call_count,1)
   self.assertTrue(opener.open.call_args.args[0].get_header('User-agent').startswith('DAMN/'))
if __name__=='__main__':unittest.main()
