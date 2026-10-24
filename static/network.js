'use strict';
const NETWORK_CARD={width:140,height:36,gapX:40,gapY:30};
function filterNetworkNodes(mods,edges,showIsolated=false){
 const valid=new Set(mods.map(m=>m.key)),links=edges.filter(e=>valid.has(e.from)&&valid.has(e.to)&&e.from!==e.to),connected=new Set(links.flatMap(e=>[e.from,e.to]));
 const nodes=showIsolated?mods:mods.filter(m=>connected.has(m.key));
 return {nodes,edges:links,hidden:mods.length-nodes.length};
}
function relationName(value){return String(value||'').split(/[\\/]/).pop().replace(/\.jar(?:\.disabled)?$/i,'').replace(/[-_ ](?:v?\d+\.\d+|neoforge|forge|fabric|quilt).*$/i,'').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g,'');}
function relationPlatform(r){
 if(['Modrinth','CurseForge'].includes(r.platform))return r.platform;
 try{const host=new URL(r.source).hostname;if(host==='modrinth.com'||host.endsWith('.modrinth.com'))return 'Modrinth';if(host==='curseforge.com'||host.endsWith('.curseforge.com'))return 'CurseForge';}catch{}
 return /^(Modrinth|CurseForge) 项目 /.exec(r.target||'')?.[1]||'';
}
function modIdentity(m){
 const ids={...m.platformInfo?.projectIds},versions=new Set([m.platformInfo?.versionId].filter(Boolean));
 for(const r of m.onlineResearch||[])if(r.identity?.exact){for(const [site,id] of Object.entries(r.identity.projectIds||{}))if(!ids[site])ids[site]=id;if(r.identity.versionId)versions.add(r.identity.versionId);}
 if(m.manifest?.projectID)ids.CurseForge=String(m.manifest.projectID);
 for(const url of m.manifest?.downloads||[]){try{const u=new URL(url),hit=/^\/data\/([A-Za-z0-9]{8})\/versions\/([A-Za-z0-9]{8})\//.exec(u.pathname);if(u.hostname==='cdn.modrinth.com'&&hit){ids.Modrinth=hit[1];versions.add(hit[2]);}}catch{}}
 const names=new Set([m.name,m.originalName,m.file,...(m.components||[]).flatMap(c=>[c.id,c.name,...(c.aliases||[])])].map(relationName).filter(Boolean));
 if(['create','机械动力','机械动力create','create机械动力'].some(n=>names.has(n))){for(const n of ['create','机械动力','机械动力create','create机械动力'])names.add(n);}
 return {ids,versions,names};
}
function resolveRelation(mods,r,ownerKey,identities){
 const platform=relationPlatform(r),target=relationName(r.target),placeholder=/^(Modrinth|CurseForge) 项目 /.test(r.target||'');
 const scored=mods.filter(m=>m.key!==ownerKey).map(m=>{
  const id=identities?.get(m.key)||modIdentity(m);let score=0,basis='';
  if(r.projectId&&platform&&String(id.ids[platform]||'')===String(r.projectId)){score=100;basis='平台项目 ID';}
  else if(r.projectId&&platform&&id.ids[platform])return null;
  if(!score&&r.versionId&&id.versions.has(r.versionId)){score=90;basis='平台版本 ID';}
  if(!score&&!placeholder&&target&&id.names.has(target)){score=50;basis='名称 / 组件 ID';}
  return score?{mod:m,score,basis}:null;
 }).filter(Boolean).sort((a,b)=>b.score-a.score);
 return scored.length&&(!scored[1]||scored[0].score>scored[1].score)?scored[0]:null;
}
function onlineRelations(owner,mods,identities=new Map(mods.map(m=>[m.key,modIdentity(m)]))){
 const unique=new Map(),rows=[...(owner.onlineResearch||[]).flatMap(r=>(r.platformDependencies||[]).map(d=>({...d,origin:'platform'}))),...(owner.aiAnnotation?.relations||[]).map(d=>({...d,origin:'ai'}))];
 for(const r of rows){
  if(!r.target&&!r.projectId&&!r.versionId)continue;
  const hit=resolveRelation(mods,r,owner.key,identities),kind=r.kind||'related',key=(hit?'mod:'+hit.mod.key:r.projectId?relationPlatform(r)+':'+r.projectId:r.versionId?'version:'+r.versionId:'name:'+relationName(r.target))+'|'+kind;
  const old=unique.get(key),row={...r,kind,target:hit?.mod.name||r.target||String(r.projectId||r.versionId),resolvedKey:hit?.mod.key,matchBasis:hit?.basis};
  if(!old||!old.projectId&&row.projectId)unique.set(key,row);
 }
 return [...unique.values()];
}
function buildWebRelations(mods,local=[],context=typeof damnRelationshipContext==='function'?damnRelationshipContext:null){
 const identities=new Map(mods.map(m=>[m.key,modIdentity(m)]));
 const edges=[],seen=new Set(),add=(owner,r,key)=>{
  const from=r.kind==='used_by'?key:owner.key,to=r.kind==='used_by'?owner.key:key,id=from+'|'+to+'|'+r.kind;
  if(from===to||seen.has(id)||r.kind==='required'&&local.some(e=>e.from===from&&e.to===to))return;
  seen.add(id);edges.push({owner:owner.key,from,to,id:r.target,kind:r.kind,source:r.source,provenance:r.provenance||'网页资料',origin:r.origin,matchBasis:r.matchBasis,inferred:r.kind==='ecosystem'});
 };
 for(const m of mods){
  const rows=onlineRelations(m,mods,identities);
  m.classificationRelations=rows.map(r=>({target:r.target,kind:r.kind,basis:r.provenance?'平台 / AI 资料':'已有资料'}));
  for(const r of rows)if(r.resolvedKey)add(m,r,r.resolvedKey);
  for(const d of m.dependencies||[]){
   if(d.type!=='required')continue;const hit=resolveRelation(mods,{target:d.target},m.key,identities);
   if(hit)add(m,{target:d.target,kind:'required',source:d.source,matchBasis:hit.basis,provenance:'文件声明与包内身份匹配，未验证文件版本'},hit.mod.key);
  }
 }
 const roots=mods.filter(m=>{const names=identities.get(m.key).names;return names.has('create')||names.has('机械动力');});
 if(roots.length===1&&context){
  const root=roots[0];for(const m of mods){
   const ecosystem=context(m).ecosystem;
   if(!ecosystem||ecosystem.root||m.key===root.key||edges.some(e=>e.from===m.key&&e.to===root.key)||local.some(e=>e.from===m.key&&e.to===root.key))continue;
   add(m,{target:root.name,kind:'ecosystem',provenance:ecosystem.basis+'；生态线索，不代表必需依赖'},root.key);
  }
 }
 return edges;
}
function networkEdges(mods,local,web=[]){
 const keys=new Set(mods.map(m=>m.key)),out=new Map();
 for(const e of [...local.map(e=>({...e,kind:e.kind||'required',web:false})),...web.map(e=>({...e,web:true}))]){
  if(e.from===e.to||!keys.has(e.from)||!keys.has(e.to))continue;
  const id=e.from+'|'+e.to+'|'+e.kind;if(!out.has(id))out.set(id,e);
 }
 return [...out.values()];
}
function filterNetworkRelations(edges,kind='all'){
 const kinds=new Set(['required','optional','incompatible','ecosystem','related','embedded','include','tool','used_by','discouraged']);
 return kinds.has(kind)?edges.filter(e=>e.kind===kind):edges.slice();
}
function buildDependencyTree(mods,edges,key){
 const by=new Map(mods.map(m=>[m.key,m])),rootMod=by.get(key),maxNodes=200,maxDepth=12;
 if(!rootMod)return {root:null,count:0,truncated:false};
 const outgoing=new Map(),seenEdges=new Map();
 for(const edge of edges){
  if(edge.kind!=='required'||!by.has(edge.from)||!by.has(edge.to))continue;
  if(!outgoing.has(edge.from)){outgoing.set(edge.from,[]);seenEdges.set(edge.from,new Set());}
  // networkEdges already prefers file evidence; keep its first edge and metadata.
  if(seenEdges.get(edge.from).has(edge.to))continue;
  seenEdges.get(edge.from).add(edge.to);outgoing.get(edge.from).push(edge);
 }
 let count=0,truncated=false;const expanded=new Set(),ancestors=new Set();
 function visit(nodeKey,edge,depth){
  const mod=by.get(nodeKey),node={key:nodeKey,name:mod.name??nodeKey,children:[]};
  if(edge)node.edge={...edge};count++;
  if(ancestors.has(nodeKey)){node.cycle=true;return node;}
  if(expanded.has(nodeKey)){node.shared=true;return node;}
  expanded.add(nodeKey);const children=outgoing.get(nodeKey)||[];
  if(depth>=maxDepth&&children.length){node.truncated='depth';truncated=true;return node;}
  ancestors.add(nodeKey);
  for(const relation of children){
   if(count>=maxNodes){node.truncated='nodes';truncated=true;break;}
   node.children.push(visit(relation.to,relation,depth+1));
  }
  ancestors.delete(nodeKey);return node;
 }
 const root=visit(key,null,0);return {root,count,truncated};
}
function networkRelationGroups(mods,edges,key){
 const by=new Map(mods.map(m=>[m.key,m])),groups={prerequisites:[],dependents:[],ecosystem:[],other:[]},seen=new Set();
 for(const e of edges){
  if(e.from===e.to||e.from!==key&&e.to!==key)continue;
  const outgoing=e.from===key,other=by.get(outgoing?e.to:e.from);if(!other)continue;
  const group=e.kind==='ecosystem'?'ecosystem':['required','optional','used_by'].includes(e.kind)?outgoing?'prerequisites':'dependents':'other';
  const id=group+'|'+other.key+'|'+e.kind;if(seen.has(id))continue;seen.add(id);
  const label=({required:'必需前置',optional:'可选前置',used_by:'依赖关系 · 待核对',ecosystem:'生态线索 · 待核对',incompatible:'不兼容',related:'网页关联 · 待确认',embedded:'内置组件',include:'包含组件',tool:'相关工具'})[e.kind]||'其他关联';
  groups[group].push({key:other.key,name:other.name||other.key,kind:e.kind,label,basis:e.kind==='ecosystem'?'名称 / 简介线索':e.web?e.origin==='platform'?'平台版本声明':e.origin==='ai'?'AI 补充 · 待核对':'网页资料 · 待核对':'文件声明',web:!!e.web,source:e.source||'',direction:outgoing?'outgoing':'incoming'});
 }
 for(const rows of Object.values(groups))rows.sort((a,b)=>(a.kind==='required'?0:1)-(b.kind==='required'?0:1)||a.name.localeCompare(b.name,'zh-CN'));
 return groups;
}
function separateNetworkCards(points,adj){
 const {width,height,gapX,gapY}=NETWORK_CARD,stepX=width+gapX,stepY=height+gapY;
 let crowded=false;
 for(let i=0;i<points.length&&!crowded;i++)for(let j=i+1;j<points.length;j++)if(Math.abs(points[i].x-points[j].x)<width+gapX&&Math.abs(points[i].y-points[j].y)<height+gapY){crowded=true;break;}
 if(!crowded)return;
 // Forces alone cannot guarantee card clearance around a busy hub.
 // Reserve distinct slots after settling; core nodes keep their position first.
 const occupied=new Set();
 for(const p of [...points].sort((a,b)=>adj.get(b.key).size-adj.get(a.key).size||a.key.localeCompare(b.key))){
  const x=Math.round(p.x/stepX),y=Math.round(p.y/stepY);let chosen=null;
  for(let radius=0;!chosen;radius++){
   let best=Infinity;
   for(let dx=-radius;dx<=radius;dx++)for(let dy=-radius;dy<=radius;dy++){
    if(Math.max(Math.abs(dx),Math.abs(dy))!==radius||occupied.has((x+dx)+','+(y+dy)))continue;
    const distance=(x+dx-p.x/stepX)**2+(y+dy-p.y/stepY)**2;
    if(distance<best){best=distance;chosen={x:x+dx,y:y+dy};}
   }
  }
  occupied.add(chosen.x+','+chosen.y);p.x=chosen.x*stepX;p.y=chosen.y*stepY;
 }
}
function buildNetworkLayout(mods,edges){
 const adj=new Map(mods.map(m=>[m.key,new Set()]));
 edges.forEach(e=>{adj.get(e.from)?.add(e.to);adj.get(e.to)?.add(e.from);});
 const seen=new Set(),groups=[];
 for(const m of [...mods].sort((a,b)=>(adj.get(b.key)?.size||0)-(adj.get(a.key)?.size||0)||a.key.localeCompare(b.key))){
  if(seen.has(m.key))continue;const keys=[m.key];seen.add(m.key);
  for(let i=0;i<keys.length;i++)for(const k of adj.get(keys[i])||[])if(!seen.has(k)){keys.push(k);seen.add(k);}
  groups.push(keys);
 }
 const boxes=groups.map(keys=>{
  const points=keys.map((key,i)=>({key,x:i===0?0:Math.cos(i*2.399963)*Math.sqrt(i)*130,y:i===0?0:Math.sin(i*2.399963)*Math.sqrt(i)*85}));
  const by=new Map(points.map(p=>[p.key,p])),links=edges.filter(e=>by.has(e.from)&&by.has(e.to));
  if(points.length<=600)for(let step=0;step<70;step++){
   const push=points.map(()=>({x:0,y:0}));
   for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){
    const dx=points[i].x-points[j].x,dy=points[i].y-points[j].y,d2=Math.max(200,dx*dx+dy*dy),d=Math.sqrt(d2),f=Math.min(12,11000/d2);
    push[i].x+=dx/d*f;push[i].y+=dy/d*f;push[j].x-=dx/d*f;push[j].y-=dy/d*f;
    // Wide labels need horizontal separation in addition to point repulsion.
    if(Math.abs(dx)<150&&Math.abs(dy)<47){const shift=(150-Math.abs(dx))*.18*(dx>=0?1:-1);push[i].x+=shift;push[j].x-=shift;}
   }
   const indexes=new Map(points.map((p,i)=>[p.key,i]));
   for(const e of links){const a=by.get(e.from),b=by.get(e.to),dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1,f=(d-180)*.025;push[indexes.get(a.key)].x+=dx/d*f;push[indexes.get(a.key)].y+=dy/d*f;push[indexes.get(b.key)].x-=dx/d*f;push[indexes.get(b.key)].y-=dy/d*f;}
   points.forEach((p,i)=>{p.x+=Math.max(-18,Math.min(18,push[i].x));p.y+=Math.max(-18,Math.min(18,push[i].y));});
  }
  separateNetworkCards(points,adj);
  const minX=Math.min(...points.map(p=>p.x))-85,minY=Math.min(...points.map(p=>p.y))-35,maxX=Math.max(...points.map(p=>p.x))+85,maxY=Math.max(...points.map(p=>p.y))+35;
  points.forEach(p=>{p.x-=minX;p.y-=minY;});return {points,width:maxX-minX,height:maxY-minY};
 });
 const target=Math.max(1000,Math.sqrt(mods.length)*145, ...boxes.map(b=>b.width));
 let x=30,y=30,row=0,width=0;const nodes=[];
 for(const box of boxes){if(x+box.width>target&&x>30){x=30;y+=row+35;row=0;}for(const p of box.points)nodes.push({...p,x:p.x+x,y:p.y+y,degree:adj.get(p.key).size});x+=box.width+25;row=Math.max(row,box.height);width=Math.max(width,x);}
 return {nodes,width:Math.max(width+30,600),height:Math.max(y+row+30,360)};
}
if(typeof module!=='undefined')module.exports={filterNetworkNodes,NETWORK_CARD,relationName,modIdentity,resolveRelation,onlineRelations,buildWebRelations,networkEdges,filterNetworkRelations,buildDependencyTree,networkRelationGroups,buildNetworkLayout};
