#!/usr/bin/env python3
"""
KWCI L1 — 관세청 수집 A단계: 품목별 총수출 (국가 무관)

928개 후보 각각의 연도별 수출금액·중량을 받는다. 품목당 1회 호출.
이 결과로 도메인별 상위 품목을 골라내면, 국가별 상세(B단계)는 상위 20개
정도만 받으면 된다. 928 x 15개국을 전수로 도는 것(약 4시간)을 피하는 설계다.

산출: kwci/trade/data/processed/item_totals.csv
      hs2022, domain, name, year, exp_usd, exp_kg, unit_value

응답은 캐시에 남으므로 중단해도 이어서 받는다(--resume 기본).

사용법
------
  python collect_customs.py --test        # 5품목만 (동작 확인, 10초)
  python collect_customs.py               # 전체 928품목 (약 10분)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests가 필요합니다:  pip install requests")

HERE = Path(__file__).resolve().parent
TRADE = HERE.parent
sys.path.insert(0, str(TRADE / "api"))
from customs import find_key, parse_xml          # noqa: E402

MASTER = TRADE / "master" / "item_master.csv"
CACHE = TRADE / "data" / "raw" / "customs"
OUT = TRADE / "data" / "processed" / "item_totals.csv"
URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"

START, END = "201801", "202512"
SLEEP = 0.35
TIMEOUT = 60


def items_of(payload) -> list[dict]:
    """응답 어디에 있든 expDlr 를 가진 사전들을 찾아 돌려준다."""
    found: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if "expDlr" in o:
                found.append(o)
            else:
                for v in o.values():
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(payload)
    return found


def num(v) -> float:
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def fetch(sess, key: str, hs: str) -> list[dict] | None:
    cached = CACHE / f"{hs}.xml"
    if cached.exists() and cached.stat().st_size > 200:
        return items_of(parse_xml(cached.read_text(encoding="utf-8")))
    try:
        r = sess.get(URL, params={"serviceKey": key, "hsSgn": hs,
                                  "strtYymm": START, "endYymm": END},
                     timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    payload = parse_xml(r.text)
    if not payload:
        return None
    # 한도 초과·미승인은 200으로 오므로 본문을 봐야 한다.
    if "LIMITED NUMBER" in r.text or "NOT REGISTERED" in r.text:
        print(f"\n  ! API 한도/권한 오류: {r.text[:120]}")
        raise SystemExit(1)
    cached.write_text(r.text, encoding="utf-8")
    return items_of(payload)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="앞 5품목만")
    ap.add_argument("--limit", type=int, help="앞 N품목만")
    ap.add_argument("--dump", metavar="HS", nargs="?", const="",
                    help="캐시된 응답의 item 을 그대로 출력 (형식 확인용)")
    args = ap.parse_args()

    if args.dump is not None:
        files = sorted(CACHE.glob(f"{args.dump or '*'}*.xml"))
        if not files:
            sys.exit(f"캐시가 없습니다: {CACHE}")
        for fp in files[:2]:
            items = items_of(parse_xml(fp.read_text(encoding="utf-8")))
            print(f"\n--- {fp.name}  item {len(items)}개 ---")
            for it in items[:8]:
                print("  ", it)
            if not items:
                print("  (expDlr 를 가진 노드 없음) 원문 앞부분:")
                print("  ", fp.read_text(encoding="utf-8")[:600])
        return 0

    if not MASTER.exists():
        sys.exit(f"{MASTER} 이 없습니다. build_item_master.py 를 먼저 돌리세요.")
    with MASTER.open(encoding="utf-8") as f:
        master = list(csv.DictReader(f))

    n = 5 if args.test else (args.limit or len(master))
    master = master[:n]
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    key = find_key()
    sess = requests.Session()
    rows: list[dict] = []
    t0 = time.time()
    empty = fail = 0

    print(f"\n관세청 A단계 — {len(master):,}품목 x {START}~{END} (국가 무관)")
    print(f"예상 {len(master)*(SLEEP+0.4)/60:.0f}분\n")

    for i, m in enumerate(master, 1):
        hs = m["hs2022"]
        items = fetch(sess, key, hs)
        if items is None:
            fail += 1
        else:
            got = 0
            for it in items:
                year = str(it.get("year", "")).strip()
                # '총계' 행과 국가 소계는 건너뛰고 연도 행만 취한다.
                if not year.isdigit() or len(year) != 4:
                    continue
                usd, kg = num(it.get("expDlr")), num(it.get("expWgt"))
                if usd == 0 and kg == 0:
                    continue
                rows.append({
                    "hs2022": hs, "domain": m["domain"], "name": m["name"],
                    "year": year, "exp_usd": usd, "exp_kg": kg,
                    "unit_value": round(usd / kg, 4) if kg else "",
                })
                got += 1
            if got == 0:
                empty += 1
        if not (CACHE / f"{hs}.xml").exists():
            time.sleep(SLEEP)

        if i % 25 == 0 or i == len(master):
            el = time.time() - t0
            eta = el / i * (len(master) - i)
            print(f"  {i:>4}/{len(master)}  행 {len(rows):>6,}  "
                  f"빈품목 {empty}  실패 {fail}  남은 {eta/60:.1f}분")

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hs2022", "domain", "name", "year",
                                          "exp_usd", "exp_kg", "unit_value"])
        w.writeheader()
        w.writerows(rows)

    if not rows:
        print("\n  ! 0행 — 응답 형식이 예상과 다릅니다. 첫 응답의 item:")
        for fp in sorted(CACHE.glob("*.xml"))[:1]:
            items = items_of(parse_xml(fp.read_text(encoding="utf-8")))
            for it in items[:6]:
                print("    ", it)
            if not items:
                print("    ", fp.read_text(encoding="utf-8")[:600])

    print(f"\n= {OUT.name}  {len(rows):,}행  ({time.time()-t0:.0f}초)")
    print(f"  수출실적 있는 품목 {len(master)-empty-fail:,} / {len(master):,}")
    if fail:
        print(f"  ! 호출 실패 {fail}건 — 다시 실행하면 캐시를 건너뛰고 재시도합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
