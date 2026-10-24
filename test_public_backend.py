"""Public edition boundaries and local-only fallback contracts."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import app_info
from appearance import AppearanceStore
from desktop import DesktopWindowBridge
import server


class PublicBoundariesTests(unittest.TestCase):
    def test_fixed_appearance_does_not_read_or_write_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'not-created';store=AppearanceStore(root)
            state=store.public()
            self.assertEqual(state['theme'], 'forest')
            self.assertFalse(state['available'])
            self.assertEqual(state['code'], 'public_feature_unavailable')
            for report in ({}, {'mods':[{'key':'example'}]}, None):store.record_analysis(report)
            self.assertEqual(store.public(), state)
            state['theme']='external-change'
            self.assertEqual(store.public()['theme'], 'forest')
            self.assertFalse(root.exists())
            self.assertFalse(hasattr(store, 'redeem'))
            self.assertFalse(hasattr(DesktopWindowBridge(), 'open_sponsor_page'))

    def test_default_profiles_are_separate_for_source_and_frozen_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(server.os.environ, {'LOCALAPPDATA':folder,'DAMN_PUBLIC_DATA_DIR':''}):
                for frozen in (False, True):
                    with patch('server.sys.frozen', frozen, create=True):
                        self.assertEqual(server.data_directory(), Path(folder)/'DAMN-Public')
            chosen=Path(folder)/'explicit-public-profile'
            with patch.dict(server.os.environ, {'DAMN_PUBLIC_DATA_DIR':str(chosen)}):
                self.assertEqual(server.data_directory(), chosen.resolve())
                self.assertEqual(server.data_directory(folder), Path(folder).resolve())

    def test_no_private_source_or_configuration_is_in_distribution(self):
        for name in ('activation_client.py','test_activation_client.py','test_appearance.py',
                     'test_personalization.cjs','.damn-user','.damn-public-user'):
            self.assertFalse((server.HERE/name).exists(), name)

    def test_demo_is_synthetic_and_has_no_private_path(self):
        report=json.loads((server.HERE/'demo.json').read_text(encoding='utf-8'))
        self.assertTrue(report['demo'])
        self.assertEqual(report['pack'], 'Public Synthetic Demo')
        self.assertEqual(report['root'], 'synthetic://public-demo')
        self.assertEqual(len(report['mods']), 6)
        self.assertTrue(all(mod['components'][0]['id'].startswith('example_') for mod in report['mods']))
        raw=json.dumps(report)
        self.assertNotIn('AppData', raw)
        self.assertNotIn('Users', raw)
        self.assertNotIn('Codex', raw)


class PublicAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.http=server.create_local_server(0, self.temp.name)
        self.worker=threading.Thread(target=self.http.serve_forever, daemon=True);self.worker.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.http.shutdown();self.worker.join(3);server.close_local_server(self.http)
    def request(self, method, route, body=None):
        connection=http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            raw=json.dumps(body).encode('utf-8') if body is not None else None
            connection.request(method,route,raw,{'X-DAMN-Token':self.http.token,'Content-Type':'application/json'})
            response=connection.getresponse();return response.status,json.loads(response.read())
        finally:connection.close()
    def test_private_actions_fail_truthfully_without_writes_or_network(self):
        with patch('server.build_opener', side_effect=AssertionError('no outbound request')):
            status,state=self.request('GET','/api/appearance')
            self.assertEqual(status,200);self.assertEqual(state['theme'],'forest')
            for route,body in (('/api/appearance',{'theme':'forest'}),
                               ('/api/appearance/event',{'event':'unused'}),
                               ('/api/appearance/redeem',{'code':'unused'})):
                with self.subTest(route=route):
                    status,state=self.request('POST',route,body)
                    self.assertEqual(status,410);self.assertEqual(state['code'],'public_feature_unavailable')
            status,state=self.request('POST','/api/updates/check',{})
            self.assertEqual(status,501);self.assertEqual(state['status'],'unavailable')
        self.assertFalse((Path(self.temp.name)/app_info.USER_DATA_SUBDIRECTORY).exists())
    def test_analysis_progress_hook_has_no_store_side_effects(self):
        handler=object.__new__(server.Handler);handler.server=Mock()
        handler.record_appearance_analysis({'mods':[{'key':'example'}]})
        handler.server.appearance.record_analysis.assert_not_called()


if __name__=='__main__':unittest.main()
