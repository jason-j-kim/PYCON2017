"""소크라테스 문답 엔진 — CLI(prototype/)와 웹(webapp/)이 공유하는 핵심 로직.

백엔드로 Claude Code CLI(`claude -p`)를 헤드리스로 호출한다.
Claude Pro/Max 구독 로그인만으로 동작하며 API 키가 필요 없다.

질문자와 채점자는 별도 호출로 분리한다:
질문자는 점수를 모르고, 채점자는 대화에 참여하지 않고 로그만 본다.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

# Windows에서 npm으로 설치한 Claude Code는 claude.cmd라서 전체 경로로 찾아야 한다
CLAUDE_BIN = shutil.which("claude") or "claude"

PROMPT_DIR = Path(__file__).parent / "prompts"
# 시스템 프롬프트는 파일 경로로 전달한다. 여러 줄 텍스트를 명령줄 인자로 넘기면
# Windows에서 claude.cmd가 cmd.exe를 거치며 줄바꿈에서 인자가 깨진다.
QUESTIONER_PROMPT_FILE = PROMPT_DIR / "questioner_system.md"
GRADER_PROMPT_FILE = PROMPT_DIR / "grader_system.md"

DEFAULT_WEIGHTS = {"originality": 0.35, "practicality": 0.35, "acceptance": 0.30}
CRITERIA = ("originality", "practicality", "acceptance")
CRITERIA_KO = {"originality": "독창성", "practicality": "실용성", "acceptance": "수용태도"}
SUBSCORES = ("specificity", "consistency", "self_awareness")

# 단계 정의: (내부 이름, 표시 이름, 질문 턴 수, 질문자에게 주입할 단계 지시)
STAGES = [
    (
        "clarify", "명료화", 2,
        "지금은 [명료화] 단계다. 아이디어를 한 문장 정의로 압축하도록 유도하라. "
        "대상, 해결하는 문제, 방법이 그 한 문장에 드러나야 한다. "
        "제안자의 표현이 이미 충분히 명확하면 합의된 정의를 짧게 되짚어 확인만 하라.",
    ),
    (
        "originality", "독창성", 3,
        "지금은 [독창성] 라운드다. 기존 해법과 무엇이 다른지, 비슷한 시도가 이미 "
        "존재하지 않는지, 차별점이 모방하기 어려운 것인지를 검증하는 질문을 하라.",
    ),
    (
        "practicality", "실용성", 3,
        "지금은 [실용성] 라운드다. 구현에 무엇이 필요한지, 가장 큰 장애물이 "
        "무엇인지, 최소 버전(MVP)은 무엇일지, 비용 대비 효과를 검증하는 질문을 하라.",
    ),
    (
        "acceptance", "수용태도", 3,
        "지금은 [수용태도] 라운드다. 누가 실제로 쓸 것인지, 그들이 지금 방식을 "
        "버리고 갈아탈 이유가 있는지, 반대할 이해관계자는 누구인지 검증하는 질문을 하라.",
    ),
    (
        "self_assess", "자기 평가", 1,
        "지금은 [자기 평가] 단계다. 지금까지의 대화를 바탕으로 제안자가 스스로 "
        "아이디어의 가장 큰 약점 하나를 꼽고, 그것을 어떻게 보완할지 말하게 하라. "
        "이번이 마지막 질문이다.",
    ),
]

# 채점자가 반환해야 할 JSON 형태 (프롬프트로 강제하고 파싱 시 검증한다)
GRADE_FORMAT = """\
{
  "originality":  {"specificity": 0, "consistency": 0, "self_awareness": 0, "evidence": ["턴 N: 근거"]},
  "practicality": {"specificity": 0, "consistency": 0, "self_awareness": 0, "evidence": ["턴 N: 근거"]},
  "acceptance":   {"specificity": 0, "consistency": 0, "self_awareness": 0, "evidence": ["턴 N: 근거"]},
  "strengths": ["..."],
  "suggestions": ["..."],
  "encouragement": "..."
}"""


def call_claude(prompt, system_prompt_file):
    """Claude Code CLI를 헤드리스로 호출한다. 도구를 모두 끄고 순수 대화만 시킨다.

    system_prompt_file: 시스템 프롬프트가 담긴 파일 경로 (인자 깨짐 방지).
    사용자 프롬프트는 stdin으로 전달하므로 줄바꿈·한국어에 안전하다.
    """
    cmd = [
        CLAUDE_BIN, "-p",
        "--system-prompt-file", str(system_prompt_file),
        "--tools", "",
        "--no-session-persistence",
        "--output-format", "text",
    ]
    try:
        # encoding을 명시하지 않으면 한국어 Windows에서 cp949로 읽다가 깨진다
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "claude CLI를 찾을 수 없습니다. Claude Code를 설치하고 "
            "(npm install -g @anthropic-ai/claude-code) 새 터미널에서 서버를 다시 시작하세요."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude 응답이 300초를 초과했습니다. 다시 시도하세요.")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "원인 미상").strip()[:500]
        hint = "(로그인이 안 된 경우 터미널에서 `claude`를 실행해 /login 하세요)"
        if "401" in detail or "authentication" in detail.lower():
            hint = (
                "(인증 실패입니다. ① 터미널에서 `echo %ANTHROPIC_API_KEY%` 를 실행해 "
                "값이 나오면 오래된 API 키가 로그인 계정을 가리는 것이니 "
                "`set ANTHROPIC_API_KEY=` 로 지우고 서버를 재시작하세요. "
                "② 값이 없으면 `claude` 실행 후 /login 으로 다시 로그인하세요)"
            )
        raise RuntimeError(f"claude CLI 오류: {detail}\n{hint}")
    return result.stdout.strip()


def ask_questioner(transcript_log, stage_directive):
    """대화 로그 전체 + 현재 단계 지시를 넘겨 다음 질문 하나를 받는다.

    transcript_log: "[턴 N] 역할: 내용" 형태의 문자열 리스트.
    """
    prompt = (
        "<대화 기록>\n" + "\n\n".join(transcript_log) + "\n</대화 기록>\n\n"
        f"<현재 단계 지시>\n{stage_directive}\n</현재 단계 지시>\n\n"
        "위 대화에 이어서, 시스템 프롬프트의 규칙에 따라 질문자의 다음 발화를 "
        "출력하라. 발화 내용만 출력하고 다른 설명은 붙이지 마라."
    )
    return call_claude(prompt, QUESTIONER_PROMPT_FILE)


def parse_grade_json(text):
    """응답에서 JSON을 추출·검증한다. 코드 펜스나 앞뒤 설명이 붙어도 견딘다."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("응답에서 JSON을 찾지 못함")
    result = json.loads(match.group(0))
    for c in CRITERIA:
        for s in SUBSCORES:
            if not isinstance(result[c][s], int):
                raise ValueError(f"{c}.{s}가 정수가 아님")
        result[c].setdefault("evidence", [])
    for key in ("strengths", "suggestions", "encouragement"):
        if key not in result:
            raise ValueError(f"{key} 누락")
    return result


def grade(transcript):
    """채점자 호출. 대화 로그 전체를 넘기고 JSON으로 받는다. 파싱 실패 시 1회 재시도."""
    prompt = (
        "다음 아이디어 평가 세션의 대화 로그를 시스템 프롬프트의 루브릭에 따라 "
        "채점하라.\n\n<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
        "결과는 아래 형태의 JSON **하나만** 출력하라. 코드 펜스나 설명 없이 "
        "JSON으로 시작해서 JSON으로 끝나야 한다.\n" + GRADE_FORMAT
    )
    last_error = None
    for _ in range(2):
        text = call_claude(prompt, GRADER_PROMPT_FILE)
        try:
            return parse_grade_json(text)
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            last_error = e
    raise RuntimeError(f"채점 결과 파싱 실패: {last_error}")


def criterion_total(c):
    return sum(c[s] for s in SUBSCORES)


def weighted_total(result, weights):
    """weights: {"originality": w1, "practicality": w2, "acceptance": w3}"""
    return sum(criterion_total(result[c]) * weights[c] for c in CRITERIA)
