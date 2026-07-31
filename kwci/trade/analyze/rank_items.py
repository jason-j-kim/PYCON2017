#!/usr/bin/env python3
"""
KWCI L1 — 도메인별 대표 품목 선정 (A단계 결과 정리)

item_totals.csv 를 읽어 도메인별 수출액 순위를 내고, 상위 N개를 B단계
(국가별 상세 · 2018 대비 성장 · RCA) 대상으로 확정한다.

API 호출 없음. 즉시 끝난다.

사용법
------
  python rank_items.py             # 도메인별 상위 15개 요약
  python rank_items.py --top 20    # 상위 N 지정
  python rank_items.py --domain K-Food --all   # 한 도메인 전체
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRADE = HERE.parent
SRC = TRADE / "data" / "processed" / "item_totals.csv"
OUT = TRADE / "data" / "processed" / "top_items.csv"

# 단위 점검용 기준값. 2024년 라면(HS 1902.30) 수출은 공표 기준 약 12억 달러다.
# 우리 합계가 이 자릿수와 맞는지로 expDlr 의 단위(달러 / 천달러)를 판별한다.
CALIB_HS = "190230"
CALIB_USD = 1.2e9

# 도메인마다 집중도가 달라 상위 N을 따로 잡는다.
# 첫 산출 기준 상위 15개의 도메인 총액 설명력: K-Beauty 99.8%, K-Food 64.3%,
# K-Fashion 60.5%. 뒤 둘은 분산이 커서 30개로 늘려야 대표성이 확보된다.
TOP_N = {"K-Beauty": 15, "K-Food": 30, "K-Fashion": 30}
TOP_DEFAULT = 15


def load() -> list[dict]:
    if not SRC.exists():
        raise SystemExit(f"{SRC} 이 없습니다. collect_customs.py 를 먼저 돌리세요.")
    with SRC.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["exp_usd"] = float(r["exp_usd"] or 0)
        r["exp_kg"] = float(r["exp_kg"] or 0)
    return rows


def money(v: float, unit: float) -> str:
    u = v * unit
    if u >= 1e8:
        return f"{u/1e8:>8,.0f}억$"
    return f"{u/1e4:>8,.0f}만$"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int,
                    help=f"모든 도메인에 같은 N 적용 (기본은 도메인별: {TOP_N})")
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true", help="상위 N 대신 전체 출력")
    args = ap.parse_args()

    rows = load()
    year = sorted({r["year"] for r in rows})[-1]
    rows = [r for r in rows if r["year"] == year]

    # 단위 판별 — 관세청 expDlr 는 오퍼레이션에 따라 달러/천달러가 갈린다.
    cal = next((r["exp_usd"] for r in rows if r["hs2022"] == CALIB_HS), None)
    unit, unit_label = 1.0, "달러"
    if cal:
        if cal * 1000 / CALIB_USD > 0.3 and cal / CALIB_USD < 0.3:
            unit, unit_label = 1000.0, "천달러"
        print(f"[단위 점검] {CALIB_HS}(라면) {year} 합계 = {cal:,.0f}")
        print(f"  공표 기준 약 12억 달러와 대조 -> expDlr 단위는 '{unit_label}'"
              f"  (환산 {cal*unit/1e8:,.1f}억 달러)\n")

    doms = sorted({r["domain"] for r in rows})
    if args.domain:
        doms = [d for d in doms if d.lower() == args.domain.lower()] or doms

    picked: list[dict] = []
    print(f"{year}년 수출 실적 — 도메인별\n")
    for d in doms:
        sel = sorted((r for r in rows if r["domain"] == d),
                     key=lambda r: -r["exp_usd"])
        tot_usd = sum(r["exp_usd"] for r in sel)
        tot_kg = sum(r["exp_kg"] for r in sel)
        live = sum(1 for r in sel if r["exp_usd"] > 0)
        print(f"■ {d}   총액 {money(tot_usd, unit)}   "
              f"총량 {tot_kg/1e6:,.0f}천톤   품목 {live}/{len(sel)}")

        n = len(sel) if args.all else (args.top or TOP_N.get(d, TOP_DEFAULT))
        cum = 0.0
        for i, r in enumerate(sel[:n], 1):
            cum += r["exp_usd"]
            share = r["exp_usd"] / tot_usd * 100 if tot_usd else 0
            uv = f"{r['exp_usd']*unit/r['exp_kg']:,.1f}" if r["exp_kg"] else "-"
            print(f"   {i:>2} {r['hs2022']}  {money(r['exp_usd'], unit)} "
                  f"{share:>5.1f}%  누적{cum/tot_usd*100 if tot_usd else 0:>5.1f}%  "
                  f"단가{uv:>9}$/kg  {r['name'][:42]}")
            picked.append({**r, "rank": i, "share_pct": round(share, 2)})
        # 상위 N이 도메인을 얼마나 대표하는지 — 낮으면 N을 늘려야 한다.
        top_share = cum / tot_usd * 100 if tot_usd else 0
        print(f"   상위 {min(n, len(sel))}개가 도메인 총액의 {top_share:.1f}% 설명\n")

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "rank", "hs2022", "name",
                                          "year", "exp_usd", "exp_kg",
                                          "unit_value", "share_pct"])
        w.writeheader()
        for r in picked:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    print(f"= {OUT.name}  {len(picked)}개  (B단계 대상)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
