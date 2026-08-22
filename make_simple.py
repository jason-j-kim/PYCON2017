#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""터널 구동에 꼭 필요한 것만 담은 zip 을 만든다. 두 판이 나온다.

  실험용  기관이 키 하나로 운영. 참여자는 초대 코드만 넣는다.
          설치할 때 운영자가 Anthropic 키·초대 코드·의안 키를 정한다.
          웹 화면에는 키 입력칸이 아예 나오지 않는다.

  개인용  각자 자기 API 키 또는 Claude 구독으로 쓴다.
          실행할 때 물어보고, 웹 화면에서도 본인 키를 넣을 수 있다.

코드는 두 판이 똑같다. 가르는 것은 zip 안의 mode.txt 한 줄뿐이다.

사용:  python make_simple.py
"""
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOP = "정책아이디어평가"          # 압축을 풀면 이 폴더 하나가 생긴다
TODAY = f"{date.today():%Y%m%d}"

EDITIONS = [
    # (mode.txt 값, 이름, 안내문 파일)
    ("experiment", "실험용", "읽어보세요_실험용.txt"),
    ("personal",   "개인용", "읽어보세요_개인용.txt"),
]

# ── 코퍼스 3종: 저장소 어디에 있든 찾아서 zip 안에서는 data/ 로 통일 ──
CORPUS = {
    "data/fiscal.json":      ["data/fiscal.json", "web/api/fiscal.json"],
    "data/kdi.sqlite":       ["kdi/kdi.sqlite", "web/api/kdi.sqlite"],
    "data/opsi_policies.db": ["overseas/opsi_policies.db", "web/api/opsi_policies.db"],
}

# ── 파이썬 · 화면 파일 ──
CODE = [
    "webapp/app.py",
    "webapp/db.py",
    "webapp/show_session.py",
    "webapp/check_bill.py",
    "webapp/check_claude.py",
    "webapp/make_report.py",
    "webapp/requirements.txt",
    "webapp/static/policy.html",
    "webapp/static/index.html",
    "socratic/__init__.py",
    "socratic/engine.py",
]
CODE += [f"socratic/prompts/{p.name}" for p in sorted((ROOT / "socratic/prompts").glob("*.md"))]
CODE += [f"kdinov/{p.name}" for p in sorted((ROOT / "kdinov").glob("*.py"))]

LAUNCHERS = ["0_제거.bat", "1_설치.bat", "2_실행.bat", "3_터널.bat", "4_키확인.bat",
             "5_보고서.bat",
             "uninstall.py", "setup.py", "start.py", "tunnel.py"]


def find(cands):
    for c in cands:
        p = ROOT / c
        if p.exists():
            return p
    return None


def collect():
    """(실제 파일, zip 안 경로) 목록. 두 판이 공유한다."""
    items = []
    for dest, cands in CORPUS.items():
        src = find(cands)
        if src is None:
            raise SystemExit(f"코퍼스를 찾을 수 없다: {dest} (후보 {cands})")
        items.append((src, dest))
    for rel in CODE + [f"package/{n}" for n in LAUNCHERS]:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"파일 없음: {rel}")
        items.append((p, rel.replace("package/", "")))
    return items


def build(mode, label, readme_name, items):
    readme = ROOT / "package" / readme_name
    if not readme.exists():
        raise SystemExit(f"안내문 없음: package/{readme_name}")

    out = ROOT / f"정책아이디어평가_{label}_{TODAY}.zip"
    if out.exists():
        out.unlink()

    raw = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, dest in items:
            if dest.endswith(".bat"):
                # 윈도우 배치는 CRLF여야 한다. LF만 있으면 라벨·괄호 블록에서
                # cmd 가 위치를 잃고 조용히 어긋난다(실제로 겪은 고장).
                body = src.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                if not body.isascii():
                    raise SystemExit(f"배치에 비ASCII 문자: {dest} — 한국어는 .py 쪽에")
                z.writestr(f"{TOP}/{dest}", body)
                raw += len(body)
            else:
                z.write(src, f"{TOP}/{dest}")
                raw += src.stat().st_size
        # 판을 가르는 것은 이 한 줄뿐이다.
        z.writestr(f"{TOP}/mode.txt", mode + "\n")
        z.write(readme, f"{TOP}/읽어보세요.txt")
        raw += readme.stat().st_size

    n = len(items) + 2
    print(f"  {label}  {out.name}")
    print(f"         파일 {n}개 · 원본 {raw/1e6:.1f}MB → 압축 {out.stat().st_size/1e6:.1f}MB")
    return out


def main():
    items = collect()
    print("생성")
    outs = [build(m, label, rn, items) for m, label, rn in EDITIONS]

    # 판이 실제로 갈렸는지 확인 — 실수로 같은 것을 두 번 만들면 의미가 없다.
    print("\n확인")
    for out in outs:
        with zipfile.ZipFile(out) as z:
            mode = z.read(f"{TOP}/mode.txt").decode().strip()
            head = z.read(f"{TOP}/읽어보세요.txt").decode("utf-8").splitlines()[0]
        print(f"  {out.name}\n         mode={mode} · 안내문 첫 줄: {head}")


if __name__ == "__main__":
    main()
