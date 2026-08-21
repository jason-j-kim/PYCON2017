@echo off
REM ── 이 파일을 keys.local.bat 으로 복사한 뒤 키를 채워 넣으세요. ──────
REM
REM  2_실행.bat 이 keys.local.bat 이 있으면 자동으로 불러옵니다.
REM  첫 줄 @echo off 는 지우지 마세요 — 키가 화면에 찍히지 않게 합니다.
REM  값은 따옴표 없이 붙여넣습니다.  set KEY=abc  (O)   set KEY="abc"  (X)
REM
REM  키가 없어도 됩니다. ③ 국회 의안 통로만 꺼지고 나머지 세 통로
REM  (재정·KDI 연구·해외사례)는 데이터가 폴더에 있어 그대로 작동합니다.

REM ③ 국회 의안 — 열린국회정보 open.assembly.go.kr 에서 발급
set ASSEMBLY_KEY=여기에_열린국회_인증키

REM (선택) 초대 코드를 여기서 바꿔도 됩니다.
REM set SOCRATIC_ACCESS_CODE=원하는코드
