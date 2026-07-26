@echo off
REM ── keys.local.bat 예시 ────────────────────────────────────────────────
REM  이 파일을 keys.local.bat 으로 복사한 뒤 실제 키를 채워 넣는다.
REM  keys.local.bat 은 .gitignore 에 있어 저장소에 올라가지 않는다.
REM
REM  · 첫 줄 @echo off 로 call 할 때 키가 화면에 찍히지 않게 한다.
REM  · 값은 따옴표 없이 붙여넣는다 (set KEY=abc  O   /   set KEY="abc"  X).
REM  · 재정(세출예산)은 data\fiscal.json 로컬 파일이라 키가 필요 없다.

REM PRISM(정책연구) — 공공데이터포털(data.go.kr) 일반 인증키(인코딩/디코딩 아무거나)
set DATA_GO_KR_KEY=여기에_data_go_kr_키

REM 국회 의안 — 열린국회정보(open.assembly.go.kr) 인증키
set ASSEMBLY_KEY=여기에_열린국회_키
