@echo off
cd /d "%~dp0"
if not exist "runtime\python\pythonw.exe" exit /b 0
start "" "%~dp0runtime\python\pythonw.exe" "%~dp0desktop.py" --stop
