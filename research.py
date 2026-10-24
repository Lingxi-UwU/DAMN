from purpose import clean_purpose
from app_info import VERSION
"""Opt-in metadata lookup; only the three requested sites and Modrinth's API."""
import concurrent.futures,html,json,re,threading,time,contextvars,math
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import quote,urlencode,urljoin,urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from taxonomy import classify,normalize_category,normalize_tags,CATEGORIES,TAXONOMY_VERSION
ALLOWED={'api.modrinth.com','modrinth.com','www.modrinth.com','curseforge.com','www.curseforge.com','mcmod.cn','www.mcmod.cn','search.mcmod.cn','api.curseforge.com'}
CACHE={};LOCK=threading.Lock();COOLDOWN={};FETCH_DEADLINE=contextvars.ContextVar('damn_lookup_deadline',default=None)
DEPENDENCY_LOCK=threading.Lock()
RATE_LOCK=threading.Lock();RATE_NEXT={}
USER_AGENT='DAMN/'+VERSION+' (local modpack analyzer and dependency helper)'
def request_slot(host,deadline):
 interval=.5 if host=='api.modrinth.com' else .6 if host=='api.curseforge.com' else 1.0
 with RATE_LOCK:
  now=time.monotonic();slot=max(now,RATE_NEXT.get(host,now))
  if slot>=deadline:raise ValueError('站点请求正在排队，本条已暂缓，请稍后重试。')
  RATE_NEXT[host]=slot+interval
 if slot>now:time.sleep(slot-now)
def retry_seconds(headers,default=120):
 value=headers.get('Retry-After','') if headers else ''
 try:seconds=float(value)
 except (ValueError,TypeError):
  try:seconds=parsedate_to_datetime(value).timestamp()-time.time()
  except (ValueError,TypeError,OverflowError,AttributeError):return default
 return max(1,seconds) if math.isfinite(seconds) else default
def rate_headers(host,headers):
 try:
  if float(headers.get('X-Ratelimit-Remaining','-1'))!=0:return
  seconds=float(headers.get('X-Ratelimit-Reset','0'))
  if seconds<=0 or not math.isfinite(seconds):return
 except (ValueError,TypeError):return
 with LOCK:COOLDOWN[host]=(time.time()+seconds,'已达到站点请求频率，等待其额度恢复')
def permitted(url):
 try:
  p=urlsplit(str(url))
  if p.scheme!='https' or p.port not in (None,443) or p.username or p.password:return False
 except ValueError:return False
 if p.hostname=='mod.mcimirror.top':
  return not p.fragment and bool(re.fullmatch(r'/(?:modrinth/v2/(?:search|project/[A-Za-z0-9_-]{1,100})|curseforge/v1/mods/(?:search|[0-9]{1,15}))/?',p.path))
 return p.hostname in ALLOWED
class SafeRedirect(HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if any(k.lower()=='x-api-key' for k in req.headers) and urlsplit(newurl).hostname!=urlsplit(req.full_url).hostname:raise ValueError('已阻止跨站点转发密钥。')
  if not permitted(newurl):raise ValueError('站点跳转超出允许的来源，已停止访问。')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def read_bounded(response,limit,deadline):
 chunks=[];size=0
 while True:
  if time.monotonic()>deadline:raise ValueError('站点读取超过时限，已跳过，可稍后重试。')
  chunk=response.read1(min(65536,limit+1-size)) if hasattr(response,'read1') else response.read(min(65536,limit+1-size))
  if not chunk:break
  chunks.append(chunk);size+=len(chunk)
  if size>limit:raise ValueError('页面内容过大，已停止读取。')
 return b''.join(chunks)

def fetch(url,api_key=None,payload=None):
 if not permitted(url):raise ValueError('只允许访问已支持的资料站点与项目查询接口。')
 if urlsplit(url).hostname=='mod.mcimirror.top' and payload is not None:raise ValueError('镜像入口只支持公开项目查询。')
 if api_key and urlsplit(url).hostname!='api.curseforge.com':raise ValueError('CurseForge 密钥只能发送给其官方 API。')
 cache_key=url if payload is None else url+'#'+json.dumps(payload,sort_keys=True)
 host=urlsplit(url).hostname
 with LOCK:
  cached=CACHE.get(cache_key)
  if cached and time.time()-cached[0]<3600:return cached[1]
  cooldown=COOLDOWN.get(host)
  if cooldown and cooldown[0]>time.time():raise ValueError(cooldown[1]+'（站点暂缓重试）')
 deadline=FETCH_DEADLINE.get() or time.monotonic()+15
 if deadline<=time.monotonic():raise ValueError('该条检索已超时，已跳过，可稍后重试。')
 request_slot(host,deadline)
 with LOCK:
  cached=CACHE.get(cache_key)
  if cached and time.time()-cached[0]<3600:return cached[1]
  cooldown=COOLDOWN.get(host)
  if cooldown and cooldown[0]>time.time():raise ValueError(cooldown[1]+'（站点暂缓重试）')
 if api_key and urlsplit(url).hostname!='api.curseforge.com':raise ValueError('CurseForge 密钥只能发送给其官方 API。')
 req=Request(url,data=json.dumps(payload).encode('utf-8') if payload is not None else None,headers={'User-Agent':USER_AGENT,'Accept':'application/json,text/html;q=0.9','Accept-Encoding':'identity'})
 if api_key:req.add_header('x-api-key',api_key)
 if payload is not None:req.add_header('Content-Type','application/json')
 if deadline<=time.monotonic():raise ValueError('该条检索已超时，已跳过，可稍后重试。')
 try:
  with build_opener(SafeRedirect).open(req,timeout=max(.2,min(9,deadline-time.monotonic()))) as response:
   rate_headers(host,response.headers)
   typ=response.headers.get('Content-Type','');raw=read_bounded(response,2_000_000,deadline);encoding=response.headers.get_content_charset() or 'utf-8'
  if len(raw)>2_000_000:raise ValueError('页面内容过大，已停止读取。')
  if not any(x in typ for x in ('json','html','text/')):raise ValueError('站点没有返回可分析的文本资料。')
  text=raw.decode(encoding,errors='replace')
  if re.search(r'<title>\s*(Just a moment|Attention Required)|cf-chl-|captcha-container',text,re.I):raise ValueError('站点要求人工验证，未读取受保护内容。')
  with LOCK:CACHE[cache_key]=(time.time(),text)
  return text
 except HTTPError as e:
  message='站点返回 HTTP '+str(e.code)+'，资料暂不可用。'
  if e.code in (401,403,429,503):
   with LOCK:COOLDOWN[host]=(time.time()+retry_seconds(e.headers),message)
  raise ValueError(message) from None
 except (URLError,TimeoutError,OSError):raise ValueError('站点连接失败或超时。') from None
class Page(HTMLParser):
 def __init__(self,text):
  super().__init__(convert_charrefs=True);self.skip=0;self.text=[];self.links=[];self.current=None;self.title='';self.in_title=False;self.description='';self.feed(text)
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag in ('script','style','noscript'):self.skip+=1
  if tag=='title':self.in_title=True
  if tag=='meta' and attrs.get('name',attrs.get('property','')).lower() in ('description','og:description'):self.description=attrs.get('content','')
  if tag=='a' and not self.skip:self.current=[attrs.get('href',''),'']
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript') and self.skip:self.skip-=1
  if tag=='title':self.in_title=False
  if tag=='a' and self.current:self.links.append(self.current);self.current=None
 def handle_data(self,data):
  if self.in_title:self.title+=data
  if self.skip:return
  value=data.strip()
  if value:self.text.append(value)
  if self.current:self.current[1]+=' '+value
 def excerpt(self):return re.sub(r'\s+',' ',self.description or ' '.join(self.text))[:1000]
def normalize(text):return re.sub(r'[^a-z0-9\u4e00-\u9fff]','',str(text).lower())
def query_for(mod):
 name=str(mod.get('name') or mod.get('file') or '')
 name=name.rsplit('/',1)[-1];name=re.sub(r'\.jar(?:\.disabled)?$','',name,flags=re.I)
 name=re.sub(r'[-_](?:\d+\.\d+|(?:neo)?forge|fabric|quilt).*','',name,flags=re.I)
 name=re.sub(r'\s*\([^)]*\)|\s*（[^）]*）','',name).strip()
 if name.startswith('CurseForge 项目'):return ''
 return name[:120]
def source(site,url,title,excerpt,match='关键词候选',**extra):
 return {'site':site,'url':url,'title':title,'excerpt':excerpt,'match':match,**extra}
def project_taxonomy(site,project,url,matched=True):
 categories=project.get('categories') or []
 return {'site':site,'projectId':str(project.get('id') or project.get('slug') or ''),'url':url,'categories':categories,'categoryIds':[c['id'] for c in categories if isinstance(c,dict) and c.get('id') is not None],'primaryCategoryId':project.get('primaryCategoryId'),'matched':matched,'retrievedAt':datetime.now(timezone.utc).isoformat()}
def modrinth(mod,query):
 base='https://api.modrinth.com/v2';manifest=mod.get('manifest') or {};version=None;project=None;match='关键词候选';sources=[]
 hashes=manifest.get('hashes',{})
 if not hashes and mod.get('sha1'):hashes={'sha1':mod['sha1']}
 for algo in ('sha512','sha1'):
  value=hashes.get(algo,'')
  if re.fullmatch(r'[a-fA-F0-9]{'+('128' if algo=='sha512' else '40')+'}',str(value)):
   try:version=json.loads(fetch(base+'/version_file/'+value+'?algorithm='+algo));match='清单哈希对应的平台版本';break
   except ValueError:pass
 if version is None:
  for url in manifest.get('downloads',[]):
   p=urlsplit(url);m=re.match(r'/data/([a-zA-Z0-9]{8})/versions/([a-zA-Z0-9]{8})/',p.path)
   if p.hostname=='cdn.modrinth.com' and m:
    try:version=json.loads(fetch(base+'/version/'+m[2]));match='清单下载地址对应的平台版本';break
    except ValueError:pass
 known=(mod.get('platformInfo') or {}).get('projectIds',{}).get('Modrinth')
 if version:
  project_id=version.get('project_id');project=json.loads(fetch(base+'/project/'+quote(str(project_id),safe='')))
 elif known and re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',str(known)):
  project=json.loads(fetch(base+'/project/'+quote(str(known),safe='')));match='已有平台项目 ID 对应的项目'
 else:
  if not query:return {'sources':[],'note':'没有可用于 Modrinth 精确匹配的哈希、下载地址或名称。'}
  results=json.loads(fetch(base+'/search?'+urlencode({'query':query,'limit':3,'facets':json.dumps([['project_type:mod']])}))).get('hits',[])
  if not results:return {'sources':[],'note':'Modrinth 未找到候选项目。'}
  hit=max(results,key=lambda x:(normalize(query)==normalize(x.get('title','')),normalize(query) in normalize(x.get('title',''))))
  project=json.loads(fetch(base+'/project/'+quote(str(hit['project_id']),safe='')))
  if normalize(query)==normalize(project.get('title','')):match='名称相符（未核对版本）'
 project_id=project.get('id') or project.get('slug');project_url='https://modrinth.com/mod/'+quote(str(project.get('slug') or project_id),safe='')
 taxonomy=project_taxonomy('Modrinth',project,project_url,bool(version or known or match=='名称相符（未核对版本）'))
 sources.append(source('Modrinth',project_url,project.get('title',query),str(project.get('description',''))[:800],match,categories=project.get('categories',[]),matched=taxonomy['matched']))
 dependencies=[]
 if version:
  sources.append(source('Modrinth',project_url+'/version/'+quote(str(version.get('id','')),safe=''),version.get('name','平台版本'),'版本 '+str(version.get('version_number',''))+'；游戏版本 '+', '.join(version.get('game_versions',[])),match,versionNumber=version.get('version_number','')))
  for d in version.get('dependencies',[])[:30]:
   pid=d.get('project_id');target='Modrinth 项目 '+str(pid) if pid else str(d.get('file_name') or d.get('version_id') or '未命名依赖')
   dependencies.append({'target':target,'projectId':pid,'versionId':d.get('version_id'),'kind':d.get('dependency_type','related'),'source':sources[-1]['url'],'provenance':'平台版本声明（未读取本地 JAR）'})
 return {'identity':{'title':project.get('title',query),'description':str(project.get('description',''))[:1500],'version':version.get('version_number') if version else None,'loaders':version.get('loaders',[]) if version else [],'projectIds':{'Modrinth':project_id},'versionId':version.get('id') if version else None,'exact':bool(version),'match':match},'sources':sources,'title':project.get('title',query),'platformCategory':project.get('categories',[]),'platformTaxonomy':[taxonomy],'projectId':project_id,'dependencies':dependencies,'match':match}
def site_search(site,query):
 if not query:return {'sources':[],'note':site+'：缺少可搜索的模组名称；项目 ID 本身不能当成名称。'}
 if site=='CurseForge':url='https://www.curseforge.com/minecraft/search?'+urlencode({'search':query,'class':'mc-mods','pageSize':5})
 else:url='https://search.mcmod.cn/s?'+urlencode({'key':query})
 page=Page(fetch(url));candidates=[]
 for href,title in page.links:
  target=urljoin(url,href);p=urlsplit(target)
  valid=(p.hostname in ('curseforge.com','www.curseforge.com') and re.fullmatch(r'/minecraft/mc-mods/[^/]+/?',p.path)) if site=='CurseForge' else (p.hostname in ('mcmod.cn','www.mcmod.cn') and re.fullmatch(r'/class/\d+\.html',p.path))
  if valid and title.strip() and target not in [x[0] for x in candidates]:candidates.append((target,title.strip()))
 if not candidates:return {'sources':[],'searchURL':url,'note':site+' 的搜索页没有返回可用项目条目，可能需要人工查看。'}
 candidates.sort(key=lambda x:(normalize(query)==normalize(x[1]),normalize(query) in normalize(x[1])),reverse=True)
 target,title=candidates[0];detail=Page(fetch(target))
 excerpt=detail.excerpt()
 if site=='MC 百科':
  text=' '.join(detail.text)
  for marker in ('Mod介绍','模组介绍'):
   if marker in text:excerpt=text.split(marker,1)[-1][:1000];break
 return {'sources':[source(site,target,detail.title.strip() or title,excerpt,'搜索候选，需与版本/作者核对')],'searchURL':url}
def curseforge_api(mod,key):
 manifest=mod.get('manifest') or {};pid=manifest.get('projectID');fid=manifest.get('fileID')
 if not str(pid).isdigit() or not key:return None
 base='https://api.curseforge.com/v1/mods/'+str(pid)
 project=json.loads(fetch(base,key))['data'];url=project.get('links',{}).get('websiteUrl','')
 if not permitted(url):raise ValueError('CurseForge 项目未提供有效的官方页面链接。')
 version=None
 taxonomy=project_taxonomy('CurseForge',project,url)
 sources=[source('CurseForge',url,project.get('name','项目 '+str(pid)),str(project.get('summary',''))[:800],'清单项目 ID 对应的官方项目',categories=taxonomy['categories'],categoryIds=taxonomy['categoryIds'],primaryCategoryId=taxonomy['primaryCategoryId'],matched=True)];deps=[]
 if str(fid).isdigit():
  version=json.loads(fetch(base+'/files/'+str(fid),key))['data'];version_url=url.rstrip('/')+'/files/'+str(fid)
  sources.append(source('CurseForge',version_url,version.get('displayName','文件 '+str(fid)),'文件名 '+str(version.get('fileName',''))+'；游戏版本 '+', '.join(version.get('gameVersions',[])),'清单项目/文件 ID 对应的官方版本',fileName=version.get('fileName','')))
  for d in version.get('dependencies',[])[:30]:
   deps.append({'target':'CurseForge 项目 '+str(d.get('modId')),'projectId':d.get('modId'),'kind':{1:'embedded',2:'optional',3:'required',4:'tool',5:'incompatible',6:'include'}.get(d.get('relationType'),'related'),'source':version_url,'provenance':'平台版本声明（未读取本地 JAR）'})
 return {'identity':{'title':project.get('name',''),'description':str(project.get('summary',''))[:1500],'version':None,'fileName':version.get('fileName') if version else None,'projectIds':{'CurseForge':pid},'exact':bool(version),'match':'清单项目 / 文件 ID 匹配' if version else '清单项目 ID 匹配'},'sources':sources,'title':project.get('name',''),'platformCategory':[c.get('name','') for c in project.get('categories',[])],'platformTaxonomy':[taxonomy],'dependencies':deps,'projectId':pid}

def _research(mod,curse_key=''):
 query=query_for(mod);result={'query':query,'sources':[],'platformDependencies':[],'platformTaxonomy':[],'notes':[],'sites':[],'retrievedAt':datetime.now(timezone.utc).isoformat()}
 if curse_key and (mod.get('manifest') or {}).get('projectID'):
  try:
   cf=curseforge_api(mod,curse_key)
   if cf:
    result['sources'].extend(cf['sources']);result['platformDependencies'].extend(cf['dependencies']);result['platformTaxonomy'].extend(cf.get('platformTaxonomy',[]));result['sites'].append({'site':'CurseForge','ok':True});result['resolvedTitle']=cf['title'];query=cf['title'] or query;result['identity']=cf.get('identity')
  except (ValueError,KeyError,TypeError,AttributeError) as e:result['notes'].append('CurseForge API：'+str(e))
 try:
  data=modrinth(mod,query);result['sources'].extend(data.get('sources',[]));result['platformDependencies'].extend(data.get('dependencies',[]));result['platformTaxonomy'].extend(data.get('platformTaxonomy',[]));result['platformCategory']=data.get('platformCategory',[]);result['projectId']=data.get('projectId');result['resolvedTitle']=data.get('title');result['sites'].append({'site':'Modrinth','ok':bool(data.get('sources'))})
  if data.get('note'):result['notes'].append(data['note'])
  query=data.get('title') or query
  if data.get('identity') and (not result.get('identity') or data['identity'].get('exact')):result['identity']=data['identity']
 except (ValueError,KeyError,TypeError,AttributeError) as e:result['sites'].append({'site':'Modrinth','ok':False});result['notes'].append('Modrinth：'+str(e))
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  futures={pool.submit(contextvars.copy_context().run,site_search,site,query):site for site in ('CurseForge','MC 百科') if not any(s['site']==site and s['ok'] for s in result['sites'])}
  for future,site in futures.items():
   try:
    data=future.result();result['sources'].extend(data.get('sources',[]));result['sites'].append({'site':site,'ok':bool(data.get('sources')),'searchURL':data.get('searchURL')})
    if data.get('note'):result['notes'].append(data['note'])
   except (ValueError,KeyError,TypeError,AttributeError) as e:result['sites'].append({'site':site,'ok':False});result['notes'].append(site+'：'+str(e))
 result['notes'].append('网页描述、关键词候选和平台版本关系不等于本地 JAR 中已经核实的依赖声明。')
 return resolve_platform_dependencies(result,curse_key)

def research(mod,curse_key=''):
 token=FETCH_DEADLINE.set(time.monotonic()+40)
 try:return _research(mod,curse_key)
 finally:FETCH_DEADLINE.reset(token)

def parse_ai_annotation(answer,research_results):
 text=answer.strip();text=re.sub(r'^'+chr(96)+r'{3}(?:json)?\s*|\s*'+chr(96)+'{3}$','',text,flags=re.I)
 try:data=json.loads(text)
 except (ValueError,TypeError):return None
 if not isinstance(data,dict):return None
 valid={s['url'] for r in research_results for s in r.get('sources',[])}
 category=normalize_category(data.get('category')) if isinstance(data.get('category'),str) else None
 evidence=[x for x in data.get('evidence',[]) if isinstance(x,str) and x in valid] if isinstance(data.get('evidence',[]),list) else []
 if not evidence:category=None
 relations=[]
 for rel in data.get('relations',[])[:20] if isinstance(data.get('relations',[]),list) else []:
  if isinstance(rel,dict) and rel.get('source') in valid and rel.get('kind') in ('required','optional','incompatible','related','used_by'):
   relations.append({'target':str(rel.get('target',''))[:150],'kind':rel['kind'],'source':rel['source'],'provenance':'AI 引用平台 / 网页，需核对版本','version':str(rel.get('version','未知'))[:120]})
 summary=data.get('summary')
 if not isinstance(summary,str) or not summary.strip():return None
 translated=str(data.get('descriptionZh') or '').strip()[:4000]
 if not re.search(r'[\u4e00-\u9fff]',translated):translated=''
 return {'descriptionZh':translated,'summary':summary,'purpose':clean_purpose(data.get('purpose')) or clean_purpose(summary),'category':category,'taxonomyVersion':TAXONOMY_VERSION,'tags':normalize_tags(data.get('tags')) if category else [],'evidence':evidence,'relations':relations,'uncertainties':data.get('uncertainties',[]) if isinstance(data.get('uncertainties',[]),list) else []}

def warm_modrinth(mods,cancel=lambda:False):
 """Populate normal lookup caches using public bulk endpoints, preserving exact identities."""
 base='https://api.modrinth.com/v2';notes=[];versions={};hashes={'sha512':set(),'sha1':set()};ids=set()
 for mod in mods:
  manifest=mod.get('manifest') or {}
  for algo,length in [('sha512',128),('sha1',40)]:
   value=(manifest.get('hashes') or {}).get(algo) or (mod.get('sha1') if algo=='sha1' else None)
   if re.fullmatch(r'[a-fA-F0-9]{'+str(length)+'}',str(value or '')):hashes[algo].add(value)
  for url in manifest.get('downloads',[]):
   p=urlsplit(url);m=re.match(r'/data/([a-zA-Z0-9]{8})/versions/([a-zA-Z0-9]{8})/',p.path)
   if p.hostname=='cdn.modrinth.com' and m:ids.add(m[2])
 def remember(url,data):
  with LOCK:CACHE[url]=(time.time(),json.dumps(data,ensure_ascii=False))
 for algo,values in hashes.items():
  values=sorted(values)
  for i in range(0,len(values),80):
   if cancel():return notes
   try:
    data=json.loads(fetch(base+'/version_files',payload={'hashes':values[i:i+80],'algorithm':algo}))
    for value,version in data.items():
     if isinstance(version,dict) and version.get('id'):
      remember(base+'/version_file/'+value+'?algorithm='+algo,version);versions[version['id']]=version
   except (ValueError,KeyError,TypeError) as e:notes.append('批量哈希匹配：'+str(e))
 ids=sorted(ids-set(versions))
 for i in range(0,len(ids),40):
  if cancel():return notes
  try:
   for version in json.loads(fetch(base+'/versions?'+urlencode({'ids':json.dumps(ids[i:i+40])}))):
    if isinstance(version,dict) and version.get('id'):versions[version['id']]=version
  except (ValueError,KeyError,TypeError) as e:notes.append('批量版本匹配：'+str(e))
 for vid,version in versions.items():remember(base+'/version/'+vid,version)
 projects=sorted({str(v['project_id']) for v in versions.values() if v.get('project_id')}|{str(d['project_id']) for v in versions.values() for d in v.get('dependencies',[]) if d.get('project_id')})
 for i in range(0,len(projects),20):
  if cancel():return notes
  try:
   for project in json.loads(fetch(base+'/projects?'+urlencode({'ids':json.dumps(projects[i:i+20])}))):
    if isinstance(project,dict) and project.get('id'):remember(base+'/project/'+project['id'],project)
  except (ValueError,KeyError,TypeError) as e:notes.append('批量项目匹配：'+str(e))
 return list(dict.fromkeys(notes))


def resolve_platform_dependencies(info,curse_key=''):
 """Resolve platform-declared project/version IDs in batches; never ask a model."""
 result={**info,'platformDependencies':[dict(d) for d in info.get('platformDependencies') or []],'notes':list(info.get('notes') or [])}
 rows=result['platformDependencies']
 if not rows:return result
 if not DEPENDENCY_LOCK.acquire(timeout=6):
  result['notes'].append('前置名称补全暂忙，保留平台项目 ID。');return result
 token=FETCH_DEADLINE.set(min(FETCH_DEADLINE.get() or float('inf'),time.monotonic()+6))
 try:
  def cached(url):
   with LOCK:item=CACHE.get(url)
   if item and time.time()-item[0]<3600:
    try:return json.loads(item[1])
    except (ValueError,TypeError):pass
   return None
  def remember(url,data):
   with LOCK:CACHE[url]=(time.time(),json.dumps(data,ensure_ascii=False))
  def site(row):
   host=urlsplit(str(row.get('source',''))).hostname or ''
   if host=='modrinth.com' or host.endswith('.modrinth.com'):return 'Modrinth'
   if host=='curseforge.com' or host.endswith('.curseforge.com'):return 'CurseForge'
   return ''
  for row in rows:
   row['platform']=site(row)
   if row['platform']:row['origin']='platform'
  base='https://api.modrinth.com/v2';versions={}
  version_ids=sorted({str(r['versionId']) for r in rows if r['platform']=='Modrinth' and re.fullmatch(r'[A-Za-z0-9]{8}',str(r.get('versionId') or ''))})
  missing=[]
  for vid in version_ids:
   found=cached(base+'/version/'+vid)
   if isinstance(found,dict) and str(found.get('id'))==vid:versions[vid]=found
   else:missing.append(vid)
  for i in range(0,len(missing),40):
   try:
    for value in json.loads(fetch(base+'/versions?'+urlencode({'ids':json.dumps(missing[i:i+40])}))):
     if isinstance(value,dict) and str(value.get('id')) in missing[i:i+40]:versions[value['id']]=value;remember(base+'/version/'+value['id'],value)
   except (ValueError,KeyError,TypeError):result['notes'].append('前置固定版本资料未能取得，版本仍待核对。')
  for row in rows:
   version=versions.get(str(row.get('versionId')))
   if version and (not row.get('projectId') or str(row['projectId'])==str(version.get('project_id'))):
    row['projectId']=version.get('project_id');row['version']=str(version.get('version_number') or '未知')[:150]
   elif not row.get('versionId'):row['version']='平台未限定具体版本'
  for platform in ('Modrinth','CurseForge'):
   ids=sorted({str(r['projectId']) for r in rows if r['platform']==platform and re.fullmatch(r'[A-Za-z0-9_-]{1,120}' if platform=='Modrinth' else r'[0-9]{1,12}',str(r.get('projectId') or ''))})
   project_base=base+'/project/' if platform=='Modrinth' else 'https://api.curseforge.com/v1/mods/'
   projects={};missing=[]
   for pid in ids:
    found=cached(project_base+pid)
    if isinstance(found,dict) and platform=='CurseForge':found=found.get('data',found)
    if isinstance(found,dict) and str(found.get('id'))==pid:projects[pid]=found
    else:missing.append(pid)
   for i in range(0,len(missing),20):
    batch=missing[i:i+20]
    try:
     if platform=='Modrinth':values=json.loads(fetch(base+'/projects?'+urlencode({'ids':json.dumps(batch)})))
     elif curse_key:values=json.loads(fetch('https://api.curseforge.com/v1/mods',curse_key,payload={'modIds':[int(pid) for pid in batch]})).get('data',[])
     else:continue
     for value in values:
      if isinstance(value,dict) and str(value.get('id')) in batch:
       pid=str(value['id']);projects[pid]=value;remember(project_base+pid,{'data':value} if platform=='CurseForge' else value)
    except (ValueError,KeyError,TypeError):result['notes'].append(platform+' 前置名称未能补全，保留项目 ID。')
   for row in rows:
    if row['platform']!=platform:continue
    project=projects.get(str(row.get('projectId')))
    if not project:continue
    title=project.get('title') if platform=='Modrinth' else project.get('name')
    if isinstance(title,str) and title.strip():row['target']=title.strip()[:200]
    url='https://modrinth.com/mod/'+quote(str(project.get('slug') or project['id']),safe='') if platform=='Modrinth' else (project.get('links') or {}).get('websiteUrl','')
    if permitted(url):row['targetURL']=url
  result['notes']=list(dict.fromkeys(result['notes']));return result
 finally:FETCH_DEADLINE.reset(token);DEPENDENCY_LOCK.release()
