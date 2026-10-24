"""Windows desktop host for DAMN; no external browser and no remote UI."""
import argparse, ctypes, hashlib, json, logging, os, sys, threading
from pathlib import Path
from app_info import VERSION, render_version
from server import HERE, create_local_server, close_local_server, data_directory

TITLE='DAMN 公开源码版 · 模组依赖网络分析器'

def splash_html():
    return render_version((HERE/'desktop-assets'/'splash.html').read_text(encoding='utf-8'))

def error_message(text):
    if sys.platform=='win32':ctypes.windll.user32.MessageBoxW(None,text,'DAMN 启动提示',0x10)

def acquire_instance(root):
    if sys.platform!='win32':return None,False
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR];kernel.CreateMutexW.restype=wintypes.HANDLE
    stamp=hashlib.sha256(str(root.resolve()).casefold().encode()).hexdigest()[:20]
    handle=kernel.CreateMutexW(None,False,'Local\\DAMN.Public.Desktop.'+stamp)
    if not handle:raise OSError('无法创建应用实例。')
    return handle,ctypes.get_last_error()==183

def fit_desktop_window(work_area,dpi=96,preferred=(1120,700)):
    """Convert usable physical desktop bounds to pywebview logical coordinates."""
    import math
    left,top,right,bottom=work_area
    if right<=left or bottom<=top or dpi<=0:raise ValueError('无效的桌面可用区域。')
    scale=dpi/96.0
    available_w=(right-left)/scale;available_h=(bottom-top)/scale
    margin=min(32,available_w/10,available_h/10)
    width=max(1,min(preferred[0],math.floor(available_w-margin)))
    height=max(1,min(preferred[1],math.floor(available_h-margin)))
    x=round((left+(right-left-width*scale)/2)/scale)
    y=round((top+(bottom-top-height*scale)/2)/scale)
    return {'width':width,'height':height,'x':x,'y':y}

def desktop_work_area():
    if sys.platform!='win32':return (0,0,1280,800),96
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    try:
        user.SetProcessDpiAwarenessContext.argtypes=[wintypes.HANDLE];user.SetProcessDpiAwarenessContext.restype=wintypes.BOOL
        user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:user.SetProcessDPIAware()
    rect=wintypes.RECT()
    user.SystemParametersInfoW.argtypes=[wintypes.UINT,wintypes.UINT,ctypes.c_void_p,wintypes.UINT]
    if not user.SystemParametersInfoW(48,0,ctypes.byref(rect),0):raise ctypes.WinError(ctypes.get_last_error())
    try:
        user.GetDpiForSystem.restype=wintypes.UINT
        dpi=user.GetDpiForSystem() or 96
    except AttributeError:dpi=96
    return (rect.left,rect.top,rect.right,rect.bottom),dpi

class DesktopWindowBridge:
    def __init__(self):self._window=None
    def minimize_window(self):
        if self._window:self._window.minimize()
        return True
    def close_window(self):
        if self._window:self._window.destroy()
        return True

class StartupGate:
    """Reveal only when both the real page and the finite logo are ready."""
    def __init__(self,reveal):
        self.reveal=reveal;self.lock=threading.RLock();self.page=False;self.logo=False;self.revealed=False;self.cancelled=False
    def signal(self,part):
        with self.lock:
            if part=='page':self.page=True
            if part=='logo':self.logo=True
            if self.cancelled or self.revealed or not (self.page and self.logo):return
            self.revealed=True
        self.reveal()
    def cancel(self):
        with self.lock:self.cancelled=True

class SplashBridge:
    def __init__(self,done):self._done=done
    def splash_done(self):self._done();return True

def main():
    parser=argparse.ArgumentParser(description=TITLE)
    parser.add_argument('--data-dir',help=argparse.SUPPRESS)
    parser.add_argument('--smoke-test',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.smoke_test and not args.data_dir:parser.error('smoke tests require an isolated data directory')
    root=data_directory(args.data_dir);root.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=root/'desktop.log',level=logging.WARNING,encoding='utf-8',format='%(asctime)s %(levelname)s %(message)s')
    handle=None;server=None;thread=None;gate=None;fallback=None
    try:
        handle,exists=acquire_instance(root)
        if exists:
            win=ctypes.windll.user32.FindWindowW(None,TITLE)
            if win:ctypes.windll.user32.ShowWindow(win,9);ctypes.windll.user32.SetForegroundWindow(win)
            return
        work_area,dpi=desktop_work_area()
        bounds=fit_desktop_window(work_area,dpi)
        splash_bounds=fit_desktop_window(work_area,dpi,(560,320))
        import webview
        server=create_local_server(0,root);server.desktop_host=True
        thread=threading.Thread(target=server.serve_forever,daemon=True,name='DAMN-public-local-api');thread.start()
        url='http://127.0.0.1:'+str(server.server_port)+'/'
        webview.settings.update(ALLOW_DOWNLOADS=True,ALLOW_FILE_URLS=False,OPEN_EXTERNAL_LINKS_IN_BROWSER=True,DRAG_REGION_DIRECT_TARGET_ONLY=True)
        bridge=DesktopWindowBridge()
        window=webview.create_window(TITLE,url,js_api=bridge,**bounds,min_size=(bounds['width'],bounds['height']),resizable=False,fullscreen=False,frameless=True,easy_drag=False,shadow=True,hidden=True,background_color='#f4f8f1',text_select=True)
        bridge._window=window
        completed=threading.Event();logo_complete=threading.Event()
        def verify():
            try:
                from urllib.request import Request,urlopen
                import ssl
                ssl.create_default_context()
                html=urlopen(url,timeout=5).read().decode('utf-8')
                for asset in ('workbench.css','motion.js','taxonomy.js'):
                    with urlopen(url+asset,timeout=5) as response:assert response.status==200
                with urlopen(Request(url+'api/settings',headers={'X-DAMN-Token':server.token}),timeout=5) as response:settings=json.load(response)
                assert not settings['configured'] and not settings['hasKey']
                state={'windowLoaded':True,'renderer':'edgechromium','version':VERSION,'port':server.server_port,'animatedSplashCompleted':gate.logo,'splashBridgeCompleted':logo_complete.is_set(),'nativeSetupGate': 'data-desktop-host="true"' in html,'freshConfiguration':True,'assetsAvailable':True,'tlsContextAvailable':True,'frameless':window.frameless,'resizable':window.resizable,'fullscreen':window.fullscreen,'logicalBounds':bounds,'workArea':work_area,'dpi':dpi,'maximizeAllowed':bool(window.native.MaximizeBox),'physicalBounds':[int(window.native.Bounds.X),int(window.native.Bounds.Y),int(window.native.Bounds.Width),int(window.native.Bounds.Height)],'windowControlsInMarkup':'id="desktop-window-controls"' in html}
                Path(args.smoke_test).write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');completed.set()
            except Exception:
                logging.exception('Desktop smoke test failed')
                Path(args.smoke_test).write_text(json.dumps({'error':'desktop smoke test failed'}),encoding='utf-8')
            finally:window.destroy()
        def reveal():
            if fallback:fallback.cancel()
            window.show()
            window.run_js("document.body.dataset.desktopReady='true';window.dispatchEvent(new Event('damn-desktop-ready'));")
            splash.destroy()
            if args.smoke_test:threading.Thread(target=verify,daemon=True).start()
        gate=StartupGate(reveal)
        def logo_done():logo_complete.set();gate.signal('logo')
        splash=webview.create_window('DAMN 正在启动',html=splash_html(),js_api=SplashBridge(logo_done),**splash_bounds,min_size=(splash_bounds['width'],splash_bounds['height']),resizable=False,frameless=True,easy_drag=False,shadow=True,background_color='#f4f8f1')
        def loaded():gate.signal('page')
        def splash_loaded():
            nonlocal fallback
            fallback=threading.Timer(3,lambda:gate.signal('logo'));fallback.daemon=True;fallback.start()
        def splash_closing():
            if not gate.revealed:gate.cancel();window.destroy()
        def main_closing():
            gate.cancel()
            if fallback:fallback.cancel()
            if not gate.revealed:splash.destroy()
        window.events.loaded+=loaded;splash.events.loaded+=splash_loaded
        splash.events.closing+=splash_closing;window.events.closing+=main_closing
        def pick_directory():
            result=window.create_file_dialog(webview.FileDialog.FOLDER)
            return result[0] if result else ''
        server.directory_picker=pick_directory
        if args.smoke_test:
            def timeout():
                if not completed.wait(40):
                    Path(args.smoke_test).write_text(json.dumps({'error':'desktop load timeout'}),encoding='utf-8');window.destroy();splash.destroy()
            threading.Thread(target=timeout,daemon=True).start()
        webview.start(gui='edgechromium',private_mode=False,storage_path=str(root/'webview'),debug=False,icon=str(HERE/'desktop-assets'/'damn.ico'))
    except Exception:
        logging.exception('Desktop startup failed')
        if not args.smoke_test:error_message('DAMN 未能启动。请确认已安装 Microsoft Edge WebView2 运行时。\n可查看本地应用数据目录中的 desktop.log。')
        if args.smoke_test:Path(args.smoke_test).write_text(json.dumps({'error':'desktop startup failed'}),encoding='utf-8')
    finally:
        if gate:gate.cancel()
        if fallback:fallback.cancel()
        if server:
            server.shutdown()
            if thread:thread.join(timeout=3)
            close_local_server(server)
        if handle:
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle(handle)

if __name__=='__main__':main()
