from __future__ import annotations

import asyncio
import json
import os
import secrets
import sqlite3
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import core, version_sources

SESSION = secrets.token_urlsafe(32)
CSRF = secrets.token_urlsafe(32)
PORT = int(os.environ.get('SKM_PORT', '8770'))
COOKIE = 'skm_session_' + str(PORT)
WEB = Path(os.environ.get('SKM_WEB', str(core.PROJECT / 'apps/web/dist')))
STOP = threading.Event()


def poll_sources():
    observers={};pending={};event_lock=threading.Lock();last_full=0
    class Handler(FileSystemEventHandler):
        def __init__(self,sid):self.sid=sid
        def on_any_event(self,event):
            # Debounce writes/renames/deletes. Source open/read events never trigger loops.
            if event.event_type in ('created','modified','deleted','moved'):
                with event_lock:pending[self.sid]=time.monotonic()
    try:
        while not STOP.wait(2):
            with core.connect() as db:
                managed={r['skill_id']:r for r in version_sources.records(db)}
                registered=[dict(r) for r in db.execute('SELECT id,root FROM skills')]
            for item in registered:
                if item['id'] in managed:continue
                if not item['root'].startswith('\\\\') and item['id'] not in observers:
                    try:
                        observer=Observer();observer.schedule(Handler(item['id']),item['root'],recursive=True);observer.start();observers[item['id']]=observer
                    except OSError:
                        pass  # Periodic complete reconciliation remains authoritative.
            stamp=time.monotonic()
            with event_lock:
                ready={sid for sid,t in pending.items() if stamp-t>=2}
                for sid in ready:pending.pop(sid,None)
            if stamp-last_full>=30:
                ready.update(item['id'] for item in registered);last_full=stamp
            for sid in ready:
                try:
                    if sid in managed:
                        if managed[sid]['version_role']=='当前登记':version_sources.check_source(managed[sid]['family_id'])
                    else:core.scan(sid)
                except (OSError,ValueError):pass
    finally:
        for observer in observers.values():observer.stop()
        for observer in observers.values():observer.join(timeout=2)


@asynccontextmanager
async def lifespan(app):
    core.init()
    version_sources.init()
    STOP.clear()
    worker = threading.Thread(target=poll_sources, daemon=True)
    worker.start()
    yield
    STOP.set()
    worker.join(timeout=3)


app = FastAPI(title='Skill 知识与组装工作台', docs_url=None, redoc_url=None, lifespan=lifespan)


@app.middleware('http')
async def local_gate(request: Request, call_next):
    allowed = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
    host = request.headers.get('host', '')
    origin = request.headers.get('origin')
    top_navigation=(request.method=='GET' and request.url.path=='/' and request.headers.get('sec-fetch-mode')=='navigate' and request.headers.get('sec-fetch-dest')=='document')
    if host not in allowed or (origin and origin not in {f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'} and not top_navigation):
        return JSONResponse({'detail':'只接受本机页面访问'},status_code=403)
    if request.headers.get('sec-fetch-site') == 'cross-site' and not top_navigation:
        return JSONResponse({'detail':'拒绝跨站访问'},status_code=403)
    if request.url.path.startswith('/api/') and request.url.path != '/api/session':
        if not secrets.compare_digest(request.cookies.get(COOKIE,''),SESSION):
            return JSONResponse({'detail':'请刷新本机页面建立会话'},status_code=401)
        if request.method not in ('GET','HEAD') and not secrets.compare_digest(request.headers.get('x-skm-csrf',''),CSRF):
            return JSONResponse({'detail':'请求校验失败'},status_code=403)
        if int(request.headers.get('content-length','0')) > 2 * 1024 * 1024:
            return JSONResponse({'detail':'请求包超过2MiB，请拆批'},status_code=413)
        if request.method not in ('GET','HEAD') and len(await request.body())>2*1024*1024:
            return JSONResponse({'detail':'请求包超过2MiB，请拆批'},status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'"
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'no-cache'
    return response


@app.exception_handler(ValueError)
async def bad_input(request, exc):
    return JSONResponse({'detail':str(exc)},status_code=409)


@app.exception_handler(OSError)
async def source_error(request, exc):
    return JSONResponse({'detail':'源文件暂不可读；上次地图保留。'+str(exc)},status_code=409)


@app.get('/api/session')
def session():
    response=JSONResponse({'csrf':CSRF,'actor':'本机用户','mode':'只读Skill / 本地维护工作台'})
    response.set_cookie(COOKIE,SESSION,httponly=True,samesite='strict',path='/')
    return response


@app.get('/api/skills')
def skills():
    with core.connect() as db:
        result=[]
        for row in db.execute('SELECT * FROM skills ORDER BY name'):
            item={k:row[k] for k in ('id','name','description','root','version','revision','state','last_sync','error')}
            item['navigation_adapter']='FILE_STRUCTURE_CANDIDATE'
            if db.execute('SELECT 1 FROM navigation_views WHERE skill_id=?',(row['id'],)).fetchone():
                item['navigation_adapter']='SOURCE_CONTENT_NAVIGATION'
                item['description']=item['description'].replace('目录分类与业务语义待核验','独立复用业务语义待核验').replace('分类与独立复用语义待核验','独立复用语义待核验')
            item['counts']={r['kind']:r['n'] for r in db.execute('SELECT kind,count(*) n FROM nodes WHERE skill_id=? AND active=1 AND id NOT IN(SELECT node_id FROM navigation_legacy) GROUP BY kind',(row['id'],))}
            item['files']=db.execute('SELECT count(*) FROM source_files WHERE skill_id=? AND deleted=0',(row['id'],)).fetchone()[0]
            item['unresolved']=db.execute('SELECT count(*) FROM unresolved WHERE skill_id=?',(row['id'],)).fetchone()[0]
            item['pending']=db.execute("SELECT count(*) FROM change_requests WHERE skill_id=? AND state!='已归档'",(row['id'],)).fetchone()[0]
            result.append(version_sources.decorate(item,db))
        return result


@app.post('/api/skills')
def add_skill(payload: dict):
    if not payload.get('root') or not payload.get('name'):
        raise ValueError('请填写准确根目录和名称；不会自动选择其它Skill')
    raise ValueError('请使用“导入与同步”预览并确认准确来源；原登记入口不再绕过版本确认')


@app.get('/api/skills/{sid}/tree')
def tree(sid: str):
    with core.connect() as db:
        return {'nodes':[dict(r) for r in db.execute('''SELECT n.id,n.title,n.kind,n.parent_id,n.summary,n.state,n.ordinal,
          n.updated_at,f.path FROM nodes n LEFT JOIN source_files f ON f.id=n.file_id WHERE n.skill_id=? AND n.active=1 AND n.id NOT IN(SELECT node_id FROM navigation_legacy) ORDER BY n.ordinal''',(sid,))],
                'edges':[dict(r) for r in db.execute('SELECT source_id,target_id,kind,confidence,review_state,evidence FROM edges WHERE skill_id=? AND source_id NOT IN(SELECT node_id FROM navigation_legacy) AND target_id NOT IN(SELECT node_id FROM navigation_legacy)',(sid,))]}


@app.get('/api/nodes/{nid}')
def node(nid: str):
    with core.connect() as db:
        detail=version_sources.current_node(nid,db)
        detail.pop('root',None)
        detail['breadcrumb']=core.breadcrumbs(db,nid)
        return detail


@app.get('/api/search')
def search(q: str, skill: str|None=None):
    if len(q)>200:
        raise ValueError('搜索词过长')
    started=time.perf_counter()
    result=core.search(q,skill)
    with core.connect() as db:
        for item in result:
            info=version_sources.decorate({'id':item['skill_id'],'state':item['state']},db)
            item.update({k:info[k] for k in ('version_role','source_status') if k in info})
    return {'results':result,'milliseconds':round((time.perf_counter()-started)*1000,2),'limit':60}


@app.post('/api/skills/{sid}/scan')
def refresh(sid: str):
    managed=next((r for r in version_sources.records() if r['skill_id']==sid),None)
    if managed:
        return version_sources.check_source(managed['family_id'])
    return core.scan(sid)


@app.get('/api/skills/{sid}/inventory')
def files(sid: str):
    with core.connect() as db:
        return {'files':[dict(r) for r in db.execute('SELECT id,path,sha256,bytes,encoding,line_count,state,deleted FROM source_files WHERE skill_id=? ORDER BY path',(sid,))],
                'unresolved':[dict(r) for r in db.execute('SELECT path,line,token,reason,source_id FROM unresolved WHERE skill_id=?',(sid,))],
                'history':[dict(r) for r in db.execute('SELECT revision,created_at,summary FROM revisions WHERE skill_id=? ORDER BY revision DESC LIMIT 30',(sid,))]}


@app.get('/api/audit')
def events():
    with core.connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM audit_events ORDER BY created_at DESC LIMIT 100')]


@app.get('/api/health')
def health():
    return {'ok':True,'protected_source_writes':False,'worker_bridge':'结构化任务包人工导入导出','semantic_review':'尚待独立人工审查'}


@app.post('/api/backup')
def backup_database():
    from .ops import backup
    return backup()


# Workflow routes are mounted only after their module passes separate validation.
def mount_workflow(router):
    app.include_router(router)


from .workflow import router as workflow_router
mount_workflow(workflow_router)

from .assembly_bridge import router as assembly_router
app.include_router(assembly_router)
app.include_router(version_sources.router)
from .release_observations import router as releases_router
app.include_router(releases_router)


if WEB.exists():
    app.mount('/assets',StaticFiles(directory=WEB/'assets'),name='assets')


@app.get('/')
def index():
    if not (WEB/'index.html').exists():
        return JSONResponse({'detail':'本地页面尚未构建'},status_code=503)
    return FileResponse(WEB/'index.html')
