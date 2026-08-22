#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""설치 — 1_설치.bat 이 부르는 본체.

받는 사람이 파일을 손수 만들 일이 없게 한다. Claude 연결 방식을 여기서
묻고, API 키를 고르면 키를 받아 **즉시 실제 호출로 검증한 뒤** keys.local.bat
을 대신 만들어 준다. 잘못된 키를 12문답 뒤에 발견하는 일이 없어야 한다.

배치 파일에 한국어와 로직을 담으면 인코딩(CP949/UTF-8)과 줄바꿈(CRLF/LF)에
따라 깨진다. 그래서 배치는 `python setup.py` 한 줄만 하고 나머지는 여기서 한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEYS = ROOT / "keys.local.bat"
CONSOLE = "https://console.anthropic.com/settings/keys"
NODE_DL = "https://nodejs.org/ko/download"


def say(*a):
    print(*a, flush=True)


def rule(ch="-"):
    say(ch * 64)


def ask(prompt, default=""):
    try:
        return input(prompt).strip() or default
    except EOFError:
        return default


def run(cmd, **kw):
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


# ── keys.local.bat 읽고 쓰기 ──────────────────────────────────────────
def read_keys():
    """{이름: 값}. 파일이 없거나 못 읽으면 빈 dict."""
    if not KEYS.exists():
        return {}
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            txt = KEYS.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return {}
    return {m.group(1).upper(): m.group(2).strip().strip('"').strip("'")
            for m in re.finditer(r"^\s*set\s+([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$",
                                 txt, re.M | re.I)}


def write_keys(values):
    """기존 값을 유지하며 덮어쓴다. 첫 줄 @echo off 로 키가 화면에 안 찍히게."""
    merged = {**read_keys(), **{k: v for k, v in values.items() if v}}
    lines = ["@echo off",
             "REM 1_설치.bat 이 만든 파일입니다. 본인 것이니 남에게 주지 마세요."]
    lines += [f"set {k}={v}" for k, v in merged.items()]
    KEYS.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def mask(key):
    return f"{key[:7]}…{key[-4:]}" if len(key) > 14 else "(짧음)"


# ── API 키 실제 검증 ──────────────────────────────────────────────────
def verify_api_key(key, model=""):
    """진짜로 한 번 불러 본다. (ok, 사람이 읽을 메시지)

    ANTHROPIC_BASE_URL 을 존중한다 — 기관이 게이트웨이·프록시를 두는 경우가
    있고, 서버(engine)도 같은 변수를 보므로 검증과 실제 호출이 어긋나면 안 된다."""
    model = model or os.environ.get("CLAUDE_MODEL") or "claude-opus-5"
    base = (os.environ.get("ANTHROPIC_BASE_URL")
            or read_keys().get("ANTHROPIC_BASE_URL")
            or "https://api.anthropic.com").rstrip("/")
    body = json.dumps({"model": model, "max_tokens": 16,
                       "messages": [{"role": "user", "content": "OK만 출력"}]}).encode()
    req = urllib.request.Request(
        f"{base}/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=60):
            return True, "키 정상 — 실제 호출에 성공했습니다."
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        if e.code == 401:
            return False, "키가 거부되었습니다(401). 콘솔에서 키를 다시 확인하세요."
        if e.code == 400 and "credit" in detail.lower():
            return False, "잔액이 부족합니다. 콘솔에서 결제 수단을 등록하세요."
        if e.code == 429:
            return False, "요청 한도를 넘었습니다(429). 잠시 뒤 다시 시도하세요."
        if e.code == 404:
            return False, (f"모델 {model} 을 쓸 수 없습니다. 콘솔에서 사용 가능한 "
                           "모델을 확인하세요.")
        return False, f"오류 HTTP {e.code}: {detail}"
    except urllib.error.URLError as e:
        return False, (f"{base} 에 닿지 못했습니다: {e.reason}\n"
                       "      방화벽이 이 주소를 막고 있는지 확인하세요. "
                       "구독 방식도 같은 곳으로 나가므로 함께 막힙니다.")


# ── 1. 파이썬 패키지 ──────────────────────────────────────────────────
def step_packages():
    say("\n[1/3] 파이썬 패키지 설치")
    say(f"      파이썬 {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        say("      [!] 3.10 이상이 필요합니다. python.org 에서 새로 설치하세요.")
        return False
    if not run([sys.executable, "-m", "pip", "install", "-q", "-r",
                str(ROOT / "webapp" / "requirements.txt")]):
        say("      [!] 설치 실패. 인터넷 연결을 확인하세요.")
        return False
    try:
        import fastapi, uvicorn        # noqa: F401
        say("      완료 — fastapi · uvicorn 확인")
        return True
    except ImportError as e:
        say(f"      [!] 설치는 됐으나 불러오지 못합니다: {e}")
        return False


# ── 2. Claude 연결 ────────────────────────────────────────────────────
def step_api_key():
    """API 키를 받아 검증하고 저장한다. 성공하면 True."""
    existing = read_keys().get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
    if existing:
        say(f"\n      이미 설정된 키가 있습니다 ({mask(existing)}). 확인합니다…")
        ok, msg = verify_api_key(existing)
        say(f"      {'✔' if ok else '✗'} {msg}")
        if ok:
            return True
        say("      새 키를 넣으시겠습니까? 그냥 Enter 를 누르면 건너뜁니다.")

    say("")
    say(f"      키 발급: {CONSOLE}")
    say("      (sk-ant- 로 시작하는 긴 문자열입니다. 결제 수단 등록이 필요합니다.)")
    try:
        import webbrowser
        webbrowser.open(CONSOLE)
        say("      발급 페이지를 브라우저에 열었습니다.")
    except Exception:
        pass

    for attempt in range(3):
        key = ask("\n      API 키를 붙여넣으세요 (건너뛰려면 Enter): ")
        if not key:
            say("      건너뜁니다.")
            return False
        if not key.startswith("sk-ant-"):
            say("      [!] sk-ant- 로 시작해야 합니다. 다시 확인해 주세요.")
            continue
        say("      확인 중…")
        ok, msg = verify_api_key(key)
        say(f"      {'✔' if ok else '✗'} {msg}")
        if ok:
            write_keys({"ANTHROPIC_API_KEY": key})
            os.environ["ANTHROPIC_API_KEY"] = key
            say(f"      keys.local.bat 에 저장했습니다. ({mask(key)})")
            return True
        if attempt < 2:
            say("      다시 시도하시겠습니까? (건너뛰려면 Enter)")
    return False


def step_subscription():
    """Claude Code 설치 + 로그인. 성공하면 True."""
    if not have("claude"):
        node = version_of("node", "--version")
        if not node:
            say("\n      [!] Node.js 가 없습니다. 구독 방식에 필요합니다.")
            say(f"          {NODE_DL} 에서 Windows Installer (.msi) LTS 를 받아")
            say("          [다음]만 눌러 설치한 뒤, 이 창을 닫고 1_설치.bat 을 다시 누르세요.")
            say("")
            say("          (API 키 방식을 고르면 Node.js 가 아예 필요 없습니다.)")
            try:
                import webbrowser
                webbrowser.open(NODE_DL)
            except Exception:
                pass
            return False
        say(f"\n      Node.js {node} — Claude Code 를 설치합니다.")
        npm = "npm.cmd" if os.name == "nt" else "npm"
        if not run([npm, "install", "-g", "@anthropic-ai/claude-code"],
                   shell=(os.name == "nt")):
            say("      [!] 설치 실패. 관리자 권한 명령창에서:")
            say("          npm install -g @anthropic-ai/claude-code")
            return False
    else:
        say(f"\n      Claude Code 이미 설치됨 — {version_of('claude', '--version') or ''}")

    say("      로그인 확인 중…")
    if login_ok()[0]:
        say("      ✔ 이미 로그인돼 있습니다.")
        return True

    say("      아직 로그인되지 않았습니다.")
    say("      Enter 를 누르면 claude 가 실행됩니다.")
    say("        1) 처음이면 테마 등을 몇 가지 물어봅니다 — 그냥 Enter 로 넘기세요.")
    say("        2) /login 입력 → 브라우저에서 계정 승인")
    say("        3) 끝나면 /exit")
    ask("\n      준비되면 Enter... ")
    run(["claude"], shell=(os.name == "nt"))
    ok = login_ok()[0]
    say("      ✔ 로그인 확인됨." if ok else
        "      ✗ 아직 확인되지 않습니다. 1_설치.bat 을 다시 실행해 보세요.")
    return ok


def login_ok():
    """대화창을 띄우지 않고 로그인 여부만 본다."""
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


def step_claude():
    """방식을 묻고 그쪽을 설정한다. ('api'|'cli'|None, 성공여부)"""
    say("\n[2/3] Claude 연결")
    say("      문답과 채점에 Claude 를 씁니다. 둘 중 하나를 고르세요.")
    say("")
    say("      1) Anthropic API 키   — 키만 있으면 됩니다. Node.js 불필요.")
    say("                             쓴 만큼 과금(아이디어 1건당 대략 300~600원).")
    say("                             기관 서버·폐쇄망에 적합합니다.")
    say("      2) Claude 구독 로그인 — Pro/Max 를 이미 쓰고 계신 경우.")
    say("                             Node.js 설치와 브라우저 로그인이 필요합니다.")
    say("                             추가 과금이 없습니다.")

    # 이미 설정돼 있으면 그 쪽을 기본으로 제시한다.
    have_key = bool(read_keys().get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
    default = "1" if have_key or not have("claude") else "2"
    choice = ask(f"\n      선택 (1 또는 2, 기본 {default}): ", default)

    if choice.startswith("2"):
        return ("cli", step_subscription())
    return ("api", step_api_key())


# ── 3. 마무리 점검 ────────────────────────────────────────────────────
def step_check(mode, ok):
    say("\n[3/3] 점검")
    files = [("① 재정", "data/fiscal.json"),
             ("② KDI 연구", "data/kdi.sqlite"),
             ("④ 해외사례", "data/opsi_policies.db")]
    for label, rel in files:
        p = ROOT / rel
        say(f"      {label:<12} " + (f"{p.stat().st_size/1e6:>7.1f}MB  바로 작동"
                                     if p.exists() else "[!] 없음 — 압축을 다시 푸세요"))
    say("      ③ 국회 의안   웹 첫 화면에서 키를 넣습니다 (선택)")
    say("")
    if mode == "api" and ok:
        say("      Claude       API 키 방식 — 검증 완료")
    elif mode == "cli" and ok:
        say("      Claude       구독 로그인 방식 — 확인 완료")
    else:
        say("      Claude       [!] 아직 설정되지 않았습니다")
    return ok


def main():
    rule("=")
    say("  정책 아이디어 평가 시스템 — 설치")
    say(f"  폴더: {ROOT}")
    rule("=")

    if not step_packages():
        rule()
        say("  파이썬 패키지 설치에서 멈췄습니다. 위 안내를 먼저 처리하세요.")
        rule()
        return 1

    mode, ok = step_claude()
    step_check(mode, ok)

    rule()
    if ok:
        say("  설치가 끝났습니다. 이제 2_실행.bat 을 실행하세요.")
    else:
        say("  Claude 연결이 아직 안 됐습니다. 1_설치.bat 을 다시 실행해 마치세요.")
        say("  (그 상태로도 2_실행.bat 은 뜨지만 문답은 시작되지 않습니다.)")
    rule()
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\n중단했습니다.")
        sys.exit(130)
