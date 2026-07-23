#!/usr/bin/env python3
"""저장된 평가 세션의 문답 전체와 평가 결과를 출력한다.

사용법 (저장소 루트에서):
    python webapp/show_session.py            # 가장 최근 세션의 전체 문답 + 평가
    python webapp/show_session.py --list        # 저장된 세션 목록(점수 포함)
    python webapp/show_session.py --list score  # 점수 낮은 순 정렬
    python webapp/show_session.py <세션ID>      # 특정 세션

화면 출력과 동시에 transcript_<세션ID>.txt 파일(UTF-8)로도 저장한다.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "sessions.db"

CRITERIA_KO = {"originality": "독창성", "practicality": "실용성", "acceptance": "수용태도"}


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def list_sessions(c, by_score=False):
    rows = [dict(r) for r in c.execute(
        "SELECT s.id, s.idea, s.status, s.created_at, e.weighted_total AS score "
        "FROM sessions s LEFT JOIN evaluations e ON e.session_id = s.id"
    ).fetchall()]
    if not rows:
        print("저장된 세션이 없습니다.")
        return
    if by_score:
        graded = sorted((r for r in rows if r["score"] is not None), key=lambda r: r["score"])
        ungraded = [r for r in rows if r["score"] is None]
        rows = graded + ungraded
        print("(점수 낮은 순 — 채점 안 된 세션은 맨 아래)\n")
    else:
        rows.sort(key=lambda r: r["created_at"], reverse=True)
    for r in rows:
        idea = r["idea"][:38] + ("…" if len(r["idea"]) > 38 else "")
        score = f"{r['score']:>5.2f}" if r["score"] is not None else "  –  "
        print(f"{r['id']}  [{r['status']:>6}]  점수 {score}  {r['created_at'][:19]}  {idea}")


def render(c, sid):
    session = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if not session:
        sys.exit(f"세션을 찾을 수 없습니다: {sid}")
    turns = c.execute(
        "SELECT seq, role, stage, content FROM turns WHERE session_id = ? ORDER BY seq",
        (sid,),
    ).fetchall()

    lines = []
    lines.append("=" * 64)
    lines.append(f"세션 {sid} · {session['created_at'][:19]} · 상태: {session['status']}")
    lines.append(f"아이디어: {session['idea']}")
    lines.append("=" * 64)
    for t in turns:
        who = f"질문자({t['stage']})" if t["role"] == "questioner" else "제안자"
        lines.append(f"\n[턴 {t['seq']}] {who}")
        lines.append(t["content"])

    ev = c.execute(
        "SELECT result, weighted_total FROM evaluations WHERE session_id = ?", (sid,)
    ).fetchone()
    if ev:
        result = json.loads(ev["result"])
        weights = json.loads(session["weights"])
        lines.append("\n" + "=" * 64)
        lines.append(f"평가 결과 · 종합 {ev['weighted_total']}/10")
        lines.append("=" * 64)
        for key, label in CRITERIA_KO.items():
            if result.get("version") == 2:
                d = result["criteria"][key]
                lines.append(f"\n[{label}] {d['final']}/10 (가중치 {weights[key]})")
                lines.append(f"  체크리스트 {d['checklist']['total']}/10 · "
                             f"종합판단 {d['holistic']['score']}/10 → 평균 {d['final']}")
                lines.append(f"  종합판단 근거: {d['holistic']['rationale']}")
                for item_id, entry in d["checklist"]["items"].items():
                    mark = "O" if entry["met"] else "X"
                    lines.append(f"  [{mark}] {item_id} — {entry['evidence']}")
            else:  # 구버전(하위지표 척도) 세션 호환
                d = result[key]
                total = d["specificity"] + d["consistency"] + d["self_awareness"]
                lines.append(f"\n[{label}] {total}/10 (가중치 {weights[key]})")
                lines.append(f"  구체성 {d['specificity']}/4 · 일관성 {d['consistency']}/3 · "
                             f"자기 인식 {d['self_awareness']}/3")
                for e in d["evidence"]:
                    lines.append(f"  - {e}")
        lines.append("\n[강점]")
        lines.extend(f"  - {s}" for s in result["strengths"])
        lines.append("\n[개선 제안]")
        lines.extend(f"  - {s}" for s in result["suggestions"])
        lines.append(f"\n[격려]\n  {result['encouragement']}")

    text = "\n".join(lines)
    # 한국어 Windows 콘솔(cp949)에서 표현 불가 문자가 있어도 죽지 않게 출력
    print(text.encode(sys.stdout.encoding or "utf-8", errors="replace")
              .decode(sys.stdout.encoding or "utf-8", errors="replace"))

    out_dir = Path(__file__).resolve().parent.parent / "transcripts"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"transcript_{sid}.txt"
    out.write_text(text, encoding="utf-8")
    print(f"\n(전문을 {out} 파일로도 저장했습니다 — 메모장에서 열어보세요)")


def main():
    if not DB_PATH.exists():
        sys.exit("세션 DB가 없습니다. 웹 앱으로 세션을 먼저 진행하세요.")
    c = conn()
    args = sys.argv[1:]
    if args and args[0] == "--list":
        by_score = len(args) > 1 and args[1] in ("score", "low", "--low")
        list_sessions(c, by_score)
        return
    if args:
        render(c, args[0])
        return
    row = c.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1").fetchone()
    if not row:
        sys.exit("저장된 세션이 없습니다.")
    render(c, row["id"])


if __name__ == "__main__":
    main()
