'use strict';
function damnConfigStamp(s){return JSON.stringify([s?.revision||'',s?.endpoint||'',s?.model||'',!!s?.hasKey,!!s?.configured,!!s?.autoSearch]);}
function damnNeedsTranslation(m){const text=m.platformInfo?.description||m.originalDescription||m.description||'';return /[a-zA-Z]{3}/.test(text)&&!/[\u4e00-\u9fff]/.test(text)&&!m.descriptionZh;}
function purposeHelpers(){return typeof damnPurposeEligible==='function'?{damnPurposeEligible,damnNeedsPurpose}:require('./catalog.js');}
function damnPendingMod(m,retry=false){
 if(!m.enrichmentComplete)return true;
 const purpose=purposeHelpers(),eligible=purpose.damnPurposeEligible(m),missingPurpose=eligible&&purpose.damnNeedsPurpose(m),translation=damnNeedsTranslation(m);
 return missingPurpose&&(retry||m.purposeAttemptedRevision!==1)||translation&&(retry||!m.translationAttempted&&m.purposeAttemptedRevision!==1)||retry&&m.resolutionStatus!=='matched';
}
function damnPercent(done,total){return total?done>=total?100:Math.floor(done/total*100):0;}
function damnProgress(s,mods=null){
 if(Array.isArray(mods)){
  const sourced=m=>purposeHelpers().damnPurposeEligible(m);
  const done=mods.filter(m=>m.enrichmentComplete).length;
  const aiTotal=mods.filter(m=>!m.enrichmentComplete||sourced(m)).length;
  const aiDone=mods.filter(m=>m.enrichmentComplete&&sourced(m)&&!damnPendingMod(m)).length;
  return {total:mods.length,done,aiTotal,aiDone,search:damnPercent(done,mods.length),ai:damnPercent(aiDone,aiTotal),
   matched:mods.filter(m=>m.resolutionStatus==='matched').length,candidates:mods.filter(m=>m.resolutionStatus==='candidate').length,failed:mods.filter(m=>m.resolutionStatus==='failed').length};
 }

 const total=Math.max(0,Number(s?.total)||0),done=Math.min(total,Math.max(0,Number(s?.done)||0));
 const aiTotal=Math.max(0,Number(s?.aiTotal)||0),aiDone=Math.min(aiTotal,Math.max(0,Number(s?.aiDone)||0));
 return {total,done,aiTotal,aiDone,search:damnPercent(done,total),ai:damnPercent(aiDone,aiTotal)};
}
function damnAutoReady(s,configChanged=false){
 if(s?.hasMore)return false;
 if(s&&(s.status==='running'||s.status==='reconnecting'))return !!(configChanged&&s.aiError);
 return !(s?.status==='complete'&&s.pipelineRevision===3&&!configChanged);
}
function damnDuration(value){
 const seconds=Math.max(0,Math.round(Number(value)||0));
 return seconds<60?seconds+' 秒':seconds<3600?Math.floor(seconds/60)+' 分'+(seconds%60?' '+seconds%60+' 秒':''):Math.floor(seconds/3600)+' 小时 '+Math.ceil(seconds%3600/60)+' 分';
}
function damnSpeed(s){
 if(!s)return '中文用途整理 · 最多 2 批并行 · 完成结果自动复用';
 const parts=[];
 if(s.waitingForConfig)parts.push('平台资料已保留，保存 API 后继续');
 else if(s.aiWorkers)parts.push(s.aiWorkers+' 批正在处理','最长已等待 '+damnDuration(s.aiCurrentSeconds));
 else parts.push(s.status==='complete'?'批量处理已结束':'中文用途整理 · 最多 '+(s.aiConcurrency||2)+' 批并行');
 if(s.aiLastBatchSeconds!=null)parts.push('上批 '+damnDuration(s.aiLastBatchSeconds));
 if(s.aiCacheHits)parts.push('已复用 '+s.aiCacheHits+' 项');
 if(s.aiEtaSeconds!=null&&s.aiEtaSeconds>0&&s.status==='running')parts.push('预计还需约 '+damnDuration(s.aiEtaSeconds));
 else if(s.aiWorkers&&!(s.aiBatchesCompleted>=2))parts.push('处理几批后估算剩余时间');
 return parts.join(' · ');
}
if(typeof module!=='undefined')module.exports={damnConfigStamp,damnNeedsTranslation,damnPendingMod,damnProgress,damnAutoReady,damnDuration,damnSpeed};
