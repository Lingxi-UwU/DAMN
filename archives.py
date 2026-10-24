"""Read ZIP-based modpacks in an isolated temporary folder. Never install or run."""
import json, re, stat, tempfile, zipfile, shutil
from pathlib import Path, PurePosixPath
from scanner import scan
MAX_UPLOAD=2*1024**3
MAX_EXTRACT=3*1024**3
TEXT_SUFFIXES={'.js','.json','.json5','.toml','.snbt','.cfg','.properties'}

def clean_path(raw):
    name=str(raw).replace('\\','/')
    bits=PurePosixPath(name).parts
    if not name or name.startswith('/') or ':' in name or '\x00' in name or '..' in bits or any(x.rstrip(' .')!=x for x in bits):
        raise ValueError('压缩包包含不安全的路径：'+name[:100])
    if any(x.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for x in bits):
        raise ValueError('压缩包包含系统保留文件名。')
    return '/'.join(x for x in bits if x not in ('','.'))

def index_zip(z):
    infos=z.infolist()
    if len(infos)>50000: raise ValueError('压缩包文件条目超过 50000，当前版本暂不分析。')
    entries={}; folded=set()
    for info in infos:
        if info.is_dir(): continue
        name=clean_path(info.filename)
        if stat.S_ISLNK(info.external_attr>>16): raise ValueError('压缩包包含符号链接，当前版本不导入链接文件。')
        if name.casefold() in folded: raise ValueError('压缩包包含重复或大小写冲突的文件路径：'+name[:100])
        if info.flag_bits & 1: raise ValueError('暂不支持加密压缩包，请先解密。')
        folded.add(name.casefold()); entries[name]=info
    return entries

def manifest_info(z,entries):
    if 'modrinth.index.json' in entries:
        info=entries['modrinth.index.json']
        if info.file_size>4_000_000: raise ValueError('整合包清单过大。')
        data=json.loads(z.read(info).decode('utf-8-sig'))
        if data.get('game')!='minecraft' or data.get('formatVersion')!=1: raise ValueError('暂不支持这个 Modrinth 清单版本或游戏类型。')
        env={k.replace('fabric-loader','fabricloader').replace('quilt-loader','quilt_loader'):str(v) for k,v in data.get('dependencies',{}).items()}
        return 'Modrinth',data,env,'modrinth.index.json'
    if 'manifest.json' in entries:
        info=entries['manifest.json']
        if info.file_size>4_000_000: raise ValueError('整合包清单过大。')
        data=json.loads(z.read(info).decode('utf-8-sig'))
        if data.get('manifestType')!='minecraftModpack': return None,{}, {},''
        env={'minecraft':str(data.get('minecraft',{}).get('version',''))}
        for loader in data.get('minecraft',{}).get('modLoaders',[]):
            ident=loader.get('id','')
            for prefix,key in [('neoforge-','neoforge'),('forge-','forge'),('fabric-','fabricloader'),('quilt-','quilt_loader')]:
                if ident.startswith(prefix) and (loader.get('primary',False) or key not in env): env[key]=ident[len(prefix):]
        return 'CurseForge',data,env,'manifest.json'
    return None,{}, {},''

def wanted(relative):
    bits=PurePosixPath(relative).parts
    if not bits: return False
    if len(bits)==2 and bits[0].lower()=='mods' and relative.lower().endswith(('.jar','.jar.disabled')): return True
    if len(bits)==1 and relative.lower().endswith('.json'): return True
    return bits[0] in ('kubejs','config','defaultconfigs','datapacks') and PurePosixPath(relative).suffix.lower() in TEXT_SUFFIXES

def manifest_mods(kind,data,source,side,actual_paths):
    rows=[]; skipped=0
    for i,item in enumerate(data.get('files',[])):
        if not isinstance(item,dict): raise ValueError('整合包文件清单格式不正确。')
        details={}
        if kind=='Modrinth':
            rel=clean_path(item.get('path',''))
            if not (rel.lower().startswith('mods/') and rel.lower().endswith('.jar')): continue
            if rel in actual_paths: continue
            state=item.get('env',{}).get(side,'required')
            if state=='unsupported': skipped+=1; continue
            name=PurePosixPath(rel).name
            details={'path':rel,'hashes':item.get('hashes',{}),'downloads':item.get('downloads',[]),'fileSize':item.get('fileSize'),'environment':item.get('env',{}),'required':state=='required'}
        else:
            if 'projectID' not in item or 'fileID' not in item: raise ValueError('CurseForge 清单缺少项目 ID 或文件 ID。')
            name='CurseForge 项目 '+str(item['projectID'])+' / 文件 '+str(item['fileID'])
            rel='待获取 / '+name
            details={'projectID':item['projectID'],'fileID':item['fileID'],'required':item.get('required',True)}
        rows.append({'key':'p'+str(i),'kind':'manifest','file':rel,'name':name,'version':'清单未提供','description':'仅有下载清单，尚未读取实际 JAR。模组用途、组件 ID 和完整依赖需要实际文件进一步确认。','descriptionSource':'整合包下载清单','category':'下载清单 / 待识别','categoryEvidence':'尚未读取 JAR','enabled':None,'active':False,'loader':kind+' 清单','loaders':[],'components':[],'dependencies':[],'dependenciesKnown':False,'bytes':item.get('fileSize',0),'sha256':'','sources':[source+'#files['+str(i)+']'],'manifest':details})
        if len(rows)>3000: raise ValueError('清单模组条目超过 3000，当前版本暂不分析。')
    return rows,skipped

def scan_archive(filename,side='client',root_hint=None,display_name=None):
    if side not in ('client','server'): raise ValueError('分析环境必须为客户端或服务端。')
    if not zipfile.is_zipfile(filename): raise ValueError('请选择 ZIP 或 MRPACK 文件。RAR / 7z 暂不支持。')
    title=display_name or Path(filename).name
    with zipfile.ZipFile(filename) as z:
        entries=index_zip(z)
        kind,data,env,manifest_source=manifest_info(z,entries)
        # Normalize the root detection for case variations of the mods directory.
        roots=sorted({re.match(r'^(.*?)(?:/)?mods/[^/]+\.jar(?:\.disabled)?$',name,re.I).group(1).rstrip('/') for name in entries if re.match(r'^(.*?)(?:/)?mods/[^/]+\.jar(?:\.disabled)?$',name,re.I)})
        overrides=clean_path(data.get('overrides','overrides')) if kind=='CurseForge' else 'overrides'
        layered=bool(kind) and all(r in {overrides,'client-overrides','server-overrides'} for r in roots)
        if layered: prefixes=[overrides]+([side+'-overrides'] if kind=='Modrinth' else [])
        else:
            if len(roots)>1 and root_hint is None: return {'needsRoot':True,'roots':roots,'archiveName':title}
            if root_hint is not None and root_hint not in roots: raise ValueError('选择的整合包子目录不存在，请重新导入。')
            if roots: prefixes=[root_hint if root_hint is not None else roots[0]]
            elif kind: prefixes=[overrides]+([side+'-overrides'] if kind=='Modrinth' else [])
            else: raise ValueError('没有找到 mods 目录、Modrinth 清单或 CurseForge 清单。')
        selected={}
        for prefix in prefixes:
            start=prefix+'/' if prefix else ''
            for name,info in entries.items():
                if not name.startswith(start): continue
                rel=name[len(start):]
                if wanted(rel):
                    bits=rel.split('/')
                    if bits[0].lower()=='mods': bits[0]='mods'
                    selected['/'.join(bits)]=(name,info)
        if sum(info.file_size for _,info in selected.values())>MAX_EXTRACT: raise ValueError('待分析文件解压后超过 3 GiB，请选择已解压的整合包目录。')
        for rel,(name,info) in selected.items():
            if info.file_size>1_500_000_000: raise ValueError('单个文件过大，当前版本无法分析：'+name[:100])
            if info.file_size>20_000_000 and info.file_size/max(info.compress_size,1)>1000: raise ValueError('压缩比异常，已停止读取：'+name[:100])
        with tempfile.TemporaryDirectory(prefix='damn-unpack-') as scratch:
            root=Path(scratch); (root/'mods').mkdir()
            extracted=0; notes=[]
            for rel,(name,info) in selected.items():
                if not rel.startswith('mods/') and info.file_size>2_000_000:
                    notes.append({'source':name,'message':'文本超过 2 MB，已跳过'});continue
                target=root/rel
                if not target.resolve().is_relative_to(root): raise ValueError('压缩包路径超出临时分析目录。')
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src,target.open('wb') as dst:
                    remaining=info.file_size
                    while chunk:=src.read(min(1024*1024,remaining+1)):
                        remaining-=len(chunk);extracted+=len(chunk)
                        if remaining<0 or extracted>MAX_EXTRACT: raise ValueError('解压大小超过安全上限。')
                        dst.write(chunk)
            report=scan(root,side,env)
        planned,skipped=manifest_mods(kind,data,manifest_source,side,set(selected)) if kind else ([],0)
        for mod in report['mods']:
            name,info=selected['mods/'+mod['file']]
            prefix=title+'!'+name
            def origin(s): return prefix+s[len(mod['file']):] if s.startswith(mod['file']) else s
            mod['archivePath']=name
            mod['sources']=[origin(s) for s in mod['sources']]
            for c in mod['components']: c['source']=origin(c['source'])
            for d in mod['dependencies']: d['source']=origin(d['source'])
        for ref in report['references']:
            ref['archivePath']=selected.get(ref['file'],(ref['file'],None))[0]
        if planned:
            for issue in report['issues']:
                if issue['kind']=='missing':
                    issue['level']='warning';issue['kind']='unresolved';issue['text']='包内文件尚未找到依赖，可能由下载清单提供：'+issue['text'].split('：',1)[-1]
            report['issues'].insert(0,{'level':'warning','kind':'manifest','mod':'instance','text':str(len(planned))+' 项仅有下载清单，尚未读取 JAR，无法完整检查依赖。','source':manifest_source})
        for p in planned: p['sources']=[title+'!'+s for s in p['sources']]
        report.update({'mode':'archive','pack':str(data.get('name') or Path(title).stem),'root':'压缩包：'+title+('!'+prefixes[0] if prefixes else ''),'mods':report['mods']+planned,'archive':{'name':title,'format':kind or 'ZIP','roots':prefixes,'manifest':manifest_source,'jarFiles':report['fileCount'],'manifestOnly':len(planned),'skippedForSide':skipped,'extractedFiles':len(selected)},'fileCount':report['fileCount']+len(planned)})
        report['errors'].extend(notes)
        report['limits'].insert(0,'压缩包仅在临时目录读取选定的模组与文本；原压缩包不会被修改，也不会自动下载清单里的文件。')
        if planned: report['limits'].insert(1,'下载清单项的名称、用途、组件和依赖尚未确认；CurseForge 项目/文件 ID 不等于模组 ID。')
        return report
