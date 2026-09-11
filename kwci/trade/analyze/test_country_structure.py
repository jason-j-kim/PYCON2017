#!/usr/bin/env python3
"""
검정 1 — 한류 수용은 도메인 단위인가 국가 단위인가

KCI 가 L2(영향력) 층을 폐기한 근거 중 하나는 KWCI 의 L2 가 "도메인을 구분하지
못한다"는 것이었다. 국가 단위로 정규화된 값이 모든 장르 행에 같게 붙으니
층이 아니라 상수라는 지적이다.

그 지적은 "도메인마다 다른 수용층이 있다"는 가정 위에 서 있다. 이 스크립트는
그 가정을 L1 패널로 검정한다. 도메인 간 국가 구성비가 서로 닮았다면 국가
단위 층은 결함이 아니라 구조의 반영이고, 흩어져 있다면 원래 지적이 맞다.

네 단계로 본다
-------------
(1) 도메인 쌍별 국가 구성비 상관 — 연도별 추이
(2) 지배 시장(CN·US·JP) 제외 후 재계산 — 세 나라가 만든 상관인가
(3) 로그 구성비 상관 — 극단값이 만든 상관인가
(4) **도메인 내 품목쌍 vs 도메인 간 품목쌍** — 핵심 판별

(4) 가 결정적이다. 같은 도메인 안의 두 품목이 서로 닮은 정도와, 다른 도메인
품목끼리 닮은 정도가 비슷하면 도메인 구분은 국가 구조에 대해 정보를 갖지
않는다. 집계 수준의 높은 상관은 큰 시장 몇 개가 만든 착시일 수 있으므로
품목 수준에서 다시 봐야 한다.

한계
----
이 검정은 필요조건이지 충분조건이 아니다. 상관이 높은 이유가 한류의 국가 단위
수용일 수도 있고, 단순히 "한국은 크고 가까운 시장에 많이 판다"는 중력
효과일 수도 있다. 이를 가르려면 **문화 무관 품목(반도체·석유·선박)의 국가
구성비와 대조**해야 하며, 그 자료는 이 패널에 없다(관세청 API 재수집 필요).
--gravity-note 로 그 설계를 출력한다.

사용법
------
  python test_country_structure.py                 # 전체 검정
  python test_country_structure.py --panel PATH    # 패널 경로 지정
  python test_country_structure.py --gravity-note  # 중력 대조 설계만 출력
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PANEL = HERE.parent / "data" / "processed" / "panel.csv"
DOMAINS = ["K-Food", "K-Beauty", "K-Fashion"]
BIG = {"CN", "US", "JP"}          # 지배 시장 — 제외 검정용
MIN_NONZERO = 5                   # 품목 수준 상관에 필요한 최소 비영 국가 수


# ── 통계 도구 ───────────────────────────────────────────────────────
def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return math.nan
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else math.nan


def ranks(v: list[float]) -> list[float]:
    """동점은 평균 순위로 처리한다. 0 이 많은 계열에서 중요하다."""
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(x: list[float], y: list[float]) -> float:
    return pearson(ranks(x), ranks(y))


def boot_ci(x: list[float], y: list[float], n: int = 2000,
            seed: int = 20260911) -> tuple[float, float]:
    rng = random.Random(seed)
    m = len(x)
    vals = []
    for _ in range(n):
        idx = [rng.randrange(m) for _ in range(m)]
        r = pearson([x[i] for i in idx], [y[i] for i in idx])
        if not math.isnan(r):
            vals.append(r)
    if len(vals) < 100:
        return math.nan, math.nan
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


# ── 데이터 ──────────────────────────────────────────────────────────
def load(panel: Path) -> list[dict]:
    if not panel.exists():
        sys.exit(f"{panel} 를 찾을 수 없습니다. --panel 로 경로를 지정하세요.")
    with panel.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["exp_usd"] = float(r["exp_usd"] or 0)
    return rows


def domain_shares(rows, dom, year, drop=frozenset()) -> dict[str, float]:
    d = defaultdict(float)
    for r in rows:
        if r["domain"] == dom and r["year"] == year and r["country"] not in drop:
            d[r["country"]] += r["exp_usd"]
    tot = sum(d.values())
    return {k: v / tot for k, v in d.items()} if tot else {}


def item_shares(rows, year) -> dict[tuple[str, str], dict[str, float]]:
    """(도메인, HS) -> 국가 구성비. 비영 국가가 적은 품목은 뺀다."""
    acc: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        if r["year"] == year:
            acc[(r["domain"], r["hs2022"])][r["country"]] += r["exp_usd"]
    out = {}
    for key, d in acc.items():
        tot = sum(d.values())
        if tot <= 0 or sum(1 for v in d.values() if v > 0) < MIN_NONZERO:
            continue
        out[key] = {k: v / tot for k, v in d.items()}
    return out


def align(a: dict, b: dict) -> tuple[list[float], list[float]]:
    ks = sorted(set(a) | set(b))
    return [a.get(k, 0.0) for k in ks], [b.get(k, 0.0) for k in ks]


# ── 검정 ────────────────────────────────────────────────────────────
def step1(rows, years) -> None:
    print("\n" + "=" * 74)
    print("(1) 도메인 쌍별 국가 구성비 상관 — 연도별 추이\n")
    print(f"  {'연도':<7}{'도메인 쌍':<26}{'피어슨':>9}{'스피어만':>11}"
          f"{'95% CI(피어슨)':>22}")
    for y in years:
        for a, b in itertools.combinations(DOMAINS, 2):
            x, yy = align(domain_shares(rows, a, y), domain_shares(rows, b, y))
            lo, hi = boot_ci(x, yy)
            print(f"  {y:<7}{a + ' × ' + b:<26}{pearson(x, yy):>9.3f}"
                  f"{spearman(x, yy):>11.3f}{f'[{lo:.2f}, {hi:.2f}]':>22}")
        print()


def step2(rows, year) -> None:
    print("=" * 74)
    print(f"(2) 지배 시장 {'·'.join(sorted(BIG))} 제외 — {year}\n")
    print(f"  {'도메인 쌍':<26}{'전체':>10}{'3국 제외':>12}{'차이':>10}")
    for a, b in itertools.combinations(DOMAINS, 2):
        xf, yf = align(domain_shares(rows, a, year), domain_shares(rows, b, year))
        xd, yd = align(domain_shares(rows, a, year, BIG),
                       domain_shares(rows, b, year, BIG))
        rf, rd = pearson(xf, yf), pearson(xd, yd)
        print(f"  {a + ' × ' + b:<26}{rf:>10.3f}{rd:>12.3f}{rd - rf:>+10.3f}")
    print("\n  세 나라를 빼도 상관이 유지되면 지배 시장이 만든 착시가 아니다.")


def step3(rows, year) -> None:
    print("\n" + "=" * 74)
    print(f"(3) 로그 구성비 상관 — 극단값 완화 ({year})\n")
    print(f"  {'도메인 쌍':<26}{'원자료':>10}{'로그':>10}")
    for a, b in itertools.combinations(DOMAINS, 2):
        sa, sb = domain_shares(rows, a, year), domain_shares(rows, b, year)
        x, yy = align(sa, sb)
        eps = 1e-6
        lx = [math.log(v + eps) for v in x]
        ly = [math.log(v + eps) for v in yy]
        print(f"  {a + ' × ' + b:<26}{pearson(x, yy):>10.3f}{pearson(lx, ly):>10.3f}")
    print("\n  로그에서도 높으면 소수 대형 시장이 아니라 순위 구조 전반이 닮은 것이다.")


def step4(rows, year) -> None:
    """핵심 판별 — 도메인 내 품목쌍과 도메인 간 품목쌍의 상관 분포 비교."""
    print("\n" + "=" * 74)
    print(f"(4) 품목 수준 — 도메인 내 vs 도메인 간 ({year})\n")
    items = item_shares(rows, year)
    by_dom = defaultdict(list)
    for (dom, hs) in items:
        by_dom[dom].append((dom, hs))
    for d in DOMAINS:
        print(f"  {d:<11}{len(by_dom[d]):>3}개 품목 (비영 국가 {MIN_NONZERO}개 이상)")

    within, across = [], []
    keys = list(items)
    for k1, k2 in itertools.combinations(keys, 2):
        x, y = align(items[k1], items[k2])
        r = spearman(x, y)
        if math.isnan(r):
            continue
        (within if k1[0] == k2[0] else across).append(r)

    def desc(v: list[float]) -> str:
        v = sorted(v)
        n = len(v)
        med = v[n // 2]
        q1, q3 = v[n // 4], v[3 * n // 4]
        return f"n={n:<6} 중앙값 {med:>6.3f}   사분위 [{q1:.3f}, {q3:.3f}]"

    print(f"\n  도메인 내 품목쌍   {desc(within)}")
    print(f"  도메인 간 품목쌍   {desc(across)}")
    gap = (sorted(within)[len(within) // 2] - sorted(across)[len(across) // 2])
    print(f"\n  중앙값 차이(내부 − 외부)  {gap:+.3f}")
    print("\n  차이가 0 에 가까우면 도메인 구분은 국가 구조에 대해 정보를 갖지")
    print("  않는다 — 국가 단위 층이 정당화된다. 내부가 뚜렷이 높으면 도메인별")
    print("  수용층이 실재하므로 국가 상수 층은 해상도 손실이다.")


GRAVITY = """
================================================================================
중력 대조 — 이 검정이 아직 답하지 못한 것

도메인 간 상관이 높은 이유는 둘 중 하나다.

  (가) 한류 수용이 국가 단위로 묶인다        → L2 국가층이 정당
  (나) 한국이 크고 가까운 시장에 많이 판다    → 중력 효과, 한류와 무관

이 패널만으로는 가르지 못한다. 세 도메인이 모두 한류 품목이기 때문이다.
판별하려면 **문화 무관 품목**의 국가 구성비를 같은 방식으로 구해 대조한다.

  대조군 HS (관세청 nitemtrade, 같은 15개국 · 같은 연도)
    854231  메모리 반도체      — 문화 무관, 전형적 중력 품목
    271019  석유제품
    890120  탱커
    870323  승용차 (1500~3000cc)

  판정
    대조군끼리의 상관 ≈ 한류 도메인끼리의 상관   → (나) 중력 효과
    대조군 상관이 뚜렷이 낮음                    → (가) 한류 고유 구조

  수집 비용: 4품목 × 15국 × 2년 = 120회 호출, 캐시 포함 약 1분.
  collect_stage_b.py 의 fetch_country() 를 그대로 쓰면 된다.
================================================================================
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", default=str(DEFAULT_PANEL), help="panel.csv 경로")
    ap.add_argument("--year", default="2024", help="단면 검정 기준연도")
    ap.add_argument("--gravity-note", action="store_true", help="중력 대조 설계만 출력")
    args = ap.parse_args()

    if args.gravity_note:
        print(GRAVITY)
        return 0

    rows = load(Path(args.panel))
    years = sorted({r["year"] for r in rows})
    print(f"패널 {len(rows):,}행 · 국가 {len({r['country'] for r in rows})}"
          f" · 연도 {years[0]}~{years[-1]}")

    step1(rows, years)
    step2(rows, args.year)
    step3(rows, args.year)
    step4(rows, args.year)
    print(GRAVITY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
