/* Shared feedback popup bridge. */
(() => {
 'use strict';
 const popup=document.getElementById('damn-feedback-popup');if(!popup)return;
 const copy=popup.querySelector('.feedback-copy'),icon=popup.querySelector('.feedback-icon'),selector='[data-feedback-notice],[data-feedback-errors-only],[role="alert"]',snapshots=new WeakMap();
 let closed=false,timer=null,source=null,route='';
 const state=el=>({text:el.textContent.trim(),error:el.classList.contains('error')||el.classList.contains('is-error')||el.dataset.kind==='error'||el.dataset.type==='error'||el.dataset.state==='error'||el.getAttribute('role')==='alert'});
 const visible=el=>!!el&&!el.hidden&&!el.closest('[hidden]')&&!el.closest('dialog:not([open])')&&window.getComputedStyle(el).display!=='none';
 const silent=(el,s)=>!s.error&&(el.dataset.feedbackErrorsOnly!==undefined||!!el.dataset.feedbackSilentPrefix&&s.text.startsWith(el.dataset.feedbackSilentPrefix));
 const seed=()=>document.querySelectorAll(selector).forEach(el=>snapshots.set(el,state(el)));
 seed();
 function release(el){if(!el)return;if(el.dataset.feedbackFloating){delete el.dataset.feedbackFloating;el.dataset.feedbackConsumed='true';}}
 function dismiss(){clearTimeout(timer);timer=null;release(source);source=null;if(typeof popup.hidePopover==='function'){try{if(popup.matches(':popover-open'))popup.hidePopover();}catch{}}delete popup.dataset.fallbackOpen;}
 function duration(){const err=popup.dataset.kind==='error',len=(copy.textContent||'').length,extra=Math.min(err?2400:1900,Math.max(0,len-28)*45);return (err?3600:2600)+extra;}
 function expires(){clearTimeout(timer);timer=null;if(closed||!source)return;timer=setTimeout(dismiss,duration());}
 function place(){const bar=document.querySelector('.workspace-topbar'),bottom=bar?Math.max(0,bar.getBoundingClientRect().bottom):68;popup.style.setProperty('--feedback-top',Math.min(bottom+12,Math.max(12,window.innerHeight-120))+'px');}
 function announce(kind){try{const r=popup.getBoundingClientRect();document.dispatchEvent(new CustomEvent('damn-feedback-shown',{detail:{kind,left:r.left,top:r.top,width:r.width,height:r.height}}));}catch{}}
 function inspect(el,repeat){
  const next=state(el),prior=snapshots.get(el);snapshots.set(el,next);if(closed)return;
  const changed=!prior||prior.text!==next.text||prior.error!==next.error;
  const eligible=!document.hidden&&!!next.text&&visible(el)&&!silent(el,next);
  if(!eligible){if(el===source)dismiss();if(changed)delete el.dataset.feedbackConsumed;return;}
  if(!changed&&!repeat)return;
  if(source&&source!==el)release(source);
  source=el;delete el.dataset.feedbackConsumed;el.dataset.feedbackFloating='true';
  const kind=next.error?'error':/扫描完成|设置已保存|测试成功|连接成功|补全完成|下载完成/.test(next.text)?'success':'info';
  copy.textContent=next.text;icon.textContent=kind==='error'?'!':kind==='success'?'✓':'i';popup.dataset.kind=kind;place();
  if(typeof popup.showPopover==='function'){try{if(!popup.matches(':popover-open'))popup.showPopover();}catch{popup.dataset.fallbackOpen='true';}}else popup.dataset.fallbackOpen='true';
  let hovered=false;try{hovered=popup.matches(':hover');}catch{}
  if(hovered){clearTimeout(timer);timer=null;}else expires();
  announce(kind);
 }
 function syncRoute(){const workspace=document.body.dataset.workspace,category=workspace==='settings'?(document.getElementById('settings-dialog')?.dataset.settingsCategory||''):'';const now=workspace+'/'+(document.querySelector('.sidebar [aria-current="page"]')?.dataset.view||'')+'/'+category;if(now!==route){route=now;dismiss();}place();}
 const observer=new MutationObserver(records=>{if(closed)return;const changed=new Map();let routeChanged=false;for(const record of records){if(record.type==='attributes'&&(record.target===document.body||record.attributeName==='aria-current'||record.attributeName==='data-settings-category'))routeChanged=true;const el=record.target.nodeType===1?record.target:record.target.parentElement,n=el?.closest?.(selector);if(n)changed.set(n,changed.get(n)||record.type!=='attributes');for(const node of record.addedNodes||[]){if(node.nodeType!==1)continue;if(node.matches(selector))changed.set(node,true);node.querySelectorAll(selector).forEach(n=>changed.set(n,true));}}if(routeChanged)syncRoute();for(const [n,repeat] of changed)inspect(n,repeat);if(source&&!visible(source))dismiss();});
 function watch(){observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class','hidden','aria-current','data-workspace','data-settings-category','role','data-kind','data-type','data-state','open']});}
 function escape(event){if(event.key==='Escape')dismiss();}function pause(){clearTimeout(timer);timer=null;}function resume(){expires();}function visibility(){if(document.hidden)dismiss();}
 function listen(){popup.addEventListener('pointerenter',pause);popup.addEventListener('pointerleave',resume);document.addEventListener('visibilitychange',visibility);window.addEventListener('resize',place,{passive:true});window.addEventListener('keydown',escape,{passive:true});}
 function suspend(){if(closed)return;closed=true;observer.disconnect();dismiss();popup.removeEventListener('pointerenter',pause);popup.removeEventListener('pointerleave',resume);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('resize',place);window.removeEventListener('keydown',escape);}
 function restore(event){if(!event.persisted||!closed)return;closed=false;route='';seed();listen();watch();syncRoute();}
 window.addEventListener('pagehide',suspend);window.addEventListener('pageshow',restore);listen();watch();syncRoute();
})();
