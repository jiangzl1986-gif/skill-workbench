"""Wrap the verified portable program in an offline, current-user installer."""
from pathlib import Path
import argparse, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0-beta.2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    build = args.build.resolve()
    bundle = build / 'dist/启动工作台'
    output = args.output.resolve()
    if output == Path(output.anchor) or str(output).startswith('\\\\') or output == ROOT or ROOT in output.parents:
        raise SystemExit('Use an independent local output directory outside the checkout.')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise SystemExit('Installer output must be empty; existing files are never removed.')
    manifest = json.loads((build / 'bundle-manifest.json').read_text('utf-8'))
    assert manifest['version'] == VERSION
    expected = {row['path']:row['sha256'] for row in manifest['files']}
    actual = {p.relative_to(bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in bundle.rglob('*') if p.is_file()}
    if actual != expected:
        raise SystemExit('Portable bundle differs from its manifest; do not install unknown files.')
    subprocess.run([str(args.compiler.resolve()), '/DBundleDir=' + str(bundle),
                    '/DOutputDir=' + str(output), str(ROOT / 'packaging/windows.iss')], check=True)
    exe = output / f'skill-workbench-{VERSION}-windows-x64-setup.exe'
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(digest + '  ' + exe.name + '\n', encoding='ascii')
    (output / 'installer-manifest.json').write_text(json.dumps({
        'version':VERSION, 'installer':exe.name, 'sha256':digest,
        'portable_archive_sha256':manifest['archive_sha256'], 'program_files':len(expected),
        'current_user_only':True, 'external_dependencies_required':False,
        'user_data_targeted_by_uninstaller':False,
    }, indent=2), encoding='utf-8')
    print(json.dumps({'installer':str(exe), 'sha256':digest}))


if __name__ == '__main__':
    main()
