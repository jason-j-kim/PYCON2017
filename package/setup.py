#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""설치 — 1_설치.bat 이 부르는 본체.

배치 파일에 한국어와 로직을 담으면 인코딩(CP949/UTF-8)과 줄바꿈(CRLF/LF)에
따라 깨진다. 그래서 배치는 `python setup.py` 한 줄만 하고, 나머지는 여기서 한다.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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
    say("\n[1/3] 파이썬 패키지 설치")
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
def api_key():
    return (os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def step_claude_cli():
    say("\n[2/3] Claude Code 설치")
    if api_key():
        # API 키가 있으면 Claude를 API로 직접 부른다 — CLI도 Node.js도 필요 없다.
        say("      ANTHROPIC_API_KEY 가 설정돼 있습니다.")
        say("      Claude 를 API 로 직접 부르므로 Claude Code·Node.js 가 필요 없습니다.")
        say("      건너뜁니다.")
        return True
    if have("claude"):
        say(f"      이미 설치됨 — {version_of('claude', '--version') or 'claude'}")
        return True
    node = version_of("node", "--version")
    if not node:
        say("      [!] Node.js 가 없습니다. Claude Code 설치에 필요합니다.")
        say("")
        say("      1) 아래 주소에서 Windows Installer (.msi) LTS 를 받으세요.")
        say("         https://nodejs.org/ko/download")
        say("      2) 설치는 [다음]만 계속 누르면 됩니다. 옵션을 바꾸지 마세요.")
        say("      3) 설치가 끝나면 이 창을 닫고 1_설치.bat 을 다시 누르세요.")
        say("         (창을 새로 열어야 설치된 경로를 인식합니다.)")
        say("")
        say("      Node.js 는 Claude Code 를 내려받는 데만 쓰입니다.")
        say("      평가 시스템 자체는 파이썬으로 돕니다.")
        try:
            import webbrowser
            webbrowser.open("https://nodejs.org/ko/download")
            say("      다운로드 페이지를 브라우저에 열었습니다.")
        except Exception:
            pass
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
def login_ok():
    """대화창을 띄우지 않고 로그인 여부만 본다.

    `claude` 를 그냥 실행하면 테마·렌더러·브라우저확장 같은 첫 실행 질문이
    줄줄이 나온다. 로그인만 확인하면 되는 자리에서 그건 방해다.
    -p(헤드리스)로 한 마디 시켜 보고 성공하면 로그인된 것이다."""
    try:
        r = subprocess.run(["claude", "-p", "OK만 출력하라.", "--tools", ""],
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace",
                           shell=(os.name == "nt"))
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()[:300]
    except FileNotFoundError:
        return False, "claude 를 찾을 수 없습니다."
    except subprocess.TimeoutExpired:
        return False, "응답이 없어 확인을 중단했습니다."


def step_login():
    say("\n[3/3] Claude 로그인")
    if api_key():
        say("      API 키 방식이라 로그인이 필요 없습니다. 건너뜁니다.")
        return True
    if not have("claude"):
        say("      [!] claude 를 찾을 수 없습니다. 명령창을 새로 열고 다시 실행하세요.")
        return False

    say("      확인 중…")
    ok, detail = login_ok()
    if ok:
        say("      이미 로그인돼 있습니다. 이 단계는 건너뜁니다.")
        return True

    say("      [!] 아직 로그인되지 않았습니다.")
    say(f"          ({detail})" if detail else "")
    say("")
    say("      Enter 를 누르면 이 창에서 claude 가 실행됩니다.")
    say("      (브라우저·앱의 Claude 와는 별개인 명령줄 도구의 로그인입니다.)")
    say("")
    say("      1) 처음 실행이면 테마 등을 몇 가지 물어봅니다 — 그냥 Enter 로 넘기세요.")
    say("      2) /login 을 입력하고 브라우저에서 계정을 승인하세요.")
    say("      3) 끝나면 /exit 로 나오세요.")
    input("\n      준비되면 Enter... ")
    run(["claude"], shell=(os.name == "nt"))

    ok, _ = login_ok()
    say("      로그인 확인됨." if ok else
        "      아직 확인되지 않습니다. 1_설치.bat 을 다시 실행해 보세요.")
    return ok


# ── 국회 의안 키는 여기서 받지 않는다 ─────────────────────────────────
# 웹 첫 화면에서 넣는다. 파일을 만들 필요도, 다시 설치할 필요도 없다.
# (운영자가 서버 기본값을 두고 싶으면 keys.local.bat 에 set ASSEMBLY_KEY=...
#  를 넣으면 start.py 가 읽는다. 그 경우 첫 화면은 "서버에 이미 설정됨"으로
#  표시되고 입력을 비워 둬도 된다.)


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
    ready = step_claude_cli()
    if ready:
        step_login()

    rule()
    if ready:
        say("  설치가 끝났습니다. 이제 2_실행.bat 을 실행하세요.")
    else:
        say("  아직 끝나지 않았습니다 — 위의 [!] 안내를 먼저 처리하세요.")
        say("  그런 다음 1_설치.bat 을 다시 실행하면 이어서 진행됩니다.")
    say("")
    say("  Claude 호출 방식: " +
        ("API 키 (ANTHROPIC_API_KEY)" if api_key() else "구독 로그인 (claude CLI)"))
    say("  바꾸려면 ANTHROPIC_API_KEY 환경변수를 설정/해제하고 다시 실행하세요.")
    say("")
    say("  ③ 국회 의안 인증키는 웹 첫 화면에서 넣습니다(선택).")
    say("  비워 두면 그 통로만 빼고 나머지 세 통로로 평가합니다.")
    rule()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\n중단했습니다.")
        sys.exit(130)
