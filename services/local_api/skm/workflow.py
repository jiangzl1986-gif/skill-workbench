"""Frozen analysis packages and exact approvals. No source-write or execution API."""
from __future__ import annotations
import json
import re
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from . import core

router=APIRouter(prefix='/api')


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Opinion(Strict):
    node_id:str
    problem:str=Field(min_length=1,max_length=10000)
    expected:str=Field(min_length=1,max_length=10000)
    example:str=Field(default='',max_length=10000)


class Change(Strict):
    relative_path:str
    before_sha256:str=Field(pattern=r'^[a-fA-F0-9]{64}$')
    expected_after_sha256:str=Field(pattern=r'^[a-fA-F0-9]{64}$')
    unified_diff:str=Field(min_length=1,max_length=1000000)


class Tests(Strict):
    positive:list[str]=Field(min_length=1)
    negative:list[str]=Field(min_length=1)
    independent_audit:str=Field(min_length=1)


class Trace(Strict):
    source_node_id:str
    original_rule:str=Field(min_length=1)
    new_location:str=Field(min_length=1)
    execution_location:str=Field(min_length=1)
    audit_location:str=Field(min_length=1)
    positive_test:str=Field(min_length=1)
    negative_test:str=Field(min_length=1)
    receipt_plan:str=Field(min_length=1)


class Proposal(Strict):
    kind:Literal['change_proposal']='change_proposal'
    request_id:str
    package_hash:str=Field(pattern=r'^[a-fA-F0-9]{64}$')
    base_manifest_hash:str=Field(pattern=r'^[a-fA-F0-9]{64}$')
    analysis:str=Field(min_length=1)
    changes:list[Change]=Field(min_length=1,max_length=40)
    impact:str=Field(min_length=1)
    tests:Tests
    risks:str=Field(min_length=1)
    rollback:str=Field(min_length=1)
    rule_fidelity:list[Trace]=Field(min_length=1)


class Decision(Strict):
    proposal_hash:str=Field(pattern=r'^[a-fA-F0-9]{64}$')
    decision:Literal['approve','reject','revise']
    reason:str=Field(default='',max_length=10000)


class Receipt(Strict):
    kind:Literal['execution_receipt']='execution_receipt'
    proposal_id:str
    proposal_hash:str
    reported_tests:Literal['passed','failed','not_run']
    report:str=Field(min_length=1)
    evidence:list[str]=Field(min_length=1)
    recovery:str=Field(min_length=1)


class Reanalyse(Strict):
    reason:str=Field(min_length=1,max_length=10000)


def get_request(db,rid):
    row=db.execute('SELECT * FROM change_requests WHERE id=?',(rid,)).fetchone()
    if not row:raise ValueError('维护意见不存在')
    result=dict(row)
    result['snapshot']=json.loads(row['snapshot'])
    return result


def authority_snapshot():
    from .config import authorities
    return authorities()


def freshness(db,request):
    snap=request['snapshot']
    skill=db.execute('SELECT * FROM skills WHERE id=?',(request['skill_id'],)).fetchone()
    try:
        if not snap.get('authorities'):
            raise ValueError('旧任务未冻结完整权威标准；请重新分析后审批')
        current=core.source_manifest(skill, db, verify_view=False)
        if current!=snap['manifest']:
            raise ValueError('源或依赖已变化；必须重新分析并批准新方案')
        for authority in snap.get('authorities',[]):
            if core.digest(__import__('pathlib').Path(authority['path']).read_bytes())!=authority['sha256']:
                raise ValueError('权威标准/模板/授权边界已变化；必须重新分析并批准')
        active=db.execute('SELECT active FROM nodes WHERE id=?',(request['node_id'],)).fetchone()
        if not active or not active[0]:raise ValueError('原节点已失效，禁止套用旧方案')
    except (OSError,ValueError) as exc:
        db.execute('UPDATE change_requests SET state=?,updated_at=? WHERE id=?',('需重新分析',core.now(),request['id']))
        db.execute("UPDATE change_proposals SET state='基线过期' WHERE request_id=? AND state IN ('待审批','已批准')",(request['id'],))
        core.audit(db,'基线复核停止',request['id'],{'reason':str(exc)},'本机索引服务')
        db.commit()
        raise ValueError(str(exc))


def freeze(db,nid):
    detail=core.current_node(nid,db)
    skill=db.execute('SELECT * FROM skills WHERE id=?',(detail['skill_id'],)).fetchone()
    manifest=core.source_manifest(skill, db)
    scope=core.source_scope(skill, db)
    indexed={r['path']:r['sha256'] for r in db.execute('SELECT path,sha256 FROM source_files WHERE skill_id=? AND deleted=0',(detail['skill_id'],))}
    expected_index={f['path']:f['sha256'] for f in scope['indexed_files']} if scope else manifest
    if expected_index!=indexed:raise ValueError('源与地图展示范围不一致，请先刷新；正式源漂移时先确认新基线')
    related={nid};queue=[nid]
    for current in queue:
        for row in db.execute('SELECT id FROM nodes WHERE parent_id=? AND active=1',(current,)):
            if row['id'] not in related:related.add(row['id']);queue.append(row['id'])
    references=[]
    files=set()
    for node_id in related:
        row=db.execute('SELECT file_id FROM nodes WHERE id=?',(node_id,)).fetchone()
        if row['file_id']:files.add(row['file_id'])
        for edge in db.execute("SELECT * FROM edges WHERE (source_id=? OR target_id=?) AND kind!='contains'",(node_id,node_id)):
            e=dict(edge);e['evidence']=json.loads(e['evidence']);references.append(e)
            target=db.execute('SELECT file_id FROM nodes WHERE id=?',(edge['target_id'],)).fetchone()
            if target and target['file_id']:files.add(target['file_id'])
    sources=[]
    for fid in sorted(files):
        row=db.execute('SELECT * FROM source_files WHERE id=?',(fid,)).fetchone()
        sources.append({'file_id':fid,'relative_path':row['path'],'sha256':row['sha256'],'encoding':row['encoding'],
                        'start_line':1,'end_line':row['line_count'],'excerpt':row['text'],'excerpt_kind':'完整文件上下文'})
    snapshot={'skill_id':detail['skill_id'],'skill_name':skill['name'],'version':skill['version'],'source_root':skill['root'],
              'revision':skill['revision'],'node_id':nid,'node_title':detail['title'],'node_kind':detail['kind'],
              'breadcrumb':core.breadcrumbs(db,nid),'source_spans':detail['spans'],'sources':sources,
              'manifest':manifest,'manifest_hash':core.digest(manifest),'known_references':references,
              'related_node_ids':sorted(related),'unresolved_references':detail['unresolved'],
              'semantic_review':'未独立审查；Worker须回读源规则和所有前提/例外，引用不是执行依赖',
              'authorities':authority_snapshot(),
              'source_scope':scope,
              'frozen_at':core.now()}
    if len(core.canonical(snapshot))>2*1024*1024:raise ValueError('完整上下文超过本批上限2MiB，请选更具体节点；不截断原文')
    return snapshot


@router.post('/requests')
def create_request(body:Opinion):
    with core.GUARD,core.connect() as db:
        snapshot=freeze(db,body.node_id)
        rid=core.ident();created=core.now()
        package={'id':rid,'problem':body.problem,'expected':body.expected,'example':body.example,'snapshot':snapshot}
        ph=core.digest(package)
        db.execute('INSERT INTO change_requests VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (rid,snapshot['skill_id'],body.node_id,body.problem,body.expected,body.example,json.dumps(snapshot,ensure_ascii=False),ph,'待Worker分析',created,created))
        core.audit(db,'保存节点维护意见',rid,{'node_id':body.node_id,'version':snapshot['version'],'package_hash':ph})
        return {'id':rid,'state':'待Worker分析','package_hash':ph}


@router.get('/requests')
def requests():
    with core.connect() as db:
        return [dict(r) for r in db.execute('SELECT r.id,r.problem,r.expected,r.state,r.created_at,n.title node_title,s.version FROM change_requests r JOIN nodes n ON n.id=r.node_id JOIN skills s ON s.id=r.skill_id ORDER BY r.created_at DESC')]


@router.get('/requests/{rid}')
def request_detail(rid:str):
    with core.connect() as db:
        result=get_request(db,rid)
        result['proposals']=[dict(r)|{'content':json.loads(r['content'])} for r in db.execute('SELECT * FROM change_proposals WHERE request_id=? ORDER BY version DESC',(rid,))]
        result['approvals']=[dict(r) for r in db.execute('SELECT a.* FROM approvals a JOIN change_proposals p ON p.id=a.proposal_id WHERE p.request_id=? ORDER BY a.created_at DESC',(rid,))]
        result['receipts']=[dict(r)|{'content':json.loads(r['content'])} for r in db.execute('SELECT r.* FROM receipts r JOIN change_proposals p ON p.id=r.proposal_id WHERE p.request_id=?',(rid,))]
        return result


@router.get('/requests/{rid}/package')
def package(rid:str):
    with core.GUARD,core.connect() as db:
        req=get_request(db,rid);freshness(db,req)
        payload={'kind':'analysis_task','schema_version':1,'request_id':rid,'package_hash':req['package_hash'],
                 'problem':req['problem'],'expected':req['expected'],'example':req['example'],'snapshot':req['snapshot'],
                 'worker_scope':'只读分析；不得修改源Skill、执行生产脚本/API。完整继承冻结的用户协议、规则、模板和门槛；目标调整或具体差异审批不自动豁免正式标准。先给出具体差异、影响、正反测试、独立审核和回滚；用户只批准准确方案。',
                 'proposal_contract':Proposal.model_json_schema(),'receipt_contract':Receipt.model_json_schema()}
        core.audit(db,'导出只读Worker分析包',rid,{'package_hash':req['package_hash']})
        return payload


@router.post('/requests/{rid}/reanalyse')
def reanalyse(rid:str,body:Reanalyse):
    with core.GUARD,core.connect() as db:
        req=get_request(db,rid)
        # Do not silently relocate an ambiguous/deleted node or accept stale pinned V16.
        snapshot=freeze(db,req['node_id']);new_id=core.ident();created=core.now()
        ph=core.digest({'id':new_id,'problem':req['problem'],'expected':req['expected'],'example':req['example'],'snapshot':snapshot})
        db.execute('INSERT INTO change_requests VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (new_id,req['skill_id'],req['node_id'],req['problem'],req['expected'],req['example'],json.dumps(snapshot,ensure_ascii=False),ph,'待Worker重新分析',created,created))
        db.execute('UPDATE change_requests SET state=?,updated_at=? WHERE id=?',('已转新冻结任务 / 旧方案停用',created,rid))
        db.execute("UPDATE change_proposals SET state='已替代 / 旧批准不可重用' WHERE request_id=? AND state IN ('待审批','已批准')",(rid,))
        core.audit(db,'重新冻结维护任务',new_id,{'previous_request':rid,'reason':body.reason,'package_hash':ph})
        return {'id':new_id,'message':'当前源已重新冻结，旧方案和旧批准停用；请重新交Worker分析。'}


def patched_bytes(raw,path,diff):
    """Strict unified diff, no fuzzy context, no source mutation."""
    text=raw.decode('utf-8-sig')
    original=text.splitlines(keepends=True)
    lines=diff.splitlines(keepends=True)
    if len(lines)<3 or not lines[0].startswith('--- ') or not lines[1].startswith('+++ '):raise ValueError('必须提供完整统一差异，含文件头与hunk')
    for line,prefix in ((lines[0],'a/'),(lines[1],'b/')):
        header=line[4:].strip().split('\t')[0]
        if header.startswith(prefix):header=header[2:]
        if header!=path:raise ValueError('差异文件头与批准路径不一致')
    out=[];cursor=0;i=2;ending='\r\n' if '\r\n' in text else '\n';hunks=0
    while i<len(lines):
        match=re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',lines[i])
        if not match:raise ValueError('差异hunk格式不合法')
        start=int(match[1]);old_count=int(match[2] or 1);new_start=int(match[3]);new_count=int(match[4] or 1)
        target=start-1 if old_count else start
        if target<cursor or target>len(original):raise ValueError('差异行号错位或重叠')
        out.extend(original[cursor:target]);cursor=target;i+=1;old_seen=new_seen=0;hunks+=1
        if new_start!=(len(out)+1 if new_count else len(out)):raise ValueError('新文件hunk行号不一致')
        while i<len(lines) and not lines[i].startswith('@@ '):
            line=lines[i];i+=1
            if line.startswith('\\ No newline at end of file'):
                if out:out[-1]=out[-1].rstrip('\r\n')
                continue
            if not line or line[0] not in ' +-':raise ValueError('差异内容格式不合法')
            operation=line[0];content=line[1:].rstrip('\r\n')
            if operation in ' -':
                if cursor>=len(original) or original[cursor].rstrip('\r\n')!=content:raise ValueError('差异上下文与冻结原文不一致')
                if operation==' ':out.append(original[cursor])
                cursor+=1;old_seen+=1
            if operation=='+':out.append(content+ending)
            if operation in ' +':new_seen+=1
        if (old_seen,new_seen)!=(old_count,new_count):raise ValueError('hunk行数与差异内容不一致')
    if not hunks:raise ValueError('方案没有实际hunk')
    out.extend(original[cursor:])
    return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+''.join(out).encode('utf-8')


@router.post('/requests/{rid}/proposals')
def import_proposal(rid:str,body:Proposal):
    with core.GUARD,core.connect() as db:
        req=get_request(db,rid);freshness(db,req);snap=req['snapshot']
        if body.request_id!=rid or body.package_hash!=req['package_hash'] or body.base_manifest_hash!=snap['manifest_hash']:raise ValueError('方案不对应这份冻结任务包')
        paths=[]
        for change in body.changes:
            if change.relative_path in paths:raise ValueError('同一文件差异重复，需合并为一个准确方案')
            paths.append(change.relative_path)
            if snap['manifest'].get(change.relative_path)!=change.before_sha256.lower():raise ValueError('修改文件不在冻结源或基线hash不一致')
            raw=core.safe_file(snap['source_root'],change.relative_path).read_bytes()
            after=patched_bytes(raw,change.relative_path,change.unified_diff)
            if after==raw:raise ValueError('差异没有产生实际变化')
            if core.digest(after)!=change.expected_after_sha256.lower():raise ValueError('候选差异生成的内容与expected_after_sha256不一致')
        for trace in body.rule_fidelity:
            node=core.current_node(trace.source_node_id,db)
            if node['skill_id']!=req['skill_id']:raise ValueError('规则映射跨到另一个Skill')
            original=''.join(s['text'] for s in node['spans'])
            if trace.original_rule not in original:raise ValueError('原规则映射无法在真实源中定位')
        if not all(any(path in trace.new_location for trace in body.rule_fidelity) for path in paths):raise ValueError('每个修改文件都必须有规则保真映射')
        payload=body.model_dump();ph=core.digest(payload);pid=core.ident()
        version=db.execute('SELECT coalesce(max(version),0)+1 FROM change_proposals WHERE request_id=?',(rid,)).fetchone()[0]
        db.execute("UPDATE change_proposals SET state='已替代 / 旧批准不可重用' WHERE request_id=? AND state IN ('待审批','已批准')",(rid,))
        db.execute('INSERT INTO change_proposals VALUES(?,?,?,?,?,?,?)',(pid,rid,version,json.dumps(payload,ensure_ascii=False),ph,'待审批',core.now()))
        db.execute('UPDATE change_requests SET state=?,updated_at=? WHERE id=?',('待审批具体方案',core.now(),rid))
        core.audit(db,'导入具体修改方案',pid,{'request_id':rid,'proposal_hash':ph,'version':version,'files':paths})
        return {'id':pid,'proposal_hash':ph,'message':'方案已导入，完整差异与基线核对通过；等待用户审批。'}


def proposal(db,pid):
    row=db.execute('SELECT * FROM change_proposals WHERE id=?',(pid,)).fetchone()
    if not row:raise ValueError('方案不存在')
    return dict(row)|{'content':json.loads(row['content'])}


@router.post('/proposals/{pid}/decision')
def decide(pid:str,body:Decision):
    with core.GUARD,core.connect() as db:
        p=proposal(db,pid);req=get_request(db,p['request_id']);freshness(db,req)
        if p['state']!='待审批' or p['proposal_hash']!=body.proposal_hash:raise ValueError('审批必须对应当前未审批方案的准确hash；旧批准不能重放')
        if body.decision in ('reject','revise') and not body.reason.strip():raise ValueError('请写明驳回或修订理由')
        scope={'source_root':req['snapshot']['source_root'],'version':req['snapshot']['version'],'manifest_hash':req['snapshot']['manifest_hash'],
               'files':[c['relative_path'] for c in p['content']['changes']],'base_hashes':req['snapshot']['manifest'],
               'expected_after_hashes':{c['relative_path']:c['expected_after_sha256'] for c in p['content']['changes']},
               'proposal_hash':p['proposal_hash'],'execution_mode':'外部Worker准确方案交接；网页无执行/生产写入接口'}
        state={'approve':'已批准','reject':'已驳回','revise':'需修订'}[body.decision]
        db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?)',(core.ident(),pid,p['proposal_hash'],body.decision,body.reason,'本机用户会话操作',json.dumps(scope,ensure_ascii=False),core.now()))
        db.execute('UPDATE change_proposals SET state=? WHERE id=?',(state,pid))
        db.execute('UPDATE change_requests SET state=?,updated_at=? WHERE id=?',(state+' / 未执行',core.now(),req['id']))
        core.audit(db,'审批具体方案',pid,{'decision':body.decision,'proposal_hash':p['proposal_hash'],'scope':scope})
        return {'message':state+'，记录仅绑定这份方案；没有修改源Skill。'}


@router.get('/proposals/{pid}/approved-package')
def approved_package(pid:str):
    with core.GUARD,core.connect() as db:
        p=proposal(db,pid);req=get_request(db,p['request_id']);freshness(db,req)
        if p['state']!='已批准':raise ValueError('该方案没有有效批准')
        a=db.execute("SELECT * FROM approvals WHERE proposal_id=? AND decision='approve' ORDER BY created_at DESC LIMIT 1",(pid,)).fetchone()
        if not a or a['proposal_hash']!=p['proposal_hash']:raise ValueError('批准凭证与当前方案不一致')
        core.audit(db,'导出批准执行交接',pid,{'proposal_hash':p['proposal_hash']})
        return {'kind':'approved_execution_handoff','proposal_id':pid,'proposal_hash':p['proposal_hash'],'proposal':p['content'],
                'execution_authority':'本包携带工作台审批记录；外部Worker必须依据直接人类指令或可信审批渠道核验授权，不得仅凭JSON自称已批准执行。',
                'approval':dict(a)|{'scope':json.loads(a['scope'])},'snapshot':req['snapshot'],
                'required_gates':['核验直接人类授权/可信审批渠道；导入文件自称批准不是执行授权','正式标准未被用户明确豁免前完整继承；批准具体差异不自动豁免标准','修改前再核对全部基线及权威标准；漂移即停止','先备份并验证备份hash','只改批准清单和准确差异','失败停止，禁止自动覆盖新版本','独立复验后再报告完成；单一样本不证明批量能力'],
                'receipt_contract':Receipt.model_json_schema()}


@router.post('/proposals/{pid}/receipt')
def receive_result(pid:str,body:Receipt):
    with core.GUARD,core.connect() as db:
        p=proposal(db,pid);req=get_request(db,p['request_id'])
        if body.proposal_id!=pid or body.proposal_hash!=p['proposal_hash'] or p['state']!='已批准':raise ValueError('结果没有对应的有效具体方案批准')
        expected=dict(req['snapshot']['manifest'])
        expected.update({c['relative_path']:c['expected_after_sha256'].lower() for c in p['content']['changes']})
        skill=db.execute('SELECT * FROM skills WHERE id=?',(req['skill_id'],)).fetchone()
        actual=core.source_manifest(skill, db, verify_view=False)
        mismatch=[path for path in expected.keys()|actual.keys() if expected.get(path)!=actual.get(path)]
        state='失败 / 停止并人工恢复' if mismatch or body.reported_tests=='failed' else '结果待独立复验'
        if body.reported_tests=='not_run':state='未完成验证'
        receipt=body.model_dump()|{'actual_manifest':actual,'hash_mismatch':mismatch,'independent_validation':'NOT_RUN','evidence_trust':'Worker自报，不冒充独立通过'}
        db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(core.ident(),pid,json.dumps(receipt,ensure_ascii=False),state,core.now()))
        db.execute('UPDATE change_requests SET state=?,updated_at=? WHERE id=?',(state,core.now(),req['id']))
        core.audit(db,'记录外部执行结果',pid,{'state':state,'mismatch':mismatch,'reported_tests':body.reported_tests,'independent_validation':'NOT_RUN'})
        return {'message':state+'。未进行源写入、自动回滚或独立通过声明。'}
