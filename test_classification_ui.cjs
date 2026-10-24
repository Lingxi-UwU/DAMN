const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const c=require('./static/catalog.js'),elements={};let requests=0,timers=0;
const report={mods:[{key:'one',name:'Save My Shit Network',enrichmentComplete:true,aiPurpose:'阻止常见模组联网且不影响其功能。'},{key:'two',name:'Unknown',enrichmentComplete:true}],classificationSession:{id:'old-paid-job'}};
const ctx={...c,report,settingsState:{autoSearch:false},enrichment:null,document:{querySelector:id=>elements[id]??={textContent:'',addEventListener(){}},addEventListener:(event,fn)=>fn()},refreshMetadata(){},persistReport(){},api:async(route,body)=>{assert.equal(route,'/api/categories/resolve');requests++;return {updates:body.mods.map((m,i)=>({key:m.key,records:m.key==='one'?[{site:'Modrinth',categories:['utility','utility'],matched:true}]:[],checkedAt:1}))};},setInterval:()=>timers++,setTimeout:()=>timers++};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('./static/classification.js','utf8'),ctx);
(async()=>{
 vm.runInContext('resetClassification()',ctx);
 for(let i=0;i<30;i++)await vm.runInContext('syncClassification()',ctx);
 assert.equal(requests,0,'offline mode does not make automatic requests');
 ctx.settingsState={autoSearch:true};await vm.runInContext('syncClassification()',ctx);
 assert.equal(requests,1);assert.equal(c.damnCategoryInfo(report.mods[0]).category,'实用工具');
 assert.equal(c.damnCategoryInfo(report.mods[0]).categories.length,1,'duplicate official slugs do not create duplicate facets');
 for(let i=0;i<30;i++)await vm.runInContext('syncClassification()',ctx);
 assert.equal(requests,1,'missing project must not trigger polling storms');
 await vm.runInContext('startClassification(true)',ctx);assert.equal(requests,2,'explicit retry can refresh unresolved entries');
 assert.equal(timers,0);assert.equal(report.classificationSession,null);assert.match(elements['#classification-mode'].textContent,/不调用 AI/);
 console.log('Free platform category UI passed: no AI calls, no automatic offline requests, no repeated failed lookups, explicit retry and old session removal.');
})();
