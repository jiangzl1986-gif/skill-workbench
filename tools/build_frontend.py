"""Keep npm/build activity on a local runtime disk, including a NAS checkout."""
from pathlib import Path
import argparse, os, shutil, subprocess, sys, uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/local_api'))
from skm.config import RUNTIME

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--npm',default=shutil.which('npm.cmd') or shutil.which('npm'))
    args=parser.parse_args()
    if not args.npm:raise SystemExit('请安装 Node.js 22 LTS（包含 npm）')
    build=RUNTIME/'build/web'
    if str(build).startswith('\\\\'):raise SystemExit('构建与数据库运行目录须选择本地磁盘。SKM_RUNTIME 可以更换位置。')
    build.mkdir(parents=True,exist_ok=True)
    files=[ROOT/'apps/web'/v for v in ('package.json','package-lock.json','tsconfig.json','index.html')]
    files += [p for p in (ROOT/'apps/web/src').rglob('*') if p.is_file() and p.suffix in ('.ts','.tsx','.css','.json')]
    for src in files:
        dst=build/src.relative_to(ROOT/'apps/web');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    subprocess.run([args.npm,'ci','--no-audit','--no-fund'],cwd=build,check=True)
    subprocess.run([args.npm,'run','build'],cwd=build,check=True)
    # Publish a complete build so retired bundles cannot remain in a download.
    target=ROOT/'apps/web/dist'
    boundary=(ROOT/'apps/web').resolve()
    if target.is_symlink() or not target.resolve().is_relative_to(boundary):
        raise SystemExit('页面输出路径超出项目目录；未替换。')
    staging=target.parent/('.dist-staging-'+uuid.uuid4().hex)
    shutil.copytree(build/'dist',staging)
    if target.exists():
        history=target.parent/'.build-history'
        history.mkdir(exist_ok=True)
        backup=history/('dist-'+uuid.uuid4().hex)
        if not backup.resolve().is_relative_to(boundary):
            raise SystemExit('页面备份路径超出项目目录；未替换。')
        target.rename(backup)
    staging.rename(target)
    print('页面已构建；Node 缓存保留在独立运行目录。')

if __name__=='__main__':main()
