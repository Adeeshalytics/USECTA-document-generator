"""Isolated bundle/installer acceptance checks; never touches company records."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import winreg
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
OPENER = build_opener(ProxyHandler({}))


def run(executable, *args, cwd=None, timeout=240):
    env = os.environ.copy()
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    env.pop("PYTHONPATH", None)
    subprocess.run([str(executable), *map(str, args)], cwd=cwd or executable.parent,
                   env=env, check=True, timeout=timeout)


def check_application(executable, audit):
    audit.mkdir(parents=True)
    run(executable, "--self-test", "--data-dir", audit)
    smoke = json.loads((audit / "offline-smoke.json").read_text())
    assert smoke["status"] == smoke["pdf"] == "passed"
    data = audit / "workspace"
    env = os.environ.copy()
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    env.pop("PYTHONPATH", None)
    launches = []
    for attempt in range(2):
        start = time.perf_counter()
        process = subprocess.Popen([str(executable), "--no-browser", "--data-dir", str(data)], cwd=audit, env=env)
        try:
            deadline = time.monotonic() + 90
            metadata = data / "launcher.json"
            while not metadata.exists():
                if process.poll() is not None:
                    raise AssertionError("Launcher exited: " + (data / "logs" / "launcher.log").read_text())
                if time.monotonic() > deadline:
                    raise AssertionError("Launcher readiness timeout")
                time.sleep(0.2)
            state = json.loads(metadata.read_text())
            assert state["url"].startswith("http://127.0.0.1:")
            with OPENER.open(state["url"] + "/_stcore/health", timeout=5) as response:
                assert response.status == 200
            launches.append(round(time.perf_counter() - start, 3))
            run(executable, "--no-browser", "--data-dir", data, timeout=15)
            assert json.loads(metadata.read_text())["pid"] == state["pid"]
        finally:
            if (data / "launcher.json").exists():
                run(executable, "--stop", "--data-dir", data, timeout=15)
            process.wait(timeout=20)
        assert not metadata.exists()
        try:
            OPENER.open(state["url"] + "/_stcore/health", timeout=1)
        except OSError:
            pass
        else:
            raise AssertionError("Server still running after exit")
    assert list((data / "backups").glob("*.zip")), "Restart should create a safety backup"
    return smoke | {"launch_seconds": launches, "duplicate_launch": "passed", "restart": "passed", "stop": "passed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path)
    args = parser.parse_args()
    audit = ROOT / ".tools" / ("release-audit-" + uuid.uuid4().hex[:8])
    audit.mkdir(parents=True)
    executable = ROOT / "dist" / "USECTA-Document-Generator" / "USECTA-Document-Generator.exe"
    if not args.installer:
        report = check_application(executable, audit / "bundle")
    else:
        for key in [r"Software\USECTA\DocumentGenerator", r"Software\Microsoft\Windows\CurrentVersion\Uninstall\USECTA-Document-Generator"]:
            try:
                handle = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key)
            except FileNotFoundError:
                continue
            handle.Close()
            raise SystemExit("An existing USECTA installation is registered. Use a clean test account.")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as folders:
            desktop = Path(os.path.expandvars(winreg.QueryValueEx(folders, "Desktop")[0]))
            programs = Path(os.path.expandvars(winreg.QueryValueEx(folders, "Programs")[0]))
        shortcuts = [desktop / "USECTA Document Generator.lnk", programs / "USECTA Document Generator"]
        if any(path.exists() for path in shortcuts):
            raise SystemExit("Existing USECTA shortcuts must not be overwritten by an acceptance test.")
        install = (audit / "Installed USECTA").resolve()
        assert install.is_relative_to((ROOT / ".tools").resolve())
        setup = args.installer.resolve()
        for attempt in range(2):
            subprocess.run(f'"{setup}" /S /D={install}', check=True, timeout=600)
            assert (install / "USECTA-Document-Generator.exe").is_file()
            assert shortcuts[0].exists() and (shortcuts[1] / "USECTA Document Generator.lnk").exists()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\USECTA-Document-Generator") as registration:
                assert winreg.QueryValueEx(registration, "UninstallString")[0] == '"' + str(install / "Uninstall.exe") + '"'
            if attempt == 0:
                report = check_application(install / "USECTA-Document-Generator.exe", audit / "installed")
        databases = list((audit / "installed/workspace").glob("*.db")) + list((audit / "installed/workspace").glob("*.sqlite3"))
        assert databases
        before = databases[0].read_bytes()
        run(install / "Uninstall.exe", "/S", timeout=120)
        deadline = time.monotonic() + 120
        while (install / "_internal").exists():
            assert time.monotonic() < deadline, "Uninstaller did not remove bundled application files"
            time.sleep(0.2)
        assert not (install / "USECTA-Document-Generator.exe").exists()
        assert not shortcuts[0].exists() and not shortcuts[1].exists()
        assert databases[0].read_bytes() == before
        report |= {"silent_install": "passed", "upgrade": "passed", "uninstall_preserves_workspace": "passed"}
    (audit / "acceptance.json").write_text(json.dumps(report, indent=2))
    print("Acceptance report:", audit / "acceptance.json")


if __name__ == "__main__":
    main()
