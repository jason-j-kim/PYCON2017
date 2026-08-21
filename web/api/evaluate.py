# -*- coding: utf-8 -*-
"""Vercel 서버리스 함수 — 정책 아이디어의 '실질 독창성'(축 B)을 평가한다.

입력: 정책 설명(자유 서술) + 방문자의 Claude API 키(BYOK, 브라우저에서 입력).
처리: 명세 추출 → 지식 판정 → 재정·PRISM·국회 의안 조회 → 독창성 판정.
  · Claude 3회 호출은 Anthropic Messages API로 한다(방문자 키 사용).
  · 재정(집행)은 함께 번들된 fiscal.json 로컬 검색(키 불필요).
  · PRISM(검토)·국회 의안(입법)은 정부 오픈API — 키는 Vercel 환경변수로 둔다
    (DATA_GO_KR_KEY, ASSEMBLY_KEY). 없으면 그 소스는 건너뛴다.

의존성 없음(표준 라이브러리만) — Vercel Python 런타임에서 그대로 돈다.
웹앱(webapp/app.py)·엔진(socratic/engine.py)의 검증된 로직을 이식했다.
"""
import html
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# ── Claude(Anthropic Messages API) ────────────────────────────────────────
# 방문자가 브라우저에 넣은 키로 호출한다. 서버(Vercel)에는 저장하지 않는다.
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
CLAUDE_MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "4000"))


def call_claude_json(system_prompt, user_prompt, api_key, schema=None):
    """Anthropic Messages API를 도구 호출로 불러 '유효한 JSON(dict)'을 돌려받는다.
    도구 입력은 API가 형식을 보장하므로 텍스트 파싱(따옴표 깨짐 등)이 필요 없다.
    schema를 주면 필수 필드를 강제해 필드 누락(policy_type 등)을 막는다."""
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": CLAUDE_MAX_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "tools": [{"name": "record",
                   "description": "결과를 이 도구의 입력(JSON)으로 제출한다.",
                   "input_schema": schema or {"type": "object"}}],
        "tool_choice": {"type": "tool", "name": "record"},
    }).encode("utf-8")
    req = urllib.request.Request(ANTHROPIC_URL, data=body, headers={
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        hint = ""
        if e.code == 401:
            hint = " (Claude API 키가 올바르지 않습니다. 키를 다시 확인하세요.)"
        elif e.code == 429:
            hint = " (요청이 한도를 초과했습니다. 잠시 후 다시 시도하세요.)"
        raise RuntimeError(f"Claude API 오류 HTTP {e.code}: {detail[:300]}{hint}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Claude API 연결 실패: {e.reason}")
    for b in data.get("content", []):
        if b.get("type") == "tool_use":
            return b.get("input", {})
    raise RuntimeError(f"구조화 출력 실패 (stop_reason={data.get('stop_reason')})")


def _call_and_parse(system_prompt, user_prompt, api_key, validator, schema=None):
    last_error = None
    for _ in range(2):
        obj = call_claude_json(system_prompt, user_prompt, api_key, schema=schema)
        try:
            return validator(obj)
        except (ValueError, KeyError, TypeError) as e:
            last_error = e
    raise RuntimeError(f"채점 결과 검증 실패: {last_error}")


# 필수 필드를 강제하는 도구 입력 스키마(누락 방지). 값의 세부 형식은 프롬프트가 안내한다.
_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "spec": {"type": "object"},
        "policy_type": {"type": "string"},
        "claimed_precedents": {"type": "array"},
        "queries": {
            "type": "object",
            "properties": {
                "fiscal": {"type": "array", "items": {"type": "string"}},
                "prism": {"type": "array", "items": {"type": "string"}},
                "bill": {"type": "array", "items": {"type": "string"}},
                "overseas": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["fiscal", "prism", "bill"],
        },
    },
    "required": ["spec", "policy_type", "claimed_precedents", "queries"],
}
_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string",
                    "enum": ["has_precedent", "no_precedent", "uncertain"]},
        "recalled": {"type": "array"},
        "reasoning": {"type": "string"},
        "retraction_condition": {"type": "string"},
    },
    "required": ["verdict"],
}
_GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "band": {"type": "string",
                 "enum": ["선례 명확", "계열 내 변형", "계열 밖 시도", "판정 보류"]},
        "confidence": {"type": "string"},
        "evidence": {"type": "array"},
        "reasoning": {"type": "string"},
        "retraction_condition": {"type": "string"},
    },
    "required": ["band"],
}


# ── 시스템 프롬프트(축 B 3단계) ────────────────────────────────────────────
# socratic/prompts/ 의 검증된 프롬프트를 그대로 옮겼다(단일 소스처럼 유지).
SPEC_EXTRACTOR_SYSTEM = """# 역할

당신은 정책 아이디어 평가의 **명세 추출가**다. 대화 로그(또는 정책 설명)를 받아 정책을
구조화하고, 선례 조회용 질의어를 만든다. **채점하지 않는다.** 요청된 JSON만 출력한다.

# 임무

1. 로그에서 정책의 핵심을 `spec`으로 요약한다 — 대상·수단·전달경로·재원.
2. 정책 유형을 하나 고른다(`policy_type`).
3. 제안자가 대화 중 스스로 지목한 기존 사업·제도를 `claimed_precedents`로 모은다(없으면 빈 배열).
4. 선례 조회용 질의어를 만든다(`queries`).

# 질의어 생성 규칙

- **대상어 × 수단어** 조합으로 만든다. 소스별 3개, 총 9개를 넘기지 않는다.
- **각 소스마다, 정책의 핵심 주제를 나타내는 '짧은 단일 명사'를 최소 하나 넣는다.**
  예: `무용`, `경유차`, `데이터바우처`, `청년월세`. **복합 신조어를 만들지 말 것** —
  `무용교육`·`예술교과` 같은 붙인 말 대신 `무용`·`교육`처럼 **쪼갠 형태**로 넣는다.
- **법률명·일반어를 한 덩어리로 붙이지 말 것.** 예: `학교체육진흥법 무용 교육`(X) →
  `무용`, `학교체육진흥법`을 **각각 따로**(O).
- **행정 명명법으로 보정한다.** 예산서·정책연구 과제명·법률명은 일상 표현과 다르다.
  - "청년 주거 지원" → `주거급여`, `청년월세`, `주거비 지원`
  - "소상공인 디지털 전환" → `스마트상점`, `소상공인 디지털`, `온라인 판로`
- `fiscal` 질의어: **사업명**에 걸리도록 짧게(2~4어절) + 핵심 단일 명사 하나.
- `prism` 질의어: **짧은 핵심 키워드**. 서술형은 최대 하나만.
- `bill` 질의어: **법률명 후보**(예: `무용진흥법`) 또는 **핵심 주제 단일 명사**(예: `무용`).
  둘을 각각 별도 질의어로 넣는다.
- `overseas` 질의어: **영어 키워드**(해외 정책사례 DB는 영문). 정책 핵심 주제의 짧은
  영어 명사·구 2~3개. 예: 예술가 기본소득→`basic income artists`, 청년월세→`youth housing allowance`.
- `claimed_precedents`에 사업명이 있으면 그 표현을 질의어에 우선 포함한다.

# 출력 형식

코드 펜스나 설명 없이 아래 JSON **하나만** 출력한다. JSON으로 시작해 JSON으로 끝난다.

{
  "spec": {
    "target": "누구를 대상으로 하는가",
    "instrument": "무엇을 주거나 규제하는가",
    "channel": "어떤 경로로 전달되는가",
    "funding": "재원 (진술 없으면 '미진술')"
  },
  "policy_type": "보조금 | 조세지출 | 규제 | 규제특례·실증 | 바우처 | 인증·정보제공 | 플랫폼·중개 | 조직개편",
  "claimed_precedents": [
    {"name": "제안자가 지목한 사업명", "period": "제안자가 말한 시기"}
  ],
  "queries": {
    "fiscal": ["질의어1", "질의어2", "질의어3"],
    "prism": ["질의어1", "질의어2", "질의어3"],
    "bill": ["질의어1", "질의어2", "질의어3"],
    "overseas": ["english keyword1", "english keyword2"]
  }
}

한국어로 작성한다."""

PRECEDENT_JUDGE_SYSTEM = """# 역할

당신은 정책 선례의 **지식 판정가**다. 정책 명세를 받아, **당신이 이미 알고 있는
지식만으로** 유사 선례가 있는지 판정한다. 외부 검색은 하지 않는다. 요청된 JSON만
출력한다.

# 원칙

- **"선례가 있다"는 기억으로 말할 수 있지만, "선례가 없다"는 기억으로 단정할 수 없다.**
  없다는 것은 부재 증명이므로, 확신이 서지 않으면 `uncertain`으로 둔다.
- 여기서의 **과잉 확신이 유령 선례의 유일한 발생 경로**다. 확실하지 않은 것을
  `A_candidate`로 올리지 않는다.

# 판정 규칙

- `recalled`의 각 항목에 `grade`를 붙인다.
  - `A_candidate` — 사업명·시기·소관부처를 특정할 수 있을 만큼 확실.
  - `B` — 유형 수준만 확실(구체 사업명은 불확실).
  - 불확실하면 목록에서 **제외**한다.
- **연도·부처 정합성을 스스로 점검한다.** 2008년 이전 사안에 "교육과학기술부",
  2013년 이전에 "미래창조과학부"가 등장하면 기억 오류 신호이므로 등급을 내린다.
- `verdict`는 종합 판정이다: 확실한 선례가 있으면 `has_precedent`, 없다고 볼
  근거가 있으면 `no_precedent`, 판단이 서지 않으면 `uncertain`.

# 해외·국제기구 사례도 반드시 포함한다 (반드시 지킬 것)

- 국내 선례만이 아니라 **해외 국가·국제기구(OECD·EU·UN·World Bank 등)** 의 유사 정책·
  실험·연구도 `recalled`에 포함한다. 이 시스템의 외부 조회는 국내 자료(재정·연구·의안)뿐이라,
  **해외 선례는 오직 이 지식 판정 단계에서만** 반영될 수 있다.
- 단, 해외 사례는 조회로 검증되지 않으므로 **grade는 항상 `B`** 로 두고, 확신이 없으면
  `note`에 **'추정'** 을 명시한다. 정확한 사업명·연도·기관을 확신 없이 지어내지 않는다
  (유령 선례 방지) — **국가명 + 대략의 취지**까지만 적는다.
  - 예: "아일랜드가 2020년대 초 예술가 대상 기본소득 시범사업을 도입한 것으로 기억(추정, 세부 미확인)".
- **국내 미발견이라도 해외에 유사 사례가 있으면** `verdict`를 `no_precedent`로 두지 말고
  `uncertain` 또는 `has_precedent`(해외 근거)로 판단한다. "국내 미발견 = 완전 최초"로 단정하지 않는다.
- `reasoning`에는 **국내/해외를 구분**해 적는다(예: "국내 조회로는 미발견이나, 해외에 유사 취지 존재(추정)").

# 출력 형식

코드 펜스나 설명 없이 아래 JSON **하나만** 출력한다.

{
  "verdict": "has_precedent | no_precedent | uncertain",
  "recalled": [
    {"name": "기억하는 사업·제도", "period": "대략의 시기", "grade": "A_candidate | B", "note": "무엇이 유사한가"}
  ],
  "reasoning": "판정 근거 3문장 이내",
  "retraction_condition": "이 판정을 철회하게 될 조건"
}

한국어로 작성한다."""

ORIGINALITY_GRADER_SYSTEM = """# 역할

당신은 정책의 **실질 독창성 판정가**다. 정책 명세와 (있으면) 선례 조회 결과, 지식
판정을 받아, 이 정책 아이디어가 실제로 새로운지 판정한다.
**사람(제안자)이 아니라 산출물(정책)을 평가한다.** 요청된 JSON만 출력한다.

# 조회 소스는 서로 다른 질문에 답한다

- **재정(세출예산)** — 예산이 붙어 **집행**되었는가. (국내)
- **PRISM** — 연구로 **검토**되었는가. (국내)
- **국회 의안** — **제도화(입법)**가 시도되었는가. (국내)
- **해외(OPSI)** — **다른 나라 정부가 실제로 시행**했는가. `lookup.overseas`에 히트가
  있으면 국가·본문(설계)까지 인용 가능한 **A급 해외 근거**다(있을 때만).

의안 히트의 `result`(의결현황)를 반드시 아래 규칙으로 읽는다.

| 값 | 읽는 법 |
|---|---|
| 원안가결 · 수정가결 | 제도화 완료. 선례 명확 |
| 부결 | 아이디어가 실제로 기각됨. **강한 신호** |
| 대안반영폐기 | 다른 법안에 흡수됨. 아이디어는 살아 있음 |
| **임기만료폐기** | **기각이 아니다.** 심사 미완이며 발의안 상당수가 이 경로로 사라진다. **감점 근거로 쓰지 않는다** |
| 계류 | 진행 중 |

# 조회 결과는 대개 "제목·메타데이터"일 뿐 본문이 아니다 (반드시 지킬 것)

- 재정 = 사업명 + 예산 시계열. **사업이 무엇을 하는지 설명은 없다.**
- PRISM = 연구명 + 기관 + 일자. **초록·연구 내용은 없다.**
- 의안 = 의안명 + 발의자 + 의결결과. 히트에 **`summary`(제안이유·주요내용 본문)가
  있을 수 있다** — 있으면 본문이 있는 유일한 소스다. 없으면 제목만이다.

따라서 **이름(제목)이 겹친다는 것은 "유사 후보가 존재한다"는 신호일 뿐, 제안 정책과
내용이 동일하다는 증거가 아니다.** 이름은 같아도 설계·대상·전달방식이 다르면 오히려
**독창성의 근거**가 된다. 감점하려면 조회 히트의 이름만 보지 말고, **명세(`spec`)에
담긴 실제 설계와 대조해 "정말 같은 것인가"를 한 문장 이상 논증**해야 한다. 대조 없이
이름 일치만으로 감점하지 않는다.

- **의안 히트에 `summary`(본문)가 있으면** "선례 있다/없다"에 그치지 말고, 그 본문과
  제안 정책의 **설계 차이(대상·수단·전달방식)를 한 문장 이상** 구체적으로 진술한다.

# 원칙

- **10점 척도를 쓰지 않는다.** 4구간(`band`)과 확신도(`confidence`)만 낸다.
- **A급 근거라도 그 자체로 감점을 정당화하지 않는다.**
  - A급 = 조회(재정·PRISM·의안)에서 확인된 후보. 사업명·연도·부처·예산·의안명을 인용할 수 있다.
    단, **명세와 설계가 실질적으로 일치함을 함께 논증할 때만** 감점 근거가 된다.
  - B급 = 모델 기억. **유형 수준 진술만** 하고 고유명사를 인용하지 않는다.
- 창의성은 `policy_type` **계열 내부에서 상대적으로** 판정한다.
- **예산 시계열**의 최근 연도 예산이 0이거나 그 연도 레코드가 없으면 **종료된 사업**이다.
- **임기만료폐기 의안을 근거로 감점하지 않는다.** `부결`과 `대안반영폐기`만 판정 근거로 쓴다.
- 조회가 실행되지 않았고 지식 판정이 `uncertain`이면 → `band: "판정 보류"`.

# 미실행 통로를 "0건"으로 쓰지 않는다 (반드시 지킬 것)

네 통로가 항상 다 도는 것은 아니다. 키나 데이터가 없으면 그 통로는 **아예 돌지
않는다.** `lookup.coverage`가 통로마다 실행 여부를 명시하고, 미실행 통로는 배열이
아니라 `"미실행(조회하지 않음)"` 문자열로 온다.

**미실행과 0건은 전혀 다른 사실이다.**

| 상태 | 뜻 | 판정에 쓰는 법 |
|---|---|---|
| 실행 — 히트 0건 | 조회했으나 못 찾음 | **약한** 미발견 근거. 그래도 부재의 증거는 아니다 |
| **미실행** | 조회 자체를 안 함 | **아무 정보도 아니다.** 근거로 전혀 쓰지 않는다 |

- 미실행 통로를 두고 "0건", "흔적이 없다", "시도되지 않았다"고 **쓰지 않는다.**
- `reasoning`에는 **어느 통로가 미실행이었는지 한 번은 밝힌다.**
- **미실행 통로가 하나라도 있으면 확신도 `상`을 쓰지 않는다**(최대 `중`).
- `retraction_condition`에 그 미실행 통로를 돌렸을 때 선례가 나오면 하향한다는
  취지를 적는다.

# 미발견은 독창성을 확정하지 못한다 — 부재의 증거는 증거의 부재 (반드시 지킬 것)

여기서 말하는 미발견은 **실제로 조회를 돌린 통로**에 한한다. 미실행 통로는 미발견에
포함하지 않는다(위 절 참조).

선례를 **찾은 것**은 강한 증거지만, **못 찾은 것**은 약한 증거다. 미발견은 다음 중
무엇이든 될 수 있다: (a) 실제로 선례가 없음, (b) 이름이 달라 검색이 놓침, (c) DB가
못 덮는 영역(지자체·기금·행정지침·해외·오래된 시기)에 존재함, (d) 질의어가 부실함.
따라서 **판정은 비대칭으로 한다.**

- 실행된 소스가 **모두 미발견**이고 지식 판정도 선례를 대지 못하면:
  - `band`는 `"계열 밖 시도"`까지 갈 수 있으나 **잠정**이며, 확신도는 **`상`을 쓰지 않는다**(최대 `중`).
  - `reasoning`에 **어느 소스·어느 시기·어떤 영역을 못 덮었는지** 검색 한계를 **한 문장 이상** 반드시 적는다.
  - `retraction_condition`에 "다른 이름의 검색어나 누락 영역에서 선례가 나오면 하향" 취지를 적는다.
- **미발견을 "완전 최초·독창 확정"으로 단정하지 않는다.** "찾은 범위에서 미발견"까지만 말한다.

# 해외 선례: 조회(OPSI)면 A급, 없으면 지식 B급 (반드시 지킬 것)

- `lookup.overseas`에 히트가 **있으면** 그 해외 사례는 **A급(`source: overseas`)** 으로,
  국가·연도·본문(설계)을 인용해 근거로 쓴다. 국내 A급(fiscal·prism·bill)과 소스만 구분한다.
- `lookup.overseas`가 **없거나 비어** 있는데도 해외 유사 사례가 기억나면, 그것은 조회로
  검증되지 않았으므로 **반드시 `knowledge`(B급)** 로 표기하고, 국내 A급과 **분리**한다.
- 해외 B급 근거는 **국가명 + 취지**까지만, '추정' 톤을 유지하고 고유명사(사업명·연도) 남발 금지.
- **국내 미발견이지만 해외에 유사 사례가 있으면** 이를 판정에 반영한다 — 이 경우 `band`를
  `"계열 밖 시도"`로 올리지 않는다(해외에 이미 같은 계열이 존재하므로 국내 최초일 뿐이다).
  `reasoning`에 "국내 미발견 · 해외에 유사 사례 존재(추정)"처럼 **국내/해외를 구분**해 적는다.

# 표기 금지

- "선례 없음" (X) → "N개 질의에서 미발견" (O)
- (미실행 통로를 두고) "의안 조회는 0건" (X) → "의안 통로는 미실행 — 확인하지 못함" (O)
- (미실행 통로를 두고) "입법 시도 흔적이 없다" (X) → "입법 시도 여부는 조회하지 않아 알 수 없다" (O)
- B급 근거로 사업명·연도 인용 (X) → "유사 취지의 바우처 계열이 존재" (O)
- "이미 국회에서 폐기된 법안"(임기만료폐기를 두고) (X) → "발의되었으나 심사 미완으로 임기만료" (O)

# 출력 형식

코드 펜스나 설명 없이 아래 JSON **하나만** 출력한다. `source`는 fiscal|prism|bill|overseas|knowledge.

{
  "band": "선례 명확 | 계열 내 변형 | 계열 밖 시도 | 판정 보류",
  "confidence": "상 | 중 | 하",
  "evidence": [
    {"grade": "A", "source": "fiscal", "text": "「사업명」 2022~2024, 국토교통부, 예산 1,020억→0 (2024년 종료)"},
    {"grade": "A", "source": "bill", "text": "「○○법 일부개정법률안」 2023 발의, 부결 — 동일 취지"},
    {"grade": "B", "source": "knowledge", "text": "2000년대 중반 유사 취지의 바우처 계열이 존재"}
  ],
  "reasoning": "3~5문장",
  "retraction_condition": "이 판정을 철회하게 될 조건"
}

한국어로 작성한다."""

_BANDS = ("선례 명확", "계열 내 변형", "계열 밖 시도", "판정 보류")


# ── 축 B 3단계(Claude) ────────────────────────────────────────────────────
def extract_spec(transcript, api_key):
    prompt = ("<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
              "시스템 프롬프트의 형식에 따라 JSON 하나만 출력하라.")

    def validate(r):
        if not isinstance(r, dict):
            raise ValueError("dict 아님")
        # 누락 필드는 실패시키지 않고 기본값으로 채운다(조회는 queries만 있으면 된다).
        r.setdefault("spec", {})
        r.setdefault("policy_type", "미상")
        r.setdefault("claimed_precedents", [])
        if not isinstance(r.get("queries"), dict):
            r["queries"] = {}
        r["queries"].setdefault("fiscal", [])
        r["queries"].setdefault("prism", [])
        r["queries"].setdefault("bill", [])
        r["queries"].setdefault("overseas", [])   # 해외(OPSI) 영어 질의어
        return r

    return _call_and_parse(SPEC_EXTRACTOR_SYSTEM, prompt, api_key, validate,
                           schema=_SPEC_SCHEMA)


def judge_by_knowledge(spec_result, api_key):
    payload = json.dumps({
        "spec": spec_result["spec"],
        "policy_type": spec_result["policy_type"],
        "claimed_precedents": spec_result.get("claimed_precedents", []),
    }, ensure_ascii=False, indent=1)
    prompt = ("<정책 명세>\n" + payload + "\n</정책 명세>\n\n"
              "시스템 프롬프트의 형식에 따라 JSON 하나만 출력하라.")

    def validate(r):
        if not isinstance(r, dict):
            raise ValueError("dict 아님")
        if r.get("verdict") not in ("has_precedent", "no_precedent", "uncertain"):
            r["verdict"] = "uncertain"      # 누락·오값이면 보수적으로 판단 보류
        r.setdefault("recalled", [])
        r.setdefault("reasoning", "")
        r.setdefault("retraction_condition", "")
        return r

    return _call_and_parse(PRECEDENT_JUDGE_SYSTEM, prompt, api_key, validate,
                           schema=_JUDGE_SCHEMA)


SOURCE_LABEL = {"fiscal": "재정(집행)", "prism": "KDI 연구(검토)",
                "bill": "국회 의안(입법)", "overseas": "해외 OPSI(시행)"}
_PROFILE_KEY = {"fiscal": "exec", "prism": "review",
                "bill": "law", "overseas": "intl"}


def judge_lookup_view(hits):
    """판정가에게 넘길 조회 결과 표현(터널판 socratic/engine.py와 동일 규칙).

    미실행 통로를 빈 배열로 넘기면 '조회했는데 0건'과 구분되지 않아, 판정문이
    "의안 조회는 0건으로 입법 시도 흔적이 없고"처럼 미실행을 부재로 단정한다.
    미실행 통로는 배열 대신 문자열로 바꿔 셀 수 없게 하고 coverage로 못 박는다."""
    if hits is None:
        return "미실행 — 어느 통로도 조회하지 않았다. 0건이 아니다."
    view = dict(hits)
    prof = hits.get("profile") or {}
    queries = dict(hits.get("queries") or {})
    failed = hits.get("failed") or {}
    coverage = {}
    for src, pkey in _PROFILE_KEY.items():
        label = SOURCE_LABEL[src]
        if prof.get(pkey) is None:
            view[src] = "미실행(조회하지 않음)"
            queries[src] = "미실행"
            coverage[label] = "미실행 — 조회기가 없어 돌리지 않았다. 0건이 아니며 부재의 근거가 될 수 없다."
        elif src in failed:
            view[src] = "조회 실패(오류로 결과를 받지 못함)"
            coverage[label] = ("조회 실패 — 시도했으나 모두 오류로 끝났다"
                               f"({failed[src][:80]}). 0건이 아니며 부재의 근거가 될 수 없다.")
        else:
            n_q = len((hits.get("queries") or {}).get(src) or [])
            coverage[label] = f"실행 — 질의 {n_q}개, 히트 {len(hits.get(src) or [])}건"
    view["queries"] = queries
    view["coverage"] = coverage
    return view


def grade_originality(spec_result, judge, hits, api_key):
    payload = {
        "spec": spec_result["spec"],
        "policy_type": spec_result["policy_type"],
        "knowledge_verdict": judge,
        "lookup": judge_lookup_view(hits),
    }
    prompt = ("<입력>\n" + json.dumps(payload, ensure_ascii=False, indent=1)
              + "\n</입력>\n\n시스템 프롬프트의 형식에 따라 JSON 하나만 출력하라.")

    def validate(r):
        if not isinstance(r, dict):
            raise ValueError("dict 아님")
        if r.get("band") not in _BANDS:
            r["band"] = "판정 보류"          # 누락·오값이면 보수적으로 판정 보류
        r.setdefault("confidence", "하")
        r.setdefault("evidence", [])
        r.setdefault("reasoning", "")
        r.setdefault("retraction_condition", "")
        return r

    return _call_and_parse(ORIGINALITY_GRADER_SYSTEM, prompt, api_key, validate,
                           schema=_GRADE_SCHEMA)


# ── 정부 오픈API 키(Vercel 환경변수) ──────────────────────────────────────
def _clean_key(name):
    return os.environ.get(name, "").strip().strip('"').strip("'").strip()


DATA_GO_KR_KEY = _clean_key("DATA_GO_KR_KEY")   # PRISM(정책연구)
ASSEMBLY_KEY = _clean_key("ASSEMBLY_KEY")        # 국회 의안
# PRISM(data.go.kr API)이 불안정해 기본 정지. 되살리려면 PRISM_ENABLED=1.
# '검토(연구)' 슬롯은 KDI 로컬 코퍼스(_kdi_lookup)가 있으면 그쪽을 우선 쓴다.
PRISM_ENABLED = os.environ.get("PRISM_ENABLED", "0").strip().lower() in ("1", "true", "yes")

# ── 공통 HTTP ─────────────────────────────────────────────────────────────
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_TIMEOUT = 8


def _redact(url):
    return re.sub(r"([?&](?:serviceKey|ServiceKey|KEY)=)[^&]+", r"\1***", url)


def _urlopen_read(url, accept, referer=None, data=None, timeout=None):
    headers = {"Accept": accept, "User-Agent": _UA, "Accept-Language": "ko,en;q=0.9"}
    if referer:
        headers["Referer"] = referer
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout or _TIMEOUT) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise RuntimeError(
            f"HTTP {e.code} {e.reason} | URL {_redact(url)} | 본문 {body[:400]}")


def _http_get_json(url, timeout=None):
    return json.loads(_urlopen_read(url, "application/json", timeout=timeout))


def _http_get_data(url):
    raw = _urlopen_read(url, "application/json, application/xml")
    s = raw.lstrip("﻿ \t\r\n")
    if s[:1] in ("{", "["):
        return json.loads(raw)
    try:
        return _xml_to_obj(ET.fromstring(raw))
    except ET.ParseError:
        return {}


def _xml_to_obj(el):
    kids = list(el)
    if not kids:
        return (el.text or "").strip()
    out = {}
    for c in kids:
        tag = c.tag.split("}")[-1]
        v = _xml_to_obj(c)
        if tag in out:
            if not isinstance(out[tag], list):
                out[tag] = [out[tag]]
            out[tag].append(v)
        else:
            out[tag] = v
    return out


def _pick(row, *keys):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for x in obj:
            r = _find_key(x, key)
            if r is not None:
                return r
    return None


def _as_rows(node):
    if isinstance(node, list):
        return [x for x in node if isinstance(x, dict)]
    if isinstance(node, dict):
        return [node]
    return []


# ── 공용 키워드 매칭 ──────────────────────────────────────────────────────
_STOPWORDS = frozenset({
    "분석", "연구", "지원", "방안", "정책", "사업", "효과", "제도", "개선", "강화",
    "관리", "활성화", "촉진", "계획", "전략", "체계", "현황", "실태", "평가", "도입",
    "운영", "구축", "확대", "및", "등", "관한", "위한", "대한", "기반", "관련",
})


def _keyword_hit(query, *texts):
    hay = " ".join(t for t in texts if t)
    q = (query or "").strip()
    if not q or not hay:
        return False
    if q in hay:
        return True
    meaningful = [t for t in q.split() if len(t) >= 2 and t not in _STOPWORDS]
    if not meaningful:
        meaningful = [t for t in q.split() if t]
    present = sum(1 for t in meaningful if t in hay)
    return present >= 2 if len(meaningful) >= 2 else present >= 1


# ── 재정: 로컬 정적 파일(fiscal.json) ─────────────────────────────────────
FISCAL_JSON = Path(__file__).resolve().parent / "fiscal.json"
_fiscal_cache = None


def _fiscal_available():
    return FISCAL_JSON.exists()


def _load_fiscal():
    global _fiscal_cache
    if _fiscal_cache is None:
        try:
            data = json.loads(FISCAL_JSON.read_text(encoding="utf-8"))
            _fiscal_cache = data["items"] if isinstance(data, dict) else data
        except Exception:
            _fiscal_cache = []
    return _fiscal_cache


def _fiscal_local_search(query):
    q = (query or "").strip()
    if not q:
        return []
    out = [rec for rec in _load_fiscal() if _keyword_hit(q, rec.get("name", ""))]
    out.sort(key=lambda r: max((s.get("amount", 0) for s in r.get("series", [])),
                               default=0), reverse=True)
    return out[:5]


# ── PRISM: 정책연구 과제(API) ─────────────────────────────────────────────
PRISM_BASE = os.environ.get(
    "PRISM_BASE", "https://apis.data.go.kr/1741000/prism_v2/getResearchList_v2")
PRISM_START = os.environ.get("PRISM_START", "20180101")
PRISM_END = os.environ.get("PRISM_END", "20261231")
PRISM_TIMEOUT = int(os.environ.get("PRISM_TIMEOUT", "20"))
PRISM_ROWS = int(os.environ.get("PRISM_ROWS", "100"))
PRISM_PAGES = int(os.environ.get("PRISM_PAGES", "3"))


def _decode_key(key):
    return urllib.parse.unquote(key or "")


def _prism_lookup(query):
    if not DATA_GO_KR_KEY:
        return []
    q = (query or "").strip()
    distinct = _bill_distinct_tokens(q) or [
        t for t in q.split() if len(t) >= 2 and t not in _STOPWORDS]
    if not distinct:
        return []
    out, seen = [], set()
    for page in range(1, PRISM_PAGES + 1):
        try:
            params = {"serviceKey": _decode_key(DATA_GO_KR_KEY), "type": "json",
                      "start_date": PRISM_START, "end_date": PRISM_END,
                      "numOfRows": PRISM_ROWS, "pageNo": page}
            data = _http_get_json(PRISM_BASE + "?" + urllib.parse.urlencode(params),
                                  timeout=PRISM_TIMEOUT)
            rows = _as_rows(_find_key(data, "research"))
            if not rows:
                break
            for r in rows:
                title = _pick(r, "research_name", "biz_name")
                if not title or title in seen:
                    continue
                hay = f"{_pick(r, 'research_name') or ''} {_pick(r, 'biz_name') or ''}"
                if not any(t in hay for t in distinct):
                    continue
                seen.add(title)
                out.append({"title": title,
                            "org": _pick(r, "organ_name"),
                            "period": _pick(r, "research_date")})
            if len(out) >= 5 or len(rows) < PRISM_ROWS:
                break
        except Exception as e:
            print(f"prism lookup 실패(p{page}):", e, file=sys.stderr)
            break
    return out[:5]


# ── 국회 의안: 열린국회정보 ALLBILLV2 ─────────────────────────────────────
ALLBILL_BASE = os.environ.get(
    "ALLBILL_BASE", "https://open.assembly.go.kr/portal/openapi/ALLBILLV2")
ERACO_TERMS = [t.strip() for t in os.environ.get(
    "ERACO_TERMS", "제22대,제21대").split(",") if t.strip()]
BILL_PSIZE = int(os.environ.get("BILL_PSIZE", "5"))
LIKMS_DETAIL_BASE = os.environ.get(
    "LIKMS_DETAIL_BASE", "https://likms.assembly.go.kr/bill/bi/billDetailPage.do")
LIKMS_BILLINFO = os.environ.get(
    "LIKMS_BILLINFO", "https://likms.assembly.go.kr/bill/bi/bill/detail/billInfo.do")
LIKMS_MENU_NO = os.environ.get("LIKMS_MENU_NO", "2600044")
BILL_SUMMARY_MAXLEN = int(os.environ.get("BILL_SUMMARY_MAXLEN", "500"))

_BILL_BROAD = _STOPWORDS | frozenset({
    "교육", "학교", "학생", "수업", "교과", "과정", "교육과정", "신설", "지정",
    "필수", "의무", "의무화", "시행", "국가", "국민", "서비스", "정보", "프로그램",
    "지자체", "활동", "확보", "마련", "추진", "조성",
})


def _is_lawname(tok):
    return tok.endswith(("법", "법률", "법안", "법률안"))


def _bill_distinct_tokens(query):
    toks = [t for t in (query or "").split()
            if len(t) >= 2 and t not in _BILL_BROAD and not _is_lawname(t)]
    return list(dict.fromkeys(toks))


def _bill_search_terms(query):
    toks = _bill_distinct_tokens(query)
    if not toks:
        toks = [t for t in (query or "").split() if len(t) >= 2 and t not in _STOPWORDS]
    return sorted(dict.fromkeys(toks), key=len, reverse=True)[:2]


def _strip_html(s):
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _bill_summary(bill_id):
    """2단계: BILL_ID로 의안정보시스템(likms)에서 제안이유 본문을 시도한다.

    ※ 미완(나중에 보완): 신형 likms는 SPA라 billInfo.do가 섹션별 조각을 주는데,
      제안이유 섹션을 고르는 정확한 파라미터를 아직 확정하지 못해 대개 빈 값이 된다.
      실패해도 무해하며(제목·결과만 남음), 코드는 향후 확정을 쉽게 하도록 남겨둔다."""
    if not bill_id:
        return ""
    referer = LIKMS_DETAIL_BASE + "?" + urllib.parse.urlencode(
        {"billId": bill_id, "currMenuNo": LIKMS_MENU_NO})
    qs = urllib.parse.urlencode({"billId": bill_id, "currMenuNo": LIKMS_MENU_NO})
    for method, url, data in (("GET", LIKMS_BILLINFO + "?" + qs, None),
                              ("POST", LIKMS_BILLINFO, qs.encode("utf-8"))):
        try:
            text = _strip_html(_urlopen_read(url, "text/html", referer=referer, data=data))
            m = re.search(r"제안이유", text)
            if m:
                body = text[m.start():].strip()
                if len(body) >= 40:
                    return body[:BILL_SUMMARY_MAXLEN]
        except Exception as e:
            print(f"bill summary(likms {method}) 실패:", e, file=sys.stderr)
    return ""


def _bill_lookup(query):
    if not ASSEMBLY_KEY:
        return []
    q = (query or "").strip()
    terms = _bill_search_terms(q)
    if not terms:
        return []
    distinct = _bill_distinct_tokens(q)
    cand, seen = [], set()
    # 시도와 실패를 센다. 전부 실패했다면 '0건'이 아니라 '조회 실패'다 — 그대로
    # 빈 목록을 돌려주면 망 장애가 미발견 근거로 둔갑한다(방법론 4.5.4).
    tries = fails = 0
    last_err = None
    for term in terms:
        for eraco in ERACO_TERMS:
            tries += 1
            try:
                params = {"KEY": ASSEMBLY_KEY, "Type": "json", "pIndex": 1,
                          "pSize": BILL_PSIZE, "ERACO": eraco, "BILL_NM": term}
                data = _http_get_data(ALLBILL_BASE + "?" + urllib.parse.urlencode(params))
                rows = _as_rows(_find_key(data, "row"))
                for r in rows:
                    name = _pick(r, "BILL_NM", "BILL_NAME")
                    if name and name not in seen:
                        seen.add(name)
                        cand.append(r)
            except Exception as e:
                fails += 1
                last_err = e
                print(f"allbillv2 lookup 실패({term}/{eraco}):", e, file=sys.stderr)
    if tries and fails == tries:
        raise RuntimeError(f"국회 의안 API 조회 실패: {last_err}")
    out = []
    for r in cand[:12]:
        name = _pick(r, "BILL_NM", "BILL_NAME")
        # 제안이유 본문(likms)은 웹(서버리스 60초 제한)에서는 조회하지 않는다 —
        # 후보 12건마다 GET+POST를 돌리면 시간이 초과되고, 대개 빈 값이라 이득이 없다.
        # 제목(의안명)만으로 관련성을 판정한다(_bill_summary 코드는 향후용으로 남겨둠).
        body = ""
        if distinct:
            if not any(t in name for t in distinct):
                continue
        elif not _keyword_hit(q, name):
            continue
        out.append({
            "name": name,
            "proposer": _pick(r, "PROPOSER", "PPSR_NM", "RPPSR_NM"),
            "date": _pick(r, "PPSL_DT", "PROPOSE_DT", "PPSL_DATE"),
            "committee": _pick(r, "JRCMIT_NM", "CURR_COMMITTEE", "COMMITTEE_NM"),
            "result": _pick(r, "RGS_CONF_RSLT", "JRCMIT_PROC_RSLT", "PROC_STAGE_CD",
                            "PASSGUBN") or "계류",
            "summary": body,
            "link": _pick(r, "LINK_URL", "DETAIL_LINK"),
            "eraco": _pick(r, "ERACO"),
        })
        if len(out) >= 5:
            break
    return out


# ── 축 B 조립(엔진 originality_axis 이식) ──────────────────────────────────
def _dedup(items, key):
    seen, out = set(), []
    for it in items:
        k = it.get(key)
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _profile_bits(hits, on):
    def bit(src):
        return (1 if hits.get(src) else 0) if on.get(src) else None
    return {"exec": bit("fiscal"), "review": bit("prism"),
            "law": bit("bill"), "intl": bit("overseas")}


# ── 해외 축: OPSI 로컬 DB(함수와 함께 번들될 때만 켜짐) ──
OPSI_DB = Path(__file__).resolve().parent / "opsi_policies.db"


def _opsi_available():
    if not OPSI_DB.exists():
        return False
    try:
        with sqlite3.connect(OPSI_DB) as c:
            return c.execute("SELECT COUNT(*) FROM cases").fetchone()[0] > 0
    except Exception:
        return False


# OPSI 사례 거의 전부에 등장해 변별력이 없는 초일반어(검색 잡음 제거).
_OPSI_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "has", "have",
    "not", "but", "all", "any", "can", "will", "new", "use", "using", "used", "based",
    "into", "per", "via", "its", "their", "our", "your", "more", "most", "such", "than",
    "then", "they", "them", "also", "may", "one", "two", "who", "how", "what", "when",
    "where", "which", "while", "been", "being", "were", "would", "could", "should",
    "about", "over", "under", "between", "within", "across", "through",
    "public", "government", "governmental", "service", "services", "sector", "innovation",
    "innovative", "project", "programme", "program", "initiative", "national", "citizen",
    "citizens", "people", "community", "development", "management",
}


def _opsi_lookup(query):
    raw = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", query or "")]
    toks = [t for t in raw if t not in _OPSI_STOP] or raw
    if not toks or not OPSI_DB.exists():
        return []
    try:
        conn = sqlite3.connect(OPSI_DB)
        conn.row_factory = sqlite3.Row
        where = " OR ".join(["cleaned_content LIKE ? OR title LIKE ? OR country LIKE ?"] * len(toks))
        params = []
        for t in toks:
            params += [f"%{t}%", f"%{t}%", f"%{t}%"]
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM cases WHERE {where} LIMIT 120", params).fetchall()]
        conn.close()
    except Exception as e:
        print("opsi lookup 실패:", e, file=sys.stderr)
        return []
    scored = []
    for d in rows:
        title = (d.get("title") or "").lower()
        hay = f"{title} {(d.get('cleaned_content') or '').lower()}"
        score = 0
        for t in toks:
            if t in title:
                score += 3
            elif t in hay:
                score += 1
        for a, b in zip(toks, toks[1:]):
            if f"{a} {b}" in hay:
                score += 3
        if score:
            scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{
        "title": d.get("title"), "country": d.get("country"), "year": d.get("year"),
        "sector": d.get("sector"), "level": d.get("level_of_government"),
        "summary": (d.get("cleaned_content") or "")[:500], "url": d.get("source_url"),
    } for _, d in scored[:5]]


# ── 검토(연구) 축: KDI 정책연구 로컬 코퍼스(kdi_corpus.db) ──
# PRISM(API)을 대체한다. reports 테이블이 채워지면 자동 활성화, 비면 자동 정지.
KDI_DB = Path(__file__).resolve().parent / "kdi_corpus.db"          # naive 폴백(reports)
KDI_SQLITE = Path(os.environ.get("KDI_SQLITE", str(Path(__file__).resolve().parent / "kdi.sqlite")))  # kdinov(docs)

_KDI_STOP = {"및", "등", "관한", "관련", "대한", "위한", "통한", "그리고", "또는",
             "the", "and", "for", "with", "of", "in", "on", "to", "study", "연구",
             "정책", "방안", "분석", "제도", "개선", "방향", "과제"}

_KDINOV = None
_KDI_CORPUS = None


def _kdinov():
    """kdinov 모듈 묶음(없으면 None). web/api/kdinov를 경로에 넣고 한 번만 로드."""
    global _KDINOV
    if _KDINOV is None:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from kdinov import sources as _s, model as _m, decompose as _d
            from kdinov import search as _se, verdict as _v
            _KDINOV = {"sources": _s, "model": _m, "decompose": _d,
                       "search": _se, "verdict": _v}
        except Exception as e:
            print("kdinov 로드 실패:", e, file=sys.stderr)
            _KDINOV = False
    return _KDINOV or None


def _kdi_corpus():
    global _KDI_CORPUS
    if _KDI_CORPUS is None:
        k = _kdinov()
        if k and KDI_SQLITE.exists():
            try:
                _KDI_CORPUS = k["sources"].Store(str(KDI_SQLITE)).all()
            except Exception as e:
                print("kdi corpus 로드 실패:", e, file=sys.stderr)
                _KDI_CORPUS = []
        else:
            _KDI_CORPUS = []
    return _KDI_CORPUS


def _kdi_idea_text(spec):
    """kdinov 분해용 전체 아이디어 문장을 명세에서 구성한다(키워드보다 정확)."""
    s = (spec or {}).get("spec") or {}
    parts = [s.get("target"), s.get("instrument"), s.get("channel"), s.get("funding")]
    txt = " ".join(str(p).strip() for p in parts
                   if p and str(p).strip() and str(p).strip() != "미진술")
    for c in (spec or {}).get("claimed_precedents") or []:
        nm = (c or {}).get("name")
        if nm:
            txt += " " + str(nm)
    if not txt.strip():
        txt = " ".join((spec or {}).get("queries", {}).get("prism", []) or [])
    return txt.strip()


def _kdinov_lookup(query):
    """kdinov로 KDI 코퍼스 대조: decompose→search→assess. 상위 5건에 code/role 부착."""
    k = _kdinov()
    corpus = _kdi_corpus()
    if not k or not corpus:
        return None
    try:
        idea = k["model"].Idea.from_dict(k["decompose"].decompose_policy_idea(query or ""))
        hits = k["search"].search_docs(corpus, k["search"].terms_from_idea(idea), limit=5)
        out = []
        for h in hits:
            d = h.doc
            a = k["verdict"].assess(d, idea)
            out.append({
                "title": d.title, "org": d.kind or d.source, "period": d.year(),
                "summary": (h.snippet or d.summary or "")[:500], "url": d.url,
                "code": a.code, "role": a.role, "score": a.score,
            })
        return out
    except Exception as e:
        print("kdinov lookup 실패:", e, file=sys.stderr)
        return None


def _kdi_available():
    # 가벼운 체크: 코퍼스 전체를 로딩하지 않고 존재·건수만 확인(첫 화면 상태용).
    if _kdinov() and KDI_SQLITE.exists():
        try:
            with sqlite3.connect(str(KDI_SQLITE)) as c:
                if c.execute("SELECT COUNT(*) FROM docs").fetchone()[0] > 0:
                    return True
        except Exception:
            pass
    if not KDI_DB.exists():                # naive reports 폴백
        return False
    try:
        with sqlite3.connect(KDI_DB) as c:
            return c.execute("SELECT COUNT(*) FROM reports").fetchone()[0] > 0
    except Exception:
        return False


def _kdi_lookup(query):
    """검토(연구) 슬롯: kdinov 우선, 없으면 naive reports 조회."""
    hits = _kdinov_lookup(query)
    if hits is not None:
        return hits
    return _kdi_naive_lookup(query)


def _kdi_naive_lookup(query):
    """폴백: KDI reports 코퍼스 LIKE 검색 상위 5건. 반환형은 PRISM과 동일 + summary."""
    raw = [w.lower() for w in re.findall(r"[0-9A-Za-z가-힣][\w가-힣\-]{1,}", query or "")]
    toks = [t for t in raw if t not in _KDI_STOP and len(t) >= 2] or raw
    if not toks or not KDI_DB.exists():
        return []
    try:
        conn = sqlite3.connect(KDI_DB)
        conn.row_factory = sqlite3.Row
        where = " OR ".join(["cleaned_content LIKE ? OR title LIKE ? OR keywords LIKE ?"] * len(toks))
        params = []
        for t in toks:
            params += [f"%{t}%", f"%{t}%", f"%{t}%"]
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM reports WHERE {where} LIMIT 120", params).fetchall()]
        conn.close()
    except Exception as e:
        print("kdi lookup 실패:", e, file=sys.stderr)
        return []
    scored = []
    for d in rows:
        title = (d.get("title") or "").lower()
        hay = f"{title} {(d.get('keywords') or '').lower()} {(d.get('cleaned_content') or '').lower()}"
        score = 0
        for t in toks:
            if t in title:
                score += 3
            elif t in hay:
                score += 1
        for a, b in zip(toks, toks[1:]):
            if f"{a} {b}" in hay:
                score += 3
        if score:
            scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{
        "title": d.get("title"), "org": d.get("org") or d.get("organization"),
        "period": d.get("period") or d.get("year"),
        "summary": (d.get("cleaned_content") or "")[:500], "url": d.get("url") or d.get("source_url"),
    } for _, d in scored[:5]]


def _do_lookups(spec):
    """명세의 질의어로 재정·KDI(연구)·의안·해외(OPSI)를 조회한다(가용 소스만). hits 또는 None."""
    # kdinov(KDI)가 활성이면 '연구' 질의어를 전체 아이디어 문장 하나로 치환(분해 정확도↑).
    if _kdinov() and _kdi_corpus():
        spec.setdefault("queries", {})["prism"] = [_kdi_idea_text(spec) or "정책"]
    fns = {
        "fiscal": _fiscal_local_search if _fiscal_available() else None,
        # '검토(연구)' 슬롯: KDI 코퍼스가 있으면 그것, 없으면 PRISM(플래그 켜졌을 때만).
        "prism": (_kdi_lookup if _kdi_available()
                  else (_prism_lookup if (PRISM_ENABLED and DATA_GO_KR_KEY) else None)),
        "bill": _bill_lookup if ASSEMBLY_KEY else None,
        "overseas": _opsi_lookup if _opsi_available() else None,
    }
    on = {k: v is not None for k, v in fns.items()}
    if not any(on.values()):
        return None
    queries = {s: (list(spec["queries"].get(s, []))[:3] if on[s] else [])
               for s in fns}

    def _safe(fn, q):
        """오류를 삼키되 삼켰다는 사실은 남긴다(터널판 engine.py와 동일).
        통신 실패를 그냥 []로 돌리면 '조회했는데 0건'과 구분되지 않는다."""
        try:
            return fn(q) or [], None
        except Exception as e:
            return [], f"{type(e).__name__}: {e}"

    collected = {s: [] for s in fns}
    errors = {s: [] for s in fns}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {s: [ex.submit(_safe, fns[s], q) for q in queries[s]] if on[s] else []
                for s in fns}
        for s in fns:
            for fut in futs[s]:
                rows, err = fut.result()
                collected[s] += rows
                if err:
                    errors[s].append(err)
    dedup_key = {"fiscal": "name", "prism": "title", "bill": "name", "overseas": "url"}
    hits = {s: _dedup(collected[s], dedup_key[s])[:5] for s in fns}
    hits["queries"] = queries
    hits["profile"] = _profile_bits(hits, on)
    hits["failed"] = {s: errors[s][0] for s in fns
                      if on[s] and queries[s] and len(errors[s]) == len(queries[s])}
    return hits


def originality_axis(transcript, api_key):
    """대화 로그 → 명세 추출 → (지식 판정 ∥ 조회) → 독창성 판정.
    지식 판정(Claude)과 외부 조회는 서로 독립이라 동시에 실행해 시간을 줄인다
    (서버리스 60초 제한 대응)."""
    spec = extract_spec(transcript, api_key)
    with ThreadPoolExecutor(max_workers=2) as ex:
        judge_fut = ex.submit(judge_by_knowledge, spec, api_key)
        hits_fut = ex.submit(_do_lookups, spec)
        judge = judge_fut.result()
        hits = hits_fut.result()
    grade = grade_originality(spec, judge, hits, api_key)
    return {"spec": spec, "judge": judge, "lookup": hits, "originality": grade}


def _sources_status():
    # prism 슬롯은 KDI 코퍼스(kdinov)가 있으면 켜짐. 옛 PRISM 키는 플래그가 켜졌을 때만.
    return {
        "fiscal": _fiscal_available(),
        "prism": _kdi_available() or bool(PRISM_ENABLED and DATA_GO_KR_KEY),
        "bill": bool(ASSEMBLY_KEY),
        "overseas": _opsi_available(),
    }


def _evaluate(payload):
    # 문답 웹은 전체 대화 로그(transcript)를 보낸다. 단문 정책 설명(policy)도 허용.
    transcript = (payload.get("transcript") or payload.get("policy") or "").strip()
    api_key = (payload.get("api_key") or "").strip()
    if not transcript:
        raise ValueError("대화 로그(또는 정책 설명)가 비어 있습니다.")
    if not api_key:
        raise ValueError("Claude API 키를 입력하세요.")
    if len(transcript) > 20000:
        transcript = transcript[:20000]
    result = originality_axis(transcript, api_key)
    o = result["originality"]
    lk = result.get("lookup")
    return {
        "policy_type": result["spec"].get("policy_type"),
        "spec": result["spec"].get("spec"),
        "claimed_precedents": result["spec"].get("claimed_precedents", []),
        "band": o.get("band"),
        "confidence": o.get("confidence"),
        "evidence": o.get("evidence", []),
        "reasoning": o.get("reasoning", ""),
        "retraction_condition": o.get("retraction_condition", ""),
        "knowledge_verdict": result["judge"].get("verdict"),
        "lookup": lk,
        "sources": _sources_status(),
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # 정부 소스 가용 여부만 알려준다(키 값은 노출하지 않는다).
        self._send(200, {"sources": _sources_status()})

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._send(400, {"error": "요청 본문(JSON)을 읽지 못했습니다."})
            return
        try:
            self._send(200, _evaluate(payload))
        except ValueError as e:
            self._send(400, {"error": str(e)})
        except RuntimeError as e:
            self._send(502, {"error": str(e)})
        except Exception as e:
            self._send(500, {"error": f"서버 오류: {e}"})
