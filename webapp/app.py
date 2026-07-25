"""소크라테스 아이디어 평가 — 웹 MVP (FastAPI).

실행 (저장소 루트에서):
    pip install fastapi "uvicorn[standard]"
    claude /login                      # 최초 1회, Pro 구독 로그인 (API 키 불필요)
    python webapp/app.py               # http://localhost:8000
    # 또는: uvicorn webapp.app:app --port 8000
"""

import json
import os
import sys
import threading
import urllib.parse
import urllib.request
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
# 선례 조사 축(축 B) — 정부 데이터 API 키. 없으면 조회를 건너뛰고 판정 보류.
FISCAL_KEY = os.environ.get("FISCAL_KEY", "").strip()          # 열린재정
DATA_GO_KR_KEY = os.environ.get("DATA_GO_KR_KEY", "").strip()  # 공공데이터포털(PRISM)


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
# 정부 데이터 API 초안 파서. 필드명은 실제 응답을 받아 확정해야 한다(열린재정·
# PRISM 모두 문서 필드명과 실제 응답이 다른 경우가 흔함). 키가 없거나 오류면
# []를 반환해 세션이 '판정 보류'로 끝까지 돌게 한다. 엔드포인트는 환경변수로
# 덮어쓸 수 있어, 실응답 확인 후 코드 수정 없이 교정 가능하다.
FISCAL_BASE = os.environ.get(
    "FISCAL_BASE", "https://openapi.openfiscaldata.go.kr/ExpenditureBudgetFinExpenditure")
PRISM_BASE = os.environ.get(
    "PRISM_BASE", "https://apis.data.go.kr/1741000/PolicyRech/getPolicyRechList")
_TIMEOUT = 8


def _http_get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


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


def _fiscal_lookup(query):
    """열린재정 세출예산 세부사업 검색. → [{name, ministry, series:[{year,amount}]}]"""
    if not FISCAL_KEY:
        return []
    try:
        params = {"Key": FISCAL_KEY, "Type": "json", "pIndex": 1, "pSize": 30,
                  "OFFC_NM": query}
        rows = _find_rows(_http_get_json(FISCAL_BASE + "?" + urllib.parse.urlencode(params)))
        grouped = {}
        for r in rows:
            name = _pick(r, "FSCL_NM", "BZ_CLS_NM", "DETAIL_BZ_NM", "OFFC_NM", "사업명")
            if not name:
                continue
            year = _pick(r, "FSCL_YY", "회계연도", "YEAR")
            amount = _pick(r, "Y_PRESENT_AMT", "예산현액", "BUDGET_AMT", "예산액")
            ministry = _pick(r, "DEPT_NM", "소관부처", "MINISTRY")
            g = grouped.setdefault(name, {"name": name, "ministry": ministry, "series": []})
            if year is not None:
                try:
                    g["series"].append({"year": int(year),
                                        "amount": int(float(amount)) if amount else 0})
                except (ValueError, TypeError):
                    pass
        for g in grouped.values():
            g["series"].sort(key=lambda s: s["year"])
        return list(grouped.values())[:5]
    except Exception as e:
        print("fiscal lookup 실패:", e, file=sys.stderr)
        return []


def _prism_lookup(query):
    """PRISM 정책연구 과제 검색. → [{title, org, period}]"""
    if not DATA_GO_KR_KEY:
        return []
    try:
        params = {"serviceKey": DATA_GO_KR_KEY, "type": "json", "numOfRows": 10,
                  "pageNo": 1, "searchword": query}
        rows = _find_rows(_http_get_json(PRISM_BASE + "?" + urllib.parse.urlencode(params)))
        out = []
        for r in rows:
            title = _pick(r, "bizTitle", "과제명", "title", "researchTitle")
            if not title:
                continue
            out.append({
                "title": title,
                "org": _pick(r, "reschOrgn", "수행기관", "org", "orgName"),
                "period": _pick(r, "reschPd", "연구기간", "period"),
            })
        return out[:5]
    except Exception as e:
        print("prism lookup 실패:", e, file=sys.stderr)
        return []


class LookupRequest(BaseModel):
    query: str
    years: list | None = None


@app.post("/api/fiscal")
def api_fiscal(req: LookupRequest):
    return {"hits": _fiscal_lookup(req.query.strip())}


@app.post("/api/prism")
def api_prism(req: LookupRequest):
    return {"hits": _prism_lookup(req.query.strip())}


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
            "quadrant": lookup["quadrant"], "queries": lookup["queries"],
            "fiscal": lookup["fiscal"], "prism": lookup["prism"],
        },
    }


def _run_originality_axis(sid):
    """백그라운드 스레드: 축 B를 돌려 결과를 DB에 저장한다.
    call_claude가 블로킹이므로 asyncio 대신 스레드로 격리한다."""
    try:
        transcript = "\n\n".join(_transcript_log(sid))
        fiscal_fn = _fiscal_lookup if FISCAL_KEY else None
        prism_fn = _prism_lookup if DATA_GO_KR_KEY else None
        result = engine.originality_axis(transcript, fiscal_fn, prism_fn)
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
