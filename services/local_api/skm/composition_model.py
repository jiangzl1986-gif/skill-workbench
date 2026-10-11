"""Workbench design positions, separate from immutable source containment."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class InnerLink(Strict):
    source:str
    target:str
    label:str=Field(default='期望交接',max_length=100)

class Slot(Strict):
    id:str=Field(pattern=r'^[a-zA-Z0-9-]{1,70}$')
    origin_id:str|None=None
    node_id:str|None
    x:float=Field(ge=-20000,le=20000,allow_inf_nan=False)
    y:float=Field(ge=-20000,le=20000,allow_inf_nan=False)
    note:str=Field(default='',max_length=2000)

class Scope(Strict):
    owner_id:str=Field(pattern=r'^[a-zA-Z0-9-]{1,70}$')
    path:list[str]=Field(default_factory=list,max_length=60)
    slots:list[Slot]=Field(default_factory=list,max_length=60)
    links:list[InnerLink]=Field(default_factory=list,max_length=120)

class Composition(Strict):
    schema_version:Literal[1]=1
    scopes:list[Scope]=Field(default_factory=list,max_length=60)

def key(owner,path):return (owner,tuple(path))
def original_id(nid):return 'o-'+nid

class Structure:
    def __init__(self,draft,facts,children,eligible,closure):
        self.draft=draft;self.facts=facts;self.children=children;self.eligible=eligible;self.closure=closure
        self.roots={i.id:i for i in draft.instances}
        self.scopes={}
        comp=draft.composition
        for scope in comp.scopes if comp else []:
            k=key(scope.owner_id,scope.path)
            if k in self.scopes:raise ValueError('重复内部画布')
            self.scopes[k]=scope
        self.touched=0;self.link_count=len(draft.links)
        self.validate()

    def at(self,owner,path):return self.scopes.get(key(owner,path))

    def choices(self,owner,path,nid):
        result={original_id(c):{'origin_id':c,'node_id':c} for c in self.children.get(nid,[]) if c in self.eligible}
        scope=self.at(owner,path)
        if scope:
            for slot in scope.slots:result[slot.id]={'origin_id':slot.origin_id,'node_id':slot.node_id}
        return result

    def resolve(self,owner,path):
        if owner not in self.roots:raise ValueError('内部画布父实例不存在')
        root=self.roots[owner];nid=root.node_id;visited={nid};prefix=[]
        blocked=set().union(*(self.closure(e) for e in root.excluded)) if root.excluded else set()
        for sid in path:
            item=self.choices(owner,prefix,nid).get(sid)
            if not item or not item['node_id']:raise ValueError('内部画布路径不存在或父项已移除')
            nid=item['node_id']
            if nid not in self.eligible:raise ValueError('内部路径来源不是已登记候选')
            if nid in blocked:raise ValueError('内部路径位于原草稿已排除范围')
            if nid in visited:raise ValueError('内部归属形成递归循环')
            visited.add(nid);prefix.append(sid)
        return nid

    def validate(self):
        # Parent scopes are checked first; a forged downstream scope cannot legalize a bad ancestor.
        for (owner,path),scope in sorted(self.scopes.items(),key=lambda e:len(e[0][1])):
            nid=self.resolve(owner,path);root=self.roots[owner]
            blocked=set().union(*(self.closure(e) for e in root.excluded)) if root.excluded else set()
            originals={c for c in self.children.get(nid,[]) if c in self.eligible}
            seen=set();origins=set()
            for slot in scope.slots:
                if slot.id in seen:raise ValueError('重复内部位置')
                seen.add(slot.id)
                if slot.origin_id is not None:
                    if slot.origin_id not in originals or slot.id!=original_id(slot.origin_id):raise ValueError('替换/移除位置不属于本层原始来源')
                    if slot.origin_id in origins:raise ValueError('重复原始子项位置')
                    origins.add(slot.origin_id)
                elif not slot.id.startswith('a-') or slot.node_id is None:raise ValueError('新增位置必须有准确候选和新增身份')
                if slot.node_id is not None and slot.node_id not in self.eligible:raise ValueError('内部位置来源不是已登记候选')
                if (slot.origin_id in blocked or slot.node_id in blocked) and slot.node_id is not None:raise ValueError('先恢复原草稿已排除范围再编辑此项')
            items=self.choices(owner,path,nid)
            active={sid for sid,item in items.items() if item['node_id'] is not None and item['origin_id'] not in blocked and item['node_id'] not in blocked}
            graph={sid:[] for sid in active};pairs=set();touched=set(seen)
            for link in scope.links:
                if link.source not in active or link.target not in active or link.source==link.target:raise ValueError('内部连线必须连接本层两个保留的子模块')
                pair=(link.source,link.target)
                if pair in pairs:raise ValueError('重复内部连线')
                pairs.add(pair);graph[link.source].append(link.target);touched.update(pair)
            self._dag(graph)
            self.touched+=len(touched);self.link_count+=len(scope.links)
        # Navigated positions also consume a design instance if descendants are edited.
        positions={(owner,tuple(path[:i]),path[i]) for owner,path in self.scopes for i in range(len(path))}
        authored={(owner,path,s.id) for (owner,path),sco in self.scopes.items() for s in sco.slots}
        authored|={(owner,path,sid) for (owner,path),sco in self.scopes.items() for e in sco.links for sid in (e.source,e.target)}
        self.touched=len(positions|authored)
        if len(self.roots)+self.touched>60:raise ValueError('外层与内部设计位置合计超过60实例；未截断，请保真分批')
        if self.link_count>120:raise ValueError('外层与内部设计连线合计超过120；未截断，请保真分批')

    @staticmethod
    def _dag(graph):
        visiting=set();done=set()
        def visit(n):
            if n in visiting:raise ValueError('内部流程存在循环；本批不自动解释循环条件')
            if n in done:return
            visiting.add(n)
            for child in graph[n]:visit(child)
            visiting.remove(n);done.add(n)
        for n in graph:visit(n)

    def selected(self):
        selected=set()
        for owner,root in self.roots.items():
            blocked=set()
            for excluded in root.excluded:blocked|=self.closure(excluded)
            paths=[path for o,path in self.scopes if o==owner]
            def walk(nid,path,ancestry):
                if nid in blocked:return set()
                if nid in ancestry:raise ValueError('来源或内部归属形成循环')
                if not any(p[:len(path)]==path for p in paths):return self.closure(nid)-blocked
                result={nid};choices=self.choices(owner,list(path),nid)
                for c in self.children.get(nid,[]):
                    if c in self.eligible:
                        sid=original_id(c);current=choices[sid]['node_id']
                        if current:result|=walk(current,path+(sid,),ancestry|{nid})
                    else:result|=self.closure(c)-blocked
                scope=self.at(owner,list(path))
                for slot in scope.slots if scope else []:
                    if slot.origin_id is None:result|=walk(slot.node_id,path+(slot.id,),ancestry|{nid})
                return result
            selected|=walk(root.node_id,(),set())
        return selected

    def active_positions(self):
        """All bounded authored/navigated active positions, for exact source packaging."""
        result={}
        addresses={(o,p,s.id) for (o,p),sco in self.scopes.items() for s in sco.slots}
        addresses|={(o,p,sid) for (o,p),sco in self.scopes.items() for e in sco.links for sid in (e.source,e.target)}
        addresses|={(o,tuple(p[:i]),p[i]) for o,p in self.scopes for i in range(len(p))}
        for o,p,sid in addresses:
            nid=self.resolve(o,p);item=self.choices(o,list(p),nid)[sid]
            if item['node_id'] is not None:result[(o,p,sid)]=item['node_id']
        return result
