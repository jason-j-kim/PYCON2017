# 정책 실질 독창성 평가 — Vercel 웹페이지

정책 아이디어를 입력하면 **재정(집행)·PRISM(연구)·국회 의안(입법)** 세 자료원과
모델 지식으로 선례를 조사해 **실질 독창성**을 판정하는 단일 페이지 웹앱입니다.
기존 `webapp/`·`socratic/`의 축 B(선례 조사) 로직을 Vercel 서버리스로 이식했습니다.

## 구성

```
web/
├─ index.html          # 화면(정책 입력 + Claude 키 입력 + 결과)
├─ api/
│  ├─ evaluate.py      # 서버리스 함수: 명세→지식판정→3소스 조회→독창성 판정
│  └─ fiscal.json      # 재정(세출예산) 로컬 데이터 — 함수와 함께 번들
├─ vercel.json         # 함수 실행시간(maxDuration) 설정
└─ README.md
```

## 키 설계 (두 종류)

| 키 | 무엇 | 어디에 넣나 |
|---|---|---|
| **Claude API 키** | 판정 3단계(명세·지식·독창성) 호출 | **방문자가 화면에 직접 입력**(BYOK). 서버에 저장 안 함. |
| `DATA_GO_KR_KEY` | PRISM(정책연구) 조회 | **Vercel 환경변수** |
| `ASSEMBLY_KEY` | 국회 의안(ALLBILLV2) 조회 | **Vercel 환경변수** |

- Claude 키는 브라우저에서 Anthropic API로 직접 전송됩니다(Vercel 서버에 남지 않음).
- 정부 키가 없으면 그 소스만 건너뛰고 나머지로 판정합니다(재정은 키가 필요 없음).

## 배포 (Vercel)

1. [vercel.com](https://vercel.com)에 로그인 → **New Project**.
2. 이 저장소를 import하고 **Root Directory**를 `web` 으로 지정합니다.
   (또는 로컬에서 `web/` 폴더에 들어가 `vercel` CLI로 배포)
3. **Settings → Environment Variables**에 정부 키를 넣습니다(선택):
   - `DATA_GO_KR_KEY` = 공공데이터포털 인증키 (PRISM)
   - `ASSEMBLY_KEY` = 열린국회정보 인증키 (국회 의안)
   - 인코딩/디코딩 키 아무거나 넣어도 코드가 정규화합니다.
4. **Deploy**. 나온 주소로 접속해 정책을 입력하고 Claude 키를 붙여 넣으면 됩니다.

CLI 배포:

```
cd web
vercel                       # 미리보기 배포
vercel env add DATA_GO_KR_KEY
vercel env add ASSEMBLY_KEY
vercel --prod                # 운영 배포
```

## 조정 가능한 환경변수(선택)

- `CLAUDE_MODEL` (기본 `claude-opus-5`) — 판정에 쓰는 모델.
- `PRISM_START` / `PRISM_END` — PRISM 조회 날짜 범위(기본 2018~2026).
- `ERACO_TERMS` (기본 `제22대,제21대`) — 국회 의안 조회 대수.

## 알려진 한계

- **PRISM은 키워드 검색 파라미터가 없어** 날짜 범위로 받아 제목에서 주제어를
  로컬 필터링합니다(최근 창 밖 연구는 놓칠 수 있음).
- **국회 의안 제안이유 본문**은 신형 의안정보시스템(likms)이 SPA라 대개 빈 값이
  됩니다. 코드는 남겨두었고, 실제 요청 파라미터를 확정하면 본문까지 살릴 수 있습니다.
- Vercel 무료 플랜은 함수 실행시간이 제한되므로(기본 최대 60초) PRISM이 매우 느린
  날에는 그 소스만 비어 반환될 수 있습니다.
