#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부팅 때 자동으로 켜지게 등록한다 — 서버_2_서비스등록.bat 이 부르는 본체.

윈도우에는 systemd 가 없다. 서비스로 만드는 길은 셋인데, 여기서는 셋째를
쓴다.

  NSSM        가장 흔하지만 외부 실행 파일을 따로 받아야 한다. 기관 서버에
              출처가 분명하지 않은 바이너리를 들이는 것은 승인이 어렵다.
  pywin32     파이썬 꾸러미를 하나 더 깔고 서비스 클래스를 써야 한다.
  작업 스케줄러  윈도우에 이미 들어 있다. 받을 것이 없다.  ← 이것을 쓴다

작업 스케줄러도 부팅 시 자동 실행·실패 시 재시작·로그온 없이 실행을 모두
한다. 서비스 목록(services.msc)에 안 보인다는 점만 다르다.

사용:
    python deploy_win\\service_win.py --install    등록
    python deploy_win\\service_win.py --status     상태
    python deploy_win\\service_win.py --start      지금 켜기
    python deploy_win\\service_win.py --stop       지금 끄기
    python deploy_win\\service_win.py --remove     등록 해제
"""
import ctypes
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = "PolicyEval"
PYW = ROOT / ".venv" / "Scripts" / "pythonw.exe"     # 창 없이
PY = ROOT / ".venv" / "Scripts" / "python.exe"
RUNNER = ROOT / "deploy_win" / "run_server.py"
XML = ROOT / "deploy_win" / "_task.xml"


def say(*a):
    print(*a, flush=True)


def hold():
    if sys.stdin.isatty():
        try:
            input("\n  Enter 를 누르면 닫힙니다. ")
        except Exception:
            pass


def is_admin():
    if os.name != "nt":
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run(args):
    """schtasks 는 CP949 로 답한다. 깨지지 않게 받는다."""
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="cp949" if os.name == "nt" else "utf-8",
                          errors="replace")


# 작업 스케줄러 XML. 명령줄(schtasks /create) 로는 재시작·무제한 실행시간을
# 지정할 수 없어 XML 로 만든다.
TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>정책 아이디어 평가 시스템 - FastAPI 서버</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT30S</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{exe}</Command>
      <Arguments>"{runner}"</Arguments>
      <WorkingDirectory>{root}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def install():
    exe = PYW if PYW.exists() else PY
    if not exe.exists():
        say(f"  [!] {exe} 가 없습니다. 서버_1_설치.bat 을 먼저 실행하세요.")
        return 1
    if not RUNNER.exists():
        say(f"  [!] {RUNNER} 가 없습니다. 압축을 다시 푸세요.")
        return 1

    xml = TASK_XML.format(exe=exe, runner=RUNNER, root=ROOT)
    # 작업 스케줄러는 UTF-16 XML 을 요구한다.
    XML.write_text(xml, encoding="utf-16")

    run(["schtasks", "/Delete", "/TN", TASK, "/F"])       # 있으면 지우고 새로
    r = run(["schtasks", "/Create", "/TN", TASK, "/XML", str(XML), "/F"])
    try:
        XML.unlink()
    except Exception:
        pass

    if r.returncode != 0:
        say("  [!] 등록에 실패했습니다.")
        say("      " + (r.stderr or r.stdout).strip()[:300])
        say("      이 창을 관리자 권한으로 다시 여세요 —")
        say("      서버_2_서비스등록.bat 을 오른쪽 클릭 → [관리자 권한으로 실행]")
        return 1

    say(f"  등록했습니다 — 작업 이름 {TASK}")
    say("    · 부팅 30초 뒤 자동으로 켜집니다")
    say("    · 죽으면 1분 뒤 다시 켭니다 (최대 999번)")
    say("    · 로그온하지 않아도 돕니다 (SYSTEM 계정)")
    say("")
    say("  지금 바로 켜려면:  서버_4_상태확인.bat 에서 [시작]")
    say("  또는 명령창에서:   schtasks /Run /TN " + TASK)
    return 0


def status():
    r = run(["schtasks", "/Query", "/TN", TASK, "/V", "/FO", "LIST"])
    if r.returncode != 0:
        say(f"  등록되지 않았습니다 (작업 {TASK} 없음).")
        say("  서버_2_서비스등록.bat 을 관리자 권한으로 실행하세요.")
        return 1
    keep = ("상태", "Status", "마지막 실행", "Last Run", "마지막 결과",
            "Last Result", "다음 실행", "Next Run", "실행할 작업", "Task To Run")
    for line in r.stdout.splitlines():
        if any(k in line for k in keep):
            say("  " + line.strip())

    # 실제로 응답하는지까지 본다. 작업이 '실행 중'이어도 앱이 죽어 있을 수 있다.
    import urllib.request
    port = os.environ.get("PORT", "8000")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/config",
                                    timeout=5) as resp:
            say(f"\n  http://127.0.0.1:{port}/api/config → {resp.status} 정상 응답")
    except Exception as e:
        say(f"\n  [!] http://127.0.0.1:{port} 가 응답하지 않습니다: {e}")
        say("      작업은 등록돼 있어도 앱이 죽었을 수 있습니다.")
        say("      서버_3_직접실행.bat 으로 켜 보면 오류가 화면에 나옵니다.")
    return 0


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "--status"

    if os.name != "nt":
        say("  [i] 윈도우에서만 쓰는 도구입니다.")
        say("      리눅스라면 deploy/policy-eval.service (systemd) 를 쓰세요.")
        return 1

    if cmd in ("--install", "--remove") and not is_admin():
        say("  [!] 관리자 권한이 필요합니다.")
        say("      서버_2_서비스등록.bat 을 오른쪽 클릭 →")
        say("      [관리자 권한으로 실행] 을 고르세요.")
        hold()
        return 1

    if cmd == "--install":
        rc = install()
    elif cmd == "--remove":
        r = run(["schtasks", "/Delete", "/TN", TASK, "/F"])
        say("  등록을 해제했습니다." if r.returncode == 0 else "  등록돼 있지 않았습니다.")
        rc = 0
    elif cmd == "--start":
        r = run(["schtasks", "/Run", "/TN", TASK])
        say("  시작 요청을 보냈습니다." if r.returncode == 0
            else "  [!] " + (r.stderr or r.stdout).strip()[:200])
        rc = r.returncode
    elif cmd == "--stop":
        r = run(["schtasks", "/End", "/TN", TASK])
        say("  껐습니다." if r.returncode == 0
            else "  [!] " + (r.stderr or r.stdout).strip()[:200])
        rc = r.returncode
    else:
        rc = status()

    hold()
    return rc


if __name__ == "__main__":
    sys.exit(main())
