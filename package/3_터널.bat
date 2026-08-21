@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  ===== 3. 외부 공개 (선택) =====
echo.
echo   먼저 2_실행.bat 이 켜져 있어야 합니다. 이 창은 따로 띄우세요.
echo.

cloudflared --version >nul 2>&1
if errorlevel 1 (
  echo  [!] cloudflared 가 없습니다.
  echo.
  echo      https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
  echo      에서 Windows 64-bit 를 받아 cloudflared.exe 를 이 폴더에 두거나
  echo      PATH 에 넣은 뒤 다시 실행하세요.
  echo.
  pause & exit /b
)

echo   잠시 뒤 화면에 https://....trycloudflare.com 주소가 나옵니다.
echo   그 주소 뒤에 /policy 를 붙여서 공유하세요.
echo.
echo   예)  https://abcd-efgh.trycloudflare.com/policy
echo.
echo   ※ 켤 때마다 주소가 바뀝니다. 이 창을 닫으면 외부 접속이 끊깁니다.
echo.

cloudflared tunnel --url http://localhost:8000

echo.
pause
