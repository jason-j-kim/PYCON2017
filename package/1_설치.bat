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
echo  [1/3] 파이썬 패키지 설치
pip install -r webapp\requirements.txt
if errorlevel 1 (
  echo.
  echo  [!] 패키지 설치 실패. 인터넷 연결을 확인하세요.
  pause & exit /b
)

echo.
echo  [2/3] Claude Code 설치
node --version
if errorlevel 1 (
  echo.
  echo  [!] Node.js 가 없습니다. nodejs.org 에서 18 이상을 설치한 뒤
  echo      이 파일을 다시 실행하세요.
  pause & exit /b
)
call npm install -g @anthropic-ai/claude-code

echo.
echo  [3/3] Claude 로그인
echo.
echo   이제 claude 가 실행됩니다.
echo   창이 열리면  /login  을 입력해 본인 Claude 계정(Pro 또는 Max)으로
echo   로그인한 뒤,  /exit  로 나오세요. 한 번만 하면 됩니다.
echo.
pause
call claude

echo.
echo  ===== 설치 끝. 다음은 2_실행.bat =====
pause
