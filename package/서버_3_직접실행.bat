@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" deploy_win\run_server.py
) else (
  python deploy_win\run_server.py
)
pause
