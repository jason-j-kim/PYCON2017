@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 초대 코드 — 원하는 값으로 바꾸세요. 접속할 때 이 코드를 입력합니다.
set SOCRATIC_ACCESS_CODE=kdi2026

REM ── ③ 국회 의안 통로 키 ────────────────────────────────────────────
REM  키는 이 파일에 적지 않는다. keys.local.bat 에 넣으면 여기서 불러온다.
REM  (keys.example.bat 을 keys.local.bat 으로 복사해 키를 채우세요.)
REM  키가 없어도 나머지 세 통로는 정상 작동합니다.
if exist keys.local.bat call keys.local.bat

echo.
echo  ===== 2. 서버 실행 =====
echo.
echo   초대 코드 : %SOCRATIC_ACCESS_CODE%
echo   주소      : http://localhost:8000/policy
if defined ASSEMBLY_KEY (
  echo   국회 의안 : 키 확인됨 - 네 통로 모두 켜집니다
) else (
  echo   국회 의안 : 키 없음 - ③ 통로만 꺼집니다 ^(keys.local.bat 참고^)
)
echo.
echo   끌 때는 이 창에서 Ctrl+C 를 누르세요.
echo   (창을 X 로 닫으면 포트가 남아 다음 실행에서 10048 오류가 납니다.
echo    그때는 명령창에  taskkill /F /IM python.exe  를 실행하세요.)
echo.

python webapp\app.py

echo.
echo  서버가 멈췄습니다.
pause
