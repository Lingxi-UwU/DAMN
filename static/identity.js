'use strict';
let identityReport=null,identityJob=null,identityGeneration=0,identityPollGeneration=0,identityPollTimer=null,identityPolling=false,identityBusy=false,identityAttempted=false,identityConnection='',identityMessage='',identityFailures=0,identityPage=0,identityCurrentKey=null,identityRenderedKey=null,identityCandidateSignature='',identityDiagnosticHTML='',identityDiagnosticCandidates=null;
let identityNeedsValidation=false,identityOrigin='manual';
const identityPageSize=10,identityChoices=new Map(),identityQueries=new Map(),identityDirtyQueries=new Set();
function identityEligible(data=identityReport){return (data?.mods||[]).filter(mod=>mod.kind!=='manifest'&&/\.jar(?:\.disabled)?$/i.test(String(mod.file||''))&&/^[a-f0-9]{40}$/i.test(String(mod.sha1||''))&&/^[a-f0-9]{64}$/i.test(String(mod.sha256||'')));}
function identityStamp(data=identityReport){return JSON.stringify(identityEligible(data).map(mod=>[String(mod.key),mod.sha1.toLowerCase(),mod.sha256.toLowerCase(),mod.cfFingerprint??null]).sort((a,b)=>a[0].localeCompare(b[0])));}
function identityActive(){return !!identityJob&&(identityJob.status==='running'||(identityJob.items||[]).some(item=>item.searching));}
function identityInAnalysis(){return typeof isAnalysisWorkspace==='function'&&isAnalysisWorkspace();}
function identityItem(key=identityCurrentKey){return (identityJob?.items||[]).find(item=>String(item.key)===String(key));}
function identityPending(item){return !['exact','confirmed'].includes(item.status);}
function identityStatus(item){if(item.searching)return '正在搜索';if(item.status==='suspect'){const checks=Object.values(item.checks||{}),hasLookupFailure=checks.some(check=>check.status==='error'||check.status==='skipped')||(item.searchChecks||[]).some(check=>check.status==='error'),bothFilesNotFound=['Modrinth','CurseForge'].every(site=>item.checks?.[site]?.status==='not_found');if(hasLookupFailure||!bothFilesNotFound)return item.candidates?.length?'候选来源 · 待确认':checks.some(check=>check.status==='error')?'联网核对未完成':'来源待确认';if(item.label)return String(item.label);return item.candidates?.length?(checks.some(check=>check.status==='not_found')?'疑似魔改 · 待确认':'候选来源 · 待确认'):'来源待确认';}return {checking:'正在核对',exact:'精确匹配',confirmed:'用户已确认',unmatched:'来源待确认',error:'联网核对未完成'}[item.status]||'来源待确认';}
function identityDiagnosticMessage(value){
 const message=String(value||'');
 if(/(?:未设置|未配置|填写|配置).{0,24}(?:CF|CurseForge).{0,16}(?:API\s*)?Key|(?:CF|CurseForge).{0,16}(?:API\s*)?Key.{0,24}(?:未设置|未配置|填写|配置)/i.test(message))return 'CurseForge 服务暂不可用，本次未完成该站查询。';
 return message;
}
function identityCheckLabel(check,search=false){
 const status=String(check?.status||''),reason=String(check?.code||check?.reason||'')+' '+String(check?.message||'');
 if(status==='error'||status==='skipped'){
  if(/429|限流|too many|rate.?limit/i.test(reason))return '请求受限';
  if(/401|403|auth|认证|密钥|API\s*Key/i.test(reason))return status==='skipped'?'服务不可用':'服务认证未通过';
  if(/timeout|timed out|超时/i.test(reason))return '查询超时';
 }
 return ({matched:search?'已找到候选':'文件已匹配',found:'已找到候选',ok:search?'查询已完成':'核对已完成',not_found:search?'未找到候选':'未匹配该文件',error:'查询失败',skipped:'未查询',pending:'待查询',running:'正在查询'})[status]||'待核对';
}
function identityHints(item,local){
 const hints=Array.isArray(item.searchHints)?item.searchHints:[],seen=new Set(),values=[];
 for(const value of hints){const query=String(typeof value==='string'?value:value?.query||'').trim();if(query&&!seen.has(query)){seen.add(query);values.push({query,source:typeof value==='string'?'本地身份线索':String(value.source||'本地身份线索')});}}
 if(!values.length)for(const component of local?.components||[]){const query=String(component.id||'').trim();if(query&&!seen.has(query)){seen.add(query);values.push({query,source:'本地组件 ID'});}}
 return values.slice(0,8);
}
function identitySearchDiagnosticsHTML(item,local){
 if(item.status==='exact')return '';
 const searches=Array.isArray(item.searchChecks)?item.searchChecks:[],checks=Object.entries(item.checks||{}).map(([site,check])=>({site,...check})),hints=identityHints(item,local);
 const queries=[...new Set(searches.map(check=>String(check.query||'').trim()).filter(Boolean))].slice(0,12);
 const visibleChecks=searches.length?searches:checks,pending=item.searching||item.status==='checking',hasError=visibleChecks.some(check=>check.status==='error'),hasSkipped=visibleChecks.some(check=>check.status==='skipped');
 const headline=pending?'正在核对文件与查询项目':item.candidates?.length?'候选项目仍需人工确认':hasError?'部分查询未完成':hasSkipped?'当前可用来源未返回候选':'本次未找到候选项目';
 const summary=pending?'查询完成后，会分别显示各平台的结果。':item.candidates?.length?'选择候选并确认，只会关联原项目资料。':hasError||hasSkipped?'未取得完整的平台结果，不能据此判断本地文件被修改。可重试，或输入原名、官方项目链接继续查找。':'平台未返回候选不代表模组不存在，也不能单凭此判断文件被修改。可尝试下方文件内身份线索，或输入官方项目链接。';
 const rows=visibleChecks.slice(0,20).map(check=>'<div class="identity-diagnostic-row" data-status="'+esc(check.status||'pending')+'"><div><strong>'+esc((check.provider==='MCIM'?'MCIM 镜像 · ':'')+(check.site||'平台'))+'</strong><span>'+esc(identityCheckLabel(check,!!searches.length))+'</span></div>'+(check.query?'<p>查询：'+esc(check.query)+'</p>':'')+(check.message?'<p>'+esc(identityDiagnosticMessage(check.message))+'</p>':'')+'</div>').join('');
 const notes=!searches.length?(item.notes||[]).map(identityDiagnosticMessage).filter(Boolean):[];
 const process=(queries.length?'<p class="identity-query-trace"><strong>已查询</strong> '+queries.map(query=>'<span>'+esc(query)+'</span>').join(' ')+'</p>':'')+(rows?'<p class="identity-diagnostic-phase">'+(searches.length?'项目搜索结果':'文件哈希核对 · 此报告未记录项目搜索明细')+'</p><div class="identity-diagnostic-results" aria-label="平台查询结果">'+rows+'</div>':'')+(notes.length?'<div class="identity-diagnostic-notes">'+[...new Set(notes)].slice(0,8).map(note=>'<p>'+esc(note)+'</p>').join('')+'</div>':'')+(hints.length?'<div class="identity-query-hints"><strong>文件内身份线索</strong><p>这些内容来自本地文件，可用于重新搜索；不等于已确认的原项目。</p><div>'+hints.map(hint=>'<button class="identity-query-hint" type="button" data-identity-query-hint="'+esc(hint.query)+'"'+(pending||identityBusy||identityJob?.expired?' disabled':'')+'><span>'+esc(hint.query)+'</span><small>'+esc(hint.source)+'</small></button>').join('')+'</div></div>':'');
 return '<div class="identity-diagnostic-summary"><strong>'+esc(headline)+'</strong><p>'+esc(summary)+'</p></div>'+(process?'<details class="identity-query-details"'+(item.candidates?.length?'':' open')+'><summary>查询过程与文件线索</summary>'+process+'</details>':'');
}
function identityProjectURL(value){try{const url=new URL(value);return url.protocol==='https:'&&['modrinth.com','www.modrinth.com','curseforge.com','www.curseforge.com'].includes(url.hostname)&&!url.username&&!url.password?url.href:null;}catch{return null;}}
function identityProjectLink(project,label){const url=identityProjectURL(project?.url);return url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(label||project.name||'查看项目')+' ↗</a>':esc(label||project?.name||'项目资料');}
function identityLabelHTML(mod){
 if(!identityReport||!identityJob)return '';
 const item=identityItem(mod.key);if(!item||String(item.sha256||'').toLowerCase()!==String(mod.sha256||'').toLowerCase()||mod.kind==='manifest')return '';
 if(item.status==='confirmed'&&item.confirmation)return '<span class="tag identity-tag identity-tag-confirmed" title="用户确认的原项目；本地文件不等同于官方版本">原项目：'+esc(item.confirmation.name||'已确认项目')+'（用户确认）</span>';
 if(item.status==='exact'&&item.exact)return '<span class="tag identity-tag identity-tag-exact">官方文件已匹配</span>';
 if(item.status==='suspect'&&item.candidates?.length)return '<span class="tag identity-tag identity-tag-suspect">'+esc(identityStatus(item))+'</span>';
 if(['unmatched','suspect'].includes(item.status))return '<span class="tag identity-tag identity-tag-pending">来源待确认</span>';
 if(item.status==='error')return '<span class="tag identity-tag identity-tag-pending">来源核对未完成</span>';
 return '';
}
function identitySave(){if(!identityReport)return;identityReport.identityReview={revision:1,stamp:identityStamp(),attempted:identityAttempted,origin:identityOrigin,job:identityJob};if(typeof persistReport==='function')persistReport();}
function identityLabelsSignature(job){return JSON.stringify((job?.items||[]).map(item=>[item.key,item.status,item.confirmation?.name,item.exact?.name,item.candidates?.length]));}
function identityRefreshLabels(){if(identityReport!==report)return;if(typeof renderList==='function')renderList();if(typeof renderDetail==='function')renderDetail();}
function identityFilteredItems(){const filter=$('#identity-filter').value||'pending';return (identityJob?.items||[]).filter(item=>filter==='all'||filter==='pending'&&identityPending(item)||item.status===filter);}
function identityRenderQueue(){
 const items=identityFilteredItems(),pages=Math.max(1,Math.ceil(items.length/identityPageSize));identityPage=Math.min(Math.max(0,identityPage),pages-1);
 if(!items.some(item=>String(item.key)===String(identityCurrentKey)))identityCurrentKey=items[identityPage*identityPageSize]?.key??null;
 const rows=items.slice(identityPage*identityPageSize,(identityPage+1)*identityPageSize);
 $('#identity-queue').innerHTML=rows.map(item=>'<button class="identity-queue-item'+(String(item.key)===String(identityCurrentKey)?' identity-queue-selected':'')+'" type="button" data-identity-key="'+esc(item.key)+'" aria-pressed="'+String(String(item.key)===String(identityCurrentKey))+'"><strong>'+esc(item.name||item.file||'未命名文件')+'</strong><span>'+esc(identityStatus(item))+'</span></button>').join('')||'<div class="identity-queue-empty">'+($('#identity-filter').value==='pending'?'当前没有待核对项。':'这个分组暂无文件。')+'</div>';
 $('#identity-page-label').textContent=items.length?'第 '+(identityPage+1)+' / '+pages+' 页 · '+items.length+' 项':'0 项';$('#identity-prev').disabled=identityPage<=0;$('#identity-next').disabled=identityPage>=pages-1;
}
function identityRenderReview(){
 const item=identityItem(),changed=String(identityRenderedKey)!==String(item?.key),busy=identityBusy||item?.searching||item?.status==='checking'||identityJob?.expired,dirty=identityDirtyQueries.has(String(item?.key));
 $('#identity-review-body').hidden=!item;$('#identity-review-empty').hidden=!!item;
 if(!item){$('#identity-confirm').disabled=true;$('#identity-clear').hidden=true;$('#identity-review-empty').textContent=$('#identity-filter').value==='pending'?'待核对队列已处理，可切换查看用户确认或精确匹配项。':'从左侧选择一个文件查看来源。';identityRenderedKey=null;identityCandidateSignature='';return;}
 const local=identityReport?.mods?.find(mod=>String(mod.key)===String(item.key)),project=item.status==='confirmed'?item.confirmation:item.status==='exact'?item.exact:null;
 $('#identity-file-heading').innerHTML='<span class="identity-local-label">本地模组</span><h4>'+esc(local?.name||item.name)+'</h4><p>'+esc(local?.file||item.file)+'</p>';
 $('#identity-file-status').textContent=identityStatus(item);$('#identity-file-status').dataset.status=item.status;
 $('#identity-confirmed-project').hidden=!project;$('#identity-confirmed-project').innerHTML=project?'<strong>'+(item.status==='confirmed'?'原项目：'+esc(project.name||'已确认项目')+'（用户确认）':'官方项目：'+esc(project.name||'已匹配项目'))+'</strong><span>'+identityProjectLink(project,'查看平台资料')+'</span>':'';
 const checks=Object.entries(item.checks||{}).map(([site,check])=>'<p><strong>'+esc(site)+'</strong> · '+esc(({matched:'文件已匹配',not_found:'未匹配到该文件',error:'连接未完成',skipped:'未查询'})[check.status]||'待核对')+(check.message?' · '+esc(identityDiagnosticMessage(check.message)):'')+'</p>').join('');
 const metadata=item.localMetadata||{},componentIds=Array.isArray(metadata.componentIds)?metadata.componentIds:(local?.components||[]).map(component=>component.id).filter(Boolean),authors=Array.isArray(metadata.authors)?metadata.authors:[],projectUrls=Array.isArray(metadata.projectUrls)?metadata.projectUrls:[];
 $('#identity-file-details').innerHTML=(componentIds.length?'<p>本地组件 ID：'+esc(componentIds.join('、'))+'</p>':'')+(authors.length?'<p>文件内作者：'+esc(authors.join('、'))+'</p>':'')+(projectUrls.length?'<p>文件内项目地址：'+projectUrls.map(url=>'<span>'+esc(url)+'</span>').join('；')+'</p>':'')+'<p class="identity-hash">SHA-256：'+esc(item.sha256||local?.sha256||'未读取')+'</p>'+checks+(item.notes||[]).map(note=>'<p>'+esc(identityDiagnosticMessage(note))+'</p>').join('');
 if(changed||!identityQueries.has(String(item.key))&&!dirty)$('#identity-query').value=identityQueries.has(String(item.key))?identityQueries.get(String(item.key)):item.query||identityHints(item,local)[0]?.query||local?.name||item.name||'';
 if(changed){$('#identity-site').value='all';identityCandidateSignature='';}
 const diagnostics=$('#identity-search-diagnostics');
 if(diagnostics){
  const html=identitySearchDiagnosticsHTML(item,local),hasCandidates=!!item.candidates?.length;
  if(changed||html!==identityDiagnosticHTML){
   const previous=diagnostics.querySelector?.('.identity-query-details')?.open,focus=document.activeElement;
   const hadFocus=!!diagnostics.contains?.(focus),hint=focus?.closest?.('[data-identity-query-hint]')?.dataset.identityQueryHint;
   diagnostics.innerHTML=html;identityDiagnosticHTML=html;
   const disclosure=diagnostics.querySelector?.('.identity-query-details');
   if(disclosure&&!changed&&identityDiagnosticCandidates===hasCandidates&&typeof previous==='boolean')disclosure.open=previous;
   identityDiagnosticCandidates=hasCandidates;
   if(hadFocus&&!changed){
    const nextHint=hint?Array.from(diagnostics.querySelectorAll?.('[data-identity-query-hint]')||[]).find(button=>button.dataset.identityQueryHint===hint):null;
    const target=nextHint||disclosure?.querySelector?.('summary')||$('.identity-file-details > summary');
    target?.focus?.({preventScroll:true});
   }
  }
  diagnostics.hidden=item.status==='exact';
 }
 $('#identity-query').disabled=!!busy;$('#identity-site').disabled=!!busy;$('#identity-search').disabled=!!busy;$('#identity-search').textContent=item.searching?'正在搜索…':'搜索';
 const candidates=Array.isArray(item.candidates)?item.candidates:[],candidateIds=new Set(candidates.map(candidate=>String(candidate.id)));
 if(!candidateIds.has(identityChoices.get(String(item.key))))identityChoices.delete(String(item.key));
 const signature=JSON.stringify([item.key,candidates,identityChoices.get(String(item.key)),!!busy,item.status,dirty]);
 if(signature!==identityCandidateSignature){
  $('#identity-candidates').innerHTML=candidates.map(candidate=>'<label class="identity-candidate"><input type="radio" name="identity-candidate" data-identity-candidate="'+esc(candidate.id)+'" '+(identityChoices.get(String(item.key))===String(candidate.id)?'checked ':'')+(busy||dirty||item.status==='exact'?'disabled ':'')+'><span><strong>'+esc(candidate.name||'未命名项目')+'</strong><small>'+esc([candidate.provider==='MCIM'?'MCIM 镜像':'',candidate.site,candidate.projectId?'项目 ID：'+candidate.projectId:'',candidate.versionHint].filter(Boolean).join(' · '))+'</small>'+(candidate.summary?'<p>'+esc(candidate.summary)+'</p>':'')+'<span class="identity-candidate-source">'+identityProjectLink(candidate,'查看来源')+'</span></span></label>').join('')||'<p class="identity-candidates-empty">'+(item.status==='exact'?'此文件已精确匹配官方文件，无需人工选择。':item.searching?'正在查找候选项目…':'没有可供确认的候选，请查看上方查询结果。')+'</p>';
  identityCandidateSignature=signature;
 }
 $('#identity-candidate-heading').textContent=dirty?'查询内容或平台已更改，请先搜索':candidates.length?'选择原项目 · '+candidates.length+' 个候选':'原项目候选';
 $('#identity-confirm').disabled=!!busy||dirty||item.status==='exact'||!identityChoices.has(String(item.key));$('#identity-confirm').hidden=item.status==='exact';$('#identity-clear').hidden=!item.confirmation;$('#identity-clear').disabled=!!busy;
 identityRenderedKey=item.key;
}
function renderIdentity(){
 const panel=$('#identity-panel');if(!panel)return;panel.hidden=!identityReport;
 if(!identityReport)return;
 const eligible=identityEligible(),job=identityJob,items=job?.items||[],active=identityActive(),pending=items.filter(identityPending).length;
 $('#identity-check').disabled=identityBusy||active||!eligible.length;$('#identity-check').textContent=identityBusy&&!job?'正在连接…':active?'正在核对文件来源…':job?'重新核对文件来源（不使用 AI）':'核对文件来源（不使用 AI）';$('#identity-cancel').hidden=!active;$('#identity-cancel').disabled=identityBusy;
 $('#identity-summary-count').textContent=job?(pending+' 项待核对'):(eligible.length+' 个可核对文件');
 const statusLabels={running:'正在核对文件来源',complete:'本轮来源核对已完成',cancelled:'来源核对已暂停',failed:'来源核对未完成'};
 $('#identity-job-status').textContent=identityConnection||identityMessage||(job?.message)||statusLabels[job?.status]||'不使用 AI；点击后查询官方平台的文件哈希与项目资料。';
 $('#identity-placeholder').hidden=!!job;$('#identity-placeholder').textContent=eligible.length?'核对后会区分官方文件匹配、用户确认和待确认来源。':(identityReport.mods||[]).some(mod=>mod.kind==='manifest')?'当前主要是下载清单；只有读取实际 JAR 后，才能核对文件来源。':'请重新扫描实际模组目录，读取完整文件哈希后再核对来源。';
 $('#identity-content').hidden=!job;$('#identity-progress').hidden=!active;
 const total=Math.max(0,Number(job?.progress?.total)||0),done=Math.max(0,Number(job?.progress?.done)||0);$('#identity-meter').value=total?Math.min(100,Math.round(done/total*100)):0;$('#identity-progress-text').textContent=done+' / '+total;
 if(job){identityRenderQueue();identityRenderReview();}
}
function identityAccept(job,{refresh=true}={}){
 if(!job||typeof job.id!=='string'||!Array.isArray(job.items))throw Error('未能取得来源核对结果，请重新核对。');
 const changed=identityLabelsSignature(identityJob)!==identityLabelsSignature(job);identityJob=job;identityNeedsValidation=false;identityAttempted=true;identityConnection='';identityFailures=0;
 identitySave();renderIdentity();if(changed&&refresh)identityRefreshLabels();identitySchedulePoll();
}
function identityLoadReport(data){
 const oldJob=identityJob,oldReport=identityReport;identityGeneration++;identityPollGeneration++;clearTimeout(identityPollTimer);identityPolling=false;identityBusy=false;identityConnection='';identityMessage='';identityFailures=0;identityPage=0;identityCurrentKey=null;identityRenderedKey=null;identityCandidateSignature='';identityChoices.clear();identityQueries.clear();identityDirtyQueries.clear();identityNeedsValidation=false;identityReport=data;identityJob=null;identityAttempted=false;identityOrigin='manual';
 if(oldReport&&oldReport!==data&&oldJob&&(oldJob.status==='running'||oldJob.items?.some(item=>item.searching)))api('/api/identity/cancel',{id:oldJob.id}).catch(()=>{});
 const saved=data?.identityReview;if(saved?.revision===1&&saved.stamp===identityStamp(data)){identityJob=saved.job||null;identityAttempted=!!saved.attempted;identityNeedsValidation=!!identityJob;identityOrigin=saved.origin==='auto'?'auto':'manual';}
 $('#identity-filter').value='pending';renderIdentity();if(typeof settingsState!=='undefined'&&settingsState)identitySettingsChanged(settingsState);identitySchedulePoll();
}
function identitySettingsChanged(settings){
 if(settings?.autoSearch||identityOrigin!=='auto'||!identityActive()&&!identityBusy)return;
 const job=identityJob;identityGeneration++;identityPollGeneration++;clearTimeout(identityPollTimer);identityBusy=false;identityNeedsValidation=false;identityAttempted=true;identityConnection='';identityMessage='自动联网已关闭，来源核对已暂停。';
 if(job){identityJob={...job,status:'cancelled',items:(job.items||[]).map(item=>({...item,searching:false}))};api('/api/identity/cancel',{id:job.id}).catch(()=>{});}
 identitySave();renderIdentity();
}
function identityWorkspaceChanged(active){
 identityPollGeneration++;clearTimeout(identityPollTimer);identityPollTimer=null;
 if(active){renderIdentity();identitySchedulePoll(50);if(identityReport&&identityReport===report)void identityMaybeAutoCheck();}
}
function identitySchedulePoll(delay=1600){
 clearTimeout(identityPollTimer);identityPollTimer=null;if(!identityInAnalysis()||!identityActive()&&!identityNeedsValidation)return;
 const epoch=identityGeneration,pollEpoch=identityPollGeneration,current=identityReport,id=identityJob.id;identityPollTimer=setTimeout(()=>identityPoll(current,id,epoch,pollEpoch),delay);
}
function identityMarkExpired(error){
 if(error.code!=='job_not_found')return false;
 identityNeedsValidation=false;identityMessage='';identityJob={...identityJob,status:'failed',expired:true,items:(identityJob.items||[]).map(item=>({...item,searching:false})),message:'来源核对任务已失效，请重新核对。已有用户确认仍保留为人工标记。'};identityChoices.clear();identitySave();renderIdentity();return true;
}
async function identityPoll(current,id,epoch,pollEpoch){
 if(!identityInAnalysis()||current!==identityReport||epoch!==identityGeneration||pollEpoch!==identityPollGeneration||identityJob?.id!==id||!identityActive()&&!identityNeedsValidation)return;
 if(identityPolling){identitySchedulePoll(400);return;}
 identityPolling=true;
 try{const job=await api('/api/identity/status?id='+encodeURIComponent(id));if(current!==identityReport||epoch!==identityGeneration||pollEpoch!==identityPollGeneration||identityJob?.id!==id)return;identityAccept(job);}
 catch(error){
  if(current!==identityReport||epoch!==identityGeneration||pollEpoch!==identityPollGeneration)return;
  if(identityMarkExpired(error))return;
  identityFailures++;identityConnection='连接暂时中断，正在重新同步来源核对状态。';renderIdentity();identitySchedulePoll(Math.min(10000,2000*identityFailures));
 }finally{identityPolling=false;}
}
async function identityMaybeAutoCheck(){
 if(!identityInAnalysis()||identityReport!==report||!identityReport||identityReport.mode==='snapshot'||!settingsState?.autoSearch||identityAttempted||identityBusy||identityJob||!identityEligible().length)return;
 return identityStartCheck('auto');
}
async function identityStartCheck(origin='manual'){
 if(!identityInAnalysis()||identityBusy||identityActive()||!identityEligible().length)return;
 identityOrigin=origin==='auto'?'auto':'manual';
 const current=identityReport,epoch=++identityGeneration;identityPollGeneration++;clearTimeout(identityPollTimer);identityBusy=true;identityAttempted=true;identityMessage='正在连接官方平台核对文件来源…';identityChoices.clear();identityDirtyQueries.clear();identityNeedsValidation=false;identityCandidateSignature='';identitySave();renderIdentity();
 const mods=identityEligible().map(mod=>({key:mod.key,name:mod.name,file:mod.file,kind:mod.kind,sha1:mod.sha1,sha256:mod.sha256,cfFingerprint:mod.cfFingerprint,version:mod.version,loader:mod.loader,components:mod.components||[]}));
 try{const job=await api('/api/identity/check',{mods});if(current!==identityReport||epoch!==identityGeneration){if(job?.id)api('/api/identity/cancel',{id:job.id}).catch(()=>{});return;}identityMessage='';identityAccept(job);}
 catch(error){if(current===identityReport&&epoch===identityGeneration){identityConnection='来源核对未能开始：'+error.message;identitySave();}}
 finally{if(current===identityReport&&epoch===identityGeneration){identityBusy=false;renderIdentity();}}
}
async function identitySearch(){
 const item=identityItem(),query=$('#identity-query').value.trim();if(!item||identityBusy||item.searching||item.status==='checking'||identityJob?.expired||!identityInAnalysis())return;
 if(!query){identityMessage='请填写项目名称或官方项目链接。';renderIdentity();$('#identity-query').focus();return;}
 const current=identityReport,id=identityJob.id,key=item.key,epoch=identityGeneration;identityPollGeneration++;clearTimeout(identityPollTimer);identityBusy=true;identityMessage='正在查找候选项目…';identityQueries.set(String(key),$('#identity-query').value);identityChoices.delete(String(key));renderIdentity();
 try{const job=await api('/api/identity/search',{id,key,query,site:$('#identity-site').value||'all'});if(current!==identityReport||epoch!==identityGeneration||identityJob?.id!==id)return;identityDirtyQueries.delete(String(key));identityMessage='候选仅供选择，请核对后确认原项目。';identityAccept(job);}
 catch(error){if(current===identityReport&&epoch===identityGeneration){if(!identityMarkExpired(error))identityMessage='搜索未完成：'+error.message;}}
 finally{if(current===identityReport&&epoch===identityGeneration){identityBusy=false;renderIdentity();}}
}
async function identityConfirm(){
 const item=identityItem(),candidateId=identityChoices.get(String(item?.key)),candidate=item?.candidates?.find(candidate=>String(candidate.id)===candidateId);
 if(!item||!candidate||identityBusy||item.searching||item.status==='checking'||item.status==='exact'||identityJob?.expired||identityDirtyQueries.has(String(item.key))||!identityInAnalysis())return;
 const current=identityReport,id=identityJob.id,key=item.key,epoch=identityGeneration;identityPollGeneration++;clearTimeout(identityPollTimer);identityBusy=true;renderIdentity();
 try{const job=await api('/api/identity/confirm',{id,key,candidateId:candidate.id});if(current!==identityReport||epoch!==identityGeneration||identityJob?.id!==id)return;identityMessage='已关联原项目：'+(candidate.name||'所选项目')+'（用户确认）。';identityChoices.delete(String(key));identityAccept(job);
  const pending=(job.items||[]).filter(identityPending),next=pending.find(next=>String(next.key)!==String(key));if(next){$('#identity-filter').value='pending';identityCurrentKey=next.key;identityPage=Math.floor(pending.findIndex(item=>String(item.key)===String(next.key))/identityPageSize);}else{$('#identity-filter').value='confirmed';identityPage=0;identityCurrentKey=key;}renderIdentity();
 }catch(error){if(current===identityReport&&epoch===identityGeneration){if(!identityMarkExpired(error))identityMessage='确认未完成：'+error.message;}}
 finally{if(current===identityReport&&epoch===identityGeneration){identityBusy=false;renderIdentity();}}
}
async function identityClear(){
 const item=identityItem();if(!item?.confirmation||identityBusy||item.searching||identityJob?.expired||!identityInAnalysis())return;
 const current=identityReport,id=identityJob.id,key=item.key,epoch=identityGeneration;identityPollGeneration++;clearTimeout(identityPollTimer);identityBusy=true;renderIdentity();
 try{const job=await api('/api/identity/clear',{id,key});if(current!==identityReport||epoch!==identityGeneration||identityJob?.id!==id)return;identityMessage='已撤销用户确认，本地文件和依赖保持原样。';identityChoices.delete(String(key));$('#identity-filter').value='pending';identityCurrentKey=key;identityPage=0;identityAccept(job);}
 catch(error){if(current===identityReport&&epoch===identityGeneration){if(!identityMarkExpired(error))identityMessage='撤销未完成：'+error.message;}}
 finally{if(current===identityReport&&epoch===identityGeneration){identityBusy=false;renderIdentity();}}
}
async function identityCancel(){
 if(!identityJob||!identityActive()||identityBusy)return;
 const current=identityReport,id=identityJob.id,epoch=identityGeneration;identityBusy=true;identityPollGeneration++;clearTimeout(identityPollTimer);renderIdentity();
 try{const job=await api('/api/identity/cancel',{id});if(current!==identityReport||epoch!==identityGeneration||identityJob?.id!==id)return;identityMessage='来源核对已暂停，可重新核对。';identityAccept(job);}
 catch(error){if(current===identityReport&&epoch===identityGeneration){identityMessage='暂停未完成：'+error.message;identitySchedulePoll();}}
 finally{if(current===identityReport&&epoch===identityGeneration){identityBusy=false;renderIdentity();}}
}
$('#identity-check').addEventListener('click',identityStartCheck);$('#identity-cancel').addEventListener('click',identityCancel);$('#identity-search').addEventListener('click',identitySearch);$('#identity-confirm').addEventListener('click',identityConfirm);$('#identity-clear').addEventListener('click',identityClear);
$('#identity-filter').addEventListener('change',()=>{identityPage=0;identityCurrentKey=null;identityChoices.clear();renderIdentity();});
$('#identity-prev').addEventListener('click',()=>{identityPage=Math.max(0,identityPage-1);identityCurrentKey=null;renderIdentity();});$('#identity-next').addEventListener('click',()=>{identityPage++;identityCurrentKey=null;renderIdentity();});
$('#identity-queue').addEventListener('click',event=>{const button=event.target.closest('[data-identity-key]');if(!button)return;if(String(identityCurrentKey)!==button.dataset.identityKey)identityChoices.clear();identityCurrentKey=button.dataset.identityKey;renderIdentity();});
$('#identity-query').addEventListener('input',()=>{if(identityCurrentKey!==null){identityQueries.set(String(identityCurrentKey),$('#identity-query').value);identityChoices.delete(String(identityCurrentKey));identityDirtyQueries.add(String(identityCurrentKey));identityRenderReview();}});
$('#identity-site').addEventListener('change',()=>{if(identityCurrentKey!==null){identityChoices.delete(String(identityCurrentKey));identityDirtyQueries.add(String(identityCurrentKey));identityRenderReview();}});$('#identity-query').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();identitySearch();}});
$('#identity-candidates').addEventListener('change',event=>{const input=event.target.closest('input[data-identity-candidate]'),item=identityItem();if(!input||!input.checked||!item||identityBusy||item.searching||identityJob?.expired||identityDirtyQueries.has(String(item.key))||item.status==='exact'||!item.candidates?.some(candidate=>String(candidate.id)===input.dataset.identityCandidate))return;identityChoices.set(String(item.key),input.dataset.identityCandidate);identityRenderReview();});
renderIdentity();

$('#identity-search-diagnostics')?.addEventListener('click',event=>{
 const button=event.target.closest('[data-identity-query-hint]'),item=identityItem();if(!button||!item||identityBusy||item.searching||item.status==='checking'||identityJob?.expired||!identityInAnalysis())return;
 const local=identityReport?.mods?.find(mod=>String(mod.key)===String(item.key)),query=button.dataset.identityQueryHint;if(!identityHints(item,local).some(hint=>hint.query===query))return;
 $('#identity-query').value=query;identityQueries.set(String(item.key),query);identityChoices.delete(String(item.key));identityDirtyQueries.add(String(item.key));identityRenderReview();void identitySearch();
});
