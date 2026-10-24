const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const helpers=require('./static/progress.js'),catalog=require('./static/catalog.js');
const full=fs.readFileSync('./static/app.js','utf8'),script=full.slice(full.indexOf('let enrichPollTimer='));
function mod(i,english=false){return {key:String(i),name:'Library '+i,file:'mods/lib-'+i+'.jar',kind:'jar',version:'1.0',components:[],dependencies:[],description:english?'A local English description':'中文简介',enrichmentComplete:true,resolutionStatus:'matched',onlineResearch:[{identity:{description:''},sources:[{url:'https://modrinth.com/mod/'+i}]}],aiAnnotation:{summary:'中文用途'},aiReviewStatus:'done'};}
function fixture(revision=3){
 const calls=[],elements={},settings={revision:'saved',autoSearch:true,configured:true,hasKey:true,endpoint:'http://localhost:1/v1',model:'stub'};
 const report={pack:'Regression',created:'fixed',mode:'archive',mods:Array.from({length:278},(_,i)=>mod(i,i===3||i===8)),enrichmentAttemptStamp:helpers.damnConfigStamp(settings)};
 const completed={id:'old-job',requestId:'r',scope:'pack',status:'complete',phase:'补全完成',pipelineRevision:revision,total:2,done:2,aiDone:2,aiTotal:2,aiBatch:0,cursor:2,hasMore:false,updates:[]};
 report.enrichmentSummary={...completed};
 let nonce=0;
 const ctx={...helpers,...catalog,effectiveCategory:m=>catalog.damnCategoryInfo(m).category,report,enrichment:{...completed},settingsState:settings,crypto:{randomUUID:()=>String(++nonce)},Date,Math,JSON,console,document:{hidden:false,addEventListener(){}},window:{addEventListener(){}},setInterval(){},setTimeout(){return 1;},clearTimeout(){},
  $:id=>elements[id]??=( {addEventListener(){},textContent:'',hidden:false,disabled:false,value:0} ),persistReport(){},refreshMetadata(){},updateAIButtons(){},notice(){},openSettings:async()=>{},setSettingsStatus(){},
  applyPatch(key,patch){Object.assign(report.mods.find(m=>m.key===key),patch);},
  api:async(route,body)=>{
   calls.push({route,body});
   if(route==='/api/settings')return settings;
   if(route.startsWith('/api/enrich/current'))return {job:null};
   if(route==='/api/enrich/cancel')return completed;
   if(route==='/api/enrich/start'){
    const updates=body.mods.map(m=>({key:m.key,patch:{descriptionZh:'已完成本地简介的中文翻译',translationAttempted:true,aiReviewStatus:'done'}}));
    return {...completed,id:'new-job',pipelineRevision:3,requestId:body.requestId,scope:body.scope,cursor:updates.length,updates};
   }
   throw Error('Unexpected route '+route);
  }};
 vm.createContext(ctx);vm.runInContext(script,ctx);return {ctx,calls,elements,report,settings,completed,run:code=>vm.runInContext(code,ctx)};
}
(async()=>{
 let f=fixture(1);await f.run('maybeAutoEnrich()');
 for(let i=0;i<20;i++)await f.run('syncEnrichmentState(true)');
 assert.equal(f.calls.filter(c=>c.route==='/api/enrich/start').length,1,'legacy task upgraded once, never restarted by the watchdog');
 assert(f.report.mods[3].descriptionZh);assert(f.report.mods[8].descriptionZh);
 assert.equal(f.elements['#enrich-percent'].textContent,'100% · 278 / 278');
 assert.equal(f.elements['#enrich-ai-percent'].textContent,'100% · 278 / 278');
 f=fixture(3);
 for(let i=0;i<20;i++)await f.run('syncEnrichmentState(true)');
 assert.equal(f.calls.filter(c=>c.route==='/api/enrich/start').length,0,'completed job never loops, even with an unresolved record');
 await f.run('renderEnrichment()');
 assert.equal(f.elements['#enrich-percent'].textContent,'100% · 278 / 278');
 assert.equal(f.elements['#enrich-ai-percent'].textContent,'99% · 276 / 278');
 f=fixture(3);f.settings.revision='changed';await f.run('maybeAutoEnrich(true)');
 assert.equal(f.calls.filter(c=>c.route==='/api/enrich/start').length,1,'new configuration may resume pending work');
 f=fixture(3);f.ctx.enrichment.hasMore=true;await f.run('maybeAutoEnrich(true)');
 assert.equal(f.calls.filter(c=>c.route==='/api/enrich/start').length,0,'must drain pending result pages before restarting');
 f=fixture(3);f.ctx.enrichment.status='running';f.ctx.enrichment.waitingForConfig=true;await f.run('maybeAutoEnrich()');
 assert.equal(f.calls.filter(c=>c.route==='/api/enrich/start').length,0,'late setup retains the current task');
 f=fixture(3);f.ctx.enrichment.cursor=10;await f.run('consumeEnrichment({...enrichment,cursor:2,updates:[{key:"3",patch:{name:"stale"}}]})');
 assert.notEqual(f.report.mods[3].name,'stale','old snapshots cannot overwrite newer results');
 f=fixture(3);f.ctx.enrichment.status='running';await f.run('renderEnrichment()');
 assert.equal(f.elements['#enrich-run'].hidden,true);assert.equal(f.elements['#enrich-stop'].hidden,false);
 f.ctx.enrichment.status='cancelled';await f.run('renderEnrichment()');
 assert.equal(f.elements['#enrich-run'].hidden,false);assert.equal(f.elements['#enrich-stop'].hidden,true);assert.equal(f.elements['#enrich-run-label'].textContent,'继续未完成项');
 f=fixture(3);for(const m of f.report.mods){m.descriptionZh='中文简介';m.aiPurpose='提供简单的示例功能。';m.purposeAttemptedRevision=1;}await f.run('renderEnrichment()');
 assert.equal(f.elements['#enrich-run'].hidden,true);assert.equal(f.elements['#enrich-done'].hidden,false);
 f.ctx.enrichment.aiError='API unavailable';await f.run('renderEnrichment()');assert.equal(f.elements['#enrich-run'].hidden,false);assert.equal(f.elements['#enrich-done'].hidden,true);
 console.log('UI regressions passed: 20 watchdog ticks do not restart completed jobs; legacy tasks recover once; 278-item progress stays cumulative; config changes, late API setup, pagination and stale results are handled.');
})().catch(e=>{console.error(e);process.exitCode=1;});
