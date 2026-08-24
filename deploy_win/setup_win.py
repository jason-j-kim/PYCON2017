#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""윈도우 서버 설치 — 서버_1_설치.bat 이 부르는 본체.

리눅스판의 setup_server.sh 와 같은 일을 한다. 다만 윈도우에는 systemd 가
없으므로 서비스 등록은 다음 단계(서버_2_서비스등록.bat)로 나눈다.

배치에 한국어와 로직을 담으면 인코딩(CP949/UTF-8)과 줄바꿈에 따라 깨진다.
그래서 배치는 `python deploy_win\\setup_win.py` 한 줄만 하고 나머지는 여기서
한다. 이 규칙은 이 저장소 전체에서 지킨다.
"""
import os
import secrets
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
KEYS = ROOT / "keys.local.bat"
PY = VENV / "Scripts" / "python.exe"
UVICORN = VENV / "Scripts" / "uvicorn.exe"


def say(*a):
    print(*a, flush=True)


def rule(ch="-"):
    say(ch * 64)


def hold():
    """더블클릭으로 열면 결과가 순식간에 사라진다. 붙잡아 둔다."""
    if sys.stdin.isatty():
        try:
            input("\n  Enter 를 누르면 닫힙니다. ")
        except Exception:
            pass


def read_mode():
    f = ROOT / "mode.txt"
    try:
        m = f.read_text(encoding="utf-8").strip().lower()
        return m if m in ("experiment", "personal") else "personal"
    except Exception:
        return "personal"


def read_keys():
    if not KEYS.exists():
        return {}
    import re
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
    """기존 값을 지키며 덮어쓴다. 여기에 키가 들어가므로 남에게 주지 않는다."""
    merged = {**read_keys(), **{k: v for k, v in values.items() if v}}
    lines = ["@echo off",
             "REM 서버_1_설치.bat 이 만든 파일입니다. 기관의 것이니 함께 배포하지 마세요."]
    lines += [f"set {k}={v}" for k, v in merged.items()]
    KEYS.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def make_code(n=8):
    """소문자·숫자 n 자. 짧은 접속 코드는 없느니만 못하므로 길이를 보장한다."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def step_python():
    say("\n[1/4] 파이썬 확인")
    say(f"      {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 10):
        say("      [!] 3.10 이상이 필요합니다. python.org 에서 새로 설치하세요.")
        return False
    return True


def step_venv():
    say("\n[2/4] 가상환경과 파이썬 꾸러미")
    if not VENV.exists():
        if subprocess.call([sys.executable, "-m", "venv", str(VENV)]) != 0:
            say("      [!] 가상환경을 만들지 못했습니다.")
            return False
        say(f"      만듦 — {VENV}")
    else:
        say(f"      이미 있음 — {VENV}")
    if not PY.exists():
        say(f"      [!] {PY} 가 없습니다. .venv 폴더를 지우고 다시 실행하세요.")
        return False
    subprocess.call([str(PY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    rc = subprocess.call([str(PY), "-m", "pip", "install", "-q", "-r",
                          str(ROOT / "webapp" / "requirements.txt")])
    if rc != 0:
        say("      [!] 설치 실패. 인터넷 연결과 프록시 설정을 확인하세요.")
        return False
    if not UVICORN.exists():
        say(f"      [!] {UVICORN} 가 없습니다.")
        return False
    say("      완료 — fastapi · uvicorn 확인")
    return True


def step_settings():
    say("\n[3/4] 운영 설정")
    cur = read_keys()
    mode = read_mode()
    say(f"      판: {mode}")

    code = cur.get("SOCRATIC_ACCESS_CODE", "")
    if not code:
        code = make_code()
        say(f"      접속 코드를 새로 만들었습니다: {code}")
        say("      ← 방문자에게 알려 줄 값입니다. 적어 두세요.")
    else:
        say(f"      접속 코드: {code}  (이미 설정돼 있어 그대로 둡니다)")

    limit = cur.get("SOCRATIC_MAX_SESSIONS_PER_DAY", "") or "100"

    vals = {"SOCRATIC_ACCESS_CODE": code,
            "SOCRATIC_MAX_SESSIONS_PER_DAY": limit}

    if mode == "experiment":
        if not cur.get("ANTHROPIC_API_KEY"):
            say("")
            say("      [!] experiment 판인데 기관 API 키가 없습니다.")
            say("          keys.local.bat 에 set ANTHROPIC_API_KEY=sk-ant-… 를")
            say("          넣고 이 창을 다시 실행하세요.")
    else:
        if cur.get("ANTHROPIC_API_KEY"):
            say("")
            say("      [!] personal 판인데 서버에 ANTHROPIC_API_KEY 가 있습니다.")
            say("          이러면 방문자가 키를 안 넣어도 이 키로 돌아가")
            say("          요금이 기관에 붙습니다. keys.local.bat 에서 지우세요.")

    write_keys(vals)
    say(f"      저장 — {KEYS}")
    return True


def step_check():
    say("\n[4/4] 평가에 쓰는 자료")
    ok = True
    for label, rel in [("① 재정", "data/fiscal.json"),
                       ("② KDI 연구", "data/kdi.sqlite"),
                       ("④ 해외사례", "data/opsi_policies.db")]:
        p = ROOT / rel
        if p.exists():
            say(f"      {label:<12} {p.stat().st_size/1e6:>7.1f}MB  바로 작동")
        else:
            say(f"      {label:<12} [!] 없음 — 압축을 다시 푸세요")
            ok = False
    say("      ③ 국회 의안   keys.local.bat 의 ASSEMBLY_KEY 또는 화면에서 (선택)")
    return ok


def main():
    rule("=")
    say("  정책 아이디어 평가 — 윈도우 서버 설치")
    say(f"  폴더: {ROOT}")
    rule("=")

    if os.name != "nt":
        say("\n  [i] 윈도우가 아닙니다. 리눅스라면 deploy/setup_server.sh 를 쓰세요.")

    if not step_python():
        rule(); hold(); return 1
    if not step_venv():
        rule(); hold(); return 1
    step_settings()
    data_ok = step_check()

    rule()
    say("  설치가 끝났습니다. 남은 것은 둘입니다.")
    say("")
    say("    서버_2_서비스등록.bat   부팅 때 자동으로 켜지게 등록합니다")
    say("                            (관리자 권한으로 실행하세요)")
    say("")
    say("    그다음 IIS 로 앞단을 걸고 인증서를 붙입니다.")
    say("    deploy_win\\README.md 와 서버설치_안내_윈도우.docx 를 보세요.")
    say("")
    say("  먼저 손으로 한 번 켜 보시려면:")
    say("    서버_3_직접실행.bat        (창을 닫으면 꺼집니다)")
    rule()
    hold()
    return 0 if data_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\n중단했습니다.")
        sys.exit(130)
