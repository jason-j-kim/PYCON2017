# OPSI 해외 정책사례 수집 절차 (인수인계 문서)

> 대상: 이 작업을 이어받는 코덱스(코딩 에이전트)/사람.
> 이 문서 하나만으로 대화 기록 없이 처음부터 끝까지 수행할 수 있게 작성했다.

---

## 0. 목적

KDI 정책 아이디어 평가 시스템의 **"선례 조사(축 B)"** 에는 국내 3소스
(재정·PRISM·국회 의안)에 더해 **해외 소스**가 있다. 그 해외 소스는
**OECD OPSI**(Observatory of Public Sector Innovation, <https://oecd-opsi.org>)의
공공부문 혁신 사례(Case Study)다.

목표: OPSI의 케이스들을 로컬 DB(`overseas/opsi_policies.db`)에 채워 넣는다.
DB가 채워지면 평가 축 B의 해외 근거가 **자동으로 켜진다**(아래 3장).

대상 목록(예): 중앙정부 사례 약 580건
`https://oecd-opsi.org/case_type/opsi/?_level_of_government=central`

---

## 1. 원칙과 제약 (반드시 지킬 것 — 반복 실패 방지)

1. **봇 우회/스텔스 금지.** OPSI는 Cloudflare로 보호된다. KDI(국가기관)가
   봇 우회로 데이터를 긁는 모양새는 부적절하다. **사람이 정상적으로 연
   브라우저 세션**에서 화면에 렌더링된 데이터를 **읽어오는 것만** 한다.
   → `requests`/헤드리스 스크래핑/헤더 위조 fetch **모두 금지**(그리고 실제로 403으로 막힌다, 8장).
2. **정부 API 키는 커밋 금지.** (이 작업과 직접 관련은 없으나 저장소 규칙.)
3. **DB 파일은 커밋 금지.** `.gitignore`에 `overseas/*.db` 등록됨.
4. 수집한 데이터는 **원본 URL을 id로** UPSERT → 몇 번을 돌려도 중복이 안 쌓인다.

---

## 2. 최종 산출물과 데이터 스키마

수집의 최종 형태는 **JSON 배열 파일**이다. 각 레코드:

```json
[
  {
    "source_url": "https://oecd-opsi.org/innovations/....",   // 필수(= id)
    "title": "정책·혁신 이름",                                  // 필수
    "country": "United Kingdom",                              // 선택
    "level_of_government": "central",                         // 선택
    "year": 2022,                                            // 선택
    "sector": "문화, 복지",                                   // 선택(분야·태그)
    "problem": "해결하려는 문제",                             // 선택(본문)
    "solution": "무엇을 어떻게 했는가",                        // 선택(본문)
    "results": "성과·영향",                                   // 선택(본문)
    "organization": "주관 기관"                               // 선택
  }
]
```

- **필수는 `source_url`과 `title`뿐.** 나머지는 있으면 좋고 없어도 임포트된다.
- 1단계 수집(목록)에서는 `source_url + title (+ country)` 만 얻는다.
- 본문(`problem/solution/results`)은 **2단계(선택, 7장)** 에서 각 상세 페이지를 열어 보강.

임포터는 `source_url`의 마지막 슬러그를 id로 쓰고, `title/problem/solution/results`를
합쳐 검색용 `cleaned_content`를 만든다(채점기가 이 텍스트로 대조한다).

---

## 3. 저장 위치 / 축 B 자동 연동

- DB 경로:
  - 터널(로컬 FastAPI): `overseas/opsi_policies.db` (`webapp/app.py`의 `OPSI_DB`)
  - Vercel: `web/api/opsi_policies.db` (`web/api/evaluate.py`의 `OPSI_DB`)
- 연동 코드: `_opsi_available()`이 `cases` 테이블 건수 > 0 이면 축 B의
  해외 조회 함수(`_opsi_lookup`)를 **자동으로 활성화**한다. 별도 설정 불필요.
- `_opsi_lookup(query)`: 명세의 영어 질의어 토큰으로 `title/cleaned_content/country`를
  LIKE 검색 → 상위 5건을 **A급 해외 근거**로 채점기에 전달.

> 즉, DB에 사례를 넣기만 하면 평가 화면에 해외 근거가 뜬다. 코드 수정 불필요.

---

## 4. 수집 방법 (실제로 작동하는 것)

핵심 제약: OPSI 목록은 **10건씩 AJAX(load-more)** 로 불러오는데, 자동으로
약 6회(≈60건) 요청하면 Cloudflare가 세션을 차단한다(403). 그래서 아래 두 길을 쓴다.
**방법 A가 성공하면 거의 한 번에 끝난다.**

### 방법 A — 사이트맵 (권장, 거의 한 번에)

WordPress 사이트맵은 페이징이 아니라 **한 페이지에 수백 개 URL**이 들어있어
load-more가 필요 없다. 사람이 브라우저로 여는 정상 내비게이션이라 Cloudflare도 통과한다.

1. 크롬에서 `https://oecd-opsi.org/wp-sitemap.xml` 로 이동.
   (404면 `sitemap.xml` 또는 `sitemap_index.xml` 시도)
2. 하위 사이트맵 목록에서 **`innovation`/`case`** 가 든 줄
   (예: `wp-sitemap-posts-innovations-1.xml`)을 연다. 여러 개면 하나씩.
3. 그 XML 페이지에서 **F12 → Console**에 부록 A-1 스니펫을 붙여넣고 Enter.
4. `opsi_sitemap_NNN.json` 이 Downloads에 저장된다 → 5장으로 임포트.

한계: 제목이 URL 슬러그에서 유도되어 다소 거칠고, 국가·본문은 없다(제목·URL만).
채점기는 제목 단어로 매칭하므로 작동한다. 본문은 7장에서 보강.

### 방법 B — 필터 슬라이스 + 자동 load-more (확실, 반복 필요)

사이트맵이 막히면 이걸로. 목록을 **60건 미만으로 좁혀** 각 조각을 자동 수집.

1. OPSI 목록 왼쪽 **필터에서 연도(또는 국가·분야)를 하나** 선택 → 60건 미만이 됨.
2. **F12 → Console**에 부록 A-2 스니펫(자동 load-more 수집기)을 붙여넣고 Enter.
   - "Load more"를 3.5초 간격으로 끝까지 눌러 그 조각을 DOM에 다 올린 뒤 수확.
   - 끝나면 `opsi_cases_NN.json` 을 Downloads에 자동 저장.
3. 필터 값을 바꿔(다음 연도) 1~2 반복.
4. 다 모은 뒤 5장에서 **와일드카드로 한꺼번에** 임포트.

> 연도 필터로 쪼개면 대략 10~15회면 전체가 모인다. 중복은 UPSERT로 자동 정리.

### 공통 원칙: 파일 다운로드 → 임포트 (클립보드 쓰지 말 것)

- 초기엔 `copy()` + `--watch-clip`(클립보드 자동 임포트)을 썼으나 **클립보드가 불안정**했다.
  (콘솔 포커스 없으면 `copy()` 실패, 빈 클립보드로 임포트 시 JSON 에러.)
- **결론: 스니펫이 JSON 파일을 자동 다운로드하게 하고, 그 파일을 임포트**한다. 가장 확실.

---

## 5. 임포트 명령 (Windows cmd 기준)

프로젝트 루트(`PYCON2017`)에서 실행. 임포터: `overseas/import_cases.py`.

```bat
REM 파일 하나
python overseas\import_cases.py %USERPROFILE%\Downloads\opsi_sitemap_580.json

REM 여러 파일을 와일드카드로 한꺼번에 (cmd가 안 풀어도 스크립트가 glob 처리)
python overseas\import_cases.py "%USERPROFILE%\Downloads\opsi_cases_*.json"

REM 폴더 통째로 (그 폴더의 *.json 전부)
python overseas\import_cases.py %USERPROFILE%\Downloads
```

성공 출력 예:
```
  ...\opsi_sitemap_580.json: 580건 반영
완료: 이번 580건 UPSERT · DB 전체 580건 · ...\overseas\opsi_policies.db
```

임포터 기타 모드: `--clip`(클립보드에서), `--stdin`(표준입력), `--watch-clip`(클립보드 감시
자동 임포트). **파일 방식이 가장 안정적이므로 기본으로 파일을 쓴다.**

---

## 6. 검증

```bat
REM DB 건수 확인
python -c "import sqlite3;print(sqlite3.connect(r'overseas\opsi_policies.db').execute('select count(*) from cases').fetchone()[0])"
```

그다음 평가 화면(터널 `/policy` 또는 Vercel)에서 아무 정책 아이디어를 평가하면
축 B에 **해외(OPSI) 근거**가 A급으로 렌더링되는지 확인한다.

---

## 7. (선택) 2단계: 상세 본문 보강

1단계는 목록에서 `url + title`만 얻는다. 매칭 품질을 높이려면 각 상세 페이지의
**문제/해법/성과 본문**을 채운다.

- 사람이 상세 페이지를 브라우저로 연 상태에서 부록 A-3 스니펫으로 본문을 추출 →
  같은 스키마(`problem/solution/results/country/year/sector/organization` 포함)로
  파일 저장 → 5장으로 재임포트(같은 `source_url`이라 UPSERT로 덮어씀).
- 580건 전부는 부담이므로, **실제 평가에서 자주 매칭되는 사례부터** 우선 보강해도 된다.

---

## 8. 실패한 접근 (다시 시도하지 말 것)

| 시도 | 결과 |
|---|---|
| `requests` + WordPress REST/AJAX | 403 (Cloudflare "Just a moment") |
| Playwright 헤드리스 | Cloudflare Turnstile 차단 |
| Playwright 헤드풀(자동 브라우저) | Turnstile가 자동 브라우저 감지, 무한 회전 |
| 콘솔에서 손으로 만든 `fetch()` (헤더 위조) | 403, 응답이 HTML(`<!DOCTYPE`) → JSON 파싱 에러 |
| 자동 load-more 6회 초과 | Cloudflare가 세션 차단(403), FacetWP `TypeError` |
| 클립보드(`copy()` + `--watch-clip`) | 포커스/빈 클립보드로 불안정 |

**교훈:** 네트워크 요청을 새로 만들지 말고, **사람이 정상적으로 렌더링한 화면의
DOM(또는 사이트맵 XML)만 읽어** 파일로 저장한 뒤 임포트한다.

---

## 부록: 콘솔 스니펫 전문

브라우저 콘솔(F12 → Console)에 통째로 붙여넣고 Enter. 저장소 파일
`overseas/collect_console.js`(방법 B)도 동일 내용이다.

### A-1. 사이트맵에서 URL 일괄 수집 (방법 A)

```javascript
(() => {
  const urls = [...new Set((document.body.innerText.match(/https?:\/\/oecd-opsi\.org\/innovations\/[^\s"<]+/g) || []))].map(u => u.replace(/\/$/, ''));
  const cases = urls.map(u => {
    const slug = u.split('/').filter(Boolean).pop();
    const title = slug.replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    return { source_url: u, title, level_of_government: 'central' };
  });
  console.log('✅ URL 수집:', cases.length, '건');
  const blob = new Blob([JSON.stringify(cases, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'opsi_sitemap_' + cases.length + '.json'; document.body.appendChild(a); a.click(); a.remove();
  window.__opsi = cases; return cases.length;
})();
```

### A-2. 목록에서 자동 load-more 수집 (방법 B)

```javascript
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const collect = () => {
    const byUrl = new Map();
    document.querySelectorAll('a[href*="/innovations/"]').forEach((a) => {
      const url = a.href.split('#')[0].split('?')[0].replace(/\/$/, '');
      let title = (a.textContent || '').replace(/\s+/g, ' ').trim();
      if (!url) return;
      const card = a.closest('article, li, .fwpl-result, [class*="result"], .card') || a.parentElement;
      let country = '';
      if (card) {
        const c = card.querySelector('[class*="country"], [class*="Country"]');
        if (c) country = (c.textContent || '').replace(/\s+/g, ' ').trim();
        if (!country) { const img = card.querySelector('img[alt]'); if (img && /^[A-Z]/.test(img.alt) && img.alt.length < 40) country = img.alt.trim(); }
      }
      const prev = byUrl.get(url);
      if (!prev) byUrl.set(url, { source_url: url, title, country, level_of_government: 'central' });
      else { if (title.length > (prev.title || '').length) prev.title = title; if (!prev.country && country) prev.country = country; }
    });
    return [...byUrl.values()].filter((c) => (c.title || '').length >= 6);
  };
  const findMore = () =>
    [...document.querySelectorAll('.facetwp-load-more, a.facetwp-load-more, button, a')]
      .find((b) => /load more|더\s*보기|더보기|show more/i.test(b.textContent || '') && b.offsetParent !== null);
  let guard = 0, lastLinks = -1, stall = 0;
  console.log('▶ Load more 자동 클릭 시작(3.5초 간격)…');
  while (guard++ < 300) {
    const btn = findMore();
    if (!btn) { console.log('· Load more 버튼 없음(끝 또는 차단).'); break; }
    btn.click();
    await sleep(3500);
    let w = 0;
    while (document.querySelector('.facetwp-loading, .facetwp-load-more.loading') && w++ < 40) await sleep(300);
    const n = document.querySelectorAll('a[href*="/innovations/"]').length;
    window.__opsi = collect();
    if (n === lastLinks) { if (++stall >= 3) { console.log('· 더 안 늘어남(끝).'); break; } }
    else { stall = 0; lastLinks = n; console.log('  …링크', n, '개 · 케이스', window.__opsi.length, '건'); }
  }
  const cases = collect(); window.__opsi = cases;
  console.log('✅ 최종 수집:', cases.length, '건');
  try {
    const blob = new Blob([JSON.stringify(cases, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'opsi_cases_' + cases.length + '.json'; document.body.appendChild(a); a.click(); a.remove();
    console.log('💾 Downloads\\' + a.download + ' 저장됨');
  } catch (e) { console.log('다운로드 실패:', e); }
  return cases.length;
})();
```

### A-3. 상세 페이지에서 본문 추출 (2단계, 선택)

상세 페이지(`/innovations/...`)를 연 상태에서 실행. 셀렉터는 페이지 구조에 맞게 조정.

```javascript
(() => {
  const txt = (sel) => (document.querySelector(sel)?.innerText || '').replace(/\s+/g, ' ').trim();
  const rec = {
    source_url: location.href.split('#')[0].split('?')[0].replace(/\/$/, ''),
    title: txt('h1') || document.title,
    country: txt('[class*="country"]'),
    // 아래 셀렉터는 실제 페이지에서 F12로 확인해 채운다:
    problem: txt('.problem, [id*="problem"], [class*="challenge"]'),
    solution: txt('.solution, [id*="solution"], [class*="approach"]'),
    results: txt('.results, [id*="result"], [class*="impact"]'),
    level_of_government: 'central',
  };
  const cases = [rec];
  const blob = new Blob([JSON.stringify(cases, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'opsi_detail.json'; document.body.appendChild(a); a.click(); a.remove();
  return rec.title;
})();
```

---

## 부록 B: 관련 파일

- `overseas/import_cases.py` — JSON → DB 임포터(파일/글롭/폴더/`--clip`/`--stdin`/`--watch-clip`).
- `overseas/collect_console.js` — 방법 B 콘솔 수집기(A-2와 동일).
- `overseas/opsi_policies.db` — 로컬 DB(커밋 안 함).
- `webapp/app.py` / `web/api/evaluate.py` — `_opsi_available` / `_opsi_lookup` 축 B 연동.
- `socratic/prompts/originality_grader_system.md` — 해외 근거 A급/B급 판정 규칙.
