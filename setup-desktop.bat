@echo off
cd /d "%~dp0"
echo Preparing the USECTA desktop edition. Internet is needed for this first setup.
echo No Python installation or IDE is required.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-desktop.ps1"
if errorlevel 1 (
    echo.
    echo Setup did not finish. Check the error above, then rerun this file.
    pause
    exit /b 1
)
echo.
echo Setup complete. Open USECTA Documents from your desktop.
pause
