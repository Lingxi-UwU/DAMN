"""Portable local settings; Windows keys encrypted using user-bound DPAPI."""
import base64, json, sys, threading, secrets
from pathlib import Path
from urllib.parse import urlsplit

def endpoint_origin(endpoint):
    p=urlsplit(str(endpoint).strip())
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('请填写有效的 API 地址，不要包含账号或查询参数。')
    if p.scheme=='http' and p.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('远程 API 请使用 HTTPS；本地模型可使用 HTTP。')
    return p.scheme+'://'+p.netloc.lower()

def protect(data,decrypt=False):
    if sys.platform!='win32': raise ValueError('当前系统不支持 Windows 密钥加密；密钥仅在本次应用会话内使用。')
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    def blob(raw):
        storage=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw)
        return Blob(len(raw),ctypes.cast(storage,ctypes.POINTER(ctypes.c_ubyte))),storage
    source,keep_source=blob(data);entropy,keep_entropy=blob(b'DAMN.settings.v1');out=Blob()
    crypto=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        fn=crypto.CryptUnprotectData;fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(source),None,ctypes.byref(entropy),None,None,1,ctypes.byref(out))
    else:
        fn=crypto.CryptProtectData;fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(source),'DAMN API Key',ctypes.byref(entropy),None,None,1,ctypes.byref(out))
    if not ok: raise ValueError('无法使用当前 Windows 账户保存或读取密钥，请重新填写。')
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel.LocalFree(ctypes.cast(out.pbData,ctypes.c_void_p))

class SettingsStore:
    def __init__(self,directory):
        self.directory=Path(directory);self.file=self.directory/'settings.json';self.lock=threading.RLock();self.session_key='';self.session_cf_key=''
    def read(self):
        with self.lock:
            if not self.file.exists(): return {'onboarded':False,'endpoint':'','model':'','key':'','cfKey':''}
            try:
                data=json.loads(self.file.read_text(encoding='utf-8'));key=self.session_key
                if data.get('encryptedKey'):key=protect(base64.b64decode(data['encryptedKey']),True).decode('utf-8')
                cf_key=self.session_cf_key
                if data.get('encryptedCurseKey'):cf_key=protect(base64.b64decode(data['encryptedCurseKey']),True).decode('utf-8')
                return {**data,'key':key,'cfKey':cf_key}
            except (ValueError,OSError,UnicodeError):
                return {'onboarded':False,'endpoint':'','model':'','key':'','error':'设置或加密密钥无法读取，请重新配置。'}
    def public(self):
        data=self.read();local=urlsplit(data.get('endpoint','')).hostname in ('127.0.0.1','localhost','::1')
        return {'onboarded':data.get('onboarded',False),'endpoint':data.get('endpoint',''),'model':data.get('model',''),'hasKey':bool(data.get('key')),'configured':bool(data.get('endpoint') and data.get('model') and (local or data.get('key'))),'keyStorage':'Windows 用户加密' if sys.platform=='win32' else '仅本次会话','error':data.get('error',''),'revision':str(data.get('revision','')),'autoSearch':bool(data.get('autoSearch',True)),'hasCurseForgeKey':bool(data.get('cfKey')),'hideAiSetup':bool(data.get('hideAiSetup',False))}
    def credentials(self,draft=None):
        old=self.read()
        if draft is None:return {'endpoint':old.get('endpoint',''),'model':old.get('model',''),'apiKey':old.get('key','')}
        endpoint=str(draft.get('endpoint','')).strip().rstrip('/');model=str(draft.get('model','')).strip();key=str(draft.get('apiKey','')).strip()
        if not key and not draft.get('clearKey') and old.get('key') and old.get('endpoint'):
            if endpoint_origin(endpoint)==endpoint_origin(old['endpoint']):key=old['key']
        return {'endpoint':endpoint,'model':model,'apiKey':key}
    def save(self,draft):
        with self.lock:
            old=self.read()
            if draft.get('platformOnly') is True:
                cf_key=str(draft.get('curseForgeKey','')).strip() or ('' if draft.get('clearCurseKey') else old.get('cfKey',''))
                if len(cf_key)>4000:raise ValueError('CurseForge 密钥过长。')
                cf_encrypted=base64.b64encode(protect(cf_key.encode('utf-8'))).decode('ascii') if cf_key and sys.platform=='win32' else ''
                self.session_cf_key=cf_key if sys.platform!='win32' else ''
                data={k:v for k,v in old.items() if k not in ('key','cfKey','error')}
                data.update(revision=secrets.token_hex(12),onboarded=True,encryptedCurseKey=cf_encrypted)
            elif draft.get('defer'):
                data={k:v for k,v in old.items() if k not in ('key','cfKey','error')};data['onboarded']=True
                if 'autoSearch' in draft:data.update(autoSearch=bool(draft['autoSearch']),revision=secrets.token_hex(12))
            else:
                creds=self.credentials(draft);origin=endpoint_origin(creds['endpoint'])
                if not creds['model']:raise ValueError('请填写模型名称。')
                local=urlsplit(creds['endpoint']).hostname in ('127.0.0.1','localhost','::1')
                if len(creds['model'])>250 or len(creds['endpoint'])>2000 or len(creds['apiKey'])>4000:raise ValueError('配置内容过长。')
                encrypted=base64.b64encode(protect(creds['apiKey'].encode('utf-8'))).decode('ascii') if creds['apiKey'] and sys.platform=='win32' else ''
                self.session_key=creds['apiKey'] if sys.platform!='win32' else ''
                cf_key=str(draft.get('curseForgeKey','')).strip() or ('' if draft.get('clearCurseKey') else old.get('cfKey',''))
                if len(cf_key)>4000:raise ValueError('CurseForge 密钥过长。')
                cf_encrypted=base64.b64encode(protect(cf_key.encode('utf-8'))).decode('ascii') if cf_key and sys.platform=='win32' else ''
                self.session_cf_key=cf_key if sys.platform!='win32' else ''
                data={'revision':secrets.token_hex(12),'onboarded':True,'endpoint':creds['endpoint'],'model':creds['model'],'encryptedKey':encrypted,'origin':origin,'autoSearch':bool(draft.get('autoSearch',old.get('autoSearch',True))),'encryptedCurseKey':cf_encrypted,'hideAiSetup':bool(old.get('hideAiSetup',False))}
            if 'hideAiSetup' in draft:
                data['hideAiSetup']=bool(draft['hideAiSetup']);data['revision']=data.get('revision') or secrets.token_hex(12)
            self.directory.mkdir(parents=True,exist_ok=True)
            temp=self.file.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.file)
            return self.public()
