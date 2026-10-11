import React,{useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {ReactFlow,ReactFlowProvider,Background,Controls,MiniMap,Handle,Position,MarkerType,BaseEdge,EdgeLabelRenderer,getSmoothStepPath,applyNodeChanges,useReactFlow,useNodesInitialized,useViewport} from '@xyflow/react';
import type {Node,NodeProps,NodeChange,Connection,EdgeProps,EdgeChange} from '@xyflow/react';
import {ChevronRight,ChevronLeft,Scissors,Plus,BookOpen,Trash2,Undo2,RefreshCw} from 'lucide-react';
import type {Unit} from './library';
import type {Draft,Location,Slot} from './composition';
import {slotsAt,scopeOf,resolveLocation,putSlot,removeSlot,restoreSlot,designError,cutInner,innerConnectionError,hasDescendants,designCounts} from './composition';
import {api} from './api';

type Props={draft:Draft,location:Location,units:Map<string,Unit>,index:Map<string,Unit[]>,busy:boolean,
  replacement:string,onReplace:(sid:string)=>void,onChange:(d:Draft)=>void,onNavigate:(l:Location|null)=>void,
  onSource:(u:Unit)=>void,onError:(s:string)=>void,onPending:(n:number)=>void};
function SlotCard({id,data}:NodeProps){
  const slot=data.slot as Slot,unit=data.unit as Unit,original=data.original as Unit|undefined;
  const removed=slot.node_id===null,excluded=!!data.excluded;
  return <div className={'part-card inner-card '+(removed||excluded?' removed':'')+(data.chosen?' chosen':'')}>
    {!removed&&!excluded&&<Handle id="in" type="target" position={Position.Left} aria-label={'内部接入端口 '+id} title="小模块接入"/>}
    <div className="part-meta">{removed?'已移除':slot.origin_id===null?'新加入':slot.node_id!==slot.origin_id?'已替换':'原有子模块'}<span>{unit.source_version}</span></div>
    <strong>{unit.title}</strong><div className="module-origin">来源：{unit.source_name}</div>
    {unit.path&&<small className="inner-source-path" title={unit.path}>{unit.path}</small>}
    {original&&slot.node_id!==slot.origin_id&&<p className="inner-original">原项：{original.title} · {original.source_name}</p>}
    {excluded&&<p>原草稿已排除；请在上层恢复范围。</p>}
    <div className="inner-actions nodrag nopan">
      {!removed&&!excluded&&<><button disabled={!!data.busy} aria-label={'进入子模块内部 '+unit.title} onClick={e=>{e.stopPropagation();(data.enter as ()=>void)();}}>进入内部<ChevronRight size={12}/></button><button disabled={!!data.busy} aria-label={'替换小模块 '+unit.title} onClick={e=>{e.stopPropagation();(data.replace as ()=>void)();}}><RefreshCw size={12}/>替换</button><button disabled={!!data.busy} aria-label={'移除小模块 '+unit.title} onClick={e=>{e.stopPropagation();(data.remove as ()=>void)();}}><Trash2 size={12}/>移除</button></>}
      {slot.origin_id&&slot.node_id!==slot.origin_id&&<button disabled={!!data.busy} aria-label={'恢复原小模块 '+original?.title} onClick={e=>{e.stopPropagation();(data.restore as ()=>void)();}}><Undo2 size={12}/>恢复原项</button>}
      {unit.path&&<button aria-label={'查看内部模块原文 '+unit.title} onClick={e=>{e.stopPropagation();(data.source as ()=>void)();}}><BookOpen size={12}/>原文</button>}
    </div>
    {!removed&&!excluded&&<Handle id="out" type="source" position={Position.Right} aria-label={'内部输出端口 '+id} title="小模块输出"/>}
  </div>;
}
const nodeTypes={inner:SlotCard};
function InnerEdge(props:EdgeProps){
  const {zoom}=useViewport();const [path,x,y]=getSmoothStepPath(props);
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} interactionWidth={28}/><EdgeLabelRenderer><button className="edge-cut nodrag nopan" style={{transform:`translate(-50%, -50%) translate(${x}px,${y}px) scale(${1/zoom})`}} aria-label={'剪断内部连接 '+props.source+' 到 '+props.target} title={String(props.label)} onClick={e=>{e.stopPropagation();(props.data?.cut as ()=>void)();}}><Scissors size={14}/></button></EdgeLabelRenderer></>;
}
const edgeTypes={inner:InnerEdge};
function Inside(props:Props){
  const {draft,location,units,index}=props;const rf=useReactFlow(),initialized=useNodesInitialized();
  const latest=useRef(draft);latest.current=draft;
  const pending=useRef(new Map<string,symbol>()),active=useRef(true);const [count,setCount]=useState(0),[note,setNote]=useState(''),[chosen,setChosen]=useState('');
  const [page,setPage]=useState(0),[from,setFrom]=useState(''),[to,setTo]=useState('');
  const [pair,setPair]=useState<string[]>([]);
  const current=resolveLocation(draft,location,index),parent=units.get(current)!;
  const slots=useMemo(()=>slotsAt(draft,location,current,index),[draft,location,current,index]);
  const pages=Math.max(1,Math.ceil(slots.length/6)),pageNow=Math.min(page,pages-1),offset=0;
  const visible=useMemo(()=>pair.length?pair.map(id=>slots.find(s=>s.id===id)).filter((s):s is Slot=>!!s):slots.slice(pageNow*6,pageNow*6+6),[slots,pageNow,pair]);
  const previousIds=useRef(new Set(slots.map(s=>s.id)));
  useEffect(()=>{const added=slots.find(s=>s.id.startsWith('a-')&&!previousIds.current.has(s.id));previousIds.current=new Set(slots.map(s=>s.id));if(added){setPair([]);setPage(Math.floor(slots.indexOf(added)/6));setChosen(added.id);}if(pair.some(id=>!slots.some(s=>s.id===id)))setPair([]);},[slots,pair]);
  const scope=scopeOf(draft,location),total=designCounts(draft);
  const root=draft.instances.find(p=>p.id===location.owner_id)!;
  const blocked=useMemo(()=>{const seen=new Set<string>(),todo=[...root.excluded];while(todo.length){const n=todo.pop()!;if(seen.has(n))continue;seen.add(n);todo.push(...(index.get(n)||[]).map(u=>u.id));}return seen;},[root.excluded,index]);
  const change=useCallback((next:Draft)=>{const problem=designError(next,index);if(problem){props.onError(problem);return false;}latest.current=next;props.onChange(next);return true;},[props.onChange,props.onError,index]);
  const action=useCallback((fn:(d:Draft)=>Draft)=>{if(props.busy||pending.current.size){props.onError('连接核对或保存期间请稍后编辑。');return false;}try{return change(fn(latest.current));}catch(e:any){props.onError(e.message);return false;}},[props.busy,props.onError,change]);
  const countPending=useCallback(()=>{setCount(pending.current.size);props.onPending(pending.current.size);},[props.onPending]);
  useEffect(()=>{active.current=true;return()=>{active.current=false;pending.current.clear();props.onPending(0);};},[props.onPending]);
  useEffect(()=>{if(!initialized)return;const frame=requestAnimationFrame(()=>{void rf.fitView({padding:.1,minZoom:.5,maxZoom:1});});return()=>cancelAnimationFrame(frame);},[initialized,rf,pageNow,pair]);
  const [nodes,setNodes]=useState<Node[]>([]);
  useEffect(()=>{setNodes(previous=>visible.map(slot=>{const unit=units.get(slot.node_id||slot.origin_id||'');if(!unit)throw new Error('内部模块来源缺失');return {...previous.find(n=>n.id===slot.id),id:slot.id,type:'inner',position:pair.length?{x:pair.indexOf(slot.id)*340,y:0}:{x:slot.x,y:slot.y-offset},draggable:!props.busy&&!count&&!pair.length,data:{slot,unit,original:slot.origin_id?units.get(slot.origin_id):undefined,chosen:chosen===slot.id,excluded:blocked.has(slot.origin_id||'')||blocked.has(slot.node_id||''),busy:props.busy||count>0,
      enter:()=>props.onNavigate({owner_id:location.owner_id,path:[...location.path,slot.id]}),replace:()=>{setChosen(slot.id);props.onReplace(slot.id);},source:()=>props.onSource(unit),
      remove:()=>action(d=>removeSlot(d,location,slot)),restore:()=>action(d=>restoreSlot(d,location,slot))},selected:chosen===slot.id};}));},[visible,offset,pair,units,chosen,props.busy,count,blocked,location,action,props.onNavigate,props.onReplace,props.onSource]);
  const cut=useCallback((source:string,target:string)=>{pending.current.delete(source+'>'+target);countPending();change(cutInner(latest.current,location,source,target));setNote('已剪断内部连接，两端子模块保留。');},[location,countPending,change]);
  const edges=useMemo(()=>{const ids=new Set(visible.map(s=>s.id));return (scope?.links||[]).filter(e=>ids.has(e.source)&&ids.has(e.target)).map(e=>({id:e.source+'>'+e.target,source:e.source,target:e.target,sourceHandle:'out',targetHandle:'in',type:'inner',label:e.label,markerEnd:{type:MarkerType.ArrowClosed},style:{stroke:'#5a8577',strokeWidth:2},data:{cut:()=>cut(e.source,e.target)}}));},[scope,cut,visible]);
  const connect=(c:Connection)=>{
    if(props.busy){props.onError('保存期间请稍后连接。');return;}
    const problem=innerConnectionError(latest.current,location,current,index,c.source,c.target);if(problem){props.onError(problem);return;}
    const link={source:c.source!,target:c.target!,label:'期望交接'},s=scopeOf(latest.current,location);
    const next={...latest.current,composition:{schema_version:1 as const,scopes:[...(latest.current.composition?.scopes||[]).filter(x=>!(x.owner_id===location.owner_id&&JSON.stringify(x.path)===JSON.stringify(location.path))),{...location,slots:s?.slots||[],links:[...(s?.links||[]),link]}]}};
    if(!change(next))return;const k=link.source+'>'+link.target,t=Symbol(k);pending.current.set(k,t);countPending();setNote('内部连接已显示，正在核对…');
    api('check',next).then(()=>{if(!active.current||pending.current.get(k)!==t)return;pending.current.delete(k);countPending();setNote('内部连接已核对；接入语义仍待审核。');}).catch(e=>{if(!active.current||pending.current.get(k)!==t)return;pending.current.delete(k);countPending();change(cutInner(latest.current,location,link.source,link.target));props.onError(e.message);});
  };
  const changes=(cs:NodeChange[])=>{
    if(pair.length)cs=cs.filter(c=>c.type!=='position');
    setNodes(old=>applyNodeChanges(cs.filter(c=>c.type!=='remove'),old));
    for(const c of cs){if(c.type!=='remove'&&c.type!=='position')continue;const slot=slots.find(s=>s.id===c.id);if(!slot)continue;if(c.type==='remove')action(d=>removeSlot(d,location,slot));else if(!c.dragging&&c.position){if(!action(d=>putSlot(d,location,{...slot,x:c.position!.x,y:c.position!.y+offset})))setNodes(old=>old.map(n=>n.id===slot.id?{...n,position:{x:slot.x,y:slot.y-offset}}:n));}}
  };
  const add=(nid:string,x:number,y:number)=>{const ok=action(d=>{if(props.replacement){const slot=slotsAt(d,location,current,index).find(s=>s.id===props.replacement);if(!slot?.node_id)throw new Error('待替换位置已失效');if(hasDescendants(d,location,slot.id))throw new Error('此项下已有内部编辑，请先处理下层编辑。');return putSlot(d,location,{...slot,node_id:nid});}return putSlot(d,location,{id:'a-'+crypto.randomUUID(),origin_id:null,node_id:nid,x,y,note:''});});if(ok)props.onReplace('');};
  const selected=slots.find(s=>s.id===chosen);
  const nav=(next:Location|null)=>{if(count||props.busy){props.onError('连接核对或保存期间请稍后切换层级。');return;}props.onReplace('');props.onNavigate(next);};
  return <div className="canvas internal-canvas" onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}} onDrop={e=>{e.preventDefault();const nid=e.dataTransfer.getData('application/skill-module');if(!units.has(nid))return;const pos=rf.screenToFlowPosition({x:e.clientX,y:e.clientY});add(nid,pos.x,pos.y);}}>
    <div className="internal-toolbar"><button aria-label="返回外层方案" onClick={()=>nav(null)}><ChevronLeft size={14}/>外层方案</button>{Array.from({length:location.path.length+1},(_,i)=><button key={i} className={i===location.path.length?'active':''} aria-label={'内部层级 '+i} onClick={()=>nav({...location,path:location.path.slice(0,i)})}>{units.get(resolveLocation(draft,{...location,path:location.path.slice(0,i)},index))?.title}<ChevronRight size={12}/></button>)}<b>内部组装 · {parent.title}</b><span>{slots.length} 个来源/设计位置 · {scope?.links.length||0} 条内部连接</span><button disabled={count>0||props.busy} aria-label="恢复此层原始组装" onClick={()=>{if(!window.confirm('恢复此层原始组装会清除本层及下层的加入、替换、移除和内部连接。仅影响当前草稿，是否继续？'))return;action(d=>{const scopes=(d.composition?.scopes||[]).filter(s=>!(s.owner_id===location.owner_id&&s.path.length>=location.path.length&&location.path.every((p,i)=>s.path[i]===p)));const next={...d};if(scopes.length)next.composition={schema_version:1,scopes};else delete next.composition;return next;});props.onReplace('');}}>恢复此层原始组装</button></div>
    <div className="internal-help">从共享模块库“加入到这里”或拖入 · 小模块端口可连接 · 替换只作用于当前位置 · 全方案 {total.instances}/60 设计实例、{total.links}/120 连接</div>
    <div className="inner-navigation"><button disabled={pageNow===0||count>0} aria-label="内部模块上一页" onClick={()=>setPage(pageNow-1)}>上一页</button><span>第 {pageNow+1}/{pages} 页 · 全部 {slots.length} 项</span><button disabled={pageNow===pages-1||count>0} aria-label="内部模块下一页" onClick={()=>setPage(pageNow+1)}>下一页</button><select aria-label="定位内部小模块" value={chosen} disabled={count>0} onChange={e=>{const i=slots.findIndex(s=>s.id===e.target.value);if(i>=0){setChosen(e.target.value);setPage(Math.floor(i/6));}}}><option value="">定位一个小模块…</option>{slots.map((s,i)=><option key={s.id} value={s.id}>{i+1}. {units.get(s.node_id||s.origin_id||'')?.title}{s.node_id===null?'（已移除）':''}</option>)}</select></div>
    <div className="inner-connection-picker"><span>跨页连接：</span><select aria-label="内部连接起点" value={from} disabled={props.busy||count>0} onChange={e=>setFrom(e.target.value)}><option value="">选择输出小模块</option>{slots.filter(s=>s.node_id&&!blocked.has(s.node_id)&&!blocked.has(s.origin_id||'')).map((s,i)=><option key={s.id} value={s.id}>{i+1}. {units.get(s.node_id!)?.title}</option>)}</select><span>→</span><select aria-label="内部连接终点" value={to} disabled={props.busy||count>0} onChange={e=>setTo(e.target.value)}><option value="">选择接入小模块</option>{slots.filter(s=>s.node_id&&!blocked.has(s.node_id)&&!blocked.has(s.origin_id||'')).map((s,i)=><option key={s.id} value={s.id}>{i+1}. {units.get(s.node_id!)?.title}</option>)}</select><button aria-label="连接所选内部小模块" disabled={!from||!to||props.busy||count>0} onClick={()=>connect({source:from,target:to,sourceHandle:'out',targetHandle:'in'})}>连接</button></div>
    {props.replacement&&<div className="internal-replacement" role="status">正在替换：{units.get(slots.find(s=>s.id===props.replacement)?.node_id||'')?.title}。从模块库选择替代项。<button onClick={()=>props.onReplace('')}>取消替换</button></div>}
    <div className="connection-status" role="status">{note||'来源包含关系已保留；没有原文依据的内部执行顺序由您设计。'}</div>
    <div className="flow-stage"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={changes} onEdgesChange={(cs:EdgeChange[])=>{for(const c of cs)if(c.type==='remove'){const e=scope?.links.find(e=>e.source+'>'+e.target===c.id);if(e)cut(e.source,e.target);}}} onConnect={connect} onNodeClick={(_,n)=>setChosen(n.id)} onPaneClick={()=>setChosen('')} connectOnClick connectionRadius={30} fitView minZoom={.15} maxZoom={1.8} deleteKeyCode={['Delete','Backspace']}><Background gap={24} color="#ccd8d1"/><Controls/><MiniMap nodeColor="#8eafa2"/></ReactFlow></div>
    {slots.length===0&&<div className="canvas-empty"><Plus size={32}/><h2>把小模块加入这里</h2><p>当前加入项将属于“{parent.title}”。</p></div>}
    <button className="fit-button" onClick={()=>rf.fitView({padding:.1,minZoom:.5,maxZoom:1})}>适应内部画布</button>
    <div className="inner-edit-panel nodrag nopan">
      {selected&&<label>当前位置的接入要求 / 调整意图<textarea aria-label="内部模块调整意图" rows={2} maxLength={2000} value={selected.note} disabled={props.busy||count>0} onChange={e=>action(d=>putSlot(d,location,{...selected,note:e.target.value}))}/></label>}
      {pair.length>0&&<button onClick={()=>setPair([])}>返回分页视图（对照不改变原位置）</button>}
      {(scope?.links||[]).map((e,i)=><label key={e.source+'>'+e.target}>内部交接 {i+1}：{units.get(slots.find(s=>s.id===e.source)?.node_id||'')?.title} → {units.get(slots.find(s=>s.id===e.target)?.node_id||'')?.title}<input aria-label={'内部第'+(i+1)+'条连线条件'} maxLength={100} value={e.label} disabled={props.busy||count>0} onChange={event=>action(d=>{const s=scopeOf(d,location)!;return {...d,composition:{schema_version:1,scopes:d.composition!.scopes.map(a=>a===s?{...s,links:s.links.map(l=>l.source===e.source&&l.target===e.target?{...l,label:event.target.value}:l)}:a)}};})}/><button aria-label={'查看内部第'+(i+1)+'条连线'} onClick={()=>setPair([e.source,e.target])}>并排查看</button><button aria-label={'移除内部第'+(i+1)+'条连线'} onClick={()=>cut(e.source,e.target)}><Scissors size={12}/></button></label>)}
    </div>
  </div>;
}
export default function InternalCanvas(props:Props){return <ReactFlowProvider><Inside {...props}/></ReactFlowProvider>;}
