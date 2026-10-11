"""Expected bytes and safety rules come from authored fixtures, never the indexer."""
from pathlib import Path
import base64, gzip, hashlib, io, json, zipfile
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from skm import core, version_sources as s, assembly_bridge as a, release_observations as releases

ROOT=Path(__file__).resolve().parents[1]

def adopt(root,version='',family=''):
    p=s.preview(root=str(root),version=version,family_id=family)
    r=s.confirm(p['preview_id'],p['preview_hash'],relation_confirmed=bool(family),missing_ack=True)
    return r

def pool():
    adopt(ROOT/'examples/notes-to-outline');adopt(ROOT/'examples/evidence-review')
    return a.catalog()

def draft(lib):
    themes=[n for n in lib['nodes'] if n['kind']=='theme'][:2]
    return {'id':None,'revision':0,'name':'跨来源公开测试','goal':'保留来源并核验接口',
            'instances':[{'id':'p'+str(i),'node_id':n['id'],'x':i*350,'y':0,'excluded':[],'note':''} for i,n in enumerate(themes)],
            'links':[{'source':'p0','target':'p1','label':'设计交接'}]}

def test_empty_first_start_has_no_personal_sources():
    assert a.catalog()['nodes']==[]
    assert s.records()==[]
    assert releases.observe(releases.loaded_config(),[])['families']==[]

def test_all_source_bytes_and_contains_have_independent_file_evidence():
    lib=pool();assert len(lib['sources'])==2
    assert len({n['id'] for n in lib['nodes']})==len(lib['nodes'])
    for rec in s.records():
        source=Path(rec['original_root']);snap=json.loads(Path(rec['path']).read_bytes())
        expected={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        assert {f['path']:f['sha256'] for f in snap['files']}==expected
        assert {p.relative_to(Path(rec['files_root'])).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(rec['files_root']).rglob('*') if p.is_file()}==expected
        for n in snap['nodes']:
            if n['parent_id']:assert any(e['kind']=='contains' and e['source_id']==n['parent_id'] and e['target_id']==n['id'] for e in snap['edges'])
        assert s.make_blueprint(snap,rec['sha256'])['links']==[]

def test_draft_save_reopen_cut_and_full_export_preserve_original_bytes():
    lib=pool();d=draft(lib);saved=a.save(d);assert saved['revision']==1
    assert a.draft(saved['id'])==saved
    saved['links']=[];saved=a.save(saved);assert len(saved['instances'])==2
    package=json.loads(a.package(saved['id']).body)
    body=json.loads(gzip.decompress(base64.b64decode(package['source_bundle'])))
    assert hashlib.sha256(core.canonical(body)).hexdigest()==package['bundle_sha256']
    assert body['execution_authority']['source_write'] is False
    for original in body['original_files']:
        rec=next(r for r in s.records() if r['skill_id']==original['source_skill_id'])
        raw=Path(rec['original_root']).joinpath(original['path']).read_bytes()
        actual=original['text'].encode(original['encoding']) if 'text' in original else base64.b64decode(original['binary_base64'])
        assert actual==raw and hashlib.sha256(raw).hexdigest()==original['sha256']
    stale=dict(saved,revision=0)
    with pytest.raises(ValueError):a.save(stale)

def test_internal_add_replace_remove_and_parent_positions_are_exported():
    lib=pool();d=draft(lib)
    root=d['instances'][0]['node_id']
    child=next(e['target'] for e in lib['contains'] if e['source']==root)
    foreign=next(n['id'] for n in lib['nodes'] if n['source_skill_id']!=next(n['source_skill_id'] for n in lib['nodes'] if n['id']==root) and n['kind']=='file')
    d['composition']={'schema_version':1,'scopes':[{'owner_id':'p0','path':[],
      'slots':[{'id':'o-'+child,'origin_id':child,'node_id':foreign,'x':0,'y':0,'note':'替换意图'},
               {'id':'a-added','origin_id':None,'node_id':child,'x':350,'y':0,'note':'保留另一位置'}],
      'links':[{'source':'o-'+child,'target':'a-added','label':'内部交接'}]}]}
    saved=a.save(d);assert a.draft(saved['id'])['composition']==d['composition']
    pkg=json.loads(a.package(saved['id']).body)
    body=json.loads(gzip.decompress(base64.b64decode(pkg['source_bundle'])))
    assert pkg['schema_version']==3 and body['draft']['composition']==d['composition']
    saved['composition']['scopes'][0]['slots'][0]['node_id']=None
    saved['composition']['scopes'][0]['links']=[]
    saved=a.save(saved);assert saved['composition']['scopes'][0]['slots'][1]['node_id']==child

def test_explicit_sync_preserves_old_version_and_rejects_changed_preview(tmp_path):
    root=tmp_path/'source';root.mkdir();(root/'SKILL.md').write_text('---\nname: test\nversion: "1"\n---\n# 原规则\n## 输出\n保留出处\n',encoding='utf-8')
    first=adopt(root);old=s.records()[0]
    (root/'SKILL.md').write_text('# 新规则\n## 输出\n保留出处和判断\n',encoding='utf-8')
    assert s.check_source(first['family_id'])['status']!='未变化'
    p=s.preview(root=str(root),version='2',family_id=first['family_id'])
    (root/'SKILL.md').write_text('# 在确认前又变化\n',encoding='utf-8')
    with pytest.raises(ValueError):s.confirm(p['preview_id'],p['preview_hash'],True,True)
    adopt(root,'3',first['family_id'])
    assert len(s.records())==2
    assert next(r for r in s.records() if r['version_id']==old['version_id'])['version_role']=='历史版本'
    assert s.verify_record(old)['skill']['version']=='1'

@pytest.mark.parametrize('bad',['../escape','/absolute','a\\b','a/../b','CON.md','a:stream','a./b','a//b','a/NUL','a\x00b'])
def test_invalid_paths_rejected(bad):
    with pytest.raises(ValueError):s.relative(bad)

def test_zip_traversal_and_size_rejected():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:z.writestr('../SKILL.md','# unsafe')
    with pytest.raises(ValueError):s.read_zip(stream.getvalue())
    with pytest.raises(ValueError):s.validate_items([('SKILL.md',b'x'*(core.MAX_BYTES+1),'a'*64)])
    with pytest.raises(ValueError):s.validate_items([('SKILL.md',b'a',core.digest(b'a')),('skill.md',b'b',core.digest(b'b'))])

@pytest.mark.parametrize('kind',['unknown','self_link','cycle','duplicate_link','unknown_parent'])
def test_bad_graphs_rejected(kind):
    d=draft(pool())
    if kind=='unknown':d['instances'][0]['node_id']='unknown'
    elif kind=='self_link':d['links']=[{'source':'p0','target':'p0','label':'bad'}]
    elif kind=='cycle':d['links'].append({'source':'p1','target':'p0','label':'bad'})
    elif kind=='duplicate_link':d['links']*=2
    else:d['composition']={'schema_version':1,'scopes':[{'owner_id':'missing','path':[],'slots':[],'links':[]}]}
    with pytest.raises(ValueError):a.save(d)

def test_handoff_is_only_read_only_and_formal_is_not_inferred():
    pool();state=releases.observe(releases.loaded_config(),releases.registry_records())
    assert len(state['families'])==2
    for row in state['families']:
        assert row['formal']['state']=='UNKNOWN' and row['installed']['state']=='UNKNOWN'
        assert not row['can_handoff_formal'] and row['can_handoff_registered']
        handoff=releases.build_handoff(row,'registered')
        assert handoff['scope']=='READ_ONLY_ANALYSIS' and handoff['usage_state']=='UNKNOWN'
        assert handoff['target_thread_id'] is None
        with pytest.raises(ValueError):releases.build_handoff(row,'formal')

def test_http_same_origin_session_csrf_and_request_size():
    from skm.api import app
    with TestClient(app,base_url='http://127.0.0.1:8770') as client:
        assert client.get('/api/skills').status_code==401
        token=client.get('/api/session').json()['csrf']
        assert client.get('/api/skills').status_code==200
        assert client.get('/api/skills',headers={'host':'evil.example'}).status_code==403
        assert client.post('/api/imports/preview',json={}).status_code==403
        assert client.post('/api/imports/preview',json={},headers={'x-skm-csrf':token,'origin':'https://evil.example'}).status_code==403
        assert client.post('/api/imports/preview',content=b'x'*(core.MAX_BYTES+1),headers={'x-skm-csrf':token}).status_code==413


def test_upload_chunk_retry_zip_and_binary_bytes_are_complete():
    raw=b'\xef\xbb\xbf---\nname: public-zip\nversion: "1"\n---\n# Chinese \xe8\xaf\x81\xe6\x8d\xae\n'
    binary=bytes(range(256));stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('example/SKILL.md',raw);z.writestr('example/assets/sample.bin',binary)
    data=stream.getvalue();u=s.upload_start([{'path':'skill.zip','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}],'zip')['upload_id']
    encoded=base64.b64encode(data).decode()
    s.upload_chunk(u,'skill.zip',0,encoded);assert s.upload_chunk(u,'skill.zip',0,encoded)['received']==len(data)
    with pytest.raises(ValueError):s.upload_chunk(u,'skill.zip',0,base64.b64encode(b'bad').decode())
    p=s.preview(upload_id=u);s.confirm(p['preview_id'],p['preview_hash'],missing_ack=True)
    rec=s.records()[0];assert not rec['original_root']
    assert Path(rec['files_root']).joinpath('SKILL.md').read_bytes()==raw
    assert Path(rec['files_root']).joinpath('assets/sample.bin').read_bytes()==binary


def test_missing_dependency_requires_explicit_acknowledgement(tmp_path):
    root=tmp_path/'missing';root.mkdir();(root/'SKILL.md').write_text('---\nname: missing\nversion: "1"\n---\n# Missing\n[rule](references/not-here.md)\n',encoding='utf-8')
    p=s.preview(root=str(root));assert p['unresolved_count']>0
    with pytest.raises(ValueError):s.confirm(p['preview_id'],p['preview_hash'])
    assert s.confirm(p['preview_id'],p['preview_hash'],missing_ack=True)['id']


def test_source_runtime_overlap_and_symlink_rejected(tmp_path):
    overlapping=core.RUNTIME/'test-source';overlapping.mkdir(exist_ok=True);(overlapping/'SKILL.md').write_text('# source',encoding='utf-8')
    with pytest.raises(ValueError):s.preview(root=str(overlapping),name='overlap',version='1')
    target=tmp_path/'real';target.mkdir();(target/'SKILL.md').write_text('# source',encoding='utf-8')
    link=tmp_path/'alias'
    try:link.symlink_to(target,target_is_directory=True)
    except OSError:pytest.skip('OS has not granted symlink creation to this test account')
    with pytest.raises(ValueError):s.preview(root=str(link),name='link',version='1')


def test_frozen_source_drift_stops_save_and_handoff():
    lib=pool();d=draft(lib);saved=a.save(d);rec=s.records()[0]
    path=Path(rec['files_root'])/'SKILL.md';before=path.read_bytes();path.write_bytes(before+b'\nchanged')
    with pytest.raises(ValueError):a.save(saved)
    rows=releases.observe(releases.loaded_config(),releases.registry_records())['families']
    assert next(r for r in rows if r['family_id']==rec['family_id'])['can_handoff_registered'] is False


@pytest.mark.parametrize('bound',['instances','links','coordinates','note','inner_identity'])
def test_model_limits_remain_enforced(bound):
    d=draft(pool())
    if bound=='instances':d['instances']=[dict(d['instances'][0],id='p'+str(i)) for i in range(61)]
    elif bound=='links':d['links']*=121
    elif bound=='coordinates':d['instances'][0]['x']=20001
    elif bound=='note':d['instances'][0]['note']='x'*2001
    else:d['composition']={'schema_version':1,'scopes':[{'owner_id':'p0','path':[],'slots':[{'id':'unqualified','origin_id':None,'node_id':d['instances'][1]['node_id'],'x':0,'y':0,'note':''}],'links':[]}]}
    with pytest.raises((ValueError,HTTPException)) as error:a.save(d)
    assert error.value
