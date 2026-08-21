#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""외부 연구자 전달용 배포 패키지(zip) 생성.

코드 + 코퍼스 + 문서를 한 파일로 묶는다. 받는 쪽은 압축을 풀고
`시작하기.md` 대로 하면 바로 구동된다.

제외: 세션 이력(개인정보 가능), 캐시, git 내부, 대용량 중간 산출물

사용:  python make_package.py
"""
import fnmatch
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / f"정책아이디어평가_배포_{date.today():%Y%m%d}.zip"

# 담을 것 — 디렉터리는 통째로, 파일은 개별로
DIRS = [
    "socratic",     # 문답·채점 엔진과 프롬프트
    "webapp",       # 터널판 서버·프런트
    "web",          # Vercel판 + 코퍼스 3종
    "kdinov",       # KDI 정밀 판정기
    "kdi",          # KDI 임포터
    "overseas",     # 해외 코퍼스 임포터·수집 도구
    "worker",       # Cloudflare Workers 배포판
    "data",         # 재정 코퍼스
    "docs",         # 문서
]
FILES = [
    "시작하기.md",
    "check_setup.py",
    "setup_tunnel.bat",
    "requirements.txt",
]

# 빼야 할 것
EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", ".pw-profile",
    "d1",              # Workers D1 적재용 중간 산출물(재생성 가능, 29MB)
    "results", "results_variants",   # 시뮬레이션 원자료 — 별도 전달
}
EXCLUDE_PATTERNS = [
    "*.pyc", "*.pyo", "*.log", "*.tmp",
    "sessions.db",     # 문답 이력 — 개인정보 가능성
    "*.local.bat", "run_policy.bat",   # 초대 코드가 든 로컬 배치
    ".DS_Store", "Thumbs.db",
]


def skip(path: Path) -> bool:
    if any(p in EXCLUDE_DIRS for p in path.parts):
        return True
    return any(fnmatch.fnmatch(path.name, pat) for pat in EXCLUDE_PATTERNS)


def collect():
    items = []
    for d in DIRS:
        base = ROOT / d
        if not base.exists():
            print(f"  (없음, 건너뜀) {d}/")
            continue
        for p in base.rglob("*"):
            if p.is_file() and not skip(p.relative_to(ROOT)):
                items.append(p)
    for f in FILES:
        p = ROOT / f
        if p.exists():
            items.append(p)
        else:
            print(f"  (없음, 건너뜀) {f}")
    return sorted(set(items))


def main():
    items = collect()
    if OUT.exists():
        OUT.unlink()

    total = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in items:
            rel = p.relative_to(ROOT)
            z.write(p, str(rel))
            total += p.stat().st_size

    size = OUT.stat().st_size
    print(f"\n생성: {OUT.name}")
    print(f"  파일 {len(items):,}개 · 원본 {total/1e6:.1f}MB → 압축 {size/1e6:.1f}MB")

    # 핵심 파일이 실제로 들어갔는지 확인
    must = [
        "시작하기.md", "check_setup.py", "setup_tunnel.bat",
        "webapp/app.py", "socratic/engine.py", "kdinov/verdict.py",
        "web/index.html", "web/api/kdi.sqlite", "web/api/opsi_policies.db",
        "data/fiscal.json",
        "docs/HANDOFF_인수인계.md", "docs/대화기반_아이디어평가_방법론.md",
        "docs/연구자_인수_셋업가이드.md",
    ]
    with zipfile.ZipFile(OUT) as z:
        names = set(z.namelist())
    print("\n  핵심 파일 확인")
    missing = []
    for m in must:
        ok = m in names or m.replace("/", os.sep) in names
        print(f"    {'✔' if ok else '✗'} {m}")
        if not ok:
            missing.append(m)

    # 들어가면 안 되는 것 확인
    bad = [n for n in names
           if n.endswith("sessions.db") or "__pycache__" in n or n.endswith(".pyc")]
    if bad:
        print(f"\n  ⚠ 제외 대상이 포함됨: {bad[:5]}")
    else:
        print("\n  제외 확인 ✔ (세션 이력·캐시 없음)")

    if missing:
        sys.exit(f"\n핵심 파일 누락: {missing}")


if __name__ == "__main__":
    main()
