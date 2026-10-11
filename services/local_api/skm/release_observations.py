"""Bounded, read-only release observations and manual analysis handoff.

Never installs, adopts a workbench version, executes source code or sends a chat.
Expected hashes come from frozen external release receipts, not this checker.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sqlite3
import stat
import threading
import time
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from . import core, version_sources

CONFIG = core.RUNTIME / 'config/releases.json'
router = APIRouter(prefix='/api/releases')
GUARD = threading.RLock()
_cached = None
_cached_at = 0.0


def safe_path(root: Path, relative: str, checked_dirs=None) -> Path:
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative or any(ord(c) < 32 for c in relative):
        raise ValueError('清单路径不合法')
    p = PurePosixPath(relative)
    if p.is_absolute() or any(v in ('', '.', '..') or v.endswith((' ', '.')) for v in relative.split('/')):
        raise ValueError('清单路径越界')
    target = root.joinpath(*p.parts)
    for candidate in dict.fromkeys([root, *root.parents, target, *target.parents]):
        if checked_dirs is not None and candidate in checked_dirs:
            continue
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('不读取链接或重解析目录')
        if checked_dirs is not None and stat.S_ISDIR(info.st_mode):
            checked_dirs.add(candidate)
    return target


def raw_file(path: Path, path_checked=False) -> bytes:
    if not path_checked:
        path = safe_path(path.parent, path.name)
    with path.open('rb') as f:
        before = os.fstat(f.fileno())
        if before.st_size > core.MAX_BYTES:
            raise ValueError('单文件超过2MiB；本批不扩大准入')
        raw = f.read(core.MAX_BYTES + 1)
        after = os.fstat(f.fileno())
    if len(raw) > core.MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('文件读取期间变化或超限')
    if (after.st_size, after.st_mtime_ns) != (path.stat().st_size, path.stat().st_mtime_ns):
        raise ValueError('文件读取后变化')
    return raw


def sealed_catalog_digest(path: Path) -> str:
    """Existing generated indexes are not newly ingested Skill source files.

    Read 64KiB at a time solely for integrity; no index text enters a handoff.
    The original 2MiB source/request limits and 32MiB batch bound stay intact.
    """
    path = safe_path(path.parent, path.name)
    digest = hashlib.sha256()
    with path.open('rb') as f:
        before = os.fstat(f.fileno())
        if before.st_size > core.MAX_SCAN_BYTES:
            raise ValueError('既有索引超过本批32MiB核对范围')
        while chunk := f.read(64 * 1024):
            digest.update(chunk)
        after = os.fstat(f.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or (after.st_size, after.st_mtime_ns) != (path.stat().st_size, path.stat().st_mtime_ns):
        raise ValueError('登记索引读取期间变化')
    return digest.hexdigest()


def verify_manifest(root: Path, expected: dict) -> dict:
    if not expected or len(expected) > core.MAX_FILES or 'SKILL.md' not in expected:
        raise ValueError('发布清单缺入口、为空或超过5000文件')
    if len({p.casefold() for p in expected}) != len(expected):
        raise ValueError('清单存在大小写重名')
    checked = []; issues = []; total = 0; observed = {}; checked_dirs = set()
    for rel, digest in expected.items():
        if not re.fullmatch(r'[a-fA-F0-9]{64}', digest):
            raise ValueError('发布清单哈希不合法')
        path = safe_path(root, rel, checked_dirs)
        try:
            raw = raw_file(path, path_checked=True); total += len(raw)
            if total > core.MAX_SCAN_BYTES:
                raise ValueError('本源累计超过32MiB')
            actual = hashlib.sha256(raw).hexdigest()
            checked.append(rel)
            observed[rel] = (path.stat().st_size, path.stat().st_mtime_ns)
            if actual != digest.lower():
                issues.append({'path': rel, 'state': '内容不同'})
        except FileNotFoundError:
            issues.append({'path': rel, 'state': '缺失'})
    # Metadata reread closes the common save/replace race across the batch.
    for rel, fingerprint in observed.items():
        p = root.joinpath(*PurePosixPath(rel).parts)
        if not p.exists() or fingerprint != (p.stat().st_size, p.stat().st_mtime_ns):
            raise ValueError('核对期间源发生变化，请重新核对')
    safe_path(root, 'SKILL.md')  # Recheck root ancestry after the complete batch.
    return {'state': 'MANIFEST_MATCH' if not issues else 'MANIFEST_DIFF',
            'checked_files': len(checked), 'expected_files': len(expected), 'bytes': total,
            'issues': issues[:100], 'issue_count': len(issues),
            'scope': '仅发布清单所列文件；未据此验证额外文件、运行语义或视频',
            'entry_sha256': expected['SKILL.md'].lower() if not any(x['path'] == 'SKILL.md' for x in issues) else None}


def loaded_config() -> dict:
    # Explicit local configuration only; no personal source is distributed.
    if not CONFIG.exists():
        return {'families': [], 'current_path': '', 'current_sha256': ''}
    raw = raw_file(CONFIG)
    config = json.loads(raw)
    if not isinstance(config, dict) or not isinstance(config.get('families'), list):
        raise ValueError('发布配置必须包含 families 数组')
    if len(config['families']) > 100:
        raise ValueError('发布配置超过100个来源，请分批核对')
    ids = [f['family_id'] for f in config['families']]
    if len(ids) != len(set(ids)):
        raise ValueError('发布配置来源家族重复')
    config.setdefault('current_path', '')
    config.setdefault('current_sha256', '')
    if raw_file(CONFIG) != raw:
        raise ValueError('发布配置在读取期间变化，停止采用')
    return config


def configured_specs(config: dict, records: list) -> list:
    explicit = {s['family_id']: s for s in config['families']}
    ids = list(dict.fromkeys(v['family_id'] for v in records))
    return [dict({'family_id': fid, 'key': fid, 'paused': False, 'installed_root': ''},
                 **explicit.get(fid, {})) for fid in ids]


def pointer_matches(config: dict) -> bool:
    return bool(config['current_path'] and config['current_sha256'] and
                hashlib.sha256(raw_file(Path(config['current_path']))).hexdigest() == config['current_sha256'])


def registry_records() -> list:
    # No schema initialization, PRAGMA writes or business row mutations.
    path = core.RUNTIME / 'data/skm.sqlite3'
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        records = version_sources.records(db)
        for record in records:
            entries = db.execute("SELECT sha256 FROM source_files WHERE skill_id=? AND path='SKILL.md' AND deleted=0", (record['skill_id'],)).fetchall()
            record['registered_entry_expected_sha256'] = entries[0]['sha256'] if len(entries) == 1 else None
        return records
    finally:
        db.close()


def checked_entry(root: str) -> dict:
    raw = raw_file(safe_path(Path(root), 'SKILL.md'), path_checked=True)
    text = raw.decode('utf-8-sig')
    title = next((line.removeprefix('#').strip() for line in text.splitlines() if line.startswith('# ')), '入口未声明标题')
    return {'entry': str(Path(root) / 'SKILL.md'), 'sha256': hashlib.sha256(raw).hexdigest(), 'title': title[:250],
            'scope': '仅SKILL.md入口字节；不代表全包、正式资格或实际调用'}


def observe_family(spec: dict, current: dict, versions: list, pointer_ok: bool) -> dict:
    row = {'family_id': spec['family_id'], 'name': current['name'], 'key': spec['key'], 'paused': spec['paused'],
           'usage': {'state': 'UNKNOWN', 'label': '尚未登记调用回执', 'note': '生成或复制指令不代表项目已使用；旧项目保持原冻结版本'},
           'versions': [{'version_id': v['version_id'], 'skill_id': v['skill_id'], 'version': v['version'], 'role': v['version_role']} for v in versions],
           'registered': {'version': current['version'], 'skill_id': current['skill_id'], 'version_id': current['version_id'],
                          'original_root': current['original_root'], 'snapshot_root': current['files_root'], 'state': 'SNAPSHOT_UNCHECKED'},
           'formal': {'state': 'UNKNOWN', 'version': None}, 'installed': {'state': 'UNKNOWN', 'root': spec['installed_root']},
           'can_handoff_formal': False, 'can_handoff_registered': False}
    try:
        if sealed_catalog_digest(Path(current['path'])) != current['sha256']:
            raise ValueError('登记清单哈希变化')
        entry = checked_entry(current['files_root'])
        if entry['sha256'] != current.get('registered_entry_expected_sha256'):
            raise ValueError('登记入口与冻结索引中的原hash不一致')
        row['registered'].update(entry, state='ENTRY_VERIFIED')
        row['can_handoff_registered'] = True
    except (ValueError, OSError, UnicodeError) as exc:
        row['registered'].update(state='ERROR', error=str(exc))
    try:
        if spec['installed_root']:
            row['installed'].update(checked_entry(spec['installed_root']), state='ENTRY_ONLY')
            row['installed']['entry_matches_registered'] = row['installed']['sha256'] == row['registered'].get('sha256')
    except (ValueError, OSError, UnicodeError) as exc:
        row['installed'].update(state='ERROR', error=str(exc))
    if spec.get('formal_root'):
        row['formal'].update(version=spec['version'], root=spec['formal_root'], receipt_path=spec['receipt_path'], receipt_sha256=spec['receipt_sha256'])
        try:
            if not pointer_ok:
                raise ValueError('正式库CURRENT声明已变化；需重新核对准确发布来源，下方保留本批锁定版本')
            receipt_raw = raw_file(Path(spec['receipt_path']))
            if hashlib.sha256(receipt_raw).hexdigest() != spec['receipt_sha256']:
                raise ValueError('正式发布凭证发生变化')
            receipt = json.loads(receipt_raw)
            if receipt.get('status') != spec['receipt_status'] or receipt.get('version', receipt.get('formal_version')) != spec['receipt_version']:
                raise ValueError('发布状态或版本不匹配')
            if spec.get('portable_path') and hashlib.sha256(raw_file(Path(spec['portable_path']))).hexdigest() != spec['portable_sha256']:
                raise ValueError('可移植清单发生变化')
            row['formal'].update(verify_manifest(Path(spec['formal_root']), spec['runtime_hashes']))
            row['formal']['entry'] = str(Path(spec['formal_root']) / 'SKILL.md')
            row['can_handoff_formal'] = row['formal']['state'] == 'MANIFEST_MATCH'
        except (ValueError, OSError, UnicodeError) as exc:
            row['formal'].update(state='ERROR', error=str(exc))
            row['can_handoff_formal'] = False
        if spec['installed_root'] and row['installed']['state'] != 'ERROR':
            try:
                row['installed'].update(verify_manifest(Path(spec['installed_root']), spec['runtime_hashes']))
                row['installed']['compared_version'] = spec['version']
            except (ValueError, OSError, UnicodeError) as exc:
                row['installed'].update(state='ERROR', error=str(exc))
    elif spec.get('declaration_path'):
        row['formal'].update(version=spec['declared_version'], root=spec['declared_root'], receipt_path=spec['declaration_path'], receipt_sha256=spec['declaration_sha256'])
        try:
            if hashlib.sha256(raw_file(Path(spec['declaration_path']))).hexdigest() != spec['declaration_sha256']:
                raise ValueError('发布声明发生变化')
            row['formal'].update(checked_entry(spec['declared_root']), state='DECLARATION_ONLY',
                                 note='发布声明及入口已定位；本批未核对全包、最新正式指针和实际执行')
        except (ValueError, OSError, UnicodeError) as exc:
            row['formal'].update(state='ERROR', error=str(exc))
    row['needs_workbench_sync'] = bool(row['formal'].get('version') and row['formal']['version'] != row['registered']['version'])
    row['note'] = '此来源标记为暂停；只允许只读分析。生产、安装及费用需另行授权。' if spec['paused'] else '本页只读核对；既有项目和草稿不会自动升级。未配置正式凭证和安装路径时显示未知。'
    return row


def observe(config: dict, records: list) -> dict:
    pointer_ok = pointer_matches(config)
    rows = []
    for spec in configured_specs(config, records):
        versions = [r for r in records if r['family_id'] == spec['family_id']]
        current = next((r for r in versions if r['version_role'] == '当前登记'), None)
        if current is None:
            rows.append({'family_id': spec['family_id'], 'name': spec['key'], 'error': '家族当前登记缺失；不推测替代版本'})
            continue
        rows.append(observe_family(spec, current, versions, pointer_ok))
    known = {s['family_id'] for s in config['families']}
    return {'schema': 'SKM_RELEASE_OBSERVATIONS_V1', 'checked_at': core.now(),
            'pointer_state': 'LOCK_MATCH' if pointer_ok else ('CHANGED' if config['current_path'] else 'UNCONFIGURED'), 'current_path': config['current_path'],
            'families': rows, 'unconfigured_family_count': len({r['family_id'] for r in records} - known),
            'protected_source_writes': False, 'automatic_dispatch': False, 'usage_receipts_implemented': False}


def status(fresh=False):
    global _cached, _cached_at
    with GUARD:
        if fresh or _cached is None or time.monotonic() - _cached_at > 60:
            _cached = observe(loaded_config(), registry_records()); _cached_at = time.monotonic()
        return copy.deepcopy(_cached)


def build_handoff(row: dict, mode: str) -> dict:
    if mode not in ('formal', 'registered'):
        raise ValueError('只支持正式来源或登记快照的只读分析交接')
    if row.get('error') or not row.get('can_handoff_' + mode):
        raise ValueError('所选来源未通过本批核对，不能生成调用交接')
    source = row[mode]
    version = source['version']
    instruction = (f"请仅在当前对话框中，读取「{row['name']}」{version} 的准确入口：\n{source['entry']}\n"
                   f"入口SHA-256：{source['entry_sha256'] if mode == 'formal' else source['sha256']}\n"
                   "先核对入口及必要依赖、完整原规则和模板；版本或内容不符时停止，不得按同名Skill自动替换。\n"
                   "本次用途：只读分析与维护准备。请回报实际读取版本、入口、哈希和核对范围；不要修改、安装、晋升、升级项目或执行生产。\n")
    if mode == 'registered':
        instruction += "这是工作台登记快照；只在这份冻结来源上分析。原目录可能已更新，快照不代表当前正式版、完整安装包或可独立执行模块。\n"
    if row['paused']:
        instruction += "此来源保持暂停；不执行 Skill、不调用外部服务或产生费用。此指令只授权当前目标对话框进行只读分析。\n"
    package = {'schema': 'SKM_MANUAL_CALL_HANDOFF_V1', 'family_id': row['family_id'], 'version': version,
               'mode': mode, 'source': source, 'scope': 'READ_ONLY_ANALYSIS', 'paused': row['paused'],
               'target_thread_id': None, 'project_binding': None, 'usage_state': 'UNKNOWN', 'generated_at': core.now(),
               'authorization': '只有用户把本指令发到目标对话框后，才授权该对话框的只读分析；无自动发送', 'instruction': instruction}
    package['handoff_sha256'] = core.digest(package)
    if len(core.canonical(package)) > core.MAX_BYTES:
        raise ValueError('调用交接超过2MiB')
    return package


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    family_id: str = Field(min_length=1, max_length=100)
    mode: str = Field(pattern='^(formal|registered)$')


@router.get('/status')
def release_status():
    return status()


@router.post('/refresh')
def refresh_status():
    return status(fresh=True)


@router.post('/handoff')
def handoff(payload: HandoffRequest):
    # Recheck the selected source at generation time; a cached badge is not proof.
    # Other independent families need not delay this particular handoff.
    with GUARD:
        config = loaded_config()
        all_records = registry_records()
        spec = next((s for s in configured_specs(config, all_records) if s['family_id'] == payload.family_id), None)
        if spec is None:
            raise HTTPException(404, '已核对家族中没有该来源')
        versions = [v for v in all_records if v['family_id'] == payload.family_id]
        current = next((v for v in versions if v['version_role'] == '当前登记'), None)
        if current is None:
            raise ValueError('家族当前登记缺失，停止生成指令')
        pointer_ok = pointer_matches(config)
        return build_handoff(observe_family(spec, current, versions, pointer_ok), payload.mode)
