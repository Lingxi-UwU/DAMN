'use strict';
const assert=require('node:assert/strict');
const {NETWORK_CARD,networkEdges,networkRelationGroups,buildNetworkLayout}=require('./static/network.js');
const mods=Array.from({length:278},(_,i)=>({key:'m'+i}));
const local=[{from:'m0',to:'m1'},{from:'m1',to:'m2'}],web=[{from:'m0',to:'m1',kind:'required'},{from:'m2',to:'m3',kind:'optional'},{from:'m0',to:'missing',kind:'related'}];
const edges=networkEdges(mods,local,web);
assert.equal(edges.length,3);assert.equal(edges[0].web,false);
const layout=buildNetworkLayout(mods,edges);
assert.equal(layout.nodes.length,278);assert.equal(new Set(layout.nodes.map(n=>n.key)).size,278);
assert(layout.nodes.some(n=>n.key==='m277'&&n.degree===0));
assert(layout.nodes.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)&&n.x>=0&&n.x<=layout.width&&n.y>=0&&n.y<=layout.height));
const dense=networkEdges(mods,mods.slice(1).map(m=>({from:'m0',to:m.key})));
assert.equal(buildNetworkLayout(mods,dense).nodes.length,278);
function clearCards(subjects,relations,label){
 const result=buildNetworkLayout(subjects,relations),{width,height,gapX,gapY}=NETWORK_CARD;
 assert.equal(result.nodes.length,subjects.length,label+' preserves all nodes');
 for(const p of result.nodes)assert(p.x-width/2>=0&&p.y-height/2>=0&&p.x+width/2<=result.width&&p.y+height/2<=result.height,label+' keeps whole cards on canvas');
 for(let i=0;i<result.nodes.length;i++)for(let j=i+1;j<result.nodes.length;j++){
  const a=result.nodes[i],b=result.nodes[j];
  assert(Math.abs(a.x-b.x)>=width+gapX-1e-6||Math.abs(a.y-b.y)>=height+gapY-1e-6,label+' has clearance between '+a.key+' and '+b.key);
 }
 return result;
}
const star=clearCards(mods,dense,'278 mods sharing a core');
assert.deepEqual(star,buildNetworkLayout(mods,dense),'layout is stable on repeated renders');
const hubs=mods.slice(2).flatMap((m,i)=>[{from:m.key,to:'m0'},{from:m.key,to:'m1'},...(i%3===0?[{from:m.key,to:mods[(i+3)%mods.length].key}]:[])]);
clearCards(mods,hubs,'two connected core mods');
clearCards(mods,mods.slice(1).map((m,i)=>({from:m.key,to:mods[i].key})),'long dependency chain');
clearCards(mods,edges,'separate components and isolated mods');
const complete=mods.slice(0,64);clearCards(complete,complete.flatMap((a,i)=>complete.slice(i+1).map(b=>({from:a.key,to:b.key}))),'many shared dependencies');
const large=Array.from({length:900},(_,i)=>({key:'big'+i}));clearCards(large,large.slice(1).map(m=>({from:m.key,to:'big0'})),'large pack beyond force-layout threshold');
assert.deepEqual(buildNetworkLayout([],[]).nodes,[]);
const directionMods=['a','b','c','d','e','f'].map(key=>({key,name:'完整模组名称 '+key}));
const directionEdges=networkEdges(directionMods,[{from:'a',to:'b'},{from:'c',to:'a'}],[{from:'d',to:'a',kind:'required'},{from:'a',to:'c',kind:'optional'},{from:'a',to:'e',kind:'ecosystem'},{from:'a',to:'f',kind:'related'},{from:'f',to:'a',kind:'used_by'}]);
const roles=networkRelationGroups(directionMods,directionEdges,'a');
assert.deepEqual(roles.prerequisites.map(r=>r.key).sort(),['b','c']);
assert.deepEqual(roles.dependents.map(r=>r.key).sort(),['c','d','f']);
assert.deepEqual(roles.ecosystem.map(r=>r.key),['e']);assert.deepEqual(roles.other.map(r=>r.key),['f']);
assert.equal(roles.prerequisites.find(r=>r.key==='b').basis,'文件声明');assert.equal(roles.dependents.find(r=>r.key==='d').basis,'网页资料 · 待核对');
assert(roles.dependents.find(r=>r.key==='f').label.includes('待核对'));
assert(roles.prerequisites.every(r=>r.name.startsWith('完整模组名称')));
assert.deepEqual(networkRelationGroups(directionMods,directionEdges,'b').dependents.map(r=>r.key),['a'],'dependency direction reverses for the selected prerequisite');
console.log('Network checks passed: all nodes and edges preserved, no card overlap or clipping in hub, shared-core, chain, isolated, dense and 900-mod networks.');
