#!/usr/bin/env python3
"""
KWCI L1 — 관세청 수집 B단계: 대표 품목의 국가별 상세 + 기준연도

A단계에서 확정한 상위 품목(top_items.csv)에 대해 두 가지를 받는다.

  1) 국가별 2024 수출  -> KWCI 횡단 L1 (어느 국가가 강한가)
  2) 전체 2018 수출    -> KWCI 시계열 (2018=100 성장배수)

브리핑 통찰 ①의 "두 개의 자"를 그대로 따른다. 횡단은 국가별 최근 실적,
시계열은 총계 기준 기준연도 대비. 두 산출을 다른 파일로 분리한다.

산출
----
  data/processed/country_totals.csv   hs2022, domain, country, exp_usd, exp_kg
  data/processed/base_2018.csv        hs2022, domain, exp_usd_2018, growth

사용법
------
  python collect_stage_b.py --test    # 3품목만
  python collect_stage_b.py           # 전체 (약 10분)
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
from collect_customs import fetch, num, WORKERS       # noqa: E402
from customs import find_key                           # noqa: E402

TOP = TRADE / "data" / "processed" / "top_items.csv"
OUT_C = TRADE / "data" / "processed" / "country_totals.csv"
OUT_B = TRADE / "data" / "processed" / "base_2018.csv"

CROSS_YEAR = "2024"      # 횡단(국가 비교)
BASE_YEAR = "2018"       # 시계열 기준연도 (KWCI 2018=100)

# KWCI 15개국 패널.
# 브리핑 17쪽에서 확인된 것: 미국·베트남·아르헨티나·태국·프랑스·일본·중국(1~7위),
# 남아공(15위). 8~14위는 브리핑에 생략되어 있어 아래 7개는 잠정이다.
# 확정 명단을 받으면 이 표만 고치면 된다.
COUNTRIES = {
    "US": "미국", "VN": "베트남", "AR": "아르헨티나", "TH": "태국",
    "FR": "프랑스", "JP": "일본", "CN": "중국", "ZA": "남아공",
    # --- 잠정 (확정 명단으로 교체 필요) ---
    "ID": "인도네시아", "PH": "필리핀", "MY": "말레이시아", "IN": "인도",
    "TW": "대만", "MX": "멕시코", "GB": "영국",
}


def fetch_country(key: str, hs: str, year: str, cnty: str) -> tuple[float, float]:
    """국가 지정 수출 실적. collect_customs.fetch 와 같은 캐시 규약을 쓴다."""
    items = fetch(key, hs, year, cnty=cnty)
    if items is None:
        return -1.0, -1.0
    for it in items:
        if str(it.get("year", "")).strip() in ("총계", "합계", "계"):
            return num(it.get("expDlr")), num(it.get("expWgt"))
    usd = sum(num(it.get("expDlr")) for it in items)
    kg = sum(num(it.get("expWgt")) for it in items)
    return usd, kg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="3품목만")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    if not TOP.exists():
        sys.exit(f"{TOP} 이 없습니다. rank_items.py 를 먼저 돌리세요.")
    with TOP.open(encoding="utf-8-sig") as f:
        items = list(csv.DictReader(f))
    n = 3 if args.test else (args.limit or len(items))
    items = items[:n]

    key = find_key()
    t0 = time.time()
    calls = len(items) * (len(COUNTRIES) + 1)
    print(f"\nB단계 — {len(items)}품목")
    print(f"  국가별 {CROSS_YEAR}: {len(COUNTRIES)}개국   기준연도 {BASE_YEAR}: 총계")
    print(f"  호출 {calls:,}회, 동시 {WORKERS}개, 예상 "
          f"{calls*4.2/WORKERS/60:.0f}분\n", flush=True)

    jobs: list[tuple] = []
    for m in items:
        for cc in COUNTRIES:
            jobs.append(("C", m, cc))
        jobs.append(("B", m, None))

    crows: list[dict] = []
    brows: list[dict] = []
    fail = 0

    def run(job):
        kind, m, cc = job
        hs = m["hs2022"]
        if kind == "C":
            usd, kg = fetch_country(key, hs, CROSS_YEAR, cc)
            return kind, m, cc, usd, kg
        usd, kg = fetch_country(key, hs, BASE_YEAR, None)
        return kind, m, None, usd, kg

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(run, j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                kind, m, cc, usd, kg = fut.result()
            except Exception as e:
                fail += 1
                print(f"    오류 {type(e).__name__}: {e}", flush=True)
                continue
            if usd < 0:
                fail += 1
                continue
            if kind == "C":
                if usd or kg:
                    crows.append({
                        "hs2022": m["hs2022"], "domain": m["domain"],
                        "name": m["name"], "country": cc,
                        "country_name": COUNTRIES[cc], "year": CROSS_YEAR,
                        "exp_usd": usd, "exp_kg": kg,
                        "unit_value": round(usd / kg, 4) if kg else "",
                    })
            else:
                base = usd
                cur = float(m["exp_usd"] or 0)
                brows.append({
                    "hs2022": m["hs2022"], "domain": m["domain"],
                    "name": m["name"], "exp_usd_2018": base,
                    "exp_usd_2024": cur,
                    # KWCI 관례에 맞춰 2018=100 지수로 낸다.
                    "index_2018_100": round(cur / base * 100, 1) if base else "",
                })
            if i % 100 == 0 or i == len(jobs):
                el = time.time() - t0
                print(f"  {i:>5}/{len(jobs)}  국가행 {len(crows):>4}  "
                      f"기준연도 {len(brows):>3}  실패 {fail}  "
                      f"남은 {el/i*(len(jobs)-i)/60:.1f}분", flush=True)

    crows.sort(key=lambda r: (r["domain"], r["hs2022"], -r["exp_usd"]))
    brows.sort(key=lambda r: (r["domain"], r["hs2022"]))

    with OUT_C.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(crows[0]) if crows else
                           ["hs2022", "domain", "name", "country",
                            "country_name", "year", "exp_usd", "exp_kg",
                            "unit_value"])
        w.writeheader()
        w.writerows(crows)
    with OUT_B.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hs2022", "domain", "name",
                                          "exp_usd_2018", "exp_usd_2024",
                                          "index_2018_100"])
        w.writeheader()
        w.writerows(brows)

    print(f"\n= {OUT_C.name}  {len(crows):,}행")
    print(f"= {OUT_B.name}  {len(brows):,}행  ({time.time()-t0:.0f}초)")
    if fail:
        print(f"  ! 실패 {fail}건 — 재실행하면 캐시를 건너뛰고 재시도합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
