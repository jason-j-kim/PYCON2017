#!/usr/bin/env python3
"""
KWCI L1 — S2(RCA) + S4 일부(단가 프리미엄)

    RCA_j = (한국의 j 수출 / 한국 총수출) ÷ (세계의 j 수출 / 세계 총수출)

RCA >= 1 이면 한국이 세계 평균보다 그 품목에 특화했다는 뜻이다(Balassa 1965).
자의적 판단이 0이고 Comtrade만으로 완전히 재현된다 — 계획서 S2의 근거.

프로브에서 확인된 전략을 쓴다. reporterCode=0(세계 집계)은 빈 응답이었고,
reporterCode 를 생략하면 전 신고국이 온다. 그 한 번의 응답에 한국(410) 행과
세계 합계가 함께 들어 있으므로 품목당 1회 호출이면 네 항이 모두 나온다.

같은 응답의 netWgt 로 단가 프리미엄도 함께 낸다.
    UP_j = (한국산 j 단가) / (세계 평균 j 단가)
"이 나라 물건을 더 비싸게 사준다"는 문화 프리미엄의 가장 순수한 형태다(계획서 2.1).

산출: data/processed/rca.csv

사용법
------
  python compute_rca.py --test     # 3품목만
  python compute_rca.py            # top_items.csv 전체 (75품목, 약 3분)
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRADE = HERE.parent
sys.path.insert(0, str(TRADE / "api"))
from comtrade import Comtrade, find_key               # noqa: E402

TOP = TRADE / "data" / "processed" / "top_items.csv"
OUT = TRADE / "data" / "processed" / "rca.csv"

KOREA = 410
PERIODS = "2022,2023"      # 단년도는 노이즈에 취약해 복수년 평균으로 본다
WORKERS = 4                # 무료 티어를 고려해 낮게
SLEEP = 0.4


def aggregate(rows: list[dict]) -> tuple[dict, dict]:
    """전 신고국 응답에서 (한국 집계, 세계 집계)를 뽑는다.

    반환값은 {period: {"usd":..., "kg":...}} 형태.
    """
    kr: dict[str, dict[str, float]] = {}
    wd: dict[str, dict[str, float]] = {}
    for r in rows:
        p = str(r.get("period", ""))
        usd = float(r.get("primaryValue") or 0)
        kg = float(r.get("netWgt") or 0)
        for tgt in (wd, kr) if str(r.get("reporterCode")) == str(KOREA) else (wd,):
            d = tgt.setdefault(p, {"usd": 0.0, "kg": 0.0})
            d["usd"] += usd
            d["kg"] += kg
    return kr, wd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    if not TOP.exists():
        sys.exit(f"{TOP} 이 없습니다. rank_items.py 를 먼저 돌리세요.")
    with TOP.open(encoding="utf-8-sig") as f:
        items = list(csv.DictReader(f))
    n = 3 if args.test else (args.limit or len(items))
    items = items[:n]

    api = Comtrade(find_key())
    t0 = time.time()

    print(f"\nS2 RCA — {len(items)}품목 x {PERIODS}")
    print(f"  전 신고국 응답에서 한국·세계를 한 번에 집계 (품목당 1회 호출)\n",
          flush=True)

    # 분모의 분모: 한국 총수출 / 세계 총수출
    st, payload, note = api.get(period=PERIODS, cmdCode="TOTAL",
                                partnerCode=0, flowCode="X")
    tot_kr, tot_wd = aggregate(api.rows(payload))
    if not tot_wd:
        sys.exit(f"총수출 조회 실패: HTTP {st} {note[:120]}")
    for p in sorted(tot_wd):
        print(f"  {p} 총수출  한국 {tot_kr.get(p, {}).get('usd', 0)/1e9:>7,.0f}십억$"
              f"   세계 {tot_wd[p]['usd']/1e12:>6,.1f}조$", flush=True)
    print(flush=True)

    rows: list[dict] = []
    fail = 0

    def one(m: dict):
        hs = m["hs2022"]
        st, payload, note = api.get(period=PERIODS, cmdCode=hs,
                                    partnerCode=0, flowCode="X")
        time.sleep(SLEEP)
        if st != 200:
            return m, None, f"HTTP {st} {note[:60]}"
        return m, aggregate(api.rows(payload)), ""

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(one, m) for m in items]
        for i, fut in enumerate(as_completed(futs), 1):
            m, agg, err = fut.result()
            if agg is None:
                fail += 1
                print(f"    실패 {m['hs2022']} {err}", flush=True)
                continue
            kr, wd = agg
            for p in sorted(wd):
                kr_usd = kr.get(p, {}).get("usd", 0.0)
                kr_kg = kr.get(p, {}).get("kg", 0.0)
                w_usd, w_kg = wd[p]["usd"], wd[p]["kg"]
                tk = tot_kr.get(p, {}).get("usd", 0.0)
                tw = tot_wd.get(p, {}).get("usd", 0.0)
                if not (w_usd and tk and tw):
                    continue
                rca = (kr_usd / tk) / (w_usd / tw)
                kr_uv = kr_usd / kr_kg if kr_kg else None
                w_uv = w_usd / w_kg if w_kg else None
                rows.append({
                    "hs2022": m["hs2022"], "domain": m["domain"],
                    "name": m["name"], "period": p,
                    "kr_usd": round(kr_usd), "world_usd": round(w_usd),
                    "kr_world_share_pct": round(kr_usd / w_usd * 100, 3),
                    "rca": round(rca, 3),
                    "s2_pass": "Y" if rca >= 1 else "",
                    "kr_unit_value": round(kr_uv, 3) if kr_uv else "",
                    "world_unit_value": round(w_uv, 3) if w_uv else "",
                    "unit_value_premium": round(kr_uv / w_uv, 3)
                    if kr_uv and w_uv else "",
                })
            if i % 10 == 0 or i == len(items):
                el = time.time() - t0
                print(f"  {i:>3}/{len(items)}  행 {len(rows):>4}  실패 {fail}  "
                      f"남은 {el/i*(len(items)-i)/60:.1f}분", flush=True)

    rows.sort(key=lambda r: (r["domain"], -r["rca"]))
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["hs2022"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n= {OUT.name}  {len(rows):,}행  ({time.time()-t0:.0f}초)")

    # 도메인별 S2 통과율 — K-Fashion 이 낮게 나오면 계획서 4.2의 진단이 된다.
    last = max((r["period"] for r in rows), default=None)
    print(f"\n[S2 통과 (RCA >= 1), {last}]")
    for d in sorted({r["domain"] for r in rows}):
        sel = [r for r in rows if r["domain"] == d and r["period"] == last]
        ok = [r for r in sel if r["rca"] >= 1]
        print(f"  {d:<10} {len(ok):>2}/{len(sel):<3} 통과   "
              f"최고 RCA {max((r['rca'] for r in sel), default=0):>7,.1f}")
        for r in sorted(ok, key=lambda x: -x["rca"])[:5]:
            print(f"      RCA {r['rca']:>7,.1f}  단가프리미엄 "
                  f"{r['unit_value_premium'] or '-':>6}  "
                  f"{r['hs2022']} {r['name'][:36]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
