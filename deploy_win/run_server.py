#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""서버를 켠다 — 서버_3_직접실행.bat 과 등록된 작업이 함께 부르는 본체.

keys.local.bat 을 실행하지 않고 직접 읽어 환경변수로 올린 뒤 uvicorn 을
띄운다. 배치를 실행하면 창이 하나 더 뜨고 작업 스케줄러에서 다루기 나빠진다.

--proxy-headers 를 붙이지 않는다. 그 옵션은 X-Forwarded-For 를 client.host
로 바꿔치기하는데, /records 의 잠금장치가 보는 것이 바로 그 값이다. 붙이면
밖에서 온 요청이 내부 주소로 위장해 기록 화면을 열 수 있다.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = os.environ.get("PORT", "8000")


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


def main():
    load_keys()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    mode = "personal"
    try:
        m = (ROOT / "mode.txt").read_text(encoding="utf-8").strip().lower()
        if m in ("experiment", "personal"):
            mode = m
    except Exception:
        pass

    print("=" * 62, flush=True)
    print("  정책 아이디어 평가 — 서버", flush=True)
    print(f"  폴더   : {ROOT}", flush=True)
    print(f"  판     : {mode}", flush=True)
    print(f"  주소   : http://{HOST}:{PORT}/policy", flush=True)
    print(f"  접속코드: {os.environ.get('SOCRATIC_ACCESS_CODE', '(없음)')}", flush=True)
    print("=" * 62, flush=True)

    import uvicorn
    uvicorn.run("webapp.app:app", host=HOST, port=int(PORT), workers=1)


if __name__ == "__main__":
    sys.exit(main())
