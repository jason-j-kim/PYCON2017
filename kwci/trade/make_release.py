#!/usr/bin/env python3
"""
KWCI L1 — 외부 배포용 zip 패키징

수집 결과(CSV) · 방법론 문서 · 재현 코드를 하나의 zip으로 묶는다.
원시 API 응답 캐시(수 GB)와 인증키는 제외한다.

사용법
------
  python make_release.py              # kwci_kfood_kbeauty_kfashion_YYYYMMDD.zip
  python make_release.py --out X.zip
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROC = HERE / "data" / "processed"
MASTER = HERE / "master"
DOCS = HERE / "docs"

# (묶음 안 경로, 원본 경로) — 없으면 경고하고 건너뛴다.
DATA = [
    "panel.csv", "item_totals.csv", "top_items.csv", "country_totals.csv",
    "base_2018.csv", "rca.csv",
    "l1_cross.csv", "l1_series.csv", "l1_diversity.csv",
]
MASTER_FILES = [
    "item_master.csv", "item_master.lock.json",
    "hs_bec5.csv", "hs2017_hs2022.csv", "hs_names.csv", "bec5_codes.csv",
]
CODE = [
    ("code/master/fetch_reference_tables.py", MASTER / "fetch_reference_tables.py"),
    ("code/master/build_item_master.py", MASTER / "build_item_master.py"),
    ("code/api/customs.py", HERE / "api" / "customs.py"),
    ("code/api/comtrade.py", HERE / "api" / "comtrade.py"),
    ("code/collect/collect_customs.py", HERE / "collect" / "collect_customs.py"),
    ("code/collect/collect_stage_b.py", HERE / "collect" / "collect_stage_b.py"),
    ("code/collect/collect_panel.py", HERE / "collect" / "collect_panel.py"),
    ("code/analyze/rank_items.py", HERE / "analyze" / "rank_items.py"),
    ("code/analyze/compute_rca.py", HERE / "analyze" / "compute_rca.py"),
    ("code/analyze/build_l1.py", HERE / "analyze" / "build_l1.py"),
]

RUN_MD = """# 재현 순서

API 키 두 개가 필요하다.

- 공공데이터포털(data.go.kr) 일반 인증키
  — "관세청_품목별 국가별 수출입실적" 활용신청 필요 (자동승인)
- UN Comtrade 구독키 (comtradeapi.un.org, 무료 티어로 충분)

`keys.local.bat`(Windows) 또는 `.env`에 넣거나 환경변수로 설정한다.

    set DATA_GO_KR_KEY=...
    set COMTRADE_KEY=...

## 실행

    pip install requests openpyxl

    python code/master/fetch_reference_tables.py      # 기준 대응표 (키 불필요)
    python code/master/build_item_master.py           # S0 · S1 -> 928개
    python code/master/build_item_master.py --freeze  # 사전등록 동결
    python code/collect/collect_customs.py            # A단계 928 x 2024   (4분)
    python code/analyze/rank_items.py                 # 대표 75품목
    python code/collect/collect_stage_b.py            # 국가별 + 기준연도  (6분)
    python code/collect/collect_panel.py              # 패널 75x15x7      (30분)
    python code/analyze/compute_rca.py                # RCA + 단가프리미엄 (5분)
    python code/analyze/build_l1.py                   # 통합 3파일

전 과정 약 50분. 모든 API 응답이 로컬 캐시에 남으므로 중단해도 이어받는다.

## 참고

- 스크립트는 저장소 디렉터리 구조(`kwci/trade/{master,api,collect,analyze}`)를
  전제로 상대 경로를 쓴다. 배포본에서 실행하려면 같은 구조로 배치하거나
  각 파일 상단의 경로 상수를 조정한다.
- 관세청 1회 조회기간은 1년 이내다. Comtrade 무료 티어는 429를 내므로 동시
  호출을 하지 않는다. 자세한 API 제약은 방법론 문서 5.0.2 참조.
"""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    args = ap.parse_args()

    out = Path(args.out) if args.out else HERE / (
        f"kwci_kfood_kbeauty_kfashion_{date.today():%Y%m%d}.zip")

    plan: list[tuple[str, Path]] = []
    for n in DATA:
        plan.append((f"data/{n}", PROC / n))
    for n in MASTER_FILES:
        plan.append((f"data/reference/{n}", MASTER / n))
    plan += CODE
    plan.append(("README.md", DOCS / "02_데이터셋_배포_요약.md"))
    plan.append(("방법론_상세.md", DOCS / "01_품목선정_및_수집계획.md"))

    missing = [p for _, p in plan if not p.exists()]
    manifest = ["# 수록 파일 목록", "",
                "| 경로 | 크기 | sha256(앞16) |", "|---|---|---|"]

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in plan:
            if not src.exists():
                print(f"  ! 없음: {src.name}")
                continue
            z.write(src, arc)
            manifest.append(f"| `{arc}` | {src.stat().st_size:,} B | `{sha(src)}` |")
            print(f"  + {arc:<48} {src.stat().st_size:>10,} B")
        z.writestr("RUN.md", RUN_MD)
        manifest.append("| `RUN.md` | — | — |")
        z.writestr("MANIFEST.md", "\n".join(manifest) + "\n")

    print(f"\n= {out.name}  {out.stat().st_size/1e6:.2f} MB")
    if missing:
        print(f"\n  ! 빠진 파일 {len(missing)}개 — 해당 단계를 먼저 실행하세요:")
        for p in missing:
            print(f"      {p.name}")
        return 1
    print("  모든 파일 포함. 외부 배포 가능합니다.")
    print("  (인증키·원시 캐시는 포함되지 않습니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
