"""Offline Windows launcher and localhost-only application supervisor."""
import argparse
import ctypes
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, build_opener, ProxyHandler
import uuid
import webbrowser

from desktop_paths import APP_NAME, VERSION, asset_root, workspace_root


def configure_logging(root, name):
    folder = root / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(folder / (name + ".log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s", force=True)


def enforce_offline_network():
    """Block application process connections outside this computer."""
    import ipaddress
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_resolve = socket.getaddrinfo

    def check(address, family):
        if family not in (socket.AF_INET, socket.AF_INET6):
            return
        host = address[0]
        if host == "localhost":
            return
        try:
            allowed = ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = False
        if not allowed:
            raise OSError("USECTA offline edition blocks external network connections.")

    def connect(sock, address):
        check(address, sock.family)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address, sock.family)
        return original_connect_ex(sock, address)

    def resolve(host, *args, **kwargs):
        if host is not None:
            check((host, 0), socket.AF_INET)
        return original_resolve(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = resolve


def serve(port):
    os.environ["USECTA_OFFLINE"] = "1"
    configure_logging(workspace_root(), "application")
    logging.info("Starting offline server on localhost port %d", port)
    if os.environ.get("USECTA_DIAGNOSTIC") == "1":
        import faulthandler
        diagnostic = (workspace_root() / "logs" / "diagnostic.log").open("a")
        faulthandler.dump_traceback_later(20, file=diagnostic)
    enforce_offline_network()
    # Streamlit is intentionally imported only in the server process.
    from streamlit.web import bootstrap
    logging.info("Streamlit loaded")
    options = {
        "server.address": "127.0.0.1", "server.port": port,
        "server.headless": True, "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False, "server.maxUploadSize": 200,
        "client.toolbarMode": "minimal",
        "server.enableCORS": True, "server.enableXsrfProtection": True,
    }
    bootstrap.load_config_options(options)
    logging.info("Local server configuration loaded")
    bootstrap.run(str(asset_root() / "app.py"), False, [], options)


def health(url):
    try:
        with build_opener(ProxyHandler({})).open(url + "/_stcore/health", timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def command_prefix():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(Path(__file__).resolve())]


def notify_error(message, interactive=True):
    logging.error(message)
    if os.name == "nt" and interactive:
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    else:
        print(message, file=sys.stderr)


def supervise(args):
    root = workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    configure_logging(root, "launcher")
    metadata = root / "launcher.json"
    import msvcrt
    lock_file = (root / "launcher.lock").open("a+b")
    lock_file.seek(0)
    # Lock before touching the byte: Windows forbids reading another process's
    # locked region. A lock can extend beyond EOF, including a fresh empty file.
    try:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock_file.close()
        for _ in range(100):
            try:
                existing = json.loads(metadata.read_text())
                if health(existing["url"]):
                    if not args.no_browser:
                        webbrowser.open(existing["url"])
                    return 0
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.1)
        notify_error("USECTA is already starting. Please wait, then open the shortcut again.", not args.no_browser)
        return 1
    if os.fstat(lock_file.fileno()).st_size == 0:
        lock_file.write(b"0")
        lock_file.flush()
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = kernel.CreateMutexW(None, False, "USECTA-Document-Generator")
    child = None
    control = None
    stopped = threading.Event()
    try:
        os.environ["USECTA_OFFLINE"] = "1"
        os.environ["USECTA_DATA_DIR"] = str(root)
        from documents import Store
        from workflows import prepare_workspace
        store = Store(root)
        if store.templates():
            from workspace_archive import save_automatic_backup
            stamp = time.strftime("%Y%m%d")
            if not list((root / "backups").glob(stamp + "-*-daily-*.zip")):
                save_automatic_backup(store, "daily")
        prepare_workspace(store)
        token = uuid.uuid4().hex

        class ControlHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/stop" or self.headers.get("X-USECTA-Token") != token:
                    self.send_error(403)
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Stopping USECTA")
                stopped.set()

            def log_message(self, *_):
                return

        control = ThreadingHTTPServer(("127.0.0.1", 0), ControlHandler)
        threading.Thread(target=control.serve_forever, daemon=True).start()
        os.environ["USECTA_CONTROL_URL"] = f"http://127.0.0.1:{control.server_port}"
        os.environ["USECTA_CONTROL_TOKEN"] = token
        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", args.port))
            port = port_socket.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        child = subprocess.Popen(command_prefix() + ["--serve", "--port", str(port)],
                                 cwd=asset_root(), env=os.environ.copy(),
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        started = time.monotonic()
        while not health(url):
            if child.poll() is not None or time.monotonic() - started > 60:
                raise RuntimeError("USECTA could not start. Check " + str(root / "logs" / "application.log"))
            time.sleep(0.1)
        metadata.write_text(json.dumps({"url": url, "pid": child.pid, "control_url": os.environ["USECTA_CONTROL_URL"], "token": token, "version": VERSION}))
        logging.info("Ready at %s in %.2fs", url, time.monotonic() - started)
        if not args.no_browser:
            webbrowser.open(url)
        while not stopped.wait(0.25):
            if child.poll() is not None:
                raise RuntimeError("USECTA stopped unexpectedly. Open the desktop shortcut to restart. Application log: " + str(root / "logs" / "application.log"))
        return 0
    except Exception as exc:
        logging.exception("Launcher failed")
        notify_error(str(exc), not args.no_browser)
        return 1
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if control:
            control.shutdown()
            control.server_close()
        metadata.unlink(missing_ok=True)
        ctypes.windll.kernel32.CloseHandle(mutex)
        lock_file.close()


def stop_running():
    try:
        info = json.loads((workspace_root() / "launcher.json").read_text())
        request = Request(info["control_url"] + "/stop", data=b"", headers={"X-USECTA-Token": info["token"]}, method="POST")
        with build_opener(ProxyHandler({})).open(request, timeout=3):
            pass
        return 0
    except (OSError, ValueError, KeyError):
        return 1


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    if args.data_dir:
        os.environ["USECTA_DATA_DIR"] = str(args.data_dir.resolve())
    os.environ["USECTA_OFFLINE"] = "1"
    if args.serve:
        serve(args.port)
        return 0
    if args.self_test:
        enforce_offline_network()
        from offline_smoke import run_smoke
        run_smoke(workspace_root())
        return 0
    if args.stop:
        return stop_running()
    return supervise(args)


if __name__ == "__main__":
    # Windowed frozen applications do not have stdout/stderr. Libraries expect
    # usable streams even when their output is captured in rotating log files.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    try:
        result = main()
    except Exception as exc:
        configure_logging(workspace_root(), "application" if "--serve" in sys.argv else "launcher")
        logging.exception("USECTA failed")
        if not any(flag in sys.argv for flag in ["--serve", "--no-browser", "--self-test", "--stop"]):
            notify_error(str(exc))
        result = 1
    sys.exit(result)
