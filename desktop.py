"""Local desktop launcher and private stop control. Runs with pythonw on Windows."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / 'data'
STATE = DATA / 'desktop-session.json'


def notice(message, error=False):
    if os.name == 'nt':
        ctypes.windll.user32.MessageBoxW(None, message, 'USECTA Documents', 0x10 if error else 0x40)
    else:
        print(message, file=sys.stderr if error else sys.stdout)


def read_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def control(state, action='status'):
    try:
        port = int(state['control_port'])
        token = state['token']
        request = Request(f'http://127.0.0.1:{port}/{action}', method='POST' if action == 'stop' else 'GET',
                          headers={'X-USECTA-Token': token})
        with urlopen(request, timeout=2) as response:
            result = json.loads(response.read())
        return result if result.get('root') == str(ROOT) else None
    except (KeyError, ValueError, OSError, URLError):
        return None


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def lock_file(path):
    handle = path.open('a+b')
    handle.seek(0)
    if os.name == 'nt':
        import msvcrt
        if not path.stat().st_size:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return None
    else:
        import fcntl
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return None
    return handle


def launch(no_browser=False):
    DATA.mkdir(exist_ok=True)
    lock = lock_file(DATA / 'desktop.lock')
    if lock is None:
        for _ in range(90):
            current = control(read_state())
            if current and current['ready']:
                if not no_browser:
                    webbrowser.open(current['url'])
                return
            time.sleep(1)
        raise RuntimeError('USECTA is already starting. Check data/desktop.log if it does not open.')
    process, server, thread, log = None, None, None, None
    stop = threading.Event()
    token = secrets.token_urlsafe(32)
    port = free_port()
    url = f'http://127.0.0.1:{port}'
    ready = False

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond(False)

        def do_POST(self):
            self.respond(True)

        def respond(self, post):
            if not secrets.compare_digest(self.headers.get('X-USECTA-Token', ''), token):
                self.send_error(403)
                return
            if self.path != ('/stop' if post else '/status'):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'root': str(ROOT), 'url': url, 'ready': ready}).encode())
            if post:
                stop.set()

        def log_message(self, *args):
            pass

    class LocalServer(HTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(2)
            return connection, address

    try:
        server = LocalServer(('127.0.0.1', 0), Handler)
        # Bound local control requests cannot stall the launcher indefinitely.
        server.timeout = 1
        def serve():
            while not stop.is_set():
                server.handle_request()
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        STATE.write_text(json.dumps({'control_port': server.server_port, 'token': token}))
        python = Path(sys.executable)
        if python.name.lower() == 'pythonw.exe':
            python = python.with_name('python.exe')
        env = os.environ.copy()
        env.update(USECTA_LOCAL_MODE='1', USECTA_DATA_DIR=str(DATA))
        log = (DATA / 'desktop.log').open('w', encoding='utf-8')
        command = [str(python), '-m', 'streamlit', 'run', str(ROOT / 'app.py'),
                   '--server.address=127.0.0.1', f'--server.port={port}', '--server.headless=true',
                   '--browser.gatherUsageStats=false', '--server.fileWatcherType=none']
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=flags)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and not stop.is_set():
            if process.poll() is not None:
                raise RuntimeError('The local app stopped during startup. See data/desktop.log for details.')
            try:
                with urlopen(url + '/_stcore/health', timeout=1) as response:
                    ready = response.status == 200 and response.read() == b'ok'
            except (OSError, URLError):
                pass
            if ready:
                break
            time.sleep(.25)
        if stop.is_set():
            return
        if not ready:
            raise RuntimeError('Startup took too long. See data/desktop.log for details.')
        if not no_browser:
            webbrowser.open(url)
        while process.poll() is None and not stop.wait(.5):
            pass
    finally:
        stop.set()
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if server:
            if thread:
                thread.join(timeout=3)
            server.server_close()
        if log:
            log.close()
        STATE.unlink(missing_ok=True)
        lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--no-browser', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.stop:
        if not control(read_state(), 'stop'):
            notice('USECTA is already closed.')
    else:
        launch(args.no_browser)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        notice(str(exc), error=True)
        sys.exit(1)
