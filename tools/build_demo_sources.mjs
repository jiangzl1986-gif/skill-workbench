import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {resolve, dirname} from 'node:path';

// Explicit allowlist: never scan a user's Skill directories for the public demo.
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const paths=['notes-to-outline/SKILL.md','notes-to-outline/modules/collect/SKILL.md','notes-to-outline/modules/outline/SKILL.md','evidence-review/SKILL.md','evidence-review/modules/evidence/SKILL.md'];
const sha=b=>createHash('sha256').update(b).digest('hex');
const names={'notes-to-outline':'笔记转大纲','evidence-review':'证据复核'};
const files=paths.map(path=>{const bytes=readFileSync(resolve(root,'examples',path));const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);return {id:path,source_skill_id:path.split('/')[0],path,sha256:sha(bytes),bytes:bytes.length,encoding:'utf-8',original_base64:bytes.toString('base64'),text,line_count:text.split('\n').length};});
const units=[];
for(const file of files){
  const lines=file.text.split('\n');
  const title=lines.find(l=>l.startsWith('# '))?.slice(2).trim()||file.path;
  const parent=file.path.endsWith('/SKILL.md')&&file.path.split('/').length>2?file.source_skill_id+'/SKILL.md':null;
  const common={source_skill_id:file.source_skill_id,source_name:names[file.source_skill_id],source_version:'1.0',source_snapshot:sha(Buffer.from(files.filter(f=>f.source_skill_id===file.source_skill_id).map(f=>f.path+':'+f.sha256).join('\n'))),source_groups:[],reuse_status:'candidate_requires_review'};
  const make=(id,title,kind,parent_id,start,end)=>({id,title,kind,parent_id,path:file.path,count:0,...common,source_content:[{file_id:file.id,path:file.path,title,sha256:file.sha256,ranges:[{start_line:start,end_line:end}]}]});
  units.push(make(file.id,title,'file',parent,1,lines.length));
  const headings=lines.map((l,i)=>({line:i+1,title:l.startsWith('## ')?l.slice(3).trim():null})).filter(h=>h.title);
  headings.forEach((h,i)=>units.push(make(file.id+'#L'+h.line,h.title,'section',file.id,h.line,(headings[i+1]?.line||lines.length+1)-1)));
}
const ids=new Map(units.map(u=>[u.id,'n-'+sha(Buffer.from(u.id)).slice(0,24)]));
for(const u of units){u.id=ids.get(u.id);u.parent_id=u.parent_id?ids.get(u.parent_id):null;}
for(const u of units)u.count=units.filter(n=>n.parent_id===u.id).length;
const result={schema_version:1,license:'MIT (only these independently authored public examples)',files,units,contains:units.filter(u=>u.parent_id).map(u=>({source:u.parent_id,target:u.id})),sources:Object.entries(names).map(([id,name])=>({id,name,version:'1.0',snapshot_sha256:units.find(u=>u.source_skill_id===id).source_snapshot,root:'examples/'+id}))};
const target=resolve(root,'apps/web/src/demo/sources.json');mkdirSync(dirname(target),{recursive:true});writeFileSync(target,JSON.stringify(result,null,2)+'\n');
console.log(`Public demo: ${files.length} allowlisted source files, ${units.length} inspectable units.`);
