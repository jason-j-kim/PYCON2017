#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""설치 — 1_설치.bat 이 부르는 본체.

배치 파일에 한국어와 로직을 담으면 인코딩(CP949/UTF-8)과 줄바꿈(CRLF/LF)에
따라 깨진다. 그래서 배치는 `python setup.py` 한 줄만 하고, 나머지는 여기서 한다.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEYS = ROOT / "keys.local.bat"


def say(*a):
    print(*a, flush=True)


def rule():
    say("-" * 62)


def run(cmd, **kw):
    """자식 프로세스 실행. 성공하면 True."""
    try:
        return subprocess.call(cmd, cwd=str(ROOT), **kw) == 0
    except FileNotFoundError:
        return False


def have(exe):
    return shutil.which(exe) is not None


def version_of(exe, *args):
    try:
        out = subprocess.check_output([exe, *args], stderr=subprocess.STDOUT,
                                      text=True, timeout=60)
        return out.strip().splitlines()[0]
    except Exception:
        return None


# ── 1. 파이썬 패키지 ──────────────────────────────────────────────────
def step_packages():
    say("\n[1/4] 파이썬 패키지 설치")
    say(f"      파이썬 {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        say("      [!] 3.10 이상이 필요합니다. python.org 에서 새로 설치하세요.")
        return False
    req = ROOT / "webapp" / "requirements.txt"
    ok = run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
    if not ok:
        say("      [!] 설치 실패. 인터넷 연결을 확인하세요.")
        return False
    try:
        import fastapi, uvicorn        # noqa: F401
        say("      완료 — fastapi · uvicorn 확인")
        return True
    except ImportError as e:
        say(f"      [!] 설치는 됐으나 불러오지 못합니다: {e}")
        return False


# ── 2. Claude Code ───────────────────────────────────────────────────
def step_claude_cli():
    say("\n[2/4] Claude Code 설치")
    if have("claude"):
        say(f"      이미 설치됨 — {version_of('claude', '--version') or 'claude'}")
        return True
    node = version_of("node", "--version")
    if not node:
        say("      [!] Node.js 가 없습니다. nodejs.org 에서 18 이상을 설치한 뒤")
        say("          1_설치.bat 을 다시 실행하세요.")
        return False
    say(f"      Node.js {node}")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    if not run([npm, "install", "-g", "@anthropic-ai/claude-code"], shell=(os.name == "nt")):
        say("      [!] 설치 실패. 관리자 권한 명령창에서 다시 해보세요:")
        say("          npm install -g @anthropic-ai/claude-code")
        return False
    say("      완료")
    return True


# ── 3. Claude 로그인 ─────────────────────────────────────────────────
def step_login():
    say("\n[3/4] Claude 로그인")
    if not have("claude"):
        say("      [!] claude 를 찾을 수 없습니다. 명령창을 새로 열고 다시 실행하세요.")
        return False
    say("      이제 claude 가 실행됩니다.")
    say("      창이 열리면  /login  을 입력해 본인 Claude 계정(Pro 또는 Max)으로")
    say("      로그인한 뒤,  /exit  로 나오세요. 한 번만 하면 됩니다.")
    input("\n      준비되면 Enter... ")
    run(["claude"], shell=(os.name == "nt"))
    return True


# ── 4. 국회 의안 키 ──────────────────────────────────────────────────
def read_key():
    """keys.local.bat 에서 ASSEMBLY_KEY 를 읽는다(배치 문법을 그대로 지원)."""
    if not KEYS.exists():
        return None
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            txt = KEYS.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None
    m = re.search(r"^\s*set\s+ASSEMBLY_KEY\s*=\s*(.+?)\s*$", txt,
                  re.M | re.I)
    return m.group(1).strip().strip('"').strip("'") if m else None


def check_bill(key):
    """방금 넣은 키로 실제 조회가 되는지 확인한다."""
    env = dict(os.environ, ASSEMBLY_KEY=key)
    subprocess.call([sys.executable, str(ROOT / "webapp" / "check_bill.py")],
                    cwd=str(ROOT), env=env)


def step_key():
    say("\n[4/4] 국회 의안 키 (선택)")
    existing = read_key()
    if existing:
        say(f"      keys.local.bat 에 키가 있습니다 ({existing[:4]}…{existing[-4:]}).")
        say("      실제로 되는지 확인합니다.")
        check_bill(existing)
        say("\n      키를 바꾸려면 keys.local.bat 을 지우고 다시 실행하세요.")
        return True

    say("      네 통로 중 ③ 국회 의안만 키가 필요합니다.")
    say("      발급처: https://open.assembly.go.kr  (열린국회정보)")
    say("      ※ 공공데이터포털(data.go.kr) 키와는 다릅니다.")
    say("")
    say("      없거나 나중에 하려면 그냥 Enter 를 누르세요. 나머지 세 통로")
    say("      (재정·KDI 연구·해외사례)는 키 없이 그대로 작동합니다.")
    try:
        key = input("\n      인증키를 붙여넣으세요: ").strip()
    except EOFError:
        key = ""
    if not key:
        say("\n      건너뜁니다. 나중에 넣으려면 1_설치.bat 을 다시 실행하세요.")
        return True

    KEYS.write_text(
        "@echo off\r\n"
        "REM 이 파일은 1_설치.bat 이 만들었습니다. 남에게 주지 마세요.\r\n"
        f"set ASSEMBLY_KEY={key}\r\n",
        encoding="utf-8")
    say(f"\n      keys.local.bat 을 만들었습니다. 실제로 되는지 확인합니다.")
    check_bill(key)
    return True


# ── 데이터 확인 ──────────────────────────────────────────────────────
def check_data():
    say("\n[데이터 확인]")
    files = [("① 재정", "data/fiscal.json"),
             ("② KDI 연구", "data/kdi.sqlite"),
             ("④ 해외사례", "data/opsi_policies.db")]
    ok = True
    for label, rel in files:
        p = ROOT / rel
        if p.exists():
            say(f"      {label:<12} {p.stat().st_size/1e6:>7.1f}MB  {rel}")
        else:
            say(f"      {label:<12} [!] 없음 — {rel}")
            ok = False
    if not ok:
        say("      압축을 덜 풀었을 수 있습니다. zip 전체를 다시 풀어 주세요.")
    return ok


def main():
    say("=" * 62)
    say("  정책 아이디어 평가 시스템 — 설치")
    say(f"  폴더: {ROOT}")
    say("=" * 62)

    check_data()
    if not step_packages():
        return 1
    if step_claude_cli():
        step_login()
    step_key()

    rule()
    say("  설치가 끝났습니다. 이제 2_실행.bat 을 실행하세요.")
    rule()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\n중단했습니다.")
        sys.exit(130)
