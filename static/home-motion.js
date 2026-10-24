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

