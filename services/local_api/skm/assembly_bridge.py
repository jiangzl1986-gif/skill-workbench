"""Native workbench routes; source remains frozen and drafts use their own DB."""
from __future__ import annotations

import importlib.util
import sys
import threading
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import ValidationError
from . import module_library

router = APIRouter(prefix='/api/assembly')
_backend = None
_load_lock = threading.Lock()

def _import_backend():
    from . import draft_engine
    return draft_engine


def backend():
    global _backend
    if _backend is None:
        with _load_lock:
            if _backend is None:
                try:
                    candidate = _import_backend()
                    from .version_assembly import Adapter
                    candidate = Adapter(candidate)
                    from .composition_adapter import Adapter as CompositionAdapter
                    candidate = CompositionAdapter(candidate)
                except Exception as exc:
                    # Failure stays local to this panel; ordinary map routes remain available.
                    raise HTTPException(503, '组装模块暂不可用，请核对冻结来源与模块目录；知识地图仍可查看。') from exc
                _backend = candidate
    if hasattr(_backend,'ensure_loaded'):
        _backend.ensure_loaded()
    return _backend


def draft_body(module, body):
    try:
        return module.Draft(**body)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_url=False, include_context=False)) from exc


@router.get('/catalog')
def catalog():
    module = backend()
    if hasattr(module, 'library'):
        return module.library()
    # Only genuinely frozen, verified sources enter the pool. Other Skills are not guessed or auto-ingested.
    return module_library.combine([module_library.from_snapshot(module.CATALOG, module.catalog())])


@router.get('/source/{nid}')
def source(nid: str):
    return backend().source_text(nid)


@router.get('/drafts')
def drafts():
    return backend().drafts()


@router.get('/drafts/{did}')
def draft(did: str):
    return backend().draft(did)


@router.post('/drafts')
def save(body: dict):
    module = backend()
    return module.save(draft_body(module, body))


@router.post('/check')
def check(body: dict):
    module = backend()
    return module.inspect(draft_body(module, body))


@router.get('/drafts/{did}/package')
def package(did: str):
    module = backend()
    # Preserve the exact canonical bytes and Python numeric values of the frozen package.
    return Response(module.canonical(module.package(did)), media_type='application/json')


@router.get('/health')
def health():
    module = backend()
    module.verify_snapshot()
    return {'ok': True, 'source_writes': False, 'generation_ready': False,
            'database': '独立SQLite', 'entry': '统一工作台 /api/assembly'}
