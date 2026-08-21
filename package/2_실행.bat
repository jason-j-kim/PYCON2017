@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal enabledelayedexpansion

REM 초대 코드 — 원하는 값으로 바꾸세요. 접속할 때 이 코드를 입력합니다.
set SOCRATIC_ACCESS_CODE=kdi2026

REM ③ 국회 의안 키는 keys.local.bat 에 있습니다(1_설치.bat 이 만듭니다).
if exist keys.local.bat call keys.local.bat

echo.
echo  ===== 2. 서버 실행 =====
echo.

REM ── 포트 8000이 남아 있으면 정리한다 (10048 오류 예방) ──────────────
REM  창을 X 로 닫으면 이전 서버가 포트를 붙잡고 있다. 그 프로세스만 끈다.
set "OLDPID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING" 2^>nul') do set "OLDPID=%%p"
if defined OLDPID (
  echo   이전 서버^(PID !OLDPID!^)가 포트 8000을 잡고 있어 정리합니다.
  taskkill /F /PID !OLDPID! >nul 2>&1
  timeout /t 2 >nul
)

echo   초대 코드 : %SOCRATIC_ACCESS_CODE%
echo   주소      : http://localhost:8000/policy
if defined ASSEMBLY_KEY (
  echo   국회 의안 : 키 확인됨 - 네 통로 모두 켜집니다
) else (
  echo   국회 의안 : 키 없음 - ③ 통로만 꺼집니다
  echo               ^(넣으려면 1_설치.bat 을 다시 실행하세요^)
)
echo.
echo   잠시 뒤 브라우저가 자동으로 열립니다.
echo   끌 때는 이 창에서 Ctrl+C 를 누르세요.
echo.

REM 서버가 뜬 뒤 브라우저를 연다(서버 실행은 이 창을 붙잡으므로 따로 띄운다).
start "" /min cmd /c "timeout /t 6 >nul & start http://localhost:8000/policy"

python webapp\app.py

echo.
echo  서버가 멈췄습니다.
pause
