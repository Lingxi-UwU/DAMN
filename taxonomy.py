import hashlib
"""Versioned DAMN taxonomy mapped from public mod categories; no network or model calls."""
import json,re
from pathlib import Path
TAXONOMY=json.loads((Path(__file__).with_name('taxonomy.json')).read_text(encoding='utf-8'))
TAXONOMY_VERSION=TAXONOMY['version']
UNKNOWN='其他 / 待识别'
CATEGORIES={c['label'] for c in TAXONOMY['categories']}
FEATURES={f['label'] for c in TAXONOMY['categories'] for f in c['features']}
RULES=[(c,[(w,re.compile(p,re.I)) for w,p in c['rules']],[(f['label'],re.compile(f['pattern'],re.I)) for f in c['features']]) for c in TAXONOMY['categories']]
def normalize_category(value):
    if not isinstance(value,str):return UNKNOWN
    value=value.strip()
    return value if value in CATEGORIES else TAXONOMY['legacy'].get(value,UNKNOWN)
def normalize_tags(values):
    result=[]
    for value in values if isinstance(values,list) else []:
        if not isinstance(value,str):continue
        value=TAXONOMY['tagAliases'].get(value.strip(),value.strip())
        if value in FEATURES and value not in result:result.append(value)
    return result[:3]
def usable(value):
    return isinstance(value,str) and len(value.strip())>=4 and not re.match(r'^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供|中文用途待总结|资料不足|无法确认)',value.strip(),re.I)
def classification_descriptions(mod):
    """Prefer the concise purpose, retaining original evidence for missed terms."""
    annotation=mod.get('aiAnnotation') or {};platform=mod.get('platformInfo') or {}
    values=[mod.get('aiPurpose'),annotation.get('purpose'),annotation.get('summary'),mod.get('descriptionZh'),annotation.get('descriptionZh'),mod.get('description'),platform.get('description'),mod.get('originalDescription')]
    result=[]
    for value in values:
        if not usable(value):continue
        value=value.strip()[:4000]
        if value not in result:result.append(value)
    return result
PLACEHOLDER=re.compile(r'^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供|中文用途待总结|资料不足)',re.I)
def text(value,limit=900):
 return value.strip()[:limit].strip() if isinstance(value,str) else ''
def useful(value):
 return len(text(value))>=5 and not PLACEHOLDER.match(text(value))
def relationship_context(mod):
 """Keep ecosystem clues separate from functional categories and required dependencies."""
 compact=mod.get('relationshipContext') or {};relations=[];seen=set()
 rows=list(mod.get('classificationRelations') or [])+list(compact.get('dependencies') or [])
 rows+=[{'target':d.get('target'),'kind':d.get('type'),'basis':'文件声明'} for d in mod.get('dependencies') or []]
 rows+=[{**d,'basis':'平台 / AI 资料'} for r in mod.get('onlineResearch') or [] for d in r.get('platformDependencies') or []]
 rows+=[{**d,'basis':'平台 / AI 资料'} for d in (mod.get('aiAnnotation') or {}).get('relations') or []]
 for row in rows:
  target=text(row.get('target'),120);kind=row.get('kind') or 'related';key=(target.lower(),kind)
  if not target or re.match(r'^(Modrinth|CurseForge) 项目 ',target) or kind not in ('required','optional','related','incompatible','used_by','embedded','include','tool') or key in seen:continue
  seen.add(key);relations.append({'target':target,'kind':kind,'basis':text(row.get('basis'),70) or '已有资料'})
 name=text(mod.get('name') or mod.get('file'),220);norm=lambda v:re.sub(r'[^a-z0-9\u4e00-\u9fff]','',str(v).lower())
 roots={'create','机械动力','机械动力create','create机械动力'}
 ecosystem=None
 if norm(name) in roots or any(c.get('id')=='create' for c in mod.get('components') or []):ecosystem={'name':'Create','basis':'本体名称 / 组件 ID','confirmed':True,'root':True}
 elif any(norm(r['target']) in roots and r['kind'] in ('required','optional','embedded','include') for r in relations):ecosystem={'name':'Create','basis':'已有前置关系','confirmed':True,'root':False}
 elif re.match(r'^(?:[Cc][Rr][Ee][Aa][Tt][Ee](?:$|(?=[\s:_-]|[A-Z]))|机械动力)',name):ecosystem={'name':'Create','basis':'名称线索，待核对','confirmed':False,'root':False}
 else:
  desc=' '.join(str(v or '') for v in [mod.get('aiPurpose'),mod.get('descriptionZh'),mod.get('description'),(mod.get('platformInfo') or {}).get('description')])
  if re.search(r'(?:add.?on.{0,30}for\s+Create\b|\bCreate\b.{0,30}add.?on|为\s*(?:Create|机械动力)|(?:Create|机械动力).{0,15}附属)',desc,re.I):ecosystem={'name':'Create','basis':'简介线索，待核对','confirmed':False,'root':False}
 if isinstance(compact.get('ecosystem'),dict) and compact['ecosystem'].get('name')=='Create':
  e=compact['ecosystem'];ecosystem={'name':'Create','basis':text(e.get('basis'),70),'confirmed':e.get('confirmed') is True,'root':e.get('root') is True}
 return {**({'ecosystem':ecosystem} if ecosystem else {}),**({'dependencies':relations[:12]} if relations else {})}
def classification_material(mod):
 annotation=mod.get('aiAnnotation') or {};platform=mod.get('platformInfo') or {}
 descriptions=[mod.get('descriptionZh'),platform.get('description'),mod.get('originalDescription'),mod.get('description')]
 purposes=[mod.get('aiPurpose'),annotation.get('purpose'),annotation.get('summary')]
 tags=[]
 for record in mod.get('onlineResearch') or []:
  tags+=record.get('platformCategory') or []
  for source in record.get('sources') or []:tags+=source.get('categories') or []
 data={'name':text(mod.get('name') or mod.get('file'),220),'file':text(mod.get('file'),220),'version':text(mod.get('version'),100),'description':next((text(x) for x in descriptions if useful(x)),''),'purpose':next((text(x,500) for x in purposes if useful(x)),''),'platformTags':list(dict.fromkeys(text(t,80) for t in tags if isinstance(t,str)))[:20]}
 context=relationship_context(mod)
 if context:data['relationshipContext']=context
 return data
def classification_input_stamp(mod):
 raw=json.dumps(classification_material(mod),ensure_ascii=False,separators=(',',':')).encode('utf-16-le','surrogatepass')
 value=2166136261
 for i in range(0,len(raw),2):value=((value^(raw[i]+(raw[i+1]<<8)))*16777619)&0xffffffff
 return 'class-v1-'+format(value,'x')
def classification_eligible(mod):
 data=classification_material(mod)
 return bool(data['description'] or data['purpose'])

def platform_classification(mod):
    """Map publisher/platform categories, never infer these labels from prose."""
    records=list(mod.get('platformTaxonomy') or [])
    for record in mod.get('onlineResearch') or []:
        records.extend(record.get('platformTaxonomy') or [])
        if not record.get('platformTaxonomy') and (record.get('platformCategory') or record.get('categoryIds')):
            records.append({'site':record.get('platform') or '', 'categories':record.get('platformCategory') or [],'categoryIds':record.get('categoryIds') or [],'primaryCategoryId':record.get('primaryCategoryId'),'url':record.get('url',''),'match':record.get('match') or (record.get('identity') or {}).get('match','')})
        records.extend(s for s in record.get('sources') or [] if s.get('categories') or s.get('categoryIds'))
    info=mod.get('platformInfo') or {}
    if info.get('categories') or info.get('categoryIds'):records.append(info)
    labels=[];evidence=[];primary=[]
    for record in records:
        if record.get('matched') is False or re.search(r'关键词候选|搜索候选|身份与版本需核对',str(record.get('match',''))):continue
        site=str(record.get('site') or record.get('platform') or '')
        url=str(record.get('url') or '')
        if not site:
            site='Modrinth' if re.match(r'https://(?:api\.|www\.)?modrinth\.com/',url) else 'CurseForge' if re.match(r'https://(?:api\.|www\.)?curseforge\.com/',url) else ''
        ids=TAXONOMY.get('platformIds',{}).get(site,{})
        own=[]
        for value in list(record.get('categories') or [])+list(record.get('categoryIds') or []):
            if isinstance(value,dict):value=value.get('id') if str(value.get('id')) in ids else value.get('slug') or value.get('name') or ''
            label=ids.get(str(value))
            if not label and isinstance(value,str):
                value=value.lower().strip()
                label=TAXONOMY.get('platformAliases',{}).get(value) or next((c['label'] for c in TAXONOMY['categories'] if value in c['platform']),None)
            if label and label not in own:own.append(label)
        if not own:continue
        for label in own:
            if label not in labels:labels.append(label)
        preferred=ids.get(str(record.get('primaryCategoryId')))
        if preferred in own and preferred not in primary:primary.append(preferred)
        item={'site':site or '平台','url':url,'labels':own}
        if item not in evidence:evidence.append(item)
    # A parent and its child are one family; retain the specific child tag.
    parents={c['parent'] for c in TAXONOMY['categories'] if c.get('parent') and c['label'] in labels}
    labels=[label for label in labels if label not in parents]
    broad={'实用','科技','游戏机制','世界元素','食物与烹饪'}
    chosen=next((p for p in primary if p in labels),next((p for p in labels if p not in broad),labels[0] if labels else None))
    if chosen:labels=[chosen]+[label for label in labels if label!=chosen]
    return labels,evidence

def classify_mod(mod):
    name=str(mod.get('name') or mod.get('file') or '')[:2000]
    descriptions=classification_descriptions(mod)
    description=descriptions[0] if descriptions else ''
    fallback='\n'.join(descriptions[1:])
    platform=[]
    for record in mod.get('onlineResearch') or []:
        platform+=record.get('platformCategory') or []
        for item in record.get('sources') or []:platform+=item.get('categories') or []
    platform={str(t).lower().strip() for t in platform}
    scores=[]
    for c,rules,_ in RULES:
        local=sum(w*(bool(p.search(name))+(2 if p.search(description) else 1 if p.search(fallback) else 0)) for w,p in rules)
        local+=sum(w for w,p in c.get('nameRules',[]) if re.search(p,name,re.I))
        votes=len(platform.intersection(c['platform']))
        scores.append((c,local,votes))
    platform_labels,platform_evidence=platform_classification(mod)
    category=UNKNOWN;source='待识别'
    if platform_labels:
        category=platform_labels[0];source='平台分类 · '+' / '.join(dict.fromkeys(e['site'] for e in platform_evidence))
    else:
        chosen=max(scores,key=lambda row:(row[1],bool(row[0].get('parent'))))
        if chosen[1]:category=chosen[0]['label'];source='本地用途规则'
    if category==UNKNOWN:
        for value,origin in [(mod.get('webCategory'),'已有平台分类'),(mod.get('category'),'已有分类映射')]:
            if origin=='已有分类映射' and re.search(r'AI',str(mod.get('categoryEvidence','')),re.I):continue
            value=normalize_category(value)
            if value!=UNKNOWN:category=value;source=origin;break
    context=relationship_context(mod);ecosystem=context.get('ecosystem')
    if category==UNKNOWN and ecosystem and usable(description):category='科技';source='本地生态线索 · 暂定用途'
    selected=next(c for c in TAXONOMY['categories'] if c['label']==category);tags=[]
    for f in ([] if platform_labels else selected['features']):
        if len(tags)>=3:break
        if re.search(f['pattern'],name+' '+'\n'.join(descriptions),re.I) and f['label'] not in tags:tags.append(f['label'])
    if mod.get('kind')=='manifest' and mod.get('resolutionStatus')=='candidate':source+=' · 候选待核对'
    return {'category':category,'categories':platform_labels or [category],'platformEvidence':platform_evidence,'tags':tags,'source':source,'version':TAXONOMY_VERSION,'reason':'','ecosystems':[dict(ecosystem,label='Create 生态')] if ecosystem else []}

def classify(text):
    return classify_mod({'description':text})['category']
def taxonomy_prompt():
    choices='；'.join(c['label']+'：'+c['description']+' 可用标签['+'、'.join(f['label'] for f in c['features'])+']' for c in TAXONOMY['categories'])
    return ('分类方案 taxonomyVersion='+str(TAXONOMY_VERSION)+'。公开源码版使用平级类别，不包含父子分类。'
            '每个模组只选一个最能描述实际用途的主分类 category，最多三个不重复的功能 tags。'
            '主分类仅限下列词表，标签仅限对应的可用标签；没有适合的标签时使用空数组。'
            '平台类别与本地关键词属于分类线索，不能证明依赖关系。资料不足用其他 / 待识别。'
            '类别与功能词表：'+choices)
