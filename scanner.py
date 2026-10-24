"""DAMN offline scanner: static metadata and text, no mod execution."""
import hashlib, io, json, re, zipfile, tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from app_info import VERSION
CF_FINGERPRINT_LIMIT = 64*1024*1024
BASE_IDS = {'minecraft','java','forge','neoforge','fabricloader','quilt_loader'}
DESCRIPTORS = [('NeoForge','META-INF/neoforge.mods.toml'),('Forge','META-INF/mods.toml'),('Fabric','fabric.mod.json')]
from taxonomy import classify,classify_mod,TAXONOMY_VERSION

def numeric(v):
    if not re.fullmatch(r'\d+(?:\.\d+)*',str(v).strip()): return None
    nums=tuple(map(int,str(v).split('.')))
    return nums+(0,)*max(0,6-len(nums))
def matches(version,requirement,flavor='NeoForge'):
    """True / False / None. None means unsupported or unknown."""
    if isinstance(requirement,list):
        vals=[matches(version,x,flavor) for x in requirement]
        return True if True in vals else (None if None in vals else False)
    rule=str(requirement or '*').strip()
    if rule in ('','*'): return True
    if version==rule or version==rule.lstrip('='): return True
    if '||' in rule: return matches(version,[x.strip() for x in rule.split('||')],flavor)
    value=numeric(version)
    if value is None: return None
    if flavor in ('NeoForge','Forge'):
        if rule.startswith(('[','(')):
            if not re.fullmatch(r'[\[(][^\[\]()]*[\])]',rule): return None
            body=rule[1:-1]
            if ',' not in body:
                bound=numeric(body)
                return value==bound if bound and rule.startswith('[') and rule.endswith(']') else None
            lower,upper=[x.strip() for x in body.split(',',1)]
            lo,hi=numeric(lower) if lower else None,numeric(upper) if upper else None
            if (lower and lo is None) or (upper and hi is None): return None
            return (not lo or value>lo or (value==lo and rule[0]=='[')) and (not hi or value<hi or (value==hi and rule[-1]==']'))
        return None
    tokens=rule.split()
    if len(tokens)>1:
        vals=[matches(version,x,flavor) for x in tokens]
        return False if False in vals else (None if None in vals else True)
    if re.fullmatch(r'\d+(?:\.\d+)*\.[xX*]',rule):
        prefix=tuple(map(int,rule.split('.')[:-1])); return value[:len(prefix)]==prefix
    if rule.startswith(('~','^')):
        raw=rule[1:]; bound=numeric(raw)
        if bound is None: return None
        bits=list(map(int,raw.split('.')))
        index=(1 if len(bits)>1 else 0) if rule[0]=='~' else next((i for i,x in enumerate(bits) if x),len(bits)-1)
        high=list(bound); high[index]+=1; high[index+1:]=[0]*(len(high)-index-1)
        return bound<=value<tuple(high)
    m=re.fullmatch(r'(>=|<=|>|<|=)?(\d+(?:\.\d+)*)',rule)
    if m:
        bound=numeric(m[2]); return {'>=':value>=bound,'<=':value<=bound,'>':value>bound,'<':value<bound,'=':value==bound,None:value==bound}[m[1]]
    return None

def safe_text(z,name,limit=2_000_000):
    if z.getinfo(name).file_size>limit: raise ValueError('元数据超出读取上限：'+name)
    return z.read(name).decode('utf-8-sig',errors='replace')

def declared_authors(*values):
    """Keep bounded local author labels; these are not verified identities."""
    authors=[]
    for value in values:
        entries=value[:64] if isinstance(value,list) else [value]
        for entry in entries:
            if isinstance(entry,dict): entry=entry.get('name')
            if not isinstance(entry,str): continue
            entry=re.sub(r'\s+',' ',entry).strip()
            if not entry or len(entry)>160 or re.search(r'[\x00-\x1f\x7f]',entry): continue
            if entry not in authors: authors.append(entry)
            if len(authors)>=16: return authors
    return authors

def declared_project_urls(*values):
    """Read links as local declarations only; never fetch or trust their target."""
    urls=[]
    for value in values:
        if not isinstance(value,str): continue
        value=value.strip()
        if not value or len(value)>2048 or re.search(r'[\s\x00-\x1f\x7f\\]',value): continue
        try:
            parsed=urlsplit(value)
            if parsed.scheme not in ('http','https') or not parsed.hostname: continue
            if parsed.username is not None or parsed.password is not None: continue
            # Parsing the port rejects malformed/out-of-range authority values.
            parsed.port
            if re.search(r'[%<>"{}|^`]',parsed.hostname): continue
        except (ValueError,UnicodeError): continue
        if value not in urls: urls.append(value)
        if len(urls)>=12: break
    return urls

def read_jar(z,origin,preferred,errors,depth=0,budget=None):
    budget=budget if budget is not None else [64_000_000]
    names=set(z.namelist()); options=[(a,b) for a,b in DESCRIPTORS if b in names]
    selected=next((x for x in options if x[0]==preferred),options[0] if options else None)
    components,deps,nested_paths=[],[],[]
    loader=selected[0] if selected else '未知'; source=origin+('!'+selected[1] if selected else '')
    if selected:
        if loader=='Fabric':
            data=json.loads(safe_text(z,selected[1])); ident=str(data['id'])
            contact=data.get('contact') if isinstance(data.get('contact'),dict) else {}
            components.append({'id':ident,'name':data.get('name',ident),'version':str(data.get('version','未知')),'description':str(data.get('description','')),'source':source,'nested':depth>0,'environment':data.get('environment','*'),'aliases':data.get('provides',[]),'authors':declared_authors(data.get('authors'),data.get('author')),'projectUrls':declared_project_urls(*(contact.get(key) for key in ('homepage','sources','issues')))})
            for field,typ in [('depends','required'),('recommends','optional'),('suggests','optional'),('breaks','incompatible'),('conflicts','discouraged')]:
                for target,constraint in data.get(field,{}).items(): deps.append({'owner':ident,'target':target,'range':constraint,'type':typ,'side':'BOTH','loader':loader,'source':source})
            nested_paths.extend(x['file'] for x in data.get('jars',[]) if isinstance(x,dict) and 'file' in x)
        else:
            data=tomllib.loads(safe_text(z,selected[1])); jar_version='未知'
            if 'META-INF/MANIFEST.MF' in names:
                m=re.search(r'^Implementation-Version:\s*(.+)$',safe_text(z,'META-INF/MANIFEST.MF'),re.M)
                if m: jar_version=m[1].strip()
            for mod in data.get('mods',[]):
                ident=str(mod['modId']); v=str(mod.get('version','未知')).replace('$'+'{file.jarVersion}',jar_version)
                components.append({'id':ident,'name':mod.get('displayName',ident),'version':v,'description':str(mod.get('description','')),'source':source,'nested':depth>0,'environment':'*','aliases':[],'authors':declared_authors(mod.get('authors'),mod.get('author')),'projectUrls':declared_project_urls(mod.get('displayURL'),mod.get('issueTrackerURL'),data.get('displayURL'),data.get('issueTrackerURL'))})
                for d in data.get('dependencies',{}).get(ident,[]):
                    typ=d.get('type','required' if d.get('mandatory',True) else 'optional')
                    deps.append({'owner':ident,'target':d['modId'],'range':d.get('versionRange','*'),'type':typ,'side':str(d.get('side','BOTH')).upper(),'loader':loader,'source':source})
    if 'META-INF/jarjar/metadata.json' in names:
        try:
            meta=json.loads(safe_text(z,'META-INF/jarjar/metadata.json'))
            nested_paths.extend(x['path'] for x in meta.get('jars',[]) if isinstance(x,dict) and 'path' in x)
        except (ValueError,KeyError) as e: errors.append({'source':origin,'message':'内置依赖目录无法解析：'+str(e)})
    for entry in dict.fromkeys(nested_paths):
        if depth>=3:
            errors.append({'source':origin+'!'+entry,'message':'内置 JAR 超出 3 层读取上限，分析不完整'}); continue
        try:
            info=z.getinfo(entry)
            if info.file_size>min(32_000_000,budget[0]): raise ValueError('内置 JAR 超出读取上限，分析不完整')
            budget[0]-=info.file_size
            with zipfile.ZipFile(io.BytesIO(z.read(entry))) as nested:
                cs,ds,_,_=read_jar(nested,origin+'!'+entry,preferred,errors,depth+1,budget)
                components.extend(cs); deps.extend(ds)
        except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e: errors.append({'source':origin+'!'+entry,'message':str(e)})
    return components,deps,loader,[x[0] for x in options]

def instance_environment(root):
    env={}
    for file in ([root/'mmc-pack.json']+sorted(root.glob('*.json')))[:30]:
        if not file.is_file() or file.is_symlink() or file.stat().st_size>2_000_000: continue
        try:
            data=json.loads(file.read_text(encoding='utf-8-sig'))
            for c in data.get('components',[]):
                key={'net.minecraft':'minecraft','net.neoforged':'neoforge','net.minecraftforge':'forge','net.fabricmc.fabric-loader':'fabricloader'}.get(c.get('uid',''))
                if key: env[key]=str(c.get('version',''))
            if 'mainClass' in data and 'id' in data:
                if data.get('inheritsFrom'): env.setdefault('minecraft',str(data['inheritsFrom']))
                elif re.fullmatch(r'\d+\.\d+(?:\.\d+)?',data['id']): env.setdefault('minecraft',data['id'])
                for lib in data.get('libraries',[]):
                    name=lib.get('name','')
                    for prefix,key in [('net.neoforged:neoforge:','neoforge'),('net.minecraftforge:forge:','forge'),('net.fabricmc:fabric-loader:','fabricloader')]:
                        if name.startswith(prefix): env.setdefault(key,name[len(prefix):].split(':')[0])
        except (ValueError,OSError,TypeError): pass
    return env

def references(root,ids,errors):
    refs,counts,visited=[],Counter(),0
    for folder in ['kubejs','config','defaultconfigs','datapacks']:
        base=root/folder
        if not base.is_dir() or base.is_symlink(): continue
        for file in sorted(base.rglob('*')):
            if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(root): continue
            if file.suffix.lower() not in {'.js','.json','.json5','.toml','.snbt','.cfg','.properties'}: continue
            visited+=1; counts[folder]+=1
            if visited>3000 or len(refs)>=5000:
                errors.append({'source':folder,'message':'文本分析达到数量上限，分析不完整'}); return refs,dict(counts)
            if file.stat().st_size>2_000_000:
                errors.append({'source':file.relative_to(root).as_posix(),'message':'文本超过 2 MB，已跳过'}); continue
            text=file.read_text(encoding='utf-8-sig',errors='replace')
            for line_no,line in enumerate(text.splitlines(),1):
                for ident in set(re.findall(r'(?<![\w])([a-z][a-z0-9_]{1,63}):[a-z0-9_./-]+',line)) & ids:
                    refs.append({'id':ident,'file':file.relative_to(root).as_posix(),'line':line_no,'snippet':line.strip()[:240],'confidence':'文本命中，需人工核对'})
    return refs,dict(counts)

def scan(directory,side='client',environment=None):
    root=Path(directory).expanduser().resolve()
    if root.name.lower()=='mods': root=root.parent
    if not root.is_dir() or not (root/'mods').is_dir(): raise ValueError('请选择包含 mods 文件夹的整合包目录，或 mods 文件夹本身。')
    if side not in ('client','server'): raise ValueError('运行环境必须为 client 或 server。')
    env=instance_environment(root)
    env.update(environment or {})
    preferred=next((n for k,n in [('neoforge','NeoForge'),('forge','Forge'),('fabricloader','Fabric')] if k in env),None)
    paths=sorted(p for p in (root/'mods').iterdir() if p.is_file() and (p.name.lower().endswith('.jar') or p.name.lower().endswith('.jar.disabled')))
    if len(paths)>3000: raise ValueError('当前版本最多扫描 3000 个模组文件。')
    mods,errors,issues=[],[],[]
    for index,file in enumerate(paths):
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            errors.append({'source':file.name,'message':'链接指向整合包外部，已跳过'}); continue
        try:
            with zipfile.ZipFile(file) as z: components,deps,loader,loaders=read_jar(z,file.name,preferred,errors)
            digest=hashlib.sha256();sha1=hashlib.sha1()
            fingerprint_data=bytearray() if file.stat().st_size<=CF_FINGERPRINT_LIMIT else None
            with file.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(chunk);sha1.update(chunk)
                    if fingerprint_data is not None:fingerprint_data.extend(chunk)
            fingerprint=None
            if fingerprint_data is not None:
                from identity import curseforge_fingerprint
                fingerprint=curseforge_fingerprint(fingerprint_data)
            del fingerprint_data
            top=[c for c in components if not c['nested']]
            title=' / '.join(str(c['name']) for c in top) or file.name; desc='\n'.join(c['description'] for c in top if c['description'])
            mods.append({'key':'m'+str(index),'file':file.name,'name':title,'version':' / '.join(dict.fromkeys(c['version'] for c in top)) or '未知','description':desc or '文件没有提供用途说明。可按需使用 AI 补充解释。','category':classify(title+' '+desc),'categoryEvidence':'本地关键词规则推测','enabled':not file.name.lower().endswith('.disabled'),'loader':loader,'loaders':loaders,'components':components,'dependencies':deps,'bytes':file.stat().st_size,'sha256':digest.hexdigest(),'sha1':sha1.hexdigest(),'cfFingerprint':fingerprint,'cfFingerprintNote':'' if fingerprint is not None else '文件超过64 MiB，已跳过CurseForge指纹；仍可按SHA-1核对Modrinth。','sources':list(dict.fromkeys(c['source'] for c in components))})
            if not components: errors.append({'source':file.name,'message':'未识别到支持的模组元数据，无法判断其依赖'})
        except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as e: errors.append({'source':file.name,'message':'无法解析：'+str(e)[:240]})
    for mod in mods:
        classification=classify_mod(mod)
        mod.update(category=classification['category'],tags=classification['tags'],categoryTaxonomyVersion=TAXONOMY_VERSION,categoryEvidence='本地用途规则 · 分类方案 v'+str(TAXONOMY_VERSION))
    providers=defaultdict(list); all_ids=set()
    for mod in mods:
        top=[c for c in mod['components'] if not c['nested']]
        mod['active']=mod['enabled'] and not (mod['loader']=='Fabric' and top and all(c['environment']==('client' if side=='server' else 'server') for c in top))
        for c in mod['components']:
            all_ids.add(c['id'])
            if mod['active'] and c['environment'] not in ({'client'} if side=='server' else {'server'}):
                for ident in [c['id']]+c['aliases']: providers[ident].append((mod,c))
    for ident,entries in providers.items():
        top={m['key'] for m,c in entries if not c['nested'] and c['id']==ident}
        if len(top)>1: issues.append({'level':'error','kind':'duplicate','mod':next(iter(top)),'text':'多个启用文件声明同一组件：'+ident,'source':'、'.join(m['file'] for m,c in entries if not c['nested'])})
    edges,unchecked=[],0
    for mod in mods:
        if not mod['active']: continue
        if preferred and preferred not in mod['loaders'] and mod['loader']!='未知': issues.append({'level':'warning','kind':'loader','mod':mod['key'],'text':'文件未声明支持实例的 '+preferred+' 加载器','source':mod['file']})
        for d in mod['dependencies']:
            if d['side'] not in ('BOTH',side.upper()) or d['type'] not in ('required','incompatible','discouraged'): continue
            if d['target'] in BASE_IDS:
                result=matches(env[d['target']],d['range'],d['loader']) if d['target'] in env else None
                if result is False and d['type']=='required': issues.append({'level':'error','kind':'version','mod':mod['key'],'text':d['target']+' 版本 '+env[d['target']]+' 不满足 '+str(d['range']),'source':d['source']})
                if result is True and d['type'] in ('incompatible','discouraged'):
                    issues.append({'level':'error' if d['type']=='incompatible' else 'warning','kind':'conflict','mod':mod['key'],'text':'声明不兼容或不推荐的基础环境：'+d['target']+' '+str(d['range']),'source':d['source']})
                if result is None: unchecked+=1
                continue
            targets=providers.get(d['target'],[])
            if not targets and d['type']=='required': issues.append({'level':'error','kind':'missing','mod':mod['key'],'text':'缺少已声明的必需依赖：'+d['target']+' '+str(d['range']),'source':d['source']})
            states=[matches(c['version'],d['range'],d['loader']) for m,c in targets]
            if targets and d['type'] in ('incompatible','discouraged'):
                if True in states: issues.append({'level':'error' if d['type']=='incompatible' else 'warning','kind':'conflict','mod':mod['key'],'text':'声明不兼容或不推荐同时使用：'+d['target']+' '+str(d['range']),'source':d['source']})
                elif None in states: unchecked+=1
            if targets and d['type']=='required':
                if all(v is False for v in states): issues.append({'level':'error','kind':'version','mod':mod['key'],'text':'依赖版本不满足要求：'+d['target']+' '+str(d['range']),'source':d['source']})
                elif None in states and True not in states: unchecked+=1
                for target,_ in targets:
                    if target['key']!=mod['key']:
                        edge={'from':mod['key'],'to':target['key'],'id':d['target'],'range':d['range'],'source':d['source']}
                        if edge not in edges: edges.append(edge)
    if (root/'config/fabric_loader_dependencies.json').is_file():
        issues.append({'level':'warning','kind':'override','mod':'instance','text':'发现 Fabric 依赖覆盖文件；当前版本未应用这些覆盖，依赖结果需要人工核对。','source':'config/fabric_loader_dependencies.json'})
    refs,files=references(root,all_ids,errors)
    return {'schema':1,'app':'DAMN','version':VERSION,'mode':'scan','pack':root.name,'root':str(root),'created':datetime.now(timezone.utc).isoformat(),'side':side,'environment':env,'mods':mods,'edges':edges,'issues':issues,'references':refs,'files':files,'errors':errors,'unchecked':unchecked,'fileCount':len(paths),'limits':['静态读取不等于已通过游戏启动验证。','用途分类由本地规则推测；脚本文本命中不能证明运行时依赖。','未分析存档、Mixin 行为和压缩数据包；复杂版本区间可能无法核对。','Java 实际运行版本未读取；缺少实例版本信息时，基础环境依赖保持待核对。','Fabric dependency overrides 尚未应用，存在覆盖文件时需手工核对。']}

def impact(report,key):
    affected={key}
    while True:
        more={e['from'] for e in report['edges'] if e['to'] in affected}
        if more<=affected: break
        affected.update(more)
    ids={c['id'] for m in report['mods'] if m['key'] in affected for c in m['components']}
    return {'mods':[m['key'] for m in report['mods'] if m['key'] in affected and m['key']!=key],'references':[r for r in report['references'] if r['id'] in ids],'note':'沿已声明的必需依赖追溯；仅供改动规划，不保证可安全删除。'}
