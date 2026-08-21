@echo off
cd /d "%~dp0"
python start.py
if errorlevel 9009 goto nopython
pause
exit /b
:nopython
echo.
echo  [!] Python not found. Run the install batch (1) first.
echo.
pause
