"""An isolated design workbench. No Skill writes, installation or execution."""
from pathlib import Path
from contextlib import contextmanager, asynccontextmanager
import hashlib, json, math, secrets, sqlite3, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import PROJECT, RUNTIME as WORKBENCH_RUNTIME
RUNTIME=WORKBENCH_RUNTIME/'assembly'
CATALOG={'skill':{'id':'','name':'','version':'','root':''},'files':[],'nodes':[],'edges':[],'spans':[],'authorities':[]}
FACTS={};FILES={};CHILDREN={}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def stamp():return datetime.now(timezone.utc).isoformat()
def lossless_table(records):
    columns=list(records[0]) if records else []
    if any(set(r)!=set(columns) for r in records):raise ValueError('记录字段不一致，禁止丢失字段')
    return {'encoding':'column_table_v1','columns':columns,'rows':[[r[key] for key in columns] for r in records],'note':'每行按columns还原原记录，字段与值完整保留'}

def closure(nid):
    if nid not in FACTS:raise ValueError('未知来源节点')
    result=set();pending=[nid]
    while pending:
        current=pending.pop()
        if current in result:continue
        result.add(current);pending.extend(CHILDREN[current])
    return result

def verify_snapshot():
    from .config import authorities
    authorities()

@contextmanager
def db():
    if not RUNTIME.resolve().is_relative_to(WORKBENCH_RUNTIME.resolve()):raise ValueError('数据写入位置不在独立目录内')
    (RUNTIME/'data').mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(RUNTIME/'data/assembly.sqlite3',timeout=15);conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL');conn.execute('PRAGMA busy_timeout=15000')
    try:yield conn;conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()

def init():
    verify_snapshot()
    with db() as conn:
        conn.executescript('CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY,revision INTEGER,payload TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,draft_id TEXT,action TEXT,revision INTEGER,payload_hash TEXT,created_at TEXT);')

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Instance(Strict):
    id:str=Field(pattern=r'^[a-zA-Z0-9-]{1,70}$')
    node_id:str
    x:float=Field(ge=-20000,le=20000,allow_inf_nan=False)
    y:float=Field(ge=-20000,le=20000,allow_inf_nan=False)
    excluded:list[str]=Field(default_factory=list,max_length=150)
    note:str=Field(default='',max_length=2000)
class Link(Strict):
    source:str;target:str
    label:str=Field(default='期望交接',max_length=100)
class Draft(Strict):
    id:str|None=Field(default=None,pattern=r'^[a-zA-Z0-9-]{1,70}$')
    revision:int=Field(default=0,ge=0)
    name:str=Field(min_length=1,max_length=100)
    goal:str=Field(default='',max_length=4000)
    instances:list[Instance]=Field(default_factory=list,max_length=60)
    links:list[Link]=Field(default_factory=list,max_length=120)

def check(draft):
    ids=[i.id for i in draft.instances]
    if len(set(ids))!=len(ids):raise ValueError('重复模块实例')
    for item in draft.instances:
        if item.node_id not in FACTS or FACTS[item.node_id]['kind'] not in ('theme','file','section'):raise ValueError('请选择已登记的模块候选范围')
        selected=closure(item.node_id)
        if item.node_id in item.excluded or any(n not in selected for n in item.excluded):raise ValueError('排除项必须属于本模块；移除整个模块请使用删除')
        if len(set(item.excluded))!=len(item.excluded):raise ValueError('重复排除项')
    graph={i:[] for i in ids};seen=set()
    for edge in draft.links:
        if edge.source not in graph or edge.target not in graph or edge.source==edge.target:raise ValueError('连线必须连接两个现有模块')
        pair=(edge.source,edge.target)
        if pair in seen:raise ValueError('重复连线')
        seen.add(pair);graph[edge.source].append(edge.target)
    visiting=set();done=set()
    def visit(n):
        if n in visiting:raise ValueError('流程存在循环，请明确循环条件后另行评估；本批不自动解释')
        if n in done:return
        visiting.add(n)
        for child in graph[n]:visit(child)
        visiting.remove(n);done.add(n)
    for nid in graph:visit(nid)

def selected_nodes(draft):
    selected=set()
    for item in draft.instances:
        retained=closure(item.node_id)
        for excluded in item.excluded:retained-=closure(excluded)
        selected|=retained
    return selected

def inspect(draft):
    check(draft);selected=selected_nodes(draft)
    refs=[{'source':e['source_id'],'target':e['target_id'],'source_title':FACTS[e['source_id']]['title'],'target_title':FACTS[e['target_id']]['title'],'evidence':json.loads(e['evidence']),'status':'文件名引用候选；是否必需须按原文核验'} for e in CATALOG['edges'] if e['kind']=='references' and e['source_id'] in selected and e['target_id'] not in selected]
    counts={nid:sum(i.node_id==nid for i in draft.instances) for nid in {i.node_id for i in draft.instances}}
    overlaps=[]
    for a,i in enumerate(draft.instances):
        left=closure(i.node_id)
        for j in draft.instances[a+1:]:
            if left&closure(j.node_id):overlaps.append({'source':i.id,'target':j.id,'status':'范围重叠；Worker需合并共享规则，不能重复执行'})
    return {'status':'组装设计草稿 · 复用待核验','selected_nodes':len(selected),'unselected_reference_candidates':refs,'overlaps':overlaps,'semantic_review':'待独立核验输入输出、触发条件、例外、权限、模板、执行及审核','generation_ready':False,'excluded_scope':'排除只表达新方案意图，不豁免任何正式规则','limits':{'instances':60,'links':120},'module_count':len(draft.instances)}

def save(draft):
    verify_snapshot();check(draft)
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT revision FROM drafts WHERE id=?',(draft.id,)).fetchone() if draft.id else None
        if draft.id and not row:raise ValueError('草稿不存在，禁止覆盖未知草稿')
        if row and row['revision']!=draft.revision:raise ValueError('草稿已有新版本，请重新打开，防止覆盖')
        if not draft.id and draft.revision!=0:raise ValueError('新草稿版本必须从零开始')
        result=draft.model_dump();result['id']=draft.id or str(uuid.uuid4());result['revision']=draft.revision+1
        now=stamp();raw=json.dumps(result,ensure_ascii=False)
        if row:conn.execute('UPDATE drafts SET revision=?,payload=?,updated_at=? WHERE id=?',(result['revision'],raw,now,result['id']))
        else:conn.execute('INSERT INTO drafts VALUES(?,?,?,?,?)',(result['id'],result['revision'],raw,now,now))
        conn.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),result['id'],'保存组装意图',result['revision'],sha(canonical(result)),now))
    return result

def load(did):
    with db() as conn:row=conn.execute('SELECT payload FROM drafts WHERE id=?',(did,)).fetchone()
    if not row:raise ValueError('草稿不存在')
    return Draft(**json.loads(row['payload']))

def package(did):
    raise ValueError('请先导入来源并选择模块，再导出设计包')

def catalog():
    return {'version':'','source_skill_id':'','source_name':'','snapshot':'','nodes':[],'contains':[]}

def source_text(nid):
    raise ValueError('未知来源节点')

def drafts():
    with db() as conn:
        return [{'id':r['id'],'revision':r['revision'],'name':json.loads(r['payload'])['name'],'updated_at':r['updated_at']}
                for r in conn.execute('SELECT * FROM drafts ORDER BY updated_at DESC LIMIT 100')]

def draft(did):
    return load(did).model_dump()
