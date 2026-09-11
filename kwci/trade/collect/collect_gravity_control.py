#!/usr/bin/env python3
"""
검정 1 보강 — 문화 무관 대조군 수집과 중력 효과 판별

검정 1(test_country_structure.py)은 세 한류 도메인의 국가 구성비가 서로 매우
닮았음을 보였다(2024년 피어슨 0.94~0.99, 품목쌍 중앙값 0.739~0.762). 그러나
그 상관의 원인은 둘 중 하나이고, 한류 품목만으로는 가르지 못한다.

  (가) 한류 수용이 국가 단위로 묶인다        -> L2 국가층이 정당
  (나) 한국이 크고 가까운 시장에 많이 판다    -> 중력 효과, 한류와 무관

판별은 간단하다. **문화 채널이 없는 품목**의 국가 구성비를 같은 방식으로 구해
같은 상관을 계산한다. 대조군끼리도 0.75 수준이면 (나)이고, 뚜렷이 낮으면
(가)다. 한류 품목만 보고 "국가 단위 수용"을 주장하면 순환이다.

대조군 두 갈래
-------------
  순수 중력 10품목 (브랜드도 문화 채널도 없는 B2B 원자재·부품) -> 45쌍
    메모리 반도체 · 프로세서 · 인쇄회로 · 반도체장비 · 석유제품
    파라자일렌 · 폴리에틸렌 · 폴리프로필렌 · 열연강판 · 도장강판

  브랜드 대조 5품목 (브랜드는 있으나 한류 귀속이 아닌 공산품) -> 10쌍
    승용차 2종 · 냉장고 · 세탁기 · TV

브랜드 대조를 따로 두는 이유가 있다. 순수 중력과 한류 사이에 "한국산 브랜드
신뢰"라는 중간 채널이 있을 수 있고, 그것은 한류와 구분되어야 한다. 셋의
상관이 중력 < 브랜드 < 한류 순으로 계단을 이루면 한류 고유분이 존재한다.

품목 수가 적으면 쌍이 급격히 준다(n -> n(n-1)/2). 한류 쪽 2,701쌍과 견주려면
대조군도 수십 쌍은 있어야 하므로 각 갈래를 넉넉히 잡았다. 판정은 점추정이
아니라 중앙값 차이의 부트스트랩 95% 구간으로 한다.

수집량: 15품목 x 15개국 x 2개년 = 450회. 캐시 포함 약 4분.
산출:   data/processed/gravity_control.csv  + 판정 출력

사용법
------
  python collect_gravity_control.py --probe   # 15품목 총계만 확인(15회)
  python collect_gravity_control.py           # 전체 수집 + 판정
  python collect_gravity_control.py --report  # 수집분으로 판정만 다시
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRADE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TRADE / "api"))
sys.path.insert(0, str(TRADE / "analyze"))
from collect_customs import fetch, num, WORKERS          # noqa: E402
from collect_stage_b import COUNTRIES                     # noqa: E402
from customs import find_key                              # noqa: E402
from test_country_structure import spearman, MIN_NONZERO  # noqa: E402

OUT = TRADE / "data" / "processed" / "gravity_control.csv"
PANEL = TRADE / "data" / "processed" / "panel.csv"
YEARS = ["2018", "2024"]

# 품목이 적으면 쌍이 급격히 준다(n품목 -> n(n-1)/2 쌍). 한류 쪽 2,701쌍과
# 견주려면 대조군도 최소 수십 쌍은 필요하므로 각 갈래를 넉넉히 잡는다.
CONTROLS = {
    # 순수 중력 — 소비자 브랜드도 문화 채널도 없는 B2B 원자재·부품 (10품목 45쌍)
    "854232": ("중력", "메모리 반도체"),
    "854231": ("중력", "프로세서·제어기"),
    "853400": ("중력", "인쇄회로"),
    "848620": ("중력", "반도체 제조장비"),
    "271019": ("중력", "석유제품(원유 제외)"),
    "290243": ("중력", "파라자일렌"),
    "390120": ("중력", "폴리에틸렌"),
    "390210": ("중력", "폴리프로필렌"),
    "720839": ("중력", "열간압연 강판"),
    "721070": ("중력", "도장 강판"),
    # 브랜드 대조 — 브랜드는 있으나 한류 귀속이 아닌 공산품 (5품목 10쌍)
    "870323": ("브랜드", "승용차 1500~3000cc"),
    "870324": ("브랜드", "승용차 3000cc 초과"),
    "841810": ("브랜드", "냉장고"),
    "845011": ("브랜드", "세탁기"),
    "852872": ("브랜드", "TV 수상기"),
}
DOMAINS = ["K-Food", "K-Beauty", "K-Fashion"]


def collect(key: str) -> list[dict]:
    jobs = [(hs, cc, y) for hs in CONTROLS for cc in COUNTRIES for y in YEARS]
    rows: list[dict] = []
    fail = 0
    t0 = time.time()
    print(f"\n대조군 수집 — {len(CONTROLS)}품목 x {len(COUNTRIES)}개국 x "
          f"{len(YEARS)}년 = {len(jobs)}회\n")

    def one(job):
        hs, cc, y = job
        items = fetch(key, hs, y, cnty=cc)
        if items is None:
            return hs, cc, y, -1.0, -1.0
        for it in items:
            if str(it.get("year", "")).strip() in ("총계", "합계", "계"):
                return hs, cc, y, num(it.get("expDlr")), num(it.get("expWgt"))
        return (hs, cc, y,
                sum(num(it.get("expDlr")) for it in items),
                sum(num(it.get("expWgt")) for it in items))

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(one, j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            hs, cc, y, usd, kg = fut.result()
            if usd < 0:
                fail += 1
                continue
            grp, name = CONTROLS[hs]
            rows.append({"hs2022": hs, "group": grp, "name": name,
                         "country": cc, "country_name": COUNTRIES[cc],
                         "year": y, "exp_usd": usd, "exp_kg": kg})
            if i % 30 == 0 or i == len(jobs):
                el = time.time() - t0
                print(f"  {i:>4}/{len(jobs)}  실패 {fail}  "
                      f"남은 {el/i*(len(jobs)-i)/60:.1f}분", flush=True)
    if fail:
        print(f"\n  ! 실패 {fail}건 — 캐시가 남으므로 재실행하면 이어받는다")
    return rows


def load_rows(path: Path, key_fn, year: str) -> dict:
    """(식별자) -> {국가: 구성비}. 비영 국가가 적은 품목은 뺀다."""
    with path.open(encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    acc: dict = defaultdict(lambda: defaultdict(float))
    for r in raw:
        if r["year"] != year:
            continue
        acc[key_fn(r)][r["country"]] += float(r["exp_usd"] or 0)
    out = {}
    for k, d in acc.items():
        tot = sum(d.values())
        if tot > 0 and sum(1 for v in d.values() if v > 0) >= MIN_NONZERO:
            out[k] = {c: v / tot for c, v in d.items()}
    return out


def pair_corrs(shares: dict, pick=None, same_group=None) -> list[float]:
    """품목쌍 상관 목록.

    pick        — 어떤 품목을 쓸지 거르는 술어
    same_group  — True 면 같은 도메인/그룹 쌍만, False 면 다른 쌍만, None 이면 전부
    """
    keys = [k for k in shares if pick is None or pick(k)]
    ctry = sorted({c for k in shares for c in shares[k]})
    out = []
    for a, b in itertools.combinations(keys, 2):
        if same_group is True and a[0] != b[0]:
            continue
        if same_group is False and a[0] == b[0]:
            continue
        x = [shares[a].get(c, 0.0) for c in ctry]
        y = [shares[b].get(c, 0.0) for c in ctry]
        r = spearman(x, y)
        if not math.isnan(r):
            out.append(r)
    return out


def desc(v: list[float]) -> str:
    if len(v) < 3:
        return f"n={len(v)}  (표본 부족)"
    v = sorted(v)
    n = len(v)
    return (f"n={n:<5} 중앙값 {v[n//2]:>6.3f}   "
            f"사분위 [{v[n//4]:.3f}, {v[3*n//4]:.3f}]")


def report(year: str) -> int:
    if not OUT.exists():
        sys.exit(f"{OUT.name} 이 없습니다. 먼저 수집하세요.")
    ctrl = load_rows(OUT, lambda r: (r["group"], r["hs2022"]), year)
    print("\n" + "=" * 74)
    print(f"판정 — 한류 품목쌍 vs 대조군 품목쌍 ({year})\n")

    for g in ("중력", "브랜드"):
        n = sum(1 for k in ctrl if k[0] == g)
        print(f"  {g} 대조군 유효 품목 {n}/{sum(1 for h,(gg,_) in CONTROLS.items() if gg==g)}")
    print()

    lines: list[tuple[str, list[float]]] = []
    hal = None
    if PANEL.exists():
        hal = load_rows(PANEL, lambda r: (r["domain"], r["hs2022"]), year)
        lines.append(("한류 — 전체 품목쌍", pair_corrs(hal)))
        lines.append(("한류 — 도메인 내", pair_corrs(hal, same_group=True)))
        lines.append(("한류 — 도메인 간", pair_corrs(hal, same_group=False)))
    else:
        print(f"  ! {PANEL.name} 이 없어 한류 쪽 비교는 생략합니다.\n")

    ctrl_g = pair_corrs(ctrl, lambda k: k[0] == "중력")
    ctrl_b = pair_corrs(ctrl, lambda k: k[0] == "브랜드")
    lines.append(("대조군 — 순수 중력", ctrl_g))
    lines.append(("대조군 — 브랜드", ctrl_b))

    for label, vals in lines:
        if vals:
            print(f"  {label:<22}{desc(vals)}")
    print()

    if not (hal and ctrl_g):
        print("  판정에는 panel.csv 와 중력 대조군이 모두 필요합니다.")
        return 0

    def med(v):
        v = sorted(v)
        return v[len(v) // 2]

    def boot_med_diff(a, b, n=4000, seed=20260911):
        """두 중앙값 차이의 95% 구간. 쌍 수가 크게 다르므로 점추정만 믿지 않는다."""
        rng = random.Random(seed)
        d = []
        for _ in range(n):
            ra = [a[rng.randrange(len(a))] for _ in range(len(a))]
            rb = [b[rng.randrange(len(b))] for _ in range(len(b))]
            d.append(med(ra) - med(rb))
        d.sort()
        return d[int(0.025 * n)], d[int(0.975 * n)]

    allh = pair_corrs(hal)
    mh, mg = med(allh), med(ctrl_g)
    lo, hi = boot_med_diff(allh, ctrl_g)

    print("=" * 74)
    print(f"  한류 품목쌍 중앙값    {mh:.3f}   (n={len(allh)})")
    print(f"  중력 품목쌍 중앙값    {mg:.3f}   (n={len(ctrl_g)})")
    if ctrl_b:
        print(f"  브랜드 품목쌍 중앙값  {med(ctrl_b):.3f}   (n={len(ctrl_b)}, 중간 채널 참고)")
    print(f"  차이 (한류 − 중력)    {mh - mg:+.3f}   95% [{lo:+.3f}, {hi:+.3f}]\n")

    if lo > 0.05:
        print("  -> 한류 품목이 대조군보다 유의하게 더 닮았다. 국가 구조에 한류")
        print("     고유분이 존재하며, 국가 단위 층(L2)이 정당화된다.")
    elif hi < -0.05:
        print("  -> 대조군이 오히려 더 닮았다. 국가 구성비의 유사성은 한류가 아니라")
        print("     중력 구조가 만든 것이고, 한류 도메인은 그보다 덜 닮았다.")
        print("     검정 1의 상관을 국가 단위 수용의 근거로 쓸 수 없다.")
    elif lo > -0.05 and hi < 0.05:
        print("  -> 두 집단이 사실상 같은 수준으로 닮았다. 높은 상관은 한류 수용이")
        print("     아니라 '한국은 크고 가까운 시장에 많이 판다'는 중력 효과다.")
        print("     검정 1의 결론을 국가 단위 수용의 근거로 쓸 수 없다.")
    else:
        print("  -> 구간이 0 을 걸쳐 판정이 서지 않는다. 대조군 품목을 늘리거나")
        print("     연도를 넓혀 재판정할 것.")

    print("\n  브랜드 대조군의 위치도 함께 보라. 중력 < 브랜드 < 한류 순으로")
    print("  계단을 이루면 '한국산 신뢰'와 '한류'가 구분되는 채널이라는 뜻이다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true", help="6품목 총계만 확인")
    ap.add_argument("--report", action="store_true", help="수집분으로 판정만")
    ap.add_argument("--year", default="2024", help="판정 기준연도")
    args = ap.parse_args()

    if args.report:
        return report(args.year)

    key = find_key()
    if args.probe:
        print("\n대조군 품목 실측 확인 (2024, 전 교역국 총계)\n")
        for hs, (grp, name) in CONTROLS.items():
            items = fetch(key, hs, "2024")
            tot = next((num(i.get("expDlr")) for i in items or []
                        if str(i.get("year", "")).strip() == "총계"), None)
            mark = "o" if tot else "x"
            val = f"{tot/1e6:,.0f}백만$" if tot else "응답 없음"
            print(f"  {mark} {hs}  {grp:<5}{name:<22}{val:>16}")
        print("\n  x 가 있으면 해당 HS 를 CONTROLS 에서 교체하세요.")
        return 0

    rows = collect(key)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hs2022", "group", "name", "country",
                                          "country_name", "year",
                                          "exp_usd", "exp_kg"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n= {OUT.name}  {len(rows):,}행")
    return report(args.year)


if __name__ == "__main__":
    raise SystemExit(main())
