'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('./static/index.html','utf8');
const source=fs.readFileSync('./static/interface.js','utf8');

// Model only native DOM behavior used by the interface controller. Element IDs,
// initial disclosure states and ancestor relationships come from the real HTML.
function fixture(initialReport){
 const elements=new Map(),all=[],stack=[],requests=[];
 const document={activeElement:null,body:null};
 const voidTags=new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);
 for(const match of html.matchAll(/<!--[\s\S]*?-->|<\/?([a-z][\w-]*)\b[^>]*>|([^<]+)/gi)){
  const token=match[0];if(token.startsWith('<!--'))continue;
  if(match[2]!==undefined){if(stack.length)stack.at(-1).textContent+=match[2];continue;}
  const tag=match[1].toLowerCase();
  if(token.startsWith('</')){const i=stack.findLastIndex(el=>el.tagName===tag);if(i>=0)stack.length=i;continue;}
  const attributes={};for(const attr of token.matchAll(/([\w-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g))attributes[attr[1]]=attr[2]??attr[3]??attr[4]??'';
  const el={tagName:tag,id:attributes.id||'',attributes,dataset:{},parentElement:stack.at(-1)||null,hidden:Object.hasOwn(attributes,'hidden'),open:Object.hasOwn(attributes,'open'),textContent:'',get innerHTML(){return this.markup||'';},set innerHTML(markup){this.markup=String(markup);this.textContent=this.markup.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();},value:'',listeners:new Map(),focusCount:0,
   setAttribute(name,value){this.attributes[name]=String(value);},
   getAttribute(name){return this.attributes[name]??null;},
   addEventListener(type,listener){if(!this.listeners.has(type))this.listeners.set(type,[]);this.listeners.get(type).push(listener);},
   click(){for(const listener of this.listeners.get('click')||[])listener({type:'click',target:this});},
   contains(other){for(let node=other;node;node=node.parentElement)if(node===this)return true;return false;},
   querySelector(selector){assert.equal(selector,'summary');return all.find(el=>el!==this&&el.tagName==='summary'&&this.contains(el))||null;},
   focus(options){this.focusCount++;document.activeElement=this;this.lastFocusOptions=options;}
  };
  for(const [key,value] of Object.entries(attributes))if(key.startsWith('data-'))el.dataset[key.slice(5).replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase())]=value;
  if(el.id){assert(!elements.has(el.id),'duplicate real HTML ID: '+el.id);elements.set(el.id,el);}
  if(tag==='body')document.body=el;all.push(el);if(!voidTags.has(tag)&&!token.endsWith('/>'))stack.push(el);
 }
 const element=id=>{assert(elements.has(id),'interface queried missing real element: '+id);return elements.get(id);};
 const heading=all.find(el=>el.tagName==='h1'&&/\boverview-heading\b/.test(el.parentElement?.parentElement?.attributes.class||''));
 assert(heading,'the overview heading exists');
 document.getElementById=element;document.querySelector=selector=>{assert.equal(selector,'.overview-heading h1');return heading;};
 const request=(...args)=>{requests.push(args);throw Error('interface navigation must not make requests');};
 const ctx={document,console,fetch:request,api:request};ctx.window=ctx;
 if(initialReport!==undefined)ctx.report=initialReport;
 vm.createContext(ctx);vm.runInContext(source,ctx,{filename:'static/interface.js'});
 return {ctx,element,document,heading,requests,sync:(data,newReport=false)=>ctx.damnSyncInterface(data,newReport),progress:running=>ctx.damnSyncEnrichmentDisclosure(running)};
}
const data={pack:'First local report',mods:[{key:'one',name:'Example'}]};
const f=fixture();
assert.equal(f.document.body.dataset.hasReport,'false','a cold entry is explicitly gated as having no report');
assert.equal(f.element('analysis-empty').hidden,false,'the empty state explains how to obtain real results');
assert.equal(f.element('analysis-import-panel').hidden,false,'import is available before scanning');
assert.equal(f.element('analysis-import-toggle').hidden,true,'an empty session offers no misleading change-pack action');
assert.equal(f.element('pack-mode').hidden,true,'there is no fake scan mode before a report exists');
for(const id of ['stat-files','stat-enabled','stat-edges','stat-issues'])assert.equal(f.element(id).textContent.trim(),'—','fresh statistics never pretend a scan found zero: '+id);
assert.equal(f.element('view-overview').dataset.overviewPanel,'mods');
assert.equal(f.requests.length,0,'cold entry does not perform API requests');

// A successful scan collapses the import controls without discarding the path.
f.element('pack-path').value='F:/fixture/mods';f.element('pack-path').focus();f.sync(data,true);
assert.equal(f.document.body.dataset.hasReport,'true');
assert.equal(f.element('analysis-empty').hidden,true);
assert.equal(f.element('pack-mode').hidden,false);
assert.equal(f.element('analysis-import-toggle').hidden,false);
assert.equal(f.element('analysis-import-panel').hidden,true);
assert.equal(f.element('analysis-import-toggle').getAttribute('aria-expanded'),'false');
assert.equal(f.element('analysis-import-toggle').textContent,'展开导入区域','a collapsed import area has an explicit opening action');
assert(!f.element('analysis-import-toggle').textContent.includes('更换整合包'),'the ambiguous old action wording is removed');
assert.equal(f.document.activeElement,f.heading,'focus leaves the now-hidden import controls');
assert.equal(f.heading.lastFocusOptions.preventScroll,true,'focus recovery preserves the user scroll position');
f.element('analysis-import-toggle').click();
assert.equal(f.element('analysis-import-panel').hidden,false,'the user can reopen import after scanning');
assert.equal(f.element('analysis-import-toggle').getAttribute('aria-expanded'),'true');
assert.equal(f.element('analysis-import-toggle').textContent,'收起导入区域','the expanded import area has an explicit closing action');
assert.equal(f.element('pack-path').value,'F:/fixture/mods','reopening retains the existing input');
f.sync(data);
assert.equal(f.element('analysis-import-panel').hidden,false,'metadata updates preserve an import area the user opened');
f.element('analysis-import-toggle').click();
assert.equal(f.element('analysis-import-panel').hidden,true,'a second click closes import');
assert.equal(f.element('analysis-import-toggle').textContent,'展开导入区域','closing returns the button to the explicit opening label');
f.sync(data);
assert.equal(f.element('analysis-import-panel').hidden,true,'metadata updates do not reopen a closed import area');

// The local result tabs only change presentation, never restart matching or AI.
const before=JSON.stringify(data);
for(let i=0;i<3;i++){
 f.element('overview-identity-open').click();
 assert.equal(f.element('view-overview').dataset.overviewPanel,'identity');
 assert.equal(f.element('overview-mods-open').getAttribute('aria-pressed'),'false');
 assert.equal(f.element('overview-identity-open').getAttribute('aria-pressed'),'true');
 f.element('overview-mods-open').click();
 assert.equal(f.element('view-overview').dataset.overviewPanel,'mods');
 assert.equal(f.element('overview-mods-open').getAttribute('aria-pressed'),'true');
 assert.equal(f.element('overview-identity-open').getAttribute('aria-pressed'),'false');
}
assert.equal(JSON.stringify(data),before,'presentation switches do not alter the report');
assert.equal(f.requests.length,0,'import/result navigation never calls the platform or AI');
f.element('overview-identity-open').click();f.element('analysis-import-toggle').click();
f.progress(true);f.sync({pack:'Second local report',mods:[]},true);
assert.equal(f.element('view-overview').dataset.overviewPanel,'mods','a newly loaded report returns to the mod list');
assert.equal(f.element('analysis-import-panel').hidden,true,'a new report closes the previous import controls');
assert.equal(f.element('enrich-panel').open,false,'a new report does not retain another report\'s progress disclosure');

// Only task transitions control native disclosure. Polling honors a manual close.
f.progress(true);assert.equal(f.element('enrich-panel').open,true,'starting a task exposes its progress once');
f.element('enrich-panel').open=false;
for(let tick=0;tick<20;tick++){f.progress(true);f.sync(data);}
assert.equal(f.element('enrich-panel').open,false,'twenty status updates respect the user\'s manual close');
f.element('enrich-panel').open=true;f.progress(false);
assert.equal(f.element('enrich-panel').open,false,'finishing a running task collapses its progress');
f.progress(true);assert.equal(f.element('enrich-panel').open,true,'a later task can expose progress again');
f.progress(false);assert.equal(f.element('enrich-panel').open,false);
assert.equal(f.requests.length,0,'disclosure transitions have no networking side effects');

// A task completing must not leave keyboard focus in the collapsed controls.
const focusCase=fixture(data),progressPanel=focusCase.element('enrich-panel');
progressPanel.hidden=false;const progressSummary=progressPanel.querySelector('summary');
assert(progressSummary,'the native progress disclosure has a real summary element');
for(const id of ['enrich-stop','enrich-refresh']){
 focusCase.progress(true);const action=focusCase.element(id);action.hidden=false;action.focus();
 const focusCount=progressSummary.focusCount;focusCase.progress(false);
 assert.equal(progressPanel.open,false);
 assert.equal(focusCase.document.activeElement,progressSummary,'completion returns focus from '+id+' to the visible summary');
 assert.equal(progressSummary.focusCount,focusCount+1,'completion moves focus only once');
 assert.equal(progressSummary.lastFocusOptions.preventScroll,true,'completion focus recovery does not move the page');
}
focusCase.progress(true);progressSummary.focus();
const summaryFocusCount=progressSummary.focusCount;focusCase.progress(false);
assert.equal(focusCase.document.activeElement,progressSummary,'focus already on the summary stays there');
assert.equal(progressSummary.focusCount,summaryFocusCount,'completion does not redundantly refocus the summary');
focusCase.progress(true);focusCase.heading.focus();focusCase.progress(false);
assert.equal(focusCase.document.activeElement,focusCase.heading,'completion leaves focus outside the disclosure undisturbed');
assert.equal(progressSummary.focusCount,summaryFocusCount);
assert.equal(focusCase.requests.length,0,'focus recovery does not perform requests');

// Restoring a cached report uses the same loaded state as a successful scan.
const restored=fixture(data);
assert.equal(restored.document.body.dataset.hasReport,'true');
assert.equal(restored.element('analysis-empty').hidden,true);
assert.equal(restored.element('analysis-import-panel').hidden,true);
assert.equal(restored.element('view-overview').dataset.overviewPanel,'mods');
restored.sync(null,true);
assert.equal(restored.document.body.dataset.hasReport,'false','clearing results restores the empty state gate');
assert.equal(restored.element('analysis-empty').hidden,false);
assert.equal(restored.element('analysis-import-panel').hidden,false);
assert.equal(restored.element('analysis-import-toggle').hidden,true);
console.log('Interface behavior passed: honest empty state, reversible import collapse, request-free result tabs, report reset, focus recovery and user-controlled progress across polling.');
