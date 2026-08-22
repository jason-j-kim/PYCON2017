#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude API 키가 왜 거부되는지 캐묻는다.

"키는 정확한데 401" 이 나오는 이유는 대개 키가 틀려서가 아니라 **붙여넣는
동안 망가져서**다. 눈으로는 구별이 안 된다.

  · 문서·메일에서 복사하다 가운데에 공백이나 줄바꿈이 섞인다
  · 콘솔의 키 목록 화면은 만들 때 한 번만 전체를 보여준다.
    나중에 다시 들어가 복사하면 잘린 값을 가져오게 된다
  · 워드·한글에서 복사하면 보이지 않는 문자(제로폭 공백 등)가 딸려온다

그래서 이 도구는 호출하기 전에 **글자 하나하나를 먼저 본다.** 길이·머리말·
허용되지 않는 글자를 위치까지 찍어 준다. 그다음에 실제로 한 번 호출해
Anthropic 이 뭐라고 답하는지 그대로 보여준다.

키는 화면에 가려서만 나오고 어디에도 저장하지 않는다.

결과는 화면에 찍는 동시에 키확인_결과.txt 에도 남긴다. 창이 닫혀 버려도
읽을 수 있어야 하고, 원인을 남에게 보여줘야 할 때가 있기 때문이다.
그 파일에도 키 전체는 들어가지 않는다.

사용:  4_키확인.bat  를 더블클릭
       python webapp\\check_claude.py
       python webapp\\check_claude.py sk-ant-api03-....
"""
import json
import os
import re
import socket
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "sk-ant-api"
ALLOWED = re.compile(r"[A-Za-z0-9_\-]")
CONSOLE = "https://console.anthropic.com/settings/keys"


LOG = ROOT / "키확인_결과.txt"
_log_lines = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    _log_lines.append(line)


def write_log():
    try:
        LOG.write_text("\n".join(_log_lines) + "\n", encoding="utf-8")
        print(f"\n  이 내용을 파일로도 남겼습니다:\n    {LOG}\n", flush=True)
    except Exception:
        pass


def hold():
    """창이 곧바로 닫히지 않게 붙잡는다. 더블클릭으로 열면 결과가 순식간에
    사라져 아무 소용이 없다."""
    if os.name != "nt" or not sys.stdin.isatty():
        return
    try:
        input("  Enter 를 누르면 닫힙니다. ")
    except Exception:
        pass


def mask(k):
    return f"{k[:14]}…{k[-4:]}" if len(k) > 22 else "(너무 짧음)"


def charname(ch):
    try:
        return unicodedata.name(ch)
    except ValueError:
        return "이름 없는 제어문자"


# ── 키 구하기 ─────────────────────────────────────────────────────────
def from_keys_file():
    f = ROOT / "keys.local.bat"
    if not f.exists():
        return "", ""
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            txt = f.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
        m = re.search(r"^\s*set\s+ANTHROPIC_API_KEY\s*=\s*(.*?)\s*$",
                      txt, re.M | re.I)
        if m:
            return m.group(1).strip().strip('"').strip("'"), "keys.local.bat"
        return "", ""
    return "", ""


def get_key():
    if len(sys.argv) > 1:
        return sys.argv[1].strip(), "명령줄"
    env = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
    if env:
        return env, "이 창의 환경변수"
    k, src = from_keys_file()
    if k:
        return k, src
    say()
    say("  검사할 키를 붙여넣고 Enter 를 누르세요.")
    say("  (웹 화면에 넣으신 것과 '똑같은 방법으로' 복사해 오셔야 합니다.")
    say("   여기서만 다시 정성껏 치면 원인을 놓칩니다.)")
    say()
    try:
        return input("  키: ").strip(), "직접 입력"
    except EOFError:
        return "", "직접 입력"


# ── 1단계: 글자 검사 (호출 전) ────────────────────────────────────────
def inspect(k):
    """(치명적 문제 있나, 의심스러운가) 를 돌려준다."""
    say("-" * 64)
    say("  1단계 — 키의 생김새")
    say("-" * 64)
    say(f"  길이   : {len(k)} 글자")
    say(f"  머리말 : {k[:13] if len(k) >= 13 else k}")
    say(f"  꼬리   : …{k[-6:] if len(k) >= 6 else k}")
    say()

    fatal = False
    warn = False

    if not k:
        say("  ✗ 빈 값입니다.")
        return True, False

    # 머리말
    if not k.startswith(PREFIX):
        say(f"  ✗ Anthropic API 키는 '{PREFIX}03-' 으로 시작합니다.")
        if k.startswith("sk-"):
            say("     'sk-' 로 시작하지만 형식이 다릅니다. 다른 회사 키이거나")
            say("     Claude Code 토큰일 수 있습니다. 콘솔의 API 키가 맞는지 보세요.")
        fatal = True
    else:
        say("  ✓ 머리말은 Anthropic API 키 형식입니다.")

    # 허용되지 않는 글자 — 이것이 '보이지 않는 손상'을 잡는 자리다
    bad = [(i, c) for i, c in enumerate(k) if not ALLOWED.match(c)]
    if bad:
        fatal = True
        say(f"  ✗ 키에 들어갈 수 없는 글자가 {len(bad)}개 섞여 있습니다.")
        say("     API 키는 영문·숫자·하이픈(-)·밑줄(_) 로만 이루어집니다.")
        for i, c in bad[:8]:
            shown = repr(c)[1:-1] or " "
            say(f"       {i+1}번째 글자: {shown!r}  U+{ord(c):04X}  {charname(c)}")
        if len(bad) > 8:
            say(f"       … 그 밖에 {len(bad)-8}개 더")
        say()
        say("     ▶ 붙여넣는 동안 망가진 것입니다. 키 자체는 멀쩡할 수 있습니다.")
        say("       메모장(Notepad)에 먼저 붙여넣어 한 줄인지 확인한 뒤,")
        say("       거기서 다시 복사해 넣어 보세요.")
    else:
        say("  ✓ 허용되지 않는 글자는 없습니다.")

    # 길이 — 잘린 값이 가장 흔한 원인
    if not fatal or k.startswith(PREFIX):
        if len(k) < 60:
            warn = True
            say(f"  ! 길이가 {len(k)} 글자로 짧습니다. 잘렸을 가능성이 큽니다.")
            say("     콘솔의 키 목록 화면은 만들 때 한 번만 전체를 보여줍니다.")
            say("     나중에 다시 들어가 복사하면 잘린 값을 가져오게 됩니다.")
            say(f"     ▶ {CONSOLE} 에서 키를 새로 만들어 그 자리에서 복사하세요.")
        elif len(k) < 95 or len(k) > 120:
            warn = True
            say(f"  ! 길이가 {len(k)} 글자입니다. 보통과 달라 잘렸거나 뭔가")
            say("     더 붙었을 수 있습니다.")

    say()
    return fatal, warn


# ── 2단계: 망이 닿나 ──────────────────────────────────────────────────
def check_net(host):
    say("-" * 64)
    say("  2단계 — 망")
    say("-" * 64)
    base = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
    if base:
        say(f"  ! ANTHROPIC_BASE_URL 이 설정돼 있습니다: {base}")
        say("     호출이 Anthropic 이 아니라 이 주소로 갑니다. 게이트웨이를")
        say("     쓰는 것이 아니라면 이것 때문에 키가 거부될 수 있습니다.")
        say()
    try:
        socket.getaddrinfo(host, 443)
        say(f"  ✓ {host} 주소를 찾았습니다.")
    except Exception as e:
        say(f"  ✗ {host} 주소를 찾지 못했습니다 — {e}")
        say("     방화벽이나 DNS 문제입니다. 망 담당자에게 이 주소를 확인하세요.")
        say()
        return False
    say()
    return True


# ── 3단계: 실제로 한 번 불러 본다 ─────────────────────────────────────
def call(k, base, model):
    say("-" * 64)
    say("  3단계 — 실제 호출")
    say("-" * 64)
    say(f"  주소 : {base}/v1/messages")
    say(f"  모델 : {model}")
    say(f"  키   : {mask(k)}")
    say("  부르는 중 …")
    say()

    body = json.dumps({"model": model, "max_tokens": 1,
                       "messages": [{"role": "user", "content": "hi"}]}).encode()
    req = urllib.request.Request(
        f"{base}/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": k,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        say("  ✓ 정상입니다. 이 키로 호출이 됩니다.")
        say()
        say("    웹 화면에서 401 이 난다면 화면에 넣은 값이 이 값과")
        say("    다른 것입니다. 「Claude 연결」 칸을 비우고 다시 넣으세요.")
        return 0
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        msg = ""
        try:
            msg = json.loads(detail).get("error", {}).get("message", "")
        except Exception:
            msg = detail[:200]
        say(f"  ✗ HTTP {e.code}")
        say(f"    Anthropic 의 답: {msg}")
        say()
        low = (msg or "").lower()
        if e.code == 401:
            say("    ▶ Anthropic 이 이 키를 모른다는 뜻입니다. 세 가지 중 하나입니다.")
            say()
            say("      1. 붙여넣는 동안 값이 바뀌었다 (가장 흔합니다)")
            say("         메모장에 붙여넣어 한 줄인지, 길이가 맞는지 보세요.")
            say("      2. 콘솔에서 그 키를 폐기(revoke)했다")
            say(f"         {CONSOLE} 에서 키가 목록에 살아 있는지 보세요.")
            say("      3. 다른 조직·계정의 키다")
            say("         콘솔 왼쪽 위에서 조직을 바꿔 가며 확인하세요.")
            say()
            say("      ※ 잔액 부족이나 한도 초과는 401 이 아니라 400 으로")
            say("        나옵니다. 지금은 잔액 문제가 아닙니다.")
        elif e.code == 400 and "credit" in low:
            say("    ▶ 잔액이 부족합니다. 키는 맞습니다.")
            say("      콘솔 Billing 에서 결제 수단과 잔액을 확인하세요.")
        elif e.code == 403:
            say("    ▶ 키는 인정되지만 권한이 없습니다. 조직 설정이나")
            say("      키에 걸린 제한을 확인하세요.")
        elif e.code == 404 and "model" in low:
            say(f"    ▶ 이 계정에서 «{model}» 을 쓸 수 없습니다. 키 문제가 아닙니다.")
        elif e.code == 429:
            say("    ▶ 요청 한도를 넘었습니다. 키는 맞습니다. 잠시 뒤 다시 하세요.")
        else:
            say(f"    ▶ 전문: {detail[:300]}")
        return 1
    except urllib.error.URLError as e:
        say(f"  ✗ 닿지 못했습니다 — {e.reason}")
        say("    방화벽이 api.anthropic.com 을 막고 있을 수 있습니다.")
        return 1


def main():
    say()
    say("=" * 64)
    say("  Claude API 키 진단")
    say("=" * 64)

    k, src = get_key()
    if not k:
        say("\n  키가 없습니다.\n")
        return 1
    say()
    say(f"  검사 대상: {src} 에서 가져온 키")
    say()

    fatal, warn = inspect(k)
    if fatal:
        say("=" * 64)
        say("  키의 생김새부터 잘못됐습니다. 호출해 봐야 같은 답만 옵니다.")
        say("  위 표시를 먼저 잡고 다시 실행하세요.")
        say("=" * 64)
        say()
        return 1

    base = (os.environ.get("ANTHROPIC_BASE_URL", "").strip()
            or "https://api.anthropic.com").rstrip("/")
    host = base.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
    if not check_net(host):
        return 1

    model = os.environ.get("CLAUDE_MODEL", "").strip() or "claude-opus-5"
    rc = call(k, base, model)
    say()
    say("=" * 64)
    say()
    return rc


if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    except KeyboardInterrupt:
        say("\n  중단했습니다.")
    except Exception as e:
        # 뜻밖의 고장도 화면에 남겨야 한다. 조용히 닫히면 아무것도 알 수 없다.
        import traceback
        say("\n  진단 도구 자체가 멈췄습니다 — " + repr(e))
        say(traceback.format_exc())
    finally:
        write_log()
        hold()
    sys.exit(rc)
