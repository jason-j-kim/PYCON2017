#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가상 문답 4건을 기록에 넣는다. 6_샘플.bat 이 부르는 본체.

네 사분면을 한 화면에서 보기 위한 것이다. 좋은 아이디어와 나쁜 아이디어
둘로만 보면 이 시스템이 하려는 일이 안 보인다 — 갈라야 할 것은
'새롭지만 못 버티는 것'과 '낡았지만 잘 버티는 것'이다.

  계열 밖 시도 · 방어 높음   추진
  계열 밖 시도 · 방어 낮음   보완 후 재문답
  선례 명확   · 방어 높음   기존 사업 개선으로 재포지셔닝
  선례 명확   · 방어 낮음   보류

넣는 것은 전부 지어낸 문답이다. 연구 자료와 섞이면 안 되므로 아이디어
앞에 [샘플] 을 붙이고, 언제든 그것만 골라 지울 수 있게 했다.

사용:  6_샘플.bat  를 더블클릭
       python webapp\\load_samples.py            넣기
       python webapp\\load_samples.py --remove   샘플만 지우기
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = HERE / "sessions.db"
MARK = "[샘플]"          # 이 표시로 연구 자료와 갈린다

sys.path.insert(0, str(ROOT))
from samples.dialogues import SAMPLES, turns_of            # noqa: E402
from socratic import engine                                # noqa: E402

WEIGHTS = {"originality": 0.35, "practicality": 0.35, "acceptance": 0.30}
SRC_BIT = {"fiscal": "exec", "prism": "review", "bill": "law", "overseas": "intl"}


def say(*a):
    print(*a, flush=True)


def hold():
    if os.name != "nt" or not sys.stdin.isatty():
        return
    try:
        input("\n  Enter 를 누르면 닫힙니다. ")
    except Exception:
        pass


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


# ── 채점 결과를 엔진이 내는 '날것' 모양 그대로 만든다 ────────────────────
def build_evaluation(d):
    labels = engine.checklist_labels("정책")
    criteria = {}
    for cname in engine.CRITERIA:
        ids = list(labels[cname].keys())
        met = d["checklist"][cname]
        items = {}
        for iid, m in zip(ids, met):
            items[iid] = {
                "met": bool(m),
                "evidence": ("문답에서 해당 진술이 확인됨" if m
                             else "문답에서 확인되지 않음"),
            }
        total = sum(1 for v in items.values() if v["met"])
        score, rationale = d["holistic"][cname]
        criteria[cname] = {
            "checklist": {"items": items, "total": total},
            "holistic": {"score": score, "rationale": rationale},
            "final": engine._combine(total, score),
            "divergent": abs(total - score) >= engine.DIVERGENCE_LIMIT,
        }
    return {
        "version": 2,
        "criteria": criteria,
        "strengths": d["strengths"],
        "suggestions": d["suggestions"],
        "encouragement": d["encouragement"],
    }


def build_axis_b(d):
    """축 B 도 저장 모양(spec/judge/lookup/originality)으로 맞춘다."""
    b = d["axis_b"]
    cov, q = b["coverage"], b["queries"]
    hits, failed, profile = {}, {}, {}
    for src in ("fiscal", "prism", "bill", "overseas"):
        v = cov.get(src)
        bit = SRC_BIT[src]
        if v == "미실행":
            hits[src], profile[bit] = [], None      # null = 조회기가 안 돎
        elif v == "조회 실패":
            hits[src], failed[src], profile[bit] = [], True, 0
        else:
            hits[src] = [{"title": f"조회 결과 {i + 1}"} for i in range(int(v))]
            profile[bit] = 1 if v else 0
    return {
        "spec": {"policy_type": b["policy_type"], "claimed_precedents": [], "queries": q},
        "judge": {"verdict": b["band"]},
        "lookup": {"profile": profile, "queries": q, "failed": failed,
                   "fiscal": hits["fiscal"], "prism": hits["prism"],
                   "bill": hits["bill"], "overseas": hits["overseas"]},
        "originality": {
            "band": b["band"], "confidence": b["confidence"],
            "reasoning": b["reasoning"], "retraction_condition": "",
            "evidence": [{"grade": g, "source": s, "text": t} for g, s, t in b["evidence"]],
        },
    }


# ── 넣기 · 지우기 ──────────────────────────────────────────────────────
def remove():
    with conn() as c:
        ids = [r["id"] for r in c.execute(
            "SELECT id FROM sessions WHERE idea LIKE ?", (MARK + "%",))]
        for sid in ids:
            c.execute("DELETE FROM turns WHERE session_id = ?", (sid,))
            c.execute("DELETE FROM evaluations WHERE session_id = ?", (sid,))
            c.execute("DELETE FROM sessions WHERE id = ?", (sid,))
    return len(ids)


def install():
    import uuid
    from datetime import datetime, timedelta
    base = datetime.now()
    made = []
    with conn() as c:
        for n, d in enumerate(SAMPLES):
            sid = "sample" + uuid.uuid4().hex[:6]
            # 목록에서 ①②③④ 순으로 보이도록 시각을 벌려 둔다.
            when = (base - timedelta(minutes=len(SAMPLES) - n)).isoformat(timespec="minutes")
            ev = build_evaluation(d)
            total = round(engine.weighted_total(ev, WEIGHTS), 2)
            ab = build_axis_b(d)
            c.execute(
                "INSERT INTO sessions (id, idea, weights, stage_index, q_in_stage, "
                "status, profile, originality, originality_status, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sid, f"{MARK} {d['idea']}", json.dumps(WEIGHTS), len(engine.STAGES), 0,
                 "graded", "정책", json.dumps(ab, ensure_ascii=False), "done", when))
            for seq, role, stage, content in turns_of(d):
                c.execute("INSERT INTO turns (session_id, seq, role, stage, content) "
                          "VALUES (?,?,?,?,?)", (sid, seq, role, stage, content))
            c.execute("INSERT INTO evaluations (session_id, result, weighted_total) "
                      "VALUES (?,?,?)", (sid, json.dumps(ev, ensure_ascii=False), total))
            made.append((d, sid, total))
    return made


def cell(total, band):
    """판정 화면의 네 칸 — 화면과 같은 규칙으로 계산한다."""
    hi_def, hi_org = total >= 6, band == "계열 밖 시도"
    return ("추진" if (hi_def and hi_org) else
            "기존 사업 개선으로 재포지셔닝" if hi_def else
            "보완 후 재문답" if hi_org else "보류")


def main():
    if not DB.exists():
        say(f"\n  기록 파일이 없습니다: {DB}")
        say("  2_실행.bat 을 한 번 켜서 만든 뒤 다시 실행하세요.\n")
        return 1

    say()
    say("=" * 64)
    say("  네 사분면 가상 문답 넣기")
    say("=" * 64)

    if "--remove" in sys.argv:
        n = remove()
        say(f"\n  샘플 {n}건을 지웠습니다. 연구 자료는 건드리지 않았습니다.\n")
        return 0

    gone = remove()                    # 두 번 눌러도 쌓이지 않게
    if gone:
        say(f"\n  이전 샘플 {gone}건을 먼저 지웠습니다.")

    made = install()
    say()
    for d, sid, total in made:
        got = cell(total, d["axis_b"]["band"])
        ok = "✓" if got == d["quadrant"] else "✗"
        say(f"  {ok} {d['key']:<12} 총점 {total:>4} · {d['axis_b']['band']:<8} → {got}")
        if got != d["quadrant"]:
            say(f"      의도한 칸은 '{d['quadrant']}' 였습니다 — 설계가 어긋났습니다.")
    say()
    say(f"  {len(made)}건을 넣었습니다. 25턴짜리 문답이 각각 들어 있습니다.")
    say()
    say("  보는 곳:  http://localhost:8000/records")
    say("  지울 때:  python webapp\\load_samples.py --remove")
    say()
    say("  ※ 전부 지어낸 문답입니다. 아이디어 앞에 [샘플] 이 붙어 있어")
    say("    실제 실험 자료와 구분됩니다.")
    say("=" * 64)
    say()
    return 0


if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    except Exception as e:
        import traceback
        say("\n  넣지 못했습니다 — " + repr(e))
        say(traceback.format_exc())
    finally:
        hold()
    sys.exit(rc)
