"""Install only in a new test directory, check actual installed EXE, then uninstall."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, socket, subprocess, time, winreg
import httpx

APP_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{D3F1782B-F98A-473B-8AB2-17DB9370F33B}_is1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--installer', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                key = winreg.OpenKey(hive, APP_KEY, 0, winreg.KEY_READ | view)
            except FileNotFoundError:
                continue
            key.Close()
            raise SystemExit('An existing installation is registered; do not change it during testing.')
    work = args.work.resolve()
    if work == Path(work.anchor) or str(work).startswith('\\\\'):
        raise SystemExit('Use a new independent local directory.')
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit('Installer acceptance directory must be empty.')
    install = (work / '中文安装 空格/Skill Workbench').resolve()
    assert work in install.parents
    subprocess.run([str(args.installer.resolve()), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NOICONS', '/TASKS=',
                    '/NORESTART', '/DIR=' + str(install), '/LOG=' + str(work / 'install.log')], check=True, timeout=90)
    manifest = json.loads((args.build / 'bundle-manifest.json').read_text('utf-8'))
    for row in manifest['files']:
        actual = (install / row['path']).read_bytes()
        assert len(actual) == row['bytes'] and hashlib.sha256(actual).hexdigest() == row['sha256']
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        assert Path(winreg.QueryValueEx(key, 'InstallLocation')[0]).resolve() == install
    env = dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','NODE_PATH','SKM_WEB','SKM_IMPORT_STORE'):
        env.pop(name, None)
    env['PATH'] = str(Path(env['WINDIR']) / 'System32') + os.pathsep + env['WINDIR']
    env['SKM_RUNTIME'] = str(work / 'user-data')
    env['PYTHONNOUSERSITE'] = '1'
    assert shutil.which('python', path=env['PATH']) is None and shutil.which('node', path=env['PATH']) is None
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    process = subprocess.Popen([str(install/'启动工作台.exe'),'--headless','--no-browser','--port',str(port),'--exit-after','6'],
                               cwd=work, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=10) as client:
            for _ in range(150):
                assert process.poll() is None, 'Installed app exited before ready'
                try:
                    session = client.get('/api/session')
                    if session.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(.1)
            else:
                raise AssertionError('Installed app did not become ready')
            assert client.get('/').status_code == 200
            assert client.get('/api/skills').json() == []
        assert process.wait(timeout=20) == 0
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=10)
    metadata = json.loads((work/'user-data/portable-launch.json').read_text('utf-8'))
    assert Path(metadata['executable']).resolve() == install/'启动工作台.exe'
    assert metadata['frozen'] is True and Path(metadata['bundle_root']) == install/'_internal'
    data_before = {p.relative_to(work/'user-data').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (work/'user-data').rglob('*') if p.is_file()}
    assert data_before
    uninstall = (install / 'unins000.exe').resolve()
    assert uninstall.parent == install and work in uninstall.parents
    subprocess.run([str(uninstall),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(work/'uninstall.log')],
                   check=True, timeout=60)
    for _ in range(100):
        if not (install/'启动工作台.exe').exists():
            break
        time.sleep(.1)
    assert not (install/'启动工作台.exe').exists()
    data_after = {p.relative_to(work/'user-data').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (work/'user-data').rglob('*') if p.is_file()}
    assert data_after == data_before
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:
        pass
    else:
        key.Close(); raise AssertionError('Test uninstall registration remains')
    result = {'status':'PASS','installed_program_files':len(manifest['files']),
        'all_program_hashes_match':True,'installed_exe_without_python_or_node':True,
        'current_user_registration':True,'test_only_installation_removed':True,'user_data_retained_byte_identical':True,
        'scope':'silent isolated install/uninstall and actual installed app on this Windows host; no second-PC GUI review'}
    (work/'installer-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
