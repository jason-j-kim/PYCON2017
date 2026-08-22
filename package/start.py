#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""서버 실행 — 2_실행.bat 이 부르는 본체.

Claude 연결을 여기서 정한다. 설치가 아니라 실행 시점인 이유는, 설치하는
사람과 실제로 실험하는 사람이 다르기 때문이다. 실험하는 분이 자기 키를
직접 넣어야 한다.

연결 방법이 하나도 없을 때만 물어본다. 이미 있으면 묻지 않고 바로 뜬다.

포트 정리 → 연결 확인 → 브라우저 열기 → 서버 기동까지 여기서 한다.
배치에는 로직을 두지 않는다(인코딩·줄바꿈에 취약해서).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8000"))
URL = f"http://localhost:{PORT}/policy"

# 접속 코드 — 바꾸고 싶으면 이 줄을 고치거나, keys.local.bat 에
# set SOCRATIC_ACCESS_CODE=원하는코드 를 넣으세요.
DEFAULT_CODE = "kdi2026"


def say(*a):
    print(*a, flush=True)


CONSOLE = "https://console.anthropic.com/settings/keys"


def read_mode():
    """experiment: 기관 키로 운영 · personal: 각자 키/구독."""
    try:
        m = (ROOT / "mode.txt").read_text(encoding="utf-8").strip().lower()
        return m if m in ("experiment", "personal") else "personal"
    except Exception:
        return "personal"


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def login_ok():
    """claude CLI 가 로그인돼 있나. 대화창은 띄우지 않는다."""
    if not shutil.which("claude"):
        return False
    try:
        r = subprocess.run(["claude", "-p", "OK만 출력하라.", "--tools", ""],
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace",
                           shell=(os.name == "nt"))
        return r.returncode == 0
    except Exception:
        return False


def verify_api_key(key):
    """진짜로 한 번 불러 본다. (ok, 사람이 읽을 메시지)"""
    base = (os.environ.get("ANTHROPIC_BASE_URL")
            or "https://api.anthropic.com").rstrip("/")
    model = os.environ.get("CLAUDE_MODEL") or "claude-opus-5"
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
        d = ""
        try:
            d = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        if e.code == 401:
            return False, "키가 거부되었습니다(401). 콘솔에서 키를 다시 확인하세요."
        if e.code == 400 and "credit" in d.lower():
            return False, "잔액이 부족합니다. 콘솔에서 결제 수단을 등록하세요."
        if e.code == 429:
            return False, "요청 한도를 넘었습니다(429). 잠시 뒤 다시 시도하세요."
        if e.code == 404:
            return False, f"모델 {model} 을 쓸 수 없습니다. 콘솔에서 확인하세요."
        return False, f"오류 HTTP {e.code}: {d}"
    except urllib.error.URLError as e:
        return False, (f"{base} 에 닿지 못했습니다: {e.reason}  "
                       "방화벽이 이 주소를 막고 있는지 확인하세요.")


def save_key(key):
    """keys.local.bat 에 남긴다. 여러 사람이 쓰는 PC 라면 저장하지 않는 편이 낫다."""
    f = ROOT / "keys.local.bat"
    keep = []
    if f.exists():
        for enc in ("utf-8", "cp949", "latin-1"):
            try:
                keep = [ln for ln in f.read_text(encoding=enc).splitlines()
                        if ln.strip() and not re.match(r"^\s*@echo|^\s*REM",
                                                       ln, re.I)
                        and not re.match(r"^\s*set\s+ANTHROPIC_API_KEY", ln, re.I)]
                break
            except UnicodeDecodeError:
                continue
    lines = ["@echo off",
             "REM 2_실행.bat 이 만든 파일입니다. 본인 것이니 남에게 주지 마세요."]
    lines += keep + [f"set ANTHROPIC_API_KEY={key}"]
    f.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def choose_connection():
    """연결 방법이 하나도 없을 때만 묻는다. 정해지면 True."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    say("")
    say("  Claude 연결이 아직 없습니다. 실험하실 분이 여기서 정하시면 됩니다.")
    say("")
    say("  · Anthropic API 키를 쓰시려면 아래에 붙여넣으세요.")
    say(f"      발급: {CONSOLE}   (sk-ant- 로 시작)")
    say("      쓴 만큼 본인 계정에 과금됩니다(아이디어 1건당 대략 300~600원).")
    say("  · Claude 구독(Pro/Max)을 쓰시려면 그냥 Enter 를 누르세요.")
    say("")

    key = ask("  API 키 (구독을 쓰려면 Enter): ")
    if not key:
        if login_ok():
            say("  구독 로그인 확인됨.")
            return True
        say("")
        say("  [!] 구독 로그인이 안 돼 있습니다.")
        if shutil.which("claude"):
            say("      명령창에서 `claude` 를 실행해 /login 한 뒤 다시 시도하세요.")
        else:
            say("      Claude Code 가 없습니다. 1_설치.bat 을 다시 실행하거나,")
            say("      API 키를 쓰시는 편이 빠릅니다(Node.js 불필요).")
        say("")
        say("      이대로 서버는 뜨지만 문답은 시작되지 않습니다.")
        say("      웹 첫 화면에서 API 키를 넣으셔도 됩니다.")
        return False

    if not key.startswith("sk-ant-"):
        say("  [!] sk-ant- 로 시작해야 합니다. 웹 첫 화면에서 다시 넣으셔도 됩니다.")
        return False
    say("  확인 중…")
    ok, msg = verify_api_key(key)
    say(f"  {'✔' if ok else '✗'} {msg}")
    if not ok:
        say("  이대로 서버는 뜹니다. 웹 첫 화면에서 다시 넣으실 수 있습니다.")
        return False

    os.environ["ANTHROPIC_API_KEY"] = key
    if ask("  이 폴더에 저장해 다음부터 묻지 않게 할까요? (y/N): ").lower().startswith("y"):
        save_key(key)
        say("  keys.local.bat 에 저장했습니다.")
    else:
        say("  저장하지 않았습니다 — 이번 실행에만 씁니다.")
    return True


def auth_line():
    """Claude를 API로 부르는지 구독 로그인으로 부르는지 한 줄로."""
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if key:
        masked = f"{key[:7]}…{key[-4:]}" if len(key) > 14 else "설정됨"
        model = (os.environ.get("CLAUDE_MODEL") or "claude-opus-5").strip()
        return f"API 키 방식 (키 {masked} · 모델 {model})"
    return "구독 로그인 방식 (claude CLI)"


# ── keys.local.bat 적재 (배치를 실행하지 않고 직접 읽는다) ────────────
def load_keys():
    f = ROOT / "keys.local.bat"
    if not f.exists():
        return
    txt = None
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            txt = f.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if txt is None:
        return
    for m in re.finditer(r"^\s*set\s+([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$",
                         txt, re.M | re.I):
        name, val = m.group(1).upper(), m.group(2).strip().strip('"').strip("'")
        if val:
            os.environ[name] = val


# ── 포트에 남은 이전 서버 정리 (10048 예방) ──────────────────────────
def free_port():
    """포트를 잡고 있는 프로세스를 찾아 그것만 끝낸다."""
    pids = set()
    try:
        if os.name == "nt":
            out = subprocess.check_output(["netstat", "-ano"], text=True,
                                          stderr=subprocess.DEVNULL, timeout=30)
            for line in out.splitlines():
                if f":{PORT} " in line and "LISTENING" in line.upper():
                    parts = line.split()
                    if parts and parts[-1].isdigit():
                        pids.add(parts[-1])
        else:
            out = subprocess.check_output(["bash", "-c", f"lsof -ti tcp:{PORT} || true"],
                                          text=True, timeout=30)
            pids = {p for p in out.split() if p.isdigit()}
    except Exception:
        return
    me = str(os.getpid())
    for pid in pids - {me}:
        say(f"  이전 서버(PID {pid})가 포트 {PORT}을 잡고 있어 정리합니다.")
        try:
            if os.name == "nt":
                subprocess.call(["taskkill", "/F", "/PID", pid],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(int(pid), 9)
        except Exception as e:
            say(f"  (정리 실패: {e} — 수동으로 끄셔야 할 수 있습니다)")
    if pids - {me}:
        time.sleep(2)


# ── 서버가 뜬 뒤 브라우저를 연다 ─────────────────────────────────────
def open_browser_when_ready():
    import urllib.request
    for _ in range(60):                      # 최대 60초 대기
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/config", timeout=2)
        except Exception:
            continue
        try:
            webbrowser.open(URL)
        except Exception:
            pass
        return
    say("  (서버 응답이 늦어 브라우저를 자동으로 열지 못했습니다. 위 주소를 직접 여세요.)")


def main():
    load_keys()
    os.environ.setdefault("SOCRATIC_ACCESS_CODE", DEFAULT_CODE)

    say("=" * 62)
    say("  정책 아이디어 평가 시스템 — 서버")
    say("=" * 62)

    mode = read_mode()
    if mode == "experiment":
        # 기관이 설치 때 정해 둔다. 여기서 묻지 않는다.
        if not os.environ.get("ANTHROPIC_API_KEY"):
            say("")
            say("  [!] 기관 API 키가 설정돼 있지 않습니다.")
            say("      1_설치.bat 을 실행해 운영 설정을 마치세요.")
            say("      (참여자는 초대 코드만 넣으면 되는 판입니다.)")
            say("")
    elif not os.environ.get("ANTHROPIC_API_KEY") and not login_ok():
        # 실행하는 사람 = 실험하는 사람. 여기서 정한다.
        choose_connection()

    free_port()

    say(f"  판       : " + ("실험용 (기관 키 · 참여자는 초대 코드만)"
                            if mode == "experiment" else "개인용 (각자 키 또는 구독)"))
    say(f"  초대 코드 : {os.environ['SOCRATIC_ACCESS_CODE']}")
    say(f"  주소      : {URL}")
    say(f"  Claude    : {auth_line()}")
    if os.environ.get("ASSEMBLY_KEY"):
        say("  국회 의안 : 서버 기본키 있음 — 화면에서 비워 두면 이 키를 씁니다")
    else:
        say("  국회 의안 : 서버 기본키 없음 — 웹 첫 화면에서 넣으세요(선택).")
        say("              비워 두면 ③만 빼고 나머지 세 통로로 평가합니다.")
    say("")
    say("  잠시 뒤 브라우저가 자동으로 열립니다.")
    say("  끌 때는 이 창에서 Ctrl+C 를 누르세요.")
    say("=" * 62)
    say("")

    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    app = ROOT / "webapp" / "app.py"
    if not app.exists():
        say(f"  [!] {app} 가 없습니다. 압축을 덜 푼 것 같습니다.")
        return 1
    try:
        return subprocess.call([sys.executable, str(app)], cwd=str(ROOT))
    except KeyboardInterrupt:
        say("\n  서버를 껐습니다.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
