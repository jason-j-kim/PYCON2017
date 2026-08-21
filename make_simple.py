#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""터널 구동에 꼭 필요한 것만 담은 zip을 만든다.

담는 것은 세 가지뿐이다.
  data/      sqlite·json 코퍼스 3개
  *.py       그 데이터를 돌리는 파이썬 파일들 (webapp · socratic · kdinov)
  *.bat      설치·실행·터널 세 개

Vercel판·Workers판·임포터·연구문서는 넣지 않는다. 그건 저장소에 있다.

사용:  python make_simple.py
"""
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / f"정책아이디어평가_터널판_{date.today():%Y%m%d}.zip"
TOP = "정책아이디어평가"          # 압축을 풀면 이 폴더 하나가 생긴다

# ── 코퍼스 3종: 저장소 어디에 있든 찾아서 zip 안에서는 data/ 로 통일 ──
CORPUS = {
    "data/fiscal.json":        ["data/fiscal.json", "web/api/fiscal.json"],
    "data/kdi.sqlite":         ["kdi/kdi.sqlite", "web/api/kdi.sqlite"],
    "data/opsi_policies.db":   ["overseas/opsi_policies.db", "web/api/opsi_policies.db"],
}

# ── 파이썬 · 화면 파일 ──
CODE = [
    "webapp/app.py",
    "webapp/db.py",
    "webapp/show_session.py",
    "webapp/check_bill.py",
    "webapp/requirements.txt",
    "webapp/static/policy.html",
    "webapp/static/index.html",
    "socratic/__init__.py",
    "socratic/engine.py",
]
CODE += [f"socratic/prompts/{p.name}" for p in sorted((ROOT / "socratic/prompts").glob("*.md"))]
CODE += [f"kdinov/{p.name}" for p in sorted((ROOT / "kdinov").glob("*.py"))]


def find(cands):
    for c in cands:
        p = ROOT / c
        if p.exists():
            return p
    return None


def main():
    items = []          # (실제 파일, zip 안 경로)

    for dest, cands in CORPUS.items():
        src = find(cands)
        if src is None:
            raise SystemExit(f"코퍼스를 찾을 수 없다: {dest} (후보 {cands})")
        items.append((src, dest))

    for rel in CODE:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"파일 없음: {rel}")
        items.append((p, rel))

    for name in ("1_설치.bat", "2_실행.bat", "3_터널.bat",
                 "setup.py", "start.py", "tunnel.py", "읽어보세요.txt"):
        p = ROOT / "package" / name
        if not p.exists():
            raise SystemExit(f"파일 없음: package/{name}")
        items.append((p, name))

    if OUT.exists():
        OUT.unlink()

    raw = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, dest in items:
            if dest.endswith(".bat"):
                # 윈도우 배치는 CRLF여야 한다. LF만 있으면 라벨·괄호 블록에서
                # cmd 가 위치를 잃고 조용히 어긋난다(실제로 겪은 고장).
                body = src.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                if not body.isascii():
                    raise SystemExit(f"배치에 비ASCII 문자: {dest} — 한국어는 .py 쪽에 두세요")
                z.writestr(f"{TOP}/{dest}", body)
                raw += len(body)
            else:
                z.write(src, f"{TOP}/{dest}")
                raw += src.stat().st_size

    print(f"생성: {OUT.name}")
    print(f"  파일 {len(items)}개 · 원본 {raw/1e6:.1f}MB → 압축 {OUT.stat().st_size/1e6:.1f}MB")
    print()
    for src, dest in items:
        kb = src.stat().st_size / 1024
        mark = "  " if kb < 1000 else "* "
        print(f"  {mark}{dest:<40} {kb:>9,.0f} KB")


if __name__ == "__main__":
    main()
