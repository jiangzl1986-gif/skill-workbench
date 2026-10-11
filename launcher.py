"""Foreground local launcher. Closing it or pressing Ctrl+C stops this service."""
from pathlib import Path
import argparse, os, socket, sys, threading, time, webbrowser
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'services/local_api'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=int(os.environ.get('SKM_PORT','8770')))
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('port must be 1024..65535')
    os.environ['SKM_PORT']=str(args.port)
    from skm import config
    # Validate runtime before creating any directories. Data stays outside the code checkout by default.
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',args.port))==0:
            raise SystemExit('端口已被使用；请关闭本实例或用 --port 选择其他端口。不会停止其他程序。')
    dist=ROOT/'apps/web/dist'
    if not (dist/'index.html').is_file():raise SystemExit('页面尚未构建，请先运行 setup.cmd。')
    from skm import api
    if api.WEB != dist:raise SystemExit('SKM_WEB 与已构建页面不一致，请核对配置。')
    url=f'http://127.0.0.1:{args.port}/'
    if not args.no_browser:
        def open_when_ready():
            for _ in range(100):
                with socket.socket() as s:
                    if s.connect_ex(('127.0.0.1',args.port))==0:
                        webbrowser.open(url);return
                time.sleep(.1)
        threading.Thread(target=open_when_ready,daemon=True).start()
    print('Skill Workbench:',url,'\n运行资料：',config.RUNTIME,'\n按 Ctrl+C 停止。')
    import uvicorn
    uvicorn.run(api.app,host='127.0.0.1',port=args.port)

if __name__=='__main__':main()
