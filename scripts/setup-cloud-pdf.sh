#!/usr/bin/env bash
# Rootless LibreOffice setup for the Debian 13 cloud machine.
set -euo pipefail
repo_dir=$(cd "$(dirname "$0")/.." && pwd)
runtime_dir="$repo_dir/data/pdf-runtime"
mkdir -p "$runtime_dir/apt/lists/partial" "$runtime_dir/apt/archives/partial" "$runtime_dir/apt/conf" "$runtime_dir/bin"
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main' > "$runtime_dir/apt/sources.list"
apt_options=(-o "Dir::Etc::parts=$runtime_dir/apt/conf" -o "Dir::Etc::sourcelist=$runtime_dir/apt/sources.list" -o Dir::Etc::sourceparts=- -o "Dir::State::lists=$runtime_dir/apt/lists" -o "Dir::Cache::archives=$runtime_dir/apt/archives" -o "APT::Sandbox::User=$(id -un)" -o Debug::NoLocking=true -o Acquire::Retries=0)
apt-get "${apt_options[@]}" update
apt-get "${apt_options[@]}" --download-only --no-install-recommends -y install libreoffice-writer fonts-crosextra-carlito
for package in "$runtime_dir"/apt/archives/*.deb; do
    dpkg-deb -x "$package" "$runtime_dir/libreoffice"
done
python3 - "$runtime_dir" <<'PY'
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape

runtime = Path(sys.argv[1])
root = runtime / 'libreoffice'
config = root / 'etc/libreoffice/registry/main.xcd'
config.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / 'usr/lib/libreoffice/share/.registry/main.xcd', config)
for path in root.rglob('*'):
    if path.is_symlink():
        target = path.readlink()
        relocated = root / str(target).lstrip('/')
        if target.is_absolute() and not str(target).startswith(str(root)) and relocated.exists():
            path.unlink()
            path.symlink_to(relocated)
for name in ['fundamentalrc', 'sofficerc']:
    path = root / 'usr/lib/libreoffice/program' / name
    path.write_text(path.read_text().replace('file:///usr/lib/libreoffice', (root / 'usr/lib/libreoffice').as_uri()).replace('file:///etc/libreoffice/sofficerc', (root / 'etc/libreoffice/sofficerc').as_uri()))
(runtime / 'fonts.conf').write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><include>/etc/fonts/fonts.conf</include><dir>' + escape(str(root / 'usr/share/fonts')) + '</dir><cachedir>' + escape(str(runtime / 'font-cache')) + '</cachedir></fontconfig>')
PY
cat > "$runtime_dir/bin/libreoffice" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
runtime_dir=$(cd "$(dirname "$0")/.." && pwd)
export LD_LIBRARY_PATH="$runtime_dir/libreoffice/usr/lib/libreoffice/program:$runtime_dir/libreoffice/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export FONTCONFIG_FILE="$runtime_dir/fonts.conf"
export XDG_CACHE_HOME="$runtime_dir/cache"
export GSETTINGS_BACKEND=memory
exec "$runtime_dir/libreoffice/usr/lib/libreoffice/program/soffice" "$@"
SH
chmod +x "$runtime_dir/bin/libreoffice"
"$runtime_dir/bin/libreoffice" --headless --version
