import React,{useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {ReactFlow,ReactFlowProvider,Background,Controls,MiniMap,Handle,Position,MarkerType,BaseEdge,EdgeLabelRenderer,getSmoothStepPath,applyNodeChanges,useReactFlow,useViewport,useNodesInitialized} from '@xyflow/react';
import type {Node,NodeProps,NodeChange,Edge,EdgeChange,EdgeProps,Connection} from '@xyflow/react';
import {Layers,Plus,ChevronRight,ChevronLeft,ChevronDown,Save,Download,Trash2,Check,AlertCircle,Network,BookOpen,Undo2,ShieldCheck,X,Search,Scissors,RefreshCw} from 'lucide-react';
import '@xyflow/react/dist/style.css';
import './style.css';
import {api,apiText,boot,download} from './api';
import {selectModules,modulePage,indexChildren} from './library';
import type {Unit} from './library';
import {connectionError,cutConnection} from './connections';
import blueprintData from './blueprints.json';
import {materializeBlueprint} from './blueprints';
import type {Blueprint} from './blueprints';
import CanvasHierarchy from './CanvasHierarchy';
import InternalCanvas from './InternalCanvas';
import {scopeOf,slotsAt,resolveLocation,putSlot,hasDescendants,designCounts,designError} from './composition';
import type {Part,Flow,Draft,Location} from './composition';
const BLUEPRINTS=blueprintData.blueprints as Blueprint[];
type DraftUpdate=React.SetStateAction<Draft>;
const empty=():Draft=>({id:null,revision:0,name:'我的新 Skill 方案',goal:'',instances:[],links:[]});
const kindLabel:Record<string,string>={theme:'大模块候选',file:'来源文件 / 小模块候选',section:'规则分类候选'};
const Card=React.memo(function Card({data,id}:NodeProps){
  const unit=data.unit as Unit,part=data.part as Part,index=data.childIndex as Map<string,Unit[]>;
  const stage=part.note.match(/^【([^】]+)】/)?.[1],open=!!data.treeOpen,childCount=(index.get(unit.id)||[]).length;
  const focus=data.focus as (id:string)=>void;
  useEffect(()=>{if(!open)return;let second=0;const first=requestAnimationFrame(()=>{second=requestAnimationFrame(()=>focus(id));});return()=>{cancelAnimationFrame(first);cancelAnimationFrame(second);};},[open,id,focus]);
  return <div className={'part-card '+(data.chosen?'chosen':'')+(open?' hierarchy-open':'')}>
    <Handle id="in" type="target" position={Position.Left} aria-label={'接入端口 '+id} title="接入：连接其他模块的输出"/><span className="port-label port-in">接入</span>
    <div className="part-meta"><Layers size={14}/>{kindLabel[unit.kind]}<span>{unit.source_version}{(unit as any).version_role==='历史版本'?' · 历史':''}</span></div>
    {stage&&<div className="draft-stage" title={part.note}>{stage}</div>}<strong>{unit.title}</strong>
    <div className="module-origin" title={unit.source_name+' · '+unit.source_version}>来源：{unit.source_name}</div>
    <p>{part.excluded.length?'已排除 '+part.excluded.length+' 个范围':'保留完整选择范围'}</p><small>复用待核验 · 连线表示设计意图</small>
    <button className="canvas-tree-button internal-enter nodrag" disabled={!!data.scopeBusy} aria-label={'进入大模块内部 '+unit.title} onClick={e=>{e.stopPropagation();(data.onEnter as (id:string)=>void)(id);}}>进入内部组装<ChevronRight size={14}/></button>
    {Number(data.internalCount)>0&&<small>内部已有 {Number(data.internalCount)} 层设计编辑</small>}
    <button className="canvas-tree-button nodrag" disabled={!childCount} aria-expanded={open} aria-label={(open?'收起':'展开')+'画布子模块 '+unit.title} onClick={e=>{e.stopPropagation();(data.toggleTree as (id:string)=>void)(id);}}>{open?<ChevronDown size={14}/>:<ChevronRight size={14}/>} {childCount?(open?'收起子模块':'展开子模块')+' · '+childCount:'没有更深的已登记子项'}</button>
    {open&&<section className="canvas-hierarchy nodrag nopan nowheel" onClick={e=>e.stopPropagation()}>
      <p className="hierarchy-caption">原始包含层级 · 展开不改变选择或执行顺序</p>
      <CanvasHierarchy unit={unit} index={index} path={[unit.id]} titles={[unit.title]} excluded={part.excluded} busy={!!data.scopeBusy}
        onSource={data.onSource as (u:Unit)=>void}
        onInclude={(nid,include)=>(data.onInclude as (id:string,nid:string,include:boolean)=>void)(id,nid,include)}/>
    </section>}
    <Handle id="out" type="source" position={Position.Right} aria-label={'输出端口 '+id} title="输出：拖到另一个模块的接入圆点，或依次点击两个圆点"/><span className="port-label port-out">输出</span>
  </div>;
});
const nodeTypes={part:Card};
function CutEdge(props:EdgeProps){
  const {zoom}=useViewport();
  const [path,x,y]=getSmoothStepPath(props);
  const cut=props.data?.cut as (()=>void)|undefined;
  const caption=typeof props.label==='string'?(props.label.includes('条件')?'条件进入':props.label.startsWith('普通')?'普通路线':props.label.startsWith('专项')?'专项路线':props.label.startsWith('依赖')?'依赖':'交接'):'';
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} interactionWidth={28}/><EdgeLabelRenderer><button className="edge-cut nodrag nopan" style={{transform:`translate(-50%, -50%) translate(${x}px,${y}px) scale(${1/zoom})`}} aria-label={'剪断连接 '+props.source+' 到 '+props.target} title={'剪断这条连接，保留两端模块；'+(typeof props.label==='string'?props.label:'期望交接')} onClick={e=>{e.stopPropagation();cut?.();}}><Scissors size={14}/></button>{typeof props.label==='string'&&props.label!=='期望交接'&&<div className="edge-condition" style={{transform:`translate(-50%, 0) translate(${x}px,${y+16/zoom}px) scale(${1/zoom})`}} title={props.label}>{caption}</div>}</EdgeLabelRenderer></>;
}
const edgeTypes={cuttable:CutEdge};
function Canvas({draft,units,childIndex,chosen,onChoose,onChange,onError,onPending,expanded,onSource,scopeBusy,onEnter}:{expanded:boolean,draft:Draft,units:Map<string,Unit>,childIndex:Map<string,Unit[]>,chosen:string,onChoose:(s:string)=>void,onChange:(d:DraftUpdate)=>void,onError:(s:string)=>void,onPending:(n:number)=>void,onSource:(u:Unit)=>void,scopeBusy:boolean,onEnter:(id:string)=>void}){
  const rf=useReactFlow();
  const initialized=useNodesInitialized();
  useEffect(()=>{if(!initialized)return;let second=0;const first=requestAnimationFrame(()=>{second=requestAnimationFrame(()=>{rf.fitView({padding:.12});});});return()=>{cancelAnimationFrame(first);cancelAnimationFrame(second);};},[initialized,expanded,rf]);
  const latest=useRef(draft);latest.current=draft;
  const pending=useRef(new Map<string,symbol>()),active=useRef(true);
  const [pendingCount,setPendingCount]=useState(0),[connectionNote,setConnectionNote]=useState('');
  const countPending=useCallback(()=>{const n=pending.current.size;setPendingCount(n);onPending(n);},[onPending]);
  useEffect(()=>{active.current=true;return()=>{active.current=false;pending.current.clear();onPending(0);};},[onPending]);
  const [nodes,setNodes]=useState<Node[]>([]);
  const [openTrees,setOpenTrees]=useState<Set<string>>(()=>new Set());
  const focus=useCallback((id:string)=>{rf.fitView({nodes:[{id}],padding:.2,minZoom:.75,maxZoom:1,duration:180});},[rf]);
  const toggleTree=useCallback((id:string)=>{onChoose(id);setOpenTrees(old=>{const next=new Set(old);if(next.has(id))next.delete(id);else next.add(id);return next;});},[onChoose]);
  const onInclude=useCallback((id:string,nid:string,include:boolean)=>{
    if((latest.current.composition?.scopes||[]).some(s=>s.owner_id===id)){onError('这个模块已有内部组装，先在内部恢复相关编辑后再调整原始排除范围。');return;}
    const current=latest.current.instances.find(p=>p.id===id);
    if(!include&&current&&!current.excluded.includes(nid)&&current.excluded.length>=150){onError('原草稿每模块最多排除150项；本次未改动，请制定完整分批方案。');return;}
    onChange(value=>({...value,instances:value.instances.map(p=>p.id===id?{...p,excluded:include?p.excluded.filter(e=>e!==nid):[...new Set([...p.excluded,nid])]}:p)}));
  },[onChange,onError]);
  useEffect(()=>{setNodes(previous=>draft.instances.map(p=>({...previous.find(n=>n.id===p.id),id:p.id,type:'part',position:{x:p.x,y:p.y},data:{unit:units.get(p.node_id),part:p,chosen:p.id===chosen,childIndex,treeOpen:openTrees.has(p.id),toggleTree,focus,onInclude,onSource,scopeBusy,onEnter,internalCount:(draft.composition?.scopes||[]).filter(s=>s.owner_id===p.id).length},selected:p.id===chosen})));},[draft.instances,draft.composition,units,chosen,childIndex,openTrees,toggleTree,focus,onInclude,onSource,scopeBusy,onEnter]);
  const cut=useCallback((source:string,target:string)=>{pending.current.delete(source+'>'+target);countPending();latest.current=cutConnection(latest.current,source,target);onChange(current=>cutConnection(current,source,target));setConnectionNote('已剪断连接，两端模块保留。');},[onChange,countPending]);
  const edges=useMemo<Edge[]>(()=>draft.links.map(e=>({id:e.source+'>'+e.target,source:e.source,target:e.target,label:e.label,sourceHandle:'out',targetHandle:'in',type:'cuttable',markerEnd:{type:MarkerType.ArrowClosed},style:{stroke:'#5a8577',strokeWidth:2},data:{cut:()=>cut(e.source,e.target)}})),[draft.links,cut]);
  const changes=(cs:NodeChange[])=>{
    cs=cs.filter(c=>{if(c.type==='remove'&&(latest.current.composition?.scopes||[]).some(s=>s.owner_id===c.id)){onError('此模块已有内部编辑，请先进入内部处理或恢复后再移除。');return false;}return true;});
    setNodes(previous=>applyNodeChanges(cs,previous));
    const removed=new Set<string>(),positions=new Map<string,{x:number,y:number}>();
    for(const change of cs){if(change.type==='remove')removed.add(change.id);else if(change.type==='position'&&!change.dragging&&change.position)positions.set(change.id,change.position);}
    if(!removed.size&&!positions.size)return;
    onChange(current=>({...current,instances:current.instances.filter(p=>!removed.has(p.id)).map(p=>positions.has(p.id)?{...p,x:positions.get(p.id)!.x,y:positions.get(p.id)!.y}:p),links:current.links.filter(e=>!removed.has(e.source)&&!removed.has(e.target))}));
  };
  const edgeChanges=(cs:EdgeChange[])=>{for(const change of cs)if(change.type==='remove'){const link=draft.links.find(e=>e.source+'>'+e.target===change.id);if(link)cut(link.source,link.target);}};
  const connect=(c:Connection)=>{
    const problem=designCounts(latest.current).links>=120?'外层与内部设计连接合计最多120条。':connectionError(latest.current,c.source,c.target);if(problem){onError(problem);return;}
    const link={source:c.source!,target:c.target!,label:'期望交接'},key=link.source+'>'+link.target,token=Symbol(key);
    const next={...latest.current,links:[...latest.current.links,link]};latest.current=next;
    pending.current.set(key,token);countPending();setConnectionNote('连接已显示，正在核对组装范围…');
    onChange(current=>connectionError(current,link.source,link.target)?current:{...current,links:[...current.links,link]});
    api('check',next).then(()=>{
      if(!active.current||pending.current.get(key)!==token)return;
      pending.current.delete(key);countPending();setConnectionNote('连接已核对，可继续组装；剪刀只移除这条线。');
    }).catch(e=>{
      if(!active.current||pending.current.get(key)!==token)return;
      pending.current.delete(key);countPending();latest.current=cutConnection(latest.current,link.source,link.target);
      onChange(current=>cutConnection(current,link.source,link.target));onError(e.message);setConnectionNote('连接核对未通过，这条线已撤回。');
    });
  };
  return <div className="canvas" onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}} onDrop={e=>{e.preventDefault();const nid=e.dataTransfer.getData('application/skill-module');if(!units.has(nid))return;if(designCounts(draft).instances>=60){onError('外层与内部设计位置合计最多60项，请保真分批。');return;}const pos=rf.screenToFlowPosition({x:e.clientX,y:e.clientY});onChange({...draft,instances:[...draft.instances,{id:crypto.randomUUID(),node_id:nid,x:pos.x,y:pos.y,excluded:[],note:''}]});}}>
    <div className="canvas-caption"><Network size={15}/>新方案画布 · {draft.instances.length} 模块 / {draft.links.length} 连接</div><div className="connection-help">右侧输出 → 左侧接入 · 拖动连接，或依次点击两个圆点 · 剪刀可断开 · 来源条件仍需遵守</div><div className={'connection-status '+(pendingCount?'pending':'')} role="status">{connectionNote}</div>
    {nodes.length===0&&<div className="canvas-empty"><Layers size={42}/><h2>把需要的模块拖到这里</h2><p>从共享模块库选择，可搜索全部来源。</p></div>}
    <div className="flow-stage"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={changes} onEdgesChange={edgeChanges} onConnect={connect} connectOnClick connectionRadius={30} onNodeClick={(_,n)=>onChoose(n.id)} onPaneClick={()=>onChoose('')} fitView minZoom={.2} maxZoom={1.8} deleteKeyCode={['Delete','Backspace']}><Background gap={24} color="#ccd8d1"/><Controls/><MiniMap nodeColor="#8eafa2"/></ReactFlow></div>
    <button className="fit-button" onClick={()=>rf.fitView({padding:.15})}>适应画布</button>
  </div>
}
export type AssemblySelection={nodeId:string,sourceSkillId:string,token:string};
export default function AssemblyWorkbench({selection,onSelectionHandled,onOpenMap,sourceRevision}:{selection:AssemblySelection|null,onSelectionHandled:()=>void,onOpenMap:(id:string,sid:string)=>void,sourceRevision:string}){
  const handled=useRef('');
  const [catalog,setCatalog]=useState<any>(null),[draft,setDraft]=useState<Draft>(empty),[saved,setSaved]=useState<any[]>([]),[trail,setTrail]=useState<string[]>([]),[chosen,setChosen]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[checks,setChecks]=useState<any>(null),[query,setQuery]=useState(''),[source,setSource]=useState<any>(null);
  const [libraryBusy,setLibraryBusy]=useState(true),[pendingCount,setPendingCount]=useState(0),[draftSession,setDraftSession]=useState(0);
  const [wholeSourceId,setWholeSourceId]=useState(''),[expandedCanvas,setExpandedCanvas]=useState(false);
  const [location,setLocation]=useState<Location|null>(null),[replacement,setReplacement]=useState('');
  useEffect(()=>{setLocation(null);setReplacement('');},[draftSession]);
  const editSerial=useRef(0);
  const draftRef=useRef(draft);draftRef.current=draft;
  const refreshRunning=useRef(false),seenRevision=useRef(sourceRevision);
  const factUnits=useMemo<Unit[]>(()=>[...(catalog?.nodes||[]),...(catalog?.historical_nodes||[])],[catalog]);
  const units=useMemo(()=>new Map<string,Unit>(factUnits.map(n=>[n.id,n])),[factUnits]);
  const childIndex=useMemo(()=>indexChildren(factUnits,[...(catalog?.contains||[]),...(catalog?.historical_contains||[])]),[factUnits,catalog]);
  type Origin={id:string,name:string,version:string,module_count:number,version_role?:string,family_id?:string};
  const sources:Origin[]=catalog?.sources||[];
  const [sourceFilter,setSourceFilter]=useState('all'),[level,setLevel]=useState('all'),[page,setPage]=useState(0);
  const [showHistory,setShowHistory]=useState(false);
  const allUnits=useMemo<Unit[]>(()=>(catalog?.nodes||[]).filter((n:any)=>showHistory||n.version_role!=='历史版本'),[catalog,showHistory]);
  const wholeBlueprints:Blueprint[]=(catalog?.blueprints||BLUEPRINTS).filter((b:Blueprint)=>showHistory||sources.find(s=>s.id===b.source_id)?.version_role!=='历史版本');
  useEffect(()=>{if(catalog&&!wholeBlueprints.some(b=>b.source_id===wholeSourceId)){const old=sources.find(s=>s.id===wholeSourceId);setWholeSourceId(sources.find(s=>s.family_id===old?.family_id&&s.version_role==='当前登记')?.id||wholeBlueprints[0]?.source_id||'');}},[catalog,showHistory,wholeSourceId]);
  const roots:Unit[]=useMemo(()=>allUnits.filter((n:Unit)=>n.kind==='theme'),[allUnits]);
  const focus=trail[trail.length-1];const children=useCallback((id:string):Unit[]=>childIndex.get(id)||[],[childIndex]);
  const scope=useMemo(()=>focus&&!query.trim()?new Set(children(focus).map(n=>n.id)):undefined,[focus,query,children]);
  const matches=useMemo(()=>selectModules(allUnits,query,sourceFilter,level,scope),[allUnits,query,sourceFilter,level,scope]);
  const paging=useMemo(()=>modulePage(matches,page),[matches,page]);
  const visible=paging.items;
  useEffect(()=>setPage(0),[query,sourceFilter,level,focus]);
  const wholeBlueprint=wholeBlueprints.find(b=>b.source_id===wholeSourceId);
  const showAll=()=>{setTrail([]);setQuery('');setSourceFilter('all');setLevel('all');setPage(0);};
  const part=draft.instances.find(p=>p.id===chosen),unit=part?units.get(part.node_id):null;
  const update=useCallback((next:DraftUpdate)=>{editSerial.current+=1;setDraft(next);setDirty(true);setChecks(null);},[]);
  const reload=()=>api('drafts').then(setSaved);
  const refreshLibrary=useCallback(async()=>{
    if(refreshRunning.current)return;refreshRunning.current=true;setLibraryBusy(true);
    try{
      const next=await api('catalog');
      const ids=new Set([...(next.nodes||[]),...(next.historical_nodes||[])].map((n:Unit)=>n.id));
      if(draftRef.current.instances.some(p=>!ids.has(p.node_id))||(draftRef.current.composition?.scopes||[]).some(s=>s.slots.some(p=>(p.node_id&&!ids.has(p.node_id))||(p.origin_id&&!ids.has(p.origin_id)))))throw new Error('更新后的模块库缺少当前草稿来源；已保留原模块库和草稿，请核对来源版本。');
      setCatalog(next);setNotice(`模块库已更新：${next.sources.length} 个 Skill，${next.nodes.length} 个候选范围。当前草稿保留。`);
    }catch(e:any){setError(e.message);}finally{refreshRunning.current=false;setLibraryBusy(false);}
  },[]);
  useEffect(()=>{let active=true;boot().then(()=>Promise.all([api('catalog'),api('drafts')])).then(([c,d])=>{if(active){setCatalog(c);setSaved(d);}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLibraryBusy(false);});return()=>{active=false;};},[]);
  useEffect(()=>{if(seenRevision.current===sourceRevision)return;seenRevision.current=sourceRevision;if(catalog)void refreshLibrary();},[sourceRevision,catalog,refreshLibrary]);
  useEffect(()=>{const handler=(e:BeforeUnloadEvent)=>{if(dirty)e.preventDefault();};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[dirty]);
  useEffect(()=>{setSource(null);},[chosen]);
  const openSource=useCallback(async(u:Unit)=>{try{setSource({...await api('source/'+u.id),source_name:u.source_name});}catch(e:any){setError(e.message);}},[]);
  const add=(nid:string)=>{
    if(busy||pendingCount){setError('保存或连接核对期间请稍后编辑。');return;}
    if(location){try{const parent=resolveLocation(draft,location,childIndex),slots=slotsAt(draft,location,parent,childIndex);let next:Draft;
      if(replacement){const old=slots.find(s=>s.id===replacement);if(!old?.node_id)throw new Error('待替换的位置已失效。');if(hasDescendants(draft,location,old.id))throw new Error('此项下已有内部编辑，请先处理下层编辑再替换。');next=putSlot(draft,location,{...old,node_id:nid});}
      else next=putSlot(draft,location,{id:'a-'+crypto.randomUUID(),origin_id:null,node_id:nid,x:(slots.length%2)*340,y:Math.floor((slots.length%6)/2)*230,note:''});
      const problem=designError(next,childIndex);if(problem)throw new Error(problem);update(next);setReplacement('');setNotice(replacement?'已在当前大模块内部替换；接入条件仍需核验。':'已加入当前大模块内部；未增加外层模块。');
    }catch(e:any){setError(e.message);}return;}
    if(designCounts(draft).instances>=60){setError('外层与内部设计位置合计最多60项，请保真分批。');return;}update({...draft,instances:[...draft.instances,{id:crypto.randomUUID(),node_id:nid,x:(draft.instances.length%3)*320,y:Math.floor(draft.instances.length/3)*180,excluded:[],note:''}]});
  };
  const enter=useCallback((id:string)=>{if(busy||pendingCount){setError('保存或连接核对期间请稍后切换。');return;}setChosen(id);setReplacement('');setLocation({owner_id:id,path:[]});},[busy,pendingCount]);
  useEffect(()=>{
    if(!selection||!catalog||handled.current===selection.token)return;
    handled.current=selection.token;
    const unit=units.get(selection.nodeId);
    if(unit&&selection.sourceSkillId!==unit.source_skill_id){setError('模块与地图来源身份不一致，请先核对来源。');onSelectionHandled();return;}
    if(!unit){setError('该范围尚未进入共享模块库，请先核对来源版本；草稿保持原样。');onSelectionHandled();return;}
    if(location){add(unit.id);onSelectionHandled();return;}
    const existing=draft.instances.find(p=>p.node_id===unit.id);
    if(existing){setChosen(existing.id);setNotice('已定位草稿中的 '+unit.title);}
    else if(designCounts(draft).instances>=60){setError('外层与内部设计位置合计最多60项，请保真分批。');}
    else{const id=crypto.randomUUID();update({...draft,instances:[...draft.instances,{id,node_id:unit.id,x:(draft.instances.length%3)*320,y:Math.floor(draft.instances.length/3)*180,excluded:[],note:''}]});setChosen(id);setNotice('已从知识地图加入 '+unit.title+'；保存草稿后可继续编辑。');}
    onSelectionHandled();
  },[selection,catalog,units,draft,update,onSelectionHandled]);
  const clone=()=>{if(pendingCount||busy)return;if(dirty){setError('请先保存当前草稿，再载入整套 Skill。');return;}if(!wholeBlueprint||!catalog)return;try{const next=materializeBlueprint(wholeBlueprint,catalog.sources,catalog.nodes);setLocation(null);setReplacement('');update(next);setDraftSession(v=>v+1);setChosen('');setExpandedCanvas(true);setNotice('已独立载入 '+wholeBlueprint.name+' '+wholeBlueprint.version+'：'+next.instances.length+' 个模块实例、'+next.links.length+' 条原文有据的主流程连接。原 Skill 保持只读；条件和辅助规则保留。');}catch(e:any){setError(e.message);}};
  const save=async()=>{if(pendingCount){setError('连接正在核对，请稍后保存。');return null;}const serial=editSerial.current;setBusy(true);try{const value=await api('drafts',draft);if(editSerial.current===serial){setDraft(value);setDirty(false);setNotice('草稿已保存，重新打开可继续编辑。');}else{setDraft(current=>({...current,id:value.id,revision:value.revision}));setDirty(true);setNotice('保存期间的新编辑已保留，请再保存一次。');}await reload();return editSerial.current===serial?value:null;}catch(e:any){setError(e.message);return null;}finally{setBusy(false);}};
  const remove=()=>{if(!part)return;if((draft.composition?.scopes||[]).some(s=>s.owner_id===part.id)){setError('这个大模块已有内部编辑，先进入内部处理或恢复编辑后再移除，避免丢失内部设计。');return;}update({...draft,instances:draft.instances.filter(p=>p.id!==part.id),links:draft.links.filter(e=>e.source!==part.id&&e.target!==part.id)});setChosen('');};
  return <div className="assembly-panel app">
    {error&&<div role="alert" className="alert"><AlertCircle size={16}/>{error}<button onClick={()=>setError('')}><X size={16}/></button></div>}{notice&&<div className="notice"><Check size={16}/>{notice}<button onClick={()=>setNotice('')}><X size={16}/></button></div>}
    <div className="toolbar"><div className="draft-title"><input aria-label="新Skill方案名称" value={draft.name} onChange={e=>update({...draft,name:e.target.value})}/><span>{dirty?'未保存':draft.id?'已保存 · 版本 '+draft.revision:'新草稿'}</span></div><button disabled={busy||pendingCount>0||!wholeBlueprint||!catalog} onClick={clone}>载入整套 Skill</button><button disabled={busy||pendingCount>0} onClick={()=>{if(dirty){setError('请先保存当前草稿。');return;}setLocation(null);setReplacement('');setDraft(empty());setDraftSession(v=>v+1);setChosen('');setChecks(null);}}><Plus size={15}/>空白方案</button><button onClick={()=>setExpandedCanvas(v=>!v)}>{expandedCanvas?'显示模块库与详情':'展开画布'}</button><button className="primary" disabled={busy||pendingCount>0} onClick={save}><Save size={15}/>保存草稿</button><button disabled={busy||pendingCount>0} onClick={async()=>{const value=await save();if(!value)return;try{const result=await apiText('drafts/'+value.id+'/package');download('Skill组装设计-'+value.name+'.json',result);setNotice('已导出冻结组装设计。Worker 先核验接入方案，不代表新 Skill 已生成。');}catch(e:any){setError(e.message);}}}><Download size={15}/>导出给 Worker</button></div>
    <div className={'workspace'+(expandedCanvas?' canvas-focused':'')}><aside className="library"><div className="panel-heading"><h2>共享模块库</h2><span>{sources.length} 个来源</span></div><div className="library-refresh"><span>{libraryBusy?'正在核对来源并载入模块…':'全部来源 · '+allUnits.length+' 个候选范围'}</span><button disabled={libraryBusy} onClick={refreshLibrary}><RefreshCw size={12}/>更新模块库</button></div><label className="import-check"><input type="checkbox" checked={showHistory} onChange={e=>{setShowHistory(e.target.checked);setTrail([]);setSourceFilter('all');}}/>显示历史版本模块</label><p className="hint">各 Skill 的模块已汇入同一列表，可直接搜索和加入。来源随卡片保留，复用待核验。</p>
      <div className="whole-skill"><h3>修改已有 Skill</h3><label><span>整套来源</span><select aria-label="选择整套 Skill 来源" value={wholeSourceId} onChange={e=>setWholeSourceId(e.target.value)}>{wholeBlueprints.map(b=><option key={b.source_id} value={b.source_id}>{b.name} · {b.version} · {sources.find(s=>s.id===b.source_id)?.version_role||'当前登记'}</option>)}</select></label><p>选择来源后，用上方“载入整套 Skill”建立独立草稿；完整范围和有据的主流程会一并载入。</p></div>
      <div className="search"><Search size={15}/><input aria-label="搜索全部模块" placeholder="搜索模块、来源或内容…" value={query} onChange={e=>setQuery(e.target.value)}/></div>
      <label className="source-filter"><span>来源（可选）</span><select aria-label="筛选模块来源" value={sourceFilter} onChange={e=>{setSourceFilter(e.target.value);setTrail([]);}}><option value="all">全部 Skill · {allUnits.length} 项</option>{sources.map(s=><option key={s.id} value={s.id}>{s.name} · {s.version} · {s.module_count} 项</option>)}</select></label>
      <div className="level-filters" aria-label="模块层级筛选">{[['all','全部'],['theme','大模块'],['file','小模块'],['section','规则分类']].map(([k,label])=><button className={level===k?'active':''} key={k} onClick={()=>{setLevel(k);setTrail([]);}}>{label}<span>{allUnits.filter(n=>(sourceFilter==='all'||n.source_skill_id===sourceFilter)&&(k==='all'||n.kind===k)).length}</span></button>)}</div>
      <details className="saved-drafts"><summary>已保存草稿 · {saved.length}</summary>{saved.length===0&&<p className="hint">尚无保存的方案。</p>}{saved.map(s=><button className="saved-draft" key={s.id} onClick={async()=>{if(pendingCount){setError('连接正在核对，请稍后切换草稿。');return;}if(dirty){setError('请先保存当前草稿再切换。');return;}try{setLocation(null);setReplacement('');setDraft(await api('drafts/'+s.id));setDraftSession(v=>v+1);setChosen('');setChecks(null);setNotice('已打开草稿 '+s.name);}catch(e:any){setError(e.message);}}}>{s.name}<small>版本 {s.revision}</small></button>)}</details>
      {focus&&<div className="breadcrumbs"><button onClick={showAll}>全部模块</button>{trail.map((id,i)=><React.Fragment key={id}><ChevronRight size={12}/><button onClick={()=>setTrail(trail.slice(0,i+1))}>{units.get(id)?.title}</button></React.Fragment>)}</div>}{focus&&!query&&<button className="back" onClick={()=>setTrail(t=>t.slice(0,-1))}><ChevronLeft size={14}/>返回上级</button>}
      <div className="library-pagination"><span>共 {paging.total} 项 · 第 {paging.current+1}/{paging.pages} 页</span><div><button aria-label="模块上一页" disabled={paging.current===0} onClick={()=>setPage(p=>p-1)}><ChevronLeft size={13}/></button><button aria-label="模块下一页" disabled={paging.current+1>=paging.pages} onClick={()=>setPage(p=>p+1)}><ChevronRight size={13}/></button></div></div>
      <div className="module-list">{visible.map(n=><div className="library-card" draggable onDragStart={e=>e.dataTransfer.setData('application/skill-module',n.id)} key={n.id}><small>{kindLabel[n.kind]}</small><strong>{n.title}</strong><div className="module-origin">来源：{n.source_name} · {n.source_version}</div><p className="content-origin" title={n.source_content.map(c=>c.path).join('\n')}>来源内容：{n.source_content.slice(0,2).map(c=>c.title).join('、')}{n.source_content.length>2?' 等'+n.source_content.length+'份内容':''}</p><div><button disabled={busy||pendingCount>0} aria-label={(location?(replacement?'替换为模块 ':'加入内部模块 '):'加入模块 ')+n.title} onClick={()=>add(n.id)}><Plus size={14}/>{location?(replacement?'替换此项':'加入到这里'):'加入'}</button>{children(n.id).length>0&&<button aria-label={'展开模块 '+n.title} onClick={()=>{setTrail(t=>[...t,n.id]);setQuery('');setLevel('all');}}>展开<ChevronRight size={14}/></button>}</div></div>)}{visible.length===0&&<p className="hint">没有匹配模块，可以调整搜索或筛选。完整规则随选中范围保留。</p>}</div></aside>
      {location?<InternalCanvas key={draftSession+'-'+location.owner_id+'-'+location.path.join('/')} draft={draft} location={location} units={units} index={childIndex} busy={busy} replacement={replacement} onReplace={setReplacement} onChange={update} onNavigate={setLocation} onSource={openSource} onError={setError} onPending={setPendingCount}/>:<ReactFlowProvider key={draftSession}><Canvas expanded={expandedCanvas} draft={draft} units={units} childIndex={childIndex} chosen={chosen} onChoose={setChosen} onChange={update} onError={setError} onPending={setPendingCount} onSource={openSource} scopeBusy={busy||pendingCount>0} onEnter={enter}/></ReactFlowProvider>}
      <aside className="inspector"><div className="panel-heading"><h2>方案与模块</h2><span>{draft.instances.length} 项</span></div><label>新 Skill 要完成什么？<textarea aria-label="新Skill目标" rows={4} placeholder="写清目标、输入和期望交付…" value={draft.goal} onChange={e=>update({...draft,goal:e.target.value})}/></label><button className="check-button" onClick={async()=>{try{setChecks(await api('check',draft));}catch(e:any){setError(e.message);}}}><ShieldCheck size={15}/>检查组装范围</button>
      {draft.links.length>0&&<div className="flow-list"><h3>流程交接 · 设计意图</h3>{draft.links.map((link,i)=><div key={link.source+'>'+link.target}><small>{units.get(draft.instances.find(p=>p.id===link.source)?.node_id||'')?.title} → {units.get(draft.instances.find(p=>p.id===link.target)?.node_id||'')?.title}</small><label className="flow-condition">交接条件 / 设计意图<input aria-label={'第'+(i+1)+'条连线的交接条件'} maxLength={100} value={link.label} onChange={e=>{const label=e.target.value;update(current=>({...current,links:current.links.map(l=>l.source===link.source&&l.target===link.target?{...l,label}:l)}));}}/></label><button aria-label={'移除第'+(i+1)+'条连线'} onClick={()=>update({...draft,links:draft.links.filter(e=>e!==link)})}><X size={12}/>移除连线</button></div>)}</div>}
      {part&&unit?<><button onClick={()=>onOpenMap(unit.id,unit.source_skill_id)}><Network size={14}/>在知识地图中查看</button><div className="selection-heading"><small>{kindLabel[unit.kind]} · {unit.source_version}</small><h3>{unit.title}</h3><div className="module-origin">来源：{unit.source_name}</div><div className="origin-details">{unit.source_content.map(c=><p key={c.file_id}><strong>{c.title}</strong><small>{c.path} · {c.ranges.map(r=>'L'+r.start_line+'–'+r.end_line).join(' / ')}</small></p>)}</div></div><p className="hint">取消子项只调整新方案的选择范围。正式标准是否适用，必须由接入分析确认。</p>{children(unit.id).map(c=><label className="submodule" key={c.id}><input type="checkbox" disabled={(draft.composition?.scopes||[]).some(s=>s.owner_id===part.id)} checked={!part.excluded.includes(c.id)} onChange={e=>update({...draft,instances:draft.instances.map(p=>p.id===part.id?{...p,excluded:e.target.checked?p.excluded.filter(id=>id!==c.id):[...p.excluded,c.id]}:p)})}/><span>{c.title}<small>{kindLabel[c.kind]}</small></span></label>)}<button onClick={()=>update({...draft,instances:draft.instances.map(p=>p.id===part.id?{...p,excluded:[]}:p)})}><Undo2 size={14}/>恢复本模块完整范围</button><label>接入要求 / 调整意图<textarea rows={3} value={part.note} onChange={e=>update({...draft,instances:draft.instances.map(p=>p.id===part.id?{...p,note:e.target.value}:p)})}/></label>{unit.path&&<button onClick={async()=>{try{setSource({...await api('source/'+unit.id),source_name:unit.source_name});}catch(e:any){setError(e.message);}}}><BookOpen size={14}/>查看完整来源</button>}<button className="danger" onClick={remove}><Trash2 size={14}/>从新方案移除模块</button></>:<div className="inspector-empty"><Layers size={32}/><p>点选画布模块，查看和调整它的小模块范围。</p></div>}
      {checks&&<div className="checks"><h3>范围检查</h3><p>{checks.module_count} 个模块 · {checks.selected_nodes} 个来源节点</p><p>复用合同与业务语义：待独立核验</p><p>{checks.unselected_reference_candidates.length} 项未选文件名引用候选 · {checks.overlaps.length} 项范围重叠</p>{checks.unselected_reference_candidates.slice(0,12).map((r:any,i:number)=><div key={i}><small>{r.source_title} → {r.target_title}</small></div>)}<p>所有连线都是期望交接，尚未证明可执行。</p></div>}</aside></div>

    {source&&<div className="modal-backdrop"><div className="source-modal"><div className="panel-heading"><div><h2>{source.title}</h2><small>{source.source_name} · {source.version} · {source.path} · SHA256 {source.sha256.slice(0,16)}</small></div><button onClick={()=>setSource(null)} aria-label="关闭原文"><X size={20}/></button></div><pre>{source.text}</pre></div></div>}
  </div>
}

