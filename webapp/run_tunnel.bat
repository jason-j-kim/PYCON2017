@echo off
REM ── 소크라테스 평가 · 터널 배포용 서버 실행 (Windows) ──────────────────
REM  Claude Pro/Max 구독으로 로그인된 PC에서 실행한다. API 키 불필요.
REM  실행할 때마다 초대 비밀번호를 새로 입력받는다(코드에 저장하지 않음).
chcp 65001 >nul
cd /d "%~dp0\.."

set /p SOCRATIC_ACCESS_CODE=새 초대 비밀번호를 입력하세요:
if "%SOCRATIC_ACCESS_CODE%"=="" (
  echo [중단] 비밀번호가 비어 있습니다. 외부 공개 시 반드시 설정해야 합니다.
  pause
  exit /b 1
)
set SOCRATIC_MAX_SESSIONS_PER_DAY=30

echo.
echo ===============================================================
echo  서버를 시작합니다 (http://localhost:8000)
echo  초대 비밀번호: %SOCRATIC_ACCESS_CODE%
echo  하루 최대 세션: %SOCRATIC_MAX_SESSIONS_PER_DAY%
echo.
echo  ▶ 이 창은 그대로 두세요. (서버 로그가 여기 표시됩니다)
echo  ▶ 두 번째 cmd 창을 열어 아래를 실행하면 외부 접속 주소가 나옵니다:
echo        cloudflared tunnel --url http://localhost:8000
echo  ▶ 종료: 이 창에서 Ctrl+C
echo ===============================================================
echo.

python webapp\app.py
