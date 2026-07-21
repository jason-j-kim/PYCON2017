# 소수 연구자 대상 터널 배포 (대안 C)

교수님 PC의 **Claude Pro/Max 구독**으로 서버를 돌리고, 임시 터널로 외부
연구자가 접속해 실제 문답 테스트를 하게 하는 방법이다. **API 키가 필요 없다.**

> 주의: Pro 구독으로 외부 사용자에게 서비스하는 것은 약관상 회색지대다.
> **소규모·단기 테스트**에만 쓰고, 지속 운영은 API 키/클라우드로 전환한다.
> 접속 비밀번호와 하루 세션 상한이 안전장치로 걸려 있다.

## 사전 준비 (최초 1회)

1. Claude Code 로그인 확인: `claude /login` (Pro/Max 계정)
2. 웹 의존성: `pip install fastapi "uvicorn[standard]"`
3. cloudflared 설치 (터널 도구, 무료):
   - <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/>
   - Windows용 `cloudflared.exe` 를 받아 PATH에 두거나 저장소 폴더에 둔다.
   - 설치 확인: `cloudflared --version`

## 실행 (매번)

**첫 번째 cmd 창** — 서버:

```
run_tunnel.bat
```

(저장소 루트에서 `webapp\run_tunnel.bat`) 실행하면 **새 초대 비밀번호**를
물어본다. 원하는 값을 입력하면 서버가 그 비밀번호로 켜진다.

**두 번째 cmd 창** — 터널:

```
cloudflared tunnel --url http://localhost:8000
```

몇 초 뒤 `https://<임의문자>.trycloudflare.com` 형태의 **공개 주소**가 출력된다.

## 연구자에게 전달할 것

- 공개 주소: `https://....trycloudflare.com`
- 그중 원본: `/` · 수정판(정책): `/policy`
- **초대 비밀번호**: 방금 입력한 값 (별도 채널로 전달)

## 비밀번호 변경

`run_tunnel.bat` 은 실행할 때마다 비밀번호를 새로 입력받으므로, **다음에 켤 때
다른 값을 입력하면 그게 새 비밀번호**가 된다. 코드나 저장소에는 저장되지 않는다.

## 종료

- 서버 창: `Ctrl+C`
- 터널 창: `Ctrl+C` (창을 닫으면 그 주소는 즉시 무효)

## 안전장치 (환경 변수)

| 변수 | 기본 | 뜻 |
|---|---|---|
| `SOCRATIC_ACCESS_CODE` | (없음) | 초대 비밀번호. 비어 있으면 누구나 접속 → 외부 공개 시 필수 |
| `SOCRATIC_MAX_SESSIONS_PER_DAY` | 30 | 하루 세션 상한(구독 남용 방지). `run_tunnel.bat`에서 조정 |
