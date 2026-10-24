import tempfile,threading,unittest,json
from pathlib import Path
from urllib.request import Request,urlopen
from unittest.mock import patch
import server
class DesktopServerTests(unittest.TestCase):
 def test_server_is_loopback_only_and_native_picker_returns_cancel_or_path(self):
  with tempfile.TemporaryDirectory() as folder:
   http=server.create_local_server(0,folder);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
   try:
    self.assertEqual(http.server_address[0],'127.0.0.1');self.assertEqual(http.settings.directory,Path(folder)/'.damn-public-user')
    base='http://127.0.0.1:'+str(http.server_port)
    def choose():
     with urlopen(Request(base+'/api/choose',data=b'{}',headers={'X-DAMN-Token':http.token,'Content-Type':'application/json'})) as response:return json.load(response)
    with patch('server.subprocess.run',side_effect=AssertionError('native picker must not relaunch the exe')):
     http.directory_picker=lambda:None;self.assertEqual(choose()['path'],'')
     http.directory_picker=lambda:'D:/中文实例';self.assertEqual(choose()['path'],'D:/中文实例')
    self.assertFalse((Path(folder)/'.damn-public-user'/'settings.json').exists(),'startup does not save any configuration')
   finally:http.shutdown();worker.join(2);server.close_local_server(http)
 def test_shutdown_cancels_existing_workers(self):
  from unittest.mock import Mock
  with tempfile.TemporaryDirectory() as folder:
   http=server.create_local_server(0,folder);a=Mock();a.current.return_value={'id':'fixture'};http.enrichment=a;http.prerequisites=Mock();http.identities=Mock()
   server.close_local_server(http);a.cancel.assert_called_once_with('fixture');http.prerequisites.close.assert_called_once();http.identities.close.assert_called_once()
class StartupGateTests(unittest.TestCase):
 def test_waits_for_both_readiness_signals_and_reveals_exactly_once(self):
  from desktop import StartupGate
  from unittest.mock import Mock
  for order in [('page','logo'),('logo','page')]:
   reveal=Mock();gate=StartupGate(reveal);gate.signal(order[0]);reveal.assert_not_called();gate.signal(order[1]);gate.signal('page');gate.signal('logo');reveal.assert_called_once()
 def test_closing_cancels_delayed_reveal(self):
  from desktop import StartupGate
  from unittest.mock import Mock
  reveal=Mock();gate=StartupGate(reveal);gate.signal('page');gate.cancel();gate.signal('logo');reveal.assert_not_called()
class DesktopGeometryTests(unittest.TestCase):
 def test_frame_fits_work_area_at_common_windows_scaling(self):
  from desktop import fit_desktop_window
  for area in [(0,0,1920,1040),(0,0,1366,728),(0,40,2560,1440)]:
   for dpi in (96,120,144,192):
    b=fit_desktop_window(area,dpi);scale=dpi/96
    self.assertLessEqual(b['width']*scale,area[2]-area[0]);self.assertLessEqual(b['height']*scale,area[3]-area[1])
    self.assertGreaterEqual(b['x']*scale,area[0]-1);self.assertGreaterEqual(b['y']*scale,area[1]-1)
    self.assertLessEqual((b['x']+b['width'])*scale,area[2]+1);self.assertLessEqual((b['y']+b['height'])*scale,area[3]+1)
 def test_main_and_splash_share_desktop_center(self):
  from desktop import fit_desktop_window
  area=(0,0,1920,1040);a=fit_desktop_window(area,120);b=fit_desktop_window(area,120,(560,320))
  self.assertLessEqual(abs(a['x']+a['width']/2-b['x']-b['width']/2),1)
  self.assertLessEqual(abs(a['y']+a['height']/2-b['y']-b['height']/2),1)
 def test_chrome_bridge_only_minimizes_or_closes_the_bound_window(self):
  from desktop import DesktopWindowBridge
  from unittest.mock import Mock
  b=DesktopWindowBridge();self.assertTrue(b.minimize_window());b._window=Mock();b.minimize_window();b.close_window();b._window.minimize.assert_called_once();b._window.destroy.assert_called_once()
if __name__=='__main__':unittest.main()
