@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ===== 1. 설치 (처음 한 번만) =====
echo.

python --version
if errorlevel 1 (
  echo.
  echo  [!] Python 이 없습니다. python.org 에서 3.10 이상을 설치하세요.
  pause & exit /b
)

echo.
echo  [1/4] 파이썬 패키지 설치
pip install -r webapp\requirements.txt
if errorlevel 1 (
  echo.
  echo  [!] 패키지 설치 실패. 인터넷 연결을 확인하세요.
  pause & exit /b
)

echo.
echo  [2/4] Claude Code 설치
node --version
if errorlevel 1 (
  echo.
  echo  [!] Node.js 가 없습니다. nodejs.org 에서 18 이상을 설치한 뒤
  echo      이 파일을 다시 실행하세요.
  pause & exit /b
)
call npm install -g @anthropic-ai/claude-code

echo.
echo  [3/4] Claude 로그인
echo.
echo   이제 claude 가 실행됩니다.
echo   창이 열리면  /login  을 입력해 본인 Claude 계정(Pro 또는 Max)으로
echo   로그인한 뒤,  /exit  로 나오세요. 한 번만 하면 됩니다.
echo.
pause
call claude

echo.
echo  [4/4] 국회 의안 키 (선택)
call :setup_key

echo.
echo  ===== 설치 끝. 다음은 2_실행.bat =====
pause
exit /b


REM ── 키 설정: 파일 복사도 편집도 필요 없이 여기서 만든다 ──────────────
:setup_key
if exist keys.local.bat (
  echo.
  echo   keys.local.bat 이 이미 있습니다. 통로를 점검합니다.
  call keys.local.bat
  python webapp\check_bill.py
  echo.
  echo   키를 바꾸려면 keys.local.bat 을 지우고 이 파일을 다시 실행하세요.
  exit /b
)

echo.
echo   ③ 국회 의안 통로만 키가 필요합니다.
echo   발급처: https://open.assembly.go.kr  (열린국회정보)
echo   ※ 공공데이터포털(data.go.kr) 키와는 다릅니다.
echo.
echo   키가 없거나 나중에 하려면 그냥 Enter 를 누르세요.
echo   나머지 세 통로(재정·KDI 연구·해외사례)는 키 없이 그대로 작동합니다.
echo.
set "ASMKEY="
set /p ASMKEY=  인증키를 붙여넣으세요:

if not defined ASMKEY (
  echo.
  echo   건너뜁니다. ③ 통로만 꺼진 상태로 쓰시면 됩니다.
  echo   나중에 넣으려면 이 파일을 다시 실행하세요.
  exit /b
)

echo "%ASMKEY%" | findstr /C:"%%" >nul
if not errorlevel 1 (
  echo.
  echo   [!] 키에 %% 문자가 있습니다. 배치 파일에서 깨집니다.
  echo       인코딩된 키 대신 디코딩된 키를 쓰세요.
  exit /b
)

REM 첫 줄 @echo off 로 키가 화면에 찍히지 않게 한다.
(
echo @echo off
echo REM 이 파일은 1_설치.bat 이 만들었습니다. 남에게 주지 마세요.
echo set ASSEMBLY_KEY=%ASMKEY%
) > keys.local.bat

set ASSEMBLY_KEY=%ASMKEY%
set "ASMKEY="

echo.
echo   keys.local.bat 을 만들었습니다. 실제로 되는지 확인합니다.
echo.
python webapp\check_bill.py
exit /b
