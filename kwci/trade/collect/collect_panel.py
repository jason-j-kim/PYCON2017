#!/usr/bin/env python3
"""
KWCI L1 — 국가 x 품목 x 연도 패널 수집

75개 대표 품목 x 15개국 x 2018~2024 의 수출금액·중량을 받는다.
이것이 S3(한류 반응성 패널회귀)의 종속변수가 되는 자료다.

    ln(수출_ijt) = b * ln(한류신호_i,t-k) + 통제 + 국가x품목 FE + 시간 FE

B단계에서 2024년치는 이미 받았으므로 캐시에서 재사용된다.
중단해도 다시 실행하면 이어받는다.

산출: data/processed/panel.csv
      hs2022, domain, name, country, country_name, year, exp_usd, exp_kg, unit_value

사용법
------
  python collect_panel.py --test           # 2품목 x 2개국 x 전 연도
  python collect_panel.py                  # 전체 (약 40~60분)
  python collect_panel.py --workers 12     # 더 빠르게 (서버 부담 주의)
  python collect_panel.py --years 2018,2021,2024   # 연도 축소
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TRADE / "api"))
from collect_customs import fetch, num, CACHE          # noqa: E402
from collect_stage_b import COUNTRIES                   # noqa: E402
from customs import find_key                            # noqa: E402

TOP = TRADE / "data" / "processed" / "top_items.csv"
OUT = TRADE / "data" / "processed" / "panel.csv"

# 2018 은 KWCI 기준연도, 2024 는 최근 실적. 그 사이를 연 단위로 채운다.
# 2025 는 연도가 끝나지 않아 기본에서 제외한다(부분연도를 섞으면 성장률이 왜곡).
YEARS = [str(y) for y in range(2018, 2025)]


def annual(key: str, hs: str, year: str, cc: str) -> tuple[float, float]:
    items = fetch(key, hs, year, cnty=cc)
    if items is None:
        return -1.0, -1.0
    for it in items:
        if str(it.get("year", "")).strip() in ("총계", "합계", "계"):
            return num(it.get("expDlr")), num(it.get("expWgt"))
    return (sum(num(it.get("expDlr")) for it in items),
            sum(num(it.get("expWgt")) for it in items))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--limit", type=int, help="앞 N품목만")
    ap.add_argument("--years", help="쉼표 구분 연도")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    if not TOP.exists():
        sys.exit(f"{TOP} 이 없습니다. rank_items.py 를 먼저 돌리세요.")
    with TOP.open(encoding="utf-8-sig") as f:
        items = list(csv.DictReader(f))

    years = ([y.strip() for y in args.years.split(",")] if args.years
             else YEARS)
    countries = dict(list(COUNTRIES.items())[:2]) if args.test else COUNTRIES
    if args.test:
        items = items[:2]
    elif args.limit:
        items = items[:args.limit]

    jobs = [(m, cc, y) for m in items for cc in countries for y in years]
    cached = sum(1 for m, cc, y in jobs
                 if (CACHE / f"{m['hs2022']}_{y}_{cc}.xml").exists())
    todo = len(jobs) - cached

    key = find_key()
    print(f"\n패널 수집 — {len(items)}품목 x {len(countries)}개국 x "
          f"{len(years)}년 = {len(jobs):,}칸")
    print(f"  캐시 {cached:,} · 신규 {todo:,}회, 동시 {args.workers}개, "
          f"예상 {todo*4.2/args.workers/60:.0f}분\n", flush=True)

    rows: list[dict] = []
    fail = 0
    t0 = time.time()

    def one(job):
        m, cc, y = job
        usd, kg = annual(key, m["hs2022"], y, cc)
        return m, cc, y, usd, kg

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(one, j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                m, cc, y, usd, kg = fut.result()
            except Exception as e:
                fail += 1
                print(f"    오류 {type(e).__name__}: {e}", flush=True)
                continue
            if usd < 0:
                fail += 1
                continue
            # 실적 0 인 칸도 남긴다. "그 해 그 시장에 안 들어갔다"는 것 자체가
            # 패널회귀에서 정보이고, 빼 버리면 표본이 생존편향에 걸린다.
            rows.append({
                "hs2022": m["hs2022"], "domain": m["domain"], "name": m["name"],
                "country": cc, "country_name": countries[cc], "year": y,
                "exp_usd": usd, "exp_kg": kg,
                "unit_value": round(usd / kg, 4) if kg else "",
            })
            if i % 250 == 0 or i == len(jobs):
                el = time.time() - t0
                print(f"  {i:>6}/{len(jobs)}  행 {len(rows):>6,}  실패 {fail}  "
                      f"남은 {el/i*(len(jobs)-i)/60:.1f}분", flush=True)

    rows.sort(key=lambda r: (r["domain"], r["hs2022"], r["country"], r["year"]))
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hs2022", "domain", "name", "country",
                                          "country_name", "year", "exp_usd",
                                          "exp_kg", "unit_value"])
        w.writeheader()
        w.writerows(rows)

    nz = sum(1 for r in rows if r["exp_usd"] > 0)
    print(f"\n= {OUT.name}  {len(rows):,}행  ({time.time()-t0:.0f}초)")
    print(f"  실적 있는 칸 {nz:,} / {len(rows):,}  "
          f"({nz/len(rows)*100 if rows else 0:.0f}%)")
    if fail:
        print(f"  ! 실패 {fail}건 — 재실행하면 캐시를 건너뛰고 재시도합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
