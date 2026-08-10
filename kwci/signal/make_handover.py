#!/usr/bin/env python3
"""
KWCI L3 — 인수인계 zip 묶기

이어받는 연구자가 이 zip 하나만 받으면 작업을 시작할 수 있게 묶는다.
사전만 넣으면 재생성이 안 되고, 코드만 넣으면 무엇을 재는지 알 수 없다.
넷을 다 넣는다 — 산출물 · 근거 문서 · 재생성 코드 · 회귀의 종속변수.

  README.md              인수인계 문서 (가장 먼저 읽을 것)
  KWCI_dict_provisional.csv   통합 사전 1,523행  ← 산출물
  MANIFEST.md            출처·해시·검증 상태
  docs/                  도메인별 설계 근거
  code/                  재생성 코드 일체
  source/                기존 486행 사전 (재생성 입력)
  l1/                    L1 패널 — S3 회귀의 종속변수

L1 자료가 없으면 그 부분만 빼고 묶되, MANIFEST 에 빠졌다고 적는다.
조용히 빠지면 받는 쪽이 없는 줄 모른다.

사용법
------
  python make_handover.py --base <486행 사전.csv>
  python make_handover.py --base ... --l1 <panel.csv 가 있는 폴더>
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRADE = HERE.parent / "trade"
STAGE = HERE / "dist" / "_handover"
ZIP = HERE / "dist" / "KWCI_L3_사전_인수인계.zip"

DOCS = [
    ("docs/00_인수인계.md", "README.md"),
    ("docs/01_관광_키워드사전_설계.md", "docs/01_관광_사전_설계.md"),
    ("docs/02_푸드_키워드사전_설계.md", "docs/02_푸드_사전_설계.md"),
    ("docs/03_소비재통합_키워드사전_설계.md", "docs/03_소비재통합_사전_설계.md"),
]
CODE = [
    "build_master_dict.py", "make_handover.py", "lexicon.py", "common.py",
    "tourism/build_tourism_dict.py",
    "consumer/build_consumer_dict.py",
    "food/build_food_dict.py",
]
# 도메인별 사전도 넣는다. 재생성 가능하지만 받자마자 열어볼 수 있어야 한다.
DICTS = [
    "tourism/ktourism_dict.csv",
    "consumer/kconsumer_dict.csv",
    "food/kfood_dict.csv",
]
# S3 회귀의 종속변수. 전체 L1 배포본은 별도 zip 이므로 필요한 것만 넣는다.
L1 = ["panel.csv", "l1_series.csv", "l1_cross.csv", "l1_diversity.csv",
      "top_items.csv"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="기존 486행 사전 경로")
    ap.add_argument("--l1", help="L1 processed 폴더 (기본: kwci/trade/data/processed)")
    args = ap.parse_args()

    base = Path(args.base)
    if not base.exists():
        sys.exit(f"{base} 를 찾을 수 없습니다.")

    # 사전을 먼저 최신 코드로 다시 만든다.
    r = subprocess.run([sys.executable, str(HERE / "build_master_dict.py"),
                        "--base", str(base)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"통합 조립 실패\n{r.stdout}\n{r.stderr}")
    print(r.stdout.rstrip())

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    added: list[tuple[str, Path]] = []

    def put(src: Path, rel: str) -> None:
        dst = STAGE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        added.append((rel, dst))

    put(HERE / "dist" / "KWCI_dict_provisional.csv", "KWCI_dict_provisional.csv")
    put(HERE / "dist" / "MANIFEST.md", "MANIFEST.md")
    for src, rel in DOCS:
        put(HERE / src, rel)
    for rel in CODE:
        put(HERE / rel, f"code/{rel}")
    for rel in DICTS:
        put(HERE / rel, f"code/{rel}")
    # 업로드 경로에서 붙은 해시 접두어(ef23b4c0-...)를 떼고 넣는다.
    base_name = re.sub(r"^[0-9a-f]{6,}-", "", base.name)
    put(base, f"source/{base_name}")

    l1dir = Path(args.l1) if args.l1 else TRADE / "data" / "processed"
    missing_l1 = []
    for name in L1:
        p = l1dir / name
        if p.exists():
            put(p, f"l1/{name}")
        else:
            missing_l1.append(name)

    # 봉투 — 무엇이 들었고 무엇이 빠졌는지
    lines = [
        "# KWCI L3 사전 인수인계 — 꾸러미 내역",
        "",
        f"**{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M %Z')}**",
        "",
        "`README.md` 를 먼저 읽으십시오. 이 문서는 파일 목록입니다.",
        "",
        "## 들어 있는 것",
        "",
        "| 파일 | 크기 | sha256 |",
        "|---|---|---|",
    ]
    for rel, p in added:
        lines.append(f"| `{rel}` | {p.stat().st_size:,} B | `{sha(p)[:16]}…` |")

    lines += ["", "## 빠진 것", ""]
    if missing_l1:
        lines += [
            "**L1 패널 자료가 들어 있지 않습니다.** S3 회귀의 종속변수라 없으면",
            "6단계를 돌릴 수 없습니다.",
            "",
        ] + [f"- `l1/{n}`" for n in missing_l1] + [
            "",
            "`kwci/trade/collect/collect_panel.py` 로 재수집하거나, 별도 배포된",
            "L1 zip(`kwci_kfood_kbeauty_kfashion_*.zip`)에서 가져오십시오.",
            "",
        ]
    else:
        lines += ["없습니다. L1 패널까지 모두 포함돼 있습니다.", ""]
    lines += [
        "Trends 수집 결과는 당연히 없습니다 — **아직 한 번도 받지 않았습니다.**",
        "그것이 인수받는 분의 1순위 작업입니다(README §4).",
        "",
        "## 재생성",
        "",
        "```",
        "cd code",
        f"python build_master_dict.py --base ../source/{base_name}",
        "```",
        "",
        "결정론적입니다. 같은 입력이면 같은 해시가 나옵니다.",
        "",
    ]
    (STAGE / "꾸러미_내역.md").write_text("\n".join(lines), encoding="utf-8")

    ZIP.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(STAGE))
    shutil.rmtree(STAGE)

    print(f"\n{'=' * 66}")
    print(f"= {ZIP.name}   {ZIP.stat().st_size / 1024:,.0f} KB")
    with zipfile.ZipFile(ZIP) as z:
        print(f"  {len(z.namelist())}개 파일")
    if missing_l1:
        print(f"\n  ! L1 자료 {len(missing_l1)}건이 빠졌습니다 — 꾸러미_내역.md 참조")
        print(f"    --l1 <panel.csv 가 있는 폴더> 로 지정하면 포함됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
