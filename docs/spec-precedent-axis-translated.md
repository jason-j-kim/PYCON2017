# 번역판 SPEC — 선례 조사 축(축 B)을 우리 스택으로

원본 `SPEC.md`는 JS + OpenAI + Vercel을 전제한다. 우리 시스템은 **Python(FastAPI) +
Claude Code CLI(구독)** 다. 이 문서는 원본의 **설계·원칙·순서를 그대로 보존**하고
런타임만 우리 것으로 치환한 것이다. **검토용이며, 아직 구현하지 않는다.**

핵심 결정 두 가지를 먼저 못박는다.

- **모든 LLM 호출은 Claude로 한다.** OpenAI·유료 API 키·`X-OpenAI-API-Key`·브라우저 키
  입력·`/api/openai-responses`·Vercel 서버리스는 **전부 제거**한다. Stage 3·4·6은
  `engine.call_claude()` + `_call_and_parse()`로, 기존 채점자와 동일한 방식으로 돈다.
- **유료 키는 0이다.** 남는 외부 키는 정부 데이터 API 2개(열린재정·PRISM)뿐이며 무료다.
  없으면 §5 폴백대로 `판정 보류`로 내려간다.

---

## A. 아키텍처 치환표 (원본 → 우리)

| 원본 SPEC | 우리 스택 |
|---|---|
| `gradeSession()` / `gradeChecklist()` / `gradeHolistic()` | `engine.grade()` / `_grade_checklist()` / `_grade_holistic()` |
| `askQuestioner()` | `engine.ask_questioner()` (무변경) |
| `STAGES`가 `policy.html` 안 | `engine.STAGES` (서버 파이썬) |
| `weightedTotal/scoreBand/evidenceLevel/fiveLines` | `weighted_total/score_band/evidence_level/five_lines` |
| `openAI()/openAIJson()/extractJson()/parseLoose()` | `call_claude()/_call_and_parse()/_extract_json()` |
| OpenAI (X-OpenAI-API-Key) | **Claude CLI (`claude -p`)** |
| Vercel `api/fiscal.js`·`api/prism.js` | **FastAPI 라우트** `webapp/app.py`의 `/api/fiscal`·`/api/prism` |
| `Promise.all` / `Promise.allSettled` | 파이썬 `asyncio.gather` (또는 스레드풀) |
| 브라우저가 채점 | 서버가 채점, `policy.html`은 얇은 클라이언트 |

`CRITERIA`/`CRITERIA_KO`/`DEFAULT_WEIGHTS`의 JSON 키 `originality`는 원본 §1대로 유지하고
**화면 라벨만** 바꾼다.

---

## B. §6 파일별 작업 — 우리 스택판

| 파일 | 작업 |
|---|---|
| `socratic/engine.py` | ① `STAGES` 독창성 단계 지시문에 한 줄 추가(원본 Stage 1) |
| | ② 신규 함수 4개: `extract_spec()`·`judge_by_knowledge()`·`grade_originality()` (모두 `call_claude` 사용) + 조회 결과를 받는 `originality_axis()` 오케스트레이터 |
| | ③ 축 B 프롬프트 파일 3개: `prompts/spec_extractor_system.md`·`precedent_judge_system.md`·`originality_grader_system.md` |
| `webapp/app.py` | ④ 라우트 `/api/fiscal`·`/api/prism` 신설 (서버가 정부 API 호출, 키는 서버 환경변수) |
| | ⑤ 축 B 파이프라인: **축 A와 분리한 별도 단계**. `POST /api/sessions/{sid}/originality`로 트리거, `GET`으로 상태 폴링 |
| | ⑥ `_evaluation_payload`는 무변경. 축 B는 **별도 payload**로 내려보냄 |
| `webapp/db.py` | ⑦ `originality`(축 B 결과 JSON) 컬럼 추가 — 부가·마이그레이션(프로필 때와 동일 패턴) |
| `webapp/static/policy.html` | ⑧ `renderResult`에 7-1~7-6 카드 추가, 라벨 `독창성`→`독창성 — 방어력`, 축 B 폴링·렌더 |
| `webapp/run_tunnel.bat` | ⑨ 있으면 `set FISCAL_KEY=…`·`set DATA_GO_KR_KEY=…` (없으면 폴백) |

원본의 "새 HTTP 헬퍼 만들지 마라"에 대응 — 정부 API 호출은 표준 라이브러리
`urllib.request`(의존성 0) 또는 이미 있으면 `httpx`로 통일한다. LLM은 `call_claude` 재사용.

---

## C. 절차 — 축 A/축 B 분리 (524 회피가 핵심)

원본은 `Promise.all([gradeSession(), extractSpec()])`로 축 A·B를 한 번에 돌린다. 우리는
**Claude 호출이 느려서**(각 20~60초) 그대로 하면 축 B가 터널 100초 한도를 반드시 넘긴다.
그래서 두 단계로 쪼갠다.

```
/finish  ─▶ 축 A: grade()  (기존, LLM 2회)  ─▶ 결과 즉시 렌더 (방어력)
                                              │
policy.html이 이어서 자동 호출 ──────────────▶ POST /originality
                                              │
      축 B (백그라운드): Stage 3 명세추출(LLM1)
                        Stage 4 지식판정(LLM1, 검색0)
                        Stage 5 조건부 조회(HTTP6, 병렬)
                        Stage 6 최종 독창성(LLM1)
                                              │
      policy.html이 GET /originality 폴링 ────▶ 준비되면 7-1~7-6 렌더
```

이렇게 하면 원본 §5 "축 B 실패해도 축 A는 반드시 표시"가 구조로 보장된다. 폴링은 이미
524 복구용으로 만든 `recover()` 패턴을 재사용한다.

---

## D. 세션당 LLM 호출 예산 (교수님이 "추가 호출 회피" 하셨던 지점)

| 단계 | Claude 호출 |
|---|---|
| 문답(질문자) | 12 (현행) |
| 축 A 채점 | 2 (현행) |
| **축 B 신규** | **+3** (명세·지식판정·최종독창성) |
| 합계 | 17 (기존 14 → +3) |

+3은 **새 축이라 불가피**하다. 대신 축 B를 비동기로 분리했으므로 문답·방어력 체감
속도에는 영향이 없다. 정부 HTTP는 LLM이 아니며 Stage 4가 `has_precedent`면 **0회**다.

---

## E. 남는 키·폴백 (유료 0)

| 키 | 성격 | 없을 때 |
|---|---|---|
| (LLM) | Claude 구독 — **키 없음** | — |
| `FISCAL_KEY` (열린재정) | 무료, 즉시 발급 | Stage 5 건너뜀 |
| `DATA_GO_KR_KEY` (PRISM) | 무료, 승인 필요 | Stage 5 건너뜀 |

정부 키 2개가 다 없어도: Stage 4가 `has_precedent`면 정상 판정, `uncertain`이면 `판정 보류`.
**세션은 유료 키 0으로 끝까지 돈다.**

---

## F. 무변경 보장 (원본 §1 대응)

`grade()`·`_grade_checklist()`·`_grade_holistic()`·`weighted_total()`·`ask_questioner()`·
`CHECKLIST_ITEMS`·프롬프트 파일은 **읽기만** 한다. `STAGES` 독창성 지시문 한 줄만 예외.
검수 시 "같은 로그로 `grade()` 결과가 이전과 동일"을 회귀로 확인한다(원본 §7 체크리스트).

---

## G. 리스크·난이도

- **열린재정 파서** — 원본 경고대로 "문서 필드명 ≠ 실제 응답". `FISCAL_KEY` 발급 후 실응답을
  한 번 받아 맞춰야 한다. 키 없이는 이 부분 개발 불가.
- **Claude JSON 안정성** — CLI에 JSON 모드가 없지만, 기존 채점자가 이미 `_call_and_parse`
  (재시도 + `_extract_json`)로 JSON을 안정적으로 뽑고 있어 동일 패턴이면 문제 없다.
- **비동기 FastAPI** — 정부 HTTP 6회 병렬(`asyncio`)과 축 B 백그라운드 처리를 위해 app.py에
  약간의 비동기화가 필요하다. 표준 라이브러리 범위에서 가능.
- **DB 잠금** — 축 B가 백그라운드로 DB에 쓰므로 SQLite 동시성만 주의(짧은 트랜잭션).

---

## H. 검수 체크리스트 (원본 §7, 우리 스택판)

- [ ] 정부 키 없이 세션이 끝까지 돌고 방어력 점수가 나온다
- [ ] Stage 4 `has_precedent`일 때 `/api/fiscal`·`/api/prism` 호출 0회
- [ ] Stage 4 `no_precedent`일 때 6회 호출
- [ ] 결과에 "선례 없음" 문자열이 없다 (원본 §3)
- [ ] 실질 독창성에 소수점 점수가 없다 (4구간 + 확신도)
- [ ] B급 근거에 사업명·연도가 인용되지 않는다
- [ ] 축 B가 실패/지연돼도 축 A(방어력)가 먼저 표시된다
- [ ] `grade()` 결과가 변경 전과 동일 (회귀)
- [ ] 예산 시계열 마지막 값이 0이면 "종료" 표기
- [ ] **OpenAI·유료 키·브라우저 키 입력이 어디에도 없다** (Claude 전환 확인)

---

## 정리

원본 SPEC의 **설계·원칙·7단계·표기 규칙은 100% 보존**한다. 바뀌는 것은 런타임뿐이다 —
JS→Python, OpenAI→Claude, Vercel→FastAPI, 동기 Promise→비동기 파이썬. 그리고 축 B를
축 A와 **분리해 비동기**로 돌려 터널 타임아웃과 체감 속도 문제를 함께 푼다.

**결정 대기:** (1) 이 번역판으로 진행할지, (2) 정부 키 2개를 발급하실지(없으면 판정 보류로
동작), (3) 축 B 비동기 분리안(C절)에 동의하실지. 셋 확정되면 파일 단위 구현 계획으로
넘어간다.
