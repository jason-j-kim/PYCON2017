#!/usr/bin/env python3
"""
KWCI L1 — 최종 통합: 수집 결과를 지수 투입 포맷으로

panel.csv(국가x품목x연도) 와 rca.csv 를 묶어 세 갈래 산출을 만든다.
브리핑 통찰 ①의 "두 개의 자"를 파일 수준에서 분리한다.

  l1_cross.csv        횡단  국가 x 도메인 x 연도 — 어느 국가가 강한가
  l1_series.csv       시계열 도메인 x 연도 (2018=100) — 얼마나 성장했나
  l1_diversity.csv    다변화 도메인 x 연도 HHI·ENM — 얼마나 튼튼한가

세 번째는 브리핑 통찰 ③(계란 바구니)을 관광에서 수출로 확장한 것이다.
    HHI = Σ(국가별 점유율)^2 ,  ENM = 1/HHI = 실질 시장 수

API 호출 없음.

사용법
------
  python build_l1.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent / "data" / "processed"
PANEL, RCA = P / "panel.csv", P / "rca.csv"
BASE_YEAR = "2018"


def read(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"{path.name} 이 없습니다. 수집을 먼저 끝내세요.")
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def f(v) -> float:
    try:
        return float(v or 0)
    except ValueError:
        return 0.0


def main() -> int:
    panel = read(PANEL)
    for r in panel:
        r["exp_usd"], r["exp_kg"] = f(r["exp_usd"]), f(r["exp_kg"])

    years = sorted({r["year"] for r in panel})
    doms = sorted({r["domain"] for r in panel})

    # --- 횡단: 국가 x 도메인 x 연도 -------------------------------------
    cross: dict[tuple, dict] = defaultdict(
        lambda: {"exp_usd": 0.0, "exp_kg": 0.0, "items": 0})
    for r in panel:
        k = (r["country"], r["country_name"], r["domain"], r["year"])
        c = cross[k]
        c["exp_usd"] += r["exp_usd"]
        c["exp_kg"] += r["exp_kg"]
        c["items"] += 1 if r["exp_usd"] > 0 else 0

    # 연도·도메인 총액 대비 국가 점유율
    dom_year = defaultdict(float)
    for (cc, cn, d, y), v in cross.items():
        dom_year[(d, y)] += v["exp_usd"]

    with (P / "l1_cross.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["country", "country_name", "domain", "year",
                    "exp_usd", "exp_kg", "unit_value",
                    "share_in_domain_pct", "items_with_export"])
        for (cc, cn, d, y), v in sorted(cross.items()):
            tot = dom_year[(d, y)]
            w.writerow([cc, cn, d, y, round(v["exp_usd"]), round(v["exp_kg"]),
                        round(v["exp_usd"] / v["exp_kg"], 4) if v["exp_kg"] else "",
                        round(v["exp_usd"] / tot * 100, 3) if tot else "",
                        v["items"]])

    # --- 시계열: 도메인 x 연도 (2018=100) --------------------------------
    with (P / "l1_series.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "year", "exp_usd", "exp_kg", "unit_value",
                    f"index_{BASE_YEAR}_100"])
        for d in doms:
            base = dom_year.get((d, BASE_YEAR), 0.0)
            for y in years:
                tot = dom_year.get((d, y), 0.0)
                kg = sum(v["exp_kg"] for (c1, c2, dd, yy), v in cross.items()
                         if dd == d and yy == y)
                w.writerow([d, y, round(tot), round(kg),
                            round(tot / kg, 4) if kg else "",
                            round(tot / base * 100, 1) if base else ""])

    # --- 다변화: HHI / ENM ------------------------------------------------
    # 총량이 커도 바구니가 하나면 취약하다 — 브리핑 통찰 ③.
    with (P / "l1_diversity.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "year", "hhi", "enm", "top1_country",
                    "top1_share_pct", f"enm_index_{BASE_YEAR}_100"])
        enm_base: dict[str, float] = {}
        for d in doms:
            for y in years:
                tot = dom_year.get((d, y), 0.0)
                if not tot:
                    continue
                sh = [(v["exp_usd"] / tot, cn)
                      for (cc, cn, dd, yy), v in cross.items()
                      if dd == d and yy == y and v["exp_usd"] > 0]
                if not sh:
                    continue
                hhi = sum(s * s for s, _ in sh)
                enm = 1 / hhi if hhi else 0
                if y == BASE_YEAR:
                    enm_base[d] = enm
                top_s, top_c = max(sh)
                w.writerow([d, y, round(hhi, 4), round(enm, 2), top_c,
                            round(top_s * 100, 1),
                            round(enm / enm_base[d] * 100, 1)
                            if enm_base.get(d) else ""])

    # --- 요약 출력 --------------------------------------------------------
    print(f"\n= l1_cross.csv      {len(cross):,}행  (국가 x 도메인 x 연도)")
    print(f"= l1_series.csv     {len(doms)*len(years):,}행  (2018=100)")
    print(f"= l1_diversity.csv  (HHI·ENM)\n")

    last = years[-1]
    print(f"[시계열] 도메인별 성장  {BASE_YEAR}=100 -> {last}")
    for d in doms:
        base, cur = dom_year.get((d, BASE_YEAR), 0), dom_year.get((d, last), 0)
        idx = cur / base * 100 if base else 0
        print(f"  {d:<10} {base/1e8:>7,.0f}억$ -> {cur/1e8:>7,.0f}억$   "
              f"지수 {idx:>6.1f}")

    print(f"\n[횡단] {last} 도메인별 상위 5개국")
    for d in doms:
        sel = sorted(((v["exp_usd"], cn) for (cc, cn, dd, yy), v in cross.items()
                      if dd == d and yy == last), reverse=True)[:5]
        tot = dom_year.get((d, last), 0)
        s = "  ".join(f"{cn} {u/tot*100:.0f}%" for u, cn in sel if tot)
        print(f"  {d:<10} {s}")

    print(f"\n[다변화] {last}  (ENM = 실질 시장 수, 클수록 튼튼)")
    for d in doms:
        tot = dom_year.get((d, last), 0.0)
        if not tot:
            continue
        sh = [v["exp_usd"] / tot for (cc, cn, dd, yy), v in cross.items()
              if dd == d and yy == last and v["exp_usd"] > 0]
        hhi = sum(s * s for s in sh)
        base_tot = dom_year.get((d, BASE_YEAR), 0.0)
        sh0 = [v["exp_usd"] / base_tot for (cc, cn, dd, yy), v in cross.items()
               if dd == d and yy == BASE_YEAR and v["exp_usd"] > 0] if base_tot else []
        hhi0 = sum(s * s for s in sh0)
        e, e0 = (1 / hhi if hhi else 0), (1 / hhi0 if hhi0 else 0)
        arrow = "개선" if e > e0 else ("악화" if e0 and e < e0 else "")
        print(f"  {d:<10} ENM {e:>5.2f}   {BASE_YEAR} {e0:>5.2f}  {arrow}")

    if RCA.exists():
        rca = read(RCA)
        per = max((r["period"] for r in rca), default="")
        sel = [r for r in rca if r["period"] == per]
        print(f"\n[S2] RCA >= 1 통과 ({per})")
        for d in sorted({r["domain"] for r in sel}):
            dd = [r for r in sel if r["domain"] == d]
            ok = [r for r in dd if f(r["rca"]) >= 1]
            print(f"  {d:<10} {len(ok):>2}/{len(dd):<3}")
    else:
        print("\n  (rca.csv 없음 — compute_rca.py 를 돌리면 S2 통과율이 함께 나옵니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
