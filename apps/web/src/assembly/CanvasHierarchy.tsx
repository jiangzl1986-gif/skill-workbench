import {useMemo,useState} from 'react';
import {ChevronDown,ChevronRight,BookOpen,Plus} from 'lucide-react';
import type {Unit} from './library';
import {hierarchyRows,hierarchyWindow} from './hierarchy';

type Props={unit:Unit,index:Map<string,Unit[]>,path:string[],titles:string[],excluded:string[],busy:boolean,
  onSource:(unit:Unit)=>void,onInclude:(id:string,include:boolean)=>void};
const names:Record<string,string>={theme:'子模块候选',file:'文件模块候选',section:'规则块候选'};

export default function CanvasHierarchy(props:Props){
  const [shown,setShown]=useState(6);
  const rows=useMemo(()=>hierarchyRows(props.unit,props.index,props.path,props.excluded),[props.unit,props.index,props.path,props.excluded]);
  const window=hierarchyWindow(rows,shown);
  return <div className="canvas-hierarchy-list" role="list" aria-label={props.unit.title+'的子模块'}>
    {window.rows.map(row=><HierarchyItem key={row.unit.id} {...props} row={row}/>)}
    {window.remaining>0&&<button className="hierarchy-more nodrag" onClick={e=>{e.stopPropagation();setShown(n=>n+6);}} aria-label={'继续显示 '+props.unit.title+' 的子模块'}>继续显示 · 还有 {window.remaining} 项</button>}
    {rows.length===0&&<p className="hierarchy-empty">没有更深的已登记子项，可查看完整来源。</p>}
  </div>;
}

function HierarchyItem(props:Props&{row:ReturnType<typeof hierarchyRows>[number]}){
  const {unit,excluded,inheritedExclusion,blocked}=props.row;
  const [open,setOpen]=useState(false);
  const children=props.index.get(unit.id)||[];
  const path=[...props.path,unit.id],titles=[...props.titles,unit.title];
  return <div role="listitem" className={'hierarchy-item'+(excluded?' scope-excluded':'')} data-source-node={unit.id}>
    <div className="hierarchy-row">
      <button className="hierarchy-toggle nodrag" disabled={!!blocked||children.length===0} aria-expanded={open} aria-label={(open?'收起':'展开')+'子模块 '+unit.title} onClick={e=>{e.stopPropagation();setOpen(v=>!v);}}>{open?<ChevronDown size={14}/>:<ChevronRight size={14}/>}</button>
      <div className="hierarchy-title"><b title={unit.title}>{unit.title}</b><span>{names[unit.kind]||'来源范围'}{children.length?' · '+children.length+' 个子项':''}</span></div>
      <label className="hierarchy-include nodrag" title={inheritedExclusion?'父级已排除，先恢复父级范围':'只调整本草稿范围；正式标准仍须核验'}><input type="checkbox" aria-label={'保留子模块 '+unit.title} checked={!excluded} disabled={props.busy||inheritedExclusion||!!blocked} onChange={e=>props.onInclude(unit.id,e.target.checked)}/>保留</label>
    </div>
    <div className="hierarchy-origin" title={titles.join(' → ')}>父级：{props.unit.title} · {unit.source_name} · {unit.source_version}</div>
    {unit.path&&<div className="hierarchy-path" title={unit.path}>{unit.path}</div>}
    {blocked?<p className="hierarchy-warning">{blocked}</p>:<div className="hierarchy-actions">
      {unit.path&&<button className="nodrag" aria-label={'查看子模块原文 '+unit.title} onClick={e=>{e.stopPropagation();props.onSource(unit);}}><BookOpen size={12}/>原文</button>}
      {excluded&&<span className="hierarchy-warning">{inheritedExclusion?'随父级排除':'本草稿已排除'}</span>}
    </div>}
    {open&&!blocked&&<CanvasHierarchy {...props} unit={unit} path={path} titles={titles}/>}
  </div>;
}
