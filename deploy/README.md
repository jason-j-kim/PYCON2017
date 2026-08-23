# 연구소 서버에 올리기

터널(개인 PC)·Vercel·Workers에 이은 네 번째 형태다. **고정 주소를 갖고 밖에
공개하되, 코퍼스와 판정기는 우리 서버에서 돈다.**

---

## 어느 판으로 할 것인가 — 밖에 열면 답은 하나다

판을 가르는 것은 `mode.txt` 한 줄이고, 갈리는 것은 **누가 Claude 요금을
내는가**다.

| | `experiment` | `personal` |
|---|---|---|
| 방문자가 넣는 것 | 초대 코드만 | 초대 코드 + 자기 API 키 |
| 요금 | 기관 키 하나에 전부 | 방문자 각자 |
| 화면 | 키 칸이 안 보임 | 「Claude 연결」 칸이 보임 |

**밖에 공개한다면 `personal` 이다.** 초대 코드는 참여자 전원이 아는 값이라
반드시 샌다. 메일 한 번 전달되면 끝이다. `experiment` 로 열어 두면 코드가
새는 순간 남의 실험이 기관 카드로 결제된다. 아이디어 1건에 300~600원이므로
하룻밤이면 감당하기 어려운 금액이 된다.

`experiment` 가 맞는 경우는 **초대한 사람만 들어오는 닫힌 실험**이다. 그때도
콘솔에서 그 키에 월 사용 한도를 걸어야 한다.

`personal` 로 열면 방문자의 키는 그 브라우저와 서버 메모리에만 있고
`sessions.db` 나 로그에는 남지 않는다. 이것이 성립하려면 **HTTPS 가
필수다** — 아래 ②를 건너뛰면 안 되는 이유가 이것이다.

---

## 리눅스

```bash
unzip 정책아이디어평가_서버용_*.zip
cd 정책아이디어평가
sudo bash deploy/setup_server.sh
```

전용 계정 · 가상환경 · `mode.txt` · `/etc/policy-eval.env`(600) · systemd
까지 한다. 접속 코드는 무작위로 만들어 화면에 찍어 준다. 여러 번 돌려도
안전하다 — 이미 있는 것은 건너뛰고, `sessions.db` 는 덮어쓰지 않는다.

`experiment` 로 하려면 `MODE=experiment sudo -E bash ... setup_server.sh`.

그다음 손으로 할 것이 둘이다.

**① nginx**

배포하는 `nginx.conf` 에는 **443 블록이 없다.** 인증서가 아직 없는데
`listen 443 ssl` 을 써 두면 nginx 가 뜨지 않고, 그러면 certbot 도 돌릴 수
없다. 80 만 두고 시작해서 certbot 이 제자리에서 443·인증서·평문 이동을
붙이게 한다.

```bash
sudo cp /opt/policy-eval/deploy/nginx.conf /etc/nginx/sites-available/policy-eval
# 파일 안의 server_name 을 실제 도메인으로 바꾼다
sudo ln -s /etc/nginx/sites-available/policy-eval /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**② HTTPS — 선택이 아니다**

```bash
sudo certbot --nginx -d policy.example.ac.kr
```

방문자가 화면에 자기 API 키를 붙여넣는다. 평문으로 받으면 그 키가 도중에
드러난다. 인증서 없이 열지 않는다.

---

## 윈도우 서버

파이썬 코드와 환경변수는 리눅스와 같다. 다른 것은 **서비스로 등록하는 방법**
하나뿐이다.

```bat
git clone <저장소> C:\policy-eval
cd C:\policy-eval
python -m venv .venv
.venv\Scripts\pip install -r webapp\requirements.txt
echo personal> mode.txt
```

서비스 등록은 [NSSM](https://nssm.cc) 이 가장 간단하다.

```bat
nssm install PolicyEval C:\policy-eval\.venv\Scripts\uvicorn.exe
nssm set PolicyEval AppParameters "webapp.app:app --host 127.0.0.1 --port 8000"
nssm set PolicyEval AppDirectory C:\policy-eval
nssm set PolicyEval AppEnvironmentExtra SOCRATIC_ACCESS_CODE=... ^
        SOCRATIC_MAX_SESSIONS_PER_DAY=100
nssm start PolicyEval
```

앞단은 IIS 의 **애플리케이션 요청 라우팅(ARR)** 으로 `127.0.0.1:8000` 에
역방향 프록시를 걸고, 인증서는 IIS 관리자에서 붙인다. `nginx.conf` 에 적어
둔 것 — `/records` 와 `/api/records` 차단 · 5분 타임아웃 · HTTPS 강제 —
을 IIS 규칙으로 똑같이 옮기면 된다.

---

## 기록 화면은 밖에서 열리지 않는다

`/records` 는 **서버가 도는 그 기계에서 연 것만** 통과한다. 프록시가 붙인
머리표(`X-Forwarded-For` 등)가 하나라도 있으면 403 이다. nginx 쪽에서도
404 로 한 번 더 막는다.

일부러 그렇게 두었다. `sessions.db` 에는 여러 사람의 문답이 함께 쌓이므로,
접속한 사람이 남의 대화를 받아 갈 수 있으면 안 된다. 초대 코드로 막는
것으로는 부족하다.

운영자는 SSH 터널로 본다.

```bash
ssh -L 8000:127.0.0.1:8000 사용자@서버
# 브라우저에서 http://localhost:8000/records
```

윈도우 서버라면 원격 데스크톱으로 들어가 그 기계의 브라우저에서 연다.

`--proxy-headers` 를 uvicorn 에 붙이면 이 잠금장치가 무력해진다. 그 옵션은
`X-Forwarded-For` 를 `client.host` 로 바꿔치기하는데, 잠금장치가 보는 것이
바로 그 값이다. systemd 유닛에 붙이지 않은 이유다.

---

## 켠 뒤에 확인할 것

```bash
systemctl status policy-eval          # 떠 있나
journalctl -u policy-eval -f          # 무슨 일이 있나
curl -s localhost:8000/api/config     # 서버가 답하나
curl -sI https://policy.example.ac.kr/records   # 404 여야 한다
```

`/api/config` 가 돌려주는 것 중 `mode` 가 정한 값인지, `access_required` 가
`true` 인지 보면 된다.

---

## 운영에서 챙길 것

**하루 세션 상한.** 기본 30건이다. 설치 스크립트가 100 으로 올려 두지만,
밖에 열어 두는 동안의 안전판이므로 필요 이상으로 올리지 않는 편이 낫다.
`/etc/policy-eval.env` 의 `SOCRATIC_MAX_SESSIONS_PER_DAY`.

**인증이 초대 코드 하나뿐이다.** 참여자 전원이 아는 값이다. 소속 연구원만
쓰게 하려면 nginx 쪽에 기본 인증이나 기관 SSO 를 한 겹 더 얹어야 한다.

**`webapp/sessions.db` 가 연구 자료다.** 문답·채점·선례 판정이 전부 여기
쌓인다. 개인정보가 담길 수 있으므로 백업 대상에 넣되 배포용 zip 에는 넣지
않는다.

**바깥으로 나가는 통신 두 곳.** `api.anthropic.com`(필수)과
`open.assembly.go.kr`(의안 통로를 쓸 때만). 폐쇄망이면 방화벽에서 이 둘을
열어야 한다.

**갱신.** 새 zip 을 풀고 설치할 때와 같은 스크립트를 다시 돌린다. 이미
쌓인 문답(`webapp/sessions.db`)과 설정(`/etc/policy-eval.env`)은 건드리지
않고 코드만 바꿔 놓는다.

```bash
unzip 새로받은.zip && cd 정책아이디어평가
sudo bash deploy/setup_server.sh
sudo systemctl restart policy-eval
```
