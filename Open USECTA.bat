@echo off
cd /d "%~dp0"
if not exist "runtime\python\pythonw.exe" (
    echo Run setup-desktop.bat once before opening USECTA.
    pause
    exit /b 1
)
start "" "%~dp0runtime\python\pythonw.exe" "%~dp0desktop.py"
