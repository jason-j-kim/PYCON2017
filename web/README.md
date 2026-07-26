# 소크라테스식 정책 문답 평가 — Vercel 웹페이지 (Claude)

정책 아이디어를 **12개 소크라테스 문답**으로 검증해 독창성·실용성·수용태도를
이원 채점하고, 이어서 **재정(집행)·PRISM(연구)·국회 의안(입법)** 세 자료원과
모델 지식으로 선례를 조사해 **실질 독창성**을 판정하는 단일 페이지 웹앱입니다.
기존 `webapp/`·`socratic/`의 문답·채점·축 B(선례 조사) 로직을 Vercel로 이식했고,
모든 Claude 호출은 **방문자의 Claude API 키(BYOK)** 로 동작합니다.

## 구성

```
web/
├─ index.html          # 문답 UI + 이원 채점 + 5문장 + 선례 조사 결과 (클라이언트)
├─ api/
│  ├─ claude.py        # 프록시: 브라우저의 문답·채점 호출 → Anthropic Messages API
│  ├─ evaluate.py      # 축 B: 명세→지식판정→재정·PRISM·의안 조회→독창성 판정
│  └─ fiscal.json      # 재정(세출예산) 로컬 데이터 — 함수와 함께 번들
├─ vercel.json         # 함수 실행시간(maxDuration) 설정
└─ README.md
```

## 동작 흐름

1. **문답(12문항·5단계)** — `index.html`이 질문자 프롬프트로 Claude를 호출(`/api/claude`
   프록시 경유). 대화는 브라우저에 유지됩니다(서버 무상태).
2. **이원 채점** — 규정 심사위원(체크리스트)·종합 심사위원(종합판단)을 각각 호출해
   점수·5문장 결과를 만듭니다.
3. **선례 조사(축 B)** — 채점 뒤 전체 대화 로그를 `/api/evaluate`로 보내
   명세 추출 → 지식 판정 → **재정·PRISM·국회 의안 조회** → 독창성 판정을 실행합니다.

## 키 설계

| 키 | 무엇 | 어디에 넣나 |
|---|---|---|
| **Claude API 키** | 문답·채점·독창성 판정 모든 호출 | **방문자가 화면에 직접 입력**(BYOK). 서버에 저장 안 함. |
| `DATA_GO_KR_KEY` | PRISM(정책연구) 조회 | **Vercel 환경변수 (미리 설정)** |
| `ASSEMBLY_KEY` | 국회 의안(ALLBILLV2) 조회 | **Vercel 환경변수 (미리 설정)** |

- Claude 키는 브라우저에서 프록시를 거쳐 Anthropic으로 전달될 뿐 Vercel에 남지 않습니다.
- 정부 키는 **서버에 미리 설정**해 둡니다(방문자는 몰라도 됨). 없으면 그 소스만
  건너뛰고 나머지로 판정합니다(재정은 키가 필요 없음).

## 배포 (Vercel)

1. [vercel.com](https://vercel.com) → **New Project** → 이 저장소 import.
2. **Root Directory**를 `web` 으로 지정.
3. **Settings → Environment Variables**에 정부 키를 미리 넣습니다:
   - `DATA_GO_KR_KEY` = 공공데이터포털 인증키 (PRISM) — 인코딩/디코딩 키 아무거나.
   - `ASSEMBLY_KEY` = 열린국회정보 인증키 (국회 의안).
4. **Deploy** → 나온 주소에 접속. 방문자는 Claude 키만 붙여 넣고 문답을 시작하면 됩니다.

CLI 배포:

```
cd web
vercel env add DATA_GO_KR_KEY
vercel env add ASSEMBLY_KEY
vercel --prod
```

## 조정 가능한 환경변수(선택)

- `CLAUDE_MODEL` (기본 `claude-opus-5`) — 문답·채점·판정에 쓰는 모델.
- `PRISM_START` / `PRISM_END` — PRISM 조회 날짜 범위(기본 2018~2026).
- `ERACO_TERMS` (기본 `제22대,제21대`) — 국회 의안 조회 대수.

## 알려진 한계

- **PRISM은 키워드 검색 파라미터가 없어** 날짜 범위로 받아 제목에서 주제어를
  로컬 필터링합니다(최근 창 밖 연구는 놓칠 수 있음).
- **국회 의안 제안이유 본문**은 신형 의안정보시스템(likms)이 SPA라 대개 빈 값이
  됩니다. 코드는 남겨두었고, 실제 요청 파라미터를 확정하면 본문까지 살릴 수 있습니다.
- Vercel 무료 플랜은 함수 실행시간이 제한됩니다(기본 최대 60초). 문답 한 턴,
  채점 한 번, 선례 조사 한 번이 각각 별도 요청이라 대개 그 안에 끝나지만, PRISM이
  매우 느린 날에는 그 소스만 비어 반환될 수 있습니다.
