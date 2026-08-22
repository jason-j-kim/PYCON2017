@echo off
cd /d "%~dp0"
python webapp\load_samples.py %1
if errorlevel 9009 goto nopython
pause
exit /b
:nopython
echo.
echo  [!] Python not found. Run the install batch (1) first.
echo.
pause
