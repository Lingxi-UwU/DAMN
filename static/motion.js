/* DAMN public interface. Rebuild with node tools/assemble.mjs. */

/* Source: home-motion.js */
'use strict';
/* Opus homepage interactions: state-driven feedback, isolated from importing. */
(() => {
 'use strict';
 const root=document.getElementById('workspace-home');
 if(!root?.classList?.contains('hm-root'))return;
 const reduce=window.matchMedia?.('(prefers-reduced-motion: reduce)');
 const fine=window.matchMedia?.('(hover: hover) and (pointer: fine)');
 const animations=new Map();
 let keyboard=false,pressed=null,lastCard=null,destroyed=false;
 const atHome=()=>document.body.dataset.workspace==='home'&&!document.hidden;
 const canMove=()=>!destroyed&&atHome()&&!reduce?.matches;
 function cancelFor(element){const old=animations.get(element);if(old){animations.delete(element);old.onfinish=null;old.oncancel=null;old.cancel();}}
 function cancelAll(){for(const element of [...animations.keys()])cancelFor(element);pressed=null;}
 function play(element,keyframes,options){
  if(!element||!canMove()||typeof element.animate!=='function')return;
  cancelFor(element);
  const animation=element.animate(keyframes,options);animations.set(element,animation);
  const release=()=>{if(animations.get(element)===animation)animations.delete(element);animation.onfinish=null;animation.oncancel=null;animation.cancel();};
  animation.onfinish=release;animation.oncancel=()=>{if(animations.get(element)===animation)animations.delete(element);};
 }
 const notice=document.getElementById('home-notice'),tray=document.getElementById('home-dropzone');
 const source=e=>{const card=e.target?.closest?.('.hm-card');if(card&&root.contains(card))lastCard=card;};
 function pointerDown(event){
  keyboard=false;source(event);
  const button=event.target?.closest?.('[data-hm-squish]');
  if(!button||!root.contains(button)||button.disabled||event.button>0||!canMove())return;
  if(pressed)cancelFor(pressed.target);
  const target=button.querySelector('.hm-face')||button;
  pressed={button,target,pointerId:event.pointerId};
  play(target,[{transform:window.getComputedStyle(target).transform},{transform:'translateY(4px) scale(1.035,.94)'}],{duration:120,easing:'ease-out',fill:'forwards'});
 }
 function releasePress(event){
  if(!pressed||(event.pointerId!==undefined&&event.pointerId!==pressed.pointerId))return;
  const {button,target}=pressed;pressed=null;
  if(event.type==='pointercancel'||button.disabled||!canMove()){cancelFor(target);return;}
  const end=target===button&&fine?.matches&&button.matches(':hover')?'translateY(-2px)':'none';
  play(target,[{transform:window.getComputedStyle(target).transform},{transform:'translateY(-2px) scale(.97,1.045)',offset:.42},{transform:'translateY(1px) scale(1.012,.99)',offset:.7},{transform:end}],{duration:390,easing:'ease-out'});
 }
 function onKey(event){keyboard=true;source(event);if(pressed){cancelFor(pressed.target);pressed=null;}}
 function folderFocus(){if(keyboard)return;play(root.querySelector('.hm-flap'),[{transform:'none'},{transform:'scaleY(.35)',offset:.35},{transform:'scaleY(1.12)',offset:.7},{transform:'none'}],{duration:520,easing:'cubic-bezier(.3,1.4,.5,1)'});}
 let previousError=notice.classList.contains('error'),previousText=notice.textContent;
 const noticeObserver=new MutationObserver(records=>{
  const error=notice.classList.contains('error'),text=notice.textContent;
  const textMutation=records.some(record=>record.type==='childList'||record.type==='characterData');
  if(error===previousError&&text===previousText&&!textMutation)return;
  const showError=error&&(!previousError||text!==previousText||textMutation);
  previousError=error;previousText=text;
  if(!text.trim()||notice.hidden||!canMove())return;
  if(showError){
   play(lastCard||root.querySelector('.hm-path'),[{transform:'none'},{transform:'translateX(-8px) rotate(-.5deg)',offset:.15},{transform:'translateX(7px) rotate(.4deg)',offset:.35},{transform:'translateX(-5px)',offset:.55},{transform:'translateX(3px)',offset:.75},{transform:'none'}],{duration:480,easing:'ease-out'});
  }
 });
 noticeObserver.observe(notice,{attributes:true,attributeFilter:['class','hidden'],childList:true,characterData:true,subtree:true});
 let dragging=tray.classList.contains('dragging');
 function syncDrag(){
  const next=tray.classList.contains('dragging');
  tray.querySelector('.hm-idle')?.setAttribute('aria-hidden',String(next));
  tray.querySelector('.hm-live')?.setAttribute('aria-hidden',String(!next));
  if(next&&!dragging)play(tray,[{transform:'scale(1)'},{transform:'scale(1.045,1.01)',offset:.4},{transform:'scale(1.01,1.03)',offset:.7},{transform:'scale(1.02)'}],{duration:460,easing:'ease-out'});
  if(!next&&dragging)cancelFor(tray);
  dragging=next;
 }
 const dragObserver=new MutationObserver(syncDrag);dragObserver.observe(tray,{attributes:true,attributeFilter:['class']});
 function synchronize(){
  const pause=!atHome()||!!reduce?.matches;
  root.classList.toggle('hm-paused',pause);
  if(pause){cancelAll();if(!atHome())tray.classList.remove('dragging');}
 }
 const routeObserver=new MutationObserver(synchronize);routeObserver.observe(document.body,{attributes:true,attributeFilter:['data-workspace']});
 root.addEventListener('pointerdown',pointerDown,true);
 root.addEventListener('drop',source,true);
 window.addEventListener('pointerup',releasePress,{passive:true});
 window.addEventListener('pointercancel',releasePress,{passive:true});
 window.addEventListener('keydown',onKey,{passive:true});
 const input=document.getElementById('home-pack-path');input.addEventListener('focus',folderFocus);
 document.addEventListener('visibilitychange',synchronize);
 reduce?.addEventListener?.('change',synchronize);
 function destroy(){
  if(destroyed)return;destroyed=true;cancelAll();
  noticeObserver.disconnect();dragObserver.disconnect();routeObserver.disconnect();
  root.removeEventListener('pointerdown',pointerDown,true);root.removeEventListener('drop',source,true);
  window.removeEventListener('pointerup',releasePress);window.removeEventListener('pointercancel',releasePress);window.removeEventListener('keydown',onKey);
  input.removeEventListener('focus',folderFocus);document.removeEventListener('visibilitychange',synchronize);reduce?.removeEventListener?.('change',synchronize);
 }
 window.addEventListener('pagehide',destroy,{once:true});
 synchronize();
})();



/* Source: feedback.js */
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


/* Source: suite-ui.js */
(function(){
var b=document.body;if(!b||!b.classList||!b.classList.contains('opus-suite'))return;
if(window.__osSuiteUi)return;window.__osSuiteUi=1;
var t=0,last='',fr=0,gen=0,dead=false,susp=false;
var L=[],O=[],T=new Set();
function on(tg,ty,fn,o){L.push([tg,ty,fn,o]);if(!susp)tg.addEventListener(ty,fn,o)}
function attachAll(){L.forEach(function(x){x[0].addEventListener(x[1],x[2],x[3])})}
function detachAll(){L.forEach(function(x){x[0].removeEventListener(x[1],x[2],x[3])})}
function observe(make){var e={make:make,ob:null};O.push(e);if(!susp)e.ob=make();return e}
function connectAll(){O.forEach(function(e){if(!e.ob)e.ob=e.make()})}
function disconnectAll(){O.forEach(function(e){if(e.ob){e.ob.disconnect();e.ob=null}})}
function later(fn,ms){var id=setTimeout(function(){T.delete(id);fn()},ms);T.add(id);return id}
function routeOf(){var r=b.dataset.workspace||'home';if(r==='analysis')r=b.classList.contains('network-view')?'network':b.classList.contains('issues-view')?'issues':'overview';return r}
function fit(){var nat=b.getAttribute('data-desktop-host')==='true',sc=nat?document.querySelector('body>.app'):null,lim=sc?sc.offsetTop+sc.clientHeight:0,empty=nat&&b.getAttribute('data-has-report')!=='true';[['.os-split',420],['.os-net-sheet',440],['.checks-scroll',280]].forEach(function(p){document.querySelectorAll(p[0]).forEach(function(el){if(!el.getClientRects().length)return;var top=0,cursor=el;while(cursor){top+=cursor.offsetTop||0;cursor=cursor.offsetParent;}var v;if(sc){var floor=empty&&p[0]==='.os-net-sheet'?300:p[1];v=Math.max(floor,Math.floor(lim-top-(empty?8:12)))+'px';}else v=Math.max(p[1],Math.round(window.innerHeight-top-24))+'px';if(el.style.getPropertyValue('--os-fit')!==v)el.style.setProperty('--os-fit',v)})})}
function kickFit(){if(fr)return;fr=requestAnimationFrame(function(){fr=0;fit()})}
function route(){var r=routeOf();if(r===last)return;last=r;b.dataset.osRoute=r;release(false);b.classList.remove('os-routing');void b.offsetWidth;b.classList.add('os-routing');gen++;if(t){clearTimeout(t);T.delete(t)}t=later(function(){t=0;b.classList.remove('os-routing');fit()},420);kickFit()}

/* ---- tactile layer ---- */
var PAGES={overview:1,network:1,issues:1,prerequisites:1,settings:1};
var ROOTS='#analysis-workspace,#workspace-prerequisites,#workspace-settings';
var mq=window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)'):null;
function rm(){return !!(mq&&mq.matches)}
function live(){return !!PAGES[b.dataset.osRoute]&&!document.hidden&&!susp&&!dead}
var lastAct=0;function mark(){lastAct=Date.now()}function recent(){return Date.now()-lastAct<1200}
var anims=new WeakMap(),running=new Set();
/* content-level reveals follow the home hm-rise family, a step lighter than the surface entrance */
var RISE_SOFT='cubic-bezier(.3,1.25,.5,1)',RISE_LIST='cubic-bezier(.3,1.3,.5,1)';
var CH={e:['opacity','translate'],s:['scale'],i:['transform'],c:['backgroundColor']};
function play(el,key,kf,opt){if(!el||!el.animate||!el.isConnected||susp||dead)return null;var m=anims.get(el);if(!m){m={};anims.set(el,m)}var p=m[key];if(p){var cs=getComputedStyle(el),f=Object.assign({},kf[0]);(CH[key]||[]).forEach(function(n){if(n in f)f[n]=cs[n]});p.onfinish=p.oncancel=null;running.delete(p);m[key]=null;try{p.cancel()}catch(e){}kf=[f].concat(kf.slice(1));opt=Object.assign({},opt,{delay:0})}var a;try{a=el.animate(kf,opt)}catch(e){return null}m[key]=a;running.add(a);var done=function(){a.onfinish=a.oncancel=null;if(m[key]===a)m[key]=null;running.delete(a)};a.onfinish=done;a.oncancel=done;return a}
function cancelAll(){Array.from(running).forEach(function(a){try{a.cancel()}catch(e){}});running.clear()}
function enter(el,dy,dur){if(!el)return;if(rm()){play(el,'e',[{opacity:0},{opacity:1}],{duration:160,easing:'ease-out'});return}play(el,'e',[{opacity:0,translate:'0 '+(dy||10)+'px'},{opacity:1,translate:'0 0'}],{duration:dur||460,easing:RISE_SOFT})}
function stagger(list){if(!list||rm())return;var k=list.slice(0,12);k.forEach(function(c,i){play(c,'e',[{opacity:0,translate:'0 10px'},{opacity:1,translate:'0 0'}],{duration:460,delay:i*34,easing:RISE_LIST,fill:'backwards'})})}
function seat(el){if(!el||rm())return;play(el,'s',[{scale:'1'},{scale:'.94',offset:.25},{scale:'1.04',offset:.6},{scale:'1'}],{duration:360,easing:'ease-out'})}
function pop(el,amt){if(!el||rm())return;play(el,'s',[{scale:'1'},{scale:String(amt||1.08),offset:.4},{scale:'1'}],{duration:340,easing:'cubic-bezier(.3,1.4,.5,1)'})}
function flash(el){if(!el)return;play(el,'c',[{backgroundColor:'rgba(169,208,143,.55)'},{backgroundColor:getComputedStyle(el).backgroundColor}],{duration:450,easing:'ease-out'})}

function ctl(n){if(!n||!n.closest)return null;var el=n.closest('button,summary,[role=button]');if(!el||!el.closest(ROOTS)||el.closest('#network-graph'))return null;if(el.disabled||el.getAttribute('aria-disabled')==='true')return null;return el}
var pressed=null,pid=null,via='';
function press(el,how,id){if(pressed&&pressed!==el)release(false);pressed=el;via=how;pid=id;el.setAttribute('data-os-press','')}
function release(commit){var el=pressed;pressed=null;pid=null;via='';if(!el)return;el.removeAttribute('data-os-press');if(commit&&el.isConnected&&!el.disabled&&live())afterRelease(el)}
function arrowOf(el){var s=el.querySelectorAll(':scope > span');for(var i=0;i<s.length;i++){if((s[i].textContent||'').trim()==='\u2197')return s[i]}return null}
function afterRelease(el){if(rm())return;var id=el.id,ic=el.querySelector(':scope > svg.ui-icon'),ar=arrowOf(el);
if(id==='enrich-refresh'&&ic)play(ic,'i',[{transform:'rotate(0deg)'},{transform:'rotate(-360deg)'}],{duration:520,easing:'cubic-bezier(.3,.9,.3,1)'});
else if(id==='enrich-run'&&ic)play(ic,'i',[{transform:'none'},{transform:'translateX(3px)',offset:.4},{transform:'none'}],{duration:320,easing:'ease-out'});
else if(id==='network-zoom-in')pop(el,1.12);
else if(id==='network-zoom-out')pop(el,.88);
else if(id==='network-fit')play(el,'s',[{scale:'1'},{scale:'1.06',offset:.3},{scale:'.98',offset:.6},{scale:'1'}],{duration:380,easing:'ease-out'});
else if(ar)play(ar,'i',[{transform:'none'},{transform:'translate(3px,-3px)',offset:.35},{transform:'none'}],{duration:340,easing:'ease-out'});
else if(ic)play(ic,'i',[{transform:'none'},{transform:'scale(1.18) rotate(-6deg)',offset:.35},{transform:'none'}],{duration:340,easing:'ease-out'})}

var CP={capture:true,passive:true};
on(document,'pointerdown',function(e){if(e.button!==0||!e.isPrimary)return;if(e.target&&e.target.closest&&e.target.closest(ROOTS))mark();var el=ctl(e.target);if(!el||!live())return;press(el,'p',e.pointerId)},CP);
on(document,'pointerup',function(e){if(pressed&&via==='p'&&e.pointerId===pid)release(pressed.contains(e.target))},CP);
on(document,'pointercancel',function(){if(via==='p')release(false)},CP);
on(document,'pointerout',function(e){if(!pressed||via!=='p'||e.pointerId!==pid)return;if(!pressed.contains(e.target))return;if(e.relatedTarget&&pressed.contains(e.relatedTarget))return;release(false)},CP);
on(document,'keydown',function(e){if(e.repeat||(e.key!=='Enter'&&e.key!==' '))return;if(e.target&&e.target.closest&&e.target.closest(ROOTS))mark();var el=ctl(e.target);if(!el||el!==e.target||!live())return;press(el,'k',null)},CP);
on(document,'keyup',function(e){if(via==='k'&&(e.key==='Enter'||e.key===' '))release(true)},CP);
on(document,'focusout',function(e){if(pressed&&via==='k'&&e.target===pressed)release(false)},CP);
on(window,'blur',function(){release(false)});
function teardown(){gen++;release(false);cancelAll();b.classList.remove('os-routing')}
function suspend(){susp=true;detachAll();disconnectAll();T.forEach(function(id){clearTimeout(id)});T.clear();t=0;if(fr){cancelAnimationFrame(fr);fr=0}}
function kill(){suspend();dead=true;window.removeEventListener('pagehide',onHide);window.removeEventListener('pageshow',onShow);if(mqLegacy&&mq.removeListener)mq.removeListener(mqc)}
function onHide(e){teardown();suspend();if(!e.persisted)kill()}
function onShow(e){if(!e.persisted||dead||!susp)return;susp=false;attachAll();connectAll();baseline();route();kickFit()}
on(document,'visibilitychange',function(){if(document.hidden)teardown()});
window.addEventListener('pagehide',onHide);
window.addEventListener('pageshow',onShow);

/* filter reset: soft confirm on the fields it actually reset */
on(document,'click',function(e){var r=e.target&&e.target.closest&&e.target.closest('#filters-reset');if(!r||!live())return;var g=gen,rt=b.dataset.osRoute;later(function(){if(g!==gen||dead||susp||!live()||b.dataset.osRoute!==rt)return;['#search','#category','#feature','#status'].forEach(function(s){var f=document.querySelector(s);if(f&&f.getClientRects().length)flash(f)})},0)},CP);
/* native checkbox real change */
on(document,'change',function(e){var x=e.target;if(!x||x.type!=='checkbox'||!x.closest(ROOTS)||!live()||rm())return;play(x,'s',[{scale:'1'},{scale:'.8',offset:.3},{scale:'1.15',offset:.65},{scale:'1'}],{duration:320,easing:'ease-out'})},CP);
/* disclosure: native open untouched; only children fade */
on(document,'toggle',function(e){var d=e.target;if(!d||d.tagName!=='DETAILS'||!d.open||!d.closest(ROOTS)||!live())return;var k=Array.prototype.filter.call(d.children,function(c){return c.tagName!=='SUMMARY'}).slice(0,6);k.forEach(function(c,i){if(rm()){play(c,'e',[{opacity:0},{opacity:1}],{duration:160})}else play(c,'e',[{opacity:0,translate:'0 -6px'},{opacity:1,translate:'0 0'}],{duration:380,delay:i*40,easing:RISE_SOFT,fill:'backwards'})})},true);

/* state observers */
var REVEAL={'prerequisite-status':1,'prerequisite-results':1,'prerequisite-empty':1,'prerequisite-environment-warning':1,'prerequisite-stale':1,'prerequisite-cancel':1,'prerequisite-open-analysis':1,'identity-content':1,'identity-review-body':1,'identity-progress':1,'enrich-done':1};
var READY={'prerequisite-install':1,'identity-confirm':1};
var lastSel=null,lastView=null,tagText='';
function onAttr(recs){if(!live())return;recs.forEach(function(r){var el=r.target;if(el.closest&&el.closest('#network-graph'))return;if(!vis(el))return;var a=r.attributeName;
if(a==='aria-pressed'){if(el.getAttribute('aria-pressed')==='true'&&r.oldValue!=='true'&&recent()){if(el.classList.contains('mod-row'))return;seat(el)}}
else if(a==='hidden'){if(REVEAL[el.id]&&!el.hidden&&r.oldValue!==null)enter(el)}
else if(a==='disabled'){if(READY[el.id]&&!el.disabled&&r.oldValue!==null)pop(el,1.07)}})}

observe(function(){var m=new MutationObserver(onAttr);document.querySelectorAll(ROOTS).forEach(function(root){m.observe(root,{subtree:true,attributes:true,attributeOldValue:true,attributeFilter:['aria-pressed','hidden','disabled']})});return m});
function q(s){return document.querySelector(s)}
function inRoute(el){return !!el.closest('#workspace-prerequisites')===(b.dataset.osRoute==='prerequisites')}
function vis(el){return !!el&&el.isConnected&&live()&&el.getClientRects().length>0&&inRoute(el)}
var LIST=['mod-list','detail','network-relations','issues-list','prerequisite-items','identity-candidates'],sigs={},keysets={};
function ck(c){return (c.getAttribute&&(c.getAttribute('data-key')||c.getAttribute('data-id')||c.id))||(c.textContent||'').trim().slice(0,160)}
function snap(el){var ks=Array.prototype.map.call(el.children,ck);return {ks:ks,sig:ks.join('|')}}
function baseline(){LIST.forEach(function(id){var el=document.getElementById(id);if(el){var s=snap(el);sigs[id]=s.sig;keysets[id]=s.ks}});var s=q('#mod-list .mod-row.selected');lastSel=s?s.getAttribute('data-key'):null;var v=q('#network-relations [data-network-view][aria-pressed=true]');lastView=v?v.getAttribute('data-network-view'):null}
function onList(id){var el=document.getElementById(id);if(!el)return;
if(id==='mod-list'){var s=el.querySelector('.mod-row.selected'),k=s?s.getAttribute('data-key'):null;if(k&&k!==lastSel&&recent()&&vis(s)&&!rm())play(s,'s',[{scale:'1'},{scale:'1.012',offset:.4},{scale:'1'}],{duration:300,easing:'ease-out'});lastSel=k;return}
if(id==='network-relations'){var v=el.querySelector('[data-network-view][aria-pressed=true]'),vk=v?v.getAttribute('data-network-view'):null,vc=vk!==lastView;lastView=vk;var rs=snap(el),sc=rs.sig!==sigs[id];sigs[id]=rs.sig;keysets[id]=rs.ks;if((vc||sc)&&recent()&&vis(el)){if(vc&&v&&vis(v))seat(v);enter(el.querySelector('.network-relation-scroll')||el,6,400)}return}
var sn=snap(el),prev=keysets[id],same=sn.sig===sigs[id];sigs[id]=sn.sig;keysets[id]=sn.ks;if(same||!vis(el))return;
if(id==='detail'){if(recent())enter(el.firstElementChild||el,6,420);return}
if(id==='identity-candidates'&&!recent())return;
stagger(Array.prototype.filter.call(el.children,function(c,i){return !prev||prev.indexOf(sn.ks[i])<0}))}
LIST.forEach(function(id){var el=document.getElementById(id);if(el)observe(function(){var m=new MutationObserver(function(){onList(id)});m.observe(el,{childList:true});return m})});
function onStage(){var tag=q('#prerequisite-state-tag'),ph=q('#prerequisite-phase');var txt=(tag?tag.textContent:'')+'|'+(ph?ph.textContent:'');if(txt===tagText)return;var had=tagText!=='';tagText=txt;if(!had||!live()||b.dataset.osRoute!=='prerequisites')return;if(tag&&vis(tag)){flash(tag);pop(tag,1.14)}}
['prerequisite-state-tag','prerequisite-phase'].forEach(function(id){var el=document.getElementById(id);if(el)observe(function(){var m=new MutationObserver(onStage);m.observe(el,{childList:true,characterData:true,subtree:true});return m})});
onStage();
var mqLegacy=false,mqc=function(){if(rm()){release(false);cancelAll()}};if(mq){if(mq.addEventListener)on(mq,'change',mqc);else if(mq.addListener){mq.addListener(mqc);mqLegacy=true}}
baseline();

observe(function(){var m=new MutationObserver(route);m.observe(b,{attributes:true,attributeFilter:['data-workspace','class']});return m});
on(window,'resize',kickFit);
if(window.ResizeObserver){var app=document.querySelector('.app')||b;observe(function(){var r=new ResizeObserver(kickFit);r.observe(app);return r})}
route();kickFit()})();


/* Source: suite-cards.js */
(function(){
'use strict';
var b=document.body;if(!b||!b.classList||!b.classList.contains('opus-suite')||window.__osCards)return;window.__osCards=1;
/* Home reference: hm-rise = opacity 0 + translateY(16px) scale(.985) -> rest. Phases (absolute, never compacted): title 0ms/700, outer surface 60ms/750, primary 140ms/700, secondary 220ms/700, supporting detail 300ms/700. */
var TITLE='cubic-bezier(.3,1.35,.5,1)',RISE='cubic-bezier(.3,1.3,.5,1)',CARD='cubic-bezier(.3,1.45,.5,1)',SIDE='cubic-bezier(.3,1.4,.5,1)',FADE='cubic-bezier(.25,.8,.35,1)',HURRY=4;
var PH_T=0,PH_O=60,PH_1=140,PH_2=220,PH_S=300;
var mq=window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)'):null,A=new Set(),last=b.dataset.osRoute||'',mo=null,L=[],raf=0,run=null;
/* Spatial entrances belong to one paper surface per branch. Layout shells and content inside a moving surface only fade, retaining their original phases. */
/* [selector, dx, dy, delay, duration, easing, kind]  kind: o=fade only, g=translate only (graph host), n=note tilt */
var OV_EMPTY=[
['#analysis-workspace .os-mast>.hero',0,16,PH_T,700,TITLE],
['#analysis-workspace .os-import-wrap',0,16,PH_O,750,RISE,'o'],
['#analysis-import-panel>#dropzone',0,14,PH_1,700,CARD],
['#analysis-import-panel>.import-divider',0,0,PH_2,600,FADE,'o'],
['#analysis-import-panel>.import-label',0,12,PH_2,700,CARD],
['#analysis-import-panel>.path-row',0,12,PH_2,700,CARD],
['#analysis-import-panel>#notice',0,10,PH_S,700,CARD],
['#analysis-workspace #analysis-empty',0,10,PH_S,700,CARD]];
var OV_REPORT=[
['#analysis-workspace .os-mast>.hero',0,16,PH_T,700,TITLE],
['#view-overview .os-readout',0,16,PH_O,750,RISE],
['#analysis-workspace .os-import-wrap',0,16,PH_O+40,750,RISE],
['#overview-mod-results>.usage-panel',0,14,PH_1,700,CARD],
['#view-overview .os-split',0,16,PH_1,700,RISE],
['#view-overview #identity-panel',0,16,PH_1,700,RISE],
['#view-overview .os-catalog',-12,4,PH_1,700,SIDE,'o'],
['#view-overview .os-dossier',12,4,PH_2,700,SIDE,'o'],
['#view-overview #enrich-panel',0,12,PH_2,700,CARD],
['#view-overview .os-switch',0,10,PH_S,700,CARD,'o'],
['#analysis-workspace #analysis-empty',0,10,PH_S,700,CARD]];
var P={
settings:[
['#workspace-settings .dialog-head',0,16,PH_T,700,TITLE],
['#workspace-settings .settings-categories',-12,4,PH_O,750,SIDE],
['#workspace-settings .settings-group:not([hidden])',0,16,PH_1,750,CARD],
['#workspace-settings .settings-group:not([hidden]) .settings-group-fields',0,12,PH_2,700,CARD,'o'],
['#workspace-settings #settings-security-note',0,8,PH_S,700,CARD],
['#workspace-settings .settings-footer',0,10,PH_S,700,CARD],
['#workspace-settings .update-options-sheet',0,16,PH_1,750,CARD],
['#workspace-settings .update-release-sheet',0,16,PH_2,750,CARD]],
network:[
['#view-network>header.os-title',0,16,PH_T,700,TITLE],
['#view-network .os-net-sheet',0,16,PH_O,750,RISE,'g'],
['#view-network .os-net-bar',0,-6,PH_1,700,CARD,'o'],
['#view-network .os-net-canvas',0,0,PH_1,600,FADE,'o'],
['#view-network .os-net-drawer',14,0,PH_2,700,SIDE,'o'],
['#view-network .os-net-foot',0,8,PH_S,700,CARD,'o']],
issues:[
['#view-issues>header.os-title',0,16,PH_T,700,TITLE],
['#view-issues .os-iss-grid',0,16,PH_O,750,RISE,'o'],
['#view-issues .os-iss-main',0,14,PH_1,700,CARD],
['#view-issues .os-note',0,14,PH_2,760,CARD,'n'],
['#view-issues #issues-list',0,8,PH_S,700,CARD,'o']],
/* Each prerequisite paper card owns one entrance; layout wrappers and the empty copy never stack transforms. */
prerequisites:[
['#workspace-prerequisites>header.os-pre-head',0,16,PH_T,700,TITLE],
['#workspace-prerequisites .os-pre-input',-12,6,PH_1,700,SIDE],
['#workspace-prerequisites .os-pre-main',12,6,PH_2,700,SIDE],
['#workspace-prerequisites #prerequisite-advanced',0,8,PH_S,700,CARD],
['#workspace-prerequisites #prerequisite-status',0,10,PH_S,700,CARD],
['#workspace-prerequisites #prerequisite-results',0,10,PH_S,700,CARD]]};
function specs(r){if(r==='overview')return b.dataset.hasReport==='true'?OV_REPORT:OV_EMPTY;return P[r]||null}
function rm(){return !!(mq&&mq.matches)}
function drop(a){A.delete(a);a.onfinish=null;a.oncancel=null}
function cancel(){if(raf){cancelAnimationFrame(raf);raf=0}run=null;var l=Array.from(A);A.clear();l.forEach(function(a){a.onfinish=null;a.oncancel=null;try{a.cancel()}catch(e){}})}
function track(a){A.add(a);a.onfinish=a.oncancel=function(){drop(a)}}
function hits(a,t){var el=a.effect&&a.effect.target;if(!el)return false;if(!t||t===b||t===document.documentElement)return true;return el===t||el.contains(t)||(typeof t.contains==='function'&&t.contains(el))}
function hurry(t){A.forEach(function(a){if(!hits(a,t))return;try{if(typeof a.updatePlaybackRate==='function')a.updatePlaybackRate(HURRY);else a.playbackRate=HURRY}catch(e){}})}
function settle(t){Array.from(A).forEach(function(a){if(!hits(a,t))return;drop(a);try{a.finish()}catch(e){}})}
function vis(el){if(!el||!el.isConnected||typeof el.animate!=='function')return false;if(el.closest('[hidden]'))return false;if(!el.getClientRects().length)return false;var r=el.getBoundingClientRect();if(r.width<1||r.height<1)return false;var cs=getComputedStyle(el);return cs.display!=='none'&&cs.visibility!=='hidden'}
function kf(s){if(s[6]==='o')return [{opacity:0},{opacity:1}];var f={opacity:0,translate:s[1]+'px '+s[2]+'px'},t={opacity:1,translate:'0px 0px'};if(s[6]!=='g'){f.scale='.985';t.scale='1'}if(s[6]==='n'){f.rotate='-1.6deg';t.rotate='0deg'}return [f,t]}
function pass(ctx){if(ctx!==run||document.hidden)return;var list=ctx.specs||specs(ctx.route);if(!list)return;var el2=performance.now()-ctx.t0;
list.forEach(function(s){var el=document.querySelector(s[0]);if(!el||ctx.done.has(el)||!vis(el))return;ctx.done.add(el);var d=ctx.red?0:Math.max(0,s[3]-el2),a;try{a=el.animate(ctx.red?[{opacity:0},{opacity:1}]:kf(s),{duration:ctx.red?160:s[4],delay:d,easing:ctx.red?'ease-out':s[5],fill:'backwards'})}catch(e){return}track(a)})}
function play(custom){cancel();if(document.hidden)return;var r=b.dataset.osRoute||'';if(!specs(r))return;var ctx={route:r,t0:performance.now(),red:rm(),done:new Set(),specs:Array.isArray(custom)?custom:null};run=ctx;pass(ctx);
/* top-up in the very next frame (before its paint) for surfaces revealed after the route attribute flipped */
raf=requestAnimationFrame(function(){raf=0;pass(ctx)})}
window.damnSettingsCategoryMotion=function(options){if(b.dataset.osRoute!=='settings')return;if(options&&options.keyboard){cancel();return;}play([['#workspace-settings .settings-group:not([hidden])',0,16,PH_T,750,CARD],['#workspace-settings .settings-group:not([hidden]) .settings-group-fields',0,12,PH_O,700,CARD,'o'],['#workspace-settings #settings-security-note',0,8,PH_1,700,CARD],['#workspace-settings .settings-footer',0,10,PH_1,700,CARD],['#workspace-settings .update-options-sheet',0,16,PH_T,750,CARD],['#workspace-settings .update-release-sheet',0,16,PH_O,750,CARD]]);};
function onRoute(){var r=b.dataset.osRoute||'';if(r===last)return;last=r;cancel();if(specs(r))play()}
function on(t,y,f,o){L.push([t,y,f,o]);t.addEventListener(y,f,o)}
var CP={capture:true,passive:true};
/* Interaction never waits: touched surface lands 4x faster, graph surfaces land at once for exact coordinates. Programmatic focus does not erase the entrance. */
on(document,'pointerdown',function(e){if(!A.size)return;var t=e.target;if(!t||t.nodeType!==1)return;if(t.closest('#network-graph'))settle(t);else hurry(t)},CP);
on(document,'wheel',function(e){if(!A.size)return;var t=e.target;if(t&&t.nodeType===1&&t.closest('#network-graph'))settle(t)},CP);
on(document,'focusin',function(e){if(!A.size)return;var t=e.target;if(!t||t.nodeType!==1)return;var kb=false;try{kb=t.matches(':focus-visible')}catch(x){kb=true}if(kb)hurry(t)},CP);
on(document,'keydown',function(e){if(!A.size)return;var k=e.key;if(k==='Tab'||k==='Shift'||k==='Control'||k==='Alt'||k==='Meta')return;var t=document.activeElement;hurry(t&&t!==document.body?t:b)},CP);
on(document,'visibilitychange',function(){if(document.hidden)cancel()});
var mc=null;if(mq){mc=function(){if(mq.matches)cancel()};if(mq.addEventListener)on(mq,'change',mc);else if(mq.addListener)mq.addListener(mc)}
function connect(){if(mo)return;mo=new MutationObserver(onRoute);mo.observe(b,{attributes:true,attributeFilter:['data-os-route']})}
function disconnect(){if(mo){mo.disconnect();mo=null}}
window.addEventListener('pagehide',function(e){cancel();disconnect();if(!e.persisted){L.forEach(function(x){x[0].removeEventListener(x[1],x[2],x[3])});L=[];if(mq&&mc&&!mq.addEventListener&&mq.removeListener)mq.removeListener(mc);mc=null}});
window.addEventListener('pageshow',function(e){if(!e.persisted||!L.length)return;last=b.dataset.osRoute||'';connect()});
connect();if(specs(last))play()})();


/* Source: onboarding.js */
(()=>{'use strict';
if(window.__damnAiSetup)return;window.__damnAiSetup=true;
const d=document.getElementById('ai-setup-dialog');if(!d)return;
const q=id=>document.getElementById(id),f={ep:q('ai-setup-endpoint'),model:q('ai-setup-model'),key:q('ai-setup-key'),hide:q('ai-setup-hide'),status:q('ai-setup-status'),save:q('ai-setup-save'),later:q('ai-setup-later'),form:q('ai-setup-form')};
const LATER='稍后，先用本地分析',mq=window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)'):null,reduced=()=>!!(mq&&mq.matches);
const INTRO_MS=1000,HURRY=4,MODK=new Set(['Shift','Control','Alt','Meta','CapsLock','OS']);
let started=false,state='idle',busy=false,timer=0,prevFocus=null,persistFailed=false,pref=false,hurried=false;
const wepoch=()=>typeof settingsWriteEpoch!=='undefined'?settingsWriteEpoch:0;
const setStatus=(t,type)=>{f.status.textContent=t||'';f.status.dataset.type=type||'';};
const lock=v=>{busy=v;[f.ep,f.model,f.key,f.hide,f.save,f.later].forEach(e=>{e.disabled=v;});d.setAttribute('aria-busy',String(v));};
const say=(t,err)=>{if(typeof notice==='function')notice(t,!!err);};
/* Intro animations are the CSS keyframes named ai-setup-* on the card subtree only; the dialog root and native window controls are never touched. */
const anims=()=>{try{if(!f.form||typeof f.form.getAnimations!=='function')return[];return f.form.getAnimations({subtree:true}).filter(a=>typeof a.animationName==='string'&&a.animationName.indexOf('ai-setup-')===0);}catch{return[];}};
const land=()=>{anims().forEach(a=>{try{a.finish();}catch{}});};
function hurry(){if(state!=='entering'||hurried)return;hurried=true;anims().forEach(a=>{try{if(typeof a.updatePlaybackRate==='function')a.updatePlaybackRate(HURRY);else a.playbackRate=HURRY;}catch{}});}
function finish(){clearTimeout(timer);timer=0;f.key.value='';d.classList.remove('is-shown','is-closing','is-intro');hurried=false;state='idle';if(d.open){try{d.close();}catch{}}lock(false);persistFailed=false;f.later.textContent=LATER;const p=prevFocus;prevFocus=null;if(p&&p.isConnected&&typeof p.focus==='function'){try{p.focus({preventScroll:true});}catch{}}}
function hide(){if(state==='idle'||state==='closing')return;state='closing';f.key.value='';clearTimeout(timer);d.classList.add('is-closing');d.classList.remove('is-shown');if(reduced()||document.hidden){finish();return;}timer=setTimeout(finish,220);}
function show(s){if(state!=='idle'||d.open)return;prevFocus=document.activeElement;f.ep.value=s.endpoint||'';f.model.value=s.model||'';f.key.value='';f.key.placeholder=s.hasKey?'已保存密钥；同一服务地址留空即保留':'填写 API Key（本地模型可留空）';pref=!!s.hideAiSetup;f.hide.checked=pref;persistFailed=false;f.later.textContent=LATER;setStatus(s.error||'',s.error?'error':'');lock(false);d.classList.remove('is-shown','is-closing','is-intro');hurried=false;try{d.showModal();}catch{return;}state='entering';void d.offsetWidth;d.classList.add('is-intro','is-shown');try{f.ep.focus({preventScroll:true});}catch{}clearTimeout(timer);timer=setTimeout(()=>{if(state==='entering')state='open';},reduced()?0:INTRO_MS);}
function accept(s){if(typeof settingsWriteEpoch!=='undefined')settingsWriteEpoch++;settingsState=s;try{if(typeof updateAIButtons==='function')updateAIButtons();}catch{}try{if(typeof identitySettingsChanged==='function')identitySettingsChanged(s);}catch{}try{if(typeof lastConfigStamp!=='undefined'&&typeof damnConfigStamp==='function')lastConfigStamp=damnConfigStamp(s);}catch{}}
async function later(){if(busy||state==='idle'||state==='closing')return;const want=f.hide.checked;if(persistFailed||want===pref){hide();return;}lock(true);setStatus('正在保存偏好…');try{const s=await api('/api/settings',{defer:true,hideAiSetup:want});accept(s);pref=want;lock(false);hide();if(want)say('已记住：下次进入不再弹出 AI 配置，可随时在设置中填写。');}catch(e){lock(false);persistFailed=true;f.later.textContent='本次跳过（不记住）';setStatus('未能记住“下次不再弹出”：'+((e&&e.message)||'保存失败')+'。可重试，或点“本次跳过”继续使用本地功能（不会记住此选择）。','error');try{f.later.focus();}catch{}}}
async function save(e){e.preventDefault();if(busy||state==='idle'||state==='closing')return;const ep=f.ep.value.trim(),model=f.model.value.trim();if(!ep||!model){setStatus('请填写 API 地址和模型名称；不使用 AI 可点“稍后”。','error');try{(ep?f.model:f.ep).focus();}catch{}return;}lock(true);setStatus('正在保存…（不会调用 AI）');try{const s=await api('/api/settings',{endpoint:ep,model,apiKey:f.key.value,clearKey:false,hideAiSetup:f.hide.checked});f.key.value='';accept(s);pref=!!s.hideAiSetup;lock(false);hide();say(s.configured?'AI 设置已保存，可在总览或模组详情中使用 AI 解读。':'设置已保存；如需 AI 解读，请在设置中补充密钥。');}catch(err){f.key.value='';lock(false);setStatus((err&&err.message)||'保存失败，请检查填写内容。','error');}}
f.form.addEventListener('submit',save);f.later.addEventListener('click',later);
f.hide.addEventListener('change',()=>{if(persistFailed){persistFailed=false;f.later.textContent=LATER;setStatus('');}});
/* Real user interaction only speeds up the remaining entrance; nothing is prevented or disabled. Programmatic focus does not trigger this. */
d.addEventListener('pointerdown',()=>{hurry();},{capture:true,passive:true});
d.addEventListener('keydown',e=>{if(MODK.has(e.key))return;hurry();},{capture:true,passive:true});
d.addEventListener('cancel',e=>{e.preventDefault();later();});
d.addEventListener('close',()=>{if(state!=='idle')finish();});
const settle=()=>{if(state==='closing')finish();else if(state==='entering'){clearTimeout(timer);state='open';land();}};
if(mq){const h=()=>{if(reduced())settle();};if(mq.addEventListener)mq.addEventListener('change',h);else if(mq.addListener)mq.addListener(h);}
document.addEventListener('visibilitychange',()=>{if(document.hidden)settle();});
window.addEventListener('pagehide',()=>{f.key.value='';settle();});
window.addEventListener('pageshow',e=>{f.key.value='';if(e.persisted&&(state==='closing'||(state!=='idle'&&!d.open)))finish();});
async function start(){if(started)return;started=true;if(typeof api!=='function')return;const ep=wepoch();let s;try{s=await loadSettingsState();}catch{return;}let eff=s;if(wepoch()!==ep)eff=settingsState||s;else if(!settingsState){settingsState=s;try{if(typeof updateAIButtons==='function')updateAIButtons();}catch{}}if(!eff||eff.configured||eff.hideAiSetup||(settingsState&&settingsState.configured))return;show(eff);}
const launch=()=>setTimeout(()=>{void start();},0);
const boot=()=>{if(document.body?.dataset.desktopHost==='true'&&document.body.dataset.desktopReady!=='true'){window.addEventListener('damn-desktop-ready',launch,{once:true});return;}launch();};
if(document.readyState==='complete')boot();else window.addEventListener('load',boot,{once:true});
})();


/* Source: desktop-ui.js */
(function(){'use strict';var b=document.body;if(!b||b.getAttribute('data-desktop-host')!=='true')return;if(window.__damnDesktopChrome)return;window.__damnDesktopChrome=true;var group=document.getElementById('desktop-window-controls');var bar=document.querySelector('aside.sidebar.workspace-topbar');if(!group||!bar)return;['aside.sidebar.workspace-topbar','.sidebar .brand-block','.sidebar-workspace-area','.sidebar-nav','#analysis-page-navigation','.analysis-nav','.sidebar-utility','.app>header','.header-location'].forEach(function(s){var n=document.querySelectorAll(s);for(var i=0;i<n.length;i++)n[i].classList.add('pywebview-drag-region');});var busy=false;function call(name){if(busy)return;var api=window.pywebview&&window.pywebview.api;var fn=api&&api[name];if(typeof fn!=='function')return;busy=true;try{var r=fn.call(api);if(r&&typeof r.then==='function')r.then(null,function(){});}catch(e){}setTimeout(function(){busy=false;},700);}var mn=document.getElementById('desktop-minimize'),cl=document.getElementById('desktop-close');if(mn)mn.addEventListener('click',function(){call('minimize_window');});if(cl)cl.addEventListener('click',function(){call('close_window');});var sc=document.querySelector('.app'),positions=Object.create(null),scrollRoute=b.dataset.osRoute||'',scrollFrame=0;var foot=sc&&sc.parentNode===b?sc.querySelector(':scope>main>footer'):null;if(foot){foot.setAttribute('data-desktop-footer','true');b.insertBefore(foot,sc.nextSibling);}var gut=function(){if(foot)foot.style.setProperty('--dk-gutter',Math.max(0,sc.offsetWidth-sc.clientWidth)+'px');};gut();function rememberScroll(){if(sc&&!scrollFrame&&(b.dataset.osRoute||'')===scrollRoute)positions[scrollRoute]=sc.scrollTop;}function routeScroll(){var r=b.dataset.osRoute||'';if(r===scrollRoute||!sc)return;var target=r==='settings'?0:positions[r]||0;scrollRoute=r;if(scrollFrame)cancelAnimationFrame(scrollFrame);scrollFrame=requestAnimationFrame(function(){scrollFrame=0;sc.scrollTop=target;});}if(sc){sc.addEventListener('scroll',rememberScroll,{passive:true});document.addEventListener('pointerdown',rememberScroll,{capture:true,passive:true});document.addEventListener('keydown',rememberScroll,{capture:true,passive:true});}var stack=[];function isOpen(d){return d&&d.isConnected&&d.hasAttribute('open');}function prune(){stack=stack.filter(isOpen);}function seed(){stack=[];var ds=document.querySelectorAll('dialog[open]');for(var i=0;i<ds.length;i++)stack.push(ds[i]);}function place(){prune();var target=null;for(var i=stack.length-1;i>=0;i--){var d=stack[i];var modal=true;try{modal=d.matches(':modal');}catch(e){}if(modal){target=d;break;}}var parent=target||bar;var had=group.contains(document.activeElement)?document.activeElement:null;if(target){if(group.parentNode!==target||target.lastElementChild!==group)target.appendChild(group);group.classList.add('dk-in-dialog');}else{if(group.parentNode!==bar||bar.firstElementChild!==group)bar.insertBefore(group,bar.firstChild);group.classList.remove('dk-in-dialog');}if(had&&document.activeElement!==had&&group.contains(had)){try{had.focus({preventScroll:true});}catch(e){}}}var mo=null;function onMut(list){var changed=false;for(var i=0;i<list.length;i++){var t=list[i].target;if(t===b&&list[i].attributeName==='data-os-route'){routeScroll();continue;}if(!t||t.nodeName!=='DIALOG')continue;changed=true;var k=stack.indexOf(t);if(k>=0)stack.splice(k,1);if(t.hasAttribute('open'))stack.push(t);}if(changed)place();}function connect(){if(mo)return;window.addEventListener('resize',gut,{passive:true});gut();seed();mo=new MutationObserver(onMut);mo.observe(document.body,{subtree:true,attributes:true,attributeFilter:['open','data-os-route']});place();}function disconnect(){window.removeEventListener('resize',gut);if(scrollFrame){cancelAnimationFrame(scrollFrame);scrollFrame=0;}if(mo){mo.disconnect();mo=null;}stack=[];place();}window.addEventListener('pagehide',disconnect);window.addEventListener('pageshow',function(e){if(e.persisted||!mo)connect();});connect();})();

/* Source: settings-categories.js */
(function(){'use strict';
if(window.__damnSettingsCategories)return;
var root=document.getElementById('settings-dialog');if(!root)return;
var buttons=Array.prototype.slice.call(root.querySelectorAll('[data-settings-category]')),panels=Array.prototype.slice.call(root.querySelectorAll('[data-settings-panel]'));
if(buttons.length!==4||panels.length!==4)return;window.__damnSettingsCategories=true;
var selected='appearance',alive=true,frame=0,epoch=0,footer=root.querySelector('.settings-footer'),security=document.getElementById('settings-security-note'),status=document.getElementById('settings-status'),statuses={},globalStatus={text:status?status.textContent:'',type:''};
function valid(id){return id==='appearance'||id==='network'||id==='ai'||id==='updates';}
function activeButton(id){return buttons.find(function(b){return b.dataset.settingsCategory===id;});}
function resetScroll(stamp){if(frame){cancelAnimationFrame(frame);frame=0;}var sc=document.querySelector('body[data-desktop-host=true] > .app');function reset(){if(!alive||stamp!==epoch||document.body.dataset.workspace!=='settings')return;if(sc)sc.scrollTop=0;else if(typeof window.scrollTo==='function')window.scrollTo({left:0,top:0,behavior:'instant'});}reset();frame=requestAnimationFrame(function(){frame=requestAnimationFrame(function(){frame=0;reset();});});}
function renderStatus(){if(!status)return;var message=statuses[selected]||globalStatus;if(selected==='network'&&!statuses.network&&!message.type&&message.text.indexOf('保存设置不会调用 AI')===0)message={text:'修改联网选项后，点击“保存设置”生效。',type:''};status.textContent=message.text;status.className='small '+(message.type||'muted');}
window.damnSetCategorySettingsStatus=function(text,type,category){if(!alive)return;if(category==='ai'||category==='network')statuses[category]={text:text,type:type||''};else{globalStatus={text:text,type:type||''};statuses={};}renderStatus();};
function select(id,options){if(!alive||!valid(id))return false;options=options||{};var changed=id!==selected,old=panels.find(function(p){return p.dataset.settingsPanel===selected;}),hadFocus=changed&&old&&old.contains(document.activeElement);selected=id;root.dataset.settingsCategory=id;buttons.forEach(function(b){var on=b.dataset.settingsCategory===id;b.setAttribute('aria-selected',String(on));b.setAttribute('tabindex',on?'0':'-1');});panels.forEach(function(p){p.hidden=p.dataset.settingsPanel!==id;});if(footer)footer.hidden=id==='appearance'||id==='updates';if(security)security.hidden=id!=='ai';renderStatus();if(options.focus||hadFocus){var button=activeButton(id);if(button)button.focus({preventScroll:true});}if(changed){epoch++;resetScroll(epoch);if(typeof window.damnSettingsCategoryMotion==='function')window.damnSettingsCategoryMotion({keyboard:!!options.keyboard});}return true;}
buttons.forEach(function(button,index){button.addEventListener('click',function(){select(button.dataset.settingsCategory);});button.addEventListener('keydown',function(e){var next;if(e.key==='ArrowDown')next=(index+1)%buttons.length;else if(e.key==='ArrowUp')next=(index+buttons.length-1)%buttons.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=buttons.length-1;else return;e.preventDefault();select(buttons[next].dataset.settingsCategory,{focus:true,keyboard:true});});});
window.damnShowSettingsCategory=function(id){return select(valid(id)?id:selected,{focus:valid(id)});};
window.addEventListener('pagehide',function(){alive=false;epoch++;if(frame){cancelAnimationFrame(frame);frame=0;}});
window.addEventListener('pageshow',function(e){if(e.persisted){alive=true;select(selected);}});
root.dataset.settingsCategories='ready';select(selected);
})();


/* Source: updates.js */
/* Public build: local preferences only; no remote update or reminder service. */
(function(){'use strict';
if(window.__damnUpdates)return;
var panel=document.getElementById('settings-updates'),dialog=document.getElementById('settings-dialog');if(!panel||!dialog)return;window.__damnUpdates=true;
var channel=document.getElementById('updates-channel'),mode=document.getElementById('updates-check-mode'),version=document.getElementById('updates-current-version'),status=document.getElementById('updates-preference-status'),check=document.getElementById('updates-check'),install=document.getElementById('updates-install'),checkStatus=document.getElementById('updates-check-status');
var defaults={channel:'stable',checkMode:'manual'},saved=null,desired=null,ready=false,reading=false,saving=false,alive=true,life=0,observer=null;
function copy(p){return {channel:p.channel,checkMode:p.checkMode};}
function valid(p){return !!p&&(p.channel==='stable'||p.channel==='preview')&&(p.checkMode==='manual'||p.checkMode==='startup');}
function same(a,b){return !!a&&!!b&&a.channel===b.channel&&a.checkMode===b.checkMode;}
function response(data){if(!data||data.schemaVersion!==1||data.serviceConfigured!==false||data.status!=='not_configured'||typeof data.currentVersion!=='string'||!(/^[0-9A-Za-z.+_-]{1,64}$/).test(data.currentVersion)||!valid(data.preferences))throw Error('版本信息暂时无法读取。');return data;}
function visible(){return alive&&!document.hidden&&document.body.dataset.workspace==='settings'&&dialog.dataset.settingsCategory==='updates'&&!panel.hidden;}
function say(text,error){if(!alive)return;status.textContent=text;status.className='update-preference-status'+(error?' error':'');}
function fields(p){channel.value=p.channel;mode.value=p.checkMode;}
function controls(){channel.disabled=mode.disabled=!ready||reading;check.disabled=true;install.disabled=true;check.setAttribute('aria-disabled','true');install.setAttribute('aria-disabled','true');checkStatus.textContent='公开源码版未接入在线更新与启动提醒。';}
function accept(data){saved=copy(data.preferences);version.textContent=data.currentVersion;}
async function refresh(){if(!visible()||reading||saving)return;var stamp=life;reading=true;controls();say('正在读取本机偏好…');try{var data=response(await api('/api/updates'));if(!alive||stamp!==life)return;accept(data);desired=copy(saved);ready=true;fields(desired);say('选择后保存在本机。');}catch(e){if(!alive||stamp!==life)return;ready=false;say(e.message,true);}finally{if(alive&&stamp===life){reading=false;controls();}}}
async function pump(){if(saving||!ready||!desired||!alive)return;var stamp=life;saving=true;try{while(alive&&stamp===life&&!same(desired,saved)){var next=copy(desired);say('正在保存本机偏好…');try{var data=response(await api('/api/updates/preferences',next));if(!alive||stamp!==life)return;if(!same(data.preferences,next))throw Error('偏好未保存，请重试。');accept(data);if(same(desired,next)){fields(saved);say('偏好已保存在本机。');}}catch(e){if(!alive||stamp!==life)return;desired=copy(saved||defaults);fields(desired);say(e.message,true);break;}}}finally{if(alive&&stamp===life){saving=false;controls();}}}
function change(){if(!alive||!ready||reading)return;var next={channel:channel.value,checkMode:mode.value};if(!valid(next)){fields(saved||defaults);return;}desired=next;pump();}
function visibleRefresh(){if(visible())refresh();}
function watch(){if(observer)return;observer=new MutationObserver(visibleRefresh);observer.observe(dialog,{attributes:true,attributeFilter:['data-settings-category']});observer.observe(document.body,{attributes:true,attributeFilter:['data-workspace']});}
function listen(){channel.addEventListener('change',change);mode.addEventListener('change',change);document.addEventListener('visibilitychange',visibleRefresh);}
window.addEventListener('pagehide',function(){alive=false;life++;ready=reading=saving=false;if(observer){observer.disconnect();observer=null;}channel.removeEventListener('change',change);mode.removeEventListener('change',change);document.removeEventListener('visibilitychange',visibleRefresh);});
window.addEventListener('pageshow',function(e){if(!e.persisted||alive)return;alive=true;listen();watch();controls();visibleRefresh();});
listen();controls();watch();visibleRefresh();
})();


/* Source: tooltips.js */
/* Shared paper tooltips. Native title text is adopted without changing business events. */
(function(){'use strict';
var body=document.body;if(!body||window.__damnTooltips)return;window.__damnTooltips=true;
var ATTR='data-damn-tooltip',NS='http://www.w3.org/2000/svg',listeners=[],observer=null,alive=true,epoch=0;
var active=null,pending=null,hovered=null,focused=null,overTip=false,showTimer=0,closeTimer=0,hideTimer=0,openFrame=0,lastClosed=0;
var generatedNames=new WeakMap(),host=document.createElement('div'),tipId='damn-tooltip',suffix=0;
while(document.getElementById(tipId))tipId='damn-tooltip-'+(++suffix);
host.id=tipId;host.className='damn-paper-tooltip';host.setAttribute('role','tooltip');host.setAttribute('popover','manual');host.hidden=true;
var topLayer=typeof host.showPopover==='function'&&typeof host.hidePopover==='function';if(!topLayer)host.removeAttribute('popover');body.appendChild(host);
function clearTimer(name){if(name==='show'&&showTimer){clearTimeout(showTimer);showTimer=0;}if(name==='close'&&closeTimer){clearTimeout(closeTimer);closeTimer=0;}if(name==='hide'&&hideTimer){clearTimeout(hideTimer);hideTimer=0;}}
function cancelFrame(){if(openFrame){cancelAnimationFrame(openFrame);openFrame=0;}}
function text(el){return el&&el.getAttribute?(el.getAttribute(ATTR)||'').trim():'';}
function isElement(el){return !!el&&el.nodeType===1;}
function visible(el){if(!el||!el.isConnected||!body.contains(el)||el.closest('[hidden]')||!el.getClientRects().length)return false;var style=getComputedStyle(el);return style.display!=='none'&&style.visibility!=='hidden';}
function named(el,value,svg){var old=generatedNames.get(el),current=el.getAttribute('aria-label');if(old&&current===old){if(value){el.setAttribute('aria-label',value);generatedNames.set(el,value);}else{el.removeAttribute('aria-label');generatedNames.delete(el);}return;}
 if(current||el.getAttribute('aria-labelledby'))return;
 var control=/^(BUTTON|INPUT|SELECT|TEXTAREA|A)$/.test(el.tagName)||el.getAttribute('role')==='button';
 var labelled=el.labels&&el.labels.length;
 if(svg||(control&&!labelled&&!(el.textContent||'').trim())){if(value){el.setAttribute('aria-label',value);generatedNames.set(el,value);}}
}
function adopt(el){if(!isElement(el)||!body.contains(el)||el===host)return;
 if(el.namespaceURI===NS&&String(el.localName||el.tagName).toLowerCase()==='title'){
  var parent=el.parentElement,value=(el.textContent||'').trim();if(!parent||!value)return;
  if(parent.getAttribute(ATTR)!==value)parent.setAttribute(ATTR,value);named(parent,value,true);parent.removeChild(el);return;
 }
 if(el.hasAttribute('title')){var value=el.getAttribute('title')||'';if(el.getAttribute(ATTR)!==value)el.setAttribute(ATTR,value);named(el,value.trim(),false);el.removeAttribute('title');}
}
function scan(root){if(!isElement(root)||!body.contains(root)||root===host||host.contains(root))return;adopt(root);if(!root.isConnected)return;var nodes=root.querySelectorAll('[title],svg title');for(var i=0;i<nodes.length;i++)adopt(nodes[i]);}
function described(el,add){if(!el||!el.getAttribute)return;var list=(el.getAttribute('aria-describedby')||'').split(/\s+/).filter(Boolean),index=list.indexOf(tipId);if(add&&index<0)list.push(tipId);if(!add&&index>=0)list.splice(index,1);if(list.length)el.setAttribute('aria-describedby',list.join(' '));else el.removeAttribute('aria-describedby');}
function conceal(){clearTimer('hide');host.hidden=true;host.removeAttribute('data-open');if(topLayer){try{host.hidePopover();}catch(e){}}}
function close(immediate){var wasOpen=!!active;clearTimer('show');clearTimer('close');cancelFrame();pending=null;if(active)described(active,false);active=null;host.removeAttribute('data-open');if(wasOpen)lastClosed=Date.now();if(immediate)conceal();else{clearTimer('hide');hideTimer=setTimeout(function(){hideTimer=0;if(!active)conceal();},135);}}
function locate(el){var anchor=el.getBoundingClientRect(),rect=host.getBoundingClientRect(),vw=window.innerWidth,vh=window.innerHeight,gap=8,edge=8;
 var x=Math.max(edge,Math.min(anchor.left+(anchor.width-rect.width)/2,Math.max(edge,vw-rect.width-edge)));
 var above=anchor.top-rect.height-gap>=edge,y=above?anchor.top-rect.height-gap:anchor.bottom+gap;
 y=Math.max(edge,Math.min(y,Math.max(edge,vh-rect.height-edge)));host.style.left=Math.round(x)+'px';host.style.top=Math.round(y)+'px';host.setAttribute('data-side',above?'top':'bottom');
}
function fallbackParent(el){return el.closest('dialog[open]')||body;}
function show(el){if(!alive||document.hidden||!visible(el)||!text(el))return;clearTimer('hide');clearTimer('close');cancelFrame();if(active&&active!==el)described(active,false);
 active=el;pending=null;host.textContent=text(el);host.hidden=false;host.removeAttribute('data-open');host.style.visibility='hidden';
 if(topLayer){var parent=fallbackParent(el);if(host.parentElement!==parent)parent.appendChild(host);try{host.showPopover();}catch(e){topLayer=false;host.removeAttribute('popover');var parent=fallbackParent(el);if(host.parentElement!==parent)parent.appendChild(host);}}
 else{var parent=fallbackParent(el);if(host.parentElement!==parent)parent.appendChild(host);}
 locate(el);host.style.visibility='';described(el,true);var stamp=epoch;openFrame=requestAnimationFrame(function(){openFrame=0;if(alive&&stamp===epoch&&active===el&&visible(el))host.setAttribute('data-open','');else close(true);});
}
function request(el,instant){if(!alive||!el||!visible(el)||!text(el))return;if(active===el){clearTimer('close');return;}clearTimer('show');clearTimer('close');if(active)close(true);pending=el;var delay=instant||(lastClosed&&Date.now()-lastClosed<900)?0:400,stamp=epoch;
 if(!delay){show(el);return;}showTimer=setTimeout(function(){showTimer=0;if(alive&&stamp===epoch&&pending===el)show(el);},delay);
}
function candidate(node){if(!isElement(node))node=node&&node.parentElement;if(!node||!node.closest)return null;var el=node.closest('['+ATTR+']');return el&&text(el)&&body.contains(el)?el:null;}
function scheduleClose(){clearTimer('close');if(overTip||(active&&(hovered===active||focused===active)))return;closeTimer=setTimeout(function(){closeTimer=0;if(!overTip&&(!active||(hovered!==active&&focused!==active)))close(false);},80);}
function pointerOver(e){if(e.pointerType==='touch')return;var node=e.target;if(host.contains(node)){overTip=true;clearTimer('close');return;}var el=candidate(node);if(el){hovered=el;request(el,false);}}
function pointerOut(e){var next=e.relatedTarget;if(host.contains(e.target)){if(host.contains(next))return;overTip=false;if(active&&active.contains(next)){hovered=active;return;}scheduleClose();return;}
 var el=candidate(e.target);if(!el&&!active&&!pending)return;if(el&&el.contains(next))return;if(el&&hovered===el)hovered=null;if(host.contains(next)){overTip=true;clearTimer('close');return;}if(pending===el&&!active){clearTimer('show');pending=null;}scheduleClose();
}
function focusIn(e){var el=candidate(e.target);if(!el)return;var keyboard=true;try{keyboard=el.matches(':focus-visible');}catch(error){}if(keyboard){focused=el;request(el,true);}}
function focusOut(e){if(focused&&focused.contains(e.relatedTarget))return;focused=null;scheduleClose();}
function dismiss(){hovered=focused=null;overTip=false;close(true);}
function onMutation(records){if(!alive)return;for(var i=0;i<records.length;i++){var r=records[i];if(r.type==='attributes'){
  if(r.attributeName==='title')adopt(r.target);
  if(r.attributeName==='data-workspace'||r.attributeName==='data-os-route'||r.attributeName==='data-settings-category'){dismiss();continue;}
  if(r.attributeName===ATTR)named(r.target,text(r.target),r.target.namespaceURI===NS);
  if((r.target===active||r.target===pending)&&(r.attributeName===ATTR||r.attributeName==='title')){if(!text(r.target))close(true);else if(r.target===active){host.textContent=text(active);locate(active);}}
 }else if(r.type==='childList'){var removed=r.removedNodes||[];for(var k=0;k<removed.length;k++){var gone=removed[k];if((active&&(gone===active||(gone.contains&&gone.contains(active))))||(pending&&(gone===pending||(gone.contains&&gone.contains(pending))))){dismiss();break;}}var nodes=r.addedNodes||[];for(var j=0;j<nodes.length;j++)scan(nodes[j]);if(r.target&&r.target.namespaceURI===NS&&String(r.target.localName||'').toLowerCase()==='title')adopt(r.target);}else if(r.type==='characterData'&&r.target&&r.target.parentElement){var parent=r.target.parentElement;if(parent.namespaceURI===NS&&String(parent.localName||'').toLowerCase()==='title')adopt(parent);}}
 if(active&&!visible(active))dismiss();if(pending&&!visible(pending)){clearTimer('show');pending=null;}
}
function connect(){if(observer||!alive)return;scan(body);observer=new MutationObserver(onMutation);observer.observe(body,{subtree:true,attributes:true,attributeFilter:['title',ATTR,'hidden','data-workspace','data-os-route','data-settings-category','open'],childList:true,characterData:true});}
function on(target,type,fn,options){listeners.push([target,type,fn,options]);target.addEventListener(type,fn,options);}
var capture={capture:true,passive:true};on(document,'pointerover',pointerOver,capture);on(document,'pointerout',pointerOut,capture);on(document,'pointerdown',dismiss,capture);on(document,'focusin',focusIn);on(document,'focusout',focusOut);/* Consume the tooltip's Escape before document/target modal cancellation. */on(window,'keydown',function(e){if(e.key!=='Escape'||(!active&&!pending&&!showTimer))return;e.preventDefault();e.stopPropagation();dismiss();},true);on(document,'scroll',function(e){if(host.contains(e.target))return;dismiss();},capture);on(window,'resize',dismiss,{passive:true});on(window,'blur',dismiss);on(document,'visibilitychange',function(){if(document.hidden)dismiss();});
window.addEventListener('pagehide',function(){alive=false;epoch++;dismiss();if(observer){observer.disconnect();observer=null;}listeners.forEach(function(item){item[0].removeEventListener(item[1],item[2],item[3]);});});
window.addEventListener('pageshow',function(e){if(!e.persisted||alive)return;alive=true;epoch++;listeners.forEach(function(item){item[0].addEventListener(item[1],item[2],item[3]);});connect();});
connect();
})();

