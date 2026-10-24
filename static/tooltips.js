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
