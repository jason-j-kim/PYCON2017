@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 초대 코드 — 원하는 값으로 바꾸세요. 접속할 때 이 코드를 입력합니다.
set SOCRATIC_ACCESS_CODE=kdi2026

REM 국회 의안 통로를 켜려면 아래 줄 앞의 REM 을 지우고 키를 넣으세요.
REM  (공공데이터포털 발급. 없어도 나머지 세 통로는 정상 작동합니다.)
REM set ASSEMBLY_KEY=발급받은키

echo.
echo  ===== 2. 서버 실행 =====
echo.
echo   초대 코드 : %SOCRATIC_ACCESS_CODE%
echo   주소      : http://localhost:8000/policy
echo.
echo   끌 때는 이 창에서 Ctrl+C 를 누르세요.
echo   (창을 X 로 닫으면 포트가 남아 다음 실행에서 10048 오류가 납니다.
echo    그때는 명령창에  taskkill /F /IM python.exe  를 실행하세요.)
echo.

python webapp\app.py

echo.
echo  서버가 멈췄습니다.
pause
