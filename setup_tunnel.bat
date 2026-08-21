@echo off
chcp 65001 >nul
REM ===================================================================
REM  고정 터널 주소 만들기 (Cloudflare Named Tunnel)
REM
REM  무료 터널(trycloudflare.com)은 켤 때마다 주소가 바뀐다.
REM  Named Tunnel을 쓰면 https://policy.본인도메인.com 처럼 고정된다.
REM
REM  준비물: Cloudflare 계정 + Cloudflare에 등록한 도메인 1개
REM          (도메인이 없으면 이 방법은 쓸 수 없다 — README 참조)
REM
REM  최초 1회만 실행한다. 그 뒤로는 run_tunnel.bat 만 쓰면 된다.
REM ===================================================================

setlocal
set TUNNEL_NAME=policy

echo.
echo  [1/4] Cloudflare 로그인 — 브라우저가 열리면 도메인을 선택하세요.
echo.
cloudflared tunnel login
if errorlevel 1 goto :fail

echo.
echo  [2/4] 터널 생성 (이름: %TUNNEL_NAME%)
echo.
cloudflared tunnel create %TUNNEL_NAME%
REM 이미 있으면 오류가 나지만 계속 진행한다.

echo.
echo  [3/4] 고정 주소 연결
echo.
set /p HOSTNAME=  사용할 주소를 입력하세요 (예: policy.example.com):
if "%HOSTNAME%"=="" goto :nohost
cloudflared tunnel route dns %TUNNEL_NAME% %HOSTNAME%
if errorlevel 1 goto :fail

echo.
echo  [4/4] 실행 스크립트 생성
(
echo @echo off
echo chcp 65001 ^>nul
echo REM 고정 주소 터널 실행 — 서버^(python webapp\app.py^)를 먼저 켜 두세요.
echo echo.
echo echo   고정 주소: https://%HOSTNAME%/policy
echo echo.
echo cloudflared tunnel run --url http://localhost:8000 %TUNNEL_NAME%
) > run_tunnel.bat

echo.
echo ===================================================================
echo   설정 완료
echo.
echo   고정 주소:  https://%HOSTNAME%/policy
echo.
echo   앞으로는 창 두 개만 띄우면 됩니다:
echo     1^) python webapp\app.py
echo     2^) run_tunnel.bat
echo ===================================================================
goto :eof

:nohost
echo   주소를 입력하지 않아 중단합니다.
goto :eof

:fail
echo.
echo   실패했습니다. 다음을 확인하세요:
echo     - cloudflared 가 설치되어 있는가
echo     - Cloudflare 계정에 도메인이 등록되어 있는가
goto :eof
