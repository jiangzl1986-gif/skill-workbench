"""Bundled Windows entry point; imported Skills remain read-only data."""
from pathlib import Path
import argparse
import json
import logging
import os
import socket
import sys
import threading
import time
import webbrowser

ROOT = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(ROOT / 'services/local_api'))


def prepare(port):
    if not 1024 <= port <= 65535:
        raise ValueError('端口须为 1024–65535 之间的整数。')
    os.environ['SKM_PORT'] = str(port)
    from skm import config
    # All bundled resources use the existing project contract, before data is written.
    if config.PROJECT != ROOT:
        raise ValueError('程序资源位置不一致，请重新完整解压下载包。')
    dist = ROOT / 'apps/web/dist'
    if not (dist / 'index.html').is_file():
        raise ValueError('页面文件缺失，请重新完整解压下载包。')
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', port)) == 0:
            raise ValueError('工作台端口已被使用。请先关闭已打开的工作台；不会停止其他程序。')
    config.RUNTIME.mkdir(parents=True, exist_ok=True)
    log = config.RUNTIME / 'launcher.log'
    stream = log.open('a', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(stream)], force=True)
    from skm import api
    if api.WEB != dist:
        raise ValueError('页面配置不一致，请核对 SKM_WEB 或重新完整解压。')
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(api.app, host='127.0.0.1', port=port,
                                         log_config=None, access_log=False))
    (config.RUNTIME / 'portable-launch.json').write_text(json.dumps({
        'version': '0.1.0-beta.2', 'pid': os.getpid(), 'port': port,
        'frozen': bool(getattr(sys, 'frozen', False)), 'executable': sys.executable,
        'python': sys.version, 'bundle_root': str(ROOT), 'sys_path': sys.path,
        'runtime': str(config.RUNTIME), 'source_write': False,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return server, config.RUNTIME


def main():
    parser = argparse.ArgumentParser(description='Skill Workbench Windows launcher')
    parser.add_argument('--port', type=int, default=int(os.environ.get('SKM_PORT', '8770')))
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--headless', action='store_true', help='For isolated packaging verification')
    parser.add_argument('--exit-after', type=float, default=0, help='Headless verification: stop this server gracefully after N seconds')
    args = parser.parse_args()
    if args.headless:
        try:
            server, _ = prepare(args.port)
        except Exception as exc:
            if sys.stderr is not None:
                print(str(exc), file=sys.stderr)
            raise SystemExit(1)
        if args.exit_after > 0:
            def scheduled_stop():
                time.sleep(args.exit_after)
                server.should_exit = True
            threading.Thread(target=scheduled_stop, daemon=True).start()
        server.run()
        return
    import tkinter as tk
    from tkinter import messagebox, ttk
    window = tk.Tk()
    window.title('Skill Workbench')
    window.geometry('540x280')
    window.resizable(False, False)
    style = ttk.Style(window)
    style.configure('TLabel', font=('Microsoft YaHei UI', 10))
    box = ttk.Frame(window, padding=24)
    box.pack(fill='both', expand=True)
    ttk.Label(box, text='Skill 可视化创作工作台', font=('Microsoft YaHei UI', 16, 'bold')).pack(anchor='w')
    status = tk.StringVar(value='正在启动，请稍候…')
    ttk.Label(box, textvariable=status).pack(anchor='w', pady=(16, 8))
    url = f'http://127.0.0.1:{args.port}/'
    ttk.Label(box, text=url).pack(anchor='w')
    ttk.Label(box, text='使用时保留此窗口，退出工作台会停止本次服务。').pack(anchor='w', pady=(8, 16))
    buttons = ttk.Frame(box)
    buttons.pack(anchor='w')
    open_button = ttk.Button(buttons, text='打开工作台', state='disabled', command=lambda: webbrowser.open(url))
    open_button.pack(side='left', padx=(0, 12))
    server = None
    worker = None
    errors = []
    closing = False

    def finish_stop():
        if worker and worker.is_alive():
            window.after(100, finish_stop)
        else:
            window.destroy()

    def stop():
        nonlocal closing
        if closing:
            return
        closing = True
        status.set('正在保存并退出…')
        open_button.configure(state='disabled')
        if server:
            server.should_exit = True
        finish_stop()

    ttk.Button(buttons, text='退出工作台', command=stop).pack(side='left')
    window.protocol('WM_DELETE_WINDOW', stop)
    try:
        server, runtime = prepare(args.port)
    except Exception as exc:
        messagebox.showerror('工作台未能启动', str(exc), parent=window)
        window.destroy()
        return

    def run():
        try:
            server.run()
        except BaseException as exc:
            errors.append(str(exc))
            logging.exception('Local workbench server stopped')

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    deadline = time.monotonic() + 30

    def ready():
        if closing:
            return
        if errors or not worker.is_alive() or time.monotonic() > deadline:
            messagebox.showerror('工作台未能启动', errors[0] if errors else f'请查看本机日志：{runtime / "launcher.log"}', parent=window)
            stop()
        elif server.started:
            status.set('工作台已打开。可以在浏览器中开始创作。')
            open_button.configure(state='normal')
            if not args.no_browser:
                webbrowser.open(url)
        else:
            window.after(100, ready)

    window.after(100, ready)
    window.mainloop()


if __name__ == '__main__':
    main()
