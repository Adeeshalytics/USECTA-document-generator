@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Create the Python environment first. See README.md.
    pause
    exit /b 1
)
set "USECTA_LOCAL_MODE=1"
".venv\Scripts\python.exe" -m streamlit run app.py --server.address=127.0.0.1
pause
