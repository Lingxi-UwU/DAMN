"""Public edition release and template contract."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen
from unittest.mock import patch
import app_info, desktop, research, scanner, server


class AppVersionTests(unittest.TestCase):
    def test_runtime_exports_share_release_and_public_edition(self):
        self.assertEqual(app_info.VERSION, '0.5.6')
        self.assertEqual(app_info.EDITION, 'public-source')
        for module in (desktop, scanner, server):
            self.assertEqual(module.VERSION, app_info.VERSION)
        self.assertTrue(research.USER_AGENT.startswith('DAMN/' + app_info.VERSION + ' '))

    def test_trusted_template_resolves_release_at_runtime(self):
        self.assertIn('__VERSION__', (server.HERE/'static/index.html').read_text(encoding='utf-8'))
        self.assertIn('__VERSION__', (server.HERE/'desktop-assets/splash.html').read_text(encoding='utf-8'))
        with patch('app_info.VERSION', '9.8.7'):
            self.assertIn('9.8.7', desktop.splash_html())
            self.assertNotIn('__VERSION__', desktop.splash_html())

    def test_ping_identifies_public_edition(self):
        with tempfile.TemporaryDirectory() as folder:
            http=server.create_local_server(0, folder)
            worker=threading.Thread(target=http.serve_forever, daemon=True);worker.start()
            try:
                with urlopen('http://127.0.0.1:'+str(http.server_port)+'/api/ping') as response:
                    value=json.load(response)
                self.assertEqual(value, {'app':'DAMN','version':app_info.VERSION,'edition':'public-source'})
                self.assertTrue(server.running_instance(http.server_port))
            finally:
                http.shutdown();worker.join(3);server.close_local_server(http)

    def test_new_scan_reports_use_same_release(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'mods').mkdir()
            report=scanner.scan(folder)
        self.assertEqual(report['version'], app_info.VERSION)


if __name__=='__main__':unittest.main()
