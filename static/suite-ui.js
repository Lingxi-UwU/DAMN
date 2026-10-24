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
