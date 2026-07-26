"""소크라테스 아이디어 평가 — 웹 MVP (FastAPI).

실행 (저장소 루트에서):
    pip install fastapi "uvicorn[standard]"
    claude /login                      # 최초 1회, Pro 구독 로그인 (API 키 불필요)
    python webapp/app.py               # http://localhost:8000
    # 또는: uvicorn webapp.app:app --port 8000
"""

import html
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from socratic import engine

try:
    from webapp import db
except ImportError:  # `python webapp/app.py`로 직접 실행한 경우
    import db

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="소크라테스 아이디어 평가")
db.init()

# 외부 공개(터널) 시 안전장치 — 환경 변수로 설정
ACCESS_CODE = os.environ.get("SOCRATIC_ACCESS_CODE", "").strip()
MAX_SESSIONS_PER_DAY = int(os.environ.get("SOCRATIC_MAX_SESSIONS_PER_DAY", "30"))
# 1이면 루트(/)를 /policy로 리다이렉트 → 연구자에게 수정판만 노출.
POLICY_ONLY = os.environ.get("SOCRATIC_POLICY_ONLY", "").strip() in ("1", "true", "True")
# 선례 조사 축(축 B) — 공공데이터포털 키 하나로 PRISM·국회 의안을 함께 쓴다.
# 재정(세출예산)은 API가 아니라 로컬 정적 파일(data/fiscal.json)이라 키가 필요 없다.
def _clean_key(name):
    """환경변수 키에서 흔한 실수(따옴표·공백·개행)를 제거한다.
    cmd에서 set KEY=\"abc\" 처럼 넣으면 따옴표가 값에 포함되어 400을 유발한다."""
    return os.environ.get(name, "").strip().strip('"').strip("'").strip()


DATA_GO_KR_KEY = _clean_key("DATA_GO_KR_KEY")      # PRISM
# 국회 의안은 열린국회정보(open.assembly.go.kr) 별도 인증키를 쓴다.
ASSEMBLY_KEY = _clean_key("ASSEMBLY_KEY")


@app.exception_handler(RuntimeError)
def runtime_error_handler(request: Request, exc: RuntimeError):
    """엔진 오류(claude CLI 미설치/미로그인 등)를 사용자가 읽을 수 있는 메시지로 반환."""
    return JSONResponse(status_code=502, content={"detail": str(exc)})


class CreateRequest(BaseModel):
    idea: str
    weights: dict | None = None  # {"originality": w1, "practicality": w2, "acceptance": w3}
    access_code: str | None = None
    profile: str | None = None   # 원본 | 정책 (수정판). 없으면 원본.


class AnswerRequest(BaseModel):
    answer: str


def _format_turn(t):
    if t["role"] == "questioner":
        return f"[턴 {t['seq']}] 질문자({t['stage']}): {t['content']}"
    return f"[턴 {t['seq']}] 제안자: {t['content']}"


def _transcript_log(sid):
    return [_format_turn(t) for t in db.get_turns(sid)]


def _next_seq(sid):
    turns = db.get_turns(sid)
    return (turns[-1]["seq"] + 1) if turns else 1


def _progress(stage_index, q_in_stage):
    _, label, n_turns, _ = engine.STAGES[stage_index]
    return {
        "stage_index": stage_index,
        "stage_label": label,
        "question_no": q_in_stage,
        "questions_in_stage": n_turns,
        "total_stages": len(engine.STAGES),
    }


def _ask_and_store(sid, stage_index):
    """현재 단계의 다음 질문을 생성해 저장하고 반환한다."""
    name, label, _, directive = engine.STAGES[stage_index]
    # 정책 프로필의 독창성 라운드에만 선례 지목 유도문을 덧붙인다(원본 무영향).
    session = db.get_session(sid)
    if session and session["profile"] == "정책" and name == "originality":
        directive = directive + " " + engine.PRECEDENT_ANCHOR_LINE
    question = engine.ask_questioner(_transcript_log(sid), directive)
    db.add_turn(sid, _next_seq(sid), "questioner", label, question)
    return question


def _grade_session(sid, weights, profile="원본"):
    """대화 로그를 채점하고 결과를 저장한다."""
    result = engine.grade("\n\n".join(_transcript_log(sid)), profile)
    total = round(engine.weighted_total(result, weights), 2)
    db.save_evaluation(sid, result, total)
    db.set_status(sid, "graded")
    return _evaluation_payload(result, total, weights, profile)


def _evaluation_payload(result, total, weights, profile="원본"):
    labels = engine.checklist_labels(profile)
    payload = {
        "profile": profile,
        "criteria": [
            {
                "key": c,
                "label": engine.CRITERIA_KO[c],
                "weight": weights[c],
                "final": result["criteria"][c]["final"],
                "checklist_total": result["criteria"][c]["checklist"]["total"],
                "holistic_score": result["criteria"][c]["holistic"]["score"],
                "holistic_rationale": result["criteria"][c]["holistic"]["rationale"],
                "items": [
                    {
                        "id": item_id,
                        "label": labels[c][item_id],
                        "met": entry["met"],
                        "evidence": entry["evidence"],
                    }
                    for item_id, entry in result["criteria"][c]["checklist"]["items"].items()
                ],
            }
            for c in engine.CRITERIA
        ],
        "weighted_total": total,
        "strengths": result["strengths"],
        "suggestions": result["suggestions"],
        "encouragement": result["encouragement"],
    }
    # 5문장 프레임·점수 범위·근거신뢰도는 원본·수정판 모두에 얹는다.
    # 전부 코드 계산 — 추가 Claude 호출 없음. (프로필 차이는 A9 채점뿐.)
    payload["five_lines"] = engine.five_lines(result, weights)
    payload["score_band"] = engine.score_band(result, weights)
    payload["evidence_level"] = engine.evidence_level(result)
    return payload


@app.get("/")
def index():
    # 터널 배포(SOCRATIC_POLICY_ONLY=1) 시 원본 대신 수정판으로 보낸다.
    if POLICY_ONLY:
        return RedirectResponse(url="/policy")
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/policy")
def policy():
    """수정판(정책 평가) — 5문장 프레임·점수 범위·강화 A9 채점."""
    return FileResponse(STATIC_DIR / "policy.html")


@app.get("/api/config")
def get_config():
    return {"access_required": bool(ACCESS_CODE)}


@app.post("/api/sessions")
def create_session(req: CreateRequest):
    if ACCESS_CODE and (req.access_code or "").strip() != ACCESS_CODE:
        raise HTTPException(403, "초대 코드가 올바르지 않습니다.")
    if db.count_sessions_today() >= MAX_SESSIONS_PER_DAY:
        raise HTTPException(429, "오늘 사용 가능한 세션 수를 모두 사용했습니다. 내일 다시 시도해 주세요.")
    idea = req.idea.strip()
    if not idea:
        raise HTTPException(400, "아이디어가 비어 있습니다.")
    weights = req.weights or dict(engine.DEFAULT_WEIGHTS)
    if set(weights) != set(engine.CRITERIA):
        raise HTTPException(400, "가중치 키가 올바르지 않습니다.")
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise HTTPException(400, f"가중치의 합은 1이어야 합니다 (현재 {sum(weights.values()):.2f})")
    profile = (req.profile or "원본").strip()
    if profile not in engine.PROFILES:
        raise HTTPException(400, "알 수 없는 평가 프로필입니다.")

    sid = db.create_session(idea, weights, profile)
    db.add_turn(sid, 1, "proposer", None, idea)
    question = _ask_and_store(sid, 0)
    db.update_progress(sid, 0, 1)
    return {"session_id": sid, "question": question, "progress": _progress(0, 1)}


@app.post("/api/sessions/{sid}/answer")
def answer(sid: str, req: AnswerRequest):
    session = db.get_session(sid)
    if not session:
        raise HTTPException(404, "세션이 없습니다.")
    if session["status"] != "active":
        raise HTTPException(400, "이미 채점이 끝난 세션입니다.")
    text = req.answer.strip()
    if not text:
        raise HTTPException(400, "답변이 비어 있습니다.")

    db.add_turn(sid, _next_seq(sid), "proposer", None, text)

    stage_index = session["stage_index"]
    q_in_stage = session["q_in_stage"]
    # 현재 단계의 질문을 모두 소화했으면 다음 단계로
    if q_in_stage >= engine.STAGES[stage_index][2]:
        stage_index += 1
        q_in_stage = 0

    if stage_index >= len(engine.STAGES):
        weights = json.loads(session["weights"])
        evaluation = _grade_session(sid, weights, session["profile"])
        return {"done": True, "evaluation": evaluation}

    question = _ask_and_store(sid, stage_index)
    q_in_stage += 1
    db.update_progress(sid, stage_index, q_in_stage)
    return {"done": False, "question": question,
            "progress": _progress(stage_index, q_in_stage)}


@app.post("/api/sessions/{sid}/finish")
def finish(sid: str):
    """남은 문답을 건너뛰고 지금까지의 로그로 바로 채점한다."""
    session = db.get_session(sid)
    if not session:
        raise HTTPException(404, "세션이 없습니다.")
    if session["status"] != "active":
        raise HTTPException(400, "이미 채점이 끝난 세션입니다.")
    weights = json.loads(session["weights"])
    evaluation = _grade_session(sid, weights, session["profile"])
    return {"done": True, "evaluation": evaluation}


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    session = db.get_session(sid)
    if not session:
        raise HTTPException(404, "세션이 없습니다.")
    weights = json.loads(session["weights"])
    payload = {
        "session_id": sid,
        "idea": session["idea"],
        "status": session["status"],
        "weights": weights,
        "turns": db.get_turns(sid),
    }
    ev = db.get_evaluation(sid)
    if ev:
        payload["evaluation"] = _evaluation_payload(
            ev["result"], ev["weighted_total"], weights, session["profile"]
        )
    return payload


# ── 선례 조사 축(축 B) ────────────────────────────────────────────────────
# 세 소스는 서로 다른 질문에 답한다: 재정(집행)·PRISM(검토)·국회 의안(입법).
# 재정은 로컬 정적 파일(연 1회 갱신)이라 키가 없다. PRISM은 DATA_GO_KR_KEY로
# apis.data.go.kr를, 국회 의안은 ASSEMBLY_KEY로 열린국회정보(open.assembly.go.kr,
# ALLBILLV2)를 호출한다. 실패/키 없음이면 해당 소스를 건너뛰고, 미조회는
# 미발견으로 처리하지 않는다(profile 비트에서 None → 화면 '-').
PRISM_BASE = os.environ.get(
    "PRISM_BASE", "https://apis.data.go.kr/1741000/prism_v2/getResearchList_v2")
# 국회 의안: 열린국회정보 '의안정보 통합 API'(ALLBILLV2). ASSEMBLY_KEY를 쓴다.
# 필수 파라미터: KEY·Type·pIndex·pSize + ERACO(대수). 검색은 BILL_NM(의안명).
ALLBILL_BASE = os.environ.get(
    "ALLBILL_BASE", "https://open.assembly.go.kr/portal/openapi/ALLBILLV2")
# ERACO(대수)가 필수라 대수별로 조회한다. 최근 대수 위주(연구 목적상 최근 선례가 중요).
ERACO_TERMS = [t.strip() for t in os.environ.get(
    "ERACO_TERMS", "제22대,제21대").split(",") if t.strip()]
# 페이지 크기. 일부 열린국회 키는 5로 제한되어 100을 보내면 400이 난다(브라우저 확인).
# 상위 몇 건만 쓰므로 5로 충분. 전체 승인 키를 쓰면 BILL_PSIZE로 올릴 수 있다.
BILL_PSIZE = int(os.environ.get("BILL_PSIZE", "5"))
# 제안이유·주요내용 본문: ALLBILLV2엔 없다. 의안정보시스템(likms)의 요약 팝업에서
# BILL_ID로 받아온다(인증키 불필요, 공개 웹). 상위 5건만 조회한다.
# 새 의안정보시스템: 상세 페이지(껍데기)는 billDetailPage.do, 제안이유 본문은 그
# 안에서 billInfo.do가 불러온다(DevTools로 확인). billInfo.do를 직접 호출한다.
LIKMS_DETAIL_BASE = os.environ.get(
    "LIKMS_DETAIL_BASE", "https://likms.assembly.go.kr/bill/bi/billDetailPage.do")
LIKMS_BILLINFO = os.environ.get(
    "LIKMS_BILLINFO", "https://likms.assembly.go.kr/bill/bi/bill/detail/billInfo.do")
LIKMS_MENU_NO = os.environ.get("LIKMS_MENU_NO", "2600044")
BILL_SUMMARY_MAXLEN = int(os.environ.get("BILL_SUMMARY_MAXLEN", "500"))  # 본문 앞에서 500자
FISCAL_JSON = ROOT / "data" / "fiscal.json"
_TIMEOUT = 8
_fiscal_cache = None


def _redact(url):
    """로그용: 인증키 값을 가린다(경로·나머지 파라미터는 보이게)."""
    return re.sub(r"([?&](?:serviceKey|ServiceKey|KEY)=)[^&]+", r"\1***", url)


# 일부 정부 API 방화벽이 Python-urllib 기본 User-Agent를 400으로 막는다.
# 브라우저처럼 보이게 헤더를 붙인다(브라우저로는 되는데 서버로만 400인 원인).
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _urlopen_read(url, accept, referer=None, data=None, timeout=None):
    """공통 GET/POST. HTTPError면 응답 본문(진짜 사유)까지 담아 RuntimeError로 올린다.
    referer를 주면 헤더에 넣는다(likms처럼 Referer를 검사하는 사이트용).
    data(bytes)를 주면 POST로 보낸다(폼 인코딩). timeout으로 대기시간을 늘릴 수 있다."""
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
    """JSON이면 json, XML이면 dict/list로 변환해 반환한다. data.go.kr 일부
    오퍼레이션은 XML만 주므로, 어느 쪽이 와도 _find_key·_pick으로 다루게 만든다."""
    raw = _urlopen_read(url, "application/json, application/xml")
    s = raw.lstrip("﻿ \t\r\n")
    if s[:1] in ("{", "["):
        return json.loads(raw)
    try:
        return _xml_to_obj(ET.fromstring(raw))
    except ET.ParseError:
        return {}


def _xml_to_obj(el):
    """XML 엘리먼트를 중첩 dict/list로. 같은 태그 반복은 리스트로 묶는다."""
    kids = list(el)
    if not kids:
        return (el.text or "").strip()
    out = {}
    for c in kids:
        tag = c.tag.split("}")[-1]  # 네임스페이스 접두사 제거
        v = _xml_to_obj(c)
        if tag in out:
            if not isinstance(out[tag], list):
                out[tag] = [out[tag]]
            out[tag].append(v)
        else:
            out[tag] = v
    return out


def _find_rows(obj):
    """중첩 JSON에서 dict들의 리스트(레코드 집합)를 재귀로 찾는다."""
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            return obj
        for x in obj:
            r = _find_rows(x)
            if r:
                return r
    elif isinstance(obj, dict):
        for v in obj.values():
            r = _find_rows(v)
            if r:
                return r
    return []


def _pick(row, *keys):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _find_key(obj, key):
    """중첩 JSON에서 특정 키의 값을 재귀로 찾는다(첫 번째)."""
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
    """레코드 컨테이너를 dict 리스트로 정규화(단건이면 리스트로 감싼다)."""
    if isinstance(node, list):
        return [x for x in node if isinstance(x, dict)]
    if isinstance(node, dict):
        return [node]
    return []


# ── 재정: 로컬 정적 파일 검색 (API 아님) ──
def _fiscal_available():
    return FISCAL_JSON.exists()


def _load_fiscal():
    global _fiscal_cache
    if _fiscal_cache is None:
        try:
            data = json.loads(FISCAL_JSON.read_text(encoding="utf-8"))
            # {unit, items:[...]} 래퍼 또는 [...] 배열 모두 허용.
            _fiscal_cache = data["items"] if isinstance(data, dict) else data
        except Exception:
            _fiscal_cache = []
    return _fiscal_cache


# 세 소스 공용 키워드 매칭. 흔한 일반어 단독 매칭을 막아 거짓 양성을 줄인다.
# 규칙: 전체 문구가 통째로 들어있거나, '의미 있는' 토큰이 2개 이상 함께 겹칠 때만 히트.
# (의미 있는 토큰이 하나뿐인 질의는 그 하나만 겹쳐도 히트 — 과소매칭 방지.)
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
    if not meaningful:                       # 질의가 전부 일반어/단문자면 원래 토큰 사용
        meaningful = [t for t in q.split() if t]
    present = sum(1 for t in meaningful if t in hay)
    return present >= 2 if len(meaningful) >= 2 else present >= 1


def _fiscal_local_search(query):
    """세부사업명 매칭(공용 규칙). 히트 과다 시 예산액 큰 순 5건."""
    q = (query or "").strip()
    if not q:
        return []
    out = [rec for rec in _load_fiscal() if _keyword_hit(q, rec.get("name", ""))]
    out.sort(key=lambda r: max((s.get("amount", 0) for s in r.get("series", [])),
                               default=0), reverse=True)
    return out[:5]


# ── PRISM: 정책연구 과제 (API) ──
# getResearchList_v2는 start_date·end_date가 필수(NO_MANDATORY_REQUEST_PARAMETERS_ERROR)
# 이고 searchword로 키워드 검색을 지원한다. 날짜(필수)+searchword(좁힘)를 함께 보낸다.
PRISM_START = os.environ.get("PRISM_START", "20180101")
PRISM_END = os.environ.get("PRISM_END", "20261231")
PRISM_TIMEOUT = int(os.environ.get("PRISM_TIMEOUT", "25"))  # PRISM API가 느려 별도 대기


def _decode_key(key):
    """data.go.kr 키를 raw로 정규화한다. Encoding 키(%2B·%2F·%3D 포함)든 Decoding
    키든 넣을 수 있게 unquote로 통일 → urlencode가 다시 정확히 인코딩한다."""
    return urllib.parse.unquote(key or "")


def _prism_search_terms(query):
    """PRISM searchword용 핵심어. 의미 있는 토큰 중 구체적인(긴) 것 최대 2개."""
    toks = [t for t in (query or "").split() if len(t) >= 2 and t not in _STOPWORDS]
    if not toks:
        toks = [t for t in (query or "").split() if t]
    return sorted(dict.fromkeys(toks), key=len, reverse=True)[:2]


def _prism_lookup(query):
    if not DATA_GO_KR_KEY:
        return []
    q = (query or "").strip()
    terms = _prism_search_terms(q)
    if not terms:
        return []
    out, seen = [], set()
    for term in terms:
        try:
            params = {"serviceKey": _decode_key(DATA_GO_KR_KEY), "type": "json",
                      "start_date": PRISM_START, "end_date": PRISM_END,
                      "numOfRows": 20, "pageNo": 1, "searchword": term}
            data = _http_get_json(PRISM_BASE + "?" + urllib.parse.urlencode(params),
                                  timeout=PRISM_TIMEOUT)
            rows = _as_rows(_find_key(data, "research"))
            if not rows:
                _debug_once(f"prism-{term}", data)
                continue
            for r in rows:
                # 확정 필드: research_name(과제명)·organ_name(기관)·research_date(기간).
                title = _pick(r, "research_name", "biz_name")
                if not title or title in seen:
                    continue
                if not _keyword_hit(q, _pick(r, "research_name"), _pick(r, "biz_name")):
                    continue
                seen.add(title)
                out.append({"title": title,
                            "org": _pick(r, "organ_name"),
                            "period": _pick(r, "research_date")})
        except Exception as e:
            print(f"prism lookup 실패({term}):", e, file=sys.stderr)
    return out[:5]


# ── 국회 의안: 열린국회정보 '의안정보 통합 API'(ALLBILLV2), ASSEMBLY_KEY ──
# 필수: KEY·Type·pIndex·pSize + ERACO(대수). 검색은 BILL_NM(의안명, 서버측 부분일치).
# 응답은 열린국회 표준({"ALLBILLV2":[{head},{row}]})이라 row 컨테이너를 꺼낸다.
# ERACO가 필수라 최근 대수별로 조회해 합친다. 목록 API라 제안이유 본문은 없을 수
# 있다 — 본문 필드가 있으면 summary에 담고(있는 데까지), 없으면 제목·결과만.
_DEBUG_SEEN = set()


def _debug_once(tag, obj):
    """미지수 확정용: 처음 한 번만 응답 구조를 콘솔에 찍는다(복사해 주면 필드 확정)."""
    if tag in _DEBUG_SEEN:
        return
    _DEBUG_SEEN.add(tag)
    try:
        preview = json.dumps(obj, ensure_ascii=False)[:800]
    except Exception:
        preview = str(obj)[:800]
    print(f"[축B 디버그:{tag}] {preview}", file=sys.stderr)


def _strip_html(s):
    """HTML을 순수 텍스트로. script/style 제거, 태그 제거, 엔티티 복원, 공백 정리."""
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _bill_summary(bill_id):
    """2단계: BILL_ID로 의안정보시스템(likms)에서 제안이유·주요내용 본문을 받는다.
    likms는 브라우저 위장(UA)+Referer가 필요하다. 요약 팝업 → 상세 페이지 순으로
    시도하고, 실패/빈값이면 빈 문자열(제목·결과만 남는다). 인증키는 필요 없다."""
    if not bill_id:
        return ""
    referer = LIKMS_DETAIL_BASE + "?" + urllib.parse.urlencode(
        {"billId": bill_id, "currMenuNo": LIKMS_MENU_NO})
    qs = urllib.parse.urlencode({"billId": bill_id, "currMenuNo": LIKMS_MENU_NO})
    # billInfo.do를 GET(?billId=) → POST(billId=) 순으로 시도한다(요청 방식 불명).
    # '제안이유'가 실제로 있는 응답만 본문으로 인정한다(404·껍데기 페이지 배제).
    for method, url, data in (("GET", LIKMS_BILLINFO + "?" + qs, None),
                              ("POST", LIKMS_BILLINFO, qs.encode("utf-8"))):
        try:
            text = _strip_html(_urlopen_read(url, "text/html", referer=referer, data=data))
            _debug_once(f"bill-summary-{method}", text[:500])
            m = re.search(r"제안이유", text)
            if m:
                body = text[m.start():].strip()
                if len(body) >= 40:
                    return body[:BILL_SUMMARY_MAXLEN]
        except Exception as e:
            print(f"bill summary(likms {method}) 실패:", e, file=sys.stderr)
    return ""


# 의안 검색·매칭에서 빼는 '너무 흔한' 도메인 일반어(정책·교육 행정 어휘).
# 이런 말로 의안명을 검색하면 무관한 개정안이 쏟아지므로 구체적 주제어만 쓴다.
_BILL_BROAD = _STOPWORDS | frozenset({
    "교육", "학교", "학생", "수업", "교과", "과정", "교육과정", "신설", "지정",
    "필수", "의무", "의무화", "시행", "국가", "국민", "서비스", "정보", "프로그램",
    "지자체", "활동", "확보", "마련", "추진", "조성",
})


def _is_lawname(tok):
    return tok.endswith(("법", "법률", "법안", "법률안"))


def _bill_distinct_tokens(query):
    """의안 관련성 판정용 '구체적 주제어'. 법률명·일반어를 뺀 고유 명사류."""
    toks = [t for t in (query or "").split()
            if len(t) >= 2 and t not in _BILL_BROAD and not _is_lawname(t)]
    return list(dict.fromkeys(toks))


def _bill_search_terms(query):
    """열린국회 BILL_NM 검색용 핵심어. 법률명(개정안 폭주)·일반어를 빼고 구체적
    주제어를 우선 쓴다. 없으면 일반 의미어라도 사용(최대 2개)."""
    toks = _bill_distinct_tokens(query)
    if not toks:
        toks = [t for t in (query or "").split() if len(t) >= 2 and t not in _STOPWORDS]
    return sorted(dict.fromkeys(toks), key=len, reverse=True)[:2]


def _bill_lookup(query):
    """짧은 핵심어로 ALLBILLV2를 대수별 조회해 후보를 모으고, 각 후보에 likms
    제안이유 본문을 붙인 뒤, 원 질의어와 '이름+본문'으로 정밀 필터링한다.
    (의안명은 법률명이라 제목만으로는 주제를 못 담으므로 본문까지 보고 판정한다.)"""
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
                if not rows:
                    _debug_once(f"bill-{term}-{eraco}", data)
                    continue
                for r in rows:
                    name = _pick(r, "BILL_NM", "BILL_NAME")
                    if name and name not in seen:
                        seen.add(name)
                        cand.append(r)
            except Exception as e:
                print(f"allbillv2 lookup 실패({term}/{eraco}):", e, file=sys.stderr)
    out = []
    for r in cand[:12]:                     # 본문 조회 상한(호출 최소화)
        name = _pick(r, "BILL_NM", "BILL_NAME")
        body = _bill_summary(_pick(r, "BILL_ID", "BILL_NO"))
        hay = f"{name} {body}"
        # 구체적 주제어가 하나라도 이름·본문에 있으면 관련 의안으로 본다(등급기가
        # 설계 차이를 판단). 구체어가 없는 질의면 공용 규칙으로 보수적으로 판정.
        if distinct:
            if not any(t in hay for t in distinct):
                continue
        elif not _keyword_hit(q, name, body):
            continue
        out.append({
            "name": name,
            "proposer": _pick(r, "PROPOSER", "PPSR_NM", "RPPSR_NM"),
            "date": _pick(r, "PPSL_DT", "PROPOSE_DT", "PPSL_DATE"),
            "committee": _pick(r, "JRCMIT_NM", "CURR_COMMITTEE", "COMMITTEE_NM"),
            # 본회의 결과 → 소관위 결과 → 처리단계 → 계류구분 순으로 가장 구체적인 값.
            "result": _pick(r, "RGS_CONF_RSLT", "JRCMIT_PROC_RSLT", "PROC_STAGE_CD",
                            "PASSGUBN") or "계류",
            "summary": body,
            "link": _pick(r, "LINK_URL", "DETAIL_LINK"),
            "eraco": _pick(r, "ERACO"),
        })
        if len(out) >= 5:
            break
    return out


class LookupRequest(BaseModel):
    query: str


@app.post("/api/prism")
def api_prism(req: LookupRequest):
    return {"hits": _prism_lookup(req.query.strip())}


@app.post("/api/bill")
def api_bill(req: LookupRequest):
    return {"hits": _bill_lookup(req.query.strip())}


def _originality_payload(result):
    o = result["originality"]
    spec, judge, lookup = result["spec"], result["judge"], result.get("lookup")
    return {
        "band": o["band"], "confidence": o["confidence"],
        "evidence": o["evidence"], "reasoning": o["reasoning"],
        "retraction_condition": o.get("retraction_condition", ""),
        "policy_type": spec.get("policy_type"),
        "verdict": judge.get("verdict"),
        "claimed_precedents": spec.get("claimed_precedents", []),
        "lookup": None if lookup is None else {
            "profile": lookup["profile"], "queries": lookup["queries"],
            "fiscal": lookup["fiscal"], "prism": lookup["prism"], "bill": lookup["bill"],
        },
    }


def _run_originality_axis(sid):
    """백그라운드 스레드: 축 B를 돌려 결과를 DB에 저장한다.
    call_claude가 블로킹이므로 asyncio 대신 스레드로 격리한다."""
    try:
        transcript = "\n\n".join(_transcript_log(sid))
        fiscal_fn = _fiscal_local_search if _fiscal_available() else None
        prism_fn = _prism_lookup if DATA_GO_KR_KEY else None
        bill_fn = _bill_lookup if ASSEMBLY_KEY else None
        result = engine.originality_axis(transcript, fiscal_fn, prism_fn, bill_fn)
        db.save_originality(sid, result)
    except Exception as e:
        db.set_originality_status(sid, "error")
        print("originality axis 실패:", e, file=sys.stderr)


@app.post("/api/sessions/{sid}/originality")
def start_originality(sid: str):
    """축 B를 백그라운드로 시작한다(정책 프로필 전용). 즉시 pending 반환."""
    session = db.get_session(sid)
    if not session:
        raise HTTPException(404, "세션이 없습니다.")
    if session["profile"] != "정책":
        raise HTTPException(400, "정책 프로필 세션에서만 선례 조사를 실행합니다.")
    cur = db.get_originality(sid)
    if cur and cur["status"] in ("pending", "done"):
        return {"status": cur["status"]}
    db.set_originality_status(sid, "pending")
    threading.Thread(target=_run_originality_axis, args=(sid,), daemon=True).start()
    return {"status": "pending"}


@app.get("/api/sessions/{sid}/originality")
def poll_originality(sid: str):
    o = db.get_originality(sid)
    if o is None:
        raise HTTPException(404, "세션이 없습니다.")
    payload = {"status": o["status"]}
    if o["result"]:
        payload["axis_b"] = _originality_payload(o["result"])
    return payload


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
