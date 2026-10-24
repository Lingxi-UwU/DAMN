'use strict';
// Platform categories are free project metadata; no AI endpoints or new timers.
let categoryLookupBusy=false,categoryLookupEpoch=0,categoryLookupDone=0,categoryLookupTotal=0,categoryLookupMessage='';
function categoryLookupStamp(m){return JSON.stringify([m.name,m.file,m.sha1,m.manifest,m.platformInfo?.projectIds]);}
function renderClassification(){
 const el=document.querySelector('#classification-mode');if(!el)return;
 const mods=typeof report!=='undefined'&&report?report.mods:[],matched=mods.filter(m=>damnPlatformClassification(m).labels.length).length;
 el.textContent=categoryLookupBusy?'免费补查平台分类 · '+categoryLookupDone+' / '+categoryLookupTotal:mods.length?'平台分类 '+matched+' / '+mods.length+' · 其余使用本地推断或待识别 · 不调用 AI'+(categoryLookupMessage?' · '+categoryLookupMessage:''):'基础分类免费 · 平台标签优先，本地规则兜底，不调用 AI';
 const button=document.querySelector('#category-refresh');if(button){button.disabled=categoryLookupBusy||!mods.length;button.textContent=categoryLookupBusy?'补查中…':'补全平台分类';}
}
function resetClassification(){
 categoryLookupEpoch++;categoryLookupMessage='';
 if(report){report.classificationSession=null;report.classificationStartRequest=null;report.classificationPausedUser=true;}
 renderClassification();
}
async function syncClassification(){
 if(typeof settingsState==='undefined'||!settingsState?.autoSearch||!report||report.mode==='snapshot')return;
 if(typeof enrichment!=='undefined'&&enrichment?.status==='running'&&!enrichment.lookupComplete)return;
 return startClassification(false);
}
async function startClassification(force=false){
 if(!report||categoryLookupBusy||!force&&!settingsState?.autoSearch)return;
 const current=report,epoch=categoryLookupEpoch;
 const pending=report.mods.filter(m=>!damnPlatformClassification(m).labels.length&&(force||m.enrichmentComplete&&m.platformCategoryCheck?.stamp!==categoryLookupStamp(m)));
 if(!pending.length){renderClassification();return;}
 categoryLookupBusy=true;categoryLookupDone=0;categoryLookupTotal=pending.length;categoryLookupMessage='';renderClassification();
 try{
  for(let i=0;i<pending.length;i+=6){
   if(current!==report||epoch!==categoryLookupEpoch)break;
   const batch=pending.slice(i,i+6),stamps=new Map(batch.map(m=>[m.key,categoryLookupStamp(m)]));
   const mods=batch.map(m=>({key:m.key,name:m.originalName||m.name,file:m.file,sha1:m.sha1,resolutionStatus:m.resolutionStatus,manifest:m.manifest?{projectID:m.manifest.projectID,fileID:m.manifest.fileID,hashes:m.manifest.hashes,downloads:(m.manifest.downloads||[]).slice(0,3)}:undefined,platformInfo:m.platformInfo?{title:m.platformInfo.title,exact:m.platformInfo.exact,projectIds:m.platformInfo.projectIds}:undefined,onlineResearch:(m.onlineResearch||[]).filter(r=>r.identity?.exact).map(r=>({identity:r.identity}))}));
   const result=await api('/api/categories/resolve',{mods});
   if(current!==report||epoch!==categoryLookupEpoch)break;
   const updates=new Map((result.updates||[]).map(update=>[update.key,update]));
   for(const m of batch){const update=updates.get(m.key);if(update?.records?.length)m.platformTaxonomy=update.records;m.platformCategoryCheck={stamp:stamps.get(m.key),checkedAt:update?.checkedAt||Date.now()/1000,notes:update?.notes||[],revision:1};}
   categoryLookupDone+=batch.length;refreshMetadata();renderClassification();
  }
 }catch(error){
  if(current===report&&epoch===categoryLookupEpoch){for(const m of pending)if(m.platformCategoryCheck?.stamp!==categoryLookupStamp(m))m.platformCategoryCheck={stamp:categoryLookupStamp(m),checkedAt:Date.now()/1000,notes:['分类连接未完成，可手动重试。'],revision:1};categoryLookupMessage='连接未完成，可手动重试';persistReport();}
 }finally{categoryLookupBusy=false;renderClassification();}
}
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',()=>{document.querySelector('#category-refresh')?.addEventListener('click',()=>startClassification(true));renderClassification();});
