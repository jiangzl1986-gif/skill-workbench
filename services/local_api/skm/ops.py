"""Backup/recovery for the workbench database only; never touches a Skill."""
import argparse
import hashlib
import json
import socket
import sqlite3
from pathlib import Path
from . import core


def backup():
    folder=core.RUNTIME/'backups';folder.mkdir(parents=True,exist_ok=True)
    if len(list(folder.glob('*.sqlite3')))>=30:raise ValueError('已达30份备份上限；请先明确归档方案，本程序不删除历史')
    target=folder/(core.now().replace(':','-')+'-'+core.ident()[:8]+'.sqlite3')
    with core.connect() as source:
        dest=sqlite3.connect(target)
        try:
            source.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('备份完整性检查失败')
        finally:dest.close()
    record={'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'scope':'仅本地地图、意见、审批和审计数据；不含Skill源修改','created_at':core.now()}
    target.with_suffix('.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    with core.connect() as db:core.audit(db,'备份工作台数据',str(target),record,'本机索引服务')
    return record


def restore(path,expected_current_sha256):
    target=Path(path).resolve(strict=True);root=(core.RUNTIME/'backups').resolve(strict=True)
    if not target.is_relative_to(root) or target.suffix!='.sqlite3':raise ValueError('恢复只能读取本工作台备份目录')
    record=json.loads(target.with_suffix('.json').read_text('utf-8'))
    if hashlib.sha256(target.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('备份hash不符，停止恢复')
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',int(__import__('os').environ.get('SKM_PORT','8770'))))==0:raise ValueError('先停止本工作台服务再恢复；不覆盖活跃数据库')
    db_path=core.RUNTIME/'data'/'skm.sqlite3'
    wal=db_path.with_name(db_path.name+'-wal')
    if wal.exists() and wal.stat().st_size:raise ValueError('数据库仍有WAL，请先正常停止/检查服务；不盲目覆盖')
    if hashlib.sha256(db_path.read_bytes()).hexdigest()!=expected_current_sha256:raise ValueError('当前数据库基线变了，停止恢复')
    rescue=backup()
    source=sqlite3.connect(f'file:{target.as_posix()}?mode=ro',uri=True);destination=sqlite3.connect(db_path)
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('恢复源完整性失败')
        source.backup(destination)
    finally:source.close();destination.close()
    with core.connect() as db:core.audit(db,'人工恢复工作台数据',str(target),{'backup':record,'pre_restore_backup':rescue},'本机恢复操作')
    return {'restored':str(target),'pre_restore_backup':rescue,'scope':'仅地图数据库恢复；Skill源未修改'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('backup');recover=sub.add_parser('restore');recover.add_argument('path');recover.add_argument('--current-sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(backup() if args.action=='backup' else restore(args.path,args.current_sha256),ensure_ascii=False))
