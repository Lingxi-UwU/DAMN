'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let token=$('meta[name="damn-token"]').content;
let sessionRefresh=null;
let damnAnalysisActive=false,analysisInitialization=null,analysisWatchdog=null,analysisCurrentView='overview';
function isAnalysisWorkspace(){return damnAnalysisActive;}

async function refreshLocalSession(){if(!sessionRefresh)sessionRefresh=(async()=>{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);try{const res=await fetch('/',{signal:controller.signal,cache:'no-store'}),html=await res.text(),match=html.match(/<meta name="damn-token" content="([A-Za-z0-9_-]{20,200})"/);if(match)token=match[1];return !!match;}finally{clearTimeout(timer);}})().finally(()=>{sessionRefresh=null;});return sessionRefresh;}
let report=null, selected=null, busy=false, aiBusy=false, pendingArchive=null, settingsState=null, firstRun=false, draftClearKey=false;
const aiAnswers=new Map();
let networkFocus=null,graphView=null,graphBase=null,graphCache=null,enrichment=null,persistTimer=null;
let networkRelationView='direct';
function effectiveCategory(m){return damnCategoryInfo(m).category;}
function persistReport(){clearTimeout(persistTimer);persistTimer=setTimeout(()=>{try{if(report)localStorage.setItem('damn-last-report-v2',JSON.stringify(report));}catch{}},250);}
function updateCategorySelection(){
 const active=$('#category').value;
 $('#usage-categories').querySelectorAll('[data-category]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.category===active)));
}
function updateCategories(){
 const old=$('#category').value,oldFeature=$('#feature').value,counts=damnCategoryBranchCounts(report.mods),total=report.mods.length,visibleCategories=damnVisibleCategories(report.mods);
 const focus=document.activeElement,focusedCategory=focus?.closest('#usage-categories')?focus.dataset.category:null;
 $('#category').innerHTML='<option value="">全部（'+total+'）</option>'+visibleCategories.map(c=>'<option value="'+esc(c.label)+'">'+(c.parent?'　↳ ':'')+esc(c.label)+'（'+counts[c.label]+'）</option>').join('');
 $('#category').value=old&&counts[damnNormalizeCategory(old)]?damnNormalizeCategory(old):'';
 const button=(category,count,description='',child=false)=>'<button type="button" class="usage-category'+(child?' usage-child':'')+'" data-category="'+esc(category)+'" title="'+esc(description)+'" aria-pressed="false"><span>'+esc(category||'全部')+'</span><strong>'+count+'</strong></button>';
 const parents=visibleCategories.filter(c=>!c.parent),families=parents.filter(c=>visibleCategories.some(child=>child.parent===c.label)),plain=parents.filter(c=>!families.includes(c));
 $('#usage-categories').innerHTML='<div class="usage-all">'+button('',total,'显示整包全部模组')+'</div>'+families.map(parent=>'<div class="usage-family">'+button(parent.label,counts[parent.label],parent.description)+'<div class="usage-children">'+visibleCategories.filter(c=>c.parent===parent.label).map(c=>button(c.label,counts[c.label],c.description,true)).join('')+'</div></div>').join('')+'<div class="usage-main">'+plain.map(c=>button(c.label,counts[c.label],c.description)).join('')+'</div>';
 const features=damnFeatureCounts(report.mods);
 $('#feature').innerHTML='<option value="">全部标签</option>'+Object.entries(features).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'zh-CN')).map(([label,count])=>'<option value="'+esc(label)+'">'+esc(label)+'（'+count+'）</option>').join('');
 $('#feature').value=oldFeature in features?oldFeature:'';
 updateCategorySelection();
 if(focusedCategory!==null)[...$('#usage-categories').querySelectorAll('[data-category]')].find(b=>b.dataset.category===focusedCategory)?.focus({preventScroll:true});
}
function categoryTagsHTML(m){
 const info=damnCategoryInfo(m);return info.categories.map(label=>'<span class="tag category-tag" title="'+esc(info.source)+'">'+esc(label)+'</span>').join('')+info.tags.map(tag=>'<span class="tag feature-tag">'+esc(tag)+'</span>').join('')+info.ecosystems.map(e=>'<span class="tag ecosystem-tag" title="'+esc(e.basis+'；生态归属与用途分类分开')+'">'+esc(e.label)+(e.confirmed?'':' · 待核对')+'</span>').join('')+(typeof identityLabelHTML==='function'?identityLabelHTML(m):'');
}
function reportWithTaxonomy(){return {...report,taxonomyVersion:DAMN_TAXONOMY_DATA.version,mods:report.mods.map(m=>({...m,classification:damnCategoryInfo(m)}))};}
function updateNetworkSelect(){const old=networkFocus||'';$('#network-select').innerHTML='<option value="">全部模组 · 全局网络</option>'+report.mods.map(m=>'<option value="'+esc(m.key)+'">'+esc(m.name)+'</option>').join('');$('#network-select').value=old;}
async function api(route,body,retrySession=true){
 const controller=new AbortController();
 const timeout=/\/api\/categories\//.test(route)?60000:/\/api\/(scan|ai|upload|archive-scan)/.test(route)?600000:/settings\/test/.test(route)?120000:/choose/.test(route)?180000:12000;
 const timer=setTimeout(()=>controller.abort(),timeout);
 try{
  const res=await fetch(route,{method:body===undefined?'GET':'POST',signal:controller.signal,headers:{'X-DAMN-Token':token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  if(res.status===403&&retrySession&&await refreshLocalSession())return await api(route,body,false);
  const data=await res.json();if(!res.ok){const error=Error(data.error||'请求未完成');error.status=res.status;error.code=data.code;throw error;}return data;
 }catch(e){if(e.name==='AbortError')throw Error('连接超时，将继续检查状态。');throw e;}finally{clearTimeout(timer);}
}
function notice(text,error=false){$('#notice').textContent=text;$('#notice').className=error?'error':'';}
function setBusy(value){busy=value;['#scan','#choose','#archive-pick'].forEach(s=>$(s).disabled=value);$('#scan').textContent=value?'正在扫描…':'开始扫描 ↗';}
function showView(view){
 if(!['overview','network','issues'].includes(view))view='overview';
 if(typeof analysisCurrentView!=='undefined')analysisCurrentView=view;
 document.body.classList.toggle('network-view',view==='network');
 document.body.classList.toggle('issues-view',view==='issues');
 $$('.view').forEach(el=>el.hidden=el.id!=='view-'+view);
 $$('.nav[data-view]').forEach(el=>{const active=el.dataset.view===view&&(typeof damnWorkspace==='undefined'||damnWorkspace==='analysis');el.classList.toggle('active',active);if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
 $('#current-view-label').textContent=({overview:'整合包总览',network:'依赖网络',issues:'静态检查'})[view]||'整合包总览';
 if(view==='network')renderGraph();
 if(typeof renderWorkspaceNavigation==='function')renderWorkspaceNavigation();
 
}
$$('.nav[data-view]').forEach(b=>b.addEventListener('click',()=>{if(typeof damnChooseWorkspace==='function')damnChooseWorkspace('analysis',b.dataset.view);else showView(b.dataset.view);}));
function mod(key){return report?.mods.find(m=>m.key===key);}
function short(text,n=26){return String(text).length>n?String(text).slice(0,n)+'…':String(text);}
function checkSummary(data){
 const issues=data.issues||[],reads=data.errors||[];
 return {total:issues.length+reads.length,details:issues.length+' 项检查提示 · '+reads.length+' 项读取提示',coverage:'版本范围待核对：'+(data.unchecked||0)+' 项'};
}
function loadReport(data){
 if(typeof damnSyncInterface==='function')damnSyncInterface(data,true);
 if(enrichment?.id&&report&&reportScope(report)!==reportScope(data))api('/api/enrich/cancel',{id:enrichment.id}).catch(()=>{});clearTimeout(enrichPollTimer);enrichEpoch++;enrichStarting=false;enrichment=null;aiAnswers.clear();networkFocus=null;graphCache=null;graphView=null;pendingArchive=null;report=data;if(typeof identityLoadReport==='function')identityLoadReport(data);rebuildWebEdges();selected=data.mods[0]?.key||null;resetClassification();$('#pack-name').textContent=data.pack;
 $('#pack-mode').textContent=data.mode==='snapshot'?'演示快照 · 2026.10.19 · 未重新扫描':data.archive?'压缩包分析 · '+data.archive.format+' · '+data.archive.name:'本地扫描 · '+new Date(data.created).toLocaleString();
 $('#stat-files-label').textContent=data.archive?.manifestOnly?'模组条目':'模组文件';
 $('#stat-enabled-label').textContent=data.archive?.manifestOnly?'已读取 JAR':'启用文件';
 $('#stat-files').textContent=data.fileCount??data.mods.length;
 $('#stat-components').textContent=data.mods.reduce((s,m)=>s+m.components.length,0)+' 个组件声明（含内置）';
 const enabled=data.mods.filter(m=>m.enabled).length;
 $('#stat-enabled').textContent=data.archive?.manifestOnly?data.archive.jarFiles:enabled;$('#stat-disabled').textContent=data.archive?.manifestOnly?data.archive.manifestOnly+' 项仅有下载清单':(data.mods.length-enabled)+' 个文件停用';
 $('#stat-edges').textContent=data.edges.length;
 const checks=checkSummary(data),snapshot=data.mode==='snapshot';
 $('#stat-issues').textContent=snapshot?'未检查':checks.total;
 $('#stat-unchecked').textContent=snapshot?'请扫描实际目录进行检查':checks.details;
 $('#stat-check-coverage').textContent=snapshot?'快照未运行本地检查':checks.coverage;
 $('#issue-badge').textContent=checks.total;$('#issue-badge').hidden=checks.total===0;
   $('#category').value='';updateCategories();
 $('#search').value='';$('#feature').value='';$('#status').value='';
 updateNetworkSelect();
 renderList();renderDetail();renderIssues();renderGraph();
 $('#pack-ai-answer').textContent='扫描后可直接分析，费用按你配置的 API 服务规则计算。';$('#pack-ai-answer').className='inline-answer muted';$('#pack-ai-usage').textContent='';if($('#pack-web-research'))$('#pack-web-research').remove();updateAIButtons();persistReport();renderEnrichment();maybeAutoEnrich();

}
function renderList(){
 if(!report)return;
 const rows=damnFilterMods(report.mods,{search:$('#search').value,category:$('#category').value,feature:$('#feature').value,status:$('#status').value});
 updateCategorySelection();$('#list-count').textContent=rows.length+' / '+report.mods.length;
 $('#mod-list').innerHTML=rows.map(m=>{
  const purpose=damnPurpose(m),category=damnCategoryInfo(m),status=m.kind==='manifest'?(m.resolutionStatus==='matched'?'已匹配 · 未读 JAR':m.resolutionStatus==='candidate'?'候选 · 未读 JAR':m.resolutionStatus==='failed'?'待重试':'仅清单'):m.enabled?'启用':'停用';
  return '<button type="button" class="mod-row '+(selected===m.key?'selected':'')+'" data-key="'+esc(m.key)+'" aria-pressed="'+(selected===m.key)+'"><span class="mod-symbol" aria-hidden="true">D</span><span class="mod-text"><span class="mod-name">'+esc(m.name)+'</span><span class="mod-meta">'+esc([m.loader,m.version].filter(Boolean).join(' · '))+'</span><span class="mod-purpose '+purpose.kind+'" title="'+esc(purpose.text)+'"><span class="purpose-label">用来做什么：</span>'+esc(purpose.text)+'</span><span class="mod-tags">'+categoryTagsHTML(m)+'<span class="tag purpose-source '+purpose.kind+'">'+esc(purpose.source)+'</span></span></span><span class="badge '+(m.enabled===true?'':'off')+'">'+status+'</span></button>';
 }).join('')||'<div class="empty">没有匹配的模组。可以更换分类，或点击“重置”。</div>';
}
$('#mod-list').addEventListener('click',e=>{const b=e.target.closest('[data-key]');if(b)select(b.dataset.key);});
function applyFilters(){if(!report)return;const visible=damnFilterMods(report.mods,{search:$('#search').value,category:$('#category').value,feature:$('#feature').value,status:$('#status').value});if(!visible.some(m=>m.key===selected))select(visible[0]?.key||null);else renderList();}
['#search','#category','#feature','#status'].forEach(s=>$(s).addEventListener(s==='#search'?'input':'change',applyFilters));
$('#usage-categories').addEventListener('click',event=>{const button=event.target.closest('[data-category]');if(!button||!report)return;$('#category').value=button.dataset.category;applyFilters();});
$('#stat-check-open').addEventListener('click',()=>showView('issues'));
$('#filters-reset').addEventListener('click',()=>{$('#search').value='';$('#category').value='';$('#feature').value='';$('#status').value='';applyFilters();});
function select(key){selected=key;if(networkFocus)networkFocus=key;updateNetworkSelect();renderList();renderDetail();renderGraph();}
function required(m){return m.dependencies.filter(d=>d.type==='required');}
function getImpact(key){
 const affected=new Set([key]);let size;
 do{size=affected.size;report.edges.forEach(e=>{if(affected.has(e.to))affected.add(e.from);});}while(size!==affected.size);
 const ids=new Set(report.mods.filter(m=>affected.has(m.key)).flatMap(m=>m.components.map(c=>c.id)));
 return {mods:report.mods.filter(m=>affected.has(m.key)&&m.key!==key),references:report.references.filter(r=>ids.has(r.id))};
}
function detailLocalCheckGroups(m,data=report){
 const scope=data?.mode==='snapshot'?'这是历史快照，未执行本次本地前置检查。':m.kind==='manifest'?'尚未读取实际 JAR，无法判断本地前置是否缺失。':m.enabled===false?'当前文件已停用，未执行本次前置检查。':m.active===false?'当前文件不适用于所选环境，未执行本次前置检查。':data?.archive?.manifestOnly?'整合包仍有仅下载清单项，本地前置完整性待核对。':m.dependenciesKnown===false?'本地 JAR 的依赖声明尚未完整读取，前置状态待核对。':'';
 const unique=new Map();
 for(const issue of data?.issues||[]){
  if(issue?.mod!==m.key)continue;
  const originalKind=String(issue.kind||'other'),text=String(issue.text||'检查提示'),key=JSON.stringify([originalKind,text]);
  let row=unique.get(key);if(!row){row={kind:scope&&originalKind==='missing'?'unresolved':originalKind,originalKind,text,level:issue.level||'warning',sources:[]};unique.set(key,row);}
  const sources=[...(Array.isArray(issue.source)?issue.source:[issue.source]),...(Array.isArray(issue.sources)?issue.sources:[])];
  for(const source of sources){if(source!==undefined&&source!==null&&String(source)&&!row.sources.includes(String(source)))row.sources.push(String(source));}
 }
 const rows=[...unique.values()];return {scope,missing:rows.filter(row=>row.kind==='missing'),unresolved:rows.filter(row=>row.kind==='unresolved'),other:rows.filter(row=>!['missing','unresolved'].includes(row.kind))};
}
function renderLocalDependencyChecks(m){
 const groups=detailLocalCheckGroups(m),kindLabels={version:'版本提示',conflict:'冲突提示',loader:'加载器提示',environment:'环境提示',duplicate:'重复提示',other:'检查提示'};
 const group=(kind,title,rows,note)=>!rows.length?'':'<section class="local-check-group local-check-'+kind+'"><div class="local-check-heading"><h4>'+title+'</h4><strong aria-label="'+title+'数量">'+rows.length+'</strong></div>'+(note?'<p class="local-check-note">'+esc(note)+'</p>':'')+'<div class="local-check-scroll" tabindex="0" role="list" aria-label="'+title+'列表">'+rows.map(row=>'<article class="local-check-item" role="listitem">'+(kind==='other'?'<span class="local-check-kind">'+esc(kindLabels[row.kind]||'检查提示')+'</span>':'')+'<p class="local-check-text">'+esc(row.text)+'</p>'+(row.sources.length?'<div class="local-check-sources"><span>来源</span><ul>'+row.sources.map(source=>'<li>'+esc(source)+'</li>').join('')+'</ul></div>':'')+'</article>').join('')+'</div></section>';
 let html='<section class="local-dependency-checks" aria-label="当前模组的本地检查结果">';
 if(groups.scope)html+='<p class="local-check-coverage">'+esc(groups.scope)+'</p>';
 html+=group('missing','缺失前置',groups.missing,'本地检查已发现以下必需前置缺失。');
 html+=group('unresolved','前置待核对',groups.unresolved,'以下项目尚不能判定为缺失，请结合实际 JAR 与整合包清单核对。');
 html+=group('other','其他检查提示',groups.other,'');
 if(!groups.scope&&!groups.missing.length&&!groups.unresolved.length)html+='<p class="local-check-empty">本次本地检查未报告缺失前置；不代表所有版本范围都已确认。</p>';
 return html+'</section>';
}
function renderOnlineDependencies(m){
 const rows=onlineRelations(m,report.mods),unique=new Map(rows.map((r,i)=>[i,r]));
 const labels={required:'必需前置',optional:'可选前置',incompatible:'不兼容',related:'关联 · 待确认',used_by:'反向依赖',embedded:'内置组件',include:'包含组件',tool:'工具'};
 let html='<section class="online-dependencies"><div class="section-label">平台 / AI 查到的依赖'+(unique.size?' <span>'+unique.size+'</span>':'')+'</div>';
 if(!unique.size)return html+'<p class="small muted">'+(m.enrichmentComplete?'本次平台资料未确认额外关系；本地检查结果见上方。':'尚未补充联网依赖关系；本地检查结果见上方。')+'</p></section>';
 html+='<div class="dependency-cards">';
 for(const r of unique.values()){
  const name=r.target,url=safeWebURL(r.source);
  html+='<div class="dependency-card"><strong>'+esc(name)+'</strong><span>'+esc(labels[r.kind]||r.kind)+'</span><small>'+esc(r.version?'适用版本：'+r.version:r.provenance||'平台版本关联，需核对具体版本')+'</small>'+(url?'<a href="'+esc(url)+'" target="_blank" rel="noreferrer">查看来源 ↗</a>':'')+'</div>';
 }
 return html+'</div><p class="small muted">联网依赖与文件声明分开显示；仅凭介绍推测的关联会标为待确认。</p></section>';
}

function renderDetail(){
 const m=mod(selected);if(!m){$('#detail').innerHTML='<div class="empty">没有可显示的模组。</div>';return;}
 const sourceDescription=m.platformInfo?.description||m.description||'';
 const originalEnglish=/[a-zA-Z]{3}/.test(sourceDescription)&&!/[\u4e00-\u9fff]/.test(sourceDescription);
 const incoming=[...new Set(report.edges.filter(e=>e.to===m.key).map(e=>e.from))];
 const imp=getImpact(m.key);
 const sourceText={file:m.file,originalName:m.originalName,platformInfo:m.platformInfo,components:m.components.map(c=>({id:c.id,version:c.version,source:c.source,nested:c.nested})),dependencies:m.dependencies,sha256:m.sha256||'示例快照未提供文件校验值',descriptionSource:m.descriptionSource||'模组元数据中的原始说明',categoryEvidence:m.categoryEvidence,classification:damnCategoryInfo(m),manifest:m.manifest,dependenciesKnown:m.dependenciesKnown,archivePath:m.archivePath};
 $('#detail').innerHTML='<div class="detail-heading"><span class="mod-symbol" aria-hidden="true">D</span><div><h3>'+esc(m.name)+'</h3><p>'+esc(m.loader+' · '+m.version)+'</p></div></div><p class="detail-description">'+esc(damnPurpose(m).text)+'</p>'+(m.platformInfo?'<p class="small muted">联网匹配：'+esc(m.platformInfo.match||'候选资料')+' · 文件：'+esc(m.file)+'</p>':'')+'<div class="detail-tags">'+categoryTagsHTML(m)+'<span class="tag">'+esc(damnPurpose(m).source)+'</span></div><p class="small muted">分类依据：'+esc(damnCategoryInfo(m).source)+'</p>'+(!damnPlatformClassification(m).labels.length&&m.platformCategoryCheck?.notes?.length?'<p class="small muted category-notes">'+esc(m.platformCategoryCheck.notes.slice(0,2).map(note=>String(note).replace(/可配置 CurseForge API Key[^。]*。?/g,'CurseForge 服务暂不可用，平台分类保留待识别。')).join(' '))+'</p>':'')+(damnCategoryInfo(m).reason?'<p class="small classification-reason">'+esc(damnCategoryInfo(m).reason)+'</p>':'')+renderLocalDependencyChecks(m)+'<div class="section-label">直接依赖它的启用文件 <span>'+incoming.length+'</span></div><div class="relations">'+(incoming.map(k=>'<button class="relation" data-jump="'+esc(k)+'">'+esc(short(mod(k)?.name||k,22))+'</button>').join('')||'<span class="muted small">未发现文件间的必需依赖连线</span>')+'</div><div class="impact-box"><strong>改动影响预览</strong><p>沿必需依赖追溯，关联 '+imp.mods.length+' 个启用文件；相关文本引用 '+imp.references.length+' 处。</p>'+(imp.mods.length?'<p>'+esc(imp.mods.slice(0,8).map(m=>m.name).join('、'))+(imp.mods.length>8?'…':'')+'</p>':'')+'<p>仅供规划；未检查存档与运行时行为。</p></div>'+'<details class="source-details"><summary>文件、组件与判断依据</summary><pre>'+esc(JSON.stringify(sourceText,null,2))+'</pre></details><button id="detail-ai" class="secondary detail-action">用自己的 AI 进一步分析 ↗</button>';
 if(originalEnglish)$('#detail .detail-description').insertAdjacentHTML('afterend','<details class="original-description"><summary>查看英文原文</summary><p>'+esc(sourceDescription)+'</p></details>');
 $('#detail .relations').insertAdjacentHTML('afterend',renderOnlineDependencies(m));
 if(report.archive?.manifestOnly&&m.kind!=='manifest')$('#detail .impact-box').insertAdjacentHTML('beforeend','<p>下载清单项的依赖尚未读取，当前影响范围可能不完整。</p>');
 if(m.kind==='manifest')$('#detail .impact-box').textContent=m.onlineResearch?'已取得平台资料，可在依赖网络查看虚线关联；尚未读取 JAR，文件内依赖与删除影响仍待确认。':'尚未读取实际 JAR，联网补全后可查看平台关联；文件内依赖与改动影响仍待确认。';
 const prior=aiAnswers.get(m.key);$('#detail').insertAdjacentHTML('beforeend','<div class="detail-ai-caption">使用设置中的服务；AI 解释与文件依据分开显示。</div><div id="detail-ai-answer" class="inline-answer'+(prior?' ai-result':'')+'">'+esc(prior?.answer||'')+'</div><div id="detail-ai-usage" class="small muted">'+esc(prior?.usageText||'')+'</div><details id="detail-ai-preview" class="evidence-preview"><summary>查看会发送给 AI 的证据摘要</summary><pre id="detail-ai-evidence"></pre></details>');
 if(prior?.research)$('#detail-ai-usage').insertAdjacentHTML('afterend',renderResearch(prior.research,prior.annotation,prior.reconciliation,prior.aiSearch,m));else if(m.onlineResearch)$('#detail-ai-usage').insertAdjacentHTML('afterend',renderResearch(m.onlineResearch,m.aiAnnotation,m.reconciliation,m.aiSearch,m));
 $('#detail-ai').textContent='AI 解读这个模组 ↗';$('#detail-ai').disabled=aiBusy;
 $('#detail-ai').addEventListener('click',()=>askAI('selected'));
 $('#detail-ai-preview').addEventListener('toggle',e=>{if(e.target.open)$('#detail-ai-evidence').textContent=buildContext('selected');});
 $('#detail').querySelectorAll('[data-jump]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.jump)));
}
function renderNetworkDependencyTree(current,edges){
 const tree=buildDependencyTree(report.mods,edges,current.key);
 const basis=edge=>edge?.web?edge.origin==='platform'?'平台版本声明':edge.origin==='ai'?'AI 补充 · 待核对':'网页资料 · 待核对':'文件声明';
 const row=node=>'<span class="network-tree-name">'+esc(node.name)+'</span><small>'+esc(basis(node.edge))+'</small>'+(node.cycle?'<span class="network-tree-flag">循环依赖 · 已停止展开</span>':node.shared?'<span class="network-tree-flag">共享前置 · 已在其他分支展开</span>':'')+(node.truncated?'<span class="network-tree-flag">'+(node.truncated==='depth'?'链条较深，后续未展开':'条目较多，部分分支未展开')+'</span>':'');
 const item=node=>'<li>'+(node.children.length?'<details class="network-tree-branch"><summary>'+row(node)+'</summary><div class="network-tree-children"><button type="button" class="quiet network-tree-locate" data-network-jump="'+esc(node.key)+'">以此模组为中心 ↗</button><ul>'+node.children.map(item).join('')+'</ul></div></details>':'<button type="button" class="network-tree-leaf" data-network-jump="'+esc(node.key)+'">'+row(node)+'</button>')+'</li>';
 return '<section class="network-tree"><h4>必需前置链</h4><p class="network-relation-note">点击分支逐层展开；仅追溯必需关系，连线不代表版本已经满足。</p>'+(tree.root?.children.length?'<ul>'+tree.root.children.map(item).join('')+'</ul>':'<p class="network-relation-empty">尚未发现可展开的包内必需前置；缺失或未匹配的前置请查看静态检查。</p>')+(tree.truncated?'<p class="network-tree-limit">为保持页面流畅，深链或大树分段显示；可点击“以此模组为中心”继续查看。</p>':'')+'</section>';
}
function updateNetworkSelection(){
 if(!report?.mods.length)return;
 const current=mod(selected)||mod(networkFocus)||report.mods[0],allEdges=networkEdges(report.mods,report.edges,report.webEdges||[]),kind=$('#network-kind').value,edges=filterNetworkRelations(allEdges,kind),groups=networkRelationGroups(report.mods,edges,current.key);
 const classes={prerequisites:'role-prerequisite',dependents:'role-dependent',ecosystem:'role-ecosystem',other:'role-other'};
 $('#network-graph').querySelectorAll('[data-node]').forEach(el=>{el.classList.toggle('selected',el.dataset.node===current.key);for(const [group,cls] of Object.entries(classes))el.classList.toggle(cls,groups[group].some(r=>r.key===el.dataset.node));});
 $('#network-graph').querySelectorAll('.graph-links line').forEach(el=>el.classList.toggle('edge-active',el.dataset.from===current.key||el.dataset.to===current.key));
 const section=(key,title,note,empty)=>{
  const rows=groups[key];if(!rows.length&&!empty)return '';
  return '<section class="network-relation-group '+key+'"><h4>'+title+' <strong>'+rows.length+'</strong></h4><p class="network-relation-note">'+esc(note)+'</p>'+(rows.length?'<ul>'+rows.map(r=>'<li><button type="button" class="network-relation-item" data-network-jump="'+esc(r.key)+'" aria-label="查看 '+esc(r.name)+' 的网络"><span class="network-relation-name">'+esc(r.name)+'</span><span class="network-relation-kind">'+esc(r.label)+'</span><small>'+esc(r.basis)+'</small></button></li>').join('')+'</ul>':'<p class="network-relation-empty">'+esc(empty)+'</p>')+'</section>';
 };
 const treeContent=['all','required'].includes(kind)?renderNetworkDependencyTree(current,allEdges):'<p class="network-relation-empty">前置链仅展示必需关系。<button type="button" class="quiet" data-network-reset-kind>切换到必需前置</button></p>';
 const directContent=Object.values(groups).some(rows=>rows.length)?section('prerequisites','它需要的前置','当前模组 → 下列模组')+section('dependents','以它为前置的模组','下列模组 → 当前模组')+section('ecosystem','生态线索 · 待核对','生态归属不能当作必需前置。')+section('other','其他关联','相关、内置与不兼容关系单独显示。'):'<div class="network-relations-empty"><h4>当前筛选暂无包内关系</h4><p>没有已知连线不等于没有前置。缺失或未匹配的前置，请查看静态检查。</p></div>';
 $('#network-relations').innerHTML='<div class="network-current"><span class="network-current-label">当前选中模组</span><h3>'+esc(current.name)+'</h3><p>使用者 → 前置 · 按当前类型筛选</p></div><div class="network-view-switch" role="group" aria-label="关系查看方式"><button type="button" data-network-view="direct" aria-pressed="'+(networkRelationView==='direct')+'">直接关系</button><button type="button" data-network-view="tree" aria-pressed="'+(networkRelationView==='tree')+'">前置链</button></div><div class="network-relation-scroll" tabindex="0" aria-label="当前模组的前置与被依赖列表">'+(networkRelationView==='tree'?treeContent:directContent)+'</div>';
 $('#network-relations').querySelectorAll('[data-network-jump]').forEach(button=>button.addEventListener('click',()=>focusNetwork(button.dataset.networkJump)));
 $('#network-relations').querySelectorAll('[data-network-view]').forEach(button=>button.addEventListener('click',()=>{networkRelationView=button.dataset.networkView;updateNetworkSelection();}));
 $('#network-relations').querySelectorAll('[data-network-reset-kind]').forEach(button=>button.addEventListener('click',()=>{$('#network-kind').value='required';renderGraph(true);}));
}

function renderGraph(reset=false){
 if(!report?.mods.length){graphView=null;graphBase=null;$('#network-graph').innerHTML='<div class="empty">导入整合包后查看模组网络。</div>';$('#network-relations').innerHTML='<div class="empty">选择一个模组查看前置和被依赖关系。</div>';$('#network-info').textContent='';return;}
 const kind=$('#network-kind').value,kindLabel=({required:'必需前置',optional:'可选前置',incompatible:'不兼容关系'})[kind]||'关系';
 let edges=filterNetworkRelations(networkEdges(report.mods,report.edges,report.webEdges||[]),kind),nodes=report.mods;
 if(networkFocus){
  const keys=new Set([networkFocus]);edges.forEach(e=>{if(e.from===networkFocus)keys.add(e.to);if(e.to===networkFocus)keys.add(e.from);});
  nodes=nodes.filter(m=>keys.has(m.key));edges=edges.filter(e=>keys.has(e.from)&&keys.has(e.to));
 }
 const filtered=filterNetworkNodes(nodes,edges,$('#network-show-isolated').checked);nodes=filtered.nodes;edges=filtered.edges;
 if(!nodes.length){
  graphView=null;graphBase=null;
  $('#network-graph').innerHTML='<div class="empty network-empty"><div><h3>当前范围暂无已知'+esc(kindLabel)+'。</h3><p>可切换关系类型，或开启“显示未连线模组”。</p><small>缺失的前置不会形成包内连线，可在静态检查中查看。</small></div></div>';
  $('#network-info').textContent='已隐藏 '+filtered.hidden+' 个暂无已知连线的模组；未连线不代表已确认没有前置。';
  $('#network-all').classList.toggle('active',!networkFocus);$('#network-select').value=networkFocus||'';updateNetworkSelection();return;
 }
 const signature=String(networkFocus)+'|'+nodes.map(m=>m.key+':'+m.name).join('|')+'|'+edges.map(e=>e.from+':'+e.to+':'+e.kind+':'+e.web).join('|');
 if(graphCache?.signature!==signature){graphCache={signature,layout:buildNetworkLayout(nodes,edges)};reset=true;}
 const layout=graphCache.layout,by=new Map(layout.nodes.map(n=>[n.key,n]));
 graphBase={x:0,y:0,width:layout.width,height:layout.height};if(reset||!graphView)graphView={...graphBase};
 let svg='<svg class="'+(nodes.length>60?'dense-network':'')+'" role="group" aria-label="'+(networkFocus?'单个模组依赖网络':'全部模组依赖网络')+'" viewBox="'+[graphView.x,graphView.y,graphView.width,graphView.height].join(' ')+'"><defs><marker id="net-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#8d9e79"/></marker></defs><g class="graph-links">';
 for(const e of edges){const a=by.get(e.from),b=by.get(e.to),dx=b.x-a.x,dy=b.y-a.y,t=Math.min((NETWORK_CARD.width/2+2)/Math.max(.001,Math.abs(dx)),(NETWORK_CARD.height/2+3)/Math.max(.001,Math.abs(dy)));svg+='<line data-from="'+esc(e.from)+'" data-to="'+esc(e.to)+'" x1="'+a.x+'" y1="'+a.y+'" x2="'+(b.x-dx*t)+'" y2="'+(b.y-dy*t)+'" stroke="'+(e.kind==='ecosystem'?'#88a0a1':e.web?'#b7ae86':'#8fab71')+'" stroke-width="1.5"'+(e.web?' stroke-dasharray="'+(e.kind==='ecosystem'?'2 5':'5 4')+'"':'')+(e.kind==='ecosystem'?'':' marker-end="url(#net-arrow)"')+'><title>'+esc((e.kind==='ecosystem'?'生态线索 · 待核对':e.web?'平台 / AI 关联':'文件声明')+' · '+(e.id||e.kind)+' · '+(e.provenance||''))+'</title></line>';}
 svg+='</g><g class="graph-nodes">';
 for(const p of layout.nodes){const m=mod(p.key);svg+='<g class="graph-node'+(p.key===selected?' selected':'')+(p.degree?'':' isolated')+'" data-node="'+esc(p.key)+'" tabindex="0" role="button" aria-label="'+esc(m.name)+'"><rect x="'+(p.x-NETWORK_CARD.width/2)+'" y="'+(p.y-NETWORK_CARD.height/2)+'" width="'+NETWORK_CARD.width+'" height="'+NETWORK_CARD.height+'" rx="9" fill="'+(m.kind==='manifest'?'#faf9f1':'#f5f9ed')+'" stroke="#c9d5b9"/><text x="'+p.x+'" y="'+(p.y+4)+'" text-anchor="middle" fill="#4c613d">'+esc(short(m.name,19))+'</text><title>'+esc(m.name+' · '+effectiveCategory(m)+(p.degree?'':' · 暂无已知连线'))+'</title></g>';}
 $('#network-graph').innerHTML=svg+'</g></svg>';updateNetworkSelection();
 $('#network-info').textContent=(report.mode==='snapshot'?'历史示例 · ':'')+(networkFocus?'单模组网络：'+mod(networkFocus)?.name:'全局网络')+(kind!=='all'?' · 仅'+kindLabel:'')+' · '+nodes.length+' 个模组 · '+edges.length+' 条关系（'+edges.filter(e=>e.web&&e.kind!=='ecosystem').length+' 条联网关联，'+edges.filter(e=>e.kind==='ecosystem').length+' 条生态线索）。'+(filtered.hidden?'已隐藏 '+filtered.hidden+' 个未连线模组。':'')+'滚轮缩放，拖动平移；双击节点进入局部网络。';
 $('#network-all').classList.toggle('active',!networkFocus);$('#network-select').value=networkFocus||'';
}
function setGraphView(){const svg=$('#network-graph svg');if(svg&&graphView)svg.setAttribute('viewBox',[graphView.x,graphView.y,graphView.width,graphView.height].join(' '));}
function zoomGraph(factor,rx=.5,ry=.5){
 if(!graphView||!graphBase)return;const width=Math.max(160,Math.min(graphBase.width*4,graphView.width*factor)),ratio=width/graphView.width;
 graphView={x:graphView.x+graphView.width*rx*(1-ratio),y:graphView.y+graphView.height*ry*(1-ratio),width,height:graphView.height*ratio};setGraphView();
}
function focusNetwork(key){networkFocus=key||null;if(key)selected=key;graphView=null;updateNetworkSelect();renderList();renderDetail();renderGraph(true);}
$('#network-select').addEventListener('change',e=>focusNetwork(e.target.value));
$('#network-kind').addEventListener('change',()=>renderGraph(true));
$('#network-all').addEventListener('click',()=>focusNetwork(null));
$('#network-zoom-in').addEventListener('click',()=>zoomGraph(.75));
$('#network-zoom-out').addEventListener('click',()=>zoomGraph(1.3));
$('#network-fit').addEventListener('click',()=>{if(!graphBase)return;graphView={...graphBase};setGraphView();});
let graphDrag=null;
$('#network-graph').addEventListener('wheel',e=>{if(!graphView)return;e.preventDefault();const rect=$('#network-graph').getBoundingClientRect();zoomGraph(e.deltaY>0?1.15:1/1.15,(e.clientX-rect.left)/rect.width,(e.clientY-rect.top)/rect.height);},{passive:false});
$('#network-graph').addEventListener('pointerdown',e=>{if(!graphView||e.button!==0)return;const rect=$('#network-graph').getBoundingClientRect();graphDrag={x:e.clientX,y:e.clientY,view:{...graphView},rect,moved:false};});
$('#network-graph').addEventListener('pointermove',e=>{if(!graphDrag)return;const dx=e.clientX-graphDrag.x,dy=e.clientY-graphDrag.y;if(Math.abs(dx)+Math.abs(dy)>4){graphDrag.moved=true;$('#network-graph').setPointerCapture(e.pointerId);}graphView={...graphDrag.view,x:graphDrag.view.x-dx*graphDrag.view.width/graphDrag.rect.width,y:graphDrag.view.y-dy*graphDrag.view.height/graphDrag.rect.height};setGraphView();});
$('#network-graph').addEventListener('pointerup',e=>{const moved=graphDrag?.moved;graphDrag=null;if(moved)return;const n=e.target.closest('[data-node]');if(n){selected=n.dataset.node;renderList();renderDetail();updateNetworkSelection();}});
$('#network-graph').addEventListener('pointercancel',()=>{graphDrag=null;});
$('#network-graph').addEventListener('dblclick',e=>{const n=e.target.closest('[data-node]');if(n){e.preventDefault();focusNetwork(n.dataset.node);}});
$('#network-graph').addEventListener('keydown',e=>{const n=e.target.closest('[data-node]');if(n&&e.key==='Enter'){e.preventDefault();focusNetwork(n.dataset.node);}});
function renderIssues(){
 $('#issues-count').textContent=report.issues.length+report.errors.length+(report.mode==='snapshot'?1:0);
 $('#issues-list').scrollTop=0;
 $('#issues-list').innerHTML=(report.mode==='snapshot'?'<div class="issue-item warning">这是原有清单的演示快照，未运行完整检查。请扫描本地目录获得当前结果。</div>':'')+report.issues.map(i=>'<div class="issue-item '+esc(i.level)+'"><strong>'+esc(i.text)+'</strong><small>'+esc(mod(i.mod)?.name||i.mod)+' · '+esc(i.source)+'</small></div>').join('')+report.errors.map(e=>'<div class="issue-item warning">'+esc(e.message)+'<small>'+esc(e.source)+'</small></div>').join('')+(!report.issues.length&&!report.errors.length&&report.mode!=='snapshot'?'<div class="empty">未发现已支持规则内的问题。<br>仍需核对分析边界及待确认版本。</div>':'');
 $('#limits-list').innerHTML=report.limits.map(s=>'<li>'+esc(s)+'</li>').join('');
}
function acceptArchiveResult(data,source){
 if(data.needsRoot){pendingArchive={...source,uploadId:data.uploadId};$('#archive-root').innerHTML=data.roots.map(r=>'<option value="'+esc(r)+'">'+esc(r||'压缩包根目录')+'</option>').join('');$('#archive-root-dialog').showModal();notice('发现多个实例，请选择一个继续。');return;}
 loadReport(data);showView('overview');
 notice(data.archive?'已打开 '+data.archive.name+'，读取 '+data.archive.jarFiles+' 个 JAR'+(data.archive.manifestOnly?'；'+data.archive.manifestOnly+' 项仅有下载清单':'')+'。':'扫描完成。共读取 '+data.mods.length+' 个模组文件；整合包文件未被修改。');
}
$('#scan').addEventListener('click',async()=>{
 if(busy)return;const value=$('#pack-path').value.trim();if(!value){notice('选择目录、填写路径，或直接拖入压缩包。',true);return;}
 const side=$('#side').value;setBusy(true);notice('正在读取文件、核对依赖并查找文本引用…');
 try{acceptArchiveResult(await api('/api/scan',{path:value,side}),{localPath:value,side});}catch(e){notice(e.message,true);}finally{setBusy(false);}
});
function uploadFile(file,side){return new Promise((resolve,reject)=>{
 const xhr=new XMLHttpRequest();xhr.open('POST','/api/upload');xhr.setRequestHeader('X-DAMN-Token',token);xhr.setRequestHeader('X-DAMN-FileName',encodeURIComponent(file.name));xhr.setRequestHeader('X-DAMN-Side',side);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.timeout=600000;
 xhr.upload.onprogress=e=>{if(e.lengthComputable)notice('正在把文件交给本机分析器：'+Math.round(e.loaded/e.total*100)+'%（不会上传到外部服务）');};
 xhr.upload.onload=()=>notice('文件已交给本机分析器，正在识别整合包结构并读取内容…');
 xhr.onload=()=>{try{const data=JSON.parse(xhr.responseText);if(xhr.status>=200&&xhr.status<300)resolve(data);else reject(Error(data.error||'文件导入失败。'));}catch(e){reject(Error('文件导入失败，服务没有返回有效结果。'));}};
 xhr.onerror=()=>reject(Error('与本机分析器的连接中断，请确认 DAMN 仍在运行。'));xhr.ontimeout=()=>reject(Error('导入超时，请改用已解压目录路径。'));xhr.send(file);
});}
async function openArchiveFile(file){
 if(busy){notice('正在分析上一个文件，请稍等。',true);return;}
 if(!file)return;if(!/\.(zip|mrpack)$/i.test(file.name)){notice('当前支持 ZIP、MRPACK 文件；RAR / 7z 暂不支持。',true);return;}
 if(file.size>2*1024**3){notice('单个文件上限为 2 GiB；更大的包请使用目录路径。',true);return;}
 const side=$('#side').value;setBusy(true);notice('正在打开 '+file.name+'…');
 try{acceptArchiveResult(await uploadFile(file,side),{side});}catch(e){notice(e.message,true);}finally{setBusy(false);$('#archive-file').value='';}
}
$('#archive-pick').addEventListener('click',e=>{e.stopPropagation();if(!busy)$('#archive-file').click();});
$('#dropzone').addEventListener('click',e=>{if(!busy&&e.target.id!=='archive-file')$('#archive-file').click();});
$('#dropzone').addEventListener('keydown',e=>{if(e.target.id==='dropzone'&&['Enter',' '].includes(e.key)){e.preventDefault();if(!busy)$('#archive-file').click();}});
$('#archive-file').addEventListener('change',e=>openArchiveFile(e.target.files[0]));
window.addEventListener('dragover',e=>{if(!damnAnalysisActive)return;if([...e.dataTransfer.types].includes('Files')){e.preventDefault();$('#dropzone').classList.add('dragging');}});
window.addEventListener('dragleave',e=>{if(!damnAnalysisActive)return;if(!e.relatedTarget)$('#dropzone').classList.remove('dragging');});
window.addEventListener('drop',e=>{e.preventDefault();if(!damnAnalysisActive)return;$('#dropzone').classList.remove('dragging');if(e.dataTransfer.files.length!==1){notice('请一次拖入一个整合包文件。',true);return;}const item=e.dataTransfer.items[0];if(item?.webkitGetAsEntry?.()?.isDirectory){notice('文件夹请通过“浏览”或路径选择打开。',true);return;}openArchiveFile(e.dataTransfer.files[0]);});
$('#root-close').addEventListener('click',()=>{$('#archive-root-dialog').close();pendingArchive=null;notice('已取消实例选择。');});
$('#archive-root-dialog').addEventListener('cancel',()=>{pendingArchive=null;});
$('#root-confirm').addEventListener('click',async()=>{
 if(!pendingArchive||busy)return;const source=pendingArchive,archiveRoot=$('#archive-root').value;$('#archive-root-dialog').close();setBusy(true);notice('正在分析选中的实例…');
 try{const data=source.uploadId?await api('/api/archive-scan',{uploadId:source.uploadId,archiveRoot}):await api('/api/scan',{path:source.localPath,side:source.side,archiveRoot});acceptArchiveResult(data,source);}catch(e){notice(e.message,true);}finally{setBusy(false);}
});
$('#choose').addEventListener('click',async()=>{setBusy(true);notice('请在目录选择器中选择整合包。');try{const data=await api('/api/choose',{});if(data.path){$('#pack-path').value=data.path;notice('目录已选择，点击“开始扫描”。');}else notice('已取消选择。');}catch(e){notice(e.message,true);}finally{setBusy(false);}});
function download(content,name,type){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);}
$('#export-json').addEventListener('click',()=>{if(!report){notice('请先扫描或载入示例。',true);return;}download(JSON.stringify(reportWithTaxonomy(),null,2),'DAMN-report.json','application/json');});
$('#export-html').addEventListener('click',()=>{
 if(!report){notice('请先扫描或载入示例。',true);return;}
 const content='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DAMN 分析报告</title><style>body{font:15px/1.7 system-ui,sans-serif;max-width:1200px;padding:30px;margin:auto;color:#253b29;background:#f8faf5}table{border-collapse:collapse;width:100%;background:white}td,th{padding:13px;border:1px solid #dce5d3;text-align:left;vertical-align:top}small{color:#7b8972}p{white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:30px}</style><h1>DAMN · 模组依赖网络分析器</h1><h2>'+esc(report.pack)+'</h2><p>'+esc(report.mode==='snapshot'?'演示快照，未重新扫描':new Date(report.created).toLocaleString())+'</p><ul>'+report.limits.map(s=>'<li>'+esc(s)+'</li>').join('')+'</ul><h2>检查与读取提示</h2><ul>'+report.issues.map(i=>'<li>'+esc(i.text)+'<small> · '+esc(i.source)+'</small></li>').join('')+report.errors.map(e=>'<li>'+esc(e.message)+' · '+esc(e.source)+'</li>').join('')+'</ul><h2>模组用途与声明</h2><table><thead><tr><th>名称 / 文件</th><th>说明与分类</th><th>必需依赖</th><th>状态</th></tr></thead><tbody>'+report.mods.map(m=>'<tr><td><strong>'+esc(m.name)+'</strong><p><small>'+esc(m.file)+'</small></p></td><td><p>'+esc(damnPurpose(m).text)+'</p><small>'+esc([effectiveCategory(m),...damnCategoryInfo(m).tags,...damnCategoryInfo(m).ecosystems.map(e=>e.label)].join(' · '))+' · '+esc(damnPurpose(m).source)+' · '+esc(damnCategoryInfo(m).source)+'</small></td><td>'+required(m).map(d=>esc(d.target)+' '+esc(Array.isArray(d.range)?d.range.join(' 或 '):d.range)).join('<br>')+'</td><td>'+(m.kind==='manifest'?'仅清单':m.enabled?'启用':'停用')+'</td></tr>').join('')+'</tbody></table><h2>脚本与配置文本引用</h2>'+report.references.map(r=>'<p>'+esc(r.id)+' · '+esc(r.file)+':'+r.line+'<br><small>'+esc(r.snippet)+'</small></p>').join('')+report.mods.filter(m=>m.onlineResearch).map(m=>'<h2>'+esc(m.name)+' · 联网补充</h2>'+renderResearch(m.onlineResearch,m.aiAnnotation,m.reconciliation,m.aiSearch,m)).join('')+'<p><small>DAMN '+esc(report.version)+' · Dependency Analysis &amp; Mod Network</small></p></html>';
 download(content,'DAMN-report.html','text/html');
});
function buildContext(scope='pack'){
 if(!report)throw Error('请先打开整合包或载入示例。');
 const chosen=scope==='selected'?mod(selected):null;if(scope==='selected'&&!chosen)throw Error('请先选择模组。');
 const base={mode:report.mode,archive:report.archive,environment:report.environment,side:report.side,limits:report.limits,enrichment:report.enrichmentSummary};
 if(chosen){base.mod={kind:chosen.kind,manifest:chosen.manifest,dependenciesKnown:chosen.dependenciesKnown,name:chosen.name,file:chosen.file,version:chosen.version,category:effectiveCategory(chosen),tags:damnCategoryInfo(chosen).tags,categoryTaxonomyVersion:DAMN_TAXONOMY_DATA.version,sha1:chosen.sha1,description:chosen.description,components:chosen.components.map(c=>({id:c.id,version:c.version,nested:c.nested})),dependencies:chosen.dependencies};base.issues=report.issues.filter(i=>i.mod===chosen.key);const imp=getImpact(chosen.key);base.affected=imp.mods.map(m=>({name:m.name,file:m.file}));base.references=imp.references.slice(0,15);}
 else{base.totalMods=report.mods.length;base.mods=report.mods.slice(0,300).map(m=>({key:m.key,kind:m.kind,name:m.name,version:m.version,category:effectiveCategory(m),purpose:short(damnPurpose(m).text,150),matched:m.resolutionStatus,enabled:m.enabled}));base.issues=report.issues.slice(0,40);base.shownMods=base.mods.length;base.note='摘要范围有限，未包含所有文件及关系。';}
 let text=JSON.stringify(base,null,2);
 if(text.length>40000){base.references=[];base.affected=base.affected?.slice(0,30);if(base.mods){base.mods=base.mods.slice(0,60);base.shownMods=base.mods.length;}base.note='内容经过截取，不能据此推断整个整合包。';text=JSON.stringify(base,null,2);}
 if(text.length>45000)throw Error('该组件的元数据过多，请缩小分析范围。');return text;
}
function updateAIButtons(){
 $('#pack-ai-run').disabled=aiBusy||!report;$('#pack-ai-run').textContent=aiBusy?'正在分析…':'分析整合包 ↗';
 if($('#detail-ai'))$('#detail-ai').disabled=aiBusy;
 $('#ai-config-summary').textContent=settingsState?.configured?'当前模型：'+settingsState.model+(settingsState.autoSearch?' · 自动搜索三站资料已开启':' · 自动搜索关闭')+(settingsState.autoSearch?' · 导入后自动补全整份清单，可暂停。':' · 点击分析调用你的 API。'):'本地分析可直接使用，AI 服务可在设置中配置。';
}
function usageText(data){return '模型：'+data.model+(data.usage?.total_tokens?' · 服务商报告 '+data.usage.total_tokens+' tokens':' · 服务商未返回 token 用量');}
async function askAI(scope){
 if(aiBusy)return;if(!report){notice('请先打开整合包。',true);return;}
 if(!settingsState?.configured){const dialog=$('#pack-ai-dialog');if(dialog?.open)dialog.close();await openSettings(false,'ai');setSettingsStatus('请先配置服务地址、模型和密钥。','','ai');return;}
 let context;try{context=buildContext(scope);}catch(e){notice(e.message,true);return;}
 const question=scope==='selected'?'解释这个模组的用途、依赖关系和改动影响，指出需要核对的文件。区分文件依据、文本命中和推测。':$('#pack-ai-question').value.trim();
 if(!question){notice('请填写分析问题。',true);return;}
 const current=report,key=selected;aiBusy=true;updateAIButtons();
 if(scope==='pack'){$('#pack-ai-evidence').textContent=context;$('#pack-ai-answer').textContent=(settingsState.autoSearch?'正在交叉核对三站资料，使用 ':'正在使用 ')+settingsState.model+' 分析本次证据…';$('#pack-ai-answer').className='inline-answer';$('#pack-ai-usage').textContent='';}
 else{$('#detail-ai-answer').textContent=(settingsState.autoSearch?'正在独立检索并核对三站资料，使用 ':'正在使用 ')+settingsState.model+' 分析这个模组…';$('#detail-ai-evidence').textContent=context;}
 try{const data=await api('/api/ai',{question,context});if(report!==current)return;
  if(scope==='pack'){$('#pack-ai-answer').textContent=data.answer;$('#pack-ai-answer').className='inline-answer ai-result';$('#pack-ai-usage').textContent=usageText(data);if($('#pack-web-research'))$('#pack-web-research').remove();if(data.research)$('#pack-ai-usage').insertAdjacentHTML('afterend','<div id="pack-web-research">'+renderResearch(data.research,data.annotation,data.reconciliation,data.aiSearch)+'</div>');}
  else{aiAnswers.set(key,{answer:data.answer,usageText:usageText(data),research:data.research,annotation:data.annotation,reconciliation:data.reconciliation,aiSearch:data.aiSearch});applyOnlineMetadata(key,data);if(selected===key)renderDetail();}
 }catch(e){if(report!==current)return;if(scope==='pack')$('#pack-ai-answer').textContent=e.message;else if(selected===key)$('#detail-ai-answer').textContent=e.message;}
 finally{aiBusy=false;updateAIButtons();}
}
$('#pack-ai-open').addEventListener('click',()=>$('#pack-ai-dialog').showModal());
$('#pack-ai-close').addEventListener('click',()=>$('#pack-ai-dialog').close());
$('#pack-ai-run').addEventListener('click',()=>askAI('pack'));
$('#pack-ai-preview').addEventListener('toggle',e=>{if(e.target.open){try{$('#pack-ai-evidence').textContent=buildContext('pack');}catch(err){$('#pack-ai-evidence').textContent=err.message;}}});
let settingsWorking=false,settingsOpenEpoch=0,settingsWriteEpoch=0,settingsReadTask=null;
async function loadSettingsState(){
 if(settingsState)return settingsState;
 if(!settingsReadTask){const epoch=settingsWriteEpoch;settingsReadTask=api('/api/settings').then(fresh=>{if(epoch===settingsWriteEpoch)settingsState=fresh;return settingsState||fresh;}).finally(()=>{settingsReadTask=null;});}
 return settingsReadTask;
}
function cancelPendingSettings(){settingsOpenEpoch++;}
function setSettingsStatus(text,type='',category){if(typeof window.damnSetCategorySettingsStatus==='function'){window.damnSetCategorySettingsStatus(text,type,category);return;}const el=$('#settings-status');el.textContent=text;el.className='small '+(type||'muted');}
function settingsDraft(){
 const draft={endpoint:$('#settings-endpoint').value.trim(),model:$('#settings-model').value.trim(),apiKey:$('#settings-key').value,clearKey:draftClearKey,autoSearch:$('#settings-auto-search').checked};
 if(!settingsState?.endpoint&&!settingsState?.model&&!settingsState?.hasKey&&!draft.endpoint&&!draft.model&&!draft.apiKey.trim()&&!draft.clearKey)return {defer:true,autoSearch:draft.autoSearch};
 return draft;
}
function settingsLock(value){settingsWorking=value;['#settings-save','#settings-test','#settings-clear-key'].forEach(s=>$(s).disabled=value);}
async function openSettings(initial=false,category){
 const openEpoch=++settingsOpenEpoch;
 try{if(!settingsState)await loadSettingsState();}catch(e){notice(e.message,true);return;}
 if(openEpoch!==settingsOpenEpoch)return;
 if(typeof damnShowSettings==='function')damnShowSettings();
 $('#settings-ai-fields').hidden=false;$('#settings-test').hidden=false;
 firstRun=initial;draftClearKey=false;$('#settings-auto-search').checked=!!settingsState.autoSearch;
 $('#settings-title').textContent=initial?'欢迎使用 DAMN':'设置';
 $('#settings-intro').textContent=initial?'本地扫描可直接使用。联网资料和 AI 解读都在这里配置，也可以稍后再填。':'查看外观与版本信息，管理联网资料与 AI 解读。';
 $('#settings-endpoint').value=settingsState.endpoint||'';$('#settings-model').value=settingsState.model||'';$('#settings-key').value='';$('#settings-key').placeholder=settingsState.hasKey?'已保存密钥；留空保留，更换服务商时请重新填写':'填写你的 API Key（本地模型可留空）';
 $('#settings-clear-key').hidden=!settingsState.hasKey;$('#settings-skip').hidden=!initial;
 $('#settings-security-note').textContent='密钥由当前 Windows 用户加密保存在本地，不加入分析报告。已保存的密钥留空保留；清除操作在保存后生效。';
 setSettingsStatus(settingsState.error||'保存设置不会调用 AI；测试连接仅发送少量测试文字，可能产生 API 费用。');
 $('#settings-dialog').dataset.mode='full';
 if(typeof window.damnShowSettingsCategory==='function')window.damnShowSettingsCategory(category||(initial?'ai':undefined));
 if(typeof damnSettingsReady==='function')damnSettingsReady(openEpoch);
}
async function dismissSettings(){
 if(settingsWorking)return;
 if(firstRun){try{settingsState=await api('/api/settings',{defer:true});settingsWriteEpoch++;firstRun=false;}catch(e){setSettingsStatus(e.message,'error');return;}}
 $('#settings-key').value='';updateAIButtons();if(typeof damnReturnFromSettings==='function')await damnReturnFromSettings();
}
$('#settings-open').addEventListener('click',()=>openSettings(false));
$('#settings-close').addEventListener('click',dismissSettings);$('#settings-skip').addEventListener('click',dismissSettings);
$('#settings-dialog').addEventListener('cancel',e=>{e.preventDefault();dismissSettings();});
$('#settings-clear-key').addEventListener('click',()=>{draftClearKey=true;$('#settings-key').value='';$('#settings-key').placeholder='保存后移除密钥；如需替换可填写新密钥';setSettingsStatus('清除将在保存后生效。','','ai');});
$('#settings-save').addEventListener('click',async()=>{
 if(settingsWorking)return;settingsLock(true);
 try{
  settingsState=await api('/api/settings',settingsDraft());settingsWriteEpoch++;firstRun=false;if(typeof identitySettingsChanged==='function')identitySettingsChanged(settingsState);
  $('#settings-key').value='';updateAIButtons();
  renderEnrichment();report&&(report.enrichmentPausedUser=false);lastConfigStamp=damnConfigStamp(settingsState);
  if(!settingsState.autoSearch&&enrichment?.id)api('/api/enrich/cancel',{id:enrichment.id}).catch(()=>{});else maybeAutoEnrich(true);
  if(typeof prerequisiteNotice==='function')prerequisiteNotice('设置已保存，可重新识别目录以使用更新后的平台配置。');
  setSettingsStatus('设置已保存。返回原工作区后继续使用。','success');$('#settings-skip').hidden=true;notice(settingsState.configured?'设置已保存，AI 解读可在总览或模组详情中使用。':'设置已保存，本地扫描和前置核对可直接使用。');
 }catch(e){setSettingsStatus(e.message,'error');}finally{settingsLock(false);}
});
$('#settings-test').addEventListener('click',async()=>{
 if(settingsWorking)return;settingsLock(true);setSettingsStatus('正在测试连接和模型响应…','','ai');
 try{const result=await api('/api/settings/test',settingsDraft());setSettingsStatus('连接成功 · '+result.model+' · '+result.milliseconds+' ms'+(result.usage?.total_tokens?' · '+result.usage.total_tokens+' tokens':''),'success','ai');}
 catch(e){setSettingsStatus(e.message,'error','ai');}finally{settingsLock(false);}
});
async function initializeAnalysis(){
 if(analysisInitialization)return analysisInitialization;
 analysisInitialization=(async()=>{try{
  await loadSettingsState();updateAIButtons();
  if(!damnAnalysisActive){analysisInitialization=null;return;}
  {try{const saved=JSON.parse(localStorage.getItem('damn-last-report-v2')||'null');if(saved&&Array.isArray(saved.mods)&&Array.isArray(saved.edges))loadReport(saved);}catch{}await maybeAutoEnrich();}
 }catch(e){analysisInitialization=null;notice('设置未能读取：'+e.message,true);}})();
 return analysisInitialization;
}
async function setAnalysisWorkspaceActive(active){
 const wasActive=damnAnalysisActive;damnAnalysisActive=!!active;
 if(typeof identityWorkspaceChanged==='function')identityWorkspaceChanged(!!active);
 if(active){if(!analysisWatchdog)analysisWatchdog=setInterval(()=>syncEnrichmentState(),5000);await initializeAnalysis();return;}
 clearInterval(analysisWatchdog);analysisWatchdog=null;
 if(!wasActive)return;
 clearTimeout(enrichPollTimer);enrichEpoch++;enrichStarting=false;
 if(typeof categoryLookupEpoch!=='undefined')categoryLookupEpoch++;
 if(report){report.enrichmentPausedUser=true;persistReport();}
 if(enrichment?.id&&['running','reconnecting'].includes(enrichment.status)){
  try{const paused=await api('/api/enrich/cancel',{id:enrichment.id,after:enrichment.cursor||0});if(!damnAnalysisActive)consumeEnrichment(paused);}catch{}
 }
}


function safeWebURL(value){try{const u=new URL(value);return u.protocol==='https:'&&['modrinth.com','www.modrinth.com','www.curseforge.com','curseforge.com','www.mcmod.cn','mcmod.cn','search.mcmod.cn','api.modrinth.com','api.curseforge.com'].includes(u.hostname)?u.href:null;}catch{return null;}}
function renderResearch(results,annotation,reconciliation,aiSearch,owner){
 const allSources=[...new Map(results.flatMap(r=>r.sources||[]).filter(s=>safeWebURL(s.url)).map(s=>[s.url,s])).values()];
 let html='<section class="web-research"><h4>核对与精简</h4>';
 if(aiSearch)html+='<p class="search-mode small">'+esc(aiSearch.message)+(aiSearch.cached?' · 复用此前已完成的结果':'')+(aiSearch.calls?.length?' · 已请求 '+aiSearch.calls.length+' 次工具':'')+'</p>';
 if(reconciliation){
  const labels={matched:'已吻合',added:'补充信息',conflicts:'存在分歧',unknown:'仍待确认'};
  Object.entries(labels).forEach(([key,label])=>{
   const rows=[...new Set(reconciliation[key]||[])];if(!rows.length)return;
   html+='<div class="comparison-group '+key+'"><strong>'+label+' <small>'+rows.length+'</small></strong><ul>'+rows.slice(0,5).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>';
   if(rows.length>5)html+='<details><summary>另 '+(rows.length-5)+' 条</summary><ul>'+rows.slice(5).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></details>';
   html+='</div>';
  });
 }
 const relationMap=new Map();
 [...results.flatMap(r=>r.platformDependencies||[]),...(annotation?.relations||[])].forEach(r=>{const key=String(r.target).toLowerCase()+'|'+r.kind;if(!relationMap.has(key))relationMap.set(key,r);});
 const relations=owner?onlineRelations({...owner,onlineResearch:results,aiAnnotation:annotation},report.mods):[...relationMap.values()];
 html+='<details class="web-evidence"><summary>查看 '+allSources.length+' 个来源与 '+relations.length+' 条网页关联</summary>';
 allSources.forEach(s=>{const url=safeWebURL(s.url);html+='<article class="web-source"><a href="'+esc(url)+'" target="_blank" rel="noreferrer">'+esc(s.site+' · '+s.title)+' ↗</a><small>'+esc(s.match||'网页资料')+'</small><p>'+esc(s.excerpt||'')+'</p>'+(s.categories?.length?'<small>平台分类：'+esc(s.categories.join('、'))+'</small>':'')+'</article>';});
 results.forEach(r=>{
  if(r.sites?.length)html+='<p class="small muted">'+esc(r.subject||r.query||'当前模组')+' · '+r.sites.map(s=>esc(s.site)+'：'+(s.ok?'已获取':'暂无资料')).join(' · ')+'</p>';
  html+='<div class="web-notes">'+[...new Set(r.notes||[])].map(n=>'<p>'+esc(n)+'</p>').join('')+'</div>';
 });
 if(relations.length)html+='<div class="section-label">网页关联 · 需核对版本</div><div class="web-relations">'+relations.map(r=>{const url=safeWebURL(r.source);return esc(({required:'必需前置',optional:'可选前置',incompatible:'不兼容',related:'相关模组',used_by:'被该模组依赖',embedded:'内置',tool:'工具',include:'包含'})[r.kind]||r.kind)+'：'+esc(r.target)+(url?' <a href="'+esc(url)+'" target="_blank" rel="noreferrer">来源 ↗</a>':'')+'<small> · '+esc(r.provenance||'AI 网页推测')+'</small>';}).join('<br>')+'</div>';
 if(aiSearch?.calls?.length)html+='<details><summary>AI 检索记录</summary><pre>'+esc(JSON.stringify(aiSearch.calls,null,2))+'</pre></details>';
 return html+'</details></section>';
}
function rebuildWebEdges(){
 if(report)report.webEdges=buildWebRelations(report.mods,report.edges);
}
function applyPatch(key,patch){
 const m=mod(key);if(!m)return;
 for(const field of ['name','description','version','loader'])if(typeof patch[field]==='string'&&patch[field]!==m[field]){const old='original'+field[0].toUpperCase()+field.slice(1);if(!(old in m))m[old]=m[field];m[field]=patch[field];}
 for(const field of ['platformInfo','platformTaxonomy','platformCategoryCheck','resolutionStatus','webCategory','webCategoryEvidence','onlineResearch','enrichmentComplete','aiSearch','aiReviewStatus','aiReviewNote','aiAnnotation','aiCategory','aiPurpose','descriptionZh','translationAttempted','purposeAttemptedRevision','aiPurposeBasis','aiClassification','classificationAttemptedStamp','classificationNote','reconciliation'])if(field in patch)m[field]=patch[field];
}
function refreshMetadata(){
 rebuildWebEdges();updateCategories();updateNetworkSelect();applyFilters();renderDetail();renderGraph();renderClassification();persistReport();
}
function applyOnlineMetadata(key,data){
 const m=mod(key);if(!m)return;
 const identity=(data.research||[]).map(r=>r.identity).find(x=>x?.exact)||(data.research||[]).find(r=>r.identity)?.identity;
 const patch={onlineResearch:data.research||m.onlineResearch};
 if(identity){patch.platformInfo=identity;patch.resolutionStatus=identity.exact?'matched':'candidate';if(m.kind==='manifest'&&identity.exact){patch.name=identity.title;patch.description=identity.description;if(identity.version)patch.version=identity.version;}}
 if(data.annotation){patch.aiAnnotation=data.annotation;patch.aiPurpose=damnCleanPurpose(data.annotation.purpose)||damnCleanPurpose(data.annotation.summary);patch.purposeAttemptedRevision=1;patch.aiPurposeBasis=data.annotation.evidence?.length?'web':'local';patch.translationAttempted=true;if(data.annotation.descriptionZh)patch.descriptionZh=data.annotation.descriptionZh;if(data.annotation.category)patch.aiCategory=data.annotation.category;}
 if(data.reconciliation)patch.reconciliation=data.reconciliation;if(data.aiSearch)patch.aiSearch=data.aiSearch;
 applyPatch(key,patch);refreshMetadata();
}
let enrichPollTimer=null,enrichEpoch=0,enrichStarting=false,enrichSyncing=false,enrichPolling=false,enrichFailures=0,enrichLastCheck=0,lastConfigStamp='',watchdogBusy=false;
function reportScope(data=report){
 let hash=2166136261;for(const c of (data?.created||'')+'|'+(data?.pack||'')+'|'+(data?.mods||[]).map(m=>m.key+':'+m.file).join('|'))hash=Math.imul(hash^c.charCodeAt(0),16777619);
 return 'pack-'+(hash>>>0).toString(16);
}
function renderEnrichment(){
 $('#enrich-panel').hidden=!report;if(!report)return;
 const s=enrichment||report.enrichmentSummary,running=s?.status==='running'||s?.status==='reconnecting'||enrichStarting,p=damnProgress(s,report.mods);
 $('#enrich-panel').hidden=!settingsState?.autoSearch&&!s;
 const finished=s?.status==='complete'&&!s.hasMore&&!s.aiError&&!s.error&&!s.waitingForConfig&&p.done===p.total&&p.aiDone===p.aiTotal;
 $('#enrich-stop').hidden=!running;$('#enrich-run').hidden=!!running||finished;$('#enrich-run').disabled=!!running;$('#enrich-done').hidden=!finished;
 $('#enrich-run-label').textContent=s?'继续未完成项':'补全整份清单';
 $('#enrich-speed').textContent=damnSpeed(s);
 $('#enrich-meter').value=p.search;$('#enrich-percent').textContent=p.search+'% · '+p.done+' / '+p.total;
 $('#enrich-ai-meter').value=p.ai;$('#enrich-ai-percent').textContent=s?.waitingForConfig?'等待 API 配置':p.aiTotal?p.ai+'% · '+p.aiDone+' / '+p.aiTotal:p.total&&p.done===p.total?'无可核对资料':'等待资料';
 if(s){
  $('#enrich-title').textContent=s.phase||'联网补全清单';
  $('#enrich-progress').textContent='平台检索 '+p.done+' / '+p.total+' · 精确匹配 '+(p.matched||0)+' · 候选 '+(p.candidates||0)+' · 无资料 '+(p.failed||0)+(s.total!==p.total?' · 本轮 '+s.done+' / '+s.total:'')+(s.aiBatch?' · AI 第 '+s.aiBatch+' 批':'')+(s.aiError?' · AI 待恢复：'+s.aiError:'')+(s.error?' · '+s.error:'');
 }else{
  $('#enrich-title').textContent='联网补全清单';$('#enrich-progress').textContent=settingsState?.autoSearch?'已开启自动搜索；稍后填写 API 也会自动继续翻译与依赖核对。':'请在设置中开启自动联网；保存后无需重新导入，会自动开始。';
 }
 const current=(s?.activeItems||[]).slice(0,2).join('、'),ai=(s?.activeAI||[]).slice(0,2).join('、');
 if(typeof damnSyncEnrichmentDisclosure==='function')damnSyncEnrichmentDisclosure(!!running);
 $('#enrich-sync').textContent=(enrichFailures?'连接暂时中断，正在自动重连（已保留进度）。':enrichLastCheck?'状态已同步 · '+new Date(enrichLastCheck).toLocaleTimeString():'每 5 秒同步配置与任务状态')+(current?' · 正在搜索：'+current:'')+(ai?' · 正在整理中文用途：'+ai:'')+(s?.waitingForConfig?' · 在设置中保存 API 后自动继续。':'');
}
function jobMods(retry=false){
 return report.mods.filter(m=>damnPendingMod(m,retry)).map(m=>({key:m.key,kind:m.kind,name:m.originalName||m.name,file:m.file,version:m.originalVersion||m.version,category:effectiveCategory(m),tags:damnCategoryInfo(m).tags,categoryTaxonomyVersion:2,sha1:m.sha1,manifest:m.manifest,dependenciesKnown:m.dependenciesKnown,components:m.components.map(c=>({id:c.id,version:c.version})),dependencies:m.dependencies.map(d=>({target:d.target,type:d.type,range:d.range})),description:m.originalDescription||m.description,loader:m.loader,onlineResearch:m.onlineResearch,enrichmentComplete:m.enrichmentComplete,resolutionStatus:m.resolutionStatus,aiAnnotation:m.aiAnnotation,aiReviewStatus:m.aiReviewStatus,descriptionZh:m.descriptionZh,translationAttempted:m.translationAttempted}));
}
function consumeEnrichment(data){
 if(!report)return;
 if(enrichment?.id===data.id&&(enrichment.cursor||0)>(data.cursor||0))return;
 for(const item of data.updates||[])applyPatch(item.key,item.patch);
 if(data.updates?.length)refreshMetadata();
 enrichment=data;enrichFailures=0;enrichLastCheck=Date.now();report.enrichmentStartRequest=null;if(!report.enrichmentAttemptStamp)report.enrichmentAttemptStamp=damnConfigStamp(settingsState);
 report.enrichmentSession={id:data.id,requestId:data.requestId,scope:data.scope,cursor:data.cursor};
 report.enrichmentSummary=Object.fromEntries(Object.entries(data).filter(([k])=>!['updates','cursor','hasMore','id'].includes(k)));
 renderEnrichment();persistReport();
}
function scheduleEnrichment(current,id,after,delay=1500){
 clearTimeout(enrichPollTimer);const epoch=enrichEpoch;
 enrichPollTimer=setTimeout(()=>{if(enrichEpoch===epoch)pollEnrichment(current,id,after);},delay);
}
async function pollEnrichment(current,id,after){
 if(typeof damnAnalysisActive!=='undefined'&&!damnAnalysisActive)return;
 if(report!==current||enrichment?.id!==id||enrichPolling)return;
 enrichPolling=true;const epoch=enrichEpoch;
 try{
  const data=await api('/api/enrich/status?id='+encodeURIComponent(id)+'&after='+after);
  if(report!==current||enrichEpoch!==epoch)return;
  consumeEnrichment(data);
  if(data.status==='running'||data.hasMore)scheduleEnrichment(current,id,data.cursor,data.hasMore?50:1500);
 }catch(e){
  if(report!==current||enrichEpoch!==epoch)return;
  if(e.code==='job_not_found'){
   enrichment=null;report.enrichmentSession=null;await maybeAutoEnrich();
  }else{
   enrichFailures++;enrichment={...enrichment,status:'reconnecting',phase:'正在重新同步搜索状态',connectionError:e.message};renderEnrichment();
   scheduleEnrichment(current,id,after,Math.min(8000,1500*2**Math.min(3,enrichFailures)));
  }
 }finally{enrichPolling=false;}
}
async function reconnectEnrichment(){
 if(!report||enrichSyncing)return false;
 enrichSyncing=true;const current=report,epoch=enrichEpoch,session=report.enrichmentSession;
 try{
  const data=await api('/api/enrich/current?scope='+reportScope()+'&after='+(session?.cursor||0));
  if(report!==current||epoch!==enrichEpoch)return true;
  enrichLastCheck=Date.now();
  if(data.job){consumeEnrichment(data.job);if(data.job.status==='running'||data.job.hasMore)scheduleEnrichment(current,data.job.id,data.job.cursor,50);return true;}
  enrichment=null;report.enrichmentSession=null;return false;
 }catch(e){enrichFailures++;renderEnrichment();return true;}
 finally{enrichSyncing=false;}
}
async function startEnrichment(retry=false){
 if(typeof damnAnalysisActive!=='undefined'&&!damnAnalysisActive)return;
 if(!report||enrichStarting)return;
 if(!settingsState?.autoSearch){await openSettings(false,'network');setSettingsStatus('开启自动联网并保存后，会自动继续当前清单。','','network');return;}
 const current=report,mods=jobMods(retry);if(!mods.length){notice('当前条目已处理完成。');return;}
 report.enrichmentPausedUser=false;const epoch=++enrichEpoch;clearTimeout(enrichPollTimer);enrichStarting=true;
 const requestId=report.enrichmentStartRequest||crypto.randomUUID();report.enrichmentStartRequest=requestId;
 try{
  enrichment={...report.enrichmentSummary,status:'running',phase:'正在连接后台补全任务',done:0,total:mods.length,matched:0,candidates:0,failed:0,aiDone:0,aiTotal:0};renderEnrichment();
  const data=await api('/api/enrich/start',{mods,requestId,scope:reportScope()});
  if(report!==current||epoch!==enrichEpoch){api('/api/enrich/cancel',{id:data.id}).catch(()=>{});return;}
  report.enrichmentStartRequest=null;report.enrichmentAttemptStamp=damnConfigStamp(settingsState);consumeEnrichment(data);
  if(data.status==='running'||data.hasMore)scheduleEnrichment(current,data.id,data.cursor,50);
 }catch(e){
  if(report===current){enrichment={...enrichment,status:'reconnecting',phase:'正在恢复后台任务连接',connectionError:e.message};enrichFailures++;renderEnrichment();}
 }finally{if(epoch===enrichEpoch)enrichStarting=false;persistReport();}
}
async function maybeAutoEnrich(configChanged=false){
 if(typeof damnAnalysisActive!=='undefined'&&!damnAnalysisActive)return;
 if(typeof identityMaybeAutoCheck==='function')void identityMaybeAutoCheck();
 if(!report||report.mode==='snapshot'||!settingsState?.autoSearch||report.enrichmentPausedUser||enrichStarting||enrichSyncing)return;
 configChanged=!!(configChanged||report.enrichmentAttemptStamp&&report.enrichmentAttemptStamp!==damnConfigStamp(settingsState));
 if(enrichment?.id&&(enrichment.status==='running'||enrichment.status==='reconnecting')&&!enrichment.aiError)return;
 if(!damnAutoReady(enrichment||report.enrichmentSummary,configChanged))return;
 if(enrichment?.status==='failed'&&!configChanged&&report.enrichmentAttemptStamp===damnConfigStamp(settingsState))return;
 if(enrichment?.aiError&&!configChanged&&report.enrichmentAttemptStamp===damnConfigStamp(settingsState))return;
 if(configChanged&&enrichment?.aiError){
  if(enrichment.id)await api('/api/enrich/cancel',{id:enrichment.id}).catch(()=>{});
  enrichment=null;report.enrichmentSession=null;report.enrichmentStartRequest=null;
 }
 if(!enrichment?.id&&await reconnectEnrichment()){
  if(!damnAutoReady(enrichment,configChanged))return;
 }
 if(report.mods.some(m=>damnPendingMod(m))&&(!enrichment?.aiError||configChanged))await startEnrichment();
}
async function syncEnrichmentState(force=false){
 if(typeof damnAnalysisActive!=='undefined'&&!damnAnalysisActive)return;
 if(watchdogBusy||(!report&&!force)||document.hidden&&!force)return;
 watchdogBusy=true;
 try{
  const fresh=await api('/api/settings'),changed=lastConfigStamp&&lastConfigStamp!==damnConfigStamp(fresh);
  if(typeof damnAnalysisActive!=='undefined'&&!damnAnalysisActive)return;
  settingsState=fresh;lastConfigStamp=damnConfigStamp(fresh);updateAIButtons();if(typeof identitySettingsChanged==='function')identitySettingsChanged(fresh);
  if(changed&&fresh.autoSearch&&report)report.enrichmentPausedUser=false;
  if(!fresh.autoSearch){if(enrichment?.status==='running'&&enrichment.id)await api('/api/enrich/cancel',{id:enrichment.id});renderEnrichment();return;}
  if(enrichment?.id&&(enrichment.status==='running'||enrichment.status==='reconnecting'||enrichment.hasMore)){
   if(!enrichPolling&&(force||Date.now()-enrichLastCheck>6000))await pollEnrichment(report,enrichment.id,enrichment.cursor||0);
  }
  await maybeAutoEnrich(!!changed);void syncClassification();renderEnrichment();
 }catch(e){enrichFailures++;renderEnrichment();}
 finally{watchdogBusy=false;}
}
$('#enrich-run').addEventListener('click',async()=>{
 if(!report)return;if(enrichment?.status==='running'&&enrichment.id)return;
 report.enrichmentPausedUser=false;report.enrichmentStartRequest=null;
 if(enrichment?.id)await api('/api/enrich/cancel',{id:enrichment.id}).catch(()=>{});
 enrichment=null;report.enrichmentSession=null;startEnrichment(true);
});
$('#enrich-refresh').addEventListener('click',()=>syncEnrichmentState(true));
$('#enrich-stop').addEventListener('click',async()=>{
 if(!report)return;report.enrichmentPausedUser=true;clearTimeout(enrichPollTimer);enrichEpoch++;enrichStarting=false;persistReport();
 if(enrichment?.id){try{const data=await api('/api/enrich/cancel',{id:enrichment.id,after:enrichment.cursor||0});consumeEnrichment(data);if(data.hasMore)scheduleEnrichment(report,data.id,data.cursor,50);}catch(e){renderEnrichment();}}
 else{enrichment={...enrichment,status:'cancelled',phase:'已暂停'};renderEnrichment();}
});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)syncEnrichmentState(true);});
window.addEventListener('focus',()=>syncEnrichmentState(true));

$('#network-show-isolated').addEventListener('change',()=>renderGraph(true));
