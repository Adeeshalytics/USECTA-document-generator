"""Assemble a clean, relocatable desktop folder without cloud keys or developer files."""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FILES = ['app.py', 'documents.py', 'workflows.py', 'cloud_access.py', 'cloud_store.py', 'desktop.py',
         'requirements.txt', 'LOCAL_DESKTOP.md', 'setup-desktop.bat', 'Open USECTA.bat',
         'Stop USECTA.bat', 'Create desktop shortcuts.bat', 'Make USB copy.bat']
SCRIPTS = ['check-desktop.py', 'create-desktop-shortcuts.ps1', 'setup-desktop.ps1', 'make-usb-copy.py']


def copy_local_data(source, target):
    db = source / 'records.sqlite3'
    if not db.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(target / 'records.sqlite3') as backup:
            original.backup(backup)
    # Copy only templates referenced by the database snapshot, not logs/review files.
    with sqlite3.connect(target / 'records.sqlite3') as backup:
        tables = {row[0] for row in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'templates' not in tables:
            return
        names = [row[0] for row in backup.execute('SELECT filename FROM templates')]
    (target / 'templates').mkdir(exist_ok=True)
    for name in names:
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Stored template filename is invalid.')
        shutil.copy2(source / 'templates' / name, target / 'templates' / name)


def assemble(root, destination, include_data=False):
    root, destination = Path(root), Path(destination)
    if destination.exists():
        raise ValueError('Choose a new destination folder. Existing copies are never overwritten.')
    if not (root / 'runtime/ready.txt').is_file():
        raise ValueError('Run setup-desktop.bat successfully before making a USB copy.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Publish the completed folder only after every file has copied successfully.
    temporary = Path(tempfile.mkdtemp(prefix='.usecta-copy-', dir=destination.parent))
    try:
        for name in FILES:
            shutil.copy2(root / name, temporary / name)
        (temporary / 'scripts').mkdir()
        for name in SCRIPTS:
            shutil.copy2(root / 'scripts' / name, temporary / 'scripts' / name)
        for name in ['company_templates', 'catalogues']:
            shutil.copytree(root / name, temporary / name)
        # Copy only known runtime folders. Downloads, secrets, .git and .venv are excluded.
        (temporary / 'runtime').mkdir()
        for name in ['python', 'libreoffice']:
            shutil.copytree(root / 'runtime' / name, temporary / 'runtime' / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(root / 'runtime/ready.txt', temporary / 'runtime/ready.txt')
        if include_data:
            copy_local_data(root / 'data', temporary / 'data')
        temporary.replace(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-data', action='store_true')
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.include_data and args.fresh:
        parser.error('Choose either --include-data or --fresh.')
    if not (ROOT / 'runtime/ready.txt').is_file():
        raise RuntimeError('Run setup-desktop.bat once before making a USB copy.')
    import subprocess
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/check-desktop.py')], cwd=ROOT)
    if result.returncode:
        raise RuntimeError('Runtime/PDF check failed. Rerun setup-desktop.bat before sharing.')
    include = args.include_data
    if not args.include_data and not args.fresh:
        include = input('Include your saved LOCAL suppliers, edited catalogues, templates and history? [y/N]: ').strip().lower() == 'y'
    destination = args.output or ROOT / 'dist' / ('USECTA-Desktop-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    assemble(ROOT, destination, include)
    print('\nUSB folder ready: ' + str(destination))
    print('Copy this WHOLE folder to the pendrive, then to the director\'s computer.')
    print('On that computer: double-click Create desktop shortcuts.bat, then the USECTA Documents shortcut.')
    print('This copy needs no Python installation, internet or cloud login for normal use.')
    if os.name == 'nt':
        os.startfile(destination.parent)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Could not prepare USB copy: ' + str(exc), file=sys.stderr)
        sys.exit(1)
