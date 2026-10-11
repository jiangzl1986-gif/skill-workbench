"""Extend candidate design metadata. Reuse all legacy draft constraints; no Skill execution."""
import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
from . import module_library

class Adapter:
    def __getattr__(self, key):return getattr(self.legacy,key)

    def library(self):
        self.verify_snapshot()
        pools=[]
        for entry in self.entries:
            snap=entry['snapshot'];files={f['id']:f for f in snap['files']}
            catalog={'source_skill_id':snap['skill']['id'],'source_name':snap['skill']['name'],'version':snap['skill']['version'],
                     'snapshot':entry['record']['sha256'],
                     'nodes':[{'id':n['id'],'title':n['title'],'kind':n['kind'],'parent_id':n['parent_id'],
                               'path':files[n['file_id']]['path'] if n['file_id'] else None,
                               'count':len(self.legacy.closure(n['id']))-1}
                              for n in snap['nodes'] if n['kind'] in ('theme','file','section') and (not n['file_id'] or files[n['file_id']]['line_count']>0)],
                     'contains':[{'source':e['source_id'],'target':e['target_id']} for e in snap['edges'] if e['kind']=='contains']}
            pools.append(module_library.from_snapshot(snap,catalog))
        combined=module_library.combine(pools)
        historical=[];historical_edges=[]
        for entry in self.entries:
            record=entry['record']
            if not record.get('legacy_catalog_path'):continue
            old=json.loads(Path(record['legacy_catalog_path']).read_text('utf-8'))
            legacy_catalog={'source_skill_id':old['skill']['id'],'source_name':old['skill']['name'],'version':old['skill']['version'],
                            'snapshot':record['legacy_catalog_sha256'],
                            'nodes':[{'id':n['id'],'title':n['title'],'kind':n['kind'],'parent_id':n['parent_id'],'path':None,
                                      'count':len(self.legacy.closure(n['id']))-1} for n in old['nodes'] if n['kind']=='theme']}
            projected=module_library.from_snapshot(old,legacy_catalog)
            current=[n for n in combined['nodes'] if n['source_skill_id']==old['skill']['id'] and n['kind']=='theme']
            for node in projected['nodes']:
                file_ids={f['file_id'] for f in node['source_content']}
                labels=[n['title'] for n in current if file_ids&{f['file_id'] for f in n['source_content']}]
                node['title']='旧草稿范围 · '+('、'.join(labels[:3]) if labels else '配套文件')
                node['reuse_status']='已有草稿的原选择范围；保持原文件与节点，不自动改用新分类'
                historical.append(node)
            historical_edges.extend({'source':e['source_id'],'target':e['target_id']} for e in entry['snapshot']['legacy_navigation_edges'])
        combined['historical_nodes']=historical
        combined['historical_contains']=historical_edges
        return combined

    def source_text(self,nid):
        if nid in self.old_ids:return self.legacy.source_text(nid)
        self.verify_snapshot()
        for entry in self.entries:
            snap=entry['snapshot'];node=next((n for n in snap['nodes'] if n['id']==nid),None)
            if not node:continue
            if not node['file_id']:raise ValueError('请选择来源文件或规则分类查看原文')
            file=next(f for f in snap['files'] if f['id']==node['file_id'])
            raw=(entry['folder']/file['path']).read_bytes()
            try:text=raw.decode('utf-8-sig')
            except UnicodeDecodeError:raise ValueError('二进制附件仅登记完整文件元数据，尚未内容审核')
            return {'title':node['title'],'path':file['path'],'sha256':file['sha256'],'text':text,
                    'spans':[s for s in snap['spans'] if s['node_id']==nid],'version':snap['skill']['version'],
                    'review':'完整冻结原文；目录/范围候选，独立复用待核验'}
        raise ValueError('未知来源节点')

    def package(self,did):
        self.verify_snapshot();draft=self.legacy.load(did)
        if all(i.node_id in self.old_ids for i in draft.instances):return self.legacy.package(did)
        if not draft.goal.strip() or not draft.instances:raise ValueError('请填写目标并选择模块')
        report=self.legacy.inspect(draft);selected=self.legacy.selected_nodes(draft)
        used={self.facts[i.node_id]['skill_id'] for i in draft.instances}
        sources=[];original_files=[];nodes=[];spans=[];standards=[];unexpanded=[]
        candidates=self.entries
        for entry in candidates:
            snap=entry['snapshot'];sid=snap['skill']['id']
            if sid not in used:continue
            scope=snap.get('source_scope')
            sources.append({'id':sid,'name':snap['skill']['name'],'version':snap['skill']['version'],'formal_root':snap['skill']['root'],
                            'snapshot_sha256':entry['record']['sha256'],
                            'full_manifest':snap.get('full_manifest',snap.get('inventory')),
                            'indexed_manifest':[{k:f[k] for k in ['path','sha256','bytes']} for f in snap['files']],
                            'source_scope':scope})
            for f in snap['files']:
                raw=(entry['folder']/f['path']).read_bytes()
                file={'source_skill_id':sid,'path':f['path'],'sha256':f['sha256'],'bytes':f['bytes'],
                      'encoding':'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8',
                      'role':'完整来源参考；未选范围不自动生效'}
                try:file['text']=raw.decode('utf-8-sig')
                except UnicodeDecodeError:file['binary_base64']=base64.b64encode(raw).decode('ascii');file['encoding']='原二进制完整字节，仅参考附件'
                original_files.append(file)
            nodes.extend(n for n in snap['nodes']+snap.get('legacy_navigation_nodes',[]) if n['id'] in selected)
            spans.extend(s for s in snap['spans'] if s['node_id'] in selected)
            standards.extend(snap['authorities'])
            unexpanded.extend({'source_skill_id':sid,**r} for r in snap.get('unresolved',[]))
        permission={'source_write':False,'skill_generation':False,'install':False,
                    'meaning':'仅供Worker评估的候选设计；尚未核验接口、依赖或生产语义，不产生执行授权'}
        requirements=['完整继承每个来源的规则、模板、前置、例外与质量门槛；冲突须报用户决定',
                      '每条适用规则建立原规则→新位置→实际执行→独立审核→正向测试→反向测试→凭证',
                      '草稿排除不豁免正式标准；视图未展开的依赖仍在原根，需核验后才可具体候选生成',
                      '未经可信人类准确方案批准，不移动、拆解、覆盖或执行任何现有Skill，也不安装新Skill',
                      '先完成一个可独立验收模块；结构/程序通过不替代语义和实际运行验收']
        full={'kind':'skill_assembly_design','schema_version':2,'draft':draft.model_dump(),'sources':sources,
              'selection':{'retained_node_ids':sorted(selected),'nodes':nodes,'source_spans':spans},
              'original_files':original_files,'standards':standards,'unexpanded_reference_candidates':unexpanded,
              'checks':report,'execution_authority':permission,'worker_requirements':requirements}
        raw=self.legacy.canonical(full)
        outer={'kind':'skill_assembly_design','schema_version':2,'draft':draft.model_dump(),
               'sources':[{k:s[k] for k in ['id','name','version','formal_root','snapshot_sha256']} for s in sources],
               'encoding':'gzip+base64+canonical-json','bundle_sha256':self.legacy.sha(raw),
               'source_bundle':base64.b64encode(gzip.compress(raw,mtime=0)).decode('ascii'),
               'execution_authority':permission,'worker_requirements':requirements,
               'decode':'base64解码source_bundle，然后gzip解压为UTF-8完整JSON；先核对bundle_sha256；正文及标准不得截断'}
        outer['package_hash']=self.legacy.sha(self.legacy.canonical(outer))
        if len(self.legacy.canonical(outer))>2*1024*1024:raise ValueError('完整保真压缩包仍超过2MiB，请分成可独立核验的设计；不截断规则')
        return outer
