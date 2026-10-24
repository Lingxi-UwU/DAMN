import json,unittest
from unittest.mock import patch,Mock
import ai_agent as a
from server import APIError,ai_request
URL='https://modrinth.com/mod/library'
def info():return {'sources':[{'url':URL,'site':'Modrinth','title':'Library','excerpt':'Shared library','match':'名称相符（未核对版本）'}],'sites':[{'site':'Modrinth','ok':True}],'platformDependencies':[],'notes':[]}
def final():return {'answer':json.dumps({'summary':'前置库。','category':'开发库','evidence':[URL],'relations':[]}), 'usage':{'total_tokens':10},'model':'stub','tool_calls':[]}
def call(name='search_mod_sources',args=None,ident='s1'):
 return {'id':ident,'type':'function','function':{'name':name,'arguments':json.dumps(args or {'subject':0,'query':'Library'})}}
class AgentTests(unittest.TestCase):
 def setUp(self):self.payload={'question':'解释','context':'{}'};self.subjects=[{'name':'Library','kind':'manifest'}]
 def test_independent_tool_round_then_final(self):
  seen=[]
  def chat(payload,**kwargs):
   seen.append(kwargs)
   return {'tool_calls':[call()],'usage':{'total_tokens':5}} if len(seen)==1 else final()
  with patch.object(a,'research',return_value=info()) as lookup:
   result,materials=a.online_analysis(self.payload,self.subjects,[info()],'',chat)
  self.assertEqual(lookup.call_count,1);self.assertEqual(result['aiSearch']['mode'],'tools');self.assertEqual(result['usage']['total_tokens'],15)
  self.assertEqual(seen[0]['tool_choice'],'required');self.assertEqual(seen[1]['messages'][-1]['role'],'tool');self.assertEqual(len(materials[0]['sources']),1)
 def test_unsupported_tool_request_falls_back_truthfully(self):
  chat=Mock(side_effect=[APIError('bad tools',400),final()])
  result,_=a.online_analysis(self.payload,self.subjects,[info()],'',chat)
  self.assertEqual(result['aiSearch']['mode'],'review_only');self.assertIn('未接受',result['aiSearch']['message']);self.assertEqual(chat.call_count,2)
 def test_authentication_failure_does_not_retry(self):
  chat=Mock(side_effect=APIError('bad auth',401))
  with self.assertRaises(APIError):a.online_analysis(self.payload,self.subjects,[],'',chat)
  self.assertEqual(chat.call_count,1)
 def test_ignored_tool_choice_is_not_reported_as_search(self):
  result,_=a.online_analysis(self.payload,self.subjects,[info()],'',Mock(return_value=final()))
  self.assertEqual(result['aiSearch']['mode'],'review_only');self.assertFalse(result['aiSearch']['calls'])
 def test_tool_budget_is_bounded(self):
  many=[call(ident='s'+str(i)) for i in range(6)]
  chat=Mock(side_effect=[{'tool_calls':many},final()])
  with patch.object(a,'research',return_value=info()) as lookup:
   result,_=a.online_analysis(self.payload,self.subjects,[],'',chat)
  self.assertEqual(lookup.call_count,4);self.assertEqual(sum(x['ok'] for x in result['aiSearch']['calls']),4);self.assertIsNone(chat.call_args.kwargs['tools'])
 def test_disallowed_url_never_fetches(self):
  with patch.object(a,'fetch') as fetch:
   with self.assertRaises(ValueError):a.run_tool('read_mod_source',{'subject':0,'url':'http://127.0.0.1/private'},self.subjects)
   fetch.assert_not_called()
 def test_unknown_tool_and_subject_are_rejected(self):
  with self.assertRaises(ValueError):a.run_tool('delete_file',{'subject':0},self.subjects)
  with self.assertRaises(ValueError):a.run_tool('search_mod_sources',{'subject':True,'query':'x'},self.subjects)
 def test_reader_passes_only_cf_key_to_cf_api(self):
  with patch.object(a,'fetch',return_value='{"data":{}}') as fetch:
   a.run_tool('read_mod_source',{'subject':0,'url':'https://api.curseforge.com/v1/mods/1'},self.subjects,'fake-cf')
   self.assertEqual(fetch.call_args.args[1],'fake-cf')
   a.run_tool('read_mod_source',{'subject':0,'url':URL},self.subjects,'fake-cf');self.assertIsNone(fetch.call_args.args[1])
 def test_merge_deduplicates_sources_but_keeps_different_evidence(self):
  x=info();y=info();y['sources']+=[{'url':'https://www.mcmod.cn/class/1.html'}]
  result=a.merge_materials([x],[y]);self.assertEqual(len(result[0]['sources']),2)
 def test_manifest_never_becomes_verified_local_dependency(self):
  result=a.reconcile(self.subjects,[info()],{'category':'开发库','relations':[{'target':'Other','kind':'required'}]})
  self.assertFalse(result['matched']);self.assertTrue(result['unknown']);self.assertEqual(len(result['added']),2)
 def test_local_relation_match_conflict_and_dedup(self):
  mod={'name':'Test','dependencies':[{'target':'base','type':'required'}]}
  x=info();x['platformDependencies']=[{'target':'base','kind':'required'},{'target':'base','kind':'required'},{'target':'base','kind':'incompatible'}]
  result=a.reconcile([mod],[x],{'relations':[]})
  self.assertEqual(len(result['matched']),1);self.assertEqual(len(result['conflicts']),1)
 def test_precise_version_conflict(self):
  x=info();x['sources'][0].update(match='清单哈希对应的平台版本',versionNumber='2.0')
  result=a.reconcile([{'name':'Library','version':'1.0'}],[x],None);self.assertTrue(result['conflicts'])

class ProtocolTests(unittest.TestCase):
 def test_chat_http_tool_roundtrip(self):
  import threading
  from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
  received=[]
  class Stub(BaseHTTPRequestHandler):
   def do_POST(self):
    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));received.append(body)
    msg={'content':None,'tool_calls':[call()]} if len(received)==1 else {'content':'已核对'}
    raw=json.dumps({'choices':[{'message':msg}],'model':'tool-stub','usage':{'total_tokens':5}}).encode()
    self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def log_message(self,*args):pass
  http=ThreadingHTTPServer(('127.0.0.1',0),Stub);threading.Thread(target=http.serve_forever,daemon=True).start()
  try:
   payload={'endpoint':'http://127.0.0.1:'+str(http.server_port)+'/v1','model':'tool-stub','question':'解释','context':'{}'}
   with patch.object(a,'research',return_value=info()):result,_=a.online_analysis(payload,[{'name':'Library'}],[],'',ai_request)
   self.assertEqual(result['answer'],'已核对');self.assertEqual(result['aiSearch']['mode'],'tools')
   self.assertEqual(received[0]['tools'][0]['type'],'function')
   self.assertEqual(received[1]['messages'][-1]['tool_call_id'],'s1')
   self.assertEqual(result['usage']['total_tokens'],10)
  finally:http.shutdown();http.server_close()
 def test_compatibility_fallback_uses_http_status(self):
  import threading
  from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
  received=[]
  class Stub(BaseHTTPRequestHandler):
   def do_POST(self):
    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));received.append(body)
    if 'tools' in body:self.send_response(400);self.end_headers();return
    raw=json.dumps({'choices':[{'message':{'content':'仅复核'}}]}).encode()
    self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def log_message(self,*args):pass
  http=ThreadingHTTPServer(('127.0.0.1',0),Stub);threading.Thread(target=http.serve_forever,daemon=True).start()
  try:
   payload={'endpoint':'http://127.0.0.1:'+str(http.server_port)+'/v1','model':'stub','question':'解释','context':'{}'}
   result,_=a.online_analysis(payload,[{'name':'Library'}],[info()],'',ai_request)
   self.assertEqual(result['aiSearch']['mode'],'review_only');self.assertEqual(len(received),2);self.assertNotIn('tools',received[1])
  finally:http.shutdown();http.server_close()

if __name__=='__main__':unittest.main()
