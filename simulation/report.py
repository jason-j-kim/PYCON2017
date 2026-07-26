#!/usr/bin/env python3
"""시뮬레이션 결과 집계 → 안정성 리포트 (simulation/REPORT.md).

측정 지표:
1. 판별력 — 창의 그룹이 진부 그룹보다 일관되게 높은 점수를 받는가
   (그룹 평균 차이, 분포 겹침 여부)
2. 안정성 — 그룹 내 점수 표준편차
3. 심사위원 간 일치도 — 체크리스트와 종합판단의 평균 절대 차이
"""

import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from socratic import engine

RESULTS_DIR = Path(__file__).parent / "results"


def load():
    records = []
    for p in sorted(RESULTS_DIR.glob("trial_*.json")):
        records.append(json.loads(p.read_text(encoding="utf-8")))
    if not records:
        sys.exit("결과가 없습니다. 먼저 run_simulation.py를 실행하세요.")
    return records


def fmt_stats(values):
    if len(values) < 2:
        return f"평균 {values[0]:.2f} (표본 1개)"
    return (f"평균 {st.mean(values):.2f} · 표준편차 {st.stdev(values):.2f} · "
            f"범위 {min(values):.1f}~{max(values):.1f}")


def main():
    records = load()
    groups = {"banal": [r for r in records if r["label"] == "banal"],
              "creative": [r for r in records if r["label"] == "creative"]}

    lines = ["# 5-에이전트 시뮬레이션 안정성 리포트", ""]
    lines.append(f"시행 수: 진부 {len(groups['banal'])} · 창의 {len(groups['creative'])} "
                 f"(총 {len(records)})")
    lines.append("")

    # 시행별 표
    lines.append("## 시행별 결과")
    lines.append("")
    lines.append("| # | 그룹 | 아이디어 | 독창성 | 실용성 | 수용태도 | 종합 |")
    lines.append("|---|------|----------|--------|--------|----------|------|")
    for r in records:
        cells = []
        for c in engine.CRITERIA:
            d = r["evaluation"]["criteria"][c]
            cells.append(f"{d['final']} (체크 {d['checklist']['total']}·종합 {d['holistic']['score']})")
        idea = r["idea"].replace("|", "/")[:45]
        lines.append(f"| {r['trial']} | {'진부' if r['label']=='banal' else '창의'} | "
                     f"{idea}… | {cells[0]} | {cells[1]} | {cells[2]} | "
                     f"**{r['weighted_total']}** |")
    lines.append("")

    # 1. 판별력
    banal_totals = [r["weighted_total"] for r in groups["banal"]]
    creative_totals = [r["weighted_total"] for r in groups["creative"]]
    lines.append("## 1. 판별력 (창의 > 진부 인가)")
    lines.append("")
    lines.append(f"- 진부 그룹 종합: {fmt_stats(banal_totals)}")
    lines.append(f"- 창의 그룹 종합: {fmt_stats(creative_totals)}")
    if banal_totals and creative_totals:
        gap = st.mean(creative_totals) - st.mean(banal_totals)
        overlap = max(banal_totals) >= min(creative_totals)
        lines.append(f"- 그룹 평균 격차: **{gap:+.2f}점**")
        lines.append(f"- 분포 겹침: {'있음 ⚠ (진부 최고 ' + str(max(banal_totals)) + ' ≥ 창의 최저 ' + str(min(creative_totals)) + ')' if overlap else '없음 ✓ (완전 분리)'}")
    lines.append("")

    # 2. 안정성 (그룹 내 분산)
    lines.append("## 2. 안정성 (그룹 내 흔들림)")
    lines.append("")
    for c in engine.CRITERIA:
        for label, name in (("banal", "진부"), ("creative", "창의")):
            vals = [r["evaluation"]["criteria"][c]["final"] for r in groups[label]]
            if vals:
                lines.append(f"- {engine.CRITERIA_KO[c]} · {name}: {fmt_stats(vals)}")
    lines.append("")

    # 3. 심사위원 간 일치도
    lines.append("## 3. 심사위원 간 일치도 (체크리스트 vs 종합판단)")
    lines.append("")
    all_diffs = []
    for c in engine.CRITERIA:
        diffs = [abs(r["evaluation"]["criteria"][c]["checklist"]["total"]
                     - r["evaluation"]["criteria"][c]["holistic"]["score"])
                 for r in records]
        all_diffs.extend(diffs)
        lines.append(f"- {engine.CRITERIA_KO[c]}: 평균 절대 차이 {st.mean(diffs):.2f}점 "
                     f"(최대 {max(diffs)}점)")
    lines.append(f"- **전체 평균 절대 차이: {st.mean(all_diffs):.2f}점** "
                 f"(3점 이상 괴리: {sum(1 for d in all_diffs if d >= 3)}/{len(all_diffs)}건)")
    lines.append("")

    # 재판장 판정문 발췌
    lines.append("## 재판장 판정문 발췌")
    lines.append("")
    for r in records:
        lines.append(f"**시행 {r['trial']} ({'진부' if r['label']=='banal' else '창의'}, "
                     f"종합 {r['weighted_total']})** — {r['synthesis']['verdict']}")
        lines.append("")

    text = "\n".join(lines)
    out = Path(__file__).parent / "REPORT.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n리포트 저장: {out}")


if __name__ == "__main__":
    main()
