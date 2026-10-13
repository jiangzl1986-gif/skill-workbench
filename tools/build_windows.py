"""Build a public-only, self-contained Windows x64 distribution."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0-beta.2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path, help='New independent local build directory')
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().upper() not in ('AMD64', 'X86_64'):
        raise SystemExit('Build this distribution on Windows x64.')
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents or output == Path(output.anchor) or str(output).startswith('\\\\'):
        raise SystemExit('Choose an independent local output directory outside the source checkout.')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise SystemExit('Output must be empty; existing builds are never removed automatically.')
    frontend = ROOT / 'apps/web/dist'
    if not (frontend / 'index.html').is_file():
        raise SystemExit('Build the public frontend with setup.cmd first.')
    # PyInstaller sees only this repository and the isolated, pinned build environment.
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
               '--name', '启动工作台', '--paths', str(ROOT / 'services/local_api'),
               '--distpath', str(output / 'dist'), '--workpath', str(output / 'work'),
               '--specpath', str(output), '--collect-submodules', 'skm',
               '--collect-submodules', 'uvicorn', '--collect-submodules', 'watchdog',
               '--copy-metadata', 'fastapi', '--copy-metadata', 'pydantic',
               '--add-data', str(frontend) + ';apps/web/dist',
               '--add-data', str(ROOT / 'docs/WORKBENCH_CONTRACT.md') + ';docs',
               str(ROOT / 'portable_launcher.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    bundle = output / 'dist/启动工作台'
    if not (bundle / '启动工作台.exe').is_file():
        raise SystemExit('Frozen launcher is missing.')
    for relative in ('examples', 'docs/dependency-licenses'):
        shutil.copytree(ROOT / relative, bundle / relative)
    for relative in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md', 'README.en.md', 'docs/USER_GUIDE.md', 'docs/WINDOWS_PORTABLE.md'):
        target = bundle / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    notices = bundle / 'docs/dependency-licenses'
    shutil.copyfile(Path(sys.base_prefix) / 'LICENSE.txt', notices / 'Python-runtime-LICENSE.txt')
    for name in ('pyinstaller', 'altgraph', 'pefile', 'pyinstaller-hooks-contrib', 'pywin32-ctypes', 'setuptools'):
        distribution = importlib.metadata.distribution(name)
        for relative in distribution.files or []:
            if any(token in relative.name.lower() for token in ('license', 'copying', 'notice')) and distribution.locate_file(relative).is_file():
                destination = notices / ('build-' + name + '-' + relative.name)
                shutil.copyfile(distribution.locate_file(relative), destination)
    (bundle / '开始使用.txt').write_text('''SkillTangram｜技能七巧板

1. 完整解压整个文件夹。
2. 双击“启动工作台.exe”，浏览器自动打开。
3. 从“导入与同步”添加自己的 Skill，或选择 examples 内的演示目录。
4. 使用时保留启动窗口；点“退出工作台”停止本次服务。

不需要安装 Python、Node.js，不需要运行 setup，也不需要联网安装依赖。
支持 Windows x64；资料保存在本机用户的 LocalAppData/skill-workbench。
保留 _internal 文件夹，不能只复制 EXE。
详细操作见 docs/USER_GUIDE.md；导出设计仍需 Agent/开发者实际接入。

Extract the entire folder, then double-click 启动工作台.exe.
No separate Python, Node.js or dependency installation is needed.
Keep the launcher open; choose 退出工作台 to stop the local service.
Keep the _internal folder with the EXE. Windows x64 only.
''', encoding='utf-8-sig')
    paths = sorted(p for p in bundle.rglob('*') if p.is_file())
    rows = [{'path': p.relative_to(bundle).as_posix(), 'bytes': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    archive = output / f'skill-workbench-{VERSION}-windows-x64-portable.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in paths:
            z.write(path, 'Skill Workbench/' + path.relative_to(bundle).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    (output / 'bundle-manifest.json').write_text(json.dumps({
        'version': VERSION, 'archive_sha256': digest, 'files': rows,
        'scope': 'public program, bundled runtime, prebuilt UI, public examples and licenses; no personal Skills or runtime data',
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'archive': str(archive), 'sha256': digest, 'files': len(rows)}))


if __name__ == '__main__':
    main()
