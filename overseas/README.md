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
