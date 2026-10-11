# Build the offline Windows installer

Build on Windows x64 with Python 3.12. Building needs internet access to fetch
dependencies and vendor tools; installation and normal use do not.

1. Create `.venv` using `py -3.12 -m venv .venv`.
2. Install `requirements-build.txt` in that environment.
3. Obtain a verified, unmodified LibreOffice Windows x64 runtime. Place its
   extracted contents under `vendor/pdf-runtime`, including `program/soffice.exe`,
   share, presets, fonts, and all licence/notices files. Do not copy only soffice.exe.
4. Run `.venv\Scripts\python.exe scripts\build_windows.py`.
   This keeps the extracted VC DLLs app-local and places bundled fonts in
   LibreOffice's private font folder; no system-wide font/runtime installation
   is needed. The self-contained converter is copied after freezing Python.
5. Compile `installer/USECTA.nsi` using the portable NSIS compiler, passing
   `/DBUILDROOT=C:\absolute\project\path`. Create `release/` first. The portable
   compiler is unpacked under `.tools/NSIS` and is not installed system-wide.
6. Run the packaged executable with `--self-test --data-dir C:\path\to\audit`.
   Review `offline-smoke.json`; the full offline release must report PDF passed.
7. Run the installer, UI, restart, upgrade and uninstall checks in
   `RELEASE_CHECKLIST.md` on a clean Windows machine.

The distribution is a one-folder PyInstaller build, installed by a single
setup executable. It does not unpack its entire runtime at every launch.
Never package `.streamlit/secrets.toml`, a personal data folder, exports,
backups, logs, or developer tools. Vendor downloads and build output are ignored.
Updates retain the installation registry key and user workspace path. Increment
the version in desktop_paths.py and installer/USECTA.nsi together.

Use `--no-browser` for automated launcher checks, `--stop` for graceful shutdown,
and `--data-dir` to keep tests isolated from company data. Application logs are
stored under the selected workspace. The application binds to localhost only
and rejects external network connections in its server process.
