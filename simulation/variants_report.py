#!/usr/bin/env python3
"""질문자 지침 3안 비교 리포트 (simulation/VARIANTS_REPORT.md).

지표: 판별력(진부/창의 격차), 자기 인식 유도(O9·P9·A9), 회피 개입,
인정 횟수, 선택지형 질문, 도구 커버리지, 어조.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from socratic import engine
from simulation.run_variants import VARIANTS, FIXED_IDEAS

RESULTS_DIR = Path(__file__).parent / "results_variants"
SELF_ITEMS = ["O9", "P9", "A9"]  # 자기 인식 관련 체크리스트 항목


def load(vkey, label):
    p = RESULTS_DIR / f"{vkey}_{label}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def self_awareness_met(rec):
    n = 0
    for c, item in zip(engine.CRITERIA, SELF_ITEMS):
        if rec["evaluation"]["criteria"][c]["checklist"]["items"][item]["met"]:
            n += 1
    return n


def main():
    lines = ["# 질문자 지침 3안 비교 시뮬레이션 리포트", ""]
    lines.append("조건 통제: 세 안 모두 **같은 아이디어**(진부: 회의실 예약 프로그램 / "
                 "창의: 약국 간 재고 교환 플랫폼)와 **같은 제안자 페르소나**로 12문답 완주. "
                 "질문자 지침만 다르다.")
    lines.append("")

    rows = []
    for vkey, (vname, _) in VARIANTS.items():
        b, c = load(vkey, "banal"), load(vkey, "creative")
        if not (b and c):
            lines.append(f"⚠ {vkey} 결과 불완전 — 건너뜀")
            continue
        rows.append({
            "vkey": vkey, "vname": vname, "b": b, "c": c,
            "gap": round(c["weighted_total"] - b["weighted_total"], 2),
            "self_aw": self_awareness_met(b) + self_awareness_met(c),
            "evasion": b["analysis"]["evasion_callouts"] + c["analysis"]["evasion_callouts"],
            "ack": b["analysis"]["acknowledgments"] + c["analysis"]["acknowledgments"],
            "choice": b["analysis"]["choice_format_questions"] + c["analysis"]["choice_format_questions"],
            "tools": len(set(b["analysis"]["tools_used"]) | set(c["analysis"]["tools_used"])),
        })

    lines.append("## 종합 지표")
    lines.append("")
    lines.append("| 지표 | " + " | ".join(f"{r['vkey']} {r['vname']}" for r in rows) + " |")
    lines.append("|---|" + "---|" * len(rows))
    metric_rows = [
        ("진부 세션 종합점수", lambda r: r["b"]["weighted_total"]),
        ("창의 세션 종합점수", lambda r: r["c"]["weighted_total"]),
        ("**판별력 (격차)**", lambda r: f"**{r['gap']:+.2f}**"),
        ("자기 인식 유도 (O9·P9·A9 충족, /6)", lambda r: r["self_aw"]),
        ("회피 명시 지적 (2세션 합)", lambda r: r["evasion"]),
        ("인정 횟수 (2세션 합, 24문항 중)", lambda r: r["ack"]),
        ("선택지형 질문", lambda r: r["choice"]),
        ("질문 도구 사용 종수 (/6)", lambda r: r["tools"]),
    ]
    for name, fn in metric_rows:
        lines.append(f"| {name} | " + " | ".join(str(fn(r)) for r in rows) + " |")
    lines.append("")

    lines.append("## 기준별 점수 상세")
    lines.append("")
    lines.append("| 안 | 세션 | 독창성 | 실용성 | 수용태도 | 종합 |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        for label, rec in (("진부", r["b"]), ("창의", r["c"])):
            cells = []
            for c in engine.CRITERIA:
                d = rec["evaluation"]["criteria"][c]
                cells.append(f"{d['final']} ({d['checklist']['total']}·{d['holistic']['score']})")
            lines.append(f"| {r['vname']} | {label} | " + " | ".join(cells)
                         + f" | **{rec['weighted_total']}** |")
    lines.append("")
    lines.append("(괄호는 체크리스트·종합판단 점수)")
    lines.append("")

    lines.append("## 어조 (분석가 평가)")
    lines.append("")
    for r in rows:
        lines.append(f"- **{r['vname']}** · 진부 세션: {r['b']['analysis']['tone']} · "
                     f"창의 세션: {r['c']['analysis']['tone']}")
    lines.append("")

    lines.append("## 질문 사례 비교 (진부 세션의 독창성 라운드 첫 질문)")
    lines.append("")
    for r in rows:
        for line in r["b"]["transcript"]:
            if "질문자(독창성)" in line:
                lines.append(f"- **{r['vname']}**: {line.split(': ', 1)[1]}")
                break
    lines.append("")

    text = "\n".join(lines)
    out = Path(__file__).parent / "VARIANTS_REPORT.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
