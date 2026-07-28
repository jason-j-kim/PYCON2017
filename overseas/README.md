# 해외 정책사례 수집 (OECD OPSI · Apolitical)

Overton 같은 유료·외국 상업 DB에 의존하지 않고, **공개 정책사례를 직접 수집해 로컬
SQLite로 소유**하기 위한 파이프라인이다. 수집한 DB는 `재정(fiscal.json)`처럼 **무료·
주권적 로컬 소스**로 선례 조사(축 B)의 "해외 축"에 붙일 수 있다.

```
overseas/
├─ opsi_scraper.py        # OECD OPSI 사례 수집(작동 · WordPress REST 기반)
├─ apolitical_scraper.py  # Apolitical 사례 수집(스캐폴드 · 구조 확정 필요)
├─ requirements.txt       # requests, beautifulsoup4
└─ README.md
```

수집 결과 스키마(두 소스 공통, 테이블 `cases`):
`id · title · country · sector · year · raw_content · cleaned_content · source_url · scraped_at`

## 준비
```
pip install -r overseas/requirements.txt
```

## 1) OECD OPSI 수집 (지금 사용 가능)

OPSI 사이트는 WordPress이므로 REST API로 사례를 페이지 단위로 받는다.

```
# ① 먼저 구조 탐지 — 실제 사례 CPT 이름과 국가·분야 분류 slug 확인
python overseas/opsi_scraper.py --discover

# ② 확인한 값으로 시험 수집(앞 3페이지만)
python overseas/opsi_scraper.py --post-type case_study --tax-country country --max-pages 3

# ③ 전체 수집
python overseas/opsi_scraper.py --post-type case_study
```

- 결과: `overseas/opsi_policies.db` (테이블 `cases`), `id` 기준 UPSERT(중복 방지·주기 갱신).
- 안정성: 요청 간 지연(1.2~3초 난수), 429·5xx·연결오류 지수 백오프 재시도, 진행 로깅.
- `--discover` 결과에서 사례 CPT의 `rest_base`(예: `case_study`)와 국가/분야 분류 slug을
  확인해 인자(또는 `opsi_scraper.py` 상단 `CONFIG`)로 맞춘다. 확정 전에는 country·sector·
  year 일부가 비어 있을 수 있다.

### ⚠ Cloudflare 봇차단 → Playwright 판을 쓴다
OPSI 사이트(oecd-opsi.org)는 **Cloudflare 봇보호("Just a moment…")** 뒤에 있어 `requests`
판(`opsi_scraper.py`)은 **HTTP 403**으로 막힌다(확인됨: `Server=cloudflare`). 이때는
**진짜 브라우저로 통과**하는 Playwright 판을 쓴다.

```
pip install playwright
playwright install chromium

python overseas/opsi_scraper_playwright.py --discover
python overseas/opsi_scraper_playwright.py --post-type case_study --max-pages 3
python overseas/opsi_scraper_playwright.py --post-type case_study            # 전체
python overseas/opsi_scraper_playwright.py --post-type case_study --headful  # 차단 심하면 창 띄워서
```

- 헤드리스 Chromium으로 홈페이지를 먼저 열어 Cloudflare 통과(clearance 쿠키 획득) 후,
  같은 컨텍스트로 REST API를 페이지 단위 호출한다. 파싱·DB는 `opsi_scraper.py` 재사용(같은 DB).
- 헤드리스가 계속 막히면 `--headful`(창 표시)이 통과율이 높다.
- 이는 사람이 브라우저로 여는 것과 같은 접근이나 **Cloudflare 보호를 지나므로 ToS를 확인**하고
  요청 간격을 지킨다. 기관(KDI)이라면 **OECD OPSI에 데이터 제공을 공식 문의**하는 편이 가장 안전·정당하다.

### ⚠⚠ OPSI는 자동 브라우저도 탐지·차단 → 수동-통과 모드를 쓴다
확인 결과, requests뿐 아니라 **자동화된 Playwright(headful)도 Cloudflare가 탐지·차단**했다.
봇 우회(stealth)로 더 밀어붙이는 대신, **사람이 직접 Cloudflare를 통과한 세션을 재사용**하는
정당한 방식(`opsi_scraper_manual.py`)을 쓴다.

```
pip install playwright
python -m playwright install chromium     # Chrome 채널 실패 시 대비

python overseas/opsi_scraper_manual.py --discover
python overseas/opsi_scraper_manual.py --post-type case_study --max-pages 3
python overseas/opsi_scraper_manual.py --post-type case_study            # 전체
```

동작: 실제 브라우저 창이 뜨면 **사용자가 Cloudflare 확인을 직접 통과**하고, 콘솔에서 Enter를
누르면 그 인증 세션으로 페이지를 이동하며 REST를 수집한다. 통과 세션은 `overseas/.pw-profile`에
저장되어 **다음 실행부터는 대개 통과가 유지**된다. 설치된 Chrome이 있으면 그것을 우선 사용한다.

> 가장 깨끗한 길은 여전히 **opsi@oecd.org 공식 데이터 요청**이다. 수동-통과 모드는 그 사이의
> 실무적 수단이며, 무료 대안(지식 판정 프롬프트의 해외 B급 반영)이 이미 ~90%를 처리한다.

## 2) Apolitical 수집 (스캐폴드 — 확정 필요)

OPSI와 달리 공개 REST가 불명확하고 콘텐츠 일부가 로그인·JS 렌더 뒤에 있을 수 있다.
그래서 **먼저 두 가지를 확인**한 뒤 진행한다.

```
# robots.txt 상 크롤링 허용 여부 확인(이용약관도 별도로 확인할 것)
python overseas/apolitical_scraper.py --check
```

- robots·ToS가 허용하고 구조가 정적이면 → `apolitical_scraper.py`의 `CONFIG['listing_url']`과
  `selectors`(카드·링크·제목·본문)를 실제 페이지 구조로 채운 뒤 `--max-pages 2`로 시험.
- **JS로만 렌더되면** requests+bs4로는 부족 → **Playwright(headless)** 로 전환한다
  (이 환경엔 Chromium이 설치돼 있어 전환이 어렵지 않다).
- 결과: `overseas/apolitical_cases.db`.

## 법적·윤리 유의
- 수집 대상의 **robots.txt와 이용약관(ToS)** 을 반드시 확인한다. 특히 Apolitical은
  상업 플랫폼이므로 대량 수집 전 **공식 API·데이터 제휴** 가능 여부를 먼저 문의하는 편이 안전하다.
- 서버를 존중한다 — 요청 간 지연·재시도는 이미 코드에 넣었다. 과도한 병렬·고빈도 금지.
- 수집 데이터는 **연구 목적**으로 다루고, 저작권·출처(`source_url`)를 보존한다.

## 로드맵 (이후)
1. **로컬 조회 함수** — `_opsi_lookup(query)`, `_apolitical_lookup(query)`를 만들어
   `cleaned_content`·`title`·`country`를 키워드로 검색(재정 `_fiscal_local_search`와 동형).
2. **선례 조사에 '해외 축' 추가** — `engine.originality_axis`/`web/api/evaluate.py`에
   4번째 소스로 연결(국가 태그 포함). grader는 해외를 A급(조회 확인)으로 인용 가능.
3. **웹서비스** — 정책 주제 입력 → OPSI·Apolitical 로컬 DB 검색 → 국가·분야·연도별
   해외 사례 목록 반환(기존 웹 UI에 카드로 표시).
