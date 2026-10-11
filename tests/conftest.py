import os, tempfile
from pathlib import Path
import pytest

_parent = Path(os.environ.get('SKM_TEST_ROOT', tempfile.gettempdir()))
_parent.mkdir(parents=True, exist_ok=True)
_runtime = tempfile.TemporaryDirectory(prefix='skill-workbench-test-',dir=_parent)
os.environ['SKM_RUNTIME'] = _runtime.name
os.environ['SKM_PORT'] = '8770'
from skm import core, version_sources, assembly_bridge

@pytest.fixture(autouse=True)
def isolated_store():
    core.init();version_sources.init()
    with core.connect() as db:
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'source_search_%'").fetchall():
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('DELETE FROM "'+row['name']+'"')
    assembly_bridge._backend=None
    from skm import draft_engine
    draft_engine.CATALOG={'skill':{'id':'','name':'','version':'','root':''},'files':[],'nodes':[],'edges':[],'spans':[],'authorities':[]}
    draft_engine.FACTS={};draft_engine.FILES={};draft_engine.CHILDREN={}
    draft_engine.init()
    with draft_engine.db() as db:
        db.execute('DELETE FROM drafts');db.execute('DELETE FROM events')
    yield
