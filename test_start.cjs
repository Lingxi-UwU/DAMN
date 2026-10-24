'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('./static/start.js','utf8');
const app=fs.readFileSync('./static/app.js','utf8');
// Run the actual existing import handlers: native click intentionally returns no
// promise, and their shared busy flag owns work after the home entry hands off.
const scanHandler=app.slice(app.indexOf("$('#scan').addEventListener('click'"),app.indexOf('function uploadFile('));
const archiveHandler=app.slice(app.indexOf('async function openArchiveFile('),app.indexOf("$('#archive-pick').addEventListener"));
const chooseHandler=app.split('\n').find(line=>line.startsWith("$('#choose').addEventListener('click'"));
assert(scanHandler&&archiveHandler&&chooseHandler,'the production import handlers are available');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(){
 const init=deferred(),request=deferred(),observers=new Set(),calls=[],elements=new Map();
 const body={dataset:new Proxy({workspace:'home'},{set(target,key,value){target[key]=value;if(key==='workspace')for(const observer of observers)observer.schedule();return true;}})};
 class Observer{
  constructor(callback){this.callback=callback;this.active=false;this.queued=false;}
  observe(target,options){assert.equal(target,body);assert.deepEqual(Array.from(options.attributeFilter),['data-workspace']);this.active=true;observers.add(this);}
  schedule(){if(!this.active||this.queued)return;this.queued=true;queueMicrotask(()=>{this.queued=false;if(this.active)this.callback();});}
  disconnect(){this.active=false;observers.delete(this);}
 }
 function element(id){
  if(elements.has(id))return elements.get(id);
  const classes=new Set(),listeners=new Map(),attributes={},el={id,disabled:false,hidden:false,textContent:'',value:'',files:[],focusCount:0,clicks:0,
   classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),toggle(x,on){if(on)classes.add(x);else classes.delete(x);},contains:x=>classes.has(x)},
   setAttribute(name,value){attributes[name]=String(value);},getAttribute:name=>attributes[name],
   addEventListener(name,callback){if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(callback);},
   emit(type,data={}){const event={type,target:el,defaultPrevented:false,stopped:false,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.stopped=true;},...data};for(const callback of listeners.get(type)||[])callback(event);return event;},
   click(){if(this.disabled)return;this.clicks++;this.emit('click');},
   focus(){this.focusCount++;},contains(other){return other===this;},
   closest(){return id==='home-dropzone'?null:this;}
  };elements.set(id,el);return el;
 }
 for(const id of ['home-pack-path','home-choose','home-scan','home-archive-pick','home-archive-file','home-dropzone','home-notice','pack-path','choose','scan','archive-file','side'])element(id);
 element('side').value='client';element('home-notice').hidden=true;
 const ctx={console,document:{body,getElementById:element},MutationObserver:Observer,busy:false,$:selector=>element(selector.slice(1)),
  damnChooseWorkspace:async(...args)=>{calls.push(['workspace',...args]);body.dataset.workspace=args[0];await init.promise;},
  damnShowImport:value=>calls.push(['showImport',value]),
  notice:(text,error=false)=>calls.push(['notice',text,error]),
  setBusy(value){ctx.busy=value;for(const id of ['scan','choose'])element(id).disabled=value;},
  api:(route,payload)=>{calls.push(['api',route,payload]);return request.promise;},
  uploadFile:(file,side)=>{calls.push(['upload',file,side]);return request.promise;},
  acceptArchiveResult:(data,origin)=>calls.push(['result',data,origin])
 };
 vm.createContext(ctx);vm.runInContext(scanHandler+'\n'+archiveHandler+'\n'+chooseHandler,ctx,{filename:'existing-import-handlers.js'});
 vm.runInContext(source,ctx,{filename:'static/start.js'});
 const callsOf=name=>calls.filter(call=>call[0]===name);
 const filesEvent=(files,items=files.map(()=>({kind:'file'})))=>({dataTransfer:{types:['Files'],files,items}});
 return{init,request,ctx,body,element,calls,callsOf,filesEvent};
}
(async()=>{
 // Opening and cancelling the native picker must preserve the cold home screen.
 const cold=fixture();assert.equal(cold.calls.length,0);
 cold.element('home-archive-pick').click();assert.equal(cold.element('home-archive-file').clicks,1);
 cold.element('home-archive-file').emit('change');assert.equal(cold.calls.length,0);
 assert.equal(cold.body.dataset.workspace,'home');assert.equal(cold.element('home-notice').hidden,true);
 cold.element('home-scan').click();assert.equal(cold.calls.length,0);assert.match(cold.element('home-notice').textContent,/目录路径/);
 cold.element('home-pack-path').value='F:/pack';
 cold.element('home-pack-path').emit('keydown',{key:'Enter',isComposing:true});assert.equal(cold.calls.length,0,'IME confirmation does not submit');

 // Snapshot the typed path; wait for initialization before using the real scan.
 const scan=fixture();scan.element('home-pack-path').value='  F:/pack  ';
 const enter=scan.element('home-pack-path').emit('keydown',{key:'Enter'});assert(enter.defaultPrevented);
 assert.equal(scan.callsOf('workspace').length,1);assert.equal(scan.callsOf('api').length,0);
 scan.element('home-scan').click();assert.equal(scan.callsOf('workspace').length,1,'double activation cannot duplicate initialization');
 scan.element('home-pack-path').value='F:/other';scan.init.resolve();await flush();
 assert.equal(scan.element('pack-path').value,'F:/pack');assert.equal(scan.callsOf('api').length,1);
 assert.equal(scan.callsOf('api')[0][1],'/api/scan');assert.equal(scan.callsOf('api')[0][2].path,'F:/pack');
 assert.equal(scan.ctx.busy,true,'the existing async scan remains busy after native click returns');
 scan.body.dataset.workspace='home';scan.element('home-scan').click();assert.equal(scan.callsOf('api').length,1,'returning home cannot start another scan during existing work');
 scan.request.resolve({mods:[]});await flush();assert.equal(scan.ctx.busy,false);

 // A navigation away and back cancels the pending action, even when the final
 // workspace value matches. Leaving for first-run settings behaves the same.
 for(const destination of ['home','settings']){
  const stale=fixture();stale.element('home-pack-path').value='F:/stale';stale.element('home-scan').click();
  stale.body.dataset.workspace=destination;stale.body.dataset.workspace='analysis';
  stale.init.resolve();await flush();assert.equal(stale.callsOf('api').length,0);assert.equal(stale.element('pack-path').value,'');
 }
 const retry=fixture();retry.element('home-pack-path').value='F:/old';retry.element('home-scan').click();
 retry.body.dataset.workspace='home';await flush();assert.equal(retry.element('home-scan').disabled,false);
 retry.element('home-pack-path').value='F:/new';retry.element('home-scan').click();retry.init.resolve();await flush();
 assert.equal(retry.callsOf('api').length,1);assert.equal(retry.callsOf('api')[0][2].path,'F:/new','an older continuation cannot overwrite the newer intent');
 retry.request.resolve({mods:[]});await flush();

 // Directory selection is dispatched once after initialization. The actual
 // chooser retains its cancellation/error handling and does not auto-scan.
 const choose=fixture();choose.element('home-choose').click();assert.equal(choose.callsOf('api').length,0);
 choose.init.resolve();await flush();assert.equal(choose.callsOf('api')[0][1],'/api/choose');
 choose.request.resolve({path:''});await flush();assert.equal(choose.callsOf('api').length,1);assert.equal(choose.element('pack-path').value,'');
 assert(choose.callsOf('notice').some(call=>call[1]==='已取消选择。'));
 const failure=fixture();failure.element('home-choose').click();failure.init.reject(Error('本机服务未连接'));await flush();
 assert.match(failure.element('home-notice').textContent,/本机服务未连接/);assert(failure.element('home-notice').classList.contains('error'));assert.equal(failure.callsOf('api').length,0);assert.equal(failure.element('home-choose').disabled,false);

 // Reject directories, batches, unsupported/oversize files without navigating.
 const invalid=fixture(),zip={name:'pack.zip',size:30};
 invalid.element('home-dropzone').emit('drop',invalid.filesEvent([zip],[{webkitGetAsEntry:()=>({isDirectory:true})}]));
 assert.match(invalid.element('home-notice').textContent,/文件夹/);
 invalid.element('home-dropzone').emit('drop',invalid.filesEvent([zip,zip]));assert.match(invalid.element('home-notice').textContent,/一次/);
 for(const file of [{name:'pack.rar',size:30},{name:'pack.modpack',size:30},{name:'big.zip',size:2*1024**3+1}]){
  invalid.element('home-archive-file').files=[file];invalid.element('home-archive-file').value='selected';invalid.element('home-archive-file').emit('change');assert.equal(invalid.element('home-archive-file').value,'');
 }
 invalid.element('home-dropzone').emit('drop',{dataTransfer:{types:['text/plain'],files:[]}});assert.equal(invalid.calls.length,0);
 const archive=fixture();const dropped=archive.element('home-dropzone').emit('drop',archive.filesEvent([zip]));assert(dropped.stopped&&dropped.defaultPrevented,'the home drop never also reaches the analysis window handler');
 assert.equal(archive.callsOf('upload').length,0);archive.init.resolve();await flush();assert.equal(archive.callsOf('upload').length,1);assert.equal(archive.callsOf('upload')[0][1],zip);
 archive.request.reject(Error('文件导入失败'));await flush();assert.equal(archive.ctx.busy,false);assert(archive.callsOf('notice').some(call=>call[1]==='文件导入失败'&&call[2]));
 const picker=fixture();picker.element('home-dropzone').click();for(const key of ['Enter',' '])picker.element('home-dropzone').emit('keydown',{key});assert.equal(picker.element('home-archive-file').clicks,0,'the noninteractive drop region does not open a picker on click or key input');assert.equal(picker.calls.length,0);
 picker.element('home-archive-pick').click();assert.equal(picker.element('home-archive-file').clicks,1,'the real button remains the picker activation target');assert.equal(picker.calls.length,0);
 picker.element('home-archive-file').files=[zip];picker.element('home-archive-file').emit('change');picker.init.resolve();await flush();assert.equal(picker.callsOf('upload').length,1);picker.request.resolve({mods:[]});await flush();
 console.log('Home import passed: lazy initialization, native picker cancellation, Enter/IME, real handler handoff, busy guard, navigation races, file-only drops and readable errors.');
})().catch(error=>{console.error(error);process.exitCode=1;});
