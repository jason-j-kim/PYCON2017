#!/usr/bin/env python3
"""저장된 세션을 여러 번 재채점해 점수 재현성(분산)을 측정한다.

같은 대화 전문을 N회 채점하면 체크리스트·종합판단 점수가 얼마나 흔들리는지
보여준다. 분산이 작을수록 채점이 안정적(재현 가능)이라는 뜻이다.

추가 설치 없음 — 표준 라이브러리 + 프로젝트 엔진만 사용한다. 채점은 Claude
Code CLI(Pro/Max 구독)로 이뤄지므로 로그인된 PC에서 실행한다.

사용법 (저장소 루트에서):
    python simulation/regrade.py <세션ID앞부분> --runs 3
    python simulation/regrade.py e0975d2b4157            # 기본 3회
"""

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "webapp"))

from socratic import engine
try:
    from webapp import db
except ImportError:
    import db


def format_turn(t):
    if t["role"] == "questioner":
        return f"[턴 {t['seq']}] 질문자({t['stage']}): {t['content']}"
    return f"[턴 {t['seq']}] 제안자: {t['content']}"


def resolve_session(prefix):
    """ID 앞부분으로 세션 하나를 찾는다."""
    import sqlite3
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM sessions WHERE id LIKE ? ORDER BY created_at DESC",
            (prefix + "%",),
        ).fetchall()
    if not rows:
        sys.exit(f"세션을 찾지 못함: {prefix}")
    if len(rows) > 1:
        print(f"경고: {len(rows)}개 일치 — 첫 번째 사용: {rows[0]['id']}")
    return dict(rows[0])


def stats_line(name, values):
    lo, hi = min(values), max(values)
    sd = statistics.pstdev(values) if len(values) > 1 else 0.0
    vals = " ".join(f"{v:>4.1f}" for v in values)
    return (f"  {name:<10} | {vals} | 평균 {statistics.mean(values):>4.1f} "
            f"| 범위 {lo:.1f}~{hi:.1f} (폭 {hi-lo:.1f}) | 표준편차 {sd:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session", help="세션 ID 또는 앞부분")
    ap.add_argument("--runs", type=int, default=3, help="재채점 횟수 (기본 3)")
    ap.add_argument("--text", action="store_true",
                    help="근거 문장까지 회차별 동일 여부 비교 (결정론 vs 안정판단 구분)")
    args = ap.parse_args()

    import json
    session = resolve_session(args.session)
    sid = session["id"]
    profile = session.get("profile", "원본")
    weights = json.loads(session["weights"])
    transcript = "\n\n".join(format_turn(t) for t in db.get_turns(sid))

    print(f"세션 {sid} · 프로필 {profile} · {args.runs}회 재채점")
    print(f"아이디어: {session['idea'][:60]}")
    print("=" * 66)

    runs = []
    for i in range(args.runs):
        print(f"[{i+1}/{args.runs}] 채점 중… (체크리스트 + 종합판단)", flush=True)
        result = engine.grade(transcript, profile)
        total = engine.weighted_total(result, weights)
        row = {"total": round(total, 2), "text": {}}
        for c in engine.CRITERIA:
            d = result["criteria"][c]
            row[c] = {
                "checklist": d["checklist"]["total"],
                "holistic": d["holistic"]["score"],
                "final": d["final"],
            }
            row["text"][c] = {
                "rationale": d["holistic"]["rationale"],
                "evidence": json.dumps(
                    {i: it["evidence"] for i, it in d["checklist"]["items"].items()},
                    ensure_ascii=False, sort_keys=True),
            }
        runs.append(row)

    print("\n" + "=" * 66)
    print("재현성 결과 (같은 대화를 여러 번 채점)")
    print("=" * 66)
    labels = {"originality": "독창성", "practicality": "실용성", "acceptance": "수용태도"}
    for c in engine.CRITERIA:
        print(f"\n[{labels[c]}]")
        print(stats_line("체크리스트", [r[c]["checklist"] for r in runs]))
        print(stats_line("종합판단", [r[c]["holistic"] for r in runs]))
        print(stats_line("최종(평균)", [r[c]["final"] for r in runs]))
    print("\n[종합 점수]")
    print(stats_line("가중종합", [r["total"] for r in runs]))

    if args.text and len(runs) > 1:
        print("\n" + "=" * 66)
        print("텍스트 재현성 — 근거 문장이 회차마다 같은가")
        print("=" * 66)
        all_identical = True
        for c in engine.CRITERIA:
            rats = [r["text"][c]["rationale"] for r in runs]
            evs = [r["text"][c]["evidence"] for r in runs]
            r_same = len(set(rats)) == 1
            e_same = len(set(evs)) == 1
            all_identical = all_identical and r_same and e_same
            print(f"\n[{labels[c]}] 종합판단 근거: {'동일' if r_same else '다름'} "
                  f"· 체크리스트 근거: {'동일' if e_same else '다름'}")
            if not r_same:
                for i, txt in enumerate(rats):
                    print(f"  ({i+1}회) {txt[:200]}")
        print("\n" + "-" * 66)
        if all_identical:
            print("판정: 모든 근거 문장이 회차마다 완전히 동일 → **완전 결정론**")
            print("      (모델이 같은 입력에 같은 출력을 그대로 재생. 채점 자체의")
            print("       강건성은 이 테스트로 알 수 없음 → 표현 불변성 테스트 필요.)")
        else:
            print("판정: 점수는 같지만 근거 문장은 회차마다 다름 → **안정 판단 + 표현 변주**")
            print("      (표현은 자연스럽게 흔들려도 숫자 판단은 일관됨. 더 이상적인 신호.)")

    spreads = [max(r[c]["final"] for r in runs) - min(r[c]["final"] for r in runs)
               for c in engine.CRITERIA]
    total_spread = max(r["total"] for r in runs) - min(r["total"] for r in runs)
    print("\n" + "-" * 66)
    print(f"해석: 기준별 최종점수 변동폭 최대 {max(spreads):.1f}점, "
          f"종합 변동폭 {total_spread:.1f}점.")
    print("      변동폭 0~0.5 = 매우 안정 · 0.5~1.5 = 안정 · 1.5+ = 분산 큼(루브릭 정교화 필요).")


if __name__ == "__main__":
    main()
