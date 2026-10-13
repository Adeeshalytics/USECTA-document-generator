"""Build the offline bundle and preserve dependency licence notices."""
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "prepare_icon.py")], cwd=ROOT, check=True)
    # Administrative MSI extraction puts VC runtimes and fonts outside program/.
    # Keep dependencies app-local, and fonts private to LibreOffice (no OS install).
    runtime = ROOT / "vendor" / "pdf-runtime"
    for source in (runtime / "System64").glob("*.dll"):
        shutil.copy2(source, runtime / "program" / source.name)
    font_dir = runtime / "share" / "fonts" / "truetype"
    font_dir.mkdir(parents=True, exist_ok=True)
    for source in (runtime / "Fonts").glob("*.ttf"):
        shutil.copy2(source, font_dir / source.name)
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(ROOT / "USECTA.spec")], cwd=ROOT, check=True)
    bundle = ROOT / "dist" / "USECTA-Document-Generator" / "_internal"
    config_dir = bundle / ".streamlit"
    config_dir.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "offline_config" / "config.toml", config_dir / "config.toml")
    for entry in runtime.iterdir():
        if entry.suffix.lower() == ".msi" or entry.name in {"Fonts", "System64", "System32", "System"}:
            continue
        target = bundle / "pdf-runtime" / entry.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)
    notices = bundle / "dependency-licenses"
    notices.mkdir(exist_ok=True)
    python_notice = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_notice.exists():
        raise SystemExit("Python's LICENSE.txt must accompany the embedded runtime.")
    shutil.copy2(python_notice, notices / "Python-LICENSE.txt")
    inventory = [{"name": "Python", "version": sys.version.split()[0], "license": "Python Software Foundation License"}]
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        inventory.append({"name": name, "version": distribution.version, "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License", "See bundled notices")})
        for entry in distribution.files or []:
            label = str(entry).lower()
            if "license" in label or "copying" in label or "notice" in label:
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    safe_parts = [part for part in Path(str(entry)).parts if part not in {"..", ".", "/", "\\"}]
                    target = notices / name / Path(*safe_parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())
    (bundle / "third-party-inventory.json").write_text(json.dumps(inventory, indent=2))
    compiler_notice = ROOT / ".tools" / "NSIS" / "nsis-3.13" / "COPYING"
    if compiler_notice.exists():
        shutil.copy2(compiler_notice, notices / "NSIS-COPYING.txt")
    print("Bundle ready:", bundle.parent)


if __name__ == "__main__":
    main()
