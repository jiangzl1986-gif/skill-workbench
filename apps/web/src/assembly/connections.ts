export type FlowLink={source:string,target:string,label:string};
export type LinkScope={instances:{id:string}[],links:FlowLink[]};

// Immediate interaction feedback only; the original server check/save/export guards remain authoritative.
export function connectionError(draft:LinkScope,source:string|null,target:string|null):string|null{
  const ids=new Set(draft.instances.map(n=>n.id));
  if(!source||!target||!ids.has(source)||!ids.has(target)||source===target)return '连线必须连接两个不同的现有模块。';
  if(draft.links.some(e=>e.source===source&&e.target===target))return '这两个模块已经连接。';
  if(draft.links.length>=120)return '本批最多120条连线，请保真分批。';
  const children=new Map<string,string[]>();
  for(const e of draft.links){if(!children.has(e.source))children.set(e.source,[]);children.get(e.source)!.push(e.target);}
  const todo=[target],seen=new Set<string>();
  while(todo.length){const id=todo.pop()!;if(id===source)return '该连接会形成循环，请先调整交接顺序。';if(seen.has(id))continue;seen.add(id);todo.push(...(children.get(id)||[]));}
  return null;
}

export function cutConnection<T extends LinkScope>(draft:T,source:string,target:string):T{
  return {...draft,links:draft.links.filter(e=>e.source!==source||e.target!==target)};
}
