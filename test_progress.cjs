const assert=require('node:assert/strict');
const {damnConfigStamp,damnNeedsTranslation,damnPendingMod,damnProgress}=require('./static/progress.js');
assert.notEqual(damnConfigStamp({revision:'before'}),damnConfigStamp({revision:'after'}));
assert(damnPendingMod({enrichmentComplete:false}));
const english={enrichmentComplete:true,onlineResearch:[{sources:[{url:'https://modrinth.com/mod/a'}]}],aiAnnotation:{summary:'中文用途'},platformInfo:{description:'An addon for Create'}};
assert(damnNeedsTranslation(english));assert(damnPendingMod(english));
assert(!damnPendingMod({...english,translationAttempted:true,aiReviewStatus:'done'}));
assert(!damnNeedsTranslation({...english,descriptionZh:'机械动力附属模组'}));
assert.equal(damnProgress({total:278,done:246}).search,88);
assert.equal(damnProgress({total:278,done:278,aiTotal:237,aiDone:0}).ai,0);
assert.equal(damnProgress({total:0,done:0}).search,0);
console.log('Progress checks passed: late config changes, English translation queue, no repeated automatic billing, 246/278 = 88%, independent AI progress.');

const {damnSpeed,damnDuration}=require('./static/progress.js');
assert.equal(damnDuration(75),'1 分 15 秒');
assert.match(damnSpeed({status:'running',aiWorkers:2,aiCurrentSeconds:12,aiLastBatchSeconds:10,aiEtaSeconds:60,aiBatchesCompleted:2,aiCacheHits:3}),/2 批正在处理/);
assert.match(damnSpeed({status:'running',aiEtaSeconds:60}),/预计还需约 1 分/);
assert(!damnSpeed({status:'complete',aiEtaSeconds:60}).includes('预计'));
assert.match(damnSpeed({aiCacheHits:3}),/已复用 3 项/);
assert.match(damnSpeed({aiWorkers:1,aiBatchesCompleted:0}),/处理几批后/);

const {damnAutoReady}=require('./static/progress.js');
assert(!damnAutoReady({status:'complete',pipelineRevision:3}));
assert(damnAutoReady({status:'complete',pipelineRevision:1}));
assert(damnAutoReady({status:'complete',pipelineRevision:2},true));
assert(!damnAutoReady({status:'complete',pipelineRevision:2,hasMore:true},true));
const pack=Array.from({length:278},(_,i)=>({key:String(i),enrichmentComplete:true,resolutionStatus:'matched',onlineResearch:[{sources:[{url:'https://modrinth.com/mod/'+i}]}],aiAnnotation:{summary:'说明'},aiReviewStatus:'done',description:'中文简介'}));
for(const i of [3,8]){pack[i].description='An English local description';pack[i].translationAttempted=false;delete pack[i].descriptionZh;}
let cumulative=damnProgress({total:2,done:0,aiTotal:0,aiDone:0},pack);
assert.equal(cumulative.total,278);assert.equal(cumulative.done,278);assert.equal(cumulative.search,100);assert.equal(cumulative.aiDone,276);assert.equal(cumulative.aiTotal,278);
pack[3].descriptionZh='中文译文';pack[8].translationAttempted=true;
cumulative=damnProgress({total:2,done:2,aiTotal:2,aiDone:2},pack);assert.equal(cumulative.ai,100);

assert.equal(damnProgress({total:278,done:277}).search,99);assert.equal(damnProgress({aiTotal:278,aiDone:277}).ai,99);

const localOnly={kind:'jar',description:'Add placeable beer mug and drink it!',enrichmentComplete:true,resolutionStatus:'failed',onlineResearch:[]};
assert(damnPendingMod(localOnly));
assert(!damnPendingMod({...localOnly,purposeAttemptedRevision:1}));
assert(damnPendingMod({...localOnly,purposeAttemptedRevision:1},true));
assert(!damnAutoReady({status:'complete',pipelineRevision:3}));
assert(damnAutoReady({status:'complete',pipelineRevision:2}));
