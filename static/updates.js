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
