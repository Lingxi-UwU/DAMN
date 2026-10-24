'use strict';
// Shared reading model for the live list and exported report. Legacy reports remain usable.
// The browser and Python load the same versioned taxonomy.json.
const DAMN_TAXONOMY_DATA=typeof module!=='undefined'&&module.exports?require('../taxonomy.json'):globalThis.DAMN_TAXONOMY;
const DAMN_CATEGORIES=DAMN_TAXONOMY_DATA.categories.map(c=>c.label);
const DAMN_CATEGORY_GROUPS=[...new Set(DAMN_TAXONOMY_DATA.categories.map(c=>c.group))];
const DAMN_FEATURES=new Set(DAMN_TAXONOMY_DATA.categories.flatMap(c=>c.features.map(f=>f.label)));
const DAMN_CATEGORY_RULES=DAMN_TAXONOMY_DATA.categories.map(c=>({...c,rules:c.rules.map(([w,p])=>[w,new RegExp(p,'i')]),features:c.features.map(f=>({...f,re:new RegExp(f.pattern,'i')}))}));
const damnTaxonomyCache=new WeakMap();
function damnNormalizeCategory(value){if(typeof value!=='string')return '其他 / 待识别';value=value.trim();return DAMN_CATEGORIES.includes(value)?value:DAMN_TAXONOMY_DATA.legacy[value]||'其他 / 待识别';}
function damnNormalizeTags(values){return [...new Set((Array.isArray(values)?values:[]).filter(x=>typeof x==='string').map(x=>DAMN_TAXONOMY_DATA.tagAliases[x.trim()]||x.trim()).filter(x=>DAMN_FEATURES.has(x)))].slice(0,3);}
function damnRelationshipContext(m){
 const compact=m.relationshipContext||{},norm=v=>String(v||'').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g,''),text=(v,n)=>typeof v==='string'?Array.from(v.trim()).slice(0,n).join('').trim():'',seen=new Set(),relations=[];
 const rows=[...(m.classificationRelations||[]),...(compact.dependencies||[]),...(m.dependencies||[]).map(d=>({target:d.target,kind:d.type,basis:'文件声明'})),...(m.onlineResearch||[]).flatMap(r=>(r.platformDependencies||[]).map(d=>({...d,basis:'平台 / AI 资料'}))),...(m.aiAnnotation?.relations||[]).map(d=>({...d,basis:'平台 / AI 资料'}))];
 for(const r of rows){const target=text(r.target,120),kind=r.kind||'related',key=target.toLowerCase()+'|'+kind;if(!target||/^(Modrinth|CurseForge) 项目 /.test(target)||!['required','optional','related','incompatible','used_by','embedded','include','tool'].includes(kind)||seen.has(key))continue;seen.add(key);relations.push({target,kind,basis:text(r.basis,70)||'已有资料'});}
 const name=text(m.name||m.file,220),roots=new Set(['create','机械动力','机械动力create','create机械动力']);let ecosystem=null;
 if(roots.has(norm(name))||(m.components||[]).some(c=>c.id==='create'))ecosystem={name:'Create',basis:'本体名称 / 组件 ID',confirmed:true,root:true};
 else if(relations.some(r=>roots.has(norm(r.target))&&['required','optional','embedded','include'].includes(r.kind)))ecosystem={name:'Create',basis:'已有前置关系',confirmed:true,root:false};
 else if(/^(?:[Cc][Rr][Ee][Aa][Tt][Ee](?:$|(?=[\s:_-]|[A-Z]))|机械动力)/.test(name))ecosystem={name:'Create',basis:'名称线索，待核对',confirmed:false,root:false};
 else if(/(?:add.?on.{0,30}for\s+Create\b|\bCreate\b.{0,30}add.?on|为\s*(?:Create|机械动力)|(?:Create|机械动力).{0,15}附属)/i.test([m.aiPurpose,m.descriptionZh,m.description,m.platformInfo?.description].filter(Boolean).join(' ')))ecosystem={name:'Create',basis:'简介线索，待核对',confirmed:false,root:false};
 if(compact.ecosystem?.name==='Create'){const e=compact.ecosystem;ecosystem={name:'Create',basis:text(e.basis,70),confirmed:e.confirmed===true,root:e.root===true};}
 return {...(ecosystem?{ecosystem}:{}),...(relations.length?{dependencies:relations.slice(0,12)}:{})};
}
function damnClassificationMaterial(m){
 const annotation=m.aiAnnotation||{},platform=m.platformInfo||{},text=(v,n=900)=>typeof v==='string'?Array.from(v.trim()).slice(0,n).join('').trim():'',useful=v=>Array.from(text(v)).length>=5&&!/^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供|中文用途待总结|资料不足)/i.test(text(v));
 const tags=(m.onlineResearch||[]).flatMap(r=>[...(r.platformCategory||[]),...(r.sources||[]).flatMap(s=>s.categories||[])]);
 const data={name:text(m.name||m.file,220),file:text(m.file,220),version:text(m.version,100),description:[m.descriptionZh,platform.description,m.originalDescription,m.description].filter(useful).map(v=>text(v))[0]||'',purpose:[m.aiPurpose,annotation.purpose,annotation.summary].filter(useful).map(v=>text(v,500))[0]||'',platformTags:[...new Set(tags.filter(t=>typeof t==='string').map(t=>text(t,80)))].slice(0,20)},context=damnRelationshipContext(m);if(Object.keys(context).length)data.relationshipContext=context;return data;
}
function damnClassificationInputStamp(m){let value=2166136261;const raw=JSON.stringify(damnClassificationMaterial(m));for(let i=0;i<raw.length;i++)value=Math.imul(value^raw.charCodeAt(i),16777619);return 'class-v1-'+(value>>>0).toString(16);}
function damnClassificationEligible(m){const data=damnClassificationMaterial(m);return !!(data.description||data.purpose);}
function damnCurrentClassification(m){const c=m.aiClassification;return c&&c.revision===1&&c.taxonomyVersion===2&&c.inputStamp===damnClassificationInputStamp(m)&&DAMN_CATEGORIES.includes(c.category)?c:null;}
function damnHasAIClassification(m){return !!damnCurrentClassification(m)||m.aiAnnotation?.taxonomyVersion===2&&DAMN_CATEGORIES.includes(m.aiAnnotation?.category)&&m.aiAnnotation.category!=='其他 / 待识别';}
function damnPendingClassification(){return false;}

function damnClassificationDescriptions(m){
 const annotation=m.aiAnnotation||{},values=[m.aiPurpose,annotation.purpose,annotation.summary,m.descriptionZh,annotation.descriptionZh,m.description,m.platformInfo?.description,m.originalDescription];
 return [...new Set(values.filter(x=>typeof x==='string'&&x.trim().length>=4&&!/^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供|中文用途待总结|资料不足|无法确认)/i.test(x.trim())).map(x=>x.trim().slice(0,4000)))];
}
function damnPlatformClassification(m){
 const records=[...(m.platformTaxonomy||[])];
 for(const record of m.onlineResearch||[]){
  records.push(...(record.platformTaxonomy||[]));
  if(!record.platformTaxonomy?.length&&(record.platformCategory?.length||record.categoryIds?.length))records.push({site:record.platform||'',categories:record.platformCategory||[],categoryIds:record.categoryIds||[],primaryCategoryId:record.primaryCategoryId,url:record.url||'',match:record.match||record.identity?.match||''});
  records.push(...(record.sources||[]).filter(s=>s.categories?.length||s.categoryIds?.length));
 }
 if(m.platformInfo?.categories?.length||m.platformInfo?.categoryIds?.length)records.push(m.platformInfo);
 const labels=[],evidence=[],primary=[];
 for(const record of records){
  if(record.matched===false||/关键词候选|搜索候选|身份与版本需核对/.test(record.match||''))continue;
  let site=String(record.site||record.platform||''),url=String(record.url||'');
  if(!site)site=/^https:\/\/(?:api\.|www\.)?modrinth\.com\//.test(url)?'Modrinth':/^https:\/\/(?:api\.|www\.)?curseforge\.com\//.test(url)?'CurseForge':'';
  const ids=DAMN_TAXONOMY_DATA.platformIds?.[site]||{},own=[];
  for(let value of [...(record.categories||[]),...(record.categoryIds||[])]){
   if(value&&typeof value==='object')value=String(value.id) in ids?value.id:value.slug||value.name||'';
   let label=ids[String(value)];
   if(!label&&typeof value==='string'){value=value.toLowerCase().trim();label=DAMN_TAXONOMY_DATA.platformAliases?.[value]||DAMN_TAXONOMY_DATA.categories.find(c=>c.platform.includes(value))?.label;}
   if(label&&!own.includes(label))own.push(label);
  }
  if(!own.length)continue;
  for(const label of own)if(!labels.includes(label))labels.push(label);
  const preferred=ids[String(record.primaryCategoryId)];if(own.includes(preferred)&&!primary.includes(preferred))primary.push(preferred);
  const item={site:site||'平台',url,labels:own};if(!evidence.some(e=>JSON.stringify(e)===JSON.stringify(item)))evidence.push(item);
 }
 const parents=new Set(DAMN_TAXONOMY_DATA.categories.filter(c=>c.parent&&labels.includes(c.label)).map(c=>c.parent)),specific=labels.filter(label=>!parents.has(label)),broad=new Set(['实用','科技','游戏机制','世界元素','食物与烹饪']);
 const chosen=primary.find(label=>specific.includes(label))||specific.find(label=>!broad.has(label))||specific[0];
 return {labels:chosen?[chosen,...specific.filter(label=>label!==chosen)]:[],evidence};
}

function damnCategoryInfo(m){
 const name=String(m.name||m.file||'').slice(0,2000),descriptions=damnClassificationDescriptions(m),description=descriptions[0]||'',fallback=descriptions.slice(1).join('\n');
 const platform=[...new Set((m.onlineResearch||[]).flatMap(r=>[...(r.platformCategory||[]),...(r.sources||[]).flatMap(s=>s.categories||[])]).map(x=>String(x).toLowerCase().trim()))],context=damnRelationshipContext(m);
 const platformInfo=damnPlatformClassification(m);
 const signature=JSON.stringify([name,descriptions,platformInfo,platform,context,m.webCategory,m.category,m.categoryEvidence,m.kind,m.resolutionStatus]);
 const cached=damnTaxonomyCache.get(m);if(cached?.signature===signature)return cached.info;
 const scores=DAMN_CATEGORY_RULES.map(c=>({c,local:c.rules.reduce((s,[w,p])=>s+w*(Number(p.test(name))+(p.test(description)?2:p.test(fallback)?1:0)),0)+(c.nameRules||[]).reduce((s,[w,p])=>s+(new RegExp(p,'i').test(name)?w:0),0),votes:platform.filter(t=>c.platform.includes(t)).length}));
 let category='其他 / 待识别',source='待识别';
 if(platformInfo.labels.length){category=platformInfo.labels[0];source='平台分类 · '+[...new Set(platformInfo.evidence.map(e=>e.site))].join(' / ');} else{
  const chosen=scores.reduce((a,b)=>b.local>a.local||b.local===a.local&&b.c.parent&&!a.c.parent?b:a);
  if(chosen.local){category=chosen.c.label;source='本地用途规则';}
 }
 if(category==='其他 / 待识别')for(const [value,origin] of [[m.webCategory,'已有平台分类'],[m.category,'已有分类映射']]){if(origin==='已有分类映射'&&/AI/i.test(m.categoryEvidence||''))continue;const label=damnNormalizeCategory(value);if(label!=='其他 / 待识别'){category=label;source=origin;break;}}
 if(category==='其他 / 待识别'&&context.ecosystem&&description){category='科技';source='本地生态线索 · 暂定用途';}
 const selected=DAMN_CATEGORY_RULES.find(c=>c.label===category),tags=[];
 for(const f of platformInfo.labels.length?[]:selected.features){if(tags.length>=3)break;if(f.re.test(name+' '+descriptions.join('\n'))&&!tags.includes(f.label))tags.push(f.label);}
 if(m.kind==='manifest'&&m.resolutionStatus==='candidate')source+=' · 候选待核对';
 const info={category,categories:platformInfo.labels.length?platformInfo.labels:[category],platformEvidence:platformInfo.evidence,tags,source,version:DAMN_TAXONOMY_DATA.version,reason:'',ecosystems:context.ecosystem?[{...context.ecosystem,label:'Create 生态'}]:[]};damnTaxonomyCache.set(m,{signature,info});return info;
}
function damnCategoryCounts(mods){const counts=Object.fromEntries(DAMN_CATEGORIES.map(c=>[c,0]));for(const m of mods)for(const label of damnCategoryInfo(m).categories)counts[label]++;return counts;}
function damnCategoryMatches(mod,category){const target=damnNormalizeCategory(category);return damnCategoryInfo(mod).categories.some(own=>own===target||DAMN_TAXONOMY_DATA.categories.find(c=>c.label===own)?.parent===target);}
function damnCategoryBranchCounts(mods){const counts=Object.fromEntries(DAMN_CATEGORIES.map(c=>[c,0]));for(const m of mods){const labels=new Set(damnCategoryInfo(m).categories);for(const label of [...labels]){const parent=DAMN_TAXONOMY_DATA.categories.find(c=>c.label===label)?.parent;if(parent)labels.add(parent);}for(const label of labels)counts[label]++;}return counts;}
function damnVisibleCategories(mods){const counts=damnCategoryBranchCounts(mods);return DAMN_TAXONOMY_DATA.categories.filter(c=>counts[c.label]>0);}
function damnFeatureCounts(mods){const counts={};for(const m of mods){const info=damnCategoryInfo(m);for(const tag of [...info.tags,...info.ecosystems.map(e=>e.label)])counts[tag]=(counts[tag]||0)+1;}return counts;}

function damnCleanPurpose(value){
 if(typeof value!=='string')return '';
 let text=value.replace(/\s+/g,' ').trim();if(!/[\u4e00-\u9fff]/.test(text))return '';
 const prefix=/^(?:(?:网页|页面|平台|官网|项目|资料|来源)(?:上)?(?:的)?(?:描述|介绍|说明|显示|称)(?:为|是|该模组|这个模组|：|:)?|根据(?:网页|页面|平台|官网|已取得的资料|资料)(?:描述|介绍|说明|显示)?[，,：:]?|该模组(?:主要)?(?:用于|可以)|这是一个)\s*/;
 for(let i=0;i<3;i++)text=text.replace(prefix,'').replace(/^[ ：:，,]+/,'');
 text=text.split(/(?:本地(?:文件)?(?:声明|要求)|(?:需要|要求)(?:安装|使用)?\s*(?:NeoForge|Forge|Fabric|Minecraft)|(?:兼容|支持|适用)(?:的)?(?:游戏)?版本[：:])/)[0].replace(/[ ，,；;]+$/,'');
 if(/完整移植|维护分叉|保留原内容|移植(?:版|分支)/.test(text)||/\d+(?:\.\d+){1,}/.test(text)||!text||/^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供|资料不足|无法确认)/i.test(text))return '';
 text=(text.match(/^[^。！？]*[。！？]?/)||[''])[0].trim();const han=(text.match(/[\u4e00-\u9fff]/g)||[]).length,latin=(text.match(/[A-Za-z]/g)||[]).length;return text&&han&&latin<=8*han+30&&text.length<=100?text+(/[。！？]$/.test(text)?'':'。'):'';
}
function damnLocalDescription(m){const text=m.originalDescription||m.description||'';return typeof text==='string'&&text.trim().length>=5&&!/^(文件没有提供|仅有下载清单|尚未读取|暂无|No description|清单未提供)/i.test(text)?text.trim():'';}
function damnNeedsPurpose(m){return ![m.aiPurpose,m.aiAnnotation?.purpose,m.aiAnnotation?.summary,m.descriptionZh,m.description,m.platformInfo?.description].some(value=>damnCleanPurpose(value));}
function damnPurposeEligible(m){return (m.onlineResearch||[]).some(r=>r.sources?.length)||!!damnLocalDescription(m);}
function damnPurpose(m){
 const candidate=m.kind==='manifest'&&m.resolutionStatus!=='matched';
 const ai=[m.aiPurpose,m.aiAnnotation?.purpose,m.aiAnnotation?.summary].map(damnCleanPurpose).find(Boolean);
 if(ai)return {text:ai,source:candidate?'AI 总结 · 候选待核对':m.aiPurposeBasis==='local'?'AI 总结 · 文件简介':'AI 总结',kind:'ai'};
 const translated=damnCleanPurpose(m.descriptionZh);
 if(translated)return {text:translated,source:candidate?'中文译文 · 候选待核对':'中文译文',kind:'translated'};
 const local=damnCleanPurpose(m.description);
 if(local)return {text:local,source:m.descriptionSource==='原有人工用途清单'?'原有用途说明':m.kind==='manifest'?'平台简介':'文件简介',kind:'original'};
 const platform=damnCleanPurpose(m.platformInfo?.description);
 if(platform)return {text:platform,source:candidate?'候选简介 · 待核对':'平台简介',kind:'original'};
 return {text:'中文用途待总结。',source:'待中文总结',kind:'pending'};
}
function damnFilterMods(mods,{search='',category='',feature='',status=''}={}){
 const terms=String(search).toLowerCase().trim().split(/\s+/).filter(Boolean);
 return mods.filter(m=>(!category||damnCategoryMatches(m,category))&&(!feature||damnCategoryInfo(m).tags.includes(feature)||damnCategoryInfo(m).ecosystems.some(e=>e.label===feature))&&(!status||(status==='manifest'?m.kind==='manifest':m.enabled===(status==='on')))&&terms.every(term=>[m.name,m.file,m.description,m.descriptionZh,m.aiPurpose,damnPurpose(m).text,damnCategoryInfo(m).category,...damnCategoryInfo(m).categories,...damnCategoryInfo(m).tags,...damnCategoryInfo(m).ecosystems.map(e=>e.label),...(m.components||[]).map(c=>c.id)].join(' ').toLowerCase().includes(term)));
}
if(typeof module!=='undefined'&&module.exports)module.exports={damnPlatformClassification,damnRelationshipContext,damnClassificationMaterial,damnClassificationInputStamp,damnClassificationEligible,damnCurrentClassification,damnHasAIClassification,damnPendingClassification,damnCategoryMatches,damnCategoryBranchCounts,DAMN_TAXONOMY_DATA,DAMN_CATEGORIES,DAMN_CATEGORY_GROUPS,damnNormalizeTags,damnFeatureCounts,damnVisibleCategories,damnCleanPurpose,damnNeedsPurpose,damnPurposeEligible,damnNormalizeCategory,damnCategoryInfo,damnCategoryCounts,damnPurpose,damnFilterMods};
