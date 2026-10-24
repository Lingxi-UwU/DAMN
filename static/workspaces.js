'use strict';
let damnWorkspace='home',damnSettingsReturnWorkspace='home',damnSettingsReturnScroll=0;
let prerequisiteJob=null,prerequisiteStamp='',prerequisiteSelection=new Set(),prerequisiteTimer=null,prerequisiteEpoch=0,prerequisiteBusy=false,prerequisiteFailures=0,prerequisiteConnection='';
function prerequisiteInput(){return {path:$('#prerequisite-path').value.trim(),side:$('#prerequisite-side').value,gameVersion:$('#prerequisite-minecraft').value.trim(),loader:$('#prerequisite-loader').value,loaderVersion:$('#prerequisite-loader-version').value.trim()};}
function prerequisiteInputStamp(){return JSON.stringify(prerequisiteInput());}
function prerequisiteActive(job=prerequisiteJob){return !!job&&['planning','installing'].includes(job.status);}
function prerequisiteReady(){return (prerequisiteJob?.items||[]).filter(item=>item.status==='ready');}
function prerequisiteCurrent(){return !!prerequisiteStamp&&prerequisiteStamp===prerequisiteInputStamp();}
function prerequisiteCanInstall(){return !!prerequisiteJob&&prerequisiteJob.status==='ready'&&!prerequisiteJob.needsEnvironment&&prerequisiteCurrent()&&!prerequisiteBusy&&prerequisiteReady().some(item=>prerequisiteSelection.has(String(item.id)));}
function prerequisiteFormatBytes(bytes){return Number(bytes)>0?(Number(bytes)/1048576>=1?(Number(bytes)/1048576).toFixed(1)+' MB':Math.ceil(Number(bytes)/1024)+' KB'):'';}
function prerequisiteNotice(message,error=false){const el=$('#prerequisite-notice');el.textContent=message;el.classList.toggle('error',!!error);}
function prerequisiteSource(item){const url=safeWebURL(item.sourceUrl);return url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(item.sourceSite||'查看来源')+' ↗</a>':'<span>'+esc(item.sourceSite||'来源待确认')+'</span>';}
function renderPrerequisiteSelection(){
 const ready=prerequisiteReady(),count=ready.filter(item=>prerequisiteSelection.has(String(item.id))).length,installing=prerequisiteJob?.status==='installing',invalid=!!prerequisiteJob&&!prerequisiteCurrent(),complete=prerequisiteJob?.status==='complete';
 $('#prerequisite-stale').hidden=!invalid;
 $('#prerequisite-selection').hidden=!ready.length;
 $('#prerequisite-select-all').checked=!!ready.length&&count===ready.length;$('#prerequisite-select-all').indeterminate=count>0&&count<ready.length;$('#prerequisite-select-all').disabled=prerequisiteActive()||prerequisiteBusy||invalid;
 $('#prerequisite-selection-count').textContent='已选 '+count+' / '+ready.length+' 项';
 $('#prerequisite-install').disabled=!prerequisiteCanInstall();$('#prerequisite-install').hidden=complete||!!prerequisiteJob&&prerequisiteJob.status!=='ready';
 $('#prerequisite-install').textContent=prerequisiteBusy&&prerequisiteJob?.status==='ready'?'正在准备补全…':'补全所选前置'+(count?'（'+count+'）':'');
 $('#prerequisite-install-summary').textContent=installing?'正在补全，请稍候':complete?'本次补全已结束':invalid?'请重新识别当前目录':count?'已选择 '+count+' 项前置':'没有选中的可补全前置';
 $('#prerequisite-install-path').textContent=prerequisiteJob?.modsDir?'目标目录：'+prerequisiteJob.modsDir:'';
 $('#prerequisite-open-analysis').hidden=!complete||invalid||!prerequisiteJob?.modsDir;
 $('#prerequisite-items').querySelectorAll('input[data-prerequisite-item]').forEach(el=>{el.checked=prerequisiteSelection.has(el.dataset.prerequisiteItem);el.disabled=prerequisiteActive()||prerequisiteBusy||invalid;});
}
function renderPrerequisites(){
 const job=prerequisiteJob,active=prerequisiteActive();
 $('#prerequisite-plan').disabled=active||prerequisiteBusy;$('#prerequisite-plan').textContent=prerequisiteBusy&&!active?'正在连接…':job?.status==='planning'?'正在识别…':job?'重新识别':'识别缺失前置 ↗';
 for(const id of ['#prerequisite-path','#prerequisite-side','#prerequisite-minecraft','#prerequisite-loader','#prerequisite-loader-version'])$(id).disabled=job?.status==='installing';
 $('#prerequisite-status').hidden=!job;$('#prerequisite-results').hidden=!job||job.status==='planning';$('#prerequisite-placeholder').hidden=!!job;
 if(!job)return;
 const labels={planning:'正在识别',ready:job.needsEnvironment?'等待补充环境':'核对完成',installing:'正在补全',complete:'补全完成',cancelled:'任务已取消',failed:'任务未完成'};
 $('#prerequisite-state-tag').textContent=labels[job.status]||'任务状态';$('#prerequisite-status').dataset.status=job.status;
 const phaseLabels={scanning:'读取本地模组',identifying:'匹配平台资料',resolving:'核对缺失前置',downloading:'下载并校验前置',validating:'检查文件与前置关系',installing:'写入 mods 目录',complete:'前置补全已完成',ready:labels.ready,cancelled:'任务已取消',failed:'任务未完成'};
 $('#prerequisite-phase').textContent=phaseLabels[job.phase]||(/[\u4e00-\u9fff]/.test(String(job.phase||''))?job.phase:labels[job.status]||'前置核对');$('#prerequisite-message').textContent=prerequisiteConnection||job.message||'';
 const done=Math.max(0,Number(job.progress?.done)||0),total=Math.max(0,Number(job.progress?.total)||0),percent=total?Math.min(100,Math.round(done/total*100)):0;
 $('#prerequisite-progress-text').textContent=total?done+' / '+total+' 项':active?'正在准备':'本次任务已结束';$('#prerequisite-percent').textContent=total?percent+'%':'';
 if(active&&!total)$('#prerequisite-meter').removeAttribute('value');else $('#prerequisite-meter').value=total?percent:100;
 $('#prerequisite-cancel').hidden=!active;$('#prerequisite-cancel').disabled=prerequisiteBusy;
 const env=job.environment||{},loaderNames={neoforge:'NeoForge',forge:'Forge',fabric:'Fabric',quilt:'Quilt'};
 $('#prerequisite-environment-summary').textContent=[env.minecraft?'Minecraft '+env.minecraft:'游戏版本待确认',[loaderNames[String(env.loader||'').toLowerCase()]||env.loader||'加载器待确认',env.loaderVersion].filter(Boolean).join(' '),JSON.parse(prerequisiteStamp||'{}').side==='server'?'服务端':'客户端'].join(' · ');
 $('#prerequisite-environment-warning').hidden=!job.needsEnvironment;if(job.needsEnvironment)$('#prerequisite-advanced').open=true;
 const items=Array.isArray(job.items)?job.items:[],ready=items.filter(item=>item.status==='ready').length,installed=items.filter(item=>item.status==='installed').length,blocked=items.filter(item=>item.status==='blocked').length,present=items.filter(item=>item.status==='present').length;
 $('#prerequisite-result-counts').innerHTML=[['可补全',ready],['已补全',installed],['需核对',blocked+(job.unresolved||[]).length],['已满足',present]].filter(row=>row[1]).map(row=>'<span><b>'+row[1]+'</b>'+row[0]+'</span>').join('');
 const notes=Array.isArray(job.notes)?job.notes:[];$('#prerequisite-notes').hidden=!notes.length;$('#prerequisite-notes').innerHTML=notes.map(note=>'<p>'+esc(note)+'</p>').join('');
 const statusNames={ready:'可补全',installed:'已补全',blocked:'需人工核对',present:'已满足'};
 $('#prerequisite-items').innerHTML=items.map(item=>{
  const selectable=item.status==='ready',by=(item.requiredBy||[]).map(by=>typeof by==='string'?by:by?.name||by?.target||'').filter(Boolean),fileDetails=[item.version,item.fileName,prerequisiteFormatBytes(item.bytes)].filter(Boolean).join(' · ');
  return '<article class="prerequisite-item" data-status="'+esc(item.status)+'">'+(selectable?'<label class="prerequisite-item-check"><input type="checkbox" data-prerequisite-item="'+esc(item.id)+'" aria-label="选择 '+esc(item.name)+'"></label>':'<span class="prerequisite-item-symbol" aria-hidden="true">'+(item.status==='installed'||item.status==='present'?'✓':'!')+'</span>')+'<div class="prerequisite-item-copy"><div class="prerequisite-item-title"><h3>'+esc(item.name||'未命名前置')+'</h3><span class="prerequisite-item-state">'+esc(statusNames[item.status]||'待核对')+'</span></div>'+(fileDetails?'<p class="prerequisite-item-file">'+esc(fileDetails)+'</p>':'')+(by.length?'<p class="prerequisite-required-by"><span>被谁需要</span>'+esc(by.join('、'))+'</p>':'')+(item.reason?'<p class="prerequisite-item-reason">'+esc(item.reason)+'</p>':'')+'<div class="prerequisite-item-source">'+prerequisiteSource(item)+'</div></div></article>';
 }).join('');
 const unresolved=Array.isArray(job.unresolved)?job.unresolved:[];$('#prerequisite-unresolved').hidden=!unresolved.length;$('#prerequisite-unresolved').innerHTML=unresolved.length?'<h3>还需要人工核对</h3>'+unresolved.map(item=>'<article><strong>'+esc(item.target||'未知前置')+'</strong><p>'+esc(item.reason||'暂时无法匹配适用文件')+'</p>'+(item.requiredBy?.length?'<small>被谁需要：'+esc((Array.isArray(item.requiredBy)?item.requiredBy:[item.requiredBy]).map(x=>typeof x==='string'?x:x?.name||'').join('、'))+'</small>':'')+'</article>').join(''):'';
 $('#prerequisite-empty').hidden=active||job.needsEnvironment||!!items.some(item=>item.status!=='present')||!!unresolved.length||job.status!=='ready';
 renderPrerequisiteSelection();
}
function acceptPrerequisiteJob(state,{selectReady=false}={}){
 if(!state||typeof state.id!=='string')throw Error('未能取得任务状态，请重新识别。');
 prerequisiteJob=state;prerequisiteConnection='';prerequisiteFailures=0;
 const readyIds=new Set(prerequisiteReady().map(item=>String(item.id)));
 prerequisiteSelection=selectReady?readyIds:new Set([...prerequisiteSelection].filter(id=>readyIds.has(id)));
 renderPrerequisites();schedulePrerequisitePoll();
}
function schedulePrerequisitePoll(delay=1500){
 clearTimeout(prerequisiteTimer);prerequisiteTimer=null;
 if(!prerequisiteActive())return;
 const id=prerequisiteJob.id,epoch=prerequisiteEpoch;
 prerequisiteTimer=setTimeout(()=>pollPrerequisites(id,epoch),delay);
}
async function pollPrerequisites(id,epoch){
 if(epoch!==prerequisiteEpoch||prerequisiteJob?.id!==id||!prerequisiteActive())return;
 try{const state=await api('/api/prerequisites/status?id='+encodeURIComponent(id));if(epoch!==prerequisiteEpoch||prerequisiteJob?.id!==id)return;const becameReady=prerequisiteJob.status==='planning'&&state.status==='ready';acceptPrerequisiteJob(state,{selectReady:becameReady});}
 catch(error){
  if(epoch!==prerequisiteEpoch||prerequisiteJob?.id!==id)return;
  if(error.code==='job_not_found'){prerequisiteJob={...prerequisiteJob,status:'failed',phase:'任务已失效',message:'服务已重新启动，请重新识别当前目录。'};renderPrerequisites();return;}
  prerequisiteFailures++;prerequisiteConnection='连接暂时中断，正在重新同步任务状态。';renderPrerequisites();schedulePrerequisitePoll(Math.min(10000,2000*prerequisiteFailures));
 }
}
async function planPrerequisites(){
 if(prerequisiteBusy||prerequisiteActive())return;
 const input=prerequisiteInput();if(!input.path){prerequisiteNotice('请先填写实例目录或 mods 目录。',true);$('#prerequisite-path').focus();return;}
 if(/\.(zip|mrpack|modpack)$/i.test(input.path.replace(/["']$/,''))){prerequisiteNotice('前置补全需要已解压的目录，请填写实例或 mods 目录路径。',true);return;}
 prerequisiteBusy=true;prerequisiteEpoch++;clearTimeout(prerequisiteTimer);const epoch=prerequisiteEpoch;prerequisiteStamp=prerequisiteInputStamp();prerequisiteSelection.clear();prerequisiteJob=null;renderPrerequisites();prerequisiteNotice('正在读取目录并核对前置…');
 try{const state=await api('/api/prerequisites/plan',input);if(epoch!==prerequisiteEpoch)return;acceptPrerequisiteJob(state,{selectReady:true});prerequisiteNotice('已开始核对，可在下方查看进度。');}
 catch(error){if(epoch===prerequisiteEpoch){prerequisiteNotice(error.message,true);prerequisiteStamp='';}}
 finally{if(epoch===prerequisiteEpoch){prerequisiteBusy=false;renderPrerequisites();}}
}
async function installPrerequisites(){
 if(!prerequisiteCanInstall())return;
 prerequisiteBusy=true;clearTimeout(prerequisiteTimer);const epoch=++prerequisiteEpoch,id=prerequisiteJob.id,itemIds=prerequisiteReady().filter(item=>prerequisiteSelection.has(String(item.id))).map(item=>item.id);renderPrerequisites();
 try{const state=await api('/api/prerequisites/install',{id,itemIds});if(epoch!==prerequisiteEpoch)return;acceptPrerequisiteJob(state);prerequisiteNotice('已确认补全，将写入下方的 mods 目录。');}
 catch(error){if(epoch===prerequisiteEpoch){prerequisiteNotice(error.message,true);schedulePrerequisitePoll();}}
 finally{if(epoch===prerequisiteEpoch){prerequisiteBusy=false;renderPrerequisites();}}
}
async function cancelPrerequisites(){
 if(!prerequisiteActive()||prerequisiteBusy)return;
 prerequisiteBusy=true;clearTimeout(prerequisiteTimer);const epoch=++prerequisiteEpoch,id=prerequisiteJob.id;renderPrerequisites();
 try{const state=await api('/api/prerequisites/cancel',{id});if(epoch!==prerequisiteEpoch)return;acceptPrerequisiteJob(state);prerequisiteNotice('任务已取消。');}
 catch(error){if(epoch===prerequisiteEpoch){prerequisiteNotice(error.message,true);schedulePrerequisitePoll();}}
 finally{if(epoch===prerequisiteEpoch){prerequisiteBusy=false;renderPrerequisites();}}
}
function renderWorkspaceNavigation(){
 const analysis=damnWorkspace==='analysis';$('#analysis-page-navigation').hidden=false;
 for(const [id,workspace] of [['workspace-home-open','home'],['workspace-prerequisites-open','prerequisites'],['settings-open','settings']]){
  const button=$('#'+id),current=damnWorkspace===workspace;button.classList.toggle('active',current);if(current)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
 }
 $$('.nav[data-view]').forEach(button=>{const current=analysis&&button.dataset.view===analysisCurrentView;button.classList.toggle('active',current);if(current)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
 
}
function damnShowSettings(){
 if(damnWorkspace!=='settings'){damnSettingsReturnWorkspace=damnWorkspace;damnSettingsReturnScroll=Math.max(0,Number(window.scrollY)||0);}
 void damnChooseWorkspace('settings');
}
function damnSettingsAfterLayout(callback){if(typeof window.requestAnimationFrame==='function')window.requestAnimationFrame(callback);else callback();}
function damnSettingsReady(openEpoch){
 damnSettingsAfterLayout(()=>{if(damnWorkspace==='settings'&&openEpoch===settingsOpenEpoch&&typeof window.scrollTo==='function')window.scrollTo({left:0,top:0,behavior:'instant'});});
}
async function damnReturnFromSettings(){
 if(damnWorkspace!=='settings')return;
 const workspace=['home','analysis','prerequisites'].includes(damnSettingsReturnWorkspace)?damnSettingsReturnWorkspace:'home',top=damnSettingsReturnScroll;
 const navigation=damnChooseWorkspace(workspace),epoch=settingsOpenEpoch;await navigation;
 damnSettingsAfterLayout(()=>{if(damnWorkspace===workspace&&epoch===settingsOpenEpoch&&typeof window.scrollTo==='function')window.scrollTo({left:0,top,behavior:'instant'});});
}
async function damnChooseWorkspace(workspace,view){
 if(!['home','analysis','prerequisites','settings'].includes(workspace))return;
 if(workspace!=='settings'&&typeof cancelPendingSettings==='function')cancelPendingSettings();
 damnWorkspace=workspace;document.body.dataset.workspace=workspace;
 $('#workspace-home').hidden=workspace!=='home';$('#workspace-prerequisites').hidden=workspace!=='prerequisites';$('#analysis-workspace').hidden=workspace!=='analysis';$('#workspace-settings').hidden=workspace!=='settings';
 document.body.classList.remove('network-view','issues-view');
 $('#current-view-label').textContent=workspace==='home'?'工具入口':workspace==='prerequisites'?'前置补全':workspace==='settings'?'设置':'整合包总览';
 if(workspace==='analysis'){showView(view||analysisCurrentView);renderWorkspaceNavigation();await setAnalysisWorkspaceActive(true);}
 else{renderWorkspaceNavigation();void setAnalysisWorkspaceActive(false);if(workspace==='prerequisites')renderPrerequisites();}
}
$('#workspace-enter-analysis').addEventListener('click',()=>damnChooseWorkspace('analysis'));
$('#workspace-enter-prerequisites').addEventListener('click',()=>damnChooseWorkspace('prerequisites'));
$('#workspace-home-open').addEventListener('click',()=>damnChooseWorkspace('home'));
$('#workspace-prerequisites-open').addEventListener('click',()=>damnChooseWorkspace('prerequisites'));
$('.brand').addEventListener('click',event=>{event.preventDefault();damnChooseWorkspace('home');});
$('#prerequisite-plan').addEventListener('click',planPrerequisites);
$('#prerequisite-path').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();planPrerequisites();}});
for(const id of ['#prerequisite-path','#prerequisite-side','#prerequisite-minecraft','#prerequisite-loader','#prerequisite-loader-version'])$(id).addEventListener(id==='#prerequisite-path'||id==='#prerequisite-minecraft'||id==='#prerequisite-loader-version'?'input':'change',()=>{if(prerequisiteJob)renderPrerequisiteSelection();});
$('#prerequisite-select-all').addEventListener('change',event=>{if(prerequisiteActive()||prerequisiteBusy||!prerequisiteCurrent())return;prerequisiteSelection=event.target.checked?new Set(prerequisiteReady().map(item=>String(item.id))):new Set();renderPrerequisiteSelection();});
$('#prerequisite-items').addEventListener('change',event=>{const input=event.target.closest('input[data-prerequisite-item]');if(!input||prerequisiteActive()||prerequisiteBusy||!prerequisiteCurrent())return;const id=input.dataset.prerequisiteItem;if(!prerequisiteReady().some(item=>String(item.id)===id))return;if(input.checked)prerequisiteSelection.add(id);else prerequisiteSelection.delete(id);renderPrerequisiteSelection();});
$('#prerequisite-install').addEventListener('click',installPrerequisites);
$('#prerequisite-cancel').addEventListener('click',cancelPrerequisites);
$('#prerequisite-open-analysis').addEventListener('click',async()=>{if(prerequisiteJob?.status!=='complete'||!prerequisiteCurrent()||!prerequisiteJob.modsDir)return;const path=prerequisiteJob.modsDir,side=prerequisiteInput().side;await damnChooseWorkspace('analysis');$('#pack-path').value=path;$('#side').value=side;if(typeof damnShowImport==='function')damnShowImport(true);notice('已填入补全后的 mods 目录，点击“开始扫描”查看分析。');});
renderWorkspaceNavigation();
renderPrerequisites();
