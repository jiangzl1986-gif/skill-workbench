from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sqlite3
import threading
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from markdown_it import MarkdownIt

from .config import PROJECT, RUNTIME
MAX_FILES, MAX_BYTES, MAX_SCAN_BYTES = 5000, 2 * 1024 * 1024, 32 * 1024 * 1024
MD = MarkdownIt('commonmark', {'html': False}).enable('table')
GUARD = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else canonical(data)).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def ident():
    return str(uuid.uuid4())


def norm(text):
    return unicodedata.normalize('NFKC', text).casefold()


@contextmanager
def connect():
    RUNTIME.joinpath('data').mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(RUNTIME / 'data' / 'skm.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=30000')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS skills(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT,root TEXT NOT NULL UNIQUE,
          version TEXT,baseline TEXT,revision INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT '未扫描',last_sync TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS source_files(id TEXT PRIMARY KEY,skill_id TEXT NOT NULL REFERENCES skills(id),path TEXT NOT NULL,
          sha256 TEXT,bytes INTEGER,encoding TEXT,text TEXT,line_count INTEGER,state TEXT,revision INTEGER,deleted INTEGER DEFAULT 0,
          UNIQUE(skill_id,path));
        CREATE TABLE IF NOT EXISTS nodes(id TEXT PRIMARY KEY,skill_id TEXT NOT NULL REFERENCES skills(id),file_id TEXT REFERENCES source_files(id),
          parent_id TEXT,title TEXT,kind TEXT,summary TEXT,summary_kind TEXT,anchor TEXT,fingerprint TEXT,state TEXT,ordinal INTEGER,
          revision INTEGER,active INTEGER NOT NULL DEFAULT 1,created_at TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS source_spans(id TEXT PRIMARY KEY,node_id TEXT NOT NULL REFERENCES nodes(id),file_id TEXT NOT NULL REFERENCES source_files(id),
          start_line INTEGER,end_line INTEGER,sha256 TEXT,version TEXT,role TEXT);
        CREATE TABLE IF NOT EXISTS navigation_legacy(skill_id TEXT REFERENCES skills(id),node_id TEXT PRIMARY KEY REFERENCES nodes(id));
        CREATE TABLE IF NOT EXISTS navigation_views(skill_id TEXT PRIMARY KEY REFERENCES skills(id),policy_hash TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS edges(id TEXT PRIMARY KEY,skill_id TEXT REFERENCES skills(id),source_id TEXT REFERENCES nodes(id),
          target_id TEXT REFERENCES nodes(id),kind TEXT,confidence REAL,review_state TEXT,evidence TEXT,revision INTEGER);
        CREATE TABLE IF NOT EXISTS unresolved(id TEXT PRIMARY KEY,skill_id TEXT,source_id TEXT,path TEXT,line INTEGER,token TEXT,reason TEXT,revision INTEGER);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,skill_id TEXT,revision INTEGER,created_at TEXT,manifest TEXT,summary TEXT);
        CREATE TABLE IF NOT EXISTS change_requests(id TEXT PRIMARY KEY,skill_id TEXT,node_id TEXT,problem TEXT,expected TEXT,example TEXT,
          snapshot TEXT,package_hash TEXT,state TEXT,created_at TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS change_proposals(id TEXT PRIMARY KEY,request_id TEXT REFERENCES change_requests(id),version INTEGER,
          content TEXT,proposal_hash TEXT,state TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,proposal_id TEXT REFERENCES change_proposals(id),proposal_hash TEXT,
          decision TEXT,reason TEXT,actor TEXT,scope TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,proposal_id TEXT,content TEXT,state TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS audit_events(id TEXT PRIMARY KEY,actor TEXT,action TEXT,entity_id TEXT,detail TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS parsed_documents(file_id TEXT PRIMARY KEY,sha256 TEXT,blocks TEXT);
        CREATE TABLE IF NOT EXISTS source_scopes(skill_id TEXT PRIMARY KEY REFERENCES skills(id),policy TEXT NOT NULL);
        CREATE VIRTUAL TABLE IF NOT EXISTS source_search USING fts5(body,skill_id UNINDEXED,file_id UNINDEXED,tokenize='trigram');
        ''')


def audit(db, action, entity_id, detail, actor='本机用户'):
    db.execute('INSERT INTO audit_events VALUES(?,?,?,?,?,?)', (ident(), actor, action, entity_id, json.dumps(detail, ensure_ascii=False), now()))


def safe_file(root, relative):
    base = Path(root).resolve(strict=True)
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or ':' in relative or '\x00' in relative:
        raise ValueError('源路径不合法')
    p = base / rel
    for piece in [p, *list(p.parents)[:len(rel.parts) - 1]]:
        if piece.is_symlink() or (piece.exists() and getattr(piece.stat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('拒绝源目录内的链接或重解析点')
    resolved = p.resolve(strict=True)
    if not resolved.is_relative_to(base) or not resolved.is_file():
        raise ValueError('文件超出登记根目录')
    return resolved


def inventory(root, include_paths=None):
    base = Path(root).resolve(strict=True)
    if not (base / 'SKILL.md').is_file():
        raise ValueError('登记根目录必须包含 SKILL.md')
    items = []
    total_bytes=0
    for folder, dirs, names in os.walk(base, followlinks=False):
        for name in dirs + names:
            p = Path(folder) / name
            if p.is_symlink() or getattr(p.stat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('发现链接或重解析点；停止扫描：' + str(p.relative_to(base)))
        for name in sorted(names):
            p = Path(folder) / name
            relative = p.relative_to(base).as_posix()
            if include_paths is not None and relative not in include_paths:
                continue
            if p.stat().st_size > MAX_BYTES:
                raise ValueError('文件超过本批可靠上限2MiB：' + str(p.relative_to(base)))
            total_bytes+=p.stat().st_size
            if total_bytes>MAX_SCAN_BYTES:
                raise ValueError('单Skill超过本批32MiB可靠上限，停止并制定完整分批方案；不截断源')
            raw = p.read_bytes()
            # File size/metadata are not authoritative for content identity.
            items.append((p.relative_to(base).as_posix(), raw, digest(raw)))
            if len(items) > MAX_FILES:
                raise ValueError('文件超过本批可靠上限5000；停止并请求拆批')
    if include_paths is not None and {p for p, _, _ in items} != set(include_paths):
        raise ValueError('已确认展示范围存在缺失文件，停止索引')
    return sorted(items)


def source_scope(skill, db):
    row = db.execute('SELECT policy FROM source_scopes WHERE skill_id=?', (skill['id'],)).fetchone()
    return json.loads(row['policy']) if row else None


def source_manifest(skill, db, verify_view=True):
    scope = source_scope(skill, db)
    if not scope:
        return {p: sha for p, raw, sha in inventory(skill['root'])}
    # A view may defer historical/media files, but drift of the entire authoritative source still invalidates it.
    root = Path(skill['root']).resolve(strict=True)
    actual = {}; total = 0
    for folder, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            p = Path(folder) / name
            if p.is_symlink() or getattr(p.stat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('完整来源出现链接或重解析点')
        for name in names:
            p = Path(folder) / name
            total += p.stat().st_size
            if total > MAX_SCAN_BYTES or len(actual) >= MAX_FILES:
                raise ValueError('完整来源超出既定32MiB/5000项批量边界')
            hashed = hashlib.sha256()
            with p.open('rb') as stream:
                for chunk in iter(lambda: stream.read(65536), b''):
                    hashed.update(chunk)
            actual[p.relative_to(root).as_posix()] = hashed.hexdigest()
    frozen = {f['path']: f['sha256'] for f in scope['full_manifest']}
    if verify_view and actual != frozen:
        raise ValueError('完整正式来源已漂移，停止当前展示范围索引')
    return actual


def register(root, name, version='', description='', baseline=None, scope=None):
    resolved = str(Path(root).resolve(strict=True))
    source_root=Path(resolved)
    for folder in ('data','envs','build/web','backups','logs'):
        writable=(RUNTIME/folder).resolve()
        if writable.is_relative_to(source_root) or source_root.is_relative_to(writable):
            raise ValueError('源Skill不能与工作台写入目录重叠；请选择独立源目录')
    safe_file(resolved, 'SKILL.md')
    with GUARD, connect() as db:
        existing = db.execute('SELECT id,name,version FROM skills WHERE root=?', (resolved,)).fetchone()
        if existing:
            if existing['name']!=name or existing['version']!=version:
                raise ValueError('此目录已登记为 '+existing['name']+' '+existing['version']+'；不能静默覆盖版本，请使用确认的新版本根目录')
            prior = source_scope({'id': existing['id']}, db)
            if scope != prior:
                raise ValueError('来源展示范围已登记，不能静默改变；请确认新范围')
            return existing['id']
        sid = ident()
        db.execute('INSERT INTO skills(id,name,description,root,version,baseline) VALUES(?,?,?,?,?,?)',
                   (sid, name, description, resolved, version, json.dumps(baseline, ensure_ascii=False) if baseline else None))
        audit(db, '登记只读Skill', sid, {'root': resolved, 'version': version})
        if scope is not None:
            full = {f['path']: f['sha256'] for f in scope['full_manifest']}
            included = {f['path'] for f in scope['indexed_files']}
            deferred = {f['path'] for f in scope['deferred_files']}
            if baseline != full or included & deferred or included | deferred != set(full) or 'SKILL.md' not in included:
                raise ValueError('展示范围必须完整交代原始来源及明确保留项，不能丢失或重叠')
            if scope['original_root'] != resolved:
                raise ValueError('展示范围来源身份不匹配')
            db.execute('INSERT INTO source_scopes VALUES(?,?)', (sid, json.dumps(scope, ensure_ascii=False)))
    return sid


def parse_blocks(text, path):
    lines = text.splitlines(keepends=True)
    tokens = MD.parse(text)
    rows, stack = [], []
    # Markdown top-level block ranges preserve lists, tables and fences whole.
    for i, token in enumerate(tokens):
        if token.level != 0 or token.map is None or token.type.endswith('_close'):
            continue
        start, stop = token.map
        if stop <= start:
            continue
        kind = 'section' if token.type == 'heading_open' else ('template' if token.type in ('table_open', 'fence', 'code_block') else 'rule_candidate')
        raw = ''.join(lines[start:stop])
        cleaned = re.sub(r'^[\s#>*`|\-]+', '', raw).strip().splitlines()
        title = tokens[i + 1].content if kind == 'section' else (cleaned[0] if cleaned else '分隔符 / 原文块')
        title = title[:140] or '原文块'
        if kind == 'section':
            depth = int(token.tag[1:])
            while stack and stack[-1][0] >= depth:
                stack.pop()
            parent_index = stack[-1][1] if stack else None
            stack.append((depth, len(rows)))
        else:
            parent_index = stack[-1][1] if stack else None
        # Anchor contains full heading lineage, never a fabricated source position.
        lineage = '/'.join(rows[x[1]]['title'] for x in stack if x[1] < len(rows))
        rows.append({'title': title, 'kind': kind, 'start': start + 1, 'end': stop,
                     'parent_index': parent_index, 'anchor': lineage + '/' + title,
                     'fingerprint': digest(raw.encode('utf-8')), 'summary': re.sub(r'\s+', ' ', raw).strip()[:230]})
    for token in tokens:
        if token.type != 'list_item_open' or token.map is None:
            continue
        start, stop = token.map
        parents = [(r['end']-r['start'],j) for j,r in enumerate(rows)
                   if r['kind'] in ('rule_candidate','subrule') and r['start'] <= start+1 and r['end'] >= stop]
        if not parents:
            continue
        parent = min(parents)[1]
        raw = ''.join(lines[start:stop])
        title = raw.strip().splitlines()[0][:140]
        rows.append({'title':title,'kind':'subrule','start':start+1,'end':stop,'parent_index':parent,
                     'anchor':rows[parent]['anchor']+'/'+title,'fingerprint':digest(raw.encode()),
                     'summary':re.sub(r'\s+',' ',raw).strip()[:230]})
    covered = {line for r in rows for line in range(r['start'], r['end'] + 1)}
    # YAML front matter, unsupported syntax and any other nonblank text remain accessible.
    missing = [i + 1 for i, line in enumerate(lines) if line.strip() and i + 1 not in covered]
    for line in missing:
        raw = lines[line - 1]
        rows.append({'title': raw.strip()[:140], 'kind': 'unclassified', 'start': line, 'end': line,
                     'parent_index': None, 'anchor': 'unclassified/' + raw.strip()[:140],
                     'fingerprint': digest(raw.encode()), 'summary': raw.strip()[:230]})
    return rows


def scan(sid, force=False):
    with GUARD, connect() as db:
        skill = db.execute('SELECT * FROM skills WHERE id=?', (sid,)).fetchone()
        if not skill:
            raise ValueError('未登记Skill')
        try:
            scope = source_scope(skill, db)
            files = inventory(skill['root'], {f['path'] for f in scope['indexed_files']} if scope else None)
            manifest = {p: sha for p, raw, sha in files}
            baseline = json.loads(skill['baseline']) if skill['baseline'] else None
            full_manifest = source_manifest(skill, db) if scope else manifest
            if baseline and full_manifest != baseline:
                raise ValueError('锁定正式源发生变化；停止当前Skill扫描，需确认新版本/基线，旧地图标过期')
            old_manifest = {r['path']: r['sha256'] for r in db.execute('SELECT path,sha256 FROM source_files WHERE skill_id=? AND deleted=0', (sid,))}
            if manifest == old_manifest and not force:
                from .content_navigation import apply
                navigation_changed=apply(db,skill,manifest)
                if navigation_changed and (source_manifest(skill,db) if scope else {p:sha for p,raw,sha in inventory(skill['root'])})!=full_manifest:
                    raise ValueError('更新内容导航时源发生变化；回滚本批')
                db.execute('UPDATE skills SET state=?,error=NULL,last_sync=? WHERE id=?', ('已同步', now(), sid))
                return {'changed': navigation_changed, 'revision': skill['revision']+int(navigation_changed), 'files': len(files)}
            rev = skill['revision'] + 1
            existing = [dict(r) for r in db.execute('SELECT * FROM nodes WHERE skill_id=? AND active=1', (sid,))]
            old_positions={r['node_id']:(r['start_line'],r['end_line']) for r in db.execute('SELECT sp.* FROM source_spans sp JOIN nodes n ON n.id=sp.node_id WHERE n.skill_id=?',(sid,))}
            unchanged_ids=set()
            unused = {r['id']: r for r in existing}
            by_content={};by_anchor={}
            for row in existing:
                by_content.setdefault((row['file_id'],row['kind'],row['fingerprint']),[]).append(row['id'])
                by_anchor.setdefault((row['file_id'],row['kind'],row['anchor']),[]).append(row['id'])
            db.execute('UPDATE nodes SET active=0 WHERE skill_id=?', (sid,))
            db.execute('UPDATE source_files SET deleted=1 WHERE skill_id=?', (sid,))
            db.execute('DELETE FROM source_spans WHERE node_id IN (SELECT id FROM nodes WHERE skill_id=?)', (sid,))
            db.execute('DELETE FROM edges WHERE skill_id=?', (sid,))
            db.execute('DELETE FROM unresolved WHERE skill_id=?', (sid,))

            def add(title, kind, parent=None, fid=None, anchor='', fingerprint='', summary='', ordinal=0, span=None):
                # Prefer unchanged content within a file; title/anchor alone cannot remap a moved rewritten rule.
                candidates = [unused[nid] for nid in by_content.get((fid,kind,fingerprint),[]) if nid in unused] if fingerprint else []
                if len(candidates) != 1:
                    candidates = [unused[nid] for nid in by_anchor.get((fid,kind,anchor),[]) if nid in unused] if anchor else []
                if len(candidates)>1 and fid in unchanged_ids and span:
                    # An unchanged file has immutable positions; repeated identical paragraphs can safely keep IDs.
                    candidates=[r for r in candidates if old_positions.get(r['id'])==(span[0],span[1])]
                ambiguous=[r['id'] for r in candidates] if len(candidates)>1 else []
                nid = candidates[0]['id'] if len(candidates) == 1 else ident()
                prior = unused.pop(nid, None)
                state = '导航分类' if kind in ('skill', 'theme') else ('源文件' if kind == 'file' else '结构定位已核对 / 语义待审')
                if ambiguous:state='节点身份匹配有歧义 / 需人工核对；语义待审'
                db.execute('''INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(id) DO UPDATE SET parent_id=excluded.parent_id,title=excluded.title,summary=excluded.summary,summary_kind=excluded.summary_kind,
                  fingerprint=excluded.fingerprint,anchor=excluded.anchor,state=excluded.state,ordinal=excluded.ordinal,
                  revision=excluded.revision,active=1,updated_at=excluded.updated_at''',
                   (nid,sid,fid,parent,title,kind,summary,('来源说明' if kind in ('file','code_symbol') else '原文摘句') if fid else '导航说明',anchor,fingerprint,state,ordinal,rev,1,
                   prior['created_at'] if prior else now(),now()))
                if parent:
                    edge(parent, nid, 'contains', 1, '结构定位', {})
                if span:
                    db.execute('INSERT INTO source_spans VALUES(?,?,?,?,?,?,?,?)',
                               (ident(), nid, fid, span[0], span[1], manifest[span[2]], skill['version'], '完整块'))
                    if ambiguous:
                        db.execute('INSERT INTO unresolved VALUES(?,?,?,?,?,?,?,?)',(ident(),sid,nid,span[2],span[0],'节点身份',
                                   '同一内容/锚点对应多个旧节点；未自动套用旧意见。候选：'+','.join(ambiguous),rev))
                return nid

            def edge(src, dst, kind, confidence, status, evidence):
                db.execute('INSERT INTO edges VALUES(?,?,?,?,?,?,?,?,?)', (ident(),sid,src,dst,kind,confidence,status,json.dumps(evidence,ensure_ascii=False),rev))

            root_id = add(skill['name'] + ' ' + skill['version'], 'skill', anchor='root', summary=skill['description'])
            is_v16 = False
            groups = [(key,title,()) for key,title in sorted({
                ('entry','入口与共用材料') if '/' not in path else
                ('/'.join(path.split('/')[:2]) if path.startswith('modules/') else path.split('/')[0],
                 '待分类 · '+('/'.join(path.split('/')[:2]) if path.startswith('modules/') else path.split('/')[0]))
                for path,raw,sha in files})]
            themes = {key: add(title, 'theme', root_id, anchor=key, summary='文件组织推导的分类候选；等待本Skill的业务语义审查。', ordinal=i) for i,(key,title,hints) in enumerate(groups)}
            db.execute('DELETE FROM source_search WHERE skill_id=?',(sid,))
            file_nodes, rows_by_path, file_ids = {}, {}, {}
            old_files = [dict(r) for r in db.execute('SELECT * FROM source_files WHERE skill_id=?', (sid,))]
            unchanged_ids.update(r['id'] for r in old_files if manifest.get(r['path'])==r['sha256'])
            old_paths = set(manifest)
            for ordinal,(path,raw,sha) in enumerate(files):
                old = next((r for r in old_files if r['path'] == path), None)
                # Unambiguous exact-byte rename keeps file identity; ambiguous matches remain new.
                if not old:
                    matches = [r for r in old_files if r['path'] not in old_paths and r['sha256'] == sha]
                    old = matches[0] if len(matches) == 1 else None
                fid = old['id'] if old else ident()
                try:
                    text = raw.decode('utf-8-sig')
                    encoding, state = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8', '已索引'
                except UnicodeDecodeError:
                    text, encoding, state = '', '未知', '需核对编码 / 未解析'
                lines = text.splitlines(keepends=True)
                db.execute('''INSERT INTO source_files VALUES(?,?,?,?,?,?,?,?,?,?,0)
                  ON CONFLICT(id) DO UPDATE SET path=excluded.path,sha256=excluded.sha256,bytes=excluded.bytes,
                  encoding=excluded.encoding,text=excluded.text,line_count=excluded.line_count,state=excluded.state,revision=excluded.revision,deleted=0''',
                  (fid,sid,path,sha,len(raw),encoding,text,len(lines),state,rev))
                file_ids[path] = fid
                group = ('entry' if '/' not in path else '/'.join(path.split('/')[:2]) if path.startswith('modules/') else path.split('/')[0])
                first_heading = next((t for t in MD.parse(text) if t.type=='inline' and t.map and text.splitlines()[t.map[0]].lstrip().startswith('#')),None) if path.endswith('.md') and text else None
                fn = add(first_heading.content if first_heading else path.split('/')[-1], 'file', themes[group], fid, anchor='file', fingerprint='',
                         summary='来源：' + path + '。完整原文保留，脚本与配置仅作静态阅读。', ordinal=ordinal,
                         span=(1,len(lines),path) if lines else None)
                file_nodes[path] = fn
                cached=db.execute('SELECT blocks FROM parsed_documents WHERE file_id=? AND sha256=?',(fid,sha)).fetchone()
                blocks = json.loads(cached['blocks']) if cached else parse_blocks(text,path) if path.endswith('.md') else []
                if not cached and not path.endswith('.md') and text:
                    # Static code symbols are navigation, never proof of rule execution.
                    if path.endswith('.py'):
                        try:
                            for item in ast.walk(ast.parse(text)):
                                if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                                    blocks.append({'title':item.name,'kind':'code_symbol','start':item.lineno,'end':item.end_lineno,
                                                   'parent_index':None,'anchor':item.name,'fingerprint':digest(''.join(lines[item.lineno-1:item.end_lineno]).encode()),
                                                   'summary':'静态定义；未执行、未核验业务调用关系。'})
                        except SyntaxError as exc:
                            db.execute('UPDATE source_files SET state=? WHERE id=?', ('AST未解析：'+str(exc),fid))
                    elif path.endswith('.json'):
                        try:
                            json.loads(text)
                        except ValueError:
                            db.execute('UPDATE source_files SET state=? WHERE id=?',('JSON未解析',fid))
                db.execute('INSERT OR REPLACE INTO parsed_documents VALUES(?,?,?)',(fid,sha,json.dumps(blocks,ensure_ascii=False)))
                db.execute('INSERT INTO source_search(body,skill_id,file_id) VALUES(?,?,?)',(norm(text),sid,fid))
                block_ids = []
                for i,b in enumerate(blocks):
                    parent = block_ids[b['parent_index']] if b['parent_index'] is not None else fn
                    block_ids.append(add(b['title'],b['kind'],parent,fid,b['anchor'],b['fingerprint'],b['summary'],i,(b['start'],b['end'],path)))
                rows_by_path[path] = (lines,blocks,block_ids)

            pattern = re.compile(r'[A-Za-z0-9_./\\\-]+\.(?:md|py|json|yaml|yml|txt)\b')
            for path,(lines,blocks,block_ids) in rows_by_path.items():
                for line_num,line in enumerate(lines,1):
                    for token in pattern.findall(line):
                        token = token.replace('\\','/').strip('./')
                        matches = [p for p in manifest if p == token or p.endswith('/'+token)]
                        candidates = [(b['end']-b['start'],nid) for b,nid in zip(blocks,block_ids) if b['start'] <= line_num <= b['end']]
                        src = min(candidates)[1] if candidates else file_nodes[path]
                        if len(matches) == 1:
                            dst = file_nodes[matches[0]]
                            if src != dst:
                                edge(src,dst,'references',1,'显式文件名 / 语义待核验',{'path':path,'line':line_num,'token':token})
                        else:
                            db.execute('INSERT INTO unresolved VALUES(?,?,?,?,?,?,?,?)', (ident(),sid,src,path,line_num,token,
                                       '多候选需核对' if matches else '未定位：可能为产物、外部路径或符号，未判为坏链接',rev))
            # Read twice across the batch to reject a mixture of source editions.
            from .content_navigation import apply
            apply(db,skill,manifest)
            final_manifest = source_manifest(skill, db) if scope else {p:sha for p,raw,sha in inventory(skill['root'])}
            if final_manifest != full_manifest:
                raise ValueError('扫描中源发生变化；本批回滚，保持上次版本')
            summary = {'files':len(files),'bytes':sum(len(raw) for _,raw,_ in files),'nodes':db.execute('SELECT count(*) FROM nodes WHERE skill_id=? AND active=1',(sid,)).fetchone()[0]}
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)',(ident(),sid,rev,now(),json.dumps(manifest,ensure_ascii=False),json.dumps(summary,ensure_ascii=False)))
            db.execute('UPDATE skills SET revision=?,state=?,last_sync=?,error=NULL WHERE id=?',(rev,'已同步',now(),sid))
            audit(db,'只读扫描完成',sid,{'revision':rev,**summary},'本机索引服务')
            db.commit()
            return {'changed':True,'revision':rev,**summary}
        except Exception as exc:
            db.rollback()
            db.execute('UPDATE skills SET state=?,error=? WHERE id=?',('源异常 / 保留上次地图',str(exc),sid))
            if skill['error']!=str(exc):
                audit(db,'扫描停止',sid,{'error':str(exc)},'本机索引服务')
            db.commit()
            raise


def current_node(nid, db):
    node = db.execute('SELECT n.*,s.name skill_name,s.version,s.root,s.state skill_state FROM nodes n JOIN skills s ON s.id=n.skill_id WHERE n.id=? AND n.active=1',(nid,)).fetchone()
    if not node:
        raise ValueError('节点不存在或已失效；请重新定位')
    result = dict(node)
    spans = []
    for row in db.execute('SELECT sp.*,f.path,f.text,f.sha256 actual_hash FROM source_spans sp JOIN source_files f ON f.id=sp.file_id WHERE sp.node_id=?',(nid,)):
        p = safe_file(node['root'],row['path'])
        if digest(p.read_bytes()) != row['sha256']:
            raise ValueError('源已变化，当前节点原文过期；请刷新并重新分析')
        lines = row['text'].splitlines(keepends=True)
        spans.append({k:row[k] for k in ('path','start_line','end_line','sha256','version','role')} | {'text':''.join(lines[row['start_line']-1:row['end_line']])})
    result['spans'] = spans
    result['context'] = None
    if node['file_id']:
        f = db.execute('SELECT * FROM source_files WHERE id=?',(node['file_id'],)).fetchone()
        if digest(safe_file(node['root'],f['path']).read_bytes()) != f['sha256']:
            raise ValueError('来源已变化，停止显示旧原文')
        result['context'] = {'path':f['path'],'sha256':f['sha256'],'text':f['text'],'line_count':f['line_count'],'state':f['state']}
    result['children'] = [dict(r) for r in db.execute("SELECT DISTINCT n.id,n.title,n.kind,n.ordinal FROM edges e JOIN nodes n ON n.id=e.target_id WHERE e.source_id=? AND e.kind='contains' AND n.active=1 AND n.id NOT IN(SELECT node_id FROM navigation_legacy) ORDER BY n.ordinal",(nid,))]
    result['edges'] = [dict(r) for r in db.execute('SELECT e.*,n.title target_title FROM edges e JOIN nodes n ON n.id=e.target_id WHERE (e.source_id=? OR e.target_id=?) AND e.kind!=?',(nid,nid,'contains'))]
    result['unresolved'] = [dict(r) for r in db.execute('SELECT * FROM unresolved WHERE source_id=?',(nid,))]
    return result


def breadcrumbs(db, nid):
    out, seen = [], set()
    while nid and nid not in seen:
        seen.add(nid)
        row = db.execute('SELECT id,title,parent_id FROM nodes WHERE id=?',(nid,)).fetchone()
        if not row:
            break
        out.append({'id':row['id'],'title':row['title']})
        nid = row['parent_id']
    return out[::-1]


def search(query, skill_id=None, limit=60):
    if not query.strip():
        return []
    needle = norm(query.strip())
    results = []
    with connect() as db:
        raw_candidates=None
        if len(needle)>=3:
            phrase='"'+needle.replace('"','""')+'"'
            raw_candidates={r['file_id'] for r in db.execute('SELECT file_id FROM source_search WHERE body MATCH ?',(phrase,))}
        params, where = [], ''
        if skill_id:
            where = ' AND n.skill_id=?'
            params.append(skill_id)
        rows = db.execute('''SELECT n.*,f.path,sp.start_line,sp.end_line,s.name skill_name,s.version,s.state skill_state
          FROM nodes n JOIN skills s ON s.id=n.skill_id LEFT JOIN source_files f ON f.id=n.file_id
          LEFT JOIN source_spans sp ON sp.node_id=n.id
          WHERE n.active=1 AND n.id NOT IN(SELECT node_id FROM navigation_legacy)''' + where + ' ORDER BY n.ordinal',params)
        source_lines={}
        for row in rows:
            hay = '\n'.join((row['title'] or '',row['summary'] or '',row['path'] or '',row['skill_name']))
            # Source content is loaded once; every node searches its exact original span.
            if row['file_id'] and (raw_candidates is None or row['file_id'] in raw_candidates):
                if row['file_id'] not in source_lines:
                    text=db.execute('SELECT text FROM source_files WHERE id=?',(row['file_id'],)).fetchone()[0]
                    source_lines[row['file_id']]=text.splitlines(keepends=True)
                hay+='\n'+''.join(source_lines[row['file_id']][(row['start_line'] or 1)-1:row['end_line']])
            normalized=norm(hay)
            pos = normalized.find(needle)
            if pos < 0:
                continue
            # Map normalized offsets back to the original characters for exact snippets.
            raw_pos=pos
            if len(normalized)!=len(hay):
                offset_map=[]
                for i,ch in enumerate(hay):offset_map.extend([i]*len(norm(ch)))
                raw_pos=offset_map[pos] if pos<len(offset_map) else 0
            results.append({'id':row['id'],'title':row['title'],'kind':row['kind'],'skill_id':row['skill_id'],
                            'skill_name':row['skill_name'],'version':row['version'],'path':row['path'],
                            'start_line':row['start_line'],'end_line':row['end_line'],
                            'snippet':hay[max(0,raw_pos-55):raw_pos+len(query)+110],'breadcrumb':breadcrumbs(db,row['id']),
                            'state':row['skill_state'],'score':(0 if needle in norm(row['title']) else 1)})
    return sorted(results,key=lambda r:r['score'])[:limit]
