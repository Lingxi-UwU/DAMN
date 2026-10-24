'use strict';
(() => {
 const byId=id=>document.getElementById(id);
 const path=byId('home-pack-path'),choose=byId('home-choose'),scan=byId('home-scan');
 const pick=byId('home-archive-pick'),fileInput=byId('home-archive-file'),drop=byId('home-dropzone'),message=byId('home-notice');
 if(!path||!choose||!scan||!pick||!fileInput||!drop||!message)return;
 const controls=[path,choose,scan,pick,fileInput];
 let pending=null;
 const atHome=()=>document.body.dataset.workspace==='home';
 const analysisBusy=()=>typeof busy!=='undefined'&&busy;
 function say(text,error=false){message.textContent=text;message.hidden=false;message.classList.toggle('error',error);}
 function lock(value){for(const control of controls)control.disabled=value;drop.setAttribute('aria-disabled',String(value));}
 function available(){
  if(!atHome())return false;
  if(pending||analysisBusy()){say('已有导入或扫描正在进行，请稍候。',true);return false;}
  return true;
 }
 function cancel(action){
  action.cancelled=true;action.observer?.disconnect();
  if(pending===action){pending=null;lock(false);say('已取消本次导入，可重新选择路径或文件。');}
 }
 async function enterAnalysis(run){
  if(!available())return;
  const action={cancelled:false,observer:null};pending=action;lock(true);say('正在打开分析工作区…');
  try{
   // Navigation changes the workspace synchronously. Observe only later changes,
   // including leave-and-return navigation while initialization is still pending.
   const navigation=damnChooseWorkspace('analysis','overview');
   action.observer=new MutationObserver(()=>cancel(action));
   action.observer.observe(document.body,{attributes:true,attributeFilter:['data-workspace']});
   await navigation;
   if(action.cancelled||pending!==action||document.body.dataset.workspace!=='analysis')return;
   action.observer.disconnect();
   if(analysisBusy()){say('已有扫描正在进行，请稍候。',true);notice('已有扫描正在进行，请稍候。',true);return;}
   if(typeof damnShowImport==='function')damnShowImport(true);
   // Native click does not return the existing async handler's promise. Hand off
   // once and let its busy state, result display and error handling own the task.
   run();
   say('已在分析工作区打开导入。');
  }catch(error){
   if(action.cancelled||pending!==action)return;
   const text='无法打开分析：'+(error?.message||'请稍后重试。');say(text,true);
   if(document.body.dataset.workspace==='analysis')notice(text,true);
  }finally{
   action.observer?.disconnect();if(pending===action){pending=null;lock(false);}
  }
 }
 function scanPath(){
  if(!available())return;
  const value=path.value.trim();if(!value){say('请填写整合包目录路径，或选择目录、压缩包。',true);path.focus();return;}
  void enterAnalysis(()=>{byId('pack-path').value=value;byId('scan').click();});
 }
 function openPicker(){if(available())fileInput.click();}
 function importFile(file){
  if(!file||!available())return;
  if(!/\.(zip|mrpack)$/i.test(file.name)){say('支持 ZIP、MRPACK 文件；文件夹请使用“选择目录”。',true);return;}
  if(file.size>2*1024**3){say('单个文件上限为 2 GiB；更大的包请使用目录路径。',true);return;}
  void enterAnalysis(()=>{void openArchiveFile(file);});
 }
 choose.addEventListener('click',()=>{void enterAnalysis(()=>byId('choose').click());});
 scan.addEventListener('click',scanPath);
 path.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.isComposing&&event.keyCode!==229){event.preventDefault();scanPath();}});
 pick.addEventListener('click',event=>{event.stopPropagation();openPicker();});
 fileInput.addEventListener('change',()=>{
  const file=fileInput.files[0];if(!file)return;
  fileInput.value='';importFile(file);
 });
 const hasFiles=event=>Array.from(event.dataTransfer?.types||[]).includes('Files');
 drop.addEventListener('dragover',event=>{
  if(!atHome()||!hasFiles(event))return;
  event.preventDefault();event.stopPropagation();
  if(!pending&&!analysisBusy())drop.classList.add('dragging');
 });
 drop.addEventListener('dragleave',event=>{if(!drop.contains(event.relatedTarget))drop.classList.remove('dragging');});
 drop.addEventListener('drop',event=>{
  if(!atHome()||!hasFiles(event))return;
  event.preventDefault();event.stopPropagation();drop.classList.remove('dragging');
  if(!available())return;
  const files=Array.from(event.dataTransfer.files||[]),items=Array.from(event.dataTransfer.items||[]);
  if(items.some(item=>item.webkitGetAsEntry?.()?.isDirectory)){say('文件夹请使用“选择目录”或填写目录路径。',true);return;}
  if(files.length!==1){say('请一次拖入一个整合包文件。',true);return;}
  importFile(files[0]);
 });
})();
