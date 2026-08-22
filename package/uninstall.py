#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""설치된 것 제거 — 0_제거.bat 이 부르는 본체.

401 이 사라지지 않을 때 대개 원인은 코드가 아니라 '지난번에 남은 값'이다.
키는 네 군데에 남는다. 어느 하나라도 살아 있으면 새 zip 을 풀어도 그대로
따라온다.

  1) 브라우저에 저장한 키      1순위 — 서버 설정을 이깁니다
  2) keys.local.bat            2순위 — 폴더 안
  3) 윈도우 사용자 환경변수     2순위 — 폴더를 지워도 남습니다
  4) __pycache__               옛 코드가 실행될 수 있습니다

셋째가 특히 고약하다. 폴더를 통째로 지우고 새로 풀어도 살아남는다.

먼저 무엇이 있는지 모두 보여주고, 그다음에 지운다. 지우기 전에 반드시
묻는다. 연구 자료(sessions.db)는 따로 확인받지 않으면 건드리지 않는다.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_NAMES = ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
             "CLAUDE_MODEL", "ASSEMBLY_KEY", "SOCRATIC_ACCESS_CODE"]


def say(*a):
    print(*a, flush=True)


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def mask(v):
    v = (v or "").strip()
    if not v:
        return "(빈 값)"
    return f"{v[:11]}…{v[-4:]}" if len(v) > 18 else "(짧은 값)"


# ── 1. 무엇이 남아 있나 ───────────────────────────────────────────────
def find_keys_file():
    f = ROOT / "keys.local.bat"
    return f if f.exists() else None


def read_user_env():
    """윈도우 사용자 환경변수(HKCU\\Environment). 폴더를 지워도 남는 것."""
    if os.name != "nt":
        return {}
    found = {}
    for name in ENV_NAMES:
        try:
            out = subprocess.run(["reg", "query", "HKCU\\Environment", "/v", name],
                                 capture_output=True, text=True, timeout=20)
        except Exception:
            return {}
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                parts = line.split(None, 2)
                if len(parts) == 3 and parts[0].upper() == name:
                    found[name] = parts[2].strip()
    return found


def read_machine_env():
    """시스템 전체 환경변수. 지우려면 관리자 권한이 필요해 알려만 준다."""
    if os.name != "nt":
        return {}
    key = "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment"
    found = {}
    for name in ENV_NAMES:
        try:
            out = subprocess.run(["reg", "query", key, "/v", name],
                                 capture_output=True, text=True, timeout=20)
        except Exception:
            return {}
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                parts = line.split(None, 2)
                if len(parts) == 3 and parts[0].upper() == name:
                    found[name] = parts[2].strip()
    return found


def find_caches():
    return sorted(p for p in ROOT.rglob("__pycache__") if p.is_dir())


def find_other_copies():
    """다른 데 풀어 둔 옛 폴더. 옛것을 켜 놓고 새것을 고쳐 봐야 소용없다."""
    if os.name != "nt":
        return []
    home = Path.home()
    roots = [home, home / "Desktop", home / "Downloads", home / "Documents",
             home / "OneDrive", home / "OneDrive" / "바탕 화면",
             home / "OneDrive" / "Desktop", Path("C:/")]
    hits, seen = [], set()
    for r in roots:
        try:
            if not r.is_dir():
                continue
            for p in r.glob("정책아이디어평가*"):
                if p.is_dir() and (p / "start.py").exists():
                    rp = p.resolve()
                    if rp != ROOT and rp not in seen:
                        seen.add(rp)
                        hits.append(rp)
        except Exception:
            continue
    return hits


def find_sessions():
    f = ROOT / "webapp" / "sessions.db"
    return f if f.exists() else None


# ── 2. 지우기 ─────────────────────────────────────────────────────────
def del_user_env(names):
    ok = []
    for name in names:
        try:
            r = subprocess.run(["reg", "delete", "HKCU\\Environment", "/v", name, "/f"],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                ok.append(name)
        except Exception:
            pass
    return ok


def main():
    say()
    say("=" * 62)
    say("  정책 아이디어 평가 — 남은 설정 제거")
    say("=" * 62)
    say()
    say("  401(인증 실패)이 계속되면 대개 코드가 아니라 지난번에 남은")
    say("  값이 원인입니다. 남을 수 있는 곳을 모두 훑습니다.")
    say()
    say(f"  이 폴더: {ROOT}")
    say()

    keys = find_keys_file()
    user_env = read_user_env()
    machine_env = read_machine_env()
    caches = find_caches()
    others = find_other_copies()
    sess = find_sessions()

    say("-" * 62)
    say("  찾은 것")
    say("-" * 62)
    n = 0

    if keys:
        n += 1
        say(f"  [1] keys.local.bat        {keys}")
        try:
            for ln in keys.read_text(encoding="utf-8", errors="replace").splitlines():
                s = ln.strip()
                if s.lower().startswith("set ") and "=" in s:
                    k, v = s[4:].split("=", 1)
                    k = k.strip().upper()
                    say(f"        {k} = " + (mask(v) if "KEY" in k or "TOKEN" in k else v.strip()))
        except Exception:
            say("        (읽지 못했습니다)")
    else:
        say("  [1] keys.local.bat        없음")

    if user_env:
        n += 1
        say("  [2] 윈도우 사용자 환경변수  ← 폴더를 지워도 남는 것")
        for k, v in user_env.items():
            say(f"        {k} = " + (mask(v) if "KEY" in k or "TOKEN" in k else v))
    else:
        say("  [2] 윈도우 사용자 환경변수  없음")

    if caches:
        n += 1
        say(f"  [3] __pycache__           {len(caches)}개")
    else:
        say("  [3] __pycache__           없음")

    say()
    if machine_env:
        say("  [!] 시스템 전체 환경변수에도 값이 있습니다 (관리자 권한 필요):")
        for k, v in machine_env.items():
            say(f"        {k} = " + (mask(v) if "KEY" in k or "TOKEN" in k else v))
        say("      제거하려면 관리자 명령 프롬프트에서:")
        for k in machine_env:
            say(f'        setx /M {k} ""')
        say()

    if others:
        say("  [!] 다른 곳에도 이 프로그램 폴더가 있습니다:")
        for p in others:
            say(f"        {p}")
        say("      옛 폴더를 켜 두고 새 폴더를 고쳐 봐야 소용없습니다.")
        say("      쓰지 않는 것은 직접 지우세요. 여기서는 건드리지 않습니다.")
        say()

    if n == 0:
        say("  이 폴더와 윈도우에는 지울 것이 없습니다.")
    else:
        say("-" * 62)
        a = ask(f"  위 [1]~[3] 을 지웁니다. 진행할까요? (Y/n) ")
        if a.lower() in ("", "y", "ye", "yes"):
            if keys:
                try:
                    keys.unlink()
                    say("  지웠습니다 — keys.local.bat")
                except Exception as e:
                    say(f"  실패 — keys.local.bat ({e})")
            if user_env:
                done = del_user_env(list(user_env))
                if done:
                    say("  지웠습니다 — 환경변수 " + ", ".join(done))
                    say("     ※ 이미 열린 명령창에는 옛 값이 남습니다.")
                    say("       모든 검은 창을 닫고 새로 여세요.")
                rest = [k for k in user_env if k not in done]
                if rest:
                    say("  실패 — " + ", ".join(rest))
            if caches:
                for p in caches:
                    shutil.rmtree(p, ignore_errors=True)
                say(f"  지웠습니다 — __pycache__ {len(caches)}개")
        else:
            say("  건드리지 않았습니다.")

    # ── 브라우저 — 여기서 지울 수 없는 유일한 곳, 그리고 1순위 ──
    say()
    say("-" * 62)
    say("  [4] 브라우저에 저장한 키 — 여기서는 지울 수 없습니다")
    say("-" * 62)
    say("  이것이 1순위입니다. 살아 있으면 위를 다 지워도 그 키로 호출하고,")
    say("  그 키가 틀렸으면 401 이 계속됩니다.")
    say()
    say("  지우는 법 — 둘 중 아무거나:")
    say()
    say("    ㄱ. 2_실행.bat 을 켠 뒤 주소창에 붙여넣기")
    say("        http://localhost:8000/policy?reset=1")
    say("        (열리면서 저장된 키가 지워집니다)")
    say()
    say("    ㄴ. 평가 화면 「Claude 연결」 칸의")
    say("        [비우고 서버 설정으로] 단추")
    say()

    if sess:
        mb = sess.stat().st_size / 1e6
        say("-" * 62)
        say(f"  연구 자료  webapp\\sessions.db ({mb:.1f}MB) — 그대로 두었습니다")
        say("-" * 62)
        say("  문답·채점 기록입니다. 401 과는 상관이 없으니 지우지 마세요.")
        say("  정말 비우려면 그 파일을 직접 지우시면 됩니다.")
        say()

    say("=" * 62)
    say("  끝났습니다. 다음 순서:")
    say("    1. 열려 있는 검은 창을 모두 닫으세요")
    say("    2. 위 [4] 로 브라우저 키를 지우세요")
    say("    3. 2_실행.bat 을 다시 켜세요")
    say("=" * 62)
    say()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("\n  중단했습니다.")
        sys.exit(1)
