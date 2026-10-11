import {useEffect,useState} from 'react';
import {RefreshCw,ShieldCheck,Copy,Download,X,ArrowRight,BookOpen,AlertCircle} from 'lucide-react';
import {api,download} from './api';
import './ReleasePanel.css';

function State({source,formal=false}:{source:any,formal?:boolean}){
  const state=source?.state;
  const label=state==='MANIFEST_MATCH'?'发布清单文件一致':state==='MANIFEST_DIFF'?'与正式发布清单有差异':state==='DECLARATION_ONLY'?'发布声明已定位 · 全包未核对':state==='ENTRY_ONLY'?'仅核对入口文件':state==='ENTRY_VERIFIED'?'登记入口已核对':state==='ERROR'?'来源核对异常':formal?'正式发布凭证未登记':'尚未核对';
  return <><span className={'release-state '+(state==='MANIFEST_MATCH'?'good':['ERROR','MANIFEST_DIFF'].includes(state)?'warn':'neutral')}>{label}</span>{source?.expected_files&&<small>已读取 {source.checked_files} / {source.expected_files} 份清单文件{source.issue_count>0&&` · ${source.issue_count} 项差异`}</small>}{source?.error&&<p className="release-error">{source.error}</p>}</>;
}

export function ReleasePanel({onOpenImports,onOpenVersion}:{onOpenImports:(id:string)=>void,onOpenVersion:(id:string)=>void}){
  const [data,setData]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[filter,setFilter]=useState('all'),[packageData,setPackageData]=useState<any>(null),[message,setMessage]=useState('');
  const load=async(fresh=false)=>{setBusy(true);setError('');try{setData(await api(fresh?'releases/refresh':'releases/status',fresh?{}:undefined));}catch(e:any){setError(e.message);}finally{setBusy(false);}};
  useEffect(()=>{void load();},[]);
  const generate=async(id:string,mode:string)=>{setBusy(true);setError('');setMessage('');try{setPackageData(await api('releases/handoff',{family_id:id,mode}));}catch(e:any){setError(e.message);}finally{setBusy(false);}};
  const rows=(data?.families||[]).filter((r:any)=>filter==='all'||filter==='sync'&&r.needs_workbench_sync||filter==='install'&&r.installed?.state==='MANIFEST_DIFF'||filter==='paused'&&r.paused);
  return <section className="release-panel">
    <div className="release-heading"><div><span className="eyebrow">每一步都有自己的版本</span><h2>发布与调用状态</h2><p>看清正式来源、安装副本和工作台登记之间的差异，再把准确指令交给目标对话框。</p></div><button disabled={busy} onClick={()=>void load(true)}><RefreshCw size={16} className={busy?'spin':''}/>{busy?'正在核对来源…':'重新核对发布状态'}</button></div>
    <div className="release-chain"><span>正式发布</span><ArrowRight size={18}/><span>本机安装 / 工作台登记</span><ArrowRight size={18}/><span>用户发到目标对话框</span><ArrowRight size={18}/><span>实际读取回执</span></div>
    <p className="release-boundary"><ShieldCheck size={16}/>本页只读核对。调用指令用于分析与维护准备；项目使用状态需实际回执，旧项目与草稿保持原版本。</p>
    {error&&<div role="alert" className="alert"><AlertCircle size={17}/>{error}</div>}
    {data?.pointer_state==='CHANGED'&&<div role="alert" className="alert">正式库声明已变化，请重新核对发布来源配置。保留本批版本记录，暂停生成正式来源指令。</div>}
    <div className="release-toolbar"><div role="group" aria-label="筛选发布状态">{[['all','全部 Skill'],['sync','登记版本待同步'],['install','安装存在差异'],['paused','暂停的 Skill']].map(([id,label])=><button key={id} aria-pressed={filter===id} className={filter===id?'active':''} onClick={()=>setFilter(id)}>{label}{id==='sync'&&data&&` · ${data.families.filter((r:any)=>r.needs_workbench_sync).length}`}</button>)}</div><small>{data?`核对于 ${new Date(data.checked_at).toLocaleString('zh-CN')}`:'正在读取来源…'}</small></div>
    {rows.map((r:any)=><article className="release-card" key={r.family_id}>
      <div className="release-card-heading"><div><BookOpen size={19}/><h3>{r.name}</h3></div>{r.paused&&<span className="release-paused">云端暂停</span>}{r.needs_workbench_sync&&<span className="release-state warn">工作台待同步</span>}</div>
      {r.error?<p className="release-error">{r.error}</p>:<><div className="release-columns">
        <div><h4>正式发布来源</h4><strong>{r.formal.version||'尚无独立正式版本记录'}</strong><State source={r.formal} formal/>{r.formal.note&&<small>{r.formal.note}</small>}</div>
        <div><h4>本机安装副本</h4><strong>{r.installed.state==='MANIFEST_MATCH'?`清单内对应 ${r.formal.version}`:r.installed.state==='MANIFEST_DIFF'?`与 ${r.installed.compared_version} 不一致`:'完整版本身份待核对'}</strong><State source={r.installed}/>{r.installed.state==='ENTRY_ONLY'&&<small>{r.installed.entry_matches_registered?'入口与登记快照一致':'入口与登记快照不同'} · 未核对完整安装包</small>}</div>
        <div><h4>工作台登记</h4><strong>{r.registered.version}</strong><State source={r.registered}/><small>{r.versions.length} 份登记版本 · 快照与旧草稿保留</small></div>
        <div><h4>项目 / 对话框使用</h4><strong>尚未登记调用回执</strong><small>未登记 ≠ 没有使用</small><small>复制、导出指令不会自动标为已调用。实际回执登记将在后续批次接入。</small></div>
      </div><p className="release-note">{r.note}</p>
      <div className="release-actions"><button disabled={busy||!r.can_handoff_formal} onClick={()=>void generate(r.family_id,'formal')}><Copy size={15}/>生成正式来源调用指令</button><button disabled={busy||!r.can_handoff_registered} onClick={()=>void generate(r.family_id,'registered')}>生成登记快照分析指令</button><button onClick={()=>onOpenImports(r.family_id)}>查看导入与同步</button></div>
      <details><summary>准确路径、核对范围与登记版本</summary><dl><dt>正式入口 / 发布声明</dt><dd>{r.formal.entry||r.formal.root||'未登记'}</dd><dt>发布凭证</dt><dd>{r.formal.receipt_path||'未登记'}</dd><dt>本机安装入口</dt><dd>{r.installed.entry||r.installed.root}</dd><dt>原登记来源</dt><dd>{r.registered.original_root}</dd><dt>不可变快照入口</dt><dd>{r.registered.entry||r.registered.snapshot_root}</dd><dt>核对范围</dt><dd>{r.formal.scope||r.formal.note||'没有完整发布清单核验'}；清单文件一致不代表额外文件、执行语义或视频已通过。</dd></dl>{r.installed.issues?.length>0&&<div className="release-issues"><strong>安装差异（最多显示100项）</strong>{r.installed.issues.map((x:any)=><p key={x.path}>{x.path} · {x.state}</p>)}</div>}<div className="release-versions">{r.versions.map((v:any)=><button key={v.version_id} onClick={()=>onOpenVersion(v.skill_id)}>{v.version} · {v.role} → 查看地图</button>)}</div></details></>}
    </article>)}
    {data&&rows.length===0&&<p className="release-empty">当前筛选下没有对应的 Skill。</p>}
    {data?.unconfigured_family_count>0&&<p className="release-note">另有 {data.unconfigured_family_count} 个新登记家族尚未配置发布核对来源。</p>}
    {packageData&&<div className="modal-backdrop"><section role="dialog" aria-modal="true" aria-labelledby="handoff-title" className="modal release-handoff"><button className="modal-close" aria-label="关闭调用指令" onClick={()=>setPackageData(null)}><X size={18}/></button><h2 id="handoff-title">{packageData.version} · {packageData.mode==='formal'?'正式来源调用':'登记快照分析'}指令</h2><p>复制后，由您发到需要使用它的对话框。该指令仅授权只读分析与维护准备。</p><textarea aria-label="准确调用指令" readOnly value={packageData.instruction}/><div className="release-actions"><button className="primary" onClick={async()=>{try{await navigator.clipboard.writeText(packageData.instruction);setMessage('指令已复制，请发到目标对话框。');}catch{setMessage('浏览器没有提供剪贴板权限，请在上方文本框选中并复制。');}}}><Copy size={15}/>复制调用指令</button><button onClick={()=>{download('Skill调用交接-'+packageData.version+'.json',packageData);setMessage('已导出交接包；尚未发送或登记实际调用。');}}><Download size={15}/>导出调用交接包</button></div>{message&&<p role="status">{message}</p>}<small>交接 SHA-256：{packageData.handoff_sha256}</small></section></div>}
  </section>;
}
