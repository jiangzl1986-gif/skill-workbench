"""Portable locations and frozen, inspectable workbench contract."""
from pathlib import Path
import hashlib, json, os, sys

PROJECT = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'skill-workbench'
RUNTIME = Path(os.environ.get('SKM_RUNTIME', str(DEFAULT_RUNTIME))).expanduser().resolve()
if str(RUNTIME).startswith('\\\\'):
    raise ValueError('数据库、WAL 与缓存须选择本地磁盘运行目录，不能放 NAS/UNC 共享目录')
if RUNTIME == Path(RUNTIME.anchor) or RUNTIME == Path.home().resolve():
    raise ValueError('请选择独立的工作台运行目录，不能使用磁盘根目录或用户主目录')
for item in (RUNTIME, *RUNTIME.parents):
    if item.is_symlink() or (item.exists() and getattr(item.stat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError('运行目录不能含链接或重解析点')

CONTRACT = PROJECT / 'docs/WORKBENCH_CONTRACT.md'
CONTRACT_SHA256 = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()

def authorities():
    raw = CONTRACT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError('本次进程的工作台契约发生变化，请核对版本并重启')
    return [{'path': str(CONTRACT), 'sha256': CONTRACT_SHA256, 'kind': '工作台设计与来源保真契约',
             'text': raw.decode('utf-8'), 'authority_note': '不替代导入者的正式规则，不授予 Skill 执行、安装或源修改权限'}]
