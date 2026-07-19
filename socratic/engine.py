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
PROPOSER_PROMPT_FILE = PROMPT_DIR / "proposer_system.md"      # 시뮬레이션용
SYNTHESIZER_PROMPT_FILE = PROMPT_DIR / "synthesizer_system.md"  # 재판장

DEFAULT_WEIGHTS = {"originality": 0.35, "practicality": 0.35, "acceptance": 0.30}
CRITERIA = ("originality", "practicality", "acceptance")
CRITERIA_KO = {"originality": "독창성", "practicality": "실용성", "acceptance": "수용태도"}
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

# 기준별 체크리스트 — "이 사건이 대화에 있었는가"로 판정 가능한 이진 항목 10개씩.
# 충족 개수가 그대로 기준별 체크리스트 점수(0~10)가 된다.
# 항목별 이론적 근거는 docs/checklist-rationale.md 참고:
# 독창성 = 창의성 표준 정의(Runco & Jaeger) + 아이디어 평가 구인(Dean et al. 2006)
# 실용성 = TELOS 타당성 프레임워크 + Real-Win-Worth(Day, HBR 2007) + 린 스타트업 MVP
# 수용태도 = 혁신 확산 이론(Rogers) 5속성 + 기술수용모형 TAM(Davis)
CHECKLIST_ITEMS = {
    "originality": [
        ("O1", "기존 해법 식별", "기존 해법이나 유사 시도를 구체적으로 언급했다"),
        ("O2", "차별점 명시", "기존 해법과의 차이를 구체적으로 진술했다"),
        ("O3", "차별점의 검증 가능성", "차별점을 제3자가 확인 가능한 형태(기능·구조·수치)로 제시했다"),
        ("O4", "공백의 설명", "왜 아직 없는지 또는 왜 지금 가능해졌는지를 설명했다"),
        ("O5", "모방 장벽", "차별점이 쉽게 모방되지 않는 이유를 제시했다"),
        ("O6", "관점 전환", "문제를 다르게 정의하거나 기존 프레임을 벗어난 요소가 있다"),
        ("O7", "새로움-가치 연결", "새로움이 사용자 가치로 이어짐을 설명했다"),
        ("O8", "유사 사례 반례 대응", "'이미 있지 않나' 류의 반례 질문에 정면 대응했다"),
        ("O9", "독창성 한계 인정", "독창성의 한계(부분적 새로움)를 스스로 인정했다"),
        ("O10", "무모순", "독창성 주장이 대화 전체에서 모순되지 않는다"),
    ],
    "practicality": [
        ("P1", "자원 구체화", "필요 인력·기술·예산을 수치나 구체 항목으로 제시했다"),
        ("P2", "MVP 정의", "최소 실행 버전의 범위를 구체적으로 한정했다"),
        ("P3", "핵심 장애물 식별", "실행의 가장 큰 장애물을 스스로 특정했다"),
        ("P4", "장애물 대응책", "그 장애물에 대한 현실적 대응 방안을 제시했다"),
        ("P5", "구현 경로", "핵심 기능의 구현 방법(데이터·기술·절차)을 설명했다"),
        ("P6", "비용 대비 효과", "비용과 기대 효과를 비교하는 논리를 제시했다"),
        ("P7", "운영 주체 특정", "누가 실행·운영하는지를 특정했다"),
        ("P8", "단계적 경로", "시작에서 확장으로 가는 단계적 실행 순서를 제시했다"),
        ("P9", "실행 리스크 인정", "실행상 리스크나 불확실성을 스스로 인정했다"),
        ("P10", "무모순", "실용성 주장이 대화 전체에서 모순되지 않는다"),
    ],
    "acceptance": [
        ("A1", "수용 주체 특정", "사용자와 이해관계자를 구체적으로 특정했다"),
        ("A2", "상대적 이점", "현재 방식 대비 사용자가 얻는 이점을 구체화했다"),
        ("A3", "전환 비용", "갈아타는 데 드는 비용·노력·학습을 다뤘다"),
        ("A4", "적합성", "사용자의 기존 습관·가치와의 정합을 설명했다"),
        ("A5", "시험 가능성", "부담 없이 먼저 써볼 수 있는 경로를 제시했다"),
        ("A6", "반대 세력 식별", "반대하거나 손해 보는 이해관계자를 식별했다"),
        ("A7", "저항 대응", "반대·저항에 대한 대응 논리를 제시했다"),
        ("A8", "확산 경로", "초기 사용자 확보와 확산 방법을 구체화했다"),
        ("A9", "수용 리스크 인정", "수용되지 않을 가능성이나 조건을 스스로 인정했다"),
        ("A10", "무모순", "수용태도 주장이 대화 전체에서 모순되지 않는다"),
    ],
}
CHECKLIST_LABELS = {
    c: {i: label for i, label, _ in items} for c, items in CHECKLIST_ITEMS.items()
}


def _checklist_format():
    lines = []
    for c in CRITERIA:
        item_obj = ", ".join(
            f'"{i}": {{"met": false, "evidence": ""}}' for i, _, _ in CHECKLIST_ITEMS[c]
        )
        lines.append(f'  "{c}": {{{item_obj}}}')
    return "{\n" + ",\n".join(lines) + "\n}"


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


def ask_questioner(transcript_log, stage_directive, system_file=None):
    """대화 로그 전체 + 현재 단계 지시를 넘겨 다음 질문 하나를 받는다.

    transcript_log: "[턴 N] 역할: 내용" 형태의 문자열 리스트.
    system_file: 질문자 지침 파일 경로 (기본은 현행 지침; A/B 실험용 교체 가능).
    """
    prompt = (
        "<대화 기록>\n" + "\n\n".join(transcript_log) + "\n</대화 기록>\n\n"
        f"<현재 단계 지시>\n{stage_directive}\n</현재 단계 지시>\n\n"
        "위 대화에 이어서, 시스템 프롬프트의 규칙에 따라 질문자의 다음 발화를 "
        "출력하라. 발화 내용만 출력하고 다른 설명은 붙이지 마라."
    )
    return call_claude(prompt, system_file or QUESTIONER_PROMPT_FILE)


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
        for item_id, _, _ in CHECKLIST_ITEMS[c]:
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
    items_desc = "\n\n".join(
        f"[{c} ({CRITERIA_KO[c]}) 전용 항목]\n"
        + "\n".join(f"- {i} ({label}): {desc}" for i, label, desc in CHECKLIST_ITEMS[c])
        for c in CRITERIA
    )
    prompt = (
        "다음 아이디어 평가 세션의 대화 로그를 체크리스트로 판정하라.\n\n"
        "<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
        "<체크리스트 항목 — 기준마다 전용 항목 10개>\n" + items_desc
        + "\n</체크리스트 항목>\n\n"
        "각 기준의 전용 항목 10개 전부를 판정하라. met=true인 항목의 evidence에는 "
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


def _parse_synthesis(text):
    result = _extract_json(text)
    for c in CRITERIA:
        if c not in result["criterion_notes"]:
            raise ValueError(f"criterion_notes.{c} 누락")
    if "verdict" not in result:
        raise ValueError("verdict 누락")
    return result


def synthesize(transcript, grade_result):
    """재판장 호출: 두 심사위원 결과를 검토하고 최종 판정문을 쓴다."""
    grader_summary = json.dumps(
        {
            c: {
                "체크리스트": grade_result["criteria"][c]["checklist"],
                "종합판단": grade_result["criteria"][c]["holistic"],
                "최종(평균)": grade_result["criteria"][c]["final"],
            }
            for c in CRITERIA
        },
        ensure_ascii=False, indent=1,
    )
    prompt = (
        "<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
        "<두 심사위원의 결과>\n" + grader_summary + "\n</두 심사위원의 결과>\n\n"
        "시스템 프롬프트의 임무에 따라 기준별 검토와 최종 판정문을 작성하라.\n"
        "결과는 아래 형태의 JSON **하나만** 출력하라. 코드 펜스나 설명 없이 "
        "JSON으로 시작해서 JSON으로 끝나야 한다.\n"
        '{\n  "criterion_notes": {"originality": "...", "practicality": "...", '
        '"acceptance": "..."},\n  "verdict": "..."\n}'
    )
    return _call_and_parse(prompt, SYNTHESIZER_PROMPT_FILE, _parse_synthesis)
