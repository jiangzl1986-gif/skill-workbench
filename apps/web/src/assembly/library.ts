export type Unit={id:string,title:string,kind:string,parent_id:string|null,path:string|null,count:number,source_skill_id:string,source_name:string,source_version:string,source_snapshot:string,source_content:{file_id:string,path:string,title:string,sha256:string,ranges:{start_line:number,end_line:number}[]}[],source_groups:string[],reuse_status:string};

// Resolve each edge once when the library changes, preserving the original display order.
export function indexChildren(units:Unit[],contains:{source:string,target:string}[]):Map<string,Unit[]>{
  const facts=new Map(units.map((n,i)=>[n.id,{node:n,order:i}]));
  const grouped=new Map<string,Map<string,Unit>>();
  for(const e of contains){const target=facts.get(e.target);if(!target)continue;if(!grouped.has(e.source))grouped.set(e.source,new Map());grouped.get(e.source)!.set(e.target,target.node);}
  return new Map([...grouped].map(([id,nodes])=>[id,[...nodes.values()].sort((a,b)=>facts.get(a.id)!.order-facts.get(b.id)!.order)]));
}

// Filtering operates on the entire pool before pagination; a source selector is optional.
export function selectModules(units:Unit[],query:string,sourceId='all',kind='all',scopeIds?:Set<string>):Unit[]{
  const needle=query.trim().toLocaleLowerCase('zh-CN');
  const rank:Record<string,number>={theme:0,file:1,section:2};
  return units.filter(n=>n.kind in rank&&
    (sourceId==='all'||n.source_skill_id===sourceId)&&
    (kind==='all'||n.kind===kind)&&(!scopeIds||scopeIds.has(n.id))&&
    (!needle||[n.title,n.path,n.source_name,n.source_version,...n.source_groups,...n.source_content.flatMap(c=>[c.title,c.path])].join(' ').toLocaleLowerCase('zh-CN').includes(needle)))
    .sort((a,b)=>rank[a.kind]-rank[b.kind]||a.title.localeCompare(b.title,'zh-CN')||a.source_name.localeCompare(b.source_name,'zh-CN')||a.id.localeCompare(b.id));
}

export function modulePage(modules:Unit[],page:number,size=20){
  const pages=Math.max(1,Math.ceil(modules.length/size));
  const current=Math.max(0,Math.min(page,pages-1));
  return {items:modules.slice(current*size,(current+1)*size),pages,current,total:modules.length};
}
