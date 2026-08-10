#!/usr/bin/env python3
"""
KWCI L3 — 통합 사전 잠정판 조립

여섯 도메인의 사전을 한 파일로 합친다. 출처가 셋이고 검증 수준이 다르므로,
합치는 것 자체보다 **어느 행이 어디서 왔고 어디까지 검증됐는지를 남기는
것**이 이 스크립트의 목적이다.

출처
----
  (A) 기존 486행 사전   KPOP 396 · KVIDEO 54 · KTOURISM 36
      실증을 통과한 자료다. Trends DOM 에서 MID 를 뽑고 신호 유무를 확인한
      결과가 들어 있다. KPOP·KVIDEO 는 그대로 승계한다.

  (B) tourism/ktourism_dict.csv   178행
      (A) 의 KTOURISM 36행을 대체한다. 36행 중 33행이 영어 질의라 비영어권
      에서 영어 검색 가능 소수층을 재고 있었기 때문이다. 다만 (A) 는 실증을
      통과했고 (B) 는 통과하지 않았으므로 provenance 상 후퇴다.
      --keep-old-tourism 으로 되돌릴 수 있다.

  (C) consumer/kconsumer_dict.csv   895행
      KFOOD·KBEAUTY·KFASHION. (A) 에 없던 도메인이라 충돌이 없다.

잠정판인 이유
------------
(B)(C) 1,073행은 **Trends 실측을 한 번도 거치지 않았다.** 신호가 있는지,
표기가 그 나라에서 실제로 쓰이는지, TOPIC 후보에 MID 가 붙는지 모른다.
그래서 전 행이 final_review_status = PENDING_EMPIRICAL_VALIDATION 이다.

이 파일을 그대로 분석에 쓰면 안 된다. 실측(3단계)을 거쳐 무신호 행을 걸러낸
뒤라야 계열이 된다. 인수받는 연구자가 가장 먼저 할 일이 그것이다.

산출
----
  dist/KWCI_dict_provisional.csv   통합 사전 (40열)
  dist/MANIFEST.md                 출처·해시·검증 상태·다음 단계

사용법
------
  python build_master_dict.py --base <486행 사전.csv>
  python build_master_dict.py --base ... --keep-old-tourism
  python build_master_dict.py --base ... --status     # 조립 없이 상태만
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import COUNTRIES, HEADER                    # noqa: E402

DIST = HERE / "dist"
OUT = DIST / "KWCI_dict_provisional.csv"
MANIFEST = DIST / "MANIFEST.md"

BUILDERS = [
    (HERE / "tourism" / "build_tourism_dict.py", HERE / "tourism" / "ktourism_dict.csv"),
    (HERE / "consumer" / "build_consumer_dict.py",
     HERE / "consumer" / "kconsumer_dict.csv"),
]

# 기존 사전 기본 탐색 위치. --base 로 직접 줄 수 있다.
BASE_HINTS = [
    HERE / "base" / "KWCI_final_topic_keyword_dictionary_486.csv",
    HERE.parent.parent / "KWCI_final_topic_keyword_dictionary_486.csv",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def regenerate() -> None:
    """도메인 사전을 다시 만들어 최신 코드와 어긋나지 않게 한다."""
    for script, _ in BUILDERS:
        r = subprocess.run([sys.executable, str(script)],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{script.name} 실패\n{r.stdout}\n{r.stderr}")
    print("  도메인 사전 재생성 완료")


def find_base(given: str | None) -> Path:
    if given:
        p = Path(given)
        if not p.exists():
            sys.exit(f"{p} 를 찾을 수 없습니다.")
        return p
    for p in BASE_HINTS:
        if p.exists():
            return p
    sys.exit("기존 486행 사전을 찾지 못했습니다. --base 로 경로를 주세요.\n"
             "  예: --base ..\\KWCI_final_topic_keyword_dictionary_486.csv")


def assemble(base: Path, keep_old_tourism: bool) -> tuple[list[dict], dict]:
    old = read(base)
    if list(old[0]) != HEADER:
        sys.exit("기존 사전의 열 구성이 다릅니다. 40열 스키마를 확인하세요.")

    tour = read(BUILDERS[0][1])
    cons = read(BUILDERS[1][1])
    new_domains = {r["domain_code"] for r in cons}

    keep = [r for r in old if r["domain_code"] not in new_domains
            and (keep_old_tourism or r["domain_code"] != "KTOURISM")]
    add = ([] if keep_old_tourism else tour) + cons
    rows = keep + add

    prov = {
        "base_kept": len(keep),
        "tourism_new": 0 if keep_old_tourism else len(tour),
        "consumer_new": len(cons),
        "dropped_old_tourism": 0 if keep_old_tourism
        else sum(1 for r in old if r["domain_code"] == "KTOURISM"),
    }
    return rows, prov


def status(rows: list[dict]) -> None:
    print(f"\n{'=' * 74}\n통합 사전 잠정판  {len(rows):,}행\n")
    print(f"  {'도메인':<12}{'행':>6}  {'출처':<24}{'검증'}")
    by = defaultdict(list)
    for r in rows:
        by[r["domain_code"]].append(r)
    for d, rs in sorted(by.items(), key=lambda x: -len(x[1])):
        src = Counter(r["source_record_set"] or "(기존 사전)" for r in rs)
        ok = sum(1 for r in rs if r["empirical_validation_status"]
                 not in ("NOT_YET_TESTED", ""))
        mark = "실증완료" if ok == len(rs) else f"미실증 {len(rs) - ok}"
        print(f"  {d:<12}{len(rs):>6}  {list(src)[0][:22]:<24}{mark}")

    ok = sum(1 for r in rows if r["empirical_validation_status"]
             not in ("NOT_YET_TESTED", ""))
    mid = sum(1 for r in rows if r["topic_mid"])
    topic_pending = sum(1 for r in rows
                        if r["technical_status"] == "PENDING_TOPIC_EXTRACTION")
    print(f"\n  실증 통과      {ok:>5}행  ({ok / len(rows) * 100:.0f}%)")
    print(f"  실증 대기      {len(rows) - ok:>5}행  ← 인수 연구자의 1순위 작업")
    print(f"  MID 보유       {mid:>5}행")
    print(f"  MID 추출 대기  {topic_pending:>5}행  (TOPIC 후보)")
    print(f"\n  국가 {len(COUNTRIES)}  ·  언어 11  ·  중국 제외(Trends 차단)")
    langs = Counter(r["query_language"] for r in rows)
    print("  언어별  " + "  ".join(f"{k}:{v}" for k, v in langs.most_common()))


def manifest(rows: list[dict], base: Path, prov: dict, keep_old: bool) -> None:
    by = Counter(r["domain_code"] for r in rows)
    ok = sum(1 for r in rows if r["empirical_validation_status"]
             not in ("NOT_YET_TESTED", ""))
    lines = [
        "# KWCI L3 통합 토픽·키워드 사전 — 잠정판",
        "",
        f"**생성 {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M %Z')}"
        f" · {len(rows):,}행 · {len(COUNTRIES)}개국 · 11개 언어**",
        "",
        "> **이 파일을 그대로 분석에 쓰지 마십시오.** 1,073행이 Trends 실측을",
        "> 거치지 않았습니다. 신호 유무·표기 타당성·MID 존재가 전부 미확인입니다.",
        "> 실측으로 무신호 행을 걸러낸 뒤라야 계열이 됩니다.",
        "",
        "## 구성",
        "",
        "| 도메인 | 행 | 출처 | 검증 |",
        "|---|---|---|---|",
    ]
    src_label = {
        "KPOP": ("기존 486행 사전", "실증 통과"),
        "KVIDEO": ("기존 486행 사전", "실증 통과"),
        "KTOURISM": ("기존 486행 사전" if keep_old else "신규 (의도어 문법)",
                     "실증 통과" if keep_old else "**미실증**"),
        "KFOOD": ("신규 (조합 생성)", "**미실증**"),
        "KBEAUTY": ("신규 (조합 생성)", "**미실증**"),
        "KFASHION": ("신규 (조합 생성)", "**미실증**"),
    }
    for d, n in by.most_common():
        s, v = src_label.get(d, ("?", "?"))
        lines.append(f"| {d} | {n:,} | {s} | {v} |")
    lines += [
        f"| **합계** | **{len(rows):,}** | | 실증 {ok} / 대기 {len(rows) - ok} |",
        "",
        "## 출처 파일",
        "",
        "| 파일 | sha256 |",
        "|---|---|",
        f"| `{base.name}` | `{sha(base)[:16]}…` |",
        f"| `tourism/ktourism_dict.csv` | `{sha(BUILDERS[0][1])[:16]}…` |",
        f"| `consumer/kconsumer_dict.csv` | `{sha(BUILDERS[1][1])[:16]}…` |",
        "",
        "## 조립 내역",
        "",
        f"- 기존 사전에서 승계: {prov['base_kept']:,}행",
        f"- 관광 신규: {prov['tourism_new']:,}행"
        + (f" (기존 {prov['dropped_old_tourism']}행 대체)"
           if prov["dropped_old_tourism"] else ""),
        f"- 소비재 신규: {prov['consumer_new']:,}행",
        "",
        "## 상태 판독법",
        "",
        "행마다 다음 열로 검증 수준을 읽습니다.",
        "",
        "| 열 | 값 | 뜻 |",
        "|---|---|---|",
        "| `empirical_validation_status` | `EMPIRICALLY_VALIDATED` | Trends 실측 통과 |",
        "| | `NOT_YET_TESTED` | **미실측** |",
        "| `technical_status` | `PENDING_TOPIC_EXTRACTION` | MID 추출 대상 |",
        "| | `PENDING_DOM_EXTRACTION` | 신호 유무만 확인 |",
        "| `selection_basis` | `EXPORT_REFERENCED` | 수출 품목이 범주를 지정 |",
        "| | `MODE_GRAMMAR` / `RULE_GRAMMAR` | 소비양식 문법 (설계 재량 있음) |",
        "| `extraction_method` | `COMPOSED` | 원산지×명사 조합 생성 |",
        "| | `ATOMIC_LEXEME` | 외래어 개별 표기 |",
        "| `ambiguity_flag` | `JP_DOMESTIC_COUNTERPART` | 일본 자국 대응물 오염 |",
        "| `remaining_risk` | (자유 서술) | 그 개념이 못 잡는 것 |",
        "",
        "## 재생성",
        "",
        "```",
        "python build_master_dict.py --base <486행 사전.csv>",
        "```",
        "",
        "도메인 사전을 먼저 다시 만든 뒤 합칩니다. 결정론적이라 같은 입력이면",
        "같은 해시가 나옵니다.",
        "",
        "자세한 설계 근거는 `docs/00_인수인계.md` 와 `docs/01~03` 을 보십시오.",
        "",
    ]
    MANIFEST.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="기존 486행 사전 경로")
    ap.add_argument("--keep-old-tourism", action="store_true",
                    help="관광을 기존 36행(영어 질의)으로 유지")
    ap.add_argument("--status", action="store_true", help="조립 없이 상태만 출력")
    args = ap.parse_args()

    base = find_base(args.base)
    print(f"  기존 사전  {base.name}")
    regenerate()
    rows, prov = assemble(base, args.keep_old_tourism)
    status(rows)
    if args.status:
        return 0

    DIST.mkdir(exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    manifest(rows, base, prov, args.keep_old_tourism)
    print(f"\n= {OUT.relative_to(HERE)}   sha256 {sha(OUT)[:16]}…")
    print(f"= {MANIFEST.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
