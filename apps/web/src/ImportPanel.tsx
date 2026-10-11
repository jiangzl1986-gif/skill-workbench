import React,{useEffect,useRef,useState} from 'react';
import {api} from './api';
type Version={skill_id:string,family_id:string,version_id:string,name:string,version:string,version_role:string,original_root:string,source_status:string};
type Candidate={root:string,name:string,version:string};
type Preview={preview_id:string,preview_hash:string,name:string,version:string,family_id:string,file_count:number,total_bytes:number,module_titles:string[],nodes:number,unresolved_count:number,unresolved:any[],manifest:{path:string,bytes:number,sha256:string}[],warning:string};

async function hash(raw:ArrayBuffer){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw))).map(x=>x.toString(16).padStart(2,'0')).join('');}
function base64(raw:Uint8Array){let s='';for(const x of raw)s+=String.fromCharCode(x);return btoa(s);}
async function droppedFiles(items:DataTransferItemList):Promise<File[]>{
  const out:File[]=[];
  const entries=Array.from(items).map(item=>({entry:(item as any).webkitGetAsEntry?.(),file:item.getAsFile()}));
  async function walk(entry:any,prefix:string){
    if(entry.isFile){const f:File=await new Promise((resolve,reject)=>entry.file(resolve,reject));Object.defineProperty(f,'importPath',{value:prefix+f.name});out.push(f);}
    else if(entry.isDirectory){const reader=entry.createReader();let page:any[];do{page=await new Promise((resolve,reject)=>reader.readEntries(resolve,reject));for(const e of page)await walk(e,prefix+entry.name+'/');}while(page.length);}
    if(out.length>5000)throw new Error('文件超过5000，请制定完整分批方案。');
  }
  for(const item of entries){if(item.entry)await walk(item.entry,'');else if(item.file)out.push(item.file);}
  return out;
}

export default function ImportPanel({initialFamily,onAdopted,onOpenVersion}:{initialFamily:string,onAdopted:(id:string)=>Promise<void>,onOpenVersion:(id:string)=>void}){
  const [versions,setVersions]=useState<Version[]>([]),[family,setFamily]=useState(initialFamily),[root,setRoot]=useState(''),[searchRoot,setSearchRoot]=useState('C:\\Users\\0.0\\.codex\\skills'),[name,setName]=useState(''),[version,setVersion]=useState(''),[uploadId,setUploadId]=useState(''),[uploadLabel,setUploadLabel]=useState('');
  const [candidates,setCandidates]=useState<Candidate[]>([]),[selected,setSelected]=useState<string[]>([]),[queue,setQueue]=useState<Candidate[]>([]),[preview,setPreview]=useState<Preview|null>(null),[relation,setRelation]=useState(false),[missing,setMissing]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(''),[history,setHistory]=useState(false);
  const folderInput=useRef<HTMLInputElement>(null),zipInput=useRef<HTMLInputElement>(null),seenInitial=useRef('__pending');
  const heads=versions.filter(v=>v.version_role==='当前登记');
  const reload=async()=>setVersions(await api('imports/versions'));
  useEffect(()=>{void reload().catch(e=>setError(e.message));},[]);
  function selectFamily(value:string){setFamily(value);const v=heads.find(v=>v.family_id===value);setRoot(v?.original_root||'');setName(v?.name||'');setVersion('');setUploadId('');setUploadLabel('');setPreview(null);setRelation(false);setMissing(false);}
  useEffect(()=>{if(versions.length&&seenInitial.current!==initialFamily){seenInitial.current=initialFamily;selectFamily(initialFamily);}},[initialFamily,versions]);
  async function action(fn:()=>Promise<void>){if(busy)return;setBusy(true);setError('');try{await fn();}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  function choose(c:Candidate){setFamily('');setUploadId('');setUploadLabel('');setRoot(c.root);setName(c.name);setVersion(c.version);setPreview(null);setRelation(false);setMissing(false);}
  async function prepare(){setPreview(null);setRelation(false);setMissing(false);setMessage('正在完整核对原文和来源文件…');const p=await api('imports/preview',{root:uploadId?'':root,upload_id:uploadId,name,version,family_id:family});setPreview(p);setName(p.name);setVersion(p.version);setMessage('预览已冻结；尚未接入工作台。');}
  async function sendFiles(files:File[],kind:'folder'|'zip'){
    if(!files.length)return;if(files.length>5000)throw new Error('最多5000文件，未截断导入。');
    if(kind==='zip'&&(files.length!==1||files[0].size>2097152))throw new Error('本批ZIP限一个、2MiB以内。');
    let total=0;for(const file of files){if(file.size>2097152)throw new Error('单文件超过2MiB：'+file.name);total+=file.size;}if(total>33554432)throw new Error('来源超过32MiB，请制定完整分批方案。');
    const paths=files.map(f=>(f as any).importPath||f.webkitRelativePath||f.name);const first=paths[0].split('/')[0];
    const strip=kind==='folder'&&paths.every(p=>p.startsWith(first+'/'));
    const records=[];
    for(let i=0;i<files.length;i++){setMessage('核对文件 '+(i+1)+' / '+files.length);records.push({path:strip?paths[i].slice(first.length+1):paths[i],bytes:files[i].size,sha256:await hash(await files[i].arrayBuffer())});}
    const start=await api('imports/uploads',{kind,files:records});
    for(let i=0;i<files.length;i++){
      const raw=new Uint8Array(await files[i].arrayBuffer());setMessage('上传 '+(i+1)+' / '+files.length+'：'+records[i].path);
      if(!raw.length)await api('imports/uploads/'+start.upload_id+'/chunk',{path:records[i].path,offset:0,data:''});
      for(let offset=0;offset<raw.length;offset+=start.chunk_bytes)await api('imports/uploads/'+start.upload_id+'/chunk',{path:records[i].path,offset,data:base64(raw.slice(offset,offset+start.chunk_bytes))});
    }
    setVersion('');if(!family)setName('');setUploadId(start.upload_id);setUploadLabel(kind==='zip'?files[0].name:first+' · '+files.length+' 文件');setRoot('');setPreview(null);setMessage('完整文件已上传；填写名称与版本后预览。');
  }
  async function adopt(){if(!preview)return;const r=await api('imports/confirm',{preview_id:preview.preview_id,preview_hash:preview.preview_hash,relation_confirmed:relation,missing_ack:missing});setPreview(null);await reload();await onAdopted(r.id);setMessage('已接入知识地图、共享模块库和整套方案。原 Skill 没有改写。');if(queue.length){const [next,...rest]=queue;setQueue(rest);choose(next);}}
  return <section className="import-panel">
    <div className="section-heading"><h2>导入与同步</h2><span className="small-badge">来源只读 · 新版先预览 · 旧版保留</span></div>
    <p className="muted">无需安装 Skill。选择准确目录，或拖入完整文件夹 / ZIP，核对后即可加入地图和模块库。</p>
    {error&&<div role="alert" className="alert">{error}</div>}{message&&<div role="status" className="notice">{message}</div>}
    <div className="import-grid"><div className="import-card">
      <h3>1. 选择来源</h3><label>导入方式<select aria-label="导入或更新已有Skill" disabled={busy} value={family} onChange={e=>selectFamily(e.target.value)}><option value="">新增一个独立 Skill</option>{heads.map(v=><option value={v.family_id} key={v.family_id}>更新：{v.name} · {v.version}</option>)}</select></label>
      <label>准确目录（包含 SKILL.md）<input aria-label="Skill来源目录" disabled={busy} value={root} onChange={e=>{setRoot(e.target.value);setVersion('');setUploadId('');setUploadLabel('');setPreview(null);}} placeholder="例如 Z:\\我的Skill\\示例"/></label>
      <div className="import-drop" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!busy){const items=e.dataTransfer.items;void action(async()=>{const files=await droppedFiles(items);await sendFiles(files,files.length===1&&files[0].name.toLowerCase().endsWith('.zip')?'zip':'folder');});}}}>
        <strong>{uploadLabel||'拖入完整 Skill 文件夹或 ZIP'}</strong><p>保留所有规则和附件；只拖 SKILL.md 会保留缺失引用提示。</p><button disabled={busy} onClick={()=>folderInput.current?.click()}>选择文件夹</button><button disabled={busy} onClick={()=>zipInput.current?.click()}>选择 ZIP</button>
        <input hidden ref={folderInput} type="file" multiple {...{webkitdirectory:''} as any} onChange={e=>{const files=Array.from(e.target.files||[]);void action(()=>sendFiles(files,'folder'));e.target.value='';}}/>
        <input hidden ref={zipInput} type="file" accept=".zip" onChange={e=>{const files=Array.from(e.target.files||[]);void action(()=>sendFiles(files,'zip'));e.target.value='';}}/>
      </div>
      <label>来源名称<input aria-label="导入Skill名称" disabled={busy} value={name} onChange={e=>{setName(e.target.value);setPreview(null);}} placeholder="可从 SKILL.md 读取"/></label>
      <label>准确版本<input aria-label="导入Skill版本" disabled={busy} value={version} onChange={e=>{setVersion(e.target.value);setPreview(null);}} placeholder="可读取声明；无声明时填写快照日期"/></label>
      <div className="task-actions"><button className="primary" disabled={busy||(!root&&!uploadId)} onClick={()=>action(prepare)}>{busy?'正在核对…':'预览完整来源与模块'}</button>{family&&<button disabled={busy} onClick={()=>action(async()=>{const r=await api('imports/check/'+family,{});setMessage(r.status+(r.changes?.length?' · '+r.changes.length+' 个文件变化':'')+(r.error?' · '+r.error:''));await reload();})}>核对原目录是否更新</button>}</div>
      <details><summary>在指定目录查找已有 Skill</summary><label>搜索范围<input aria-label="Skill搜索目录" disabled={busy} value={searchRoot} onChange={e=>setSearchRoot(e.target.value)}/></label><button disabled={busy} onClick={()=>action(async()=>{const r=await api('imports/discover',{root:searchRoot,depth:3});setCandidates(r.candidates);setSelected([]);setMessage('发现 '+r.candidates.length+' 个候选；尚未导入。');})}>搜索此目录</button>
      {candidates.map(c=><label className="import-candidate" key={c.root}><input type="checkbox" disabled={busy} checked={selected.includes(c.root)} onChange={e=>setSelected(a=>e.target.checked?[...a,c.root]:a.filter(p=>p!==c.root))}/><span><strong>{c.name} {c.version}</strong><small>{c.root}</small></span></label>)}
      {!!selected.length&&<button disabled={busy} onClick={()=>{const list=candidates.filter(c=>selected.includes(c.root));choose(list[0]);setQueue(list.slice(1));}}>逐个预览选中的 {selected.length} 个 Skill</button>}{queue.length>0&&<p>还有 {queue.length} 个待逐个核对。</p>}</details>
    </div><div className="import-card">
      <h3>2. 核对后接入三个视图</h3>{preview?<><h4>{preview.name} · {preview.version}</h4><p>{preview.file_count} 文件 · {(preview.total_bytes/1024).toFixed(1)} KiB · {preview.module_titles.length} 模块组 · {preview.nodes} 原文节点</p><p className="muted">{preview.warning}</p><ul>{preview.module_titles.map((t,i)=><li key={i}>{t}</li>)}</ul><details><summary>完整来源清单与校验</summary><div className="import-manifest">{preview.manifest.map(f=><p key={f.path}><strong>{f.path}</strong><small>{f.bytes} 字节 · {f.sha256}</small></p>)}</div></details>
        {preview.family_id&&<label className="import-check"><input aria-label="确认来源属于新版" type="checkbox" checked={relation} onChange={e=>setRelation(e.target.checked)}/>我确认这是所选 Skill 的新版本；旧版和旧草稿继续保留。</label>}
        {preview.unresolved_count>0&&<><details open><summary>{preview.unresolved_count} 个缺失引用，依赖尚未完整</summary>{preview.unresolved.map((r,i)=><p key={i}>{r.path}:{r.line} → {r.token}</p>)}</details><label className="import-check"><input type="checkbox" checked={missing} onChange={e=>setMissing(e.target.checked)}/>知晓缺失依赖，仅以结构候选接入。</label></>}
        <button className="primary" disabled={busy||(!!preview.family_id&&!relation)||(preview.unresolved_count>0&&!missing)} onClick={()=>action(adopt)}>确认这份预览并接入</button><small className="import-hash">预览校验：{preview.preview_hash}</small>
      </>:<p className="muted">预览后会显示模块、完整文件和缺失引用。确认只采纳这份准确内容；原文件再次变化时，需重新预览。</p>}
    </div></div>
    <div className="import-card version-history"><div className="section-heading"><h3>已登记版本</h3><label className="import-check"><input type="checkbox" checked={history} onChange={e=>setHistory(e.target.checked)}/>显示历史版本</label></div>{versions.filter(v=>history||v.version_role==='当前登记').map(v=><div className="version-row" key={v.version_id}><div><strong>{v.name} · {v.version}</strong><small>{v.version_role} · {v.source_status}</small><small>{v.original_root||'上传冻结快照；提供新版包即可同步'}</small></div><button onClick={()=>onOpenVersion(v.skill_id)}>查看此版地图</button><button disabled={busy||v.version_role!=='当前登记'} onClick={()=>selectFamily(v.family_id)}>预览新版</button></div>)}</div>
  </section>;
}
