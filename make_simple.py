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
    # mode     : mode.txt 에 들어갈 한 줄. 판을 가르는 것은 이것뿐이다.
    # launcher : "windows" 면 .bat 과 그 짝인 .py, "linux" 면 deploy/ 일습.
    # extras   : 함께 넣을 워드 문서.
    #
    # 실험용은 기관이 설치를 끝내 두고 참여자는 주소와 초대 코드만 받으므로
    # 워드 안내서가 필요 없다. 개인용과 서버용은 받는 사람이 직접 깔아야 해서
    # 텍스트 한 장으로는 모자란다 — 다만 받는 사람이 서로 다르다. 개인용은
    # 파이썬을 처음 까는 분, 서버용은 연구소 서버를 맡은 분이다.
    dict(mode="experiment", label="실험용", launcher="windows",
         readme="읽어보세요_실험용.txt", extras=[]),
    dict(mode="personal", label="개인용", launcher="windows",
         readme="읽어보세요_개인용.txt", extras=["설치와실행_안내.docx"]),
    # 서버용이 personal 인 이유 — 밖에 열기 때문이다. 초대 코드는 참여자
    # 전원이 아는 값이라 반드시 샌다. experiment 로 열어 두면 코드가 새는
    # 순간 남의 실험이 기관 카드로 결제된다.
    dict(mode="personal", label="서버용", launcher="linux",
         readme="읽어보세요_서버용.txt", extras=["서버설치_안내.docx"]),
    # 윈도우 서버는 systemd 도 nginx 도 없다. 작업 스케줄러와 IIS 를 쓴다.
    dict(mode="personal", label="서버용_윈도우", launcher="winserver",
         readme="읽어보세요_서버용_윈도우.txt",
         extras=["서버설치_안내_윈도우.docx"]),
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
    "webapp/load_samples.py",
    "samples/__init__.py",
    "samples/dialogues.py",
    "webapp/requirements.txt",
    "webapp/static/policy.html",
    "webapp/static/records.html",
    "webapp/static/index.html",
    "socratic/__init__.py",
    "socratic/engine.py",
]
CODE += [f"socratic/prompts/{p.name}" for p in sorted((ROOT / "socratic/prompts").glob("*.md"))]
CODE += [f"kdinov/{p.name}" for p in sorted((ROOT / "kdinov").glob("*.py"))]

# 윈도우 판에 들어가는 것 — 배치와 그 짝인 파이썬. 전부 package/ 아래.
WIN_LAUNCHERS = ["0_제거.bat", "1_설치.bat", "2_실행.bat", "3_터널.bat",
                 "4_키확인.bat", "5_보고서.bat", "6_샘플.bat",
                 "uninstall.py", "setup.py", "start.py", "tunnel.py"]

# 리눅스 서버 판에 들어가는 것. 배치는 넣지 않는다 — 서버에서 쓸 일이 없고,
# 있으면 무엇을 눌러야 하는지 헷갈리게만 한다.
LINUX_FILES = ["deploy/setup_server.sh", "deploy/policy-eval.service",
               "deploy/nginx.conf", "deploy/README.md"]

# 윈도우 서버 판. 데스크톱용 배치(1_설치·2_실행·3_터널)는 넣지 않는다 —
# 서버에서 쓸 일이 없고, 있으면 무엇을 눌러야 하는지 헷갈리게만 한다.
WINSRV_FILES = ["deploy_win/setup_win.py", "deploy_win/service_win.py",
                "deploy_win/run_server.py", "deploy_win/web.config",
                "deploy_win/README.md"]
WINSRV_LAUNCHERS = ["서버_1_설치.bat", "서버_2_서비스등록.bat",
                    "서버_3_직접실행.bat", "서버_4_상태확인.bat"]


def find(cands):
    for c in cands:
        p = ROOT / c
        if p.exists():
            return p
    return None


def collect(launcher):
    """(실제 파일, zip 안 경로) 목록."""
    items = []
    for dest, cands in CORPUS.items():
        src = find(cands)
        if src is None:
            raise SystemExit(f"코퍼스를 찾을 수 없다: {dest} (후보 {cands})")
        items.append((src, dest))
    if launcher == "windows":
        rels = CODE + [f"package/{n}" for n in WIN_LAUNCHERS]
    elif launcher == "linux":
        rels = CODE + LINUX_FILES
    elif launcher == "winserver":
        rels = (CODE + WINSRV_FILES
                + [f"package/{n}" for n in WINSRV_LAUNCHERS])
    else:
        raise SystemExit(f"모르는 launcher: {launcher}")
    for rel in rels:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"파일 없음: {rel}")
        items.append((p, rel.replace("package/", "")))
    return items


def build(mode, label, readme_name, extras, items, exec_bits=()):
    readme = ROOT / "package" / readme_name
    if not readme.exists():
        raise SystemExit(f"안내문 없음: package/{readme_name}")
    extra_paths = []
    for name in extras:
        p = ROOT / "package" / name
        if not p.exists():
            raise SystemExit(f"안내서 없음: package/{name}")
        extra_paths.append(p)

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
            elif dest.endswith(".sh"):
                # 리눅스 셸은 LF 여야 한다. CRLF 가 섞이면 첫 줄의 #! 뒤에
                # \r 이 붙어 "bad interpreter" 로 죽는다. 그리고 zip 은
                # 실행 권한을 외부 속성에 담아야 살아남는다.
                body = src.read_bytes().replace(b"\r\n", b"\n")
                info = zipfile.ZipInfo(f"{TOP}/{dest}")
                info.date_time = (2026, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o755 << 16)
                z.writestr(info, body)
                raw += len(body)
            else:
                z.write(src, f"{TOP}/{dest}")
                raw += src.stat().st_size
        # 판을 가르는 것은 이 한 줄뿐이다.
        z.writestr(f"{TOP}/mode.txt", mode + "\n")
        z.write(readme, f"{TOP}/읽어보세요.txt")
        raw += readme.stat().st_size
        for p in extra_paths:
            z.write(p, f"{TOP}/{p.name}")
            raw += p.stat().st_size

    n = len(items) + 2 + len(extra_paths)
    print(f"  {label}  {out.name}")
    print(f"         파일 {n}개 · 원본 {raw/1e6:.1f}MB → 압축 {out.stat().st_size/1e6:.1f}MB")
    return out


def main():
    print("생성")
    outs = []
    for e in EDITIONS:
        items = collect(e["launcher"])
        outs.append(build(e["mode"], e["label"], e["readme"], e["extras"], items))

    # 판이 실제로 갈렸는지 확인 — 실수로 같은 것을 두 번 만들면 의미가 없다.
    print("\n확인")
    for out in outs:
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            mode = z.read(f"{TOP}/mode.txt").decode().strip()
            head = z.read(f"{TOP}/읽어보세요.txt").decode("utf-8").splitlines()[0]
            bats = sum(1 for n in names if n.endswith(".bat"))
            deploys = sum(1 for n in names if "/deploy/" in n)
        print(f"  {out.name}")
        print(f"         mode={mode} · bat {bats}개 · deploy {deploys}개")
        print(f"         안내문 첫 줄: {head}")


if __name__ == "__main__":
    main()
