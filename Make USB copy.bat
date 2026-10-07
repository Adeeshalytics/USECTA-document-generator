@echo off
cd /d "%~dp0"
if not exist "runtime\python\python.exe" (
    echo Run setup-desktop.bat first to prepare the portable runtime.
    pause
    exit /b 1
)
"%~dp0runtime\python\python.exe" "%~dp0scripts\make-usb-copy.py"
if errorlevel 1 (
    pause
    exit /b 1
)
pause
