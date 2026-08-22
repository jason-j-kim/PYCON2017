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


# ── 2. Claude Code (선택) ─────────────────────────────────────────────
# 여기서 API 키를 묻지 않는다. 설치하는 사람과 실제로 실험하는 사람이 다르다.
# 설치자가 남의 키를 대신 넣게 되거나, 실험자가 설치를 다시 돌려야 한다.
# Claude 연결은 2_실행 할 때 정한다.
def login_ok():
    """대화창을 띄우지 않고 로그인 여부만 본다."""
    try:
        r = subprocess.run(["claude", "-p", "OK만 출력하라.", "--tools", ""],
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace",
                           shell=(os.name == "nt"))
        return r.returncode == 0
    except Exception:
        return False


def step_claude_code():
    """구독 로그인을 쓸 사람을 위해 Claude Code 를 준비해 둔다.

    강요하지 않는다. Node.js 가 없으면 안내만 하고 넘어간다 — API 키로
    쓸 사람에게는 Node.js 가 아예 필요 없기 때문이다."""
    say("\n[2/2] Claude Code (선택)")
    if have("claude"):
        say(f"      이미 설치됨 — {version_of('claude', '--version') or 'claude'}")
        say("      로그인 " + ("확인됨." if login_ok() else
                              "안 됨 — 구독으로 쓰시려면 명령창에서 `claude` → /login"))
        return True

    node = version_of("node", "--version")
    if not node:
        say("      Node.js 가 없어 건너뜁니다.")
        say("      → Anthropic API 키로 쓰실 거라면 이대로 두셔도 됩니다.")
        say("         (Node.js 도 Claude Code 도 필요 없습니다.)")
        say(f"      → Claude 구독(Pro/Max)으로 쓰시려면 {NODE_DL} 에서")
        say("         Node.js LTS 를 설치한 뒤 1_설치.bat 을 다시 실행하세요.")
        return True

    say(f"      Node.js {node} — Claude Code 를 설치합니다.")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    if run([npm, "install", "-g", "@anthropic-ai/claude-code"], shell=(os.name == "nt")):
        say("      완료. 구독으로 쓰시려면 명령창에서 `claude` → /login 하세요.")
    else:
        say("      [!] 설치 실패. 관리자 권한 명령창에서:")
        say("          npm install -g @anthropic-ai/claude-code")
        say("      (API 키로 쓰실 거라면 없어도 됩니다.)")
    return True


# ── 마무리 점검 ──────────────────────────────────────────────────────
def step_check():
    say("\n[점검] 평가에 쓰는 자료")
    for label, rel in [("① 재정", "data/fiscal.json"),
                       ("② KDI 연구", "data/kdi.sqlite"),
                       ("④ 해외사례", "data/opsi_policies.db")]:
        p = ROOT / rel
        say(f"      {label:<12} " + (f"{p.stat().st_size/1e6:>7.1f}MB  바로 작동"
                                     if p.exists() else "[!] 없음 — 압축을 다시 푸세요"))
    say("      ③ 국회 의안   웹 첫 화면에서 키를 넣습니다 (선택)")


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
    step_claude_code()
    step_check()

    rule()
    say("  설치가 끝났습니다. 이제 2_실행.bat 을 실행하세요.")
    say("")
    say("  Claude 연결은 여기서 정하지 않습니다 — 실행할 때 정합니다.")
    say("  2_실행.bat 이 처음 한 번 물어봅니다.")
    say("")
    say("     · Anthropic API 키를 붙여넣거나")
    say("     · 그냥 Enter 를 눌러 Claude 구독 로그인을 쓰거나")
    say("")
    say("  실험하는 분이 직접 자기 키를 넣으시면 됩니다.")
    rule()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\n중단했습니다.")
        sys.exit(130)
