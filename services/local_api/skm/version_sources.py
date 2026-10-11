"""Read-only Skill ingestion and immutable, explicitly adopted design versions.

Skill content is data: no imports, subprocesses, installation or remote services.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import stat
import threading
import zipfile
from pathlib import Path, PurePosixPath
from . import core

DEFAULT_STORE = core.RUNTIME / 'versions'
STORE = Path(os.environ.get('SKM_IMPORT_STORE', str(DEFAULT_STORE))).resolve()
if not STORE.is_relative_to(core.RUNTIME.resolve()):
    raise ValueError('版本快照必须位于本工作台独立运行目录')
UPLOAD = core.RUNTIME / 'cache' / 'skill-imports'
GUARD = threading.RLock()
CHUNK = 256 * 1024


def relative(value):
    """Reject Windows aliases, ADS, case collisions, traversal and link escapes."""
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('文件相对路径不合法')
    p = PurePosixPath(value)
    if p.is_absolute() or any(v in ('', '.', '..') for v in value.split('/')):
        raise ValueError('文件路径越界')
    for part in p.parts:
        if ':' in part or part.endswith((' ', '.')) or any(c in part for c in '<>"|?*'):
            raise ValueError('文件路径包含不支持的字符')
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            raise ValueError('文件路径包含系统保留名')
    return p.as_posix()


def manifest(items):
    return [{'path':p,'bytes':len(raw),'sha256':sha} for p,raw,sha in items]


def validate_items(items):
    if not items or len(items)>core.MAX_FILES:
        raise ValueError('来源文件数量必须为1至5000，不截断导入')
    seen=set();total=0
    for p,raw,sha in items:
        p=relative(p)
        if p.casefold() in seen:raise ValueError('重复或大小写冲突的文件路径：'+p)
        seen.add(p.casefold());total+=len(raw)
        if len(raw)>core.MAX_BYTES:raise ValueError('单文件超过2MiB：'+p)
        if sha!=core.digest(raw):raise ValueError('文件内容校验失败：'+p)
    if total>core.MAX_SCAN_BYTES:raise ValueError('来源超过32MiB，需要完整分批方案；没有截断')
    if 'SKILL.md' not in {p for p,_,_ in items}:raise ValueError('完整来源根目录必须包含SKILL.md')
    return sorted(items)


def read_folder(root):
    p=Path(root)
    if not p.is_absolute():raise ValueError('请提供准确的绝对目录')
    # Check the supplied path before resolve, including junction parents.
    for part in (p,*p.parents):
        if part.is_symlink() or (part.exists() and getattr(part.stat(),'st_file_attributes',0)&0x400):
            raise ValueError('拒绝链接或重解析点来源')
    return validate_items(core.inventory(p))


def read_zip(raw):
    if len(raw)>core.MAX_BYTES:raise ValueError('ZIP压缩包超过2MiB，本批不扩容')
    items=[];seen=set();total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if len(infos)>core.MAX_FILES*2:raise ValueError('ZIP条目超限')
        files=[i for i in infos if not i.is_dir()]
        if len(files)>core.MAX_FILES:raise ValueError('ZIP文件数超过5000')
        for info in infos:
            name=relative(info.filename.rstrip('/'))
            mode=info.external_attr>>16
            if stat.S_ISLNK(mode) or (mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):
                raise ValueError('ZIP含链接或特殊文件')
            if info.flag_bits&1:raise ValueError('不接受加密ZIP')
            if info.is_dir():continue
            if name.casefold() in seen:raise ValueError('ZIP路径冲突')
            seen.add(name.casefold());total+=info.file_size
            if info.file_size>core.MAX_BYTES or total>core.MAX_SCAN_BYTES:raise ValueError('ZIP展开内容超过原文件/总量上限')
            with z.open(info) as stream:data=stream.read(core.MAX_BYTES+1)
            if len(data)!=info.file_size:raise ValueError('ZIP文件不完整')
            items.append((name,data,core.digest(data)))
    # A single enclosing folder is supported; never pick one of several Skills.
    if not any(p=='SKILL.md' for p,_,_ in items):
        roots={p.split('/')[0] for p,_,_ in items}
        if len(roots)==1 and any(p==next(iter(roots))+'/SKILL.md' for p,_,_ in items):
            prefix=next(iter(roots))+'/'
            items=[(p[len(prefix):],data,sha) for p,data,sha in items]
    return validate_items(items)


def discover(root, depth=3):
    base=Path(root)
    if not base.is_absolute() or not base.is_dir():raise ValueError('请选择存在的搜索目录')
    if not 0<=depth<=6:raise ValueError('搜索深度限0至6层')
    found=[];visited=0;stack=[(base,0)]
    while stack:
        folder,level=stack.pop();visited+=1
        if visited>3000:raise ValueError('搜索超过3000目录，请缩小范围；结果未作为完整列表提交')
        if folder.is_symlink() or getattr(folder.stat(),'st_file_attributes',0)&0x400:continue
        entry=folder/'SKILL.md'
        if entry.is_file() and not entry.is_symlink():
            if entry.stat().st_size>core.MAX_BYTES:raise ValueError('发现SKILL.md超限：'+str(entry))
            meta=metadata(entry.read_bytes())
            found.append({'root':str(folder),'name':meta['name'] or folder.name,'version':meta['version'],'registration':'候选来源；尚未导入'})
            if len(found)>100:raise ValueError('搜索发现超过100个来源，请缩小范围')
            continue
        if level<depth:
            stack.extend((p,level+1) for p in sorted(folder.iterdir(),reverse=True) if p.is_dir())
    return {'candidates':found,'visited_directories':visited,'depth':depth,'registration':'未导入；请逐个选择预览'}


def metadata(raw):
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:raise ValueError('SKILL.md必须为UTF-8文本')
    front=re.match(r'^---\s*\n(.*?)\n---\s*(?:\n|$)',text,re.S)
    def field(key):
        m=re.search(r'^'+key+r':\s*(.+)$',front.group(1),re.M) if front else None
        return m.group(1).strip().strip('"\'') if m else ''
    heading=re.search(r'^#\s+(.+)$',text,re.M)
    return {'name':field('name') or (heading.group(1) if heading else ''),'version':field('version'),'description':field('description'),'text':text}


def upload_start(records, kind='folder'):
    if kind not in ('folder','zip'):raise ValueError('上传类型不支持')
    if not isinstance(records,list) or not 1<=len(records)<=core.MAX_FILES:raise ValueError('上传清单数量超限')
    total=0;seen=set();safe=[]
    for f in records:
        p=relative(f['path']);size=f['bytes'];sha=f['sha256']
        if type(size)!=int or not 0<=size<=core.MAX_BYTES or not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('上传清单不合法')
        if p.casefold() in seen:raise ValueError('上传路径冲突')
        seen.add(p.casefold());total+=size;safe.append({'path':p,'bytes':size,'sha256':sha})
    if total>core.MAX_SCAN_BYTES or (kind=='zip' and (len(safe)!=1 or total>core.MAX_BYTES)):raise ValueError('上传超限')
    uid=core.ident();folder=UPLOAD/uid;folder.mkdir(parents=True)
    (folder/'manifest.json').write_bytes(core.canonical({'kind':kind,'files':safe}))
    (folder/'files').mkdir()
    return {'upload_id':uid,'chunk_bytes':CHUNK}


def upload_chunk(uid,path,offset,data):
    if not re.fullmatch('[0-9a-f-]{36}',uid):raise ValueError('上传标识无效')
    path=relative(path)
    with GUARD:
        folder=UPLOAD/uid;m=json.loads((folder/'manifest.json').read_bytes())
        f=next((v for v in m['files'] if v['path']==path),None)
        if not f:raise ValueError('文件未在完整清单中')
        raw=base64.b64decode(data,validate=True)
        if len(raw)>CHUNK or type(offset)!=int or offset<0:raise ValueError('上传块超限或偏移无效')
        p=folder/'files'/path;p.parent.mkdir(parents=True,exist_ok=True)
        current=p.stat().st_size if p.exists() else 0
        # Idempotent retry after a lost response, without duplicate appends.
        if offset<current:
            with p.open('rb') as stream:stream.seek(offset);prior=stream.read(len(raw))
            if prior==raw and offset+len(raw)<=current:return {'received':current}
            raise ValueError('重试块与已接收内容不一致')
        if current!=offset or offset+len(raw)>f['bytes']:raise ValueError('上传偏移或长度不一致')
        with p.open('ab') as stream:stream.write(raw)
        return {'received':offset+len(raw)}


def uploaded(uid):
    if not re.fullmatch('[0-9a-f-]{36}',uid):raise ValueError('上传标识无效')
    folder=UPLOAD/uid;m=json.loads((folder/'manifest.json').read_bytes());items=[]
    for f in m['files']:
        p=folder/'files'/f['path']
        if not p.is_file() or p.stat().st_size!=f['bytes']:raise ValueError('上传未完整，尚未导入：'+f['path'])
        raw=p.read_bytes()
        if core.digest(raw)!=f['sha256']:raise ValueError('上传文件校验失败：'+f['path'])
        items.append((f['path'],raw,f['sha256']))
    actual={p.relative_to(folder/'files').as_posix() for p in (folder/'files').rglob('*') if p.is_file()}
    if actual!={f['path'] for f in m['files']}:raise ValueError('上传目录出现未登记文件')
    return read_zip(items[0][1]) if m['kind']=='zip' else validate_items(items)


def freeze(items, target):
    items=validate_items(items);target=Path(target)
    if target.exists():raise ValueError('冻结目录已存在，拒绝覆盖')
    target.mkdir(parents=True)
    for p,raw,sha in items:
        dest=target/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    if manifest(read_folder(target))!=manifest(items):raise ValueError('冻结复读字节不一致')
    return manifest(items)


def init():
    with core.GUARD,core.connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS skm_version_families(id TEXT PRIMARY KEY,name TEXT NOT NULL,head TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS skm_versions(id TEXT PRIMARY KEY,family_id TEXT NOT NULL REFERENCES skm_version_families(id),
          skill_id TEXT NOT NULL UNIQUE REFERENCES skills(id),data TEXT NOT NULL,created_at TEXT);
        CREATE TABLE IF NOT EXISTS skm_import_previews(id TEXT PRIMARY KEY,hash TEXT NOT NULL,data TEXT NOT NULL,state TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS skm_version_confirmations(id TEXT PRIMARY KEY,preview_id TEXT,preview_hash TEXT,version_id TEXT,
          prior_head TEXT,actor TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS skm_source_observations(family_id TEXT PRIMARY KEY,status TEXT,data TEXT,checked_at TEXT);
        ''')


def records(db=None):
    if db is None:
        with core.connect() as conn:return records(conn)
    return [dict(json.loads(r['data']),version_id=r['id'],family_id=r['family_id'],
                 version_role='当前登记' if r['head']==r['id'] else '历史版本')
            for r in db.execute('SELECT v.*,f.head FROM skm_versions v JOIN skm_version_families f ON f.id=v.family_id ORDER BY v.created_at,v.id')]


def authorities():
    from .config import authorities as contract_authorities
    return contract_authorities()


def build_snapshot(items,sid,name,version,folder,original_root):
    """Structural module candidates; all source bytes/rules remain in closures."""
    files=[];nodes=[];spans=[];edges=[];groups={};file_nodes={};texts={};unresolved=[]
    timestamp=core.now()
    def node(title,kind,parent=None,file=None,start=None,end=None,anchor=''):
        nid=core.ident();n={'id':nid,'skill_id':sid,'file_id':file['id'] if file else None,'parent_id':parent,'title':title[:500],
        'kind':kind,'summary':'来源结构候选；接口与生产语义待独立核验','summary_kind':'来源结构','anchor':anchor,
        'fingerprint':core.digest([title,kind,start,end]),'state':'结构已定位 / 独立复用待审','ordinal':len(nodes),
        'revision':1,'active':1,'created_at':timestamp,'updated_at':timestamp};nodes.append(n)
        if parent:edges.append({'id':core.ident(),'skill_id':sid,'source_id':parent,'target_id':nid,'kind':'contains',
        'confidence':1.0,'review_state':'源结构','evidence':'原文件/标题层级；不是执行顺序','revision':1})
        if file and start is not None:spans.append({'id':core.ident(),'node_id':nid,'file_id':file['id'],
          'start_line':start,'end_line':end,'sha256':file['sha256'],'version':version,'role':'完整原文范围'})
        return nid
    titles={}
    for p,raw,sha in items:
        try:txt=raw.decode('utf-8-sig');texts[p]=txt
        except UnicodeDecodeError:continue
        h=re.search(r'^#\s+(.+)$',txt,re.M)
        if h:titles[p]=h.group(1)
    group_names={'entry':'入口与总规则','references':'参考规则与规范','scripts':'工具定义与校验','assets':'资源与模板','support':'配套规则与文件'}
    root_node=node(name,'skill')
    for p,raw,sha in items:
        parts=PurePosixPath(p).parts
        if len(parts)>=3 and parts[0]=='modules':
            group='modules/'+parts[1];title=titles.get(group+'/SKILL.md',parts[1])
        else:
            group='entry' if p=='SKILL.md' else parts[0] if parts[0] in ('references','scripts','assets') else 'support'
            title=group_names[group]
        if group not in groups:groups[group]=node(title,'theme',root_node)
        text=texts.get(p);lines=len(text.splitlines()) if text is not None else 0
        file={'id':core.ident(),'path':p,'sha256':sha,'bytes':len(raw),'encoding':'utf-8' if text is not None else 'binary',
              'line_count':lines,'state':'完整原文已索引' if text is not None else '附件元数据；内容未审'};files.append(file)
        fn=node(titles.get(p,p),'file',groups[group],file,1,lines) if lines else node(p,'file',groups[group],file)
        file_nodes[p]=fn
        if text is None:continue
        if p.lower().endswith('.md'):
            parsed=core.parse_blocks(text,p);block_ids=[];source_lines=text.splitlines()
            for b in parsed:
                parent=block_ids[b['parent_index']] if b['parent_index'] is not None else fn
                bid=node(b['title'],b['kind'],parent,file,b['start'],b['end'],b['anchor']);block_ids.append(bid)
                # Entry H2 headings are visible module candidates as well as preserved original hierarchy.
                if p=='SKILL.md' and b['kind']=='section' and re.match(r'^##\s+',source_lines[b['start']-1]):
                    key='entry-section-'+str(b['start']);theme=node(b['title'],'theme',root_node)
                    groups[key]=theme
                    edges.append({'id':core.ident(),'skill_id':sid,'source_id':theme,'target_id':bid,'kind':'contains',
                      'confidence':1.0,'review_state':'原入口二级标题候选','evidence':'原SKILL.md二级标题；不证明可独立执行','revision':1})
        elif lines:node('完整文件内容','rule_candidate',fn,file,1,lines)
    if len(groups)>60:raise ValueError('独立模块组超过60，需完整分批组装方案，不截断')
    for p,text in texts.items():
        matches=list(re.finditer(r'\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)',text))
        matches+=list(re.finditer(r'`([^`\n]+\.(?:md|json|yaml|yml|csv|txt|py|js|ts|html))`',text,re.I))
        matches+=list(re.finditer(r'\b((?:references|modules|scripts|assets)/[^\s()<>"`]+?\.(?:md|json|yaml|yml|csv|txt|py|js|ts|html))\b',text,re.I))
        seen_refs=set()
        for match in sorted(matches,key=lambda m:m.start()):
            token=match.group(1);line=text[:match.start()].count('\n')+1
            if (token,line) in seen_refs:continue
            seen_refs.add((token,line))
            if token.startswith(('#','http:','https:','mailto:','data:')):continue
            target=token.split('#')[0]
            try:
                from urllib.parse import unquote
                candidate=os.path.normpath(str(PurePosixPath(p).parent/unquote(target))).replace('\\','/')
                candidate=relative(candidate)
            except ValueError:candidate=''
            if candidate in file_nodes:
                edges.append({'id':core.ident(),'skill_id':sid,'source_id':file_nodes[p],'target_id':file_nodes[candidate],
                'kind':'references','confidence':1.0,'review_state':'明确文件引用','evidence':json.dumps({'path':p,'line':line,'token':token},ensure_ascii=False),'revision':1})
            else:unresolved.append({'id':core.ident(),'skill_id':sid,'source_id':file_nodes[p],'path':p,'line':line,
            'token':token,'reason':'引用或输出文件未在来源中定位；依赖完整性待核验','revision':1})
    return {'kind':'IMMUTABLE_SOURCE_VERSION_CANDIDATE','skill':{'id':sid,'name':name,'version':version,'root':str(folder),
      'description':'完整来源结构模块；接口与独立复用语义待核验','original_root':original_root},'files':files,'nodes':nodes,
      'edges':edges,'spans':spans,'full_manifest':manifest(items),'source_scope':None,'authorities':authorities(),
      'unresolved':unresolved,'not_proven':['没有执行Skill','结构候选不是可独立运行模块','未推断业务顺序；未识别关系保留为待补连线']}


def make_blueprint(snap,sha):
    themes=[n for n in snap['nodes'] if n['kind']=='theme'];sid=snap['skill']['id']
    return {'key':'import-'+sid,'source_id':sid,'name':snap['skill']['name'],'version':snap['skill']['version'],'snapshot':sha,
      'instances':[{'key':'module-'+str(i),'node_id':n['id'],'x':(i%3)*350,'y':(i//3)*210,
        'role':'来源结构模块','note':n['title']+'；完整来源结构范围，连接关系尚待按原文确认'} for i,n in enumerate(themes)],
      'links':[],'warnings':['本来源自动提取了完整模块范围；没有从文件排列编造执行连线。请依据原文设置交接关系。',
                             '总入口与入口标题模块保留原层级，可能共享范围；共享规则不可重复执行。']}


def scoped_items(root,head):
    """Preserve the user's exact execution/deferred split, without importing history."""
    old=json.loads(Path(head['path']).read_bytes());indexed={f['path'] for f in old['files']}
    expected={f['path']:f for f in old['full_manifest']};actual=[]
    base=Path(root)
    for part in (base,*base.parents):
        if part.is_symlink() or (part.exists() and getattr(part.stat(),'st_file_attributes',0)&0x400):raise ValueError('拒绝链接来源')
    if not base.is_dir():raise ValueError('原目录不存在')
    import hashlib
    for folder,dirs,names in os.walk(base,followlinks=False):
        for name in dirs+names:
            p=Path(folder)/name
            if p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400:raise ValueError('拒绝来源链接')
        for name in names:
            p=Path(folder)/name;relative_path=relative(p.relative_to(base).as_posix())
            if len(actual)>=core.MAX_FILES:raise ValueError('来源文件数超限')
            h=hashlib.sha256();size=0
            with p.open('rb') as stream:
                for chunk in iter(lambda:stream.read(65536),b''):h.update(chunk);size+=len(chunk)
            actual.append({'path':relative_path,'bytes':size,'sha256':h.hexdigest()})
    actual.sort(key=lambda f:f['path'])
    if {f['path'] for f in actual}!=set(expected):raise ValueError('来源展示范围的文件清单变化，请先明确新版执行/暂缓范围；旧视图完整保留')
    if any(f['sha256']!=expected[f['path']]['sha256'] for f in actual if f['path'] not in indexed):
        raise ValueError('暂缓历史/证据资料也发生变化，请先确认准确新版范围；不自动纳入资料库')
    return validate_items(core.inventory(base,include_paths=indexed)),actual


def preview(root='',upload_id='',name='',version='',family_id=''):
    if bool(root)==bool(upload_id):raise ValueError('请选择一个准确目录或已完整上传的包')
    if root:
        supplied=Path(root)
        if not supplied.is_absolute():raise ValueError('请提供准确的绝对目录')
        for part in (supplied,*supplied.parents):
            if part.is_symlink() or (part.exists() and getattr(part.stat(),'st_file_attributes',0)&0x400):
                raise ValueError('拒绝链接或重解析点来源')
        source_root=supplied.resolve(strict=True)
        if source_root.is_relative_to(core.RUNTIME.resolve()) or core.RUNTIME.resolve().is_relative_to(source_root):
            raise ValueError('源Skill不能与工作台写入目录重叠；请选择独立源目录')
        root=str(source_root)
    head=None
    if family_id:
        head=next((r for r in records() if r['family_id']==family_id and r['version_role']=='当前登记'),None)
        if not head:raise ValueError('更新来源家族不存在')
    if head and head.get('source_scope'):
        if not root:raise ValueError('该来源保留执行/暂缓范围，请通过准确完整目录预览，不以无范围上传覆盖')
        items,full_manifest=scoped_items(root,head)
    else:
        items=read_folder(root) if root else uploaded(upload_id);full_manifest=manifest(items)
    meta=metadata(next(raw for p,raw,sha in items if p=='SKILL.md'))
    name=(name or meta['name']).strip();version=(version or meta['version']).strip()
    if not name or len(name)>100 or not version or len(version)>100:raise ValueError('请明确确认来源名称及版本（无版本声明时可填写导入快照日期）')
    family=None;prior=''
    with core.connect() as db:
        if family_id:
            family=db.execute('SELECT * FROM skm_version_families WHERE id=?',(family_id,)).fetchone()
            if not family:raise ValueError('更新来源家族不存在')
            prior=family['head']
            head=next(r for r in records(db) if r['version_id']==prior)
        # Same exact path must be consciously assigned to its family, not silently duplicated.
        same=[r for r in records(db) if root and os.path.normcase(os.path.abspath(r['original_root']))==os.path.normcase(os.path.abspath(root))]
        if same and not family_id:raise ValueError('该目录已登记，请选择对应Skill进行新版预览')
        if same and family_id not in {r['family_id'] for r in same}:raise ValueError('此目录属于另一已登记Skill，不能错接到当前家族；请选择正确来源')
    pid=core.ident();vid=core.ident();sid=core.ident();target=STORE/vid;files=target/'files'
    freeze(items,files)
    snap=build_snapshot(items,sid,name,version,files,str(Path(root).absolute()) if root else '')
    if head and head.get('source_scope'):
        snap['source_scope']=dict(head['source_scope'],source_version=version,original_root=snap['skill']['original_root'],
                                  full_manifest=full_manifest)
        snap['full_manifest']=full_manifest
    raw=core.canonical(snap);sha=core.digest(raw);(target/'catalog.json').write_bytes(raw)
    bp=make_blueprint(snap,sha);bpraw=core.canonical(bp);(target/'blueprint.json').write_bytes(bpraw)
    data={'preview_id':pid,'version_id':vid,'skill_id':sid,'family_id':family_id,'prior_head':prior,'name':name,'version':version,
      'original_root':snap['skill']['original_root'],'path':str(target/'catalog.json'),'sha256':sha,'files_root':str(files),
      'blueprint_path':str(target/'blueprint.json'),'blueprint_sha256':core.digest(bpraw),'manifest':manifest(items),
      'module_titles':[n['title'] for n in snap['nodes'] if n['kind']=='theme'],'nodes':len(snap['nodes']),
      'unresolved_count':len(snap['unresolved']),'unresolved':snap['unresolved'],'upload_id':upload_id,
      'full_manifest':full_manifest,'source_scope':snap['source_scope'],
      'warning':'完整原文已冻结；结构模块候选，独立复用和执行顺序待核验。缺失引用不会伪装已完整。'}
    h=core.digest(data)
    with core.GUARD,core.connect() as db:db.execute('INSERT INTO skm_import_previews VALUES(?,?,?,?,?)',(pid,h,core.canonical(data).decode(),'待确认',core.now()))
    return dict(data,preview_hash=h,file_count=len(items),total_bytes=sum(len(b) for p,b,sha in items))


def verify_record(record):
    raw=Path(record['path']).read_bytes()
    if core.digest(raw)!=record['sha256']:raise ValueError('冻结版本清单漂移')
    snap=json.loads(raw);items=read_folder(record['files_root'])
    if any(record[key]!=snap['skill'][key.replace('skill_id','id')] for key in ('skill_id','name','version')):
        raise ValueError('版本身份与冻结来源不一致')
    if record['original_root']!=snap['skill'].get('original_root',snap['skill']['root']):raise ValueError('版本原来源目录漂移')
    # Scoped historical views intentionally contain only indexed execution files.
    expected=[{'path':f['path'],'bytes':f['bytes'],'sha256':f['sha256']} for f in snap['files']]
    if manifest(items)!=sorted(expected,key=lambda x:x['path']):raise ValueError('冻结版本原字节漂移')
    if record.get('blueprint_path') and core.digest(Path(record['blueprint_path']).read_bytes())!=record['blueprint_sha256']:raise ValueError('来源组装模板漂移')
    return snap


def confirm(pid,preview_hash,relation_confirmed=False,missing_ack=False):
    with GUARD,core.GUARD,core.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM skm_import_previews WHERE id=?',(pid,)).fetchone()
        if not row or row['hash']!=preview_hash:raise ValueError('准确预览校验不一致，请重新预览')
        d=json.loads(row['data'])
        if row['state']=='已接入':return {'id':d['skill_id'],'version_id':d['version_id'],'family_id':d['family_id'],'already_confirmed':True}
        if row['state']!='待确认':raise ValueError('预览不可接入')
        if core.digest(d)!=row['hash']:raise ValueError('预览内容已漂移，请重新预览')
        authorities()
        if d['family_id'] and not relation_confirmed:raise ValueError('请明确确认此来源属于选定Skill的新版本')
        if d['unresolved_count'] and not missing_ack:raise ValueError('来源存在缺失引用，请确认以依赖未完整的结构候选接入')
        snap=verify_record(d)
        scoped_head=next((r for r in records(db) if r['version_id']==d['prior_head']),None) if d.get('source_scope') else None
        actual,full_manifest=scoped_items(d['original_root'],scoped_head) if scoped_head else (read_folder(d['original_root']) if d['original_root'] else uploaded(d['upload_id']),d['full_manifest'])
        if manifest(actual)!=d['manifest']:raise ValueError('预览后源文件变化，拒绝接入；请重新预览')
        if full_manifest!=d['full_manifest']:raise ValueError('完整来源清单变化，请重新预览')
        if d['family_id']:
            head=db.execute('SELECT head FROM skm_version_families WHERE id=?',(d['family_id'],)).fetchone()
            if not head or head['head']!=d['prior_head']:raise ValueError('当前版本已被另一确认更新，请重新预览')
            old=next(r for r in records(db) if r['version_id']==head['head'])
            oldsnap=json.loads(Path(old['path']).read_bytes())
            if [{p: f[p] for p in ('path','sha256')} for f in d['full_manifest']]==[{p:f[p] for p in ('path','sha256')} for f in sorted(oldsnap.get('full_manifest',oldsnap['files']),key=lambda f:f['path'])] and d['version']==old['version']:
                raise ValueError('内容与版本未变化，无需创建重复版本')
        else:
            d['family_id']=core.ident()
            db.execute('INSERT INTO skm_version_families VALUES(?,?,?,?)',(d['family_id'],d['name'],None,core.now()))
        # Commit map, source pool identity and current head together in one SQLite transaction.
        sid=d['skill_id'];stamp=core.now()
        db.execute('INSERT INTO skills VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,d['name'],snap['skill']['description'],d['files_root'],d['version'],d['sha256'],1,'冻结版本 / 语义待审',stamp,None))
        item_text={p:raw for p,raw,sha in actual}
        for f in snap['files']:
            raw=item_text[f['path']];text=raw.decode('utf-8-sig') if f['encoding']=='utf-8' else None
            db.execute('INSERT INTO source_files VALUES(?,?,?,?,?,?,?,?,?,?,?)',(f['id'],sid,f['path'],f['sha256'],f['bytes'],f['encoding'],text,f['line_count'],f['state'],1,0))
            if text:db.execute('INSERT INTO source_search(body,skill_id,file_id) VALUES(?,?,?)',(text,sid,f['id']))
        def insert(table,entries):
            for entry in entries:
                keys=list(entry);db.execute(f"INSERT INTO {table}({','.join(keys)}) VALUES({','.join('?' for k in keys)})",[entry[k] for k in keys])
        insert('nodes',snap['nodes']);insert('source_spans',snap['spans']);insert('edges',snap['edges']);insert('unresolved',snap['unresolved'])
        db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)',(core.ident(),sid,1,stamp,core.canonical(d['manifest']).decode(),'准确预览确认的不可变来源版本'))
        db.execute('INSERT INTO skm_versions VALUES(?,?,?,?,?)',(d['version_id'],d['family_id'],sid,core.canonical(d).decode(),stamp))
        db.execute('UPDATE skm_version_families SET head=? WHERE id=?',(d['version_id'],d['family_id']))
        db.execute('INSERT INTO skm_version_confirmations VALUES(?,?,?,?,?,?,?)',(core.ident(),pid,preview_hash,d['version_id'],d['prior_head'],'本机用户准确预览确认',stamp))
        db.execute('UPDATE skm_import_previews SET state=?,data=? WHERE id=?',('已接入',core.canonical(d).decode(),pid))
        final,final_full=scoped_items(d['original_root'],scoped_head) if scoped_head else (read_folder(d['original_root']) if d['original_root'] else uploaded(d['upload_id']),d['full_manifest'])
        if manifest(final)!=d['manifest']:raise ValueError('确认提交期间源发生变化，整个接入已回滚')
        if final_full!=d['full_manifest']:raise ValueError('确认期间完整范围变化，已回滚')
        return {'id':sid,'version_id':d['version_id'],'family_id':d['family_id'],'already_confirmed':False}


def check_source(family_id):
    versions=[r for r in records() if r['family_id']==family_id];head=next((r for r in versions if r['version_role']=='当前登记'),None)
    if not head:raise ValueError('来源家族不存在')
    try:
        snap=verify_record(head)
        if not head['original_root']:status='导入快照；手动提供新版包';detail={'changes':[]}
        elif head.get('source_scope'):
            # Entire original manifest, including deferred material, is observed without indexing/media reads.
            actual={}
            for folder,dirs,names in os.walk(head['original_root'],followlinks=False):
                for name in dirs+names:
                    p=Path(folder)/name
                    if p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400:raise ValueError('来源出现链接')
                for name in names:
                    p=Path(folder)/name
                    if len(actual)>=core.MAX_FILES:raise ValueError('来源文件数超限')
                    import hashlib
                    h=hashlib.sha256()
                    with p.open('rb') as stream:
                        for chunk in iter(lambda:stream.read(65536),b''):h.update(chunk)
                    actual[p.relative_to(head['original_root']).as_posix()]=h.hexdigest()
            expected={f['path']:f['sha256'] for f in snap['full_manifest']}
            changed=[p for p in sorted(set(actual)|set(expected)) if actual.get(p)!=expected.get(p)]
            status='待同步' if changed else '原目录一致';detail={'changes':changed,'scope':'旧执行视图不自动扩展'}
        else:
            actual={p:sha for p,raw,sha in read_folder(head['original_root'])}
            expected={f['path']:f['sha256'] for f in snap.get('full_manifest',snap['files'])}
            changed=[p for p in sorted(set(actual)|set(expected)) if actual.get(p)!=expected.get(p)]
            status='待同步' if changed else '原目录一致';detail={'changes':changed}
    except (OSError,ValueError) as exc:status='来源异常 / 历史保留';detail={'error':str(exc),'changes':[]}
    with core.GUARD,core.connect() as db:
        db.execute('INSERT OR REPLACE INTO skm_source_observations VALUES(?,?,?,?)',(family_id,status,core.canonical(detail).decode(),core.now()))
    return dict(detail,family_id=family_id,status=status,version=head['version'],automatic_adoption=False)


def decorate(item,db):
    match=next((r for r in records(db) if r['skill_id']==item['id']),None)
    if not match:return item
    observation=db.execute('SELECT * FROM skm_source_observations WHERE family_id=?',(match['family_id'],)).fetchone()
    pending=' · 原目录'+observation['status'] if match['version_role']=='当前登记' and observation and observation['status'] in ('待同步','来源异常 / 历史保留') else ''
    return dict(item,family_id=match['family_id'],version_id=match['version_id'],version_role=match['version_role'],
      original_root=match['original_root'],source_status='历史冻结版本；原目录核对以当前登记版为准' if match['version_role']=='历史版本' else observation['status'] if observation else '尚未核对原目录',
      state=item['state']+' · '+match['version_role']+pending)


def current_node(nid,db):
    row=db.execute('SELECT n.*,s.name skill_name,s.version,s.root,s.state skill_state FROM nodes n JOIN skills s ON s.id=n.skill_id WHERE n.id=? AND n.active=1',(nid,)).fetchone()
    if not row:raise ValueError('节点不存在或已失效')
    rec=next((r for r in records(db) if r['skill_id']==row['skill_id']),None)
    if not rec:return core.current_node(nid,db)
    if core.digest(Path(rec['path']).read_bytes())!=rec['sha256']:raise ValueError('冻结来源清单漂移，停止读取')
    result=dict(row);result.update({k:rec[k] for k in ('family_id','version_id','version_role','original_root')})
    spans=[]
    for s in db.execute('SELECT sp.*,f.path,f.text FROM source_spans sp JOIN source_files f ON f.id=sp.file_id WHERE sp.node_id=?',(nid,)):
        raw=core.safe_file(rec['files_root'],s['path']).read_bytes()
        if core.digest(raw)!=s['sha256']:raise ValueError('冻结原文漂移')
        text=raw.decode('utf-8-sig');lines=text.splitlines(keepends=True)
        spans.append({k:s[k] for k in ('path','start_line','end_line','sha256','version','role')}|{'text':''.join(lines[s['start_line']-1:s['end_line']])})
    result['spans']=spans;result['context']=None
    if row['file_id']:
        f=db.execute('SELECT * FROM source_files WHERE id=?',(row['file_id'],)).fetchone()
        raw=core.safe_file(rec['files_root'],f['path']).read_bytes()
        if core.digest(raw)!=f['sha256']:raise ValueError('冻结原文漂移')
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:text=None
        result['context']={'path':f['path'],'sha256':f['sha256'],'text':text,'line_count':f['line_count'],'state':f['state']}
    result['children']=[dict(r) for r in db.execute("SELECT DISTINCT n.id,n.title,n.kind,n.ordinal FROM edges e JOIN nodes n ON n.id=e.target_id WHERE e.source_id=? AND e.kind='contains' AND n.active=1 AND n.id NOT IN(SELECT node_id FROM navigation_legacy) ORDER BY n.ordinal",(nid,))]
    result['edges']=[dict(r) for r in db.execute("SELECT e.*,n.title target_title FROM edges e JOIN nodes n ON n.id=e.target_id WHERE (e.source_id=? OR e.target_id=?) AND e.kind!='contains'",(nid,nid))]
    result['unresolved']=[dict(r) for r in db.execute('SELECT * FROM unresolved WHERE source_id=?',(nid,))]
    return result


from fastapi import APIRouter
router=APIRouter(prefix='/api/imports')

@router.post('/discover')
def api_discover(body:dict):return discover(body.get('root',''),body.get('depth',3))

@router.post('/uploads')
def api_upload(body:dict):return upload_start(body.get('files'),body.get('kind','folder'))

@router.post('/uploads/{uid}/chunk')
def api_chunk(uid:str,body:dict):return upload_chunk(uid,body.get('path',''),body.get('offset'),body.get('data',''))

@router.post('/preview')
def api_preview(body:dict):
    try:return preview(**{k:body.get(k,'') for k in ('root','upload_id','name','version','family_id')})
    except (zipfile.BadZipFile,RuntimeError,NotImplementedError) as exc:raise ValueError('ZIP包损坏或压缩格式不支持；没有接入') from exc

@router.post('/confirm')
def api_confirm(body:dict):return confirm(body.get('preview_id',''),body.get('preview_hash',''),body.get('relation_confirmed') is True,body.get('missing_ack') is True)

@router.get('/versions')
def api_versions():
    with core.connect() as db:
        obs={r['family_id']:dict(r) for r in db.execute('SELECT * FROM skm_source_observations')}
        return [{k:r[k] for k in ('skill_id','family_id','version_id','name','version','version_role','original_root','sha256')}|{
          'source_status':'历史冻结版本；原目录核对以当前登记版为准' if r['version_role']=='历史版本' else obs.get(r['family_id'],{}).get('status','尚未核对原目录')} for r in records(db)]

@router.post('/check/{family_id}')
def api_check(family_id:str):return check_source(family_id)
