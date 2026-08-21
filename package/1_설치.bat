@echo off
cd /d "%~dp0"
python setup.py
if errorlevel 9009 goto nopython
pause
exit /b
:nopython
echo.
echo  [!] Python not found. Install Python 3.10+ from python.org
echo      and be sure to check "Add python.exe to PATH".
echo.
pause
