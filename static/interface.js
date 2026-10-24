'use strict';
(() => {
 const byId=id=>document.getElementById(id);
 const overview=byId('view-overview'),importPanel=byId('analysis-import-panel'),importToggle=byId('analysis-import-toggle');
 let hasReport=false,lastRunning=false;
 function choosePanel(name){
  const identity=name==='identity';overview.dataset.overviewPanel=identity?'identity':'mods';
  byId('overview-mods-open').setAttribute('aria-pressed',String(!identity));
  byId('overview-identity-open').setAttribute('aria-pressed',String(identity));
  byId('overview-panel-hint').textContent=identity?'匹配与人工确认':'用途与文件声明';
 }
 function showImport(open){
  const expanded=!!open||!hasReport,wasInside=importPanel.contains(document.activeElement);
  importPanel.hidden=!expanded;importToggle.setAttribute('aria-expanded',String(expanded));
  importToggle.innerHTML='<svg class="ui-icon import-toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 11h18"/></svg><span class="import-toggle-label">'+(expanded?'收起导入区域':'展开导入区域')+'</span><svg class="ui-icon import-toggle-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>';
  importToggle.title=expanded?'收起导入区域，继续查看当前结果':'展开导入区域，选择整合包或重新扫描';
  if(!expanded&&wasInside){const heading=document.querySelector('.overview-heading h1');heading?.focus({preventScroll:true});}
 }
 window.damnShowImport=showImport;
 window.damnSyncInterface=(data,newReport=false)=>{
  hasReport=!!data;document.body.dataset.hasReport=String(hasReport);
  importToggle.hidden=!hasReport;byId('pack-mode').hidden=!hasReport;byId('analysis-empty').hidden=hasReport;
  if(newReport){lastRunning=false;byId('enrich-panel').open=false;showImport(!hasReport);choosePanel('mods');}
  else showImport(!hasReport||!importPanel.hidden);
 };
 window.damnSyncEnrichmentDisclosure=running=>{
  const panel=byId('enrich-panel');panel.dataset.running=String(running);
  // Open once when a task starts; polling preserves the user's disclosure choice.
  if(running!==lastRunning){
   const summary=panel.querySelector('summary');
   const focusInside=panel.contains(document.activeElement)&&!summary?.contains(document.activeElement);
   panel.open=running;
   if(!running&&focusInside)summary?.focus({preventScroll:true});
  }
  lastRunning=running;
 };
 importToggle.addEventListener('click',()=>showImport(importPanel.hidden));
 byId('overview-mods-open').addEventListener('click',()=>choosePanel('mods'));
 byId('overview-identity-open').addEventListener('click',()=>choosePanel('identity'));
 const heading=document.querySelector('.overview-heading h1');if(heading)heading.tabIndex=-1;
 window.damnSyncInterface(typeof report==='undefined'?null:report,true);
})();
