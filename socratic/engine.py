"""소크라테스 문답 엔진 — CLI(prototype/)와 웹(webapp/)이 공유하는 핵심 로직.

백엔드로 Claude Code CLI(`claude -p`)를 헤드리스로 호출한다.
Claude Pro/Max 구독 로그인만으로 동작하며 API 키가 필요 없다.

질문자와 채점자는 별도 호출로 분리한다:
질문자는 점수를 모르고, 채점자는 대화에 참여하지 않고 로그만 본다.
"""

import json
import os
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
# 선례 조사 축(축 B) — 정책 프로필 전용, 문답 뒤 별도 단계
SPEC_EXTRACTOR_PROMPT_FILE = PROMPT_DIR / "spec_extractor_system.md"
PRECEDENT_JUDGE_PROMPT_FILE = PROMPT_DIR / "precedent_judge_system.md"
ORIGINALITY_GRADER_PROMPT_FILE = PROMPT_DIR / "originality_grader_system.md"
# 정책 프로필의 독창성 라운드에만 덧붙이는 선례 지목 유도문(축 B 앵커).
# 원본 STAGES는 손대지 않고, app 계층에서 정책일 때만 이 줄을 지시문에 붙인다.
PRECEDENT_ANCHOR_LINE = (
    "이 라운드의 1문은 반드시 다음 취지로 묻는다: '이 정책과 가장 가까운 기존 "
    "사업·제도를 하나 지목해 주십시오. 사업명과 대략의 시기까지 밝혀 주시면 됩니다. "
    "없다고 판단하신다면 그 근거를 말씀해 주십시오.'"
)

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

# ── 수정판(정책 평가) 프로필 ──────────────────────────────────────────────
# 원본은 손대지 않는다. 정책 프로필에서만 수용태도 A9를 "수용 리스크 인정"에서
# "판단 갱신 조건 명시(반증 기준)"로 강화해 실제 채점에 반영한다. 항목 ID는
# 그대로(A1~A10)이므로 포맷·파싱 로직은 두 프로필이 공유한다.
POLICY_ACCEPTANCE = [
    ("A1", "수용 주체 특정", "사용자와 이해관계자를 구체적으로 특정했다"),
    ("A2", "상대적 이점", "현재 방식 대비 사용자가 얻는 이점을 구체화했다"),
    ("A3", "전환 비용", "갈아타는 데 드는 비용·노력·학습을 다뤘다"),
    ("A4", "적합성", "사용자의 기존 습관·가치와의 정합을 설명했다"),
    ("A5", "시험 가능성", "부담 없이 먼저 써볼 수 있는 경로를 제시했다"),
    ("A6", "반대 세력 식별", "반대하거나 손해 보는 이해관계자를 식별했다"),
    ("A7", "저항 대응", "반대·저항에 대한 대응 논리를 제시했다"),
    ("A8", "확산 경로", "초기 사용자 확보와 확산 방법을 구체화했다"),
    ("A9", "판단 갱신 조건 명시",
     "어떤 지표·수치·기간이 관측되면 이 정책을 수정·중단하겠는지 구체적 반증 "
     "기준을 제시했다 (기준을 말한 턴을 인용해야 충족)"),
    ("A10", "무모순", "수용태도 주장이 대화 전체에서 모순되지 않는다"),
]

PROFILES = ("원본", "정책")


def _profile_items(profile):
    """프로필별 체크리스트 항목 dict. 항목 ID는 동일, 정책은 A9만 강화된다."""
    if profile == "정책":
        return {**CHECKLIST_ITEMS, "acceptance": POLICY_ACCEPTANCE}
    return CHECKLIST_ITEMS


def checklist_labels(profile="원본"):
    """프로필별 항목 라벨 (결과 화면 표시용)."""
    items = _profile_items(profile)
    return {c: {i: label for i, label, _ in its} for c, its in items.items()}


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


def _grade_checklist(transcript, items=None):
    if items is None:
        items = CHECKLIST_ITEMS
    items_desc = "\n\n".join(
        f"[{c} ({CRITERIA_KO[c]}) 전용 항목]\n"
        + "\n".join(f"- {i} ({label}): {desc}" for i, label, desc in items[c])
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


def grade(transcript, profile="원본"):
    """이원 채점: 규정 심사위원(체크리스트)과 종합 심사위원(전체 인상)을 각각
    호출하고, 기준별 최종 점수는 두 점수의 평균으로 한다.

    profile="원본"(기본)이면 현행 그대로. profile="정책"이면 수용태도 A9만
    반증·판단갱신으로 강화된 체크리스트를 쓴다(추가 호출 없음)."""
    checklist = _grade_checklist(transcript, _profile_items(profile))
    holistic = _grade_holistic(transcript)
    criteria = {}
    for c in CRITERIA:
        cl_total = sum(1 for item in checklist[c].values() if item["met"])
        h_score = holistic[c]["score"]
        criteria[c] = {
            "checklist": {"items": checklist[c], "total": cl_total},
            "holistic": {"score": h_score, "rationale": holistic[c]["rationale"]},
            "final": _combine(cl_total, h_score),
            "divergent": abs(cl_total - h_score) >= DIVERGENCE_LIMIT,
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


# 두 채점이 이만큼 벌어지면 평균을 신뢰하지 않는다(보수적으로 낮은 쪽을 쓴다).
# 근거: 체크리스트는 '언급 여부'만 세므로 항목을 훑어 열거하면 부풀려진다.
# 실제로 LLM 대필 세션에서 체크 9 · 종합 6(괴리 3)이 관측됐고, 평균 7.5가
# 그 경고를 삼켰다. 괴리가 크다는 것은 '무엇을 재는지 두 채점자가 불일치한다'는
# 뜻이므로, 높은 쪽을 채택할 근거가 없다.
DIVERGENCE_LIMIT = int(os.environ.get("DIVERGENCE_LIMIT", "3"))


def _combine(cl_total, h_score):
    """기준별 최종 점수. 두 채점의 괴리가 임계 이상이면 낮은 쪽을 채택한다."""
    if abs(cl_total - h_score) >= DIVERGENCE_LIMIT:
        return float(min(cl_total, h_score))
    return round((cl_total + h_score) / 2, 1)


# ── 수정판 표현 계층 ──────────────────────────────────────────────────────
# 추가 Claude 호출 없이, 이미 나온 이원 채점 결과만으로 계산한다. 새 점수를
# 만들지 않고 기존 숫자·근거 문장을 서술로 재조립한다.

# 근거신뢰도(E0~E4) 산출에 쓰는 '검증 가능·수치·구체' 항목 5개.
EVIDENCE_ITEMS = (
    ("originality", "O3"),   # 차별점을 제3자 확인 가능한 형태(기능·구조·수치)로
    ("practicality", "P1"),  # 필요 자원을 수치·구체 항목으로
    ("practicality", "P5"),  # 구현을 데이터·기술·절차로
    ("practicality", "P6"),  # 비용 대비 효과 비교 논리
    ("acceptance", "A2"),    # 현재 대비 구체적 이점
)

_EVIDENCE_LABELS = {
    0: "주장 중심", 1: "일화·부분 근거", 2: "자료 기반",
    3: "실증 기반", 4: "행동·데이터 기반",
}


def evidence_level(result):
    """근거신뢰도: 검증 가능·수치·구체 항목의 충족도를 E0~E4로 환산한다.
    자기신고가 아니라 규정 심사위원의 대화 판정에서 산출한다."""
    met = 0
    for c, item_id in EVIDENCE_ITEMS:
        entry = result["criteria"][c]["checklist"]["items"].get(item_id)
        if entry and entry["met"]:
            met += 1
    total = len(EVIDENCE_ITEMS)
    level = round(met / total * 4)
    return {"level": level, "label": _EVIDENCE_LABELS[level],
            "met": met, "total": total}


def score_band(result, weights):
    """점수 범위(불확실성 밴드): 두 심사위원(체크리스트↔종합)의 괴리를 폭으로.
    최종 점수는 두 점수의 중점이므로, 괴리가 클수록 밴드가 넓어진다."""
    total = weighted_total(result, weights)
    radius = 0.0
    for c in CRITERIA:
        cl = result["criteria"][c]["checklist"]["total"]
        h = result["criteria"][c]["holistic"]["score"]
        radius += weights[c] * abs(cl - h) / 2
    return {
        "low": round(max(0.0, total - radius), 1),
        "high": round(min(10.0, total + radius), 1),
        "radius": round(radius, 1),
    }


def five_lines(result, weights):
    """5문장 프레임: 현재가치·잠재가치·핵심위험·근거신뢰도·다음검증행동.
    새 숫자·새 호출 없이 이원 채점 결과를 서술로 묶는다."""
    total = round(weighted_total(result, weights), 1)
    crit = result["criteria"]
    ranked = sorted(CRITERIA, key=lambda c: crit[c]["final"])
    weak, strong = ranked[0], ranked[-1]
    ev = evidence_level(result)
    band = score_band(result, weights)
    sugg = [s for s in result.get("suggestions", []) if s]
    strong_r = crit[strong]["holistic"]["rationale"]
    unmet = sum(1 for c in CRITERIA
                for it in crit[c]["checklist"]["items"].values() if not it["met"])
    orig_final = crit["originality"]["final"]
    return {
        "현재가치": (
            f"현재 근거로 방어 가능한 종합 수준은 {total}/10입니다"
            f"(범위 {band['low']}–{band['high']}). 가장 탄탄히 입증된 축은 "
            f"'{CRITERIA_KO[strong]}'({crit[strong]['final']}/10)이며, {strong_r}"
        ),
        "잠재가치": (
            f"독창성 {orig_final}/10을 축으로, 아직 입증되지 않은 항목 "
            f"{unmet}개가 근거로 채워지면 상방이 열립니다."
        ),
        "핵심위험": (
            f"가장 취약한 축은 '{CRITERIA_KO[weak]}'({crit[weak]['final']}/10)입니다."
            + (f" {sugg[0]}" if sugg else "")
        ),
        "근거신뢰도": (
            f"제시된 근거는 {ev['label']}(E{ev['level']}) 수준입니다"
            f"({ev['met']}/{ev['total']} 근거 항목이 검증 가능한 형태로 충족)."
        ),
        "다음검증행동": (
            "다음으로 확인할 것 — "
            + ("; ".join(sugg[:3]) if sugg else "핵심 가정을 검증할 최소 실험을 정하세요.")
        ),
    }


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


# ── 선례 조사 축(축 B) ────────────────────────────────────────────────────
# 문답이 끝난 뒤 별도로 도는 단계다. 대화 로그는 Stage 3에서 한 번만 읽고,
# 이후 단계는 명세만 평가한다(사람이 아니라 산출물을 평가). 기존 채점 경로
# (grade 등)와 완전히 분리되어 있으며 추가 Claude 호출은 3회(명세·판정·독창성).
_BANDS = ("선례 명확", "계열 내 변형", "계열 밖 시도", "판정 보류")


def extract_spec(transcript):
    """Stage 3: 로그를 명세·유형·질의어로 구조화한다(채점 아님)."""
    prompt = ("<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
              "시스템 프롬프트의 형식에 따라 JSON 하나만 출력하라.")

    def parse(text):
        r = _extract_json(text)
        for k in ("spec", "policy_type", "claimed_precedents", "queries"):
            if k not in r:
                raise ValueError(f"{k} 누락")
        r["queries"].setdefault("fiscal", [])
        r["queries"].setdefault("prism", [])
        r["queries"].setdefault("bill", [])
        return r

    return _call_and_parse(prompt, SPEC_EXTRACTOR_PROMPT_FILE, parse)


def judge_by_knowledge(spec_result):
    """Stage 4: 모델 지식만으로 선례 유무를 판정한다(검색 0)."""
    payload = json.dumps({
        "spec": spec_result["spec"],
        "policy_type": spec_result["policy_type"],
        "claimed_precedents": spec_result.get("claimed_precedents", []),
    }, ensure_ascii=False, indent=1)
    prompt = ("<정책 명세>\n" + payload + "\n</정책 명세>\n\n"
              "시스템 프롬프트의 형식에 따라 JSON 하나만 출력하라.")

    def parse(text):
        r = _extract_json(text)
        if r.get("verdict") not in ("has_precedent", "no_precedent", "uncertain"):
            raise ValueError("verdict 값 오류")
        r.setdefault("recalled", [])
        r.setdefault("reasoning", "")
        r.setdefault("retraction_condition", "")
        return r

    return _call_and_parse(prompt, PRECEDENT_JUDGE_PROMPT_FILE, parse)


def grade_originality(spec_result, judge, hits=None):
    """Stage 6: 4구간 + 확신도로 실질 독창성을 판정한다(로그 미투입)."""
    payload = {
        "spec": spec_result["spec"],
        "policy_type": spec_result["policy_type"],
        "knowledge_verdict": judge,
        "lookup": hits if hits is not None else "미실행",
    }
    prompt = ("<입력>\n" + json.dumps(payload, ensure_ascii=False, indent=1)
              + "\n</입력>\n\n시스템 프롬프트의 형식에 따라 JSON 하나만 출력하라.")

    def parse(text):
        r = _extract_json(text)
        if r.get("band") not in _BANDS:
            raise ValueError("band 값 오류")
        r.setdefault("confidence", "하")
        r.setdefault("evidence", [])
        r.setdefault("reasoning", "")
        r.setdefault("retraction_condition", "")
        return r

    return _call_and_parse(prompt, ORIGINALITY_GRADER_PROMPT_FILE, parse)


def _dedup(items, key):
    seen, out = set(), []
    for it in items:
        k = it.get(key)
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _profile_bits(hits, on):
    """소스별 히트 여부 비트. 미조회 소스는 None(화면에서 '-').
    exec=재정(집행) · review=PRISM(검토) · law=의안(입법) · intl=해외(OPSI 실행)."""
    def bit(src):
        return (1 if hits.get(src) else 0) if on.get(src) else None
    return {"exec": bit("fiscal"), "review": bit("prism"),
            "law": bit("bill"), "intl": bit("overseas")}


def originality_axis(transcript, fiscal_fn=None, prism_fn=None, bill_fn=None,
                     overseas_fn=None, spec=None, judge=None):
    """축 B 전체: Stage 3 → 4 → (조건부 5) → 6. 소스는 서로 다른 질문에 답한다 —
    재정(집행)·PRISM(검토)·의안(입법)·해외(OPSI 실행). 각 fn은 query→히트리스트
    호출체(해당 소스 미가용이면 None). 미조회 소스는 미발견으로 처리하지 않는다.
    spec/judge를 주면 재추출하지 않는다(재현성: 같은 명세로 재조회·재채점)."""
    from concurrent.futures import ThreadPoolExecutor

    if spec is None:
        spec = extract_spec(transcript)
    if judge is None:
        judge = judge_by_knowledge(spec)
    hits = None
    fns = {"fiscal": fiscal_fn, "prism": prism_fn, "bill": bill_fn, "overseas": overseas_fn}
    on = {k: v is not None for k, v in fns.items()}
    # 소스가 하나라도 있으면 항상 조회한다. 기억으로 선례가 확실하다(has_precedent)고
    # 보이더라도, 제목·메타데이터를 실제로 대조해 A급 근거를 확보하고 확신도를 올린다.
    if any(on.values()):
        def _q(s):
            # 해외(OPSI)는 영어 질의어(overseas)를 쓴다. 구버전 명세에 없으면 빈 목록.
            return list(spec["queries"].get(s, []))[:3]
        queries = {s: (_q(s) if on[s] else []) for s in fns}

        def _safe(fn, q):
            try:
                return fn(q) or []
            except Exception:
                return []

        collected = {s: [] for s in fns}
        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {s: [ex.submit(_safe, fns[s], q) for q in queries[s]] if on[s] else []
                    for s in fns}
            for s in fns:
                for fut in futs[s]:
                    collected[s] += fut.result()
        dedup_key = {"fiscal": "name", "prism": "title", "bill": "name", "overseas": "url"}
        hits = {s: _dedup(collected[s], dedup_key[s])[:5] for s in fns}
        hits["queries"] = queries
        hits["profile"] = _profile_bits(hits, on)
    grade = grade_originality(spec, judge, hits)
    return {"spec": spec, "judge": judge, "lookup": hits, "originality": grade}
