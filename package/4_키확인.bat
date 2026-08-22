@echo off
cd /d "%~dp0"
python webapp\check_claude.py
if errorlevel 9009 goto nopython
pause
exit /b
:nopython
echo.
echo  [!] Python not found. Run the install batch (1) first.
echo.
pause
