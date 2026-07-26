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
    "bill": ["질의어1", "질의어2", "질의어3"]
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

# 세 조회 소스는 서로 다른 질문에 답한다

- **재정(세출예산)** — 예산이 붙어 **집행**되었는가.
- **PRISM** — 연구로 **검토**되었는가.
- **국회 의안** — **제도화(입법)**가 시도되었는가.

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

# 미발견은 독창성을 확정하지 못한다 — 부재의 증거는 증거의 부재 (반드시 지킬 것)

선례를 **찾은 것**은 강한 증거지만, **못 찾은 것**은 약한 증거다. 미발견은 다음 중
무엇이든 될 수 있다: (a) 실제로 선례가 없음, (b) 이름이 달라 검색이 놓침, (c) DB가
못 덮는 영역(지자체·기금·행정지침·해외·오래된 시기)에 존재함, (d) 질의어가 부실함.
따라서 **판정은 비대칭으로 한다.**

- 세 소스가 **모두 미발견**이고 지식 판정도 선례를 대지 못하면:
  - `band`는 `"계열 밖 시도"`까지 갈 수 있으나 **잠정**이며, 확신도는 **`상`을 쓰지 않는다**(최대 `중`).
  - `reasoning`에 **어느 소스·어느 시기·어떤 영역을 못 덮었는지** 검색 한계를 **한 문장 이상** 반드시 적는다.
  - `retraction_condition`에 "다른 이름의 검색어나 누락 영역에서 선례가 나오면 하향" 취지를 적는다.
- **미발견을 "완전 최초·독창 확정"으로 단정하지 않는다.** "찾은 범위에서 미발견"까지만 말한다.

# 표기 금지

- "선례 없음" (X) → "N개 질의에서 미발견" (O)
- B급 근거로 사업명·연도 인용 (X) → "유사 취지의 바우처 계열이 존재" (O)
- "이미 국회에서 폐기된 법안"(임기만료폐기를 두고) (X) → "발의되었으나 심사 미완으로 임기만료" (O)

# 출력 형식

코드 펜스나 설명 없이 아래 JSON **하나만** 출력한다. `source`는 fiscal|prism|bill|knowledge.

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


def grade_originality(spec_result, judge, hits, api_key):
    payload = {
        "spec": spec_result["spec"],
        "policy_type": spec_result["policy_type"],
        "knowledge_verdict": judge,
        "lookup": hits if hits is not None else "미실행",
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
    for term in terms:
        for eraco in ERACO_TERMS:
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
                print(f"allbillv2 lookup 실패({term}/{eraco}):", e, file=sys.stderr)
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
        return (1 if hits[src] else 0) if on[src] else None
    return {"exec": bit("fiscal"), "review": bit("prism"), "law": bit("bill")}


def _do_lookups(spec):
    """명세의 질의어로 재정·PRISM·의안을 조회한다(가용 소스만). hits 또는 None."""
    fns = {
        "fiscal": _fiscal_local_search if _fiscal_available() else None,
        "prism": _prism_lookup if DATA_GO_KR_KEY else None,
        "bill": _bill_lookup if ASSEMBLY_KEY else None,
    }
    on = {k: v is not None for k, v in fns.items()}
    if not any(on.values()):
        return None
    queries = {s: (list(spec["queries"].get(s, []))[:3] if on[s] else [])
               for s in fns}

    def _safe(fn, q):
        try:
            return fn(q) or []
        except Exception:
            return []

    collected = {"fiscal": [], "prism": [], "bill": []}
    with ThreadPoolExecutor(max_workers=9) as ex:
        futs = {s: [ex.submit(_safe, fns[s], q) for q in queries[s]] if on[s] else []
                for s in fns}
        for s in fns:
            for fut in futs[s]:
                collected[s] += fut.result()
    dedup_key = {"fiscal": "name", "prism": "title", "bill": "name"}
    hits = {s: _dedup(collected[s], dedup_key[s])[:5] for s in fns}
    hits["queries"] = queries
    hits["profile"] = _profile_bits(hits, on)
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
    return {
        "fiscal": _fiscal_available(),
        "prism": bool(DATA_GO_KR_KEY),
        "bill": bool(ASSEMBLY_KEY),
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
