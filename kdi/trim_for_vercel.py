#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KDI docs 코퍼스(kdi.sqlite) → Vercel 배포용 경량본 web/api/kdi.sqlite.

kdinov 매칭은 title·keywords·toc·summary만 쓴다. 원본의 raw(=raw_markdown 등
본문 전체)는 검색에 안 쓰이면서 용량의 대부분을 차지하므로 비운다.
→ 파일이 크게 줄고 Vercel 콜드스타트도 빨라진다.

사용(프로젝트 루트에서):
    python kdi/trim_for_vercel.py                     # 소스: kdi/kdi.sqlite
    python kdi/trim_for_vercel.py D:\\work\\kdinov\\kdi.sqlite

결과: web/api/kdi.sqlite  (이 파일을 git add·commit·push 하면 Vercel에 배포됨)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web" / "api"))   # 벤더된 kdinov 패키지

from kdinov.sources import Store  # noqa: E402

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "kdi" / "kdi.sqlite"
DST = ROOT / "web" / "api" / "kdi.sqlite"


def main():
    if not SRC.exists():
        sys.exit(f"소스 없음: {SRC}\n먼저 kdi.sqlite 위치를 인자로 주세요.")
    docs = Store(str(SRC)).all()
    for d in docs:
        d.raw = {}                       # 본문(raw_markdown 등) 비우기 — 검색엔 불필요
    if DST.exists():
        DST.unlink()
    Store(str(DST)).put(docs)
    print(f"완료: {len(docs)}건 → {DST}")
    print(f"  원본 {SRC.stat().st_size/1e6:.1f}MB → 경량 {DST.stat().st_size/1e6:.1f}MB")
    print("  이제:  git add web/api/kdi.sqlite web/api/kdinov  &&  git commit  &&  git push")


if __name__ == "__main__":
    main()
