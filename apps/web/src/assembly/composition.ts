import type {Unit} from './library';
import {connectionError} from './connections';
export type Part={id:string,node_id:string,x:number,y:number,excluded:string[],note:string};
export type Flow={source:string,target:string,label:string};
export type Slot={id:string,origin_id:string|null,node_id:string|null,x:number,y:number,note:string};
export type Location={owner_id:string,path:string[]};
export type Scope=Location&{slots:Slot[],links:Flow[]};
export type Draft={id:string|null,revision:number,name:string,goal:string,instances:Part[],links:Flow[],composition?:{schema_version:1,scopes:Scope[]}|null};
export const sameLocation=(a:Location,b:Location)=>a.owner_id===b.owner_id&&a.path.length===b.path.length&&a.path.every((p,i)=>p===b.path[i]);
export const scopeOf=(d:Draft,l:Location)=>d.composition?.scopes.find(s=>sameLocation(s,l));
export const originalId=(nid:string)=>'o-'+nid;
export function slotsAt(d:Draft,l:Location,nid:string,index:Map<string,Unit[]>):Slot[]{
  const edits=new Map(scopeOf(d,l)?.slots.map(s=>[s.id,s])||[]);
  const originals=(index.get(nid)||[]).map((u,i)=>edits.get(originalId(u.id))||{id:originalId(u.id),origin_id:u.id,node_id:u.id,x:(i%2)*340,y:Math.floor((i%6)/2)*230,note:''});
  return [...originals,...[...edits.values()].filter(s=>s.origin_id===null)];
}
export function resolveLocation(d:Draft,l:Location,index:Map<string,Unit[]>):string{
  const root=d.instances.find(p=>p.id===l.owner_id);
  if(!root)throw new Error('父模块已不存在，请返回外层。');
  let nid:string=root.node_id;
  const prefix:string[]=[],seen=new Set([nid]);
  for(const sid of l.path){
    const slot:Slot|undefined=slotsAt(d,{owner_id:l.owner_id,path:[...prefix]},nid,index).find(s=>s.id===sid);
    if(!slot?.node_id)throw new Error('内部父项已移除或路径失效。');
    nid=slot.node_id;if(seen.has(nid))throw new Error('内部归属不能形成循环。');seen.add(nid);prefix.push(sid);
  }
  return nid;
}
export function setScope(d:Draft,l:Location,slots:Slot[],links:Flow[]):Draft{
  const scopes=(d.composition?.scopes||[]).filter(s=>!sameLocation(s,l));
  if(slots.length||links.length)scopes.push({...l,path:[...l.path],slots,links});
  const next={...d};if(scopes.length)next.composition={schema_version:1,scopes};else delete next.composition;
  return next;
}
export function putSlot(d:Draft,l:Location,slot:Slot):Draft{
  const s=scopeOf(d,l),old=s?.slots||[];return setScope(d,l,old.some(x=>x.id===slot.id)?old.map(x=>x.id===slot.id?slot:x):[...old,slot],s?.links||[]);
}
export function hasDescendants(d:Draft,l:Location,sid:string){
  const path=[...l.path,sid];return (d.composition?.scopes||[]).some(s=>s.owner_id===l.owner_id&&s.path.length>=path.length&&path.every((p,i)=>s.path[i]===p));
}
export function removeSlot(d:Draft,l:Location,slot:Slot):Draft{
  if(hasDescendants(d,l,slot.id))throw new Error('此项下已有内部编辑，请先进入下层恢复或清除那些编辑，再移除此项。');
  const s=scopeOf(d,l),other=(s?.slots||[]).filter(x=>x.id!==slot.id);
  if(slot.origin_id)other.push({...slot,node_id:null});
  return setScope(d,l,other,(s?.links||[]).filter(e=>e.source!==slot.id&&e.target!==slot.id));
}
export function restoreSlot(d:Draft,l:Location,slot:Slot):Draft{
  if(!slot.origin_id)throw new Error('新增项没有原项，使用移除。');
  if(hasDescendants(d,l,slot.id)&&slot.node_id!==slot.origin_id)throw new Error('替代项下已有内部编辑，请先处理下层编辑，再恢复原项。');
  return putSlot(d,l,{...slot,node_id:slot.origin_id,note:''});
}
export function designCounts(d:Draft){
  const positions=new Set<string>();let links=d.links.length;
  for(const s of d.composition?.scopes||[]){
    const id=(path:string[],sid:string)=>JSON.stringify([s.owner_id,path,sid]);
    for(const a of s.slots)positions.add(id(s.path,a.id));
    for(const e of s.links){positions.add(id(s.path,e.source));positions.add(id(s.path,e.target));}
    for(let i=0;i<s.path.length;i++)positions.add(id(s.path.slice(0,i),s.path[i]));
    links+=s.links.length;
  }
  return {instances:d.instances.length+positions.size,links,internal:positions.size};
}
export function designError(d:Draft,index:Map<string,Unit[]>):string|null{
  const n=designCounts(d);if(n.instances>60)return '外层与内部设计位置合计超过60项；本次未改动，请保真分批。';
  if(n.links>120)return '外层与内部设计连线合计超过120条；本次未改动，请保真分批。';
  try{
    const scopes=d.composition?.scopes||[];if(scopes.length>60)return '内部画布超过本批上限。';
    const scopeKeys=new Set<string>();
    for(const s of scopes){
      const sk=JSON.stringify([s.owner_id,s.path]);if(scopeKeys.has(sk))return '重复内部画布。';scopeKeys.add(sk);
      const nid=resolveLocation(d,s,index),originals=new Set((index.get(nid)||[]).map(u=>u.id)),seen=new Set<string>();
      const root=d.instances.find(p=>p.id===s.owner_id)!;const blocked=new Set<string>(),todo=[...root.excluded];
      while(todo.length){const id=todo.pop()!;if(blocked.has(id))continue;blocked.add(id);todo.push(...(index.get(id)||[]).map(u=>u.id));}
      for(let i=0;i<s.path.length;i++)if(blocked.has(resolveLocation(d,{owner_id:s.owner_id,path:s.path.slice(0,i+1)},index)))return '内部路径位于已排除范围。';
      for(const slot of s.slots){
        if(seen.has(slot.id))return '重复内部位置。';seen.add(slot.id);
        if(slot.origin_id!==null&&(!originals.has(slot.origin_id)||slot.id!==originalId(slot.origin_id)))return '替换或移除位置不属于本层来源。';
        if(slot.origin_id===null&&(!slot.id.startsWith('a-')||!slot.node_id))return '新增位置身份不完整。';
        if(slot.note.length>2000||Math.abs(slot.x)>20000||Math.abs(slot.y)>20000||!Number.isFinite(slot.x)||!Number.isFinite(slot.y))return '内部备注或位置超过原限制。';
        if(slot.node_id){if(blocked.has(slot.node_id)||blocked.has(slot.origin_id||''))return '先恢复已排除范围再编辑此项。';resolveLocation(d,{owner_id:s.owner_id,path:[...s.path,slot.id]},index);}
      }
      const active=slotsAt(d,s,nid,index).filter(a=>a.node_id&&!blocked.has(a.node_id)&&!blocked.has(a.origin_id||''));const checked:Flow[]=[];
      for(const e of s.links){const problem=connectionError({instances:active,links:checked},e.source,e.target);if(problem)return problem;if(e.label.length>100)return '交接条件超过原100字上限。';checked.push(e);}
    }
  }catch(e:any){return e.message;}
  return null;
}
export function innerConnectionError(d:Draft,l:Location,nid:string,index:Map<string,Unit[]>,source:string|null,target:string|null){
  const s=scopeOf(d,l),problem=connectionError({instances:slotsAt(d,l,nid,index).filter(a=>a.node_id!==null),links:s?.links||[]},source,target);
  if(problem)return problem;return designCounts(d).links>=120?'外层与内部连线合计最多120条。':null;
}
export function cutInner(d:Draft,l:Location,source:string,target:string){
  const s=scopeOf(d,l);return setScope(d,l,s?.slots||[],(s?.links||[]).filter(e=>e.source!==source||e.target!==target));
}
