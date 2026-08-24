# 윈도우 서버에 올리기

리눅스판(`deploy/`)과 같은 코드·같은 데이터다. 다른 것은 **서비스로 만드는
방법**과 **앞단 프록시**뿐이다.

| | 리눅스 | 윈도우 |
|---|---|---|
| 서비스 | systemd | **작업 스케줄러** |
| 앞단 | nginx | **IIS (URL Rewrite + ARR)** |
| 인증서 | certbot | IIS 관리자에서 바인딩 |
| 설정 파일 | `/etc/policy-eval.env` (600) | `keys.local.bat` |

---

## 왜 NSSM 이 아니라 작업 스케줄러인가

윈도우에서 파이썬 앱을 서비스로 만드는 길은 셋이다.

- **NSSM** — 가장 흔하지만 외부 실행 파일을 따로 받아야 한다. 기관 서버에
  출처가 분명하지 않은 바이너리를 들이는 것은 승인이 어렵다.
- **pywin32** — 꾸러미를 하나 더 깔고 서비스 클래스를 써야 한다.
- **작업 스케줄러** — 윈도우에 이미 들어 있다. 받을 것이 없다. ← 이것을 쓴다

작업 스케줄러도 부팅 시 자동 실행·실패 시 재시작·로그온 없이 실행을 모두
한다. `services.msc` 목록에 안 보인다는 점만 다르다. 등록되는 작업 이름은
`PolicyEval` 이고, 부팅 30초 뒤에 뜨며, 죽으면 1분 뒤 다시 켠다.

---

## 순서

압축을 풀고 그 폴더 안에서 순서대로 누른다.

```
서버_1_설치.bat          가상환경 · 꾸러미 · 접속 코드
서버_2_서비스등록.bat    ← 오른쪽 클릭 → [관리자 권한으로 실행]
서버_4_상태확인.bat      떠 있는지 · 실제로 응답하는지
```

`서버_1_설치.bat` 이 접속 코드를 새로 만들어 화면에 찍어 준다. **적어 두어야
한다** — 방문자에게 알려 줄 값이다. 놓쳤으면 `keys.local.bat` 의
`SOCRATIC_ACCESS_CODE` 를 보면 된다.

먼저 손으로 켜 보려면 `서버_3_직접실행.bat`. 창을 닫으면 꺼지므로 시험용이다.
오류가 있으면 이 창에 그대로 나온다.

### 미리 있어야 할 것

- **Python 3.10 이상** — 설치할 때 `Add python.exe to PATH` 체크
- **IIS** — 역할 추가에서 켠다
- **URL Rewrite** 와 **Application Request Routing** 모듈 — 아래 참조
- 도메인 하나와 **인증서**
- 방화벽 **443** 열기
- 바깥으로 나가는 통신: `api.anthropic.com`(필수),
  `open.assembly.go.kr`(의안 통로를 쓸 때만)

---

## IIS 앞단

모듈 두 개를 먼저 깐다. 없으면 규칙이 조용히 무시되고 404 가 난다.

- URL Rewrite — <https://www.iis.net/downloads/microsoft/url-rewrite>
- Application Request Routing — <https://www.iis.net/downloads/microsoft/application-request-routing>

ARR 은 설치한 뒤 한 번 켜야 한다.

```
IIS 관리자 → 서버 노드 → Application Request Routing Cache
          → Server Proxy Settings → Enable proxy 체크 → 적용
```

그다음 사이트를 하나 만들고(실체 경로는 아무 빈 폴더여도 된다) 이 폴더의
`web.config` 를 그 경로에 복사한다. 규칙 셋이 들어 있다.

| 규칙 | 하는 일 |
|---|---|
| `BlockRecords` | `/records` 와 `/api/records` 를 404 로 막는다 |
| `ForceHttps` | 평문을 https 로 보낸다 — **주석으로 되어 있다** |
| `ToUvicorn` | 나머지를 `127.0.0.1:8000` 으로 넘긴다 |

`ForceHttps` 는 인증서를 붙인 **뒤에** 주석을 푼다. 인증서 없이 켜면 접속이
아예 안 된다.

인증서는 IIS 관리자에서 사이트 바인딩(https, 443)에 붙인다.

### IIS 를 쓰지 않는다면

`run_server.py` 를 `HOST=0.0.0.0` 으로 띄우고 uvicorn 에 인증서를 직접
물릴 수도 있다. 다만 그러면 `BlockRecords` 겹막기와 요청 제한이 없어지고,
앱 안의 잠금장치 하나만 남는다. 기관 서버라면 IIS 를 앞에 두는 편이 낫다.

---

## 기록 화면은 밖에서 열리지 않는다

`/records` 는 **서버가 도는 그 기계에서 연 것만** 통과한다. 프록시가 붙인
머리표(`X-Forwarded-For` 등)가 하나라도 있으면 403 이다. IIS 쪽에서도 404 로
한 번 더 막는다.

일부러 그렇게 두었다. `sessions.db` 에는 여러 사람의 문답이 함께 쌓이므로,
접속한 사람이 남의 대화를 받아 갈 수 있으면 안 된다. 초대 코드로 막는 것으로는
부족하다 — 참여자 전원이 아는 값이다.

**운영자는 서버에 원격 데스크톱으로 들어가** 그 기계의 브라우저에서
`http://localhost:8000/records` 를 연다.

`run_server.py` 에 `--proxy-headers` 를 붙이지 않는다. 그 옵션은
`X-Forwarded-For` 를 `client.host` 로 바꿔치기하는데, 잠금장치가 보는 것이
바로 그 값이다. 붙이면 밖에서 온 요청이 내부 주소로 위장해 통과한다.

---

## 판은 `personal` 이다

`mode.txt` 한 줄이 판을 가른다. 갈리는 것은 **누가 Claude 요금을 내는가**다.

| | `personal` (이 zip) | `experiment` |
|---|---|---|
| 방문자가 넣는 것 | 초대 코드 + 자기 API 키 | 초대 코드만 |
| 요금 | 방문자 각자 | 기관 키 하나에 전부 |

밖에 공개한다면 `personal` 이어야 한다. 초대 코드는 참여자 전원이 아는 값이라
반드시 샌다. `experiment` 로 열어 두면 코드가 새는 순간 남의 실험이 기관
카드로 결제된다. 아이디어 1건에 300~600원이다.

`experiment` 로 바꾸려면 `mode.txt` 를 고치고 `keys.local.bat` 에
`set ANTHROPIC_API_KEY=sk-ant-…` 를 넣은 뒤 작업을 다시 켠다. 그때는 콘솔에서
그 키에 월 사용 한도를 반드시 건다.

`personal` 판에서는 `keys.local.bat` 에 `ANTHROPIC_API_KEY` 를 **넣지
않는다.** 넣으면 방문자가 키를 안 넣어도 그 키로 돌아가 요금이 기관에 붙는다.
`서버_1_설치.bat` 이 이 경우를 발견하면 경고한다.

---

## 운영

**설정은 `keys.local.bat` 한 곳에 있다.** 고친 뒤 작업을 다시 켠다.

```
schtasks /End /TN PolicyEval
schtasks /Run /TN PolicyEval
```

| 이름 | 무엇 |
|---|---|
| `SOCRATIC_ACCESS_CODE` | 접속 코드. 방문자에게 알려 줄 값 |
| `SOCRATIC_MAX_SESSIONS_PER_DAY` | 하루 세션 상한. 설치가 100 으로 둔다 |
| `ASSEMBLY_KEY` | 국회 의안 인증키 (선택). 열린국회정보에서 발급 |
| `ANTHROPIC_API_KEY` | `experiment` 판일 때만 |

**`keys.local.bat` 에는 키가 들어간다.** 이 폴더를 통째로 남에게 주지 않는다.

**`webapp\sessions.db` 가 연구 자료다.** 문답·채점·선례 판정이 전부 여기
쌓인다. 백업 대상에 넣되, 개인정보가 담길 수 있으므로 배포용 zip 에는 넣지
않는다.

**갱신.** 새 zip 을 풀고 `webapp\sessions.db` 와 `keys.local.bat` 을 남겨 둔
채 나머지를 덮어쓴 뒤, `서버_1_설치.bat` 을 다시 실행하고 작업을 재시작한다.

---

## 잘 안 될 때

| 이런 일이 | 이렇게 |
|---|---|
| 배치를 눌렀는데 창이 순식간에 사라진다 | 파이썬이 없거나 PATH 에 없다 |
| 등록에 실패한다 | 관리자 권한으로 실행하지 않았다 |
| 작업은 실행 중인데 화면이 안 뜬다 | `서버_3_직접실행.bat` 으로 켜면 오류가 화면에 나온다 |
| IIS 가 404 를 낸다 | URL Rewrite / ARR 모듈이 없거나 proxy 를 안 켰다 |
| 502 · 504 | 파이썬 서버가 죽었다. `서버_4_상태확인.bat` |
| 「닿지 못했습니다」 | 방화벽이 `api.anthropic.com` 을 막고 있다 |
| 의안 통로가 의심스럽다 | `.venv\Scripts\python webapp\check_bill.py` |
| Claude 키가 의심스럽다 | `.venv\Scripts\python webapp\check_claude.py` |

`서버_4_상태확인.bat` 은 작업이 등록됐는지만 보지 않고 `127.0.0.1:8000` 에
실제로 물어본다. 작업이 '실행 중'이어도 앱이 죽어 있을 수 있기 때문이다.
