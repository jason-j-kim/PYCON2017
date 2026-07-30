#!/usr/bin/env python3
"""
KWCI L1 — S0·S1: 품목 후보 유니버스 구축 및 동결

  S0  최종소비재 필터   hs_bec5.csv 에서 bec_class == 'consumption' 만
  S1  도메인 매핑       K-Food / K-Beauty / K-Fashion HS 대역과 교집합

산출되는 item_master.csv 가 이후 S2(RCA)·S3(패널회귀)·S4(문화 프리미엄)의
입력이자, 사전등록(pre-registration) 대상이다. 검정 결과를 보고 후보를 손대면
S3 전체가 무의미해지므로, 이 파일은 확정 후 해시로 동결한다.

전제: fetch_reference_tables.py 를 먼저 돌려 hs_bec5.csv 가 있어야 한다.
      hs_names.csv 가 있으면 품목명이 함께 붙는다(사람 검토용, 없어도 동작).

사용법
------
  python build_item_master.py              # 후보 생성 + 요약
  python build_item_master.py --freeze     # 생성 후 해시 동결
  python build_item_master.py --review K-Fashion   # 도메인 전체 목록 출력
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEC = HERE / "hs_bec5.csv"
NAMES = HERE / "hs_names.csv"
OUT = HERE / "item_master.csv"
LOCK = HERE / "item_master.lock.json"

# --- S1 도메인 대역 -------------------------------------------------------
#
# 여기 적힌 것은 "확정 품목"이 아니라 후보 유니버스다. 실제 대표 품목은
# S2(RCA>=1) -> S3(한류 반응성 회귀+위약검정) -> S4(문화 프리미엄)로 좁힌다.
#
# 대역 자체는 우리가 발명하지 않고 공식 분류를 채택한다:
#   K-Food    aT K-Food+ 품목군 / 농식품부 수출통계 분류 (HS 02~22 식품 章)
#   K-Beauty  대한화장품협회 수출 분류 / MTI 소비재 (HS 33 章 + 부속)
#   K-Fashion KOTRA·산업부 소비재 수출 분류 / MTI 의류·잡화
#
# 접두(prefix) 매칭이며 2자리(章) 또는 4자리(호) 단위로 적는다.
DOMAINS: dict[str, dict] = {
    "K-Food": {
        "prefixes": [
            "02", "03", "04",          # 육류 · 어패류 · 낙농/계란/꿀
            "07", "08", "09", "10",    # 채소 · 과실 · 커피/차/향신료 · 곡물
            "11", "12",                # 제분 · 종자(인삼 1211.20)
            "15", "16", "17", "18",    # 유지 · 육어류조제품 · 당류 · 코코아
            "19", "20", "21", "22",    # 곡물조제품(라면) · 채소과실조제품(김치)
                                       # 기타조제식료품(소스/조미김) · 음료(소주)
        ],
        "watch": ["190230", "200599", "121221", "210390", "220890", "121120"],
    },
    "K-Beauty": {
        "prefixes": [
            "3303", "3304", "3305", "3306", "3307",   # 향수·기초/색조·두발·구강·기타
            "340130",                                  # 세안용 비누·클렌저
            "9616",                                    # 화장용 분무기·퍼프
        ],
        "watch": ["330499", "330510", "330790", "330410"],
    },
    "K-Fashion": {
        "prefixes": [
            "61", "62",                # 편물 의류 · 직물 의류
            "64", "65",                # 신발 · 모자
            "4202",                    # 가방·케이스
            "7113", "7117",            # 귀금속 장신구 · 모조 장신구
            "9003", "9004",            # 안경테 · 안경/선글라스
        ],
        "watch": ["620342", "610910", "640399", "420292", "711790"],
    },
}


# --- S0 예외 -------------------------------------------------------------
#
# BEC의 end-use는 "경제적 기능"(투입재냐 최종재냐)을 잰다. 그래서 추가 가공의
# 투입재가 될 수 있는 1차 농수산물은 소비재로 잡히지 않는다. 이 기준은 그
# 자체로 타당하지만, 한류 소비재 지수의 목적과는 어긋나는 지점이 생긴다.
#
# 예외를 인정하되 세 조건을 건다. 그래야 자의적 끼워넣기가 되지 않는다.
#   (1) 외부 권위에 앵커  — aT K-Food+ 공식 품목군에 포함될 것
#   (2) 사전등록          — S3 검정 전에 확정하고 동결할 것
#   (3) 표시              — s0_override 플래그로 남겨 민감도 분석이 가능할 것
#
# S3(한류 반응성 회귀)는 이 예외 품목에도 똑같이 적용된다. 반응이 없으면
# 예외로 넣었더라도 Tier 1에 오르지 못한다 — 예외는 후보 자격일 뿐이다.
EXCEPTIONS: dict[str, tuple[str, str]] = {
    "121221": ("K-Food", "마른김 — aT K-Food+ 핵심 품목. BEC는 1차 수산물을 "
                         "가공 투입재로 보나 실제로는 최종소비재로 수출된다"),
    "121120": ("K-Food", "인삼(수삼·백삼) — aT K-Food+ 핵심 품목. BEC는 약용식물 "
                         "원물을 중간재로 분류"),
}


def load_bec() -> list[dict]:
    if not BEC.exists():
        raise SystemExit(
            f"{BEC.name} 이 없습니다. 먼저 실행하세요:\n"
            f"  python fetch_reference_tables.py"
        )
    with BEC.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_names() -> dict[str, str]:
    if not NAMES.exists():
        return {}
    with NAMES.open(encoding="utf-8") as f:
        return {r["hs"]: r["name"] for r in csv.DictReader(f)}


def domain_of(hs: str) -> str | None:
    """가장 긴(=가장 구체적인) 접두가 이기도록 매칭한다."""
    best, best_len = None, -1
    for name, spec in DOMAINS.items():
        for p in spec["prefixes"]:
            if hs.startswith(p) and len(p) > best_len:
                best, best_len = name, len(p)
    return best


def build(rows: list[dict], names: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        hs, cls = r["hs"], r["bec_class"]
        override = hs in EXCEPTIONS
        if cls != "consumption" and not override:      # S0 (+예외)
            continue
        dom = EXCEPTIONS[hs][0] if override else domain_of(hs)   # S1
        if not dom:
            continue
        out.append({
            "domain": dom,
            "hs2022": hs,
            "name": names.get(hs, ""),
            "bec": r["bec"],
            "bec_class": cls,
            "tier": "candidate",          # S2~S4 통과 전까지 전부 관찰 등급
            "watch": "Y" if hs in DOMAINS[dom]["watch"] else "",
            "s0_override": "Y" if override else "",
        })
    return sorted(out, key=lambda x: (x["domain"], x["hs2022"]))


def dropped(rows: list[dict], names: dict[str, str],
            only: str | None = None) -> list[dict]:
    """도메인 대역 안에 있으나 S0(소비재 필터)에서 탈락한 품목.

    S0가 무엇을 버렸는지 눈에 보여야 한다. 김·인삼처럼 대표 품목이
    조용히 사라지는 것이 이 지수에서 가장 위험한 실패다.
    """
    out = []
    for r in rows:
        hs, cls = r["hs"], r["bec_class"]
        if cls == "consumption" or hs in EXCEPTIONS:
            continue
        dom = domain_of(hs)
        if not dom or (only and dom.lower() != only.lower()):
            continue
        out.append({"domain": dom, "hs2022": hs, "bec_class": cls,
                    "name": names.get(hs, "")})
    return sorted(out, key=lambda x: (x["domain"], x["hs2022"]))


def report(rows: list[dict], all_bec: list[dict], names: dict[str, str]) -> None:
    total = len(all_bec)
    cons = sum(1 for r in all_bec if r["bec_class"] == "consumption")
    print(f"\nS0  최종소비재 필터   {total:,} -> {cons:,}")
    print(f"S1  도메인 매핑       {cons:,} -> {len(rows):,}\n")

    for dom in DOMAINS:
        sel = [r for r in rows if r["domain"] == dom]
        chapters = sorted({r['hs2022'][:2] for r in sel})
        print(f"  {dom:<10} {len(sel):>5}개   章 {' '.join(chapters)}")

    # 대표로 지목해 둔 품목(watch)이 실제로 후보에 들어왔는지 확인.
    # 빠졌다면 S0에서 걸러졌거나 대역이 잘못된 것이므로 즉시 드러나야 한다.
    print("\n  주요 품목 점검 (S0·S1 통과 여부)")
    got = {r["hs2022"] for r in rows}
    missing_any = False
    for dom, spec in DOMAINS.items():
        for hs in spec["watch"]:
            ok = hs in got
            missing_any |= not ok
            label = names.get(hs, "")[:42]
            print(f"    {'o' if ok else 'X'} {dom:<10} {hs}  {label}")
    if missing_any:
        print("\n    X 표시 품목은 S0(소비재 아님)에서 탈락했거나 대역이 어긋난 것입니다.")
        print("      hs_bec5.csv 에서 해당 HS의 bec_class 를 확인하세요.")

    ov = [r for r in rows if r["s0_override"]]
    if ov:
        print(f"\n  S0 예외 {len(ov)}건 (BEC는 비소비재로 보나 후보로 인정)")
        for r in ov:
            print(f"    · {r['domain']:<10} {r['hs2022']}  {r['name'][:40]}")
            print(f"      사유: {EXCEPTIONS[r['hs2022']][1]}")

    drop = dropped(all_bec, names)
    print(f"\n  S0에서 탈락한 도메인 대역 품목: {len(drop):,}건"
          f"  (--dropped 로 확인)")

    if not names:
        print("\n  ! hs_names.csv 가 없어 품목명이 비어 있습니다.")
        print("    fetch_reference_tables.py 재실행 시 HS 품목명을 함께 받습니다.")


def freeze(rows: list[dict]) -> None:
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    LOCK.write_text(json.dumps({
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": OUT.name,
        "sha256": digest,
        "rows": len(rows),
        "by_domain": {d: sum(1 for r in rows if r["domain"] == d) for d in DOMAINS},
        "note": "사전등록: S2~S4 검정 결과를 보고 이 후보를 수정하면 검정이 무효가 된다.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n동결 완료  {LOCK.name}\n  sha256 {digest}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--freeze", action="store_true", help="생성 후 해시로 동결")
    ap.add_argument("--review", metavar="DOMAIN", help="해당 도메인 전체 목록 출력")
    ap.add_argument("--dropped", nargs="?", const="", metavar="DOMAIN",
                    help="S0에서 탈락한 도메인 대역 품목 목록 (章별)")
    args = ap.parse_args()

    all_bec = load_bec()
    names = load_names()
    rows = build(all_bec, names)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else
                           ["domain", "hs2022", "name", "bec", "bec_class",
                            "tier", "watch"])
        w.writeheader()
        w.writerows(rows)

    report(rows, all_bec, names)
    print(f"\n= {OUT.name}  {len(rows):,}개 후보")

    if args.review:
        sel = [r for r in rows if r["domain"].lower() == args.review.lower()]
        if not sel:
            print(f"\n'{args.review}' 도메인이 없습니다: {list(DOMAINS)}")
            return 1
        print(f"\n[{args.review}] {len(sel)}개")
        for r in sel:
            print(f"  {r['hs2022']}  {r['name'][:60]}")

    if args.dropped is not None:
        drop = dropped(all_bec, names, args.dropped or None)
        path = HERE / "dropped_by_s0.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["domain", "hs2022",
                                              "bec_class", "name"])
            w.writeheader()
            w.writerows(drop)

        print(f"\n[S0 탈락 품목] {len(drop):,}건 — 도메인 대역에는 있으나 "
              f"BEC가 최종소비재로 보지 않은 것")
        print(f"  전체 목록 -> {path.name}  (엑셀로 열어 검토)\n")

        from collections import Counter
        by_ch = Counter((r["domain"], r["hs2022"][:2]) for r in drop)
        cur = None
        for (dom, ch), n in sorted(by_ch.items()):
            if dom != cur:
                print(f"  {dom}")
                cur = dom
            sample = [r["name"][:38] for r in drop
                      if r["domain"] == dom and r["hs2022"].startswith(ch)][:2]
            print(f"    章 {ch}  {n:>4}건   {' / '.join(sample)}")

        print("\n  aT K-Food+ 등 공식 품목군에 속한 것이 있으면 "
              "EXCEPTIONS 에 사유와 함께 추가하세요.")

    if args.freeze:
        freeze(rows)
    else:
        print("\n검토 후 확정되면:  python build_item_master.py --freeze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
