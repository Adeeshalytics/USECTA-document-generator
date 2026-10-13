# Build on Windows using Python 3.12: python -m PyInstaller USECTA.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / name), ".") for name in ["app.py", "OFFLINE_USER_GUIDE.md", "THIRD_PARTY_NOTICES.md"]]
datas += [(str(root / "company_templates"), "company_templates"), (str(root / "catalogues"), "catalogues")]
datas += [(str(root / "assets"), "assets")]
binaries = []
hidden = ["documents", "workflows", "cloud_access", "backup_ui", "workspace_archive", "offline_smoke", "desktop_paths", "sample_labels", "sample_labels_ui"]
for package in ["streamlit", "docxtpl", "docx", "openpyxl", "uvicorn", "websockets", "httptools", "anyio"]:
    package_data, package_binaries, package_hidden = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hidden += package_hidden
datas += copy_metadata("streamlit")
pdf_runtime = root / "vendor" / "pdf-runtime"
if not (pdf_runtime / "program" / "soffice.exe").is_file():
    raise SystemExit("Full offline build requires vendor/pdf-runtime/program/soffice.exe. See BUILD_WINDOWS.md.")
# The complete self-contained vendor tree is copied by build_windows.py after
# freezing Python. Do not reclassify its thousands of non-Python DLL/resources.

a = Analysis([str(root / "launcher.py")], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hidden, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=["pytest", "streamlit.testing", "IPython", "matplotlib", "tkinter"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="USECTA-Document-Generator",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, icon=str(root / "assets" / "usecta-icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="USECTA-Document-Generator")
