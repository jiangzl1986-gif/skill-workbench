import {connectionError} from './connections';
import type {Unit} from './library';
export type SourceIdentity={id:string,name:string,version:string,snapshot:string};
export type Blueprint={key:string,source_id:string,name:string,version:string,snapshot:string,warnings:string[],instances:{key:string,node_id:string,x:number,y:number,note:string,role:string}[],links:{source:string,target:string,label:string,evidence:{path:string,sha256:string,start_line:number,end_line:number,text:string}}[]};

// Materialize a new design only. The original source, rules, schema and server guards stay authoritative.
export function materializeBlueprint(bp:Blueprint,sources:SourceIdentity[],units:Unit[],newId=()=>crypto.randomUUID()):{
  id:null,revision:number,name:string,goal:string,instances:{id:string,node_id:string,x:number,y:number,excluded:string[],note:string}[],links:{source:string,target:string,label:string}[]
}{
  const source=sources.find(s=>s.id===bp.source_id);
  if(!source||source.snapshot!==bp.snapshot||source.version!==bp.version)throw new Error('整套来源流程与当前模块库的版本或哈希不一致；草稿未改变，请先核对来源。');
  const facts=new Map(units.map(n=>[n.id,n])),themeIds=new Set(units.filter(n=>n.kind==='theme'&&n.source_skill_id===source.id).map(n=>n.id));
  const selected=new Set(bp.instances.map(p=>p.node_id));
  if(selected.size!==themeIds.size||[...themeIds].some(id=>!selected.has(id)))throw new Error('整套来源范围不完整，不能载入。');
  if(bp.instances.length>60||bp.links.length>120)throw new Error('整套流程超过本批60模块或120连接上限，请先制定保真分批方案。');
  const ids=new Map<string,string>();
  const instances=bp.instances.map(p=>{
    const fact=facts.get(p.node_id);
    if(ids.has(p.key)||!fact||fact.kind!=='theme'||fact.source_skill_id!==source.id||fact.source_snapshot!==bp.snapshot||p.note.length>2000||!Number.isFinite(p.x)||!Number.isFinite(p.y)||Math.abs(p.x)>20000||Math.abs(p.y)>20000)throw new Error('整套流程模块身份、范围或备注异常，草稿未改变。');
    const id=newId();if([...ids.values()].includes(id))throw new Error('整套流程实例身份重复，草稿未改变。');ids.set(p.key,id);
    return {id,node_id:p.node_id,x:p.x,y:p.y,excluded:[],note:p.note};
  });
  const links:{source:string,target:string,label:string}[]=[];
  for(const e of bp.links){
    const from=ids.get(e.source),to=ids.get(e.target),problem=connectionError({instances,links},from||null,to||null);
    if(problem||!e.label||e.label.length>100)throw new Error(problem||'来源连接条件异常，草稿未改变。');
    links.push({source:from!,target:to!,label:e.label});
  }
  return {id:null,revision:0,name:source.name+' '+source.version+' 修改草稿',goal:'基于 '+source.name+' '+source.version+' 设计独立修改方案。\n'+bp.warnings.join('\n')+'\n不执行、不修改来源；删除卡片不自动豁免正式规则。',instances,links};
}
