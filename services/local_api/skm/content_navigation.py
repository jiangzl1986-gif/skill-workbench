"""Content navigation only: retain every original node, span, file and legacy selection."""
import hashlib
import json
import uuid
from pathlib import Path
from datetime import datetime,timezone
from .config import PROJECT

POLICY_LOCK=PROJECT/'config/content_navigation.lock.json'

def plan(skill,manifest):
    if not POLICY_LOCK.is_file():return None
    locked=json.loads(POLICY_LOCK.read_text('utf-8-sig'));raw=Path(locked['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=locked['sha256']:raise ValueError('内容导航策略漂移；请先核对分类来源')
    source=next((s for s in json.loads(raw)['sources'] if s['skill_id']==skill['id']),None)
    if not source:return None
    if source['version']!=skill['version'] or source['root']!=skill['root']:raise ValueError('内容导航来源版本不一致')
    if {f['path']:f['sha256'] for f in source['files']}!=manifest:raise ValueError('内容导航必须完整覆盖当前执行视图且hash一致')
    keys={g['key'] for g in source['groups']}
    if len(keys)!=len(source['groups']) or len({f['path'] for f in source['files']})!=len(source['files']) or any(f['group'] not in keys for f in source['files']):raise ValueError('内容导航分类重复、遗漏或所属板块无效')
    return source,locked['sha256']

def apply(db,skill,manifest):
    configured=plan(skill,manifest)
    if not configured:return False
    source,digest=configured
    old=db.execute('SELECT policy_hash FROM navigation_views WHERE skill_id=?',(skill['id'],)).fetchone()
    if old and old[0]==digest:
        # A source rebuild may temporarily remove derived nodes; repair that case without changing raw IDs.
        existing={r[0] for r in db.execute('SELECT anchor FROM nodes WHERE skill_id=? AND kind=? AND active=1',(skill['id'],'theme'))}
        if all('content/'+g['key'] in existing for g in source['groups']):return False
    stamp=datetime.now(timezone.utc).isoformat();sid=skill['id'];rev=skill['revision']+1
    root=db.execute("SELECT id FROM nodes WHERE skill_id=? AND kind='skill' AND active=1",(sid,)).fetchone()[0]
    originals=list(db.execute("SELECT id,anchor FROM nodes WHERE skill_id=? AND kind='theme' AND active=1",(sid,)))
    for row in originals:
        if not row['anchor'].startswith('content/'):
            db.execute('INSERT OR IGNORE INTO navigation_legacy VALUES(?,?)',(sid,row['id']))
    ids={g['key']:str(uuid.uuid5(uuid.NAMESPACE_URL,'skill-content-navigation/'+sid+'/'+g['key'])) for g in source['groups']}
    def edge(a,b,evidence):
        if not db.execute("SELECT 1 FROM edges WHERE source_id=? AND target_id=? AND kind='contains'",(a,b)).fetchone():
            db.execute('INSERT INTO edges VALUES(?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),sid,a,b,'contains',1,'源内容导航 / 不改变执行授权',json.dumps(evidence,ensure_ascii=False),rev))
    for i,g in enumerate(source['groups']):
        nid=ids[g['key']]
        db.execute('''INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET active=1,title=excluded.title,summary=excluded.summary,ordinal=excluded.ordinal''',
          (nid,sid,None,root,g['title'],'theme',source['classification_boundary'],'导航说明','content/'+g['key'],'','内容导航',i,rev,1,stamp,stamp))
        edge(root,nid,{'navigation_policy_sha256':digest,'entry_evidence':source['entry_evidence'],'role':'来源内容分类，非执行顺序'})
    for f in source['files']:
        node=db.execute("SELECT n.id,n.file_id FROM nodes n JOIN source_files sf ON sf.id=n.file_id WHERE n.skill_id=? AND n.kind='file' AND n.active=1 AND sf.path=? AND sf.sha256=?",(sid,f['path'],f['sha256'])).fetchone()
        if not node or node['file_id']!=f['file_id']:raise ValueError('原始文件节点身份失配，停止内容导航')
        db.execute('UPDATE nodes SET parent_id=? WHERE id=?',(ids[f['group']],node['id']))
        edge(ids[f['group']],node['id'],{'path':f['path'],'sha256':f['sha256'],'basis':f['basis'],'original_title':f['original_title']})
    for link in source.get('section_links',[]):
        node=db.execute("SELECT n.id FROM nodes n JOIN source_files f ON f.id=n.file_id WHERE n.skill_id=? AND n.kind='section' AND n.active=1 AND f.path=? AND f.sha256=? AND n.title=?",(sid,link['path'],link['sha256'],link['heading'])).fetchall()
        if len(node)!=1:raise ValueError('正式入口章节证据不唯一；停止关联')
        edge(ids[link['group']],node[0]['id'],link)
    db.execute('INSERT OR REPLACE INTO navigation_views VALUES(?,?,?)',(sid,digest,stamp))
    db.execute('UPDATE skills SET revision=revision+1 WHERE id=?',(sid,))
    return True
