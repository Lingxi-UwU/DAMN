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
