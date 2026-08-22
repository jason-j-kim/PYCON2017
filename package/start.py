#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""서버 실행 — 2_실행.bat 이 부르는 본체.

포트 정리 → 키 적재 → 브라우저 열기 → 서버 기동까지 여기서 한다.
배치에는 로직을 두지 않는다(인코딩·줄바꿈에 취약해서).
"""
import os
import re
import subprocess
import sys
import threading
import time
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
    free_port()

    say(f"  초대 코드 : {os.environ['SOCRATIC_ACCESS_CODE']}")
    say(f"  주소      : {URL}")
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
