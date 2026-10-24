from purpose import clean_purpose,local_description,annotation_purpose,SUMMARY_REVISION
"""Background lookup for every supplied mod; incremental results and bounded AI batches."""
import json,re,secrets,threading,concurrent.futures,time,queue,math
from ai_cache import AnnotationCache
from research import research,warm_modrinth,parse_ai_annotation,resolve_platform_dependencies
from taxonomy import classify_mod,TAXONOMY_VERSION
from ai_agent import reconcile,online_analysis,merge_materials

def web_category(info):
 identity=info.get('identity') or {}
 return classify_mod({'name':identity.get('title',''),'description':identity.get('description',''),'onlineResearch':[info]})['category']

def metadata_patch(mod,info):
 identity=info.get('identity') or {}
 # Search candidates never replace a manifest's file identity.
 matched=bool(identity.get('exact') or identity.get('projectIds',{}).get('CurseForge'))
 patch={'onlineResearch':[info],'platformInfo':identity,'resolutionStatus':'matched' if matched else 'candidate' if info.get('sources') else 'failed','webCategory':web_category(info) if web_category(info)!='其他 / 待识别' else None,'webCategoryEvidence':'平台介绍与分类标签的规则映射','enrichmentComplete':True}
 if matched and mod.get('kind')=='manifest':
  for source,target in [('title','name'),('description','description'),('version','version')]:
   if identity.get(source):patch[target]=str(identity[source])[:2000]
  if identity.get('loaders'):patch['loader']=' / '.join(identity['loaders'])+' · 平台资料'
 return patch

def compact_material(info,index):
 identity=info.get('identity') or {}
 return {'subjectIndex':index,'identity':{k:(str(v)[:400] if isinstance(v,str) else v) for k,v in identity.items() if k in ('title','description','version','exact','projectIds','match')},'sources':[{k:(str(v)[:240] if k=='excerpt' else v) for k,v in s.items() if k in ('site','url','title','excerpt','match')} for s in info.get('sources',[])[:3]],'platformDependencies':[{k:v for k,v in d.items() if k in ('target','kind','source','projectId','versionId')} for d in info.get('platformDependencies',[])[:8]],'notes':[str(n)[:200] for n in info.get('notes',[])[:1]]}
def parse_batch(answer,batch,materials):
 text=re.sub(r'^'+chr(96)+r'{3}(?:json)?\s*|\s*'+chr(96)+'{3}$','',answer.strip(),flags=re.I)
 try:data=json.loads(text)
 except (ValueError,TypeError):return {}
 rows=data.get('items',[]) if isinstance(data,dict) else []
 allowed={m['key']:i for i,m in enumerate(batch)};out={}
 for row in rows if isinstance(rows,list) else []:
  if not isinstance(row,dict) or row.get('key') not in allowed or row['key'] in out:continue
  i=allowed[row['key']]
  own=[r for r in materials if r.get('subjectIndex',0)==i]
  row={**row,'summary':row.get('summary') or row.get('purpose') or row.get('descriptionZh'),'relations':[],'category':None,'tags':[]}
  annotation=parse_ai_annotation(json.dumps(row,ensure_ascii=False),own)
  if annotation and (annotation.get('evidence') or local_description(batch[i]) and annotation_purpose(annotation)):out[row['key']]=annotation
 return out

class EnrichmentManager:
 def __init__(self,settings,chat,lookup=None,warm=None,cache=None,parallelism=2):
  self.settings=settings;self.chat=chat;self.lookup=lookup or research;self.warm=warm or warm_modrinth;self.lock=threading.RLock();self.job=None
  directory=getattr(settings,'directory',None)
  self.cache=cache if cache is not None else AnnotationCache(directory/'ai-cache.json' if directory is not None else None)
  self.parallelism=max(1,min(2,int(parallelism)))
 def start(self,mods,request_id='',scope=''):
  if not self.settings.public().get('autoSearch'):raise ValueError('请先在设置中开启自动联网搜索。')
  if not isinstance(mods,list) or not 1<=len(mods)<=3000:raise ValueError('一次可补全 1 至 3000 个模组。')
  keys=set();clean=[]
  fields=('key','kind','name','file','version','category','categoryTaxonomyVersion','tags','sha1','manifest','dependenciesKnown','components','dependencies','description','loader','onlineResearch','enrichmentComplete','resolutionStatus','aiAnnotation','aiReviewStatus','descriptionZh','translationAttempted','originalDescription','aiPurpose','purposeAttemptedRevision')
  for m in mods:
   if not isinstance(m,dict) or not isinstance(m.get('key'),str) or m['key'] in keys:raise ValueError('清单条目标识无效或重复。')
   keys.add(m['key']);clean.append({k:m[k] for k in fields if k in m})
  request_id=str(request_id)[:128];scope=str(scope)[:128]
  with self.lock:
   if request_id and self.job and self.job.get('requestId')==request_id:return self.snapshot(self.job['id'])
   if self.job:self.job['cancel'].set()
   now=time.time()
   job={'id':secrets.token_urlsafe(18),'requestId':request_id,'scope':scope,'cancel':threading.Event(),'status':'running','stage':'lookup','phase':'批量匹配平台文件','done':0,'total':len(clean),'matched':0,'candidates':0,'failed':0,'aiDone':0,'aiTotal':0,'aiBatch':0,'aiError':'','error':'','notes':[],'updates':[],'createdAt':now,'heartbeatAt':now,'updatedAt':now,'lookupComplete':False,'waitingForConfig':False,'configRevision':self.settings.public().get('revision',''),'pipelineRevision':3,'activeItems':[],'activeAI':[],'aiCacheHits':0,'aiProcessed':0,'aiBatchesCompleted':0,'aiStartedAt':None,'aiFinishedAt':None,'aiLastBatchSeconds':None,'aiBatchSeconds':0,'aiWorkers':0,'aiConcurrency':self.parallelism,'_aiActive':{}}
   self.job=job
  threading.Thread(target=self.run,args=(job,clean),daemon=True).start()
  return self.snapshot(job['id'])
 def emit(self,job,key,patch):
  with self.lock:
   if job['cancel'].is_set():return
   job['updates'].append({'key':key,'patch':patch});job['updatedAt']=time.time()
 def beat(self,job,**values):
  with self.lock:job.update(values);job['heartbeatAt']=time.time()
 def run(self,job,mods):
  ai_queue=queue.Queue();ai_thread=None;active={}
  try:
   pending=[m for m in mods if not m.get('enrichmentComplete')];cf=self.settings.read().get('cfKey','')
   def publish(mod,info,seed=False):
    if job['cancel'].is_set():return
    info={**info,'subject':str(mod.get('name','')),'subjectIndex':0}
    if seed and info.get('platformDependencies'):info=resolve_platform_dependencies(info,cf)
    patch=metadata_patch(mod,info);self.emit(job,mod['key'],patch)
    with self.lock:
     job['done']+=1;job[{'matched':'matched','candidate':'candidates','failed':'failed'}[patch['resolutionStatus']]]+=1
     job['updatedAt']=time.time()
    if info.get('sources') or local_description(mod):
     with self.lock:job['aiTotal']+=1
     if not needs_summary(info,mod):
      with self.lock:job['aiDone']+=1
     else:ai_queue.put((mod,info))
   for mod in mods:
    if mod.get('enrichmentComplete'):
     records=mod.get('onlineResearch') or []
     info=merge_materials([],records)[0] if records else {'sources':[],'notes':[],'sites':[]}
     publish(mod,info,True)
   ai_thread=threading.Thread(target=self.run_ai,args=(job,ai_queue),daemon=True);ai_thread.start()
   job['notes']=self.warm(pending,job['cancel'].is_set)
   if job['cancel'].is_set():return
   self.beat(job,phase='搜索三站并补全清单')
   def lookup_one(mod):
    if job['cancel'].is_set():return None
    with self.lock:active[mod['key']]=str(mod.get('name',''));job['activeItems']=list(active.values())
    try:return self.lookup(mod,self.settings.read().get('cfKey',''))
    except Exception:return {'sources':[],'notes':['该条资料读取未完成，可重试。'],'sites':[]}
    finally:
     with self.lock:active.pop(mod['key'],None);job['activeItems']=list(active.values())
   pool=concurrent.futures.ThreadPoolExecutor(max_workers=3)
   futures={pool.submit(lookup_one,m):m for m in pending}
   try:
    while futures and not job['cancel'].is_set():
     ready,_=concurrent.futures.wait(futures,timeout=.5,return_when=concurrent.futures.FIRST_COMPLETED);self.beat(job)
     for future in ready:
      mod=futures.pop(future);info=future.result()
      if info is not None:publish(mod,info)
   finally:
    pool.shutdown(wait=False,cancel_futures=True)
   self.beat(job,lookupComplete=True,stage='ai',activeItems=[])
   ai_queue.put(None)
   while ai_thread.is_alive() and not job['cancel'].is_set():
    ai_thread.join(.5);self.beat(job)
   if not job['cancel'].is_set():
    self.beat(job,status='complete',phase='平台资料已完成 · AI 待恢复' if job['aiError'] else '补全完成',stage='done')
  except Exception:
   self.beat(job,status='failed',phase='补全未完成',error='后台补全未完成；已取得的条目已保留，可继续未完成项。')
  finally:
   ai_queue.put(None)
   if job['cancel'].is_set():self.beat(job,status='cancelled',stage='paused',phase='已暂停',activeItems=[],activeAI=[])
 def run_ai(self,job,tasks):
  # Ramp up after the first successful request, so bad credentials fail only once.
  pool=concurrent.futures.ThreadPoolExecutor(max_workers=self.parallelism);futures=set();ended=False
  try:
   while not job['cancel'].is_set():
    for future in list(futures):
     if future.done():
      futures.remove(future)
      try:future.result()
      except Exception:
       if not job['aiError']:self.beat(job,aiError='AI 整理未完成，已取得的结果已保留，可继续未完成项。')
    if job['aiError'] or ended and not futures:break
    capacity=self.parallelism if job['aiBatchesCompleted'] else 1
    if ended or len(futures)>=capacity:
     if futures:concurrent.futures.wait(futures,timeout=.1,return_when=concurrent.futures.FIRST_COMPLETED)
     continue
    try:first=tasks.get(timeout=.1)
    except queue.Empty:continue
    if first is None:ended=True;continue
    batch=[first];until=time.monotonic()+1
    while len(batch)<10 and not job['cancel'].is_set():
     try:item=tasks.get(timeout=max(.001,until-time.monotonic()))
     except queue.Empty:break
     if item is None:ended=True;break
     batch.append(item)
    while not job['cancel'].is_set() and not self.settings.public().get('configured'):
     self.beat(job,waitingForConfig=True,phase='检索中 · 等待 API 配置' if not job['lookupComplete'] else '平台检索完成 · 等待 API 配置')
     job['cancel'].wait(.5)
    if job['cancel'].is_set() or job['aiError'] or not self.settings.public().get('autoSearch'):break
    futures.add(pool.submit(self.process_batch,job,batch))
   while futures and not job['cancel'].is_set():
    ready,_=concurrent.futures.wait(futures,timeout=.2,return_when=concurrent.futures.FIRST_COMPLETED)
    for future in ready:
     futures.remove(future)
     try:future.result()
     except Exception:pass
  finally:
   pool.shutdown(wait=False,cancel_futures=True)
   self.beat(job,aiFinishedAt=time.time())
 def annotation_patch(self,mod,materials,annotation,search,cached=False):
  own=[{**r,'subjectIndex':0} for r in materials]
  patch={'onlineResearch':own,'aiSearch':{**(search or {}),'cached':cached},'aiReviewStatus':'done' if annotation else 'unstructured','translationAttempted':True,'purposeAttemptedRevision':SUMMARY_REVISION}
  if annotation:
   annotation={**annotation,'relations':[],'category':None,'tags':[]}
   patch.update(aiAnnotation=annotation,aiCategory=annotation.get('category'),aiPurpose=annotation_purpose(annotation),aiPurposeBasis='web' if any(r.get('sources') for r in own) else 'local',reconciliation=reconcile([mod],own,annotation))
   if annotation.get('descriptionZh'):patch['descriptionZh']=annotation['descriptionZh']
  else:patch['aiReviewNote']='AI 未返回该条可验证的结构化结果；平台资料已保留，可单独分析。'
  return patch
 def process_batch(self,job,batch):
  started=time.monotonic();batch_id=None;credentials=self.settings.credentials();revision=self.settings.public().get('revision','')
  try:
   fresh=[]
   for mod,info in batch:
    cache_key=self.cache.key(credentials,mod,info);hit=self.cache.get(cache_key)
    if hit and hit.get('annotation') and annotation_purpose(hit['annotation']) and (not needs_translation(info,mod) or hit['annotation'].get('descriptionZh')):
     self.emit(job,mod['key'],self.annotation_patch(mod,hit['materials'],hit['annotation'],hit.get('aiSearch'),True))
     with self.lock:job['aiCacheHits']+=1;job['aiDone']+=1
    else:fresh.append((mod,info,cache_key))
   if not fresh or job['cancel'].is_set():return
   batch=[(m,info) for m,info,_ in fresh]
   with self.lock:
    job['aiBatch']+=1;batch_id=job['aiBatch'];job['_aiActive'][batch_id]={'names':[str(m.get('name','')) for m,_ in batch],'started':time.time()}
    if job['aiStartedAt'] is None:job['aiStartedAt']=time.time()
    self.refresh_ai_active(job)
   self.beat(job,waitingForConfig=False,phase='平台检索与中文用途整理' if not job['lookupComplete'] else '中文用途总结与翻译')
   subjects=[m for m,_ in batch];materials=[compact_material(info,i) for i,(_,info) in enumerate(batch)]
   context={'mods':[{'key':m['key'],'name':m.get('name'),'file':m.get('file'),'description':str(info.get('identity',{}).get('description') or m.get('description',''))[:1200]} for m,info in batch],'sources':[{'subjectIndex':r['subjectIndex'],'sources':r['sources']} for r in materials]}
   question='逐项提供简体中文用途短句与简介翻译。purpose 用一句15到45字、最多80字直说新增功能或体验，禁止网页描述为等引述开头、版本号、加载器要求、移植历史和安装说明；专名可保留英文。descriptionZh 忠实翻译原简介。资料不足不得编造。只返回 JSON：{"items":[{"key":"原样 key","descriptionZh":"原简介中文翻译","purpose":"一句简短中文功能说明","summary":"简短用途说明","evidence":["该条目给出的来源 URL"]}]}。只有文件简介时 evidence 返回空数组。不要跨条目借用资料。分类和前置关系由应用读取平台及文件声明，本次不要判定分类、依赖或调用检索工具。'
   payload={**credentials,'question':question,'context':json.dumps(context,ensure_ascii=False),'summaryOnly':True}
   result=self.chat(payload);merged=materials
   result['aiSearch']={'mode':'summary','message':'AI 仅生成中文用途与翻译；分类和前置由应用直接读取平台及文件声明。','calls':[]}
   annotations=parse_batch(result['answer'],subjects,merged)
   for index,(mod,info,cache_key) in enumerate(fresh):
    own=merge_materials([{**info,'subjectIndex':index}],[r for r in merged if r.get('subjectIndex',0)==index]);annotation=annotations.get(mod['key'])
    patch=self.annotation_patch(mod,own,annotation,result.get('aiSearch'));self.emit(job,mod['key'],patch)
    if annotation and (not needs_translation(info,mod) or annotation.get('descriptionZh')) and not job['cancel'].is_set():
     self.cache.put(cache_key,{'annotation':annotation,'materials':[{**r,'subjectIndex':0} for r in own],'aiSearch':result.get('aiSearch')},persist=False)
   self.cache.flush()
   duration=round(time.monotonic()-started,2)
   with self.lock:
    job['aiDone']+=len(batch);job['aiProcessed']+=len(batch);job['aiBatchesCompleted']+=1;job['aiBatchSeconds']+=duration
    self.beat(job,aiLastBatchSeconds=duration,configRevision=revision)
  except ValueError as e:
   text=str(e)[:300]
   if getattr(e,'status',None)==429:text='服务商限流，已暂停新批次；已完成的结果已保留，稍后可继续。'
   self.beat(job,aiError=text,configRevision=revision)
   raise
  except Exception:
   self.beat(job,aiError='AI 整理未完成，平台资料和已完成结果已保留。');raise
  finally:
   with self.lock:
    if batch_id is not None:job['_aiActive'].pop(batch_id,None)
    self.refresh_ai_active(job)
 def refresh_ai_active(self,job):
  job['activeAI']=[name for task in job['_aiActive'].values() for name in task['names']]
  job['aiWorkers']=len(job['_aiActive'])
 def snapshot(self,ident,after=0):
  with self.lock:
   job=self.job
   if not job or ident!=job['id']:raise ValueError('补全任务已失效，请继续未完成项。')
   after=min(len(job['updates']),max(0,int(after)));updates=job['updates'][after:after+100];cursor=after+len(updates)
   fields=('id','requestId','scope','status','stage','phase','done','total','matched','candidates','failed','aiDone','aiTotal','aiBatch','aiError','error','notes','createdAt','heartbeatAt','updatedAt','lookupComplete','waitingForConfig','configRevision','activeItems','activeAI','pipelineRevision','aiCacheHits','aiProcessed','aiBatchesCompleted','aiLastBatchSeconds','aiWorkers','aiConcurrency')
   now=time.time();elapsed=max(0,(job['aiFinishedAt'] or now)-(job['aiStartedAt'] or now))
   active=max([now-t['started'] for t in job['_aiActive'].values()] or [0]);remaining=max(0,job['aiTotal']-job['aiDone'])
   eta=round(remaining*elapsed/job['aiProcessed']) if job['lookupComplete'] and job['aiBatchesCompleted']>=2 and job['aiProcessed'] and not job['aiError'] and job['status']=='running' else None
   if eta is not None and job['aiBatchesCompleted']:
    average=job['aiBatchSeconds']/job['aiBatchesCompleted']
    # Account for an in-flight final batch even when whole-job throughput is high.
    eta=max(eta,math.ceil(max([average-(now-t['started']) for t in job['_aiActive'].values()] or [0])))
   return {k:job[k] for k in fields}|{'aiElapsedSeconds':round(elapsed),'aiCurrentSeconds':round(active),'aiEtaSeconds':eta,'updates':updates,'cursor':cursor,'hasMore':cursor<len(job['updates']),'serverTime':time.time()}
 def current(self,scope='',after=0):
  with self.lock:
   if not self.job or (scope and scope!=self.job.get('scope')):return None
   return self.snapshot(self.job['id'],after)
 def cancel(self,ident,after=0):
  with self.lock:
   if self.job and self.job['id']==ident:
    self.job['cancel'].set();self.beat(self.job,status='cancelled',stage='paused',phase='已暂停')
  return self.snapshot(ident,after)
def needs_translation(info,mod=None):
 mod=mod or {}
 text=str((info.get('identity') or {}).get('description') or mod.get('originalDescription') or mod.get('description') or '')
 return bool(re.search(r'[a-zA-Z]{3}',text)) and not bool(re.search(r'[\u4e00-\u9fff]',text))


def needs_summary(info,mod):
 annotation=mod.get('aiAnnotation') or {}
 values=[mod.get('aiPurpose'),annotation.get('purpose'),annotation.get('summary'),mod.get('descriptionZh'),(info.get('identity') or {}).get('description'),mod.get('description')]
 has_purpose=any(clean_purpose(v) for v in values)
 return not has_purpose or needs_translation(info,mod) and not mod.get('descriptionZh')
