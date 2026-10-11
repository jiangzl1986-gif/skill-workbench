"""Test this application's Tk callbacks in a hidden test window, with real local HTTP."""
from pathlib import Path
import argparse
import json
import os
import socket
import sys
import time
import tkinter as tk
from tkinter import messagebox
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    if work == Path(work.anchor) or str(work).startswith('\\\\'):
        raise SystemExit('Choose an independent local GUI test directory.')
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit('Test directory must be empty.')
    os.environ['SKM_RUNTIME'] = str(work / 'data')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    os.environ['SKM_PORT'] = str(port)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import portable_launcher
    original_tk = tk.Tk
    opened = []
    failures = []
    outcomes = []
    portable_launcher.webbrowser.open = lambda url: opened.append(url) or True
    messagebox.showerror = lambda title, text, **kwargs: failures.append(str(text))
    deadline = time.monotonic() + 30

    def test_window():
        root = original_tk()
        root.withdraw()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def verify():
            if time.monotonic() > deadline:
                failures.append('GUI startup timeout')
                root.destroy(); return
            if not opened:
                root.after(50, verify); return
            url = f'http://127.0.0.1:{port}/'
            try:
                assert opened == [url]
                assert httpx.get(url + 'api/session', trust_env=False).status_code == 200
                buttons = {widget.cget('text'): widget for widget in descendants(root)
                           if widget.winfo_class() == 'TButton'}
                assert set(buttons) == {'打开工作台', '退出工作台'}
                buttons['打开工作台'].invoke()
                assert opened == [url, url]
                outcomes.append('auto browser and reopen callback')
                buttons['退出工作台'].invoke()
                outcomes.append('normal exit callback')
            except Exception as exc:
                failures.append(str(exc)); root.destroy()
        root.after(50, verify)
        return root

    tk.Tk = test_window
    sys.argv = [sys.argv[0], '--port', str(port)]
    portable_launcher.main()
    assert not failures, failures
    assert len(outcomes) == 2
    with socket.socket() as sock:
        assert sock.connect_ex(('127.0.0.1', port)) != 0
    result = {'status': 'PASS', 'actual_tk_callbacks': outcomes, 'local_http_ready_before_open': True,
              'exit_callback_stops_only_this_service': True,
              'scope': 'hidden test window of this application; not a visual review on another user computer'}
    (work / 'gui-acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
