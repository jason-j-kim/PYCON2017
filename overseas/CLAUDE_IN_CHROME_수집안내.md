# Claude in Chrome 로 OPSI 사례 수집 → 로컬 DB 넣기

자동 스크래핑은 Cloudflare가 막지만, **Claude in Chrome(크롬 확장)은 교수님의 실제
브라우저 세션**(이미 통과한 사람 세션)에서 동작하므로 정당하게 사례를 열어 데이터를
추출할 수 있다. 추출 결과(JSON)를 `import_cases.py`로 로컬 DB에 넣는다.

## 순서
1. 크롬에서 대상 목록을 연다. 예(중앙정부 필터):
   `https://oecd-opsi.org/case_type/opsi/?_level_of_government=central`
2. **Claude in Chrome**에 아래 "추출 지시문"을 붙여 실행 → JSON을 받는다.
3. 받은 JSON을 `cases.json` 으로 저장한다.
4. 로컬에서 임포트:
   ```
   python overseas/import_cases.py cases.json
   ```
   → `overseas/opsi_policies.db` 에 UPSERT(중복 자동 방지, 다시 돌려도 안전).

## Claude in Chrome 추출 지시문 (그대로 붙여넣기)

> 이 페이지는 OECD OPSI의 정책 사례 목록입니다. 목록의 각 사례 링크를 하나씩 열어
> 아래 항목을 추출하고, 원래 목록으로 돌아와 다음 사례로 진행하세요. 모든 사례를
> 마치면(다음 페이지가 있으면 페이지네이션을 따라가며) 결과를 **하나의 JSON 배열**로만
> 출력하세요. 설명·머리말 없이 JSON만.
>
> 각 사례 객체 필드:
> - `source_url`: 사례 상세 페이지 URL
> - `title`: 사례 제목
> - `country`: 시행 국가
> - `level_of_government`: 정부 수준(central/local 등)
> - `year`: 도입/시작 연도(숫자)
> - `sector`: 분야·주제·태그(쉼표로 구분)
> - `problem`: 해결하려는 문제(2~3문장)
> - `solution`: 무엇을 어떻게 했는가 — 핵심 설계(4~6문장)
> - `results`: 성과·영향(있으면)
> - `organization`: 주관 기관
>
> 값을 못 찾은 필드는 빈 문자열("")로 두세요. 본문(problem/solution)은 요약하되
> **설계 내용(대상·수단·전달방식)** 이 드러나게 적으세요.
>
> 출력 예:
> ```json
> [
>   {"source_url":"https://oecd-opsi.org/innovations/...","title":"...","country":"...",
>    "level_of_government":"central","year":2022,"sector":"...","problem":"...",
>    "solution":"...","results":"...","organization":"..."}
> ]
> ```

## 팁 (실무)
- **한 번에 너무 많이 시키지 말 것** — 목록 한 페이지(또는 10~20건)씩 나눠 추출하고,
  파일도 `cases1.json`, `cases2.json`… 로 나눠 저장한 뒤 한꺼번에 임포트:
  `python overseas/import_cases.py cases1.json cases2.json`
- **정확도 확인** — 추출한 JSON에서 country·year·solution 몇 건을 원본과 대조.
- **서버 존중** — 빠르게 연속 열지 말고 사람 속도로. (Claude in Chrome이 사람 세션이라도 예의)
- **중복 걱정 없음** — `source_url` 기준 UPSERT라, 같은 사례를 다시 넣어도 갱신만 된다.

## 이 데이터가 붙는 곳
`import_cases.py` 가 넣는 `cases` 테이블(제목·국가·수준·연도·분야·본문·성과·기관·URL)은
이후 `_opsi_lookup(query)` 로 검색되어, 선례 조사(축 B)의 **해외 축**으로 연결된다.
그러면 grader가 해외 사례를 **국가·본문까지 인용하는 A급 근거**로 쓸 수 있다.
