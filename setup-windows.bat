@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Setup complete. Double-click run-windows.bat to start the app.
pause
exit /b 0
:failed
echo.
echo Setup failed. Check the message above. Python 3.12 or newer is required.
pause
exit /b 1
