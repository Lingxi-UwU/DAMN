"""Local validated AI results; credentials and whole reports are never stored here."""
import hashlib,json,threading,time
from pathlib import Path

class AnnotationCache:
 VERSION='fast-evidence-v1'
 def __init__(self,file=None,ttl=7*24*3600,limit=3000):
  self.file=Path(file) if file else None;self.ttl=ttl;self.limit=limit;self.lock=threading.RLock();self.entries={}
  try:
   if self.file and self.file.stat().st_size<=24*1024*1024:
    data=json.loads(self.file.read_text(encoding='utf-8'))
    if isinstance(data,dict):self.entries={k:v for k,v in data.items() if isinstance(v,dict) and isinstance(v.get('savedAt'),(int,float)) and time.time()-v['savedAt']<ttl}
  except (OSError,ValueError,TypeError):pass
 def key(self,credentials,mod,info):
  # Endpoint and model isolate providers; changing a secret never puts it on disk.
  context={k:mod.get(k) for k in ('kind','name','file','version','category','sha1','manifest','dependenciesKnown','dependencies','components','description','loader')}
  evidence={k:info.get(k) for k in ('identity','sources','platformDependencies','platformCategory')}
  data=[self.VERSION,credentials.get('endpoint','').rstrip('/'),credentials.get('model',''),context,evidence]
  return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 def get(self,key):
  with self.lock:
   row=self.entries.get(key)
   if not row or time.time()-row['savedAt']>=self.ttl:return None
   # Return a copy: subject indexes and reconciliation are local to each batch.
   return json.loads(json.dumps(row.get('value')))
 def put(self,key,value,persist=True):
  with self.lock:
   self.entries[key]={'savedAt':time.time(),'value':value}
   if len(self.entries)>self.limit:
    self.entries=dict(sorted(self.entries.items(),key=lambda x:x[1]['savedAt'],reverse=True)[:self.limit])
   if persist:self.flush()
 def flush(self):
  with self.lock:
   if not self.file:return
   try:
    raw=json.dumps(self.entries,ensure_ascii=False,separators=(',',':'))
    while len(raw.encode('utf-8'))>24*1024*1024 and len(self.entries)>1:
     keep=max(1,int(len(self.entries)*.8));self.entries=dict(sorted(self.entries.items(),key=lambda x:x[1]['savedAt'],reverse=True)[:keep])
     raw=json.dumps(self.entries,ensure_ascii=False,separators=(',',':'))
    self.file.parent.mkdir(parents=True,exist_ok=True);temp=self.file.with_suffix('.tmp')
    temp.write_text(raw,encoding='utf-8');temp.replace(self.file)
   except OSError:pass
