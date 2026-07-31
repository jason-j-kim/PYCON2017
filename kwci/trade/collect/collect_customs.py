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
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# 관세청은 1회 조회기간을 1년 이내로 제한한다(resultCode 99).
# 그래서 연도별로 나눠 부른다. 기본은 2018(KWCI 기준연도)과 2024(최근 실적)
# 두 해만 — 순위 선정과 성장배수 산출에 이 둘이면 충분하고, 8년 전수(7,424회)를
# 피할 수 있다. 상위 품목의 전 연도는 B단계에서 채운다.
# 순위는 최근 실적만으로 정해진다. 기준연도(2018) 대비 성장배수는 순위가
# 정해진 뒤 상위 품목에만 받으면 되므로, A단계는 2024 한 해만 훑는다.
YEARS = ["2024"]
# 관세청 응답이 호출당 4초 안팎으로 느리다. 순차로 돌면 928건에 65분이라
# 스레드로 병렬 호출한다. 서버 부담을 고려해 동시 8개로 제한.
WORKERS = 8
SLEEP = 0.05
TIMEOUT = 30
RETRY = 2

_local = threading.local()


def session() -> "requests.Session":
    """스레드마다 별도 세션을 쓴다."""
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    return _local.s


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


def ok_response(text: str) -> bool:
    """resultCode 00 인 응답만 유효하다. 오류도 HTTP 200으로 오므로 본문을 본다."""
    return "<resultCode>00</resultCode>" in text.replace(" ", "")


def fetch(key: str, hs: str, year: str) -> list[dict] | None:
    sess = session()
    cached = CACHE / f"{hs}_{year}.xml"
    if cached.exists():
        text = cached.read_text(encoding="utf-8")
        if ok_response(text):
            return items_of(parse_xml(text))
        cached.unlink()          # 오류 응답이 캐시된 경우 버리고 다시 받는다
    r = None
    for attempt in range(RETRY + 1):
        try:
            r = sess.get(URL, params={"serviceKey": key, "hsSgn": hs,
                                      "strtYymm": f"{year}01",
                                      "endYymm": f"{year}12"},
                         timeout=TIMEOUT)
            break
        except requests.RequestException as e:
            print(f"    재시도 {hs} ({attempt+1}/{RETRY}) {type(e).__name__}",
                  flush=True)
            time.sleep(1.5)
    if r is None or r.status_code != 200:
        return None
    if "LIMITED NUMBER" in r.text or "NOT REGISTERED" in r.text:
        print(f"\n  ! API 한도/권한 오류: {r.text[:140]}")
        raise SystemExit(1)
    if not ok_response(r.text):
        return None
    cached.write_text(r.text, encoding="utf-8")
    return items_of(parse_xml(r.text))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="앞 5품목만")
    ap.add_argument("--limit", type=int, help="앞 N품목만")
    ap.add_argument("--years", help="쉼표 구분 연도 (기본 2024)")
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

    if args.years:
        YEARS[:] = [y.strip() for y in args.years.split(",") if y.strip()]
    n = 5 if args.test else (args.limit or len(master))
    master = master[:n]
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    key = find_key()
    rows: list[dict] = []
    t0 = time.time()
    empty = fail = 0

    print(f"\n관세청 A단계 — {len(master):,}품목 x {'/'.join(YEARS)} (국가 무관)")
    print(f"호출 {len(master)*len(YEARS):,}회, 동시 {WORKERS}개, 예상 "
          f"{len(master)*len(YEARS)*4.2/WORKERS/60:.0f}분", flush=True)
    done = len(list(CACHE.glob("*.xml")))
    if done:
        print(f"캐시 {done:,}건 재사용 (중단 지점부터 이어받음)", flush=True)
    print(flush=True)

    def one(m: dict) -> tuple[dict, list[dict]]:
        """품목 하나의 연도별 실적 행을 만든다."""
        hs, made = m["hs2022"], []
        for year in YEARS:
            items = fetch(key, hs, year)
            if items is None:
                made.append({"_fail": True})
                continue
            # 응답에는 '총계' 행과 월별 행이 섞여 있다. 연간 합계는
            # '총계' 행이 담고 있으므로 그것을 연도 실적으로 쓴다.
            usd = kg = 0.0
            for it in items:
                if str(it.get("year", "")).strip() in ("총계", "합계", "계"):
                    usd, kg = num(it.get("expDlr")), num(it.get("expWgt"))
                    break
            else:
                for it in items:      # 총계 행이 없으면 월별을 더한다
                    usd += num(it.get("expDlr"))
                    kg += num(it.get("expWgt"))
            if usd or kg:
                made.append({
                    "hs2022": hs, "domain": m["domain"], "name": m["name"],
                    "year": year, "exp_usd": usd, "exp_kg": kg,
                    "unit_value": round(usd / kg, 4) if kg else "",
                })
        return m, made

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(one, m): m for m in master}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                m, made = fut.result()
            except Exception as e:
                fail += 1
                print(f"    오류 {type(e).__name__}: {e}", flush=True)
                continue
            good = [r for r in made if not r.get("_fail")]
            failed = len(made) - len(good)
            fail += failed
            rows.extend(good)
            if not good and not failed:   # 호출은 됐는데 실적이 0인 품목
                empty += 1
            if i <= 3 or i % 25 == 0 or i == len(master):
                el = time.time() - t0
                eta = el / i * (len(master) - i)
                print(f"  {i:>4}/{len(master)}  행 {len(rows):>5,}  "
                      f"빈 {empty}  실패 {fail}  남은 {eta/60:.1f}분", flush=True)

    rows.sort(key=lambda r: (r["domain"], r["hs2022"], r["year"]))

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hs2022", "domain", "name", "year",
                                          "exp_usd", "exp_kg", "unit_value"])
        w.writeheader()
        w.writerows(rows)

    if not rows:
        print("\n  ! 0행 — 응답 형식이 예상과 다릅니다. 첫 응답의 item:")
        for fp in sorted(CACHE.glob("*.xml"))[-1:]:
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
