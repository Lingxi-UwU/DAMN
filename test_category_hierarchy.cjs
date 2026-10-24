'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const c=require('./static/catalog.js'),taxonomy=require('./taxonomy.json');
const expected={adventure:'冒险探索',cursed:'怪趣',decoration:'建筑装饰',economy:'经济',equipment:'装备工具',food:'饮食','game-mechanics':'玩法机制',library:'开发库',magic:'魔法',management:'管理',minigame:'迷你游戏',mobs:'生物',optimization:'性能优化',social:'社交',storage:'存储',technology:'科技',transportation:'交通',utility:'实用工具',worldgen:'世界生成'};
assert.equal(taxonomy.version,3);assert.equal(taxonomy.layout,'flat-official-modrinth-facets');
assert.deepEqual(taxonomy.sources[0].officialSnapshot.map(x=>x.name),Object.keys(expected),'all recorded official mod-category slugs remain represented');
assert.deepEqual(c.DAMN_CATEGORIES,[...Object.values(expected),'其他 / 待识别']);
assert(taxonomy.categories.every(x=>!x.parent),'the public category data has no inherited hierarchy');
assert.deepEqual(taxonomy.platformIds,{},'private numeric category dictionaries are not required');
const platformMod=(slug,extra={})=>({name:'Synthetic project',platformTaxonomy:[{site:'Modrinth',matched:true,categories:[slug]}],...extra});
for(const [slug,label] of Object.entries(expected)){
 const m=platformMod(slug);assert.equal(c.damnCategoryInfo(m).category,label,slug);assert.equal(c.damnFilterMods([m],{category:label}).length,1);assert.equal(c.damnCategoryInfo(m).version,3);
}
const mods=[{name:'Generator',description:'提供能源与机器。'},{name:'Machines',description:'自动化加工机器。'},{name:'Framework',description:'为其他模组提供开发框架。'},{name:'Unknown',description:'仅有下载清单。'}];
const counts=c.damnCategoryCounts(mods),branches=c.damnCategoryBranchCounts(mods);
assert.equal(Object.values(counts).reduce((a,b)=>a+b,0),mods.length,'single-category records count once');
assert.deepEqual(branches,counts,'flat facets do not invent branch totals');assert.equal(counts['科技'],2);assert.equal(counts['开发库'],1);
assert.equal(c.damnFilterMods(mods,{category:'科技'}).length,2);assert.equal(c.damnFilterMods(mods,{category:'科技',search:'能源'}).length,1);
assert.deepEqual(c.damnVisibleCategories(mods).map(x=>x.label),['开发库','科技','其他 / 待识别']);
for(const [old,label] of Object.entries(taxonomy.legacy))assert.equal(c.damnNormalizeCategory(old),label);
assert.equal(c.damnNormalizeCategory('not-a-category'),'其他 / 待识别');
const app=fs.readFileSync('./static/app.js','utf8');
function categoryFixture(model,records){const elements={},ctx={...model,report:{mods:records},esc:String,document:{activeElement:null},$:id=>elements[id]??={value:'',innerHTML:'',querySelectorAll(){return [];}},console};vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('function updateCategorySelection(){'),app.indexOf('function categoryTagsHTML(')),ctx);vm.runInContext('updateCategories()',ctx);return {ctx,elements};}
const {ctx,elements}=categoryFixture(c,mods);
assert(!elements['#category'].innerHTML.includes('↳'),'official flat facets display without child indentation');
assert(!elements['#usage-categories'].innerHTML.includes('usage-family'));assert(!elements['#usage-categories'].innerHTML.includes('魔法'));
elements['#category'].value='科技';ctx.report.mods=[mods[2]];vm.runInContext('updateCategories()',ctx);assert.equal(elements['#category'].value,'');assert(!elements['#category'].innerHTML.includes('科技'));
const multi={name:'Synthetic multi-facet project',platformTaxonomy:[{site:'Modrinth',matched:true,categories:['technology','equipment','technology']},{site:'Modrinth',matched:true,categories:['equipment']}]};
assert.deepEqual(new Set(c.damnCategoryInfo(multi).categories),new Set(['科技','装备工具']));assert.equal(c.damnFilterMods([multi],{category:'科技'}).length,1);assert.equal(c.damnFilterMods([multi],{category:'装备工具'}).length,1);
assert.equal(c.damnCategoryBranchCounts([multi])['科技'],1,'repeated facet evidence never duplicates a mod');
assert.equal(c.damnCategoryInfo(platformMod('utility',{platformTaxonomy:[{site:'Modrinth',matched:false,categories:['utility']}]})).category,'其他 / 待识别','unconfirmed search results do not assign official categories');
assert.equal(c.damnCategoryInfo({name:'Unknown',platformTaxonomy:[{site:'CurseForge',categoryIds:[412,4843,434]}]}).category,'其他 / 待识别','numeric IDs outside the public mapping remain unknown');
const late={name:'Unknown'};assert.equal(c.damnCategoryInfo(late).category,'其他 / 待识别');late.aiAnnotation={summary:'提供玩家聊天和社交互动。'};assert.equal(c.damnCategoryInfo(late).category,'社交','a newly displayed summary invalidates cached fallback');late.platformTaxonomy=[{site:'Modrinth',categories:['utility'],matched:true}];assert.equal(c.damnCategoryInfo(late).category,'实用工具','official categories precede inferred descriptions');
// Generic hierarchy helpers remain available for a consumer-supplied taxonomy.
// This artificial fixture is independent of the public official-category data.
const artificial={version:3,legacy:{},tagAliases:{},platformAliases:{'fixture-parent':'Fixture parent','fixture-child':'Fixture child'},platformIds:{},categories:[{label:'Fixture parent',group:'Fixture parent',description:'Synthetic parent',platform:['fixture-parent'],rules:[],features:[]},{label:'Fixture child',parent:'Fixture parent',group:'Fixture parent',description:'Synthetic child',platform:['fixture-child'],rules:[],features:[]},{label:'其他 / 待识别',group:'其他 / 待识别',description:'Unknown',platform:[],rules:[],features:[]}]};
const isolated={module:{exports:{}},require(file){assert.equal(file,'../taxonomy.json');return artificial;}};vm.createContext(isolated);vm.runInContext(fs.readFileSync('./static/catalog.js','utf8'),isolated);const h=isolated.module.exports;
const child={name:'Synthetic child project',platformTaxonomy:[{site:'Modrinth',categories:['fixture-parent','fixture-child','fixture-child'],matched:true}]},parent={name:'Synthetic parent project',platformTaxonomy:[{site:'Modrinth',categories:['fixture-parent'],matched:true}]};
assert.equal(h.damnCategoryInfo(child).categories.join('|'),'Fixture child','specific child supersedes duplicate parent evidence');assert.equal(h.damnCategoryCounts([child,parent])['Fixture parent'],1);assert.equal(h.damnCategoryBranchCounts([child,parent])['Fixture parent'],2);assert.equal(h.damnCategoryBranchCounts([child,parent])['Fixture child'],1);assert.equal(h.damnFilterMods([child,parent],{category:'Fixture parent'}).length,2);assert.equal(h.damnFilterMods([child,parent],{category:'Fixture child'}).length,1);
const nested=categoryFixture(h,[child,parent]);assert.match(nested.elements['#category'].innerHTML,/↳ Fixture child（1）/);assert.match(nested.elements['#usage-categories'].innerHTML,/usage-family/);
// The actual navigation handler keeps exactly one active accessible page.
const bodyClasses=new Set(),views=['overview','network','issues'].map(view=>({id:'view-'+view,hidden:false}));
const nav=['overview','network','issues'].map(view=>({dataset:{view},attributes:{},classList:{toggle(name,on){this[name]=on;}},setAttribute(k,v){this.attributes[k]=v;},removeAttribute(k){delete this.attributes[k];}}));
let graphs=0;
const navctx={document:{body:{classList:{toggle(name,on){if(on)bodyClasses.add(name);else bodyClasses.delete(name);}}}},$$:selector=>selector==='.view'?views:nav,$:()=>elements.label??={textContent:''},renderGraph:()=>graphs++};
vm.createContext(navctx);vm.runInContext(app.slice(app.indexOf('function showView('),app.indexOf("\n$$('.nav[data-view]')")),navctx);
for(const view of ['issues','network','overview']){vm.runInContext(`showView('${view}')`,navctx);assert.equal(views.filter(v=>!v.hidden).length,1);assert.equal(nav.filter(n=>n.attributes['aria-current']==='page').length,1);assert.equal(nav.find(n=>n.attributes['aria-current']==='page').dataset.view,view);}
assert.equal(graphs,1);assert.equal(bodyClasses.size,0);
const network=require('./static/network.js'),nodes=[{key:'a'},{key:'b'},{key:'c'}],edges=[{from:'a',to:'b',kind:'required'}];
assert.deepEqual(network.filterNetworkNodes(nodes,edges).nodes.map(n=>n.key),['a','b']);
assert.equal(network.filterNetworkNodes(nodes,edges).hidden,1);assert.equal(network.filterNetworkNodes(nodes,edges,true).nodes.length,3);
assert.equal(network.filterNetworkNodes(nodes,[]).nodes.length,0);assert.equal(network.filterNetworkNodes(nodes,[]).hidden,3);
console.log('Public category checks passed: all official slugs, flat filters and counts, evidence precedence, cache refresh, isolated generic hierarchy and accessible navigation.');
