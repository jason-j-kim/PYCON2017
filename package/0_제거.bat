@echo off
cd /d "%~dp0"
python uninstall.py
if errorlevel 9009 goto nopython
pause
exit /b
:nopython
echo.
echo  [!] Python not found. Nothing to remove by script.
echo.
pause
