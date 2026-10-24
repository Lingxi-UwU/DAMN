'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const root=__dirname,staticRoot=path.join(root,'static'),read=file=>fs.readFileSync(path.join(staticRoot,file),'utf8');
const whitelist=['app.js','catalog.js','classification.js','desktop-footer.css','desktop-ui.css','desktop-ui.js','empty-workspaces.css','feedback.js','home-motion.js','identity.css','identity.js','index.html','interface.css','interface.js','legacy-workbench.css','motion.js','native-controls.css','network.js','onboarding.css','onboarding.js','progress.js','public-appearance.css','settings-categories.css','settings-categories.js','start.js','style.css','suite-cards.css','suite-cards.js','suite-controls.css','suite-ui.js','suite.css','tooltips.css','tooltips.js','updates.css','updates.js','workbench.css','workspaces.css','workspaces.js'];
assert.deepEqual(fs.readdirSync(staticRoot).sort(),whitelist.sort(),'public assets use an explicit allowlist');
const html=read('index.html');assert(html.includes('data-theme="forest"'));assert(!html.includes('__THEME__'));
const forbidden=/personalization|theme-choice|os-dock|os-actor|damn-companion|companion-body|appearance-spark|sponsor|unlock|milestone|activation|easter.?egg|device.?id/i;
for(const file of whitelist){const text=read(file);assert(!forbidden.test(text),file+' contains an excluded feature');if(file.endsWith('.js'))new vm.Script(text,{filename:file});}
const ids=[...html.matchAll(/\bid=["']([^"']+)["']/g)].map(m=>m[1]);assert.equal(ids.length,new Set(ids).size,'ordinary DOM IDs remain unique');
for(const script of html.matchAll(new RegExp('<script[^>]+src="/([^"/]+)"','g')))assert(script[1]==='taxonomy.js'||whitelist.includes(script[1]),'missing public script '+script[1]);
for(const id of ['updates-check','updates-install'])assert(new RegExp('<button[^>]*id="'+id+'"[^>]* disabled(?:[ >])').test(html),id+' must be unavailable in real markup');
assert(!/<(?:button|input|select)\b[^>]*(?:data-theme|appearance-code|appearance-redeem)/.test(html));
function fixture(){
 const calls=[],observers=[],nodes=new Map();let handler;
 function el(id){if(nodes.has(id))return nodes.get(id);const listeners=new Map(),attributes={};const n={id,dataset:{},value:'',textContent:'',className:'',hidden:false,disabled:false,attributes,setAttribute(k,v){attributes[k]=String(v);},addEventListener(k,f){listeners.set(k,f);},removeEventListener(k,f){if(listeners.get(k)===f)listeners.delete(k);},emit(k){return listeners.get(k)?.({target:n});}};nodes.set(id,n);return n;}
 const body=el('body');body.dataset.workspace='home';const dialog=el('settings-dialog');dialog.dataset.settingsCategory='appearance';
 const document={body,hidden:false,getElementById:el,addEventListener(){},removeEventListener(){}};const events=new Map();
 const data=p=>({schemaVersion:1,serviceConfigured:false,status:'not_configured',currentVersion:'0.5.6',preferences:p||{channel:'stable',checkMode:'manual'}});
 const api=async(route,body)=>{calls.push({route,body});return handler?handler(route,body):data(body);};
 const context={document,api,window:{addEventListener(k,f){events.set(k,f);}},MutationObserver:class{constructor(fn){this.fn=fn;observers.push(this);}observe(){}disconnect(){}}};
 vm.runInNewContext(read('updates.js'),context);
 return {calls,nodes,el,body,dialog,data,events,setHandler(fn){handler=fn;},show(){body.dataset.workspace='settings';dialog.dataset.settingsCategory='updates';observers.forEach(o=>o.fn());},hide(){body.dataset.workspace='home';observers.forEach(o=>o.fn());},mutate(){observers.forEach(o=>o.fn());}};
}
const settle=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
(async()=>{
 const assembly=await import(pathToFileURL(path.join(root,'tools','assemble.mjs')).href);await assembly.assemble({check:true});const before=await assembly.expectedBundles();await assembly.assemble();assert.deepEqual(await assembly.expectedBundles(),before,'assembly is deterministic');
 const f=fixture();assert.equal(f.calls.length,0,'startup does not check update services');assert(f.el('updates-check').disabled);assert(f.el('updates-install').disabled);
 f.show();await settle();assert.deepEqual(f.calls.map(x=>x.route),['/api/updates']);assert.equal(f.el('updates-current-version').textContent,'0.5.6');assert(!f.el('updates-channel').disabled);
 f.el('updates-channel').value='preview';f.el('updates-check-mode').value='startup';f.el('updates-channel').emit('change');await settle();assert.equal(f.calls.at(-1).route,'/api/updates/preferences');assert.equal(f.calls.at(-1).body.channel,'preview');assert.equal(f.calls.at(-1).body.checkMode,'startup');
 assert(f.el('updates-check').disabled);assert(f.el('updates-install').disabled);assert(f.el('updates-check-status').textContent.includes('未接入'));assert(!f.calls.some(x=>/check|install|notification/.test(x.route)));
 const count=f.calls.length;f.hide();f.mutate();await settle();assert.equal(f.calls.length,count,'hidden settings do not poll');
 f.show();await settle();f.setHandler(()=>{throw Error('local write failed');});f.el('updates-channel').value='preview';f.el('updates-channel').emit('change');await settle();assert.equal(f.el('updates-channel').value,'stable','failed local preference writes restore saved values');assert(f.el('updates-preference-status').className.includes('error'));
 console.log('Public frontend checks passed: asset allowlist, excluded feature boundary, unique DOM, JavaScript syntax, deterministic bundles and local-only update preferences.');
})().catch(error=>{console.error(error);process.exitCode=1;});
