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
GRADER_HOLISTIC_PROMPT_FILE = PROMPT_DIR / "grader_holistic_system.md"
GRADER_CHECKLIST_PROMPT_FILE = PROMPT_DIR / "grader_checklist_system.md"

DEFAULT_WEIGHTS = {"originality": 0.35, "practicality": 0.35, "acceptance": 0.30}
CRITERIA = ("originality", "practicality", "acceptance")
CRITERIA_KO = {"originality": "독창성", "practicality": "실용성", "acceptance": "수용태도"}
# 체크리스트 항목 — "이 사건이 대화에 있었는가"로 판정 가능한 10개 이진 항목.
# 충족 개수가 그대로 기준별 체크리스트 점수(0~10)가 된다.
CHECKLIST_ITEMS = [
    ("S1", "수치·고유명사 제시", "이 기준과 관련해 구체적 수치, 이름, 범위를 제시했다"),
    ("S2", "사례·경험 인용", "실제 사례나 직접 경험을 근거로 들었다"),
    ("S3", "근거 출처 구분", "직접 확인한 것과 추측을 구분해서 말했다"),
    ("S4", "검증 가능한 진술", "제3자가 사실 여부를 확인할 수 있는 형태로 주장했다"),
    ("C1", "무모순", "이 기준과 관련한 답변이 이전 답변과 모순되지 않는다"),
    ("C2", "반례 대응", "반례·전제 검증 질문에 논리적으로 대응했다"),
    ("C3", "정면 응답", "질문이 묻는 바에 회피 없이 직접 답했다"),
    ("A1", "약점 인정", "이 기준과 관련한 약점이나 한계를 스스로 인정했다"),
    ("A2", "개선안 제시", "인정한 약점에 대한 보완·개선 방향을 제시했다"),
    ("A3", "전제 명시", "아이디어가 성립하기 위한 전제·조건을 스스로 밝혔다"),
]
CHECKLIST_LABELS = {i: label for i, label, _ in CHECKLIST_ITEMS}


def _checklist_format():
    item_obj = ", ".join(f'"{i}": {{"met": false, "evidence": ""}}' for i, _, _ in CHECKLIST_ITEMS)
    body = ",\n".join(f'  "{c}": {{{item_obj}}}' for c in CRITERIA)
    return "{\n" + body + "\n}"


HOLISTIC_FORMAT = """\
{
  "originality":  {"score": 0, "rationale": "턴 번호를 인용한 이유"},
  "practicality": {"score": 0, "rationale": "..."},
  "acceptance":   {"score": 0, "rationale": "..."},
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


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("응답에서 JSON을 찾지 못함")
    return json.loads(match.group(0))


def _parse_checklist(text):
    """규정 심사위원 응답 검증. met=true인데 근거 인용이 없으면 불충족 처리."""
    result = _extract_json(text)
    parsed = {}
    for c in CRITERIA:
        parsed[c] = {}
        for item_id, _, _ in CHECKLIST_ITEMS:
            entry = result[c][item_id]
            met = bool(entry["met"])
            evidence = str(entry.get("evidence", "")).strip()
            if met and not evidence:
                met = False
                evidence = "(근거 인용 누락으로 불충족 처리)"
            parsed[c][item_id] = {"met": met, "evidence": evidence}
    return parsed


def _parse_holistic(text):
    """종합 심사위원 응답 검증. 점수는 0~10 정수로 강제."""
    result = _extract_json(text)
    for c in CRITERIA:
        score = result[c]["score"]
        if not isinstance(score, int):
            raise ValueError(f"{c}.score가 정수가 아님")
        result[c]["score"] = max(0, min(10, score))
        result[c].setdefault("rationale", "")
    for key in ("strengths", "suggestions", "encouragement"):
        if key not in result:
            raise ValueError(f"{key} 누락")
    return result


def _call_and_parse(prompt, system_file, parser):
    last_error = None
    for _ in range(2):
        text = call_claude(prompt, system_file)
        try:
            return parser(text)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            last_error = e
    raise RuntimeError(f"채점 결과 파싱 실패: {last_error}")


def _grade_checklist(transcript):
    items_desc = "\n".join(f"- {i} ({label}): {desc}" for i, label, desc in CHECKLIST_ITEMS)
    prompt = (
        "다음 아이디어 평가 세션의 대화 로그를 체크리스트로 판정하라.\n\n"
        "<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
        "<체크리스트 항목>\n" + items_desc + "\n</체크리스트 항목>\n\n"
        "세 기준 originality(독창성), practicality(실용성), acceptance(수용태도) "
        "각각에 대해 10개 항목 전부를 판정하라. met=true인 항목의 evidence에는 "
        "반드시 '턴 N: ...' 형태의 인용을 적어라.\n"
        "결과는 아래 형태의 JSON **하나만** 출력하라. 코드 펜스나 설명 없이 "
        "JSON으로 시작해서 JSON으로 끝나야 한다.\n" + _checklist_format()
    )
    return _call_and_parse(prompt, GRADER_CHECKLIST_PROMPT_FILE, _parse_checklist)


def _grade_holistic(transcript):
    prompt = (
        "다음 아이디어 평가 세션의 대화 로그를 시스템 프롬프트의 점수 밴드에 따라 "
        "종합 채점하라.\n\n<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
        "결과는 아래 형태의 JSON **하나만** 출력하라. 코드 펜스나 설명 없이 "
        "JSON으로 시작해서 JSON으로 끝나야 한다.\n" + HOLISTIC_FORMAT
    )
    return _call_and_parse(prompt, GRADER_HOLISTIC_PROMPT_FILE, _parse_holistic)


def grade(transcript):
    """이원 채점: 규정 심사위원(체크리스트)과 종합 심사위원(전체 인상)을 각각
    호출하고, 기준별 최종 점수는 두 점수의 평균으로 한다."""
    checklist = _grade_checklist(transcript)
    holistic = _grade_holistic(transcript)
    criteria = {}
    for c in CRITERIA:
        cl_total = sum(1 for item in checklist[c].values() if item["met"])
        h_score = holistic[c]["score"]
        criteria[c] = {
            "checklist": {"items": checklist[c], "total": cl_total},
            "holistic": {"score": h_score, "rationale": holistic[c]["rationale"]},
            "final": round((cl_total + h_score) / 2, 1),
        }
    return {
        "version": 2,
        "criteria": criteria,
        "strengths": holistic["strengths"],
        "suggestions": holistic["suggestions"],
        "encouragement": holistic["encouragement"],
    }


def weighted_total(result, weights):
    """weights: {"originality": w1, "practicality": w2, "acceptance": w3}"""
    return sum(result["criteria"][c]["final"] * weights[c] for c in CRITERIA)
