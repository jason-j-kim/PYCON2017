#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""구동 환경 점검 — 무엇이 준비됐고 무엇이 빠졌는지 한 번에 보여준다.

인수받은 연구자가 가장 먼저 실행할 스크립트다. 서버를 켜기 전에 돌리면
"왜 안 되는지"를 찾느라 시간을 쓰지 않아도 된다.

사용:
    python check_setup.py            # 기본 점검
    python check_setup.py --deep     # Claude CLI 실제 호출까지 확인(느림)
"""
import importlib.util
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEEP = "--deep" in sys.argv

OK, WARN, BAD = "  [OK]  ", "  [선택] ", "  [필요] "
issues, notes = [], []


def line(mark, label, detail=""):
    print(f"{mark}{label}" + (f"  —  {detail}" if detail else ""))


def need(cond, label, detail_ok="", detail_no="", fix=""):
    if cond:
        line(OK, label, detail_ok)
    else:
        line(BAD, label, detail_no)
        if fix and fix not in issues:
            issues.append(fix)
    return cond


def opt(cond, label, detail_ok="", detail_no="", fix=""):
    line(OK if cond else WARN, label, detail_ok if cond else detail_no)
    if not cond and fix and fix not in notes:
        notes.append(fix)
    return cond


def has_mod(name):
    return importlib.util.find_spec(name) is not None


def count_rows(path, table):
    try:
        with sqlite3.connect(str(path)) as c:
            return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return None


def port_free(port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


print("=" * 64)
print("  정책 아이디어 평가 시스템 — 구동 환경 점검")
print(f"  위치: {ROOT}")
print("=" * 64)

# ── 1. 런타임 ────────────────────────────────────────────────
print("\n[1] 파이썬")
v = sys.version_info
need(v >= (3, 10), "Python 3.10 이상",
     f"{v.major}.{v.minor}.{v.micro}",
     f"{v.major}.{v.minor} — 3.10 이상이 필요합니다",
     "Python 3.11 이상을 설치하세요.")

# ── 2. 패키지 ────────────────────────────────────────────────
print("\n[2] 파이썬 패키지")
need(has_mod("fastapi"), "fastapi", fix="pip install -r webapp/requirements.txt")
need(has_mod("uvicorn"), "uvicorn", fix="pip install -r webapp/requirements.txt")
opt(has_mod("docx"), "python-docx", "Word 불러오기 가능", "Word 불러오기 불가",
    "pip install python-docx")
opt(has_mod("pypdf"), "pypdf", "PDF 불러오기 가능", "PDF 불러오기 불가",
    "pip install pypdf")
opt(has_mod("kiwipiepy"), "kiwipiepy",
    "한국어 문장 분할 정밀", "없어도 동작(정규식으로 퇴화)",
    "pip install kiwipiepy   (선택 — 판정 정밀도 소폭 향상)")

# ── 3. Claude 호출 경로 ──────────────────────────────────────
print("\n[3] Claude 호출 (터널판은 CLI를 씁니다)")
claude_bin = shutil.which("claude") or shutil.which("claude.cmd")
need(bool(claude_bin), "claude CLI", claude_bin or "",
     "설치되지 않음",
     "npm install -g @anthropic-ai/claude-code  후 터미널에서 `claude` 실행 → /login")

if claude_bin and DEEP:
    try:
        r = subprocess.run([claude_bin, "-p", "--tools", "", "--output-format", "text"],
                           input="7만 출력하라.", capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        ok = r.returncode == 0 and r.stdout.strip()
        need(bool(ok), "claude 로그인·응답", (r.stdout or "").strip()[:40],
             (r.stderr or "")[:120],
             "터미널에서 `claude` 실행 후 /login 으로 로그인하세요.")
    except Exception as e:
        need(False, "claude 로그인·응답", "", str(e)[:100],
             "터미널에서 `claude` 실행 후 /login 으로 로그인하세요.")
elif claude_bin:
    line(WARN, "claude 로그인 여부", "미확인 — `--deep` 옵션으로 확인 가능")

if os.environ.get("ANTHROPIC_API_KEY"):
    line(WARN, "ANTHROPIC_API_KEY 환경변수가 설정됨",
         "CLI 로그인보다 우선할 수 있습니다. 문제가 나면 지우세요")

# ── 4. 선례 검증 4통로 ───────────────────────────────────────
print("\n[4] 선례 검증 — 네 통로")

fiscal = ROOT / "web" / "api" / "fiscal.json"
opt(fiscal.exists(), "① 재정 (세출예산)",
    f"{fiscal.stat().st_size/1e6:.1f}MB" if fiscal.exists() else "",
    "fiscal.json 없음 → 이 통로 꺼짐",
    "저장소에 포함되어 있습니다. git clone이 온전한지 확인하세요.")

kdi_path = Path(os.environ.get("KDI_SQLITE", ROOT / "kdi" / "kdi.sqlite"))
kdi_alt = ROOT / "web" / "api" / "kdi.sqlite"
kdi_used = kdi_path if kdi_path.exists() else (kdi_alt if kdi_alt.exists() else None)
if kdi_used:
    n = count_rows(kdi_used, "docs")
    tag = "원본(kdinov 정밀 판정)" if kdi_used == kdi_path else "경량본(본문 없음)"
    line(OK, "② 정책연구 (KDI)", f"{n:,}건 · {tag} · {kdi_used.name}")
    if kdi_used != kdi_path:
        notes.append("kdi/kdi.sqlite(원본 53MB)를 두면 kdinov 2차원 판정이 켜집니다.")
else:
    line(BAD, "② 정책연구 (KDI)", "코퍼스 없음 → 이 통로 꺼짐")
    issues.append("kdi/kdi.sqlite 를 받아 kdi/ 폴더에 두세요(별도 전달 파일).")

assembly = os.environ.get("ASSEMBLY_KEY", "").strip()
opt(bool(assembly), "③ 국회 의안",
    "키 설정됨", "ASSEMBLY_KEY 없음 → 이 통로 꺼짐",
    "공공데이터포털에서 국회 의안정보 키를 발급받아 set ASSEMBLY_KEY=... (선택)")

opsi = ROOT / "overseas" / "opsi_policies.db"
opsi_alt = ROOT / "web" / "api" / "opsi_policies.db"
opsi_used = opsi if opsi.exists() else (opsi_alt if opsi_alt.exists() else None)
if opsi_used:
    n = count_rows(opsi_used, "cases")
    line(OK, "④ 해외사례 (OPSI)", f"{n:,}건 · {opsi_used.name}")
    if opsi_used != opsi:
        notes.append("overseas/opsi_policies.db 로 복사해 두면 터널판이 직접 읽습니다."
                     "  (copy web\\api\\opsi_policies.db overseas\\)")
else:
    line(BAD, "④ 해외사례 (OPSI)", "코퍼스 없음 → 이 통로 꺼짐")
    issues.append("overseas/opsi_policies.db 가 필요합니다.")

# kdinov 임포트 확인
sys.path.insert(0, str(ROOT))
opt(has_mod("kdinov"), "kdinov 판정기",
    "사용 가능(중첩도 N0~N4 · 역할 판정)", "임포트 실패",
    "kdinov/ 폴더가 저장소에 있는지 확인하세요.")

# ── 5. 실행 조건 ─────────────────────────────────────────────
print("\n[5] 실행 조건")
need((ROOT / "webapp" / "app.py").exists(), "webapp/app.py", fix="저장소를 다시 clone 하세요.")
free = port_free(8000)
opt(free, "포트 8000", "사용 가능", "이미 사용 중",
    "taskkill /F /IM python.exe   (이전 서버가 남아 있습니다)")

code = os.environ.get("SOCRATIC_ACCESS_CODE", "").strip()
opt(bool(code), "초대 코드", "설정됨 — 접근 통제 켜짐",
    "미설정 — 누구나 접속 가능",
    "외부 공개 시  set SOCRATIC_ACCESS_CODE=원하는코드")

opt(bool(shutil.which("cloudflared")), "cloudflared",
    "외부 공개 가능", "없음 — 로컬만 접속 가능",
    "외부 공개가 필요하면 cloudflared 를 설치하세요.")

# ── 결과 ─────────────────────────────────────────────────────
print("\n" + "=" * 64)
if issues:
    print(f"  필수 조치 {len(issues)}건")
    for i, s in enumerate(issues, 1):
        print(f"    {i}. {s}")
else:
    print("  필수 조건 모두 충족 — 서버를 켤 수 있습니다.")
    print("\n    set SOCRATIC_ACCESS_CODE=원하는코드")
    print("    python webapp\\app.py")
    print("    → http://localhost:8000/policy")

if notes:
    print(f"\n  선택 사항 {len(notes)}건 (없어도 동작)")
    for s in notes:
        print(f"    · {s}")
print("=" * 64)

sys.exit(1 if issues else 0)
