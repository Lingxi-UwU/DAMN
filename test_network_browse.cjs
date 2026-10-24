'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const logic=require('./static/network.js'),source=fs.readFileSync('./static/app.js','utf8');
const escape=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const decode=value=>String(value).replace(/&(amp|lt|gt|quot|#39);/g,(_,entity)=>({amp:'&',lt:'<',gt:'>',quot:'"','#39':"'"}[entity]));
function classes(value=''){
 const values=new Set(value.split(/\s+/).filter(Boolean));
 return {contains:name=>values.has(name),add:name=>values.add(name),remove:name=>values.delete(name),toggle(name,force){const enabled=force===undefined?!values.has(name):force;if(enabled)values.add(name);else values.delete(name);return enabled;}};
}
class Element{
 constructor(tag='div',attributes={}){this.tag=tag;this.attributes={...attributes};this.dataset={};for(const [key,value]of Object.entries(attributes))if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=value;this.classList=classes(attributes.class);this.listeners={};this.value='';this.checked=false;this.textContent='';this._html='';this.parts=[];}
 set innerHTML(value){
  this._html=value;this.parts=[];
  for(const match of value.matchAll(/<([a-z][\w-]*)(\s[^>]*?)?>/gi)){
   const attributes={};for(const attribute of (match[2]||'').matchAll(/([\w-]+)(?:="([^"]*)")?/g))attributes[attribute[1]]=decode(attribute[2]??'');
   this.parts.push(new Element(match[1],attributes));
  }
 }
 get innerHTML(){return this._html;}
 querySelectorAll(selector){
  if(selector==='svg')return this.parts.filter(el=>el.tag==='svg');
  if(selector==='.graph-links line')return this.parts.filter(el=>el.tag==='line');
  const data=/^\[([\w-]+)\]$/.exec(selector);if(data)return this.parts.filter(el=>Object.hasOwn(el.attributes,data[1]));
  if(selector.startsWith('.'))return this.parts.filter(el=>el.classList.contains(selector.slice(1)));
  return this.parts.filter(el=>el.tag===selector);
 }
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 addEventListener(name,listener){(this.listeners[name]??=[]).push(listener);}
 fire(name,event={}){for(const listener of this.listeners[name]||[])listener({target:this,preventDefault(){},...event});}
 setAttribute(name,value){this.attributes[name]=value;}
 getBoundingClientRect(){return {left:0,top:0,width:900,height:600};}
 setPointerCapture(){}
}
function setup(data,key='a'){
 const elements=new Map(['network-kind','network-graph','network-relations','network-info','network-all','network-select','network-zoom-in','network-zoom-out','network-fit','network-show-isolated'].map(id=>['#'+id,new Element()]));
 elements.get('#network-kind').value='all';
 const body={classList:classes('network-view')},calls={list:0,detail:0};
 const context={...logic,report:data,selected:key,networkFocus:null,networkRelationView:'direct',graphView:null,graphBase:null,graphCache:null,document:{body},esc:escape,calls,
  $(selector){if(selector==='#network-graph svg')return elements.get('#network-graph').querySelector('svg');if(!elements.has(selector))throw Error('Unexpected selector '+selector);return elements.get(selector);},
  mod(key){return context.report?.mods.find(mod=>mod.key===key);},short(text,n=26){return String(text).length>n?String(text).slice(0,n)+'…':String(text);},effectiveCategory(){return '测试分类';},
  renderList(){calls.list++;},renderDetail(){calls.detail++;}};
 vm.createContext(context);
 const selectStart=source.indexOf('function updateNetworkSelect()'),selectEnd=source.indexOf('async function api(',selectStart);
 const start=source.indexOf('function renderNetworkDependencyTree('),end=source.indexOf('function renderIssues(){',start);
 assert(selectStart>=0&&selectEnd>selectStart&&start>=0&&end>start,'network entry points exist');
 vm.runInContext(source.slice(selectStart,selectEnd)+'\n'+source.slice(start,end),context);
 return {context,el:id=>elements.get('#'+id),run:code=>vm.runInContext(code,context),calls};
}
const mods=['a','b','c','d','e','f','isolated'].map(key=>({key,name:'模组 '+key,kind:'jar'}));
const data={mode:'scan',mods,edges:[{from:'a',to:'b',kind:'required',id:'b',source:'a.jar!/META-INF/neoforge.mods.toml'}],webEdges:[
 {from:'a',to:'c',kind:'optional',origin:'platform',source:'https://modrinth.com/mod/c'},
 {from:'a',to:'d',kind:'incompatible',origin:'platform'},
 {from:'a',to:'e',kind:'ecosystem',origin:'ai'},{from:'f',to:'a',kind:'required',origin:'ai'}]};
const failures=[];let passed=0;
function check(name,body){try{body();passed++;}catch(error){failures.push(name+': '+error.message);}}
const lineKeys=h=>h.el('network-graph').querySelectorAll('.graph-links line').map(el=>el.dataset.from+'>'+el.dataset.to).sort();
const jumpKeys=h=>h.el('network-relations').querySelectorAll('[data-network-jump]').map(el=>el.dataset.networkJump).sort();
check('relation filters drive graph and direct sidebar together',()=>{
 const h=setup(data);h.run('renderGraph(true)');
 assert.deepEqual(lineKeys(h),['a>b','a>c','a>d','a>e','f>a']);assert.deepEqual(jumpKeys(h),['b','c','d','e','f']);
 for(const [kind,expected]of [['required',['a>b','f>a']],['optional',['a>c']],['incompatible',['a>d']]]){
  h.el('network-kind').value=kind;h.el('network-kind').fire('change');
  assert.deepEqual(lineKeys(h),expected,kind+' graph');
  assert.deepEqual(jumpKeys(h),expected.map(key=>key.split('>')).map(([from,to])=>from==='a'?to:from).sort(),kind+' direct relationships');
  assert.equal(h.context.selected,'a');assert.equal(h.context.networkFocus,null);
 }
 assert.equal(h.calls.list,0,'changing the relation type must not silently select another mod');
});
check('type changes and returning global keep the selected key',()=>{
 const h=setup(data,'isolated');h.el('network-kind').value='optional';h.run('renderGraph(true)');
 assert.equal(h.context.selected,'isolated');assert(h.el('network-relations').innerHTML.includes('模组 isolated'));
 h.el('network-kind').value='all';h.el('network-kind').fire('change');
 assert.equal(h.context.selected,'isolated');assert.equal(h.calls.list,0);
 h.context.networkFocus='isolated';h.el('network-all').fire('click');
 assert.equal(h.context.networkFocus,null);assert.equal(h.context.selected,'isolated');
 assert(h.el('network-relations').innerHTML.includes('模组 isolated'));
});
check('tree names and keys stay escaped, with cycle and shared leaves',()=>{
 const hostileName='<img src=x onerror=alert(1)> & "name"',hostileKey='b" data-danger="yes';
 const records={mods:[{key:'a',name:'Root'},{key:hostileKey,name:hostileName},{key:'c',name:'C'},{key:'d',name:'D'}],edges:[
  {from:'a',to:hostileKey,kind:'required'},{from:'a',to:'c',kind:'required'},{from:hostileKey,to:'d',kind:'required'},
  {from:'c',to:'d',kind:'required'},{from:'d',to:'a',kind:'required'}],webEdges:[]};
 const h=setup(records);h.context.networkRelationView='tree';h.run('renderGraph(true)');
 const html=h.el('network-relations').innerHTML;
 assert(!html.includes('<img'));assert(html.includes(escape(hostileName)));assert(!html.includes('data-danger="yes"'));
 assert(html.includes('循环依赖 · 已停止展开'));assert(html.includes('共享前置 · 已在其他分支展开'));
 assert(html.includes('<details class="network-tree-branch"><summary>'),'native details exposes a keyboard-operable expanding branch');
 assert(!html.includes('onclick='));assert(jumpKeys(h).includes(hostileKey),'escaped attributes round-trip to their original key');
});
check('tree depth limits are explained',()=>{
 const records={mods:Array.from({length:40},(_,i)=>({key:'deep'+i,name:'Deep '+i})),edges:Array.from({length:39},(_,i)=>({from:'deep'+i,to:'deep'+(i+1),kind:'required'})),webEdges:[]};
 const h=setup(records,'deep0');h.context.networkRelationView='tree';h.run('renderGraph(true)');
 assert(h.el('network-relations').innerHTML.includes('链条较深，后续未展开'));assert(h.el('network-relations').innerHTML.includes('以此模组为中心'));
});
check('tree/direct switches, branch jump, selector and global return use real listeners',()=>{
 const h=setup(data);h.run('renderGraph(true)');
 h.el('network-relations').querySelectorAll('[data-network-view]').find(el=>el.dataset.networkView==='tree').fire('click');
 assert.equal(h.context.networkRelationView,'tree');assert(h.el('network-relations').innerHTML.includes('必需前置链'));
 assert.deepEqual(jumpKeys(h),['b'],'optional and ecosystem links do not become prerequisites');
 h.el('network-relations').querySelector('[data-network-jump]').fire('click');
 assert.equal(h.context.selected,'b');assert.equal(h.context.networkFocus,'b');assert.equal(h.el('network-select').value,'b');
 assert.equal(h.calls.list,1);assert.equal(h.calls.detail,1);
 h.el('network-all').fire('click');assert.equal(h.context.networkFocus,null);assert.equal(h.context.selected,'b');assert.equal(h.el('network-select').value,'');
 h.el('network-select').value='a';h.el('network-select').fire('change');assert.equal(h.context.networkFocus,'a');assert.equal(h.context.selected,'a');
 h.el('network-relations').querySelectorAll('[data-network-view]').find(el=>el.dataset.networkView==='direct').fire('click');
 assert.equal(h.context.networkRelationView,'direct');assert(!h.el('network-relations').innerHTML.includes('<h4>必需前置链</h4>'));
});
check('non-required tree view can return to the required filter',()=>{
 const h=setup(data);h.context.networkRelationView='tree';h.el('network-kind').value='optional';h.run('renderGraph(true)');
 assert(h.el('network-relations').innerHTML.includes('前置链仅展示必需关系'));
 h.el('network-relations').querySelector('[data-network-reset-kind]').fire('click');
 assert.equal(h.el('network-kind').value,'required');assert.deepEqual(lineKeys(h),['a>b','f>a']);assert.equal(h.context.selected,'a');
 assert(h.el('network-relations').innerHTML.includes('必需前置链'));
});
check('empty filtered results clear viewport and allow safe graph controls',()=>{
 const h=setup(data);h.run('renderGraph(true)');assert(h.context.graphView&&h.context.graphBase);
 h.context.networkFocus='b';h.el('network-kind').value='incompatible';h.el('network-kind').fire('change');
 assert.equal(h.context.graphView,null);assert.equal(h.context.graphBase,null);assert.equal(h.context.selected,'a');
 assert(h.el('network-graph').innerHTML.includes('暂无已知不兼容关系'));assert.equal(h.el('network-graph').querySelector('svg'),null);
 for(const id of ['network-fit','network-zoom-in','network-zoom-out'])assert.doesNotThrow(()=>h.el(id).fire('click'));
 assert.equal(h.context.graphView,null,'fit must not make an empty viewport object');
 h.el('network-show-isolated').checked=true;h.run('renderGraph(true)');
 assert(h.context.graphView&&h.context.graphBase);assert.equal(h.el('network-graph').querySelectorAll('[data-node]').length,1);
 assert.equal(h.context.selected,'a');
});
check('empty reports remove stale graph and selected relationships',()=>{
 const h=setup(data);h.run('renderGraph(true)');assert(h.el('network-relations').innerHTML.includes('模组 a'));
 h.context.report={mods:[],edges:[],webEdges:[]};h.run('renderGraph(true)');
 assert.equal(h.context.graphView,null);assert.equal(h.context.graphBase,null);assert.equal(h.el('network-graph').querySelector('svg'),null);
 assert(!h.el('network-relations').innerHTML.includes('模组 a'),'old selected relationships must disappear');
 assert(!h.el('network-info').textContent.includes('7 个模组'));
 for(const id of ['network-fit','network-zoom-in','network-zoom-out'])assert.doesNotThrow(()=>h.el(id).fire('click'));
 h.context.report=null;assert.doesNotThrow(()=>h.run('renderGraph(true)'));
});
if(failures.length){console.error(failures.join('\n'));throw Error(failures.length+' network browsing check(s) failed');}
console.log('Network browsing checks passed ('+passed+' groups): escaped tree, cycle/shared limits, consistent filters, preserved selection, expand/jump/return listeners and empty viewport safety.');
