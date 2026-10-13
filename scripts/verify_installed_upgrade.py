"""User-authorized in-place update, with isolated tests and data preservation checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import time
import uuid
from contextlib import closing

import pefile

from verify_windows_release import ROOT, check_application


def workspace_hashes(workspace):
    paths = [workspace / "records.sqlite3"]
    for folder in ("templates", "exports"):
        if (workspace / folder).exists():
            paths.extend(path for path in (workspace / folder).rglob("*") if path.is_file())
    return {str(path.relative_to(workspace)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.is_file()}


def check_icon(executable):
    artwork = (ROOT / "assets/usecta-icon.ico").read_bytes()
    count = struct.unpack_from("<H", artwork, 4)[0]
    expected = set()
    for index in range(count):
        length, offset = struct.unpack_from("<II", artwork, 6 + index * 16 + 8)
        expected.add(artwork[offset:offset + length])
    with pefile.PE(str(executable)) as binary:
        kinds = {entry.id for entry in binary.DIRECTORY_ENTRY_RESOURCE.entries}
        assert {3, 14} <= kinds, "Windows executable lacks icon resources"
        icons = next(entry for entry in binary.DIRECTORY_ENTRY_RESOURCE.entries if entry.id == 3)
        assert len(icons.directory.entries) >= 7, "Expected seven icon resolutions"
        actual = set()
        for icon in icons.directory.entries:
            for language in icon.directory.entries:
                resource = language.data.struct
                actual.add(binary.get_data(resource.OffsetToData, resource.Size))
        assert expected <= actual, "Embedded icon does not match the supplied artwork"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--install-dir", required=True, type=Path)
    parser.add_argument("--source-passed", type=int, required=True)
    parser.add_argument("--source-skipped", type=int, default=0)
    args = parser.parse_args()
    install = args.install_dir.resolve()
    expected = (Path(os.environ["LOCALAPPDATA"]) / "Programs" / "USECTA Document Generator").resolve()
    if install != expected or not (install / "USECTA-Document-Generator.exe").is_file():
        raise SystemExit("This update check only supports the existing per-user USECTA installation.")
    workspace = Path(os.environ["LOCALAPPDATA"]) / "USECTA Document Generator"
    audit = ROOT / ".tools" / ("upgrade-audit-" + uuid.uuid4().hex[:8])
    audit.mkdir(parents=True)
    before = workspace_hashes(workspace)
    safety = audit / "pre-upgrade-workspace"
    safety.mkdir()
    database = workspace / "records.sqlite3"
    if database.exists():
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(safety / "records.sqlite3")) as backup:
                original.backup(backup)
    if (workspace / "templates").exists():
        shutil.copytree(workspace / "templates", safety / "templates")
    (audit / "before-hashes.json").write_text(json.dumps(before, indent=2))
    # NSIS /D must be the final argument; the target is validated above.
    subprocess.run(f'"{args.installer.resolve()}" /S /D={install}', check=True, timeout=600)
    executable = install / "USECTA-Document-Generator.exe"
    reference = ROOT / "dist" / "USECTA-Document-Generator" / executable.name
    assert hashlib.sha256(executable.read_bytes()).digest() == hashlib.sha256(reference.read_bytes()).digest(), "Installed executable differs from verified build"
    check_icon(executable)
    check_icon(args.installer.resolve())
    report = check_application(executable, audit / "isolated")
    after = workspace_hashes(workspace)
    assert before == after, "Company database/templates/exports changed during isolated update checks"
    report |= {"in_place_upgrade": "passed", "company_workspace_unchanged": "passed",
               "executable_and_installer_icons": "passed", "source_tests": {"passed": args.source_passed, "skipped": args.source_skipped}}
    (audit / "acceptance.json").write_text(json.dumps(report, indent=2))
    print("Updated installation:", install)
    print("Acceptance report:", audit / "acceptance.json")


if __name__ == "__main__":
    main()
