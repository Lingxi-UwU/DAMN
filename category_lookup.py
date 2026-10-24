"""Free, bounded project metadata refresh. This module has no AI dependency."""
import concurrent.futures,time,re
import research as sources
from urllib.parse import urlencode

REVISION=1

def project_ids(mod):
    identity=mod.get('platformInfo') or {};ids={}
    if identity.get('exact') or mod.get('resolutionStatus')=='matched' or sources.normalize(identity.get('title'))==sources.normalize(mod.get('name')):
        ids.update(identity.get('projectIds') or {})
    for record in mod.get('onlineResearch') or []:
        ident=record.get('identity') or {}
        if ident.get('exact'):ids.update(ident.get('projectIds') or {})
    if (mod.get('manifest') or {}).get('projectID'):ids['CurseForge']=mod['manifest']['projectID']
    return ids

def resolve_categories(mods,curse_key='',lookup=None,warm=None):
    if not isinstance(mods,list) or not 1<=len(mods)<=12:raise ValueError('一次可补查 1 至 12 个模组的平台分类。')
    clean=[];keys=set()
    for mod in mods:
        if not isinstance(mod,dict) or not isinstance(mod.get('key'),str) or not 1<=len(mod['key'])<=200 or mod['key'] in keys:raise ValueError('模组条目或标识无效。')
        keys.add(mod['key']);clean.append(mod)
    # Populate the public hash/version/project caches in batches first.
    (warm or sources.warm_modrinth)([m for m in clean if not project_ids(m).get('Modrinth')])
    def one(mod):
        token=sources.FETCH_DEADLINE.set(time.monotonic()+10)
        try:
            if lookup:return lookup(mod,curse_key)
            ids=project_ids(mod);records=[];notes=[]
            # A known project ID is sufficient for project categories; no version guess.
            target={**mod,'platformInfo':{'projectIds':ids}}
            if ids.get('Modrinth'):target={**target,'sha1':None,'manifest':{}}
            try:
                data=sources.modrinth(target,sources.query_for(mod))
                records.extend(r for r in data.get('platformTaxonomy') or [] if r.get('matched'))
                if not records:notes.append('Modrinth 尚未匹配到相符项目。')
            except (ValueError,KeyError,TypeError,AttributeError):notes.append('Modrinth 分类暂不可用。')
            if curse_key:
                try:
                    if ids.get('CurseForge'):
                        data=sources.curseforge_api({'manifest':{'projectID':ids['CurseForge']}},curse_key)
                        records.extend((data or {}).get('platformTaxonomy') or [])
                    elif not records:
                        import json
                        query=sources.query_for(mod)
                        data=json.loads(sources.fetch('https://api.curseforge.com/v1/mods/search?'+urlencode({'gameId':432,'classId':6,'searchFilter':query,'pageSize':3}),curse_key))
                        for project in data.get('data') or []:
                            title=re.sub(r'\[[^\]]*\]|\([^)]*\)','',project.get('name',''))
                            if sources.normalize(query)!=sources.normalize(title):continue
                            url=(project.get('links') or {}).get('websiteUrl','')
                            if sources.permitted(url):records.append(sources.project_taxonomy('CurseForge',project,url))
                            break
                except (ValueError,KeyError,TypeError,AttributeError):notes.append('CurseForge 分类暂不可用。')
            elif not records:notes.append('CurseForge 服务暂不可用，平台分类保留待识别。')
            return {'records':records,'notes':notes}
        finally:sources.FETCH_DEADLINE.reset(token)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        values=list(pool.map(one,clean))
    return {'revision':REVISION,'aiCalls':0,'updates':[{'key':mod['key'],'records':value.get('records') or [],'notes':value.get('notes') or [],'checkedAt':int(time.time())} for mod,value in zip(clean,values)]}
