"""Independent HTTP/byte checks against a relocated EXE, without importing application code."""
from pathlib import Path
import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
import httpx


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    if work == Path(work.anchor) or str(work).startswith('\\\\'):
        raise SystemExit('Use an independent local acceptance directory.')
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit('Acceptance directory must be empty; existing data is never removed.')
    install = work / '中文路径 空格/Skill Workbench'
    shutil.copytree(args.bundle.resolve(), install)
    exe = install / '启动工作台.exe'
    runtime = work / 'user-data'
    env = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'NODE_PATH', 'SKM_WEB', 'SKM_IMPORT_STORE'):
        env.pop(name, None)
    env['PATH'] = str(Path(env['WINDIR']) / 'System32') + os.pathsep + env['WINDIR']
    env['SKM_RUNTIME'] = str(runtime)
    env['PYTHONNOUSERSITE'] = '1'
    assert shutil.which('python', path=env['PATH']) is None
    assert shutil.which('node', path=env['PATH']) is None
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    baseline = {p.relative_to(install / 'examples').as_posix(): sha(p.read_bytes())
                for p in (install / 'examples').rglob('*') if p.is_file()}

    def launch(seconds):
        return subprocess.Popen([str(exe), '--headless', '--no-browser', '--port', str(port), '--exit-after', str(seconds)],
                                cwd=work, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @contextmanager
    def connect(process):
        client = httpx.Client(base_url=base, timeout=15, trust_env=False)
        for _ in range(200):
            if process.poll() is not None:
                client.close()
                raise AssertionError('Portable process exited: ' + str(process.returncode))
            try:
                response = client.get('/api/session')
                if response.status_code == 200:
                    client.headers['x-skm-csrf'] = response.json()['csrf']
                    try:
                        yield client
                    finally:
                        client.close()
                    return
            except httpx.TransportError:
                pass
            time.sleep(.1)
        client.close()
        raise AssertionError('Portable startup did not become ready.')

    process = launch(18)
    try:
        with connect(process) as client:
            page = client.get('/'); page.raise_for_status()
            assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
            assert len(assets) >= 2
            for url in assets:
                assert client.get(url).status_code == 200
            assert client.get('/api/skills').json() == []
            assert client.get('/api/assembly/catalog').json()['nodes'] == []
            for name in ('notes-to-outline', 'evidence-review'):
                preview = client.post('/api/imports/preview', json={'root': str(install / 'examples' / name)})
                preview.raise_for_status(); source = preview.json()
                adopted = client.post('/api/imports/confirm', json={'preview_id': source['preview_id'],
                    'preview_hash': source['preview_hash'], 'relation_confirmed': False, 'missing_ack': True})
                adopted.raise_for_status()
            catalog = client.get('/api/assembly/catalog').json()
            assert len(catalog['sources']) == 2
            assert all(not blueprint['links'] for blueprint in catalog['blueprints'])
            nodes = [next(n for n in catalog['nodes'] if n['kind'] == 'theme' and n['source_skill_id'] == source['id'])
                     for source in catalog['sources']]
            child = next(edge['target'] for edge in catalog['contains'] if edge['source'] == nodes[0]['id'])
            foreign = next(n['id'] for n in catalog['nodes'] if n['kind'] == 'file' and n['source_skill_id'] == nodes[1]['source_skill_id'])
            draft = {'id': None, 'revision': 0, 'name': '免安装包跨来源验证', 'goal': '规则和原文保真',
                'instances': [{'id': 'p0', 'node_id': nodes[0]['id'], 'x': 0, 'y': 0, 'excluded': [], 'note': ''},
                              {'id': 'p1', 'node_id': nodes[1]['id'], 'x': 350, 'y': 0, 'excluded': [], 'note': ''}],
                'links': [{'source': 'p0', 'target': 'p1', 'label': '设计交接'}],
                'composition': {'schema_version': 1, 'scopes': [{'owner_id': 'p0', 'path': [], 'slots': [
                    {'id': 'o-' + child, 'origin_id': child, 'node_id': child, 'x': 0, 'y': 0, 'note': ''},
                    {'id': 'a-foreign', 'origin_id': None, 'node_id': foreign, 'x': 350, 'y': 0, 'note': '跨来源加入'}],
                    'links': [{'source': 'o-' + child, 'target': 'a-foreign', 'label': '内部交接'}]}]}}
            saved_response = client.post('/api/assembly/drafts', json=draft)
            saved_response.raise_for_status(); saved = saved_response.json()
            package_response = client.get('/api/assembly/drafts/' + saved['id'] + '/package')
            package_response.raise_for_status(); package = package_response.json()
            body = json.loads(gzip.decompress(base64.b64decode(package['source_bundle'])))
            canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            assert sha(canonical) == package['bundle_sha256']
            assert body['draft']['composition'] == draft['composition']
            assert body['execution_authority']['source_write'] is False
            for item in body['original_files']:
                actual = item['text'].encode(item['encoding']) if 'text' in item else base64.b64decode(item['binary_base64'])
                assert sha(actual) == item['sha256']
                assert any((install / 'examples' / name / item['path']).is_file() and
                           (install / 'examples' / name / item['path']).read_bytes() == actual
                           for name in ('notes-to-outline', 'evidence-review'))
            assert httpx.get(base + '/api/skills', trust_env=False).status_code == 401
            assert client.get('/api/skills', headers={'Host': 'foreign.invalid'}).status_code == 403
            assert client.post('/api/assembly/drafts', json=draft, headers={'x-skm-csrf': 'wrong'}).status_code == 403
            stale = dict(saved, revision=0)
            assert client.post('/api/assembly/drafts', json=stale).status_code == 409
            conflict_env = dict(env, SKM_RUNTIME=str(work / 'conflict-data'))
            conflict = subprocess.run([str(exe), '--headless', '--no-browser', '--port', str(port)], env=conflict_env,
                                      cwd=work, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            assert conflict.returncode != 0 and not (work / 'conflict-data').exists()
            assert client.get('/api/skills').status_code == 200
            info = json.loads((runtime / 'portable-launch.json').read_bytes())
            assert info['frozen'] is True
            assert Path(info['bundle_root']) == install / '_internal'
            assert all(str(install) in path for path in info['sys_path'])
            python_dlls = list((install / '_internal').glob('python3*.dll'))
            assert python_dlls
        assert process.wait(timeout=25) == 0
        process = launch(8)
        with connect(process) as client:
            reopened = client.get('/api/assembly/drafts/' + saved['id']).json()
            assert reopened['composition'] == draft['composition'] and len(reopened['instances']) == 2
            assert len(client.get('/api/skills').json()) == 2
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=10)
    after = {p.relative_to(install / 'examples').as_posix(): sha(p.read_bytes())
             for p in (install / 'examples').rglob('*') if p.is_file()}
    assert after == baseline
    report = {'status': 'PASS', 'restricted_path_no_python_or_node': True, 'frozen_runtime': True,
        'relocated_unicode_space_directory': True, 'prebuilt_assets_served': len(assets),
        'blank_first_start': True, 'imported_public_sources': 2, 'nested_cross_source_save_and_export': True,
        'original_bytes_and_export_hash': True, 'source_files_unchanged': True,
        'session_host_csrf_and_stale_draft_rejections': True, 'occupied_port_rejected_without_stopping_owner': True,
        'graceful_headless_stop_and_restart_persistence': True,
        'scope': 'independent process and HTTP/byte checks on this Windows host; not second physical computer or arbitrary Skill business execution'}
    (work / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
