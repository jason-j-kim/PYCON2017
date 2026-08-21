# Cloudflare Workers 배포판

터널·Vercel에 이은 **세 번째 배포 형태**다. 고정 주소(`*.workers.dev` 또는 사용자
도메인)를 갖고, 서버를 켜 둘 필요가 없다.

---

## 무엇이 같고 무엇이 다른가

**같은 것** — 프런트엔드(`web/`)를 그대로 쓴다. 12문답·이원 채점·괴리 임계 규칙은
브라우저에서 돌므로 Vercel판과 완전히 동일하다. 축 B의 세 프롬프트(명세 추출·지식
판정·독창성 판정)는 `web/api/evaluate.py`에서 **자동 추출**해 쓰므로 문언이 어긋나지
않는다.

**다른 것** — 두 가지다.

| | Vercel판 | Workers판 |
|---|---|---|
| 코퍼스 | `web/api/`에 SQLite 파일 번들 | **D1**(서버리스 SQLite) |
| KDI 통로 | kdinov 2차원 판정(N0~N4 × 실행/경합/근거/선례) | **키워드 조회만** |
| Word·PDF 불러오기 | 지원 | 미지원(.txt/.json만) |

### KDI 통로의 제약 — 반드시 알고 쓸 것

kdinov는 Python 패키지이고 한국어 형태 처리를 포함하므로 Workers(JS 런타임)에서
동작하지 않는다. 따라서 Workers판의 KDI 통로는 **Vercel/터널판이 kdinov 부재 시
쓰는 폴백과 같은 수준**이다 — 제목·키워드·본문 가중 검색은 하지만 **중첩도와 역할
판정은 나오지 않는다.**

정밀 판정이 필요한 연구용은 터널판을, 넓은 접근성이 필요한 공개용은 Workers판을
쓰는 식으로 나누는 것이 맞다.

---

## 배포 절차

### 0. 준비

```bash
npm install -g wrangler
wrangler login
```

### 1. D1 생성

```bash
cd worker
wrangler d1 create policy-corpus
```

출력된 `database_id`를 `wrangler.toml`의 해당 자리에 붙여넣는다.

### 2. 코퍼스 → D1 적재용 SQL 생성

프로젝트 루트에서 실행한다. 로컬 코퍼스를 읽어 `worker/d1/*.sql`을 만든다.

```bash
python worker/build_d1.py
```

읽는 원본:

| 통로 | 원본 | 건수 |
|---|---|---|
| 재정 | `web/api/fiscal.json` | 14,122 |
| 정책연구 | `kdi/kdi.sqlite` (없으면 `web/api/kdi.sqlite`) | 7,362 |
| 해외 | `overseas/opsi_policies.db` (없으면 `web/api/`) | 1,015 |

### 3. 적재

```bash
wrangler d1 execute policy-corpus --remote --file=worker/d1/schema.sql
wrangler d1 execute policy-corpus --remote --file=worker/d1/fiscal.sql
wrangler d1 execute policy-corpus --remote --file=worker/d1/kdi.sql
wrangler d1 execute policy-corpus --remote --file=worker/d1/opsi.sql
```

용량이 커 몇 분 걸린다. 확인:

```bash
wrangler d1 execute policy-corpus --remote \
  --command="SELECT (SELECT COUNT(*) FROM fiscal) f, (SELECT COUNT(*) FROM kdi) k, (SELECT COUNT(*) FROM opsi) o"
```

### 4. 국회 의안 키 등록 (선택)

```bash
wrangler secret put ASSEMBLY_KEY
```

등록하지 않으면 ③ 국회 의안 통로만 꺼지고 나머지 세 통로는 정상 동작한다.

### 5. 배포

```bash
cd worker
wrangler deploy
```

`https://policy-eval.<계정>.workers.dev` 로 열린다. **주소가 고정**이라 터널처럼
매번 바뀌지 않는다.

---

## 프롬프트 동기화

축 B 프롬프트를 고쳤다면 재생성한다.

```bash
python worker/build_prompts.py     # web/api/evaluate.py → worker/src/prompts.js
```

`worker/src/prompts.js`는 자동 생성 파일이므로 직접 고치지 않는다.

---

## 사용자 인증

Vercel판과 같은 **BYOK** 방식이다. 이용자가 자기 Claude API 키를 브라우저에 넣고,
Worker는 그것을 Anthropic으로 넘기기만 한다(저장하지 않는다).

기관이 단일 계정으로 운영하려면 이 구조를 바꿔야 한다 — `wrangler secret put
ANTHROPIC_API_KEY`로 키를 서버에 두고, `handleClaudeProxy`와 `originalityAxis`가
요청 본문 대신 `env.ANTHROPIC_API_KEY`를 쓰게 하면 된다. 이 경우 **접근 통제를
반드시 함께 붙여야 한다**(초대 코드 또는 Cloudflare Access).

---

## 알려진 위험 — 배포 전 확인

이 배포판은 **실제 Cloudflare에 올려 검증하지 않았다.** 코드는 로컬에서 D1 API를
흉내 낸 어댑터로 조회 결과가 Python판과 일치함을 확인했으나, 아래 항목은 실배포에서
확인해야 한다.

### 1. D1 무료 한도 — 하루 20건 남짓

조회는 `LIKE '%…%'` 이므로 인덱스를 못 쓰고 전수 훑기가 된다. 아이디어 1건 평가에
소스별 최대 3질의 × 4소스 = 12회 조회가 돌고, 각 조회가 테이블을 훑는다.

| | 1회 평가당 읽는 행 | 무료 한도(5백만/일) | 유료($5/월, 250억/일) |
|---|---|---|---|
| 대략 | 약 27만 행 | **하루 18건 내외** | 사실상 제한 없음 |

**공개 서비스로 쓰려면 D1 유료 요금제가 사실상 필수다.** 시험용이라면 무료로도
충분하다. 개선하려면 FTS5 가상 테이블을 만들어 전수 훑기를 없애면 된다.

### 2. 응답 시간

축 B는 Claude를 순차로 3회 호출한다(명세 추출 → 지식 판정 → 독창성 판정). 모델과
대화 길이에 따라 **2~3분**이 걸릴 수 있다.

Vercel판은 `maxDuration = 300`으로 명시하지만 Workers에는 대응 설정이 없다. Worker
자체의 CPU 시간은 문제가 아니지만(대기는 CPU를 쓰지 않는다), 브라우저 쪽에서 연결이
끊길 수 있다. **장문 대화에서 이 경로를 반드시 시험할 것.**

### 3. 정적 자산 제외 설정

`web/.assetsignore` 가 `api/` 를 제외한다. **이 파일이 없으면 배포가 실패한다** —
`web/api/kdi.sqlite`(26MB)가 Workers Assets 파일당 한도(25MiB)를 넘기고, 서버 소스가
공개 URL로 노출된다. 제외 후 업로드 용량은 43MB → 72KB.

### 4. 배포 전 필수 입력

`wrangler.toml` 의 `database_id` 가 플레이스홀더다. `wrangler d1 create` 출력값으로
바꾸지 않으면 배포되지 않는다.

---

## 세 배포 비교

| | 터널 | Vercel | Workers |
|---|---|---|---|
| 주소 | 실행할 때마다 변경 | 고정 | **고정** |
| 서버 상시 가동 | 필요 | 불필요 | 불필요 |
| Claude 호출 | Claude Code CLI(Pro 로그인) | API 키(BYOK) | API 키(BYOK) |
| 코퍼스 | 로컬 파일 | 번들 파일 | **D1** |
| kdinov 2차원 판정 | ✅ | ✅ | ❌ |
| Word·PDF 불러오기 | ✅ | ✅ | ❌ |
| 세션 저장 | 서버 SQLite | localStorage | localStorage |

---

## 주소만 고정하고 싶다면

Workers 이식 없이 **터널 주소만 고정**하는 방법이 따로 있다. Cloudflare에 도메인이
있다면 **Named Tunnel**을 쓰면 된다.

```bash
cloudflared tunnel login
cloudflared tunnel create policy
cloudflared tunnel route dns policy policy.example.com
cloudflared tunnel run --url http://localhost:8000 policy
```

이 방식은 **kdinov 정밀 판정과 Word·PDF 지원을 그대로 유지**한다. 이식 작업이
필요 없고 주소만 영구히 고정된다. 목적이 "주소가 자꾸 바뀌는 불편"이라면 이쪽이
훨씬 적은 노력으로 해결된다.
