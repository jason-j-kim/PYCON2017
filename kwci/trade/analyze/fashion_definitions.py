#!/usr/bin/env python3
"""
K-Fashion 정의 3종 병렬 산출 — 정의를 바꾸면 무엇이 달라지는가

KCI 보고서(김영범)는 MTI 4 기준으로 베트남 19.6% 1위, KWCI는 BEC 소비재
기준으로 중국 28% 1위다. 같은 산업 같은 해인데 순위가 다르다. 품목 정의가
다르기 때문이다. 그 차이를 정량화한다.

공통 틀
------
세 정의를 그대로 비교하면 포괄 범위가 달라 비교가 성립하지 않는다.
KWCI 의 K-Fashion 대역에는 신발(64)·가방(4202)·장신구(7113/7117)·안경
(9003/9004)이 들어 있고 이들은 MTI 4(섬유류) 밖이다. 그래서 공통 틀을
섬유·의류(HS 50~63)로 좁힌다. 대역 밖 품목은 참고 계열로 따로 낸다.

  (1) 섬유류 전체    HS 50~63           원사·직물·의류 전부 = MTI 4 근사
  (2) 의류 완제품    HS 61+62 중 BEC 소비재 통과분
  (3) 순수 완제품    (2) 에서 6217(의류 부속품) 제외

(1)→(2)→(3) 으로 가며 국가 비중이 어떻게 이동하는지가 "수출통계가 소비
신호를 얼마나 왜곡하는가"의 측정값이다.

(1) 은 새로 수집한다(원사·직물은 BEC 소비재가 아니라 기존 928 후보에 없다).
장(章) 단위로 받으므로 호출이 적다.

산출: data/processed/fashion_defs.csv  ·  fashion_defs_country.csv

사용법
------
  python fashion_definitions.py --probe    # 장 단위 조회 가능 여부만 확인
  python fashion_definitions.py            # 수집 + 대조 (약 5분)
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRADE = HERE.parent
sys.path.insert(0, str(TRADE / "collect"))
sys.path.insert(0, str(TRADE / "api"))
from collect_customs import fetch, num, WORKERS        # noqa: E402
from collect_stage_b import COUNTRIES                   # noqa: E402
from customs import find_key                            # noqa: E402

PANEL = TRADE / "data" / "processed" / "panel.csv"
OUT = TRADE / "data" / "processed" / "fashion_defs.csv"
OUT_C = TRADE / "data" / "processed" / "fashion_defs_country.csv"

YEARS = ["2018", "2024"]
# HS 50~63 = 섬유류. 50 견 · 51 양모 · 52 면 · 53 기타식물성섬유 · 54 인조필라멘트
# 55 인조스테이플 · 56 부직포 · 57 카펫 · 58 특수직물 · 59 침투처리직물
# 60 편물 · 61 편물의류 · 62 직물의류 · 63 기타섬유제품
TEXTILE = [f"{c:02d}" for c in range(50, 64)]
APPAREL = ("61", "62")            # 의류 완제품 장
PARTS_PREFIX = ("6217",)          # 의류 부속품 — (3) 에서 제외


def collect_textile(key: str) -> list[dict]:
    """(1) 섬유류 전체를 장 단위로 받는다."""
    jobs = [(ch, cc, y) for ch in TEXTILE for cc in COUNTRIES for y in YEARS]
    rows: list[dict] = []
    fail = 0
    t0 = time.time()
    print(f"\n(1) 섬유류 HS 50~63 — {len(TEXTILE)}개 장 x {len(COUNTRIES)}개국 "
          f"x {len(YEARS)}년 = {len(jobs)}회", flush=True)

    def one(job):
        ch, cc, y = job
        items = fetch(key, ch, y, cnty=cc)
        if items is None:
            return ch, cc, y, -1.0, -1.0
        for it in items:
            if str(it.get("year", "")).strip() in ("총계", "합계", "계"):
                return ch, cc, y, num(it.get("expDlr")), num(it.get("expWgt"))
        return (ch, cc, y,
                sum(num(it.get("expDlr")) for it in items),
                sum(num(it.get("expWgt")) for it in items))

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(one, j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            ch, cc, y, usd, kg = fut.result()
            if usd < 0:
                fail += 1
                continue
            rows.append({"chapter": ch, "country": cc, "year": y,
                         "exp_usd": usd, "exp_kg": kg})
            if i % 100 == 0 or i == len(jobs):
                el = time.time() - t0
                print(f"  {i:>4}/{len(jobs)}  실패 {fail}  "
                      f"남은 {el/i*(len(jobs)-i)/60:.1f}분", flush=True)
    return rows


def load_panel() -> list[dict]:
    if not PANEL.exists():
        sys.exit(f"{PANEL.name} 이 없습니다. collect_panel.py 를 먼저 돌리세요.")
    with PANEL.open(encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["domain"] == "K-Fashion"]
    for r in rows:
        r["exp_usd"] = float(r["exp_usd"] or 0)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true",
                    help="장(2자리) 단위 조회가 되는지만 확인")
    args = ap.parse_args()
    key = find_key()

    if args.probe:
        # 관세청이 hsSgn 2자리를 받는지는 실측해야 안다.
        for hs, label in (("61", "장 2자리"), ("6109", "호 4자리")):
            items = fetch(key, hs, "2024", cnty="US")
            tot = next((num(i.get("expDlr")) for i in items or []
                        if str(i.get("year", "")).strip() == "총계"), None)
            print(f"  {'o' if tot else 'x'} {label:<10} hsSgn={hs} "
                  f"-> {f'{tot:,.0f}$' if tot else '응답 없음'}")
        print("\n  2자리가 x 면 TEXTILE 을 4자리 호 목록으로 바꿔야 합니다.")
        return 0

    tex = collect_textile(key)
    panel = load_panel()

    # ── 세 정의별 국가 x 연도 집계 ─────────────────────────────
    defs: dict[str, dict[tuple, float]] = {
        "(1) 섬유류 전체": defaultdict(float),
        "(2) 의류 완제품": defaultdict(float),
        "(3) 순수 완제품": defaultdict(float),
        "[참고] 비섬유 잡화": defaultdict(float),
    }
    for r in tex:
        defs["(1) 섬유류 전체"][(r["country"], r["year"])] += r["exp_usd"]
    for r in panel:
        hs, k = r["hs2022"], (r["country"], r["year"])
        if hs[:2] in APPAREL:
            defs["(2) 의류 완제품"][k] += r["exp_usd"]
            if not hs.startswith(PARTS_PREFIX):
                defs["(3) 순수 완제품"][k] += r["exp_usd"]
        else:
            defs["[참고] 비섬유 잡화"][k] += r["exp_usd"]

    # ── 국가별 상세 저장 ───────────────────────────────────────
    with OUT_C.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["definition", "country", "country_name", "year",
                    "exp_usd", "share_pct"])
        for d, m in defs.items():
            for y in YEARS:
                tot = sum(v for (c, yy), v in m.items() if yy == y)
                for (c, yy), v in sorted(m.items()):
                    if yy != y:
                        continue
                    w.writerow([d, c, COUNTRIES.get(c, c), y, round(v),
                                round(v / tot * 100, 2) if tot else ""])

    # ── 요약 ───────────────────────────────────────────────────
    def tot_of(d, y):
        return sum(v for (c, yy), v in defs[d].items() if yy == y)

    print("\n" + "=" * 66)
    print("정의별 총액과 성장 (15개국 합계)\n")
    print(f"  {'정의':<20} {'2018':>12} {'2024':>12} {'지수':>8}  {'(1) 대비':>9}")
    base_24 = tot_of("(1) 섬유류 전체", "2024")
    summary = []
    for d in defs:
        a, b = tot_of(d, "2018"), tot_of(d, "2024")
        idx = b / a * 100 if a else 0
        print(f"  {d:<20} {a/1e6:>10,.0f}백만 {b/1e6:>10,.0f}백만 "
              f"{idx:>8.1f} {b/base_24*100 if base_24 else 0:>8.1f}%")
        summary.append({"definition": d, "usd_2018": round(a),
                        "usd_2024": round(b), "index_2018_100": round(idx, 1),
                        "share_of_def1_pct": round(b / base_24 * 100, 1)
                        if base_24 else ""})

    print("\n" + "=" * 66)
    print("정의별 2024년 국가 순위 — 정의가 바뀌면 순위가 바뀐다\n")
    for d in defs:
        tot = tot_of(d, "2024")
        top = sorted(((v, c) for (c, y), v in defs[d].items() if y == "2024"),
                     reverse=True)[:5]
        s = "  ".join(f"{COUNTRIES.get(c, c)} {v/tot*100:.0f}%"
                      for v, c in top if tot)
        print(f"  {d:<20} {s}")

    # 베트남 비중 이동 — 이 대조의 핵심 지표
    print("\n" + "=" * 66)
    print("베트남·중국 비중 이동 (2024)\n")
    for cc, nm in (("VN", "베트남"), ("CN", "중국"), ("US", "미국")):
        line = []
        for d in ("(1) 섬유류 전체", "(2) 의류 완제품", "(3) 순수 완제품"):
            tot = tot_of(d, "2024")
            v = defs[d].get((cc, "2024"), 0.0)
            line.append(f"{v/tot*100:>5.1f}%" if tot else "    -")
        print(f"  {nm:<6} (1) {line[0]}  ->  (2) {line[1]}  ->  (3) {line[2]}")

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    print(f"\n= {OUT.name} · {OUT_C.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
