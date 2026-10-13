import sourceData from './sources.json';
import type {Unit} from '../assembly/library';
import {indexChildren} from '../assembly/library';
import {designError, slotsAt} from '../assembly/composition';
import type {Draft, Location} from '../assembly/composition';
import {connectionError} from '../assembly/connections';

export const data=sourceData;
export const units=data.units as Unit[];
export const byId=new Map(units.map(u=>[u.id,u]));
export const children=indexChildren(units,data.contains);
export const STORAGE_KEY='skill-workbench-public-demo-v1';
export const LIMIT=2*1024*1024;
export const fileUnit=(path:string)=>units.find(u=>u.path===path&&u.kind==='file')!;
export const outline=fileUnit('notes-to-outline/modules/outline/SKILL.md');
export const evidence=fileUnit('evidence-review/modules/evidence/SKILL.md');
export const uid=()=> 'a-'+crypto.randomUUID();
export function freshDraft():Draft{
  const chosen=[fileUnit('notes-to-outline/modules/collect/SKILL.md'),outline,units.find(u=>u.title==='自检与交付')!];
  return {id:null,revision:0,name:'Notes to outline + evidence review',goal:'Design where evidence checking belongs; verify interfaces before implementation.',instances:chosen.map((u,i)=>({id:'p-'+i,node_id:u.id,x:i*320,y:110,excluded:[],note:''})),links:[]};
}
const bounded=(s:unknown,max:number)=>typeof s==='string'&&s.length<=max;
const position=(n:any)=>Number.isFinite(n.x)&&Number.isFinite(n.y)&&Math.abs(n.x)<=20000&&Math.abs(n.y)<=20000;
const identifier=(s:unknown)=>typeof s==='string'&&/^[a-zA-Z0-9-]{1,70}$/.test(s);
const only=(o:object,allowed:string[])=>Object.keys(o).every(k=>allowed.includes(k));
// Validate storage as untrusted input before shared, typed composition helpers see it.
export function validateDraft(value:unknown):string|null{
  try{
    if(new TextEncoder().encode(JSON.stringify(value)).length>LIMIT)return 'Draft exceeds 2 MiB.';
    const d=value as Draft;
    if(!d||!only(d,['id','revision','name','goal','instances','links','composition']))return 'Unknown draft fields.';
    if(!d||(!bounded(d.name,100)||d.name.length===0)||!bounded(d.goal,4000)||!Number.isInteger(d.revision)||d.revision<0||!Array.isArray(d.instances)||!Array.isArray(d.links)||d.instances.length>60||d.links.length>120) return 'Invalid draft header or limits.';
    if(d.id!==null&&!identifier(d.id))return 'Invalid draft identity.';
    const ids=new Set<string>();
    for(const p of d.instances){if(!only(p,['id','node_id','x','y','excluded','note'])||!identifier(p.id)||ids.has(p.id)||!byId.has(p.node_id)||!position(p)||!bounded(p.note,2000)||!Array.isArray(p.excluded)||p.excluded.length!==0)return 'Invalid or unknown module position.';ids.add(p.id);}
    const validateLinks=(links:any[])=>links.every(e=>e&&only(e,['source','target','label'])&&identifier(e.source)&&identifier(e.target)&&bounded(e.label,100));
    if(!validateLinks(d.links))return 'Invalid connection.';
    const checked:typeof d.links=[];
    for(const link of d.links){const err=connectionError({instances:d.instances,links:checked},link.source,link.target);if(err)return err;checked.push(link);}
    if(d.composition){
      if(!only(d.composition,['schema_version','scopes'])||d.composition.schema_version!==1||!Array.isArray(d.composition.scopes)||d.composition.scopes.length>60)return 'Invalid internal design.';
      for(const s of d.composition.scopes){
        if(!only(s,['owner_id','path','slots','links'])||!identifier(s.owner_id)||!Array.isArray(s.path)||s.path.length>60||!s.path.every(identifier)||!Array.isArray(s.slots)||s.slots.length>60||!Array.isArray(s.links)||s.links.length>120||!validateLinks(s.links))return 'Invalid internal canvas.';
        for(const a of s.slots)if(!only(a,['id','origin_id','node_id','x','y','note'])||!identifier(a.id)||(a.origin_id!==null&&!byId.has(a.origin_id))||(a.node_id!==null&&!byId.has(a.node_id))||!position(a)||!bounded(a.note,2000))return 'Invalid or unknown inner module.';
      }
    }
    return designError(d,children);
  }catch{return 'Unreadable draft; reset or recover a valid design.';}
}
export function restoreDraft():{draft:Draft;message:string|null}{
  try{const raw=localStorage.getItem(STORAGE_KEY);if(!raw)return {draft:freshDraft(),message:null};if(raw.length>LIMIT)throw Error('Saved draft too large.');const parsed=JSON.parse(raw);const err=validateDraft(parsed);if(err)throw Error(err);return {draft:parsed,message:null};}
  catch{return {draft:freshDraft(),message:'Saved data could not be read. The public example is loaded; nothing was overwritten.'};}
}
export function retainedNodes(d:Draft):string[]{
  const selected=new Set<string>();let visits=0;
  function walk(nid:string,l:Location,ancestry:Set<string>){
    if(++visits>5000||ancestry.has(nid))throw Error('Source traversal exceeded its safe bound.');
    selected.add(nid);const next=new Set([...ancestry,nid]);
    for(const a of slotsAt(d,l,nid,children))if(a.node_id)walk(a.node_id,{owner_id:l.owner_id,path:[...l.path,a.id]},next);
  }
  for(const p of d.instances)walk(p.node_id,{owner_id:p.id,path:[]},new Set());
  return [...selected].sort();
}
export async function sha256(bytes:Uint8Array){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(bytes).buffer))].map(b=>b.toString(16).padStart(2,'0')).join('');}
export async function exportDesign(d:Draft){
  const problem=validateDraft(d);if(problem)throw Error(problem);
  for(const f of data.files){const bytes=Uint8Array.from(atob(f.original_base64),c=>c.charCodeAt(0));if(bytes.length!==f.bytes||await sha256(bytes)!==f.sha256||new TextDecoder('utf-8',{fatal:true}).decode(bytes)!==f.text)throw Error('Public source integrity check failed.');}
  const retained=retainedNodes(d);
  const payload={kind:'skill_workbench_public_demo_design',schema_version:1,
    format_note:'Public browser example handoff. Not the desktop native import format. This is a design, not an executable Skill.',
    draft:d,sources:data.sources,original_files:data.files,source_catalog:units,source_contains:data.contains,
    selection:{retained_node_ids:retained,source_spans:units.filter(u=>retained.includes(u.id)).flatMap(u=>u.source_content)},
    checks:{structure:'validated',source_sha256:'verified_against_bundled_manifest',semantics:'not_validated',execution:'not_run',private_sources:'none'},
    execution_authority:{source_write:false,skill_generation:false,install:false,execution:false,publish:false},
    worker_requirements:[
      'Preserve the source rules, templates, conditions, exceptions and quality gates. Removing a design position is not a waiver.',
      'Validate inputs, outputs, dependencies and intended handoffs against complete source texts. Containment and headings are not execution order.',
      'Map each applicable rule to its new location, execution, independent review, positive test, negative test and evidence.',
      'Report conflicts and obtain a specific human decision before altering a formal standard.',
      'This design grants no authority to modify, execute, install or publish a Skill. Request implementation authorization separately.'
    ]};
  const raw=JSON.stringify(payload,null,2);const json=JSON.stringify({...payload,payload_sha256:await sha256(new TextEncoder().encode(raw)),hash_note:'SHA-256 of JSON.stringify(payload, null, 2), before payload_sha256 and hash_note.'},null,2)+'\n';
  if(new TextEncoder().encode(json).length>LIMIT)throw Error('Complete design exceeds 2 MiB; export stopped without truncation.');
  return json;
}
