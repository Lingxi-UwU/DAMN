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
