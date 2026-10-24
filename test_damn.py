import io,json,tempfile,unittest,zipfile,threading
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from scanner import scan,matches,impact
from server import ai_request,Handler

def makejar(folder,name,ident,version='1.0.0',deps='',extras=None,flavor='NeoForge'):
    with zipfile.ZipFile(folder/name,'w') as z:
        if flavor=='Fabric': z.writestr('fabric.mod.json',json.dumps({'schemaVersion':1,'id':ident,'version':version,'name':ident,**(extras or {})}))
        else:
            z.writestr('META-INF/neoforge.mods.toml','modLoader="javafml"\nloaderVersion="[1,)"\nlicense="test"\n[[mods]]\nmodId="'+ident+'"\nversion="'+version+'"\ndisplayName="'+ident+'"\n'+deps)
            for p,b in (extras or {}).items(): z.writestr(p,b)

def dep(owner,target,version='*',typ='required',side='BOTH'):
    return '\n[[dependencies.'+owner+']]\nmodId="'+target+'"\ntype="'+typ+'"\nversionRange="'+version+'"\nside="'+side+'"\n'

class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.mods=self.root/'mods';self.mods.mkdir()
    def tearDown(self): self.temp.cleanup()
    def test_maven_bounds_and_unknown(self):
        self.assertTrue(matches('1.5.0','[1,2)'));self.assertFalse(matches('2.0','[1,2)'))
        self.assertTrue(matches('2','[2]'));self.assertFalse(matches('1.9','[2]'))
        self.assertIsNone(matches('1.0-beta','[1,2)'));self.assertIsNone(matches('2','1.0'))
        self.assertIsNone(matches('1','(,1],[2,)'))
    def test_fabric_semver(self):
        self.assertTrue(matches('1.4.2','>=1.2 <2','Fabric'));self.assertFalse(matches('2','^1.2','Fabric'))
        self.assertTrue(matches('0.2.5','^0.2.1','Fabric'));self.assertFalse(matches('0.3','^0.2.1','Fabric'))
        self.assertTrue(matches('1.4.9','~1.4','Fabric'));self.assertFalse(matches('1.5','~1.4','Fabric'))
        self.assertTrue(matches('2.1',['1.x','2.x'],'Fabric'))
    def test_disabled_dependency_is_missing(self):
        makejar(self.mods,'base.jar.disabled','base');makejar(self.mods,'addon.jar','addon',deps=dep('addon','base'))
        result=scan(self.root);self.assertEqual([x['kind'] for x in result['issues']],['missing']);self.assertFalse(result['edges'])
    def test_sha1_matches_actual_jar_bytes(self):
        import hashlib
        makejar(self.mods,'base.jar','base');result=scan(self.root)
        self.assertEqual(result['mods'][0]['sha1'],hashlib.sha1((self.mods/'base.jar').read_bytes()).hexdigest())
    def test_transitive_impact(self):
        makejar(self.mods,'base.jar','base');makejar(self.mods,'addon.jar','addon',deps=dep('addon','base'));makejar(self.mods,'more.jar','more',deps=dep('more','addon'))
        result=scan(self.root);key=next(m['key'] for m in result['mods'] if m['name']=='base')
        self.assertEqual(len(impact(result,key)['mods']),2);self.assertFalse(result['issues'])
    def test_nested_jar_and_same_file_components(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z: z.writestr('fabric.mod.json',json.dumps({'schemaVersion':1,'id':'inner','version':'1.0'}))
        extras={'META-INF/jarjar/metadata.json':json.dumps({'jars':[{'path':'META-INF/jarjar/inner.jar'}]}),'META-INF/jarjar/inner.jar':buf.getvalue()}
        makejar(self.mods,'bundle.jar','bundle',deps=dep('bundle','inner','[1,)'),extras=extras)
        result=scan(self.root);self.assertEqual(len(result['mods'][0]['components']),2);self.assertFalse(result['issues']);self.assertFalse(result['edges'])
    def test_duplicate_top_level_mod(self):
        makejar(self.mods,'one.jar','same');makejar(self.mods,'two.jar','same');result=scan(self.root)
        self.assertTrue(any(x['kind']=='duplicate' for x in result['issues']))
    def test_conflict_only_for_matching_range(self):
        makejar(self.mods,'base.jar','base',version='2.0');makejar(self.mods,'addon.jar','addon',deps=dep('addon','base','[1,2)','incompatible'))
        self.assertFalse(scan(self.root)['issues'])
        makejar(self.mods,'base.jar','base',version='1.5');self.assertEqual(scan(self.root)['issues'][0]['kind'],'conflict')
    def test_side_specific_dependency(self):
        makejar(self.mods,'addon.jar','addon',deps=dep('addon','clientonly','*','required','CLIENT'))
        self.assertTrue(scan(self.root,'client')['issues']);self.assertFalse(scan(self.root,'server')['issues'])
    def test_client_fabric_mod_is_inactive_on_server(self):
        makejar(self.mods,'client.jar','client',flavor='Fabric',extras={'environment':'client','depends':{'missing':'*'}})
        self.assertFalse(scan(self.root,'server')['issues']);self.assertTrue(scan(self.root,'client')['issues'])
    def test_references_have_line_and_never_execute(self):
        makejar(self.mods,'base.jar','base');scripts=self.root/'kubejs/server_scripts';scripts.mkdir(parents=True)
        (scripts/'recipe.js').write_text('// comment\nServerEvents.recipes(e => e.remove({output:"base:test"}));',encoding='utf-8')
        result=scan(self.root);self.assertEqual(result['references'][0]['line'],2);self.assertEqual(result['references'][0]['id'],'base')
    def test_bad_jar_is_reported(self):
        (self.mods/'bad.jar').write_bytes(b'not a zip');result=scan(self.root);self.assertEqual(result['fileCount'],1);self.assertEqual(len(result['errors']),1)
    def test_declared_environment_version(self):
        (self.root/'mmc-pack.json').write_text(json.dumps({'components':[{'uid':'net.minecraft','version':'1.21.1'},{'uid':'net.neoforged','version':'21.1.1'}]}))
        makejar(self.mods,'addon.jar','addon',deps=dep('addon','minecraft','[1.20,1.21)'))
        result=scan(self.root);self.assertEqual(result['issues'][0]['kind'],'version')
    def test_unknown_environment_is_not_pass(self):
        makejar(self.mods,'addon.jar','addon',deps=dep('addon','minecraft','[1.21,)'));self.assertEqual(scan(self.root)['unchecked'],1)
    def test_empty_or_wrong_path(self):
        self.assertEqual(scan(self.root)['fileCount'],0)
        with self.assertRaises(ValueError):scan(self.root/'nope')

class AIStub(BaseHTTPRequestHandler):
    received=None
    def do_POST(self):
        AIStub.received=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        data=json.dumps({'choices':[{'message':{'content':'测试回答'}}],'usage':{'total_tokens':12},'model':'stub'}).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
class AITests(unittest.TestCase):
    def test_local_ai_contract_without_paid_request(self):
        server=HTTPServer(('127.0.0.1',0),AIStub);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result=ai_request({'endpoint':'http://127.0.0.1:'+str(server.server_port)+'/v1','model':'stub','question':'解释依赖','context':'{}'})
            self.assertEqual(result['answer'],'测试回答');self.assertEqual(result['usage']['total_tokens'],12)
            self.assertEqual(AIStub.received['model'],'stub');self.assertEqual(AIStub.received['messages'][0]['role'],'system')
        finally:server.shutdown();server.server_close()
    def test_remote_http_rejected(self):
        with self.assertRaises(ValueError):ai_request({'endpoint':'http://example.com/v1','model':'x','question':'x'})
    def test_credentials_in_url_rejected(self):
        with self.assertRaises(ValueError):ai_request({'endpoint':'https://user:password@example.com','model':'x','question':'x'})
if __name__=='__main__':unittest.main(verbosity=2)
