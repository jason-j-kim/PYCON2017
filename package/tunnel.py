#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""외부 공개(터널) — 3_터널.bat 이 부르는 본체."""
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8000"))
DL = ("https://developers.cloudflare.com/cloudflare-one/connections/"
      "connect-networks/downloads/")


def say(*a):
    print(*a, flush=True)


def find_cloudflared():
    """PATH 에 없으면 이 폴더에 둔 실행 파일도 찾아 준다."""
    p = shutil.which("cloudflared")
    if p:
        return p
    for name in ("cloudflared.exe", "cloudflared"):
        cand = ROOT / name
        if cand.exists():
            return str(cand)
    return None


def server_alive():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/config", timeout=3)
        return True
    except Exception:
        return False


def main():
    say("=" * 62)
    say("  외부 공개 (터널)")
    say("=" * 62)

    if not server_alive():
        say(f"  [!] 서버가 꺼져 있습니다 (localhost:{PORT} 응답 없음).")
        say("      2_실행.bat 을 먼저 켜 두고, 이 창은 따로 띄우세요.")
        return 1
    say("  서버 확인됨.")

    exe = find_cloudflared()
    if not exe:
        say("  [!] cloudflared 가 없습니다.")
        say("")
        say(f"      {DL}")
        say("      에서 Windows 64-bit 를 받아 cloudflared.exe 를")
        say(f"      이 폴더({ROOT})에 두고 다시 실행하세요.")
        return 1

    say("")
    say("  잠시 뒤 아래 형태의 주소가 나옵니다.")
    say("      https://····.trycloudflare.com")
    say("  그 주소 뒤에 /policy 를 붙여 공유하세요.")
    say("")
    say("  ※ 켤 때마다 주소가 바뀝니다. 이 창을 닫으면 외부 접속이 끊깁니다.")
    say("=" * 62)
    say("")

    try:
        return subprocess.call([exe, "tunnel", "--url", f"http://localhost:{PORT}"])
    except KeyboardInterrupt:
        say("\n  터널을 껐습니다.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
