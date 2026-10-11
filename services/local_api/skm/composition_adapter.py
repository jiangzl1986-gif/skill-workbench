"""Add bounded internal design positions; keep every legacy draft path unchanged."""
import base64,copy,gzip,json,uuid
from .composition_model import Composition,Structure

class Adapter:
    def __init__(self,base):
        self.base=base;self.legacy=base.legacy
        class ComposedDraft(self.legacy.Draft):
            composition:Composition|None=None
        self.Draft=ComposedDraft
        pool=base.library()
        self.eligible={n['id'] for n in pool['nodes']+pool.get('historical_nodes',[])}

    def __getattr__(self,name):return getattr(self.base,name)

    def ensure_loaded(self):
        self.base.ensure_loaded()
        for snap in [self.base.base_snapshot]+[e['snapshot'] for e in self.base.entries]:
            files={f['id']:f for f in snap['files']}
            self.eligible.update(n['id'] for n in snap['nodes'] if n['kind'] in ('theme','file','section') and (not n['file_id'] or files[n['file_id']]['line_count']>0))
            self.eligible.update(n['id'] for n in snap.get('legacy_navigation_nodes',[]) if n['kind']=='theme')

    def library(self):
        pool=self.base.library()
        self.eligible={n['id'] for n in pool['nodes']+pool.get('historical_nodes',[])}
        return pool

    def flat(self,draft):return self.legacy.Draft(**draft.model_dump(exclude={'composition'}))

    def structure(self,draft):
        self.legacy.check(self.flat(draft))
        return Structure(draft,self.base.facts,self.legacy.CHILDREN,self.eligible,self.legacy.closure)

    def inspect(self,draft):
        if draft.composition is None:return self.base.inspect(self.flat(draft))
        shape=self.structure(draft);report=self.base.inspect(self.flat(draft));selected=shape.selected()
        report.update(selected_nodes=len(selected),module_count=len(draft.instances)+shape.touched,
                      internal_scopes=len(shape.scopes),internal_design_positions=shape.touched,
                      design_links=shape.link_count,internal_review='内部连接和替换均为设计意图，生产接口与适用标准待独立核验')
        positions=[((i.id,()),i.node_id) for i in draft.instances]+[((o,p+(sid,)),n) for (o,p,sid),n in shape.active_positions().items()]
        closures={n:self.legacy.closure(n) for _,n in positions}
        for i,(left,ln) in enumerate(positions):
            for right,rn in positions[i+1:]:
                if not left[1] and not right[1]:continue
                if left[0]==right[0] and (left[1][:len(right[1])]==right[1] or right[1][:len(left[1])]==left[1]):continue
                if closures[ln]&closures[rn]:report['overlaps'].append({'source':list(left),'target':list(right),'status':'内部位置原范围重叠候选；Worker需逐位置核验共享规则，不能重复执行'})
        report['unselected_reference_candidates']=[{'source':e['source_id'],'target':e['target_id'],
            'source_title':self.base.facts[e['source_id']]['title'],'target_title':self.base.facts[e['target_id']]['title'],
            'evidence':json.loads(e['evidence']),'status':'文件名引用候选；是否必需须按原文核验'}
            for e in self.legacy.CATALOG['edges'] if e['kind']=='references' and e['source_id'] in selected and e['target_id'] not in selected]
        return report

    def draft(self,did):
        with self.legacy.db() as db:row=db.execute('SELECT payload FROM drafts WHERE id=?',(did,)).fetchone()
        if not row:raise ValueError('草稿不存在')
        return json.loads(row['payload'])

    def save(self,draft):
        if draft.composition is None:return self.base.save(self.flat(draft))
        self.base.verify_snapshot();self.inspect(draft)
        with self.legacy.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision FROM drafts WHERE id=?',(draft.id,)).fetchone() if draft.id else None
            if draft.id and not row:raise ValueError('草稿不存在，禁止覆盖未知草稿')
            if row and row['revision']!=draft.revision:raise ValueError('草稿已有新版本，请重新打开，防止覆盖')
            if not draft.id and draft.revision!=0:raise ValueError('新草稿版本必须从零开始')
            result=draft.model_dump();result.update(id=draft.id or str(uuid.uuid4()),revision=draft.revision+1)
            now=self.legacy.stamp();raw=json.dumps(result,ensure_ascii=False)
            if len(self.legacy.canonical(result))>2*1024*1024:raise ValueError('完整草稿超过2MiB；未截断')
            if row:db.execute('UPDATE drafts SET revision=?,payload=?,updated_at=? WHERE id=?',(result['revision'],raw,now,result['id']))
            else:db.execute('INSERT INTO drafts VALUES(?,?,?,?,?)',(result['id'],result['revision'],raw,now,now))
            db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),result['id'],'保存内部组装意图',result['revision'],self.legacy.sha(self.legacy.canonical(result)),now))
        return result

    def package(self,did):
        body=self.draft(did)
        if not body.get('composition'):return self.base.package(did)
        draft=self.Draft(**body);shape=self.structure(draft);selected=shape.selected();report=self.inspect(draft)
        flat=self.flat(draft)
        # Local facade supplies the evaluated design to the existing complete source packer.
        # No global loader, source graph, DB row or legacy module is patched.
        extras=[self.legacy.Instance(id='inner-'+str(i),node_id=n,x=0,y=0,excluded=[],note='内部设计位置')
                for i,n in enumerate(shape.active_positions().values())]
        flat=flat.model_copy(update={'instances':flat.instances+extras})
        legacy=self.legacy
        class Facade:
            def __getattr__(self,name):return getattr(legacy,name)
            def load(self,_):return flat
            def selected_nodes(self,_):return selected
            def inspect(self,_):return report
        packer=object.__new__(type(self.base));packer.__dict__.update(self.base.__dict__);packer.legacy=Facade();packer.old_ids=set()
        outer=packer.package(did)
        full=json.loads(gzip.decompress(base64.b64decode(outer['source_bundle'])))
        for obj in (outer,full):
            obj['schema_version']=3;obj['draft']=draft.model_dump()
            obj['composition_semantics']='冻结包含关系和新方案插槽分开；内部加入/替换/移除/连线只表示本草稿的当前位置意图，不豁免规则或授予生产执行权限'
            obj['worker_requirements'].append('按composition的父实例、路径、原项/当前项和连线逐位置核验；同源在其他位置仍保留，不能全局误删；内部连接需核验实际接口，不能仅凭图执行')
        raw=legacy.canonical(full);outer['source_bundle']=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
        outer['bundle_sha256']=legacy.sha(raw);outer.pop('package_hash',None);outer['package_hash']=legacy.sha(legacy.canonical(outer))
        if len(legacy.canonical(outer))>2*1024*1024:raise ValueError('完整内部设计包超过2MiB；未截断，请保真分批')
        return outer
