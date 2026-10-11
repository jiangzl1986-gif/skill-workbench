import type {Unit} from './library';

export type HierarchyRow={unit:Unit,excluded:boolean,inheritedExclusion:boolean,blocked:string};

// A containment view is separate from draft flow links and never changes source scopes.
export function hierarchyRows(parent:Unit,index:Map<string,Unit[]>,path:string[],excluded:readonly string[]):HierarchyRow[]{
  const inheritedExclusion=path.some(id=>excluded.includes(id));
  return (index.get(parent.id)||[]).map(unit=>({unit,inheritedExclusion,
    excluded:inheritedExclusion||excluded.includes(unit.id),
    blocked:unit.source_skill_id!==parent.source_skill_id?'来源不一致，请核对':path.includes(unit.id)?'来源层级形成循环，请核对':''}));
}

export function hierarchyWindow<T>(rows:readonly T[],shown:number,size=6){
  const count=Math.min(rows.length,Math.max(size,shown));
  return {rows:rows.slice(0,count),remaining:rows.length-count,total:rows.length};
}
