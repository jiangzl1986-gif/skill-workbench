"""The approved immutable-version boundary, retaining the original draft engine."""
import copy
import json
import threading
import base64
import gzip
from pathlib import Path
from . import core, version_sources as sources
from .multi_source_assembly import Adapter as OriginalAdapter


class Adapter(OriginalAdapter):
    def __init__(self,legacy):
        self.legacy=legacy
        self.base_snapshot=copy.deepcopy(legacy.CATALOG);self.old_ids=set(legacy.FACTS)
        self.entries=[];self.facts=dict(legacy.FACTS);self.loaded=set();self.guard=threading.RLock()
        legacy.verify_snapshot=self.verify_snapshot
        # Capture the V16-only projection before adding other versions' edges.
        self.base_catalog=legacy.catalog();self.ensure_loaded()
        legacy.init()

    def ensure_loaded(self):
        with self.guard:
            for rec in sources.records():
                if rec['version_id'] in self.loaded:continue
                snap=sources.verify_record(rec)
                if snap['skill']['id']==self.base_snapshot['skill']['id']:
                    self.loaded.add(rec['version_id']);continue
                entry={'record':rec,'snapshot':snap,'folder':Path(rec['files_root'])}
                additions=snap['nodes']+snap.get('legacy_navigation_nodes',[])
                if any(n['id'] in self.facts or n['skill_id']!=snap['skill']['id'] for n in additions):raise ValueError('版本来源节点冲突')
                known=set(self.facts)|{n['id'] for n in additions}
                edges=snap['edges']+snap.get('legacy_navigation_edges',[])
                if any(e['source_id'] not in known or e['target_id'] not in known for e in edges):raise ValueError('版本图引用缺失')
                for n in additions:
                    self.facts[n['id']]=n;self.legacy.FACTS[n['id']]=n;self.legacy.CHILDREN[n['id']]=[]
                for e in edges:
                    if e['kind']=='contains':self.legacy.CHILDREN[e['source_id']].append(e['target_id'])
                self.legacy.CATALOG['edges'].extend(edges)
                self.entries.append(entry);self.loaded.add(rec['version_id'])

    def verify_snapshot(self):
        with self.guard:
            sources.authorities()
            for rec in sources.records():
                sources.verify_record(rec)
                if rec.get('legacy_catalog_path') and core.digest(Path(rec['legacy_catalog_path']).read_bytes())!=rec['legacy_catalog_sha256']:
                    raise ValueError('旧草稿原范围快照漂移')
            # Live source drift is observed separately, never silently adopted or represented as current bytes.

    def library(self):
        self.ensure_loaded();combined=super().library();meta={r['skill_id']:r for r in sources.records()}
        with core.connect() as db:
            observations={r['family_id']:r['status'] for r in db.execute('SELECT * FROM skm_source_observations')}
        for source in combined['sources']:
            rec=meta[source['id']]
            source.update({k:rec[k] for k in ('family_id','version_id','version_role','original_root')})
            source['source_status']='历史冻结版本；原目录核对以当前登记版为准' if rec['version_role']=='历史版本' else observations.get(rec['family_id'],'尚未核对原目录')
        for node in combined['nodes']:
            node['version_role']=meta[node['source_skill_id']]['version_role']
        fixed={'blueprints':[]}
        combined['blueprints']=fixed['blueprints']+[json.loads(Path(r['blueprint_path']).read_bytes()) for r in meta.values() if r.get('blueprint_path')]
        combined['source_revision']=core.digest([{k:r[k] for k in ('version_id','version_role','sha256')} for r in meta.values()])
        return combined

    def package(self,did):
        self.ensure_loaded();outer=super().package(did)
        used={self.facts[i.node_id]['skill_id'] for i in self.legacy.load(did).instances}
        provenance=[{k:r[k] for k in ('skill_id','family_id','version_id','version','version_role','original_root','sha256')}
                    for r in sources.records() if r['skill_id'] in used]
        with core.connect() as db:
            observations={r['family_id']:r['status'] for r in db.execute('SELECT * FROM skm_source_observations')}
        for rec in provenance:
            rec['source_status']='历史冻结版本；原目录核对以当前登记版为准' if rec['version_role']=='历史版本' else observations.get(rec['family_id'],'尚未核对原目录')
            rec['read_basis']='准确确认的不可变版本快照；当前登记不代表原目录未变化'
        # Add version facts without removing original payload, rules, limits or permissions.
        if outer.get('source_bundle'):
            body=json.loads(gzip.decompress(base64.b64decode(outer['source_bundle'])))
            body['version_provenance']=provenance
            body['standards'].extend(sources.authorities())
            raw=self.legacy.canonical(body);outer['source_bundle']=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
            outer['bundle_sha256']=core.digest(raw)
        outer['version_provenance']=provenance
        outer.pop('package_hash',None);outer['package_hash']=core.digest(outer)
        if len(core.canonical(outer))>core.MAX_BYTES:raise ValueError('完整版本设计包超过2MiB，请制定完整分批方案；未截断')
        return outer
