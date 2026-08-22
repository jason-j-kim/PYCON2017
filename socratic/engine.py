"""소크라테스 문답 엔진 — CLI(prototype/)와 웹(webapp/)이 공유하는 핵심 로직.

Claude를 부르는 길이 둘이다. 어느 쪽인지는 환경변수 하나로 정해진다.

    ANTHROPIC_API_KEY 있음 → Anthropic API 직접 호출 (기관 서버·헤드리스용)
    없음                   → claude CLI 헤드리스 (구독 로그인, 연구자 개인용)

CLI의 내부 우선순위에 기대지 않고 여기서 명시적으로 가른다. 기관 서버는
브라우저 OAuth가 어렵고 키를 기관이 소유해야 하므로 API 쪽이 맞고, 개인
연구자는 구독만으로 추가 과금 없이 쓸 수 있어 CLI 쪽이 맞다.

두 길의 응답 처리는 동일하다 — 양쪽 다 '텍스트'를 돌려주고 그 뒤 파싱이
같다. 도구호출(JSON 강제) 같은 편의를 API 쪽에만 붙이면 두 방식의 결과가
갈려 세션 간 비교가 깨지므로 일부러 맞춰 두었다.

질문자와 채점자는 별도 호출로 분리한다:
질문자는 점수를 모르고, 채점자는 대화에 참여하지 않고 로그만 본다.
"""

import contextvars
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
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



# ── 인증 방식 ────────────────────────────────────────────────────────────
# 키가 있으면 API, 없으면 CLI. 서버가 켜진 뒤 키를 넣는 일은 없으므로
# 호출 때마다 다시 읽지 않고 모듈 적재 시 한 번 정한다(세션 간 일관성).
def _clean_env(name):
    return os.environ.get(name, "").strip().strip('"').strip("'").strip()


ANTHROPIC_API_KEY = _clean_env("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = (_clean_env("ANTHROPIC_BASE_URL")
                      or "https://api.anthropic.com").rstrip("/")
CLAUDE_MODEL = _clean_env("CLAUDE_MODEL") or "claude-opus-5"
CLAUDE_MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "8000"))
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "300"))
API_RETRIES = int(os.environ.get("CLAUDE_API_RETRIES", "3"))


# 요청·세션 단위로 덮어쓰는 키. 화면에서 자기 키를 넣은 경우에만 채워진다.
# contextvars 라서 요청/스레드마다 독립이고, 끝나면 자동으로 원래대로 돌아간다.
_REQ_API_KEY = contextvars.ContextVar("anthropic_api_key", default="")

# 키가 있어도 구독 로그인으로 돌리라는 명시적 선택. 우선순위(키가 먼저)는
# 기본값일 뿐 강제가 아니어야 한다 — 키를 설정해 둔 사람이 이번에는 과금 없이
# 구독으로 돌리고 싶을 수 있고, 그 선택을 서버를 껐다 켜야만 할 수 있게
# 만들면 사실상 선택이 없는 것과 같다.
_REQ_FORCE_CLI = contextvars.ContextVar("force_cli", default=False)


def set_request_api_key(key):
    """이 요청(또는 스레드)에서만 쓸 키를 건다. 되돌릴 토큰을 준다."""
    return _REQ_API_KEY.set((key or "").strip())


def reset_request_api_key(token):
    _REQ_API_KEY.reset(token)


def set_request_force_cli(on):
    """이 요청에서만 구독 로그인을 쓰게 한다. 되돌릴 토큰을 준다."""
    return _REQ_FORCE_CLI.set(bool(on))


def reset_request_force_cli(token):
    _REQ_FORCE_CLI.reset(token)


def cli_available():
    """claude CLI 가 이 PC 에 있나. 키가 있어도 따로 알아야 한다 —
    화면에서 '구독으로 돌리기'를 보여줄지 정하는 데 쓴다."""
    return bool(shutil.which(CLAUDE_BIN))


def effective_api_key():
    """실제로 쓸 키. 화면 입력이 서버 기본값보다 우선한다.

    구독을 명시적으로 고른 요청에서는 키가 있어도 쓰지 않는다.
    """
    if _REQ_FORCE_CLI.get():
        return ""
    return _REQ_API_KEY.get() or ANTHROPIC_API_KEY


def key_source():
    """이 호출에 쓰인 키가 어디서 왔나 — 오류를 볼 때 이게 없으면 못 고친다."""
    if _REQ_API_KEY.get():
        return "화면"
    return "서버" if ANTHROPIC_API_KEY else ""


def _describe_key(key):
    """어느 키인지 사람이 알아볼 만큼만. 값은 절대 다 보이지 않는다."""
    masked = f"{key[:11]}…{key[-4:]}" if len(key) > 18 else "(짧은 값)"
    where = key_source()
    place = {"화면": "웹 화면에 입력한 키",
             "서버": "서버 설정(keys.local.bat 또는 환경변수)의 키"}.get(where, "키")
    return f"{place} {masked}"


def server_auth_mode():
    """서버 자체의 기본 방식 — 'api' | 'cli' | 'none'.

    'none' 은 API 키도 없고 claude CLI 도 없는 상태다. 이 경우 방문자가
    화면에 자기 키를 넣지 않으면 호출이 실패하므로, 첫 화면이 미리 알려야 한다.
    """
    if ANTHROPIC_API_KEY:
        return "api"
    return "cli" if shutil.which("claude") else "none"


def auth_mode():
    """'api' 또는 'cli'. 화면·로그에 어느 쪽으로 도는지 밝히는 데 쓴다."""
    return "api" if effective_api_key() else "cli"


def auth_description():
    """사람이 읽을 한 줄 설명(키 값은 절대 넣지 않는다)."""
    if ANTHROPIC_API_KEY:
        k = ANTHROPIC_API_KEY
        masked = f"{k[:7]}…{k[-4:]}" if len(k) > 14 else "설정됨"
        return f"API 키 방식 · 모델 {CLAUDE_MODEL} · 키 {masked}"
    return "구독 로그인 방식 · claude CLI"


def _call_api(prompt, system_text, api_key):
    """Anthropic Messages API 직접 호출. 표준 라이브러리만 쓴다.

    CLI 경로와 같게 '텍스트'를 돌려준다. 도구호출로 JSON을 강제하면 편하지만
    그러면 두 방식의 산출이 달라져 세션 간 비교가 깨진다."""
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": CLAUDE_MAX_TOKENS,
        "system": system_text,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    who = _describe_key(api_key)
    req = urllib.request.Request(
        f"{ANTHROPIC_BASE_URL}/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json",
                 "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"})

    last = ""
    for attempt in range(API_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=CLAUDE_TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            break
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            # 과부하·일시 오류만 재시도한다. 인증·요청 오류는 다시 해도 같다.
            if e.code in (429, 500, 502, 503, 529) and attempt < API_RETRIES - 1:
                time.sleep(2 ** attempt)
                last = f"HTTP {e.code}: {detail}"
                continue
            hint = ""
            if e.code == 401:
                extra = ("웹 첫 화면 「Claude 연결」 칸을 비우면 서버 설정으로 "
                         "돌아갑니다." if key_source() == "화면" else
                         "keys.local.bat 을 지우고 2_실행 을 다시 켜면 키를 다시 "
                         "물어봅니다.")
                hint = (f" (거부된 것은 «{who}» 입니다. Anthropic 콘솔에서 이 키가 "
                        f"살아 있는지, 잔액과 사용 한도가 남았는지 확인하세요. {extra})")
            elif e.code == 429:
                hint = " (요청 한도를 넘었습니다. 잠시 후 다시 시도하세요.)"
            elif e.code == 400 and "credit" in detail.lower():
                hint = " (콘솔 잔액이 부족할 수 있습니다.)"
            raise RuntimeError(f"Claude API 오류 HTTP {e.code}: {detail}{hint}")
        except urllib.error.URLError as e:
            if attempt < API_RETRIES - 1:
                time.sleep(2 ** attempt)
                last = str(e.reason)
                continue
            raise RuntimeError(
                f"Claude API 에 닿지 못했습니다: {e.reason}\n"
                f"(방화벽이 {ANTHROPIC_BASE_URL} 로 나가는 통신을 막고 있는지 "
                "확인하세요. 이 경우 구독 방식도 같은 곳으로 나가므로 함께 막힙니다.)")
    else:
        raise RuntimeError(f"Claude API 재시도 실패: {last}")

    out = "".join(b.get("text", "") for b in data.get("content", [])
                  if b.get("type") == "text").strip()
    if not out:
        raise RuntimeError(
            f"Claude API 가 빈 응답을 돌려줬습니다 (stop_reason={data.get('stop_reason')}). "
            "max_tokens 가 너무 작을 수 있습니다 — CLAUDE_MAX_TOKENS 를 올려 보세요.")
    return out


def call_claude(prompt, system_prompt_file):
    """Claude를 부른다. 키가 있으면 API, 없으면 CLI(구독 로그인).

    system_prompt_file: 시스템 프롬프트가 담긴 파일 경로. CLI에는 경로로 넘긴다
    (여러 줄 텍스트를 명령줄 인자로 주면 Windows에서 깨진다). API에는 파일을
    읽어 본문으로 넘긴다.
    """
    key = effective_api_key()
    if key:
        return _call_api(prompt, Path(system_prompt_file).read_text(encoding="utf-8"), key)
    return _call_cli(prompt, system_prompt_file)


def _call_cli(prompt, system_prompt_file):
    """Claude Code CLI를 헤드리스로 호출한다. 도구를 모두 끄고 순수 대화만 시킨다.

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
            encoding="utf-8", errors="replace", timeout=CLAUDE_TIMEOUT,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "claude CLI를 찾을 수 없습니다. 둘 중 하나를 하세요. "
            "① Claude Code 설치(npm install -g @anthropic-ai/claude-code) 후 "
            "새 터미널에서 서버 재시작. "
            "② CLI 없이 쓰려면 ANTHROPIC_API_KEY 를 설정하고 서버를 재시작하세요 "
            "(그러면 API로 직접 호출합니다)."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude 응답이 {CLAUDE_TIMEOUT}초를 초과했습니다. 다시 시도하세요.")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "원인 미상").strip()[:500]
        hint = "(로그인이 안 된 경우 터미널에서 `claude`를 실행해 /login 하세요)"
        if "401" in detail or "authentication" in detail.lower():
            hint = (
                "(구독 로그인 인증 실패입니다. `claude` 를 실행해 /login 하세요. "
                "브라우저를 쓸 수 없는 서버라면 ANTHROPIC_API_KEY 를 설정해 "
                "API 방식으로 돌리는 편이 낫습니다.)"
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


SOURCE_LABEL = {"fiscal": "재정(집행)", "prism": "KDI 연구(검토)",
                "bill": "국회 의안(입법)", "overseas": "해외 OPSI(시행)"}
# profile 비트 키 ↔ 소스키. profile 값이 None이면 그 통로는 아예 돌지 않았다.
_PROFILE_KEY = {"fiscal": "exec", "prism": "review",
                "bill": "law", "overseas": "intl"}


def judge_lookup_view(hits):
    """판정가에게 넘길 조회 결과 표현.

    미실행 통로를 빈 배열로 넘기면 '조회했는데 0건'과 구분되지 않는다. 실제로
    의안 키가 없어 통로가 꺼진 세션에서 판정문이 "의안 조회는 0건으로 입법 시도
    흔적이 없고"라고 적힌 사례가 있었다 — 미발견≠부재 원칙에 어긋난다.

    그래서 미실행 통로는 배열이 아니라 문자열로 바꿔 **애초에 셀 수 없게** 하고,
    coverage에 통로별 실행 여부를 못 박는다. 화면·DB에 저장되는 hits 원본은
    건드리지 않는다(프런트가 리스트를 기대한다)."""
    if hits is None:
        return "미실행 — 어느 통로도 조회하지 않았다. 0건이 아니다."
    view = dict(hits)
    prof = hits.get("profile") or {}
    queries = dict(hits.get("queries") or {})
    failed = hits.get("failed") or {}
    coverage = {}
    for src, pkey in _PROFILE_KEY.items():
        label = SOURCE_LABEL[src]
        if prof.get(pkey) is None:          # 조회기 없음 → 통로가 꺼져 있었다
            view[src] = "미실행(조회하지 않음)"
            queries[src] = "미실행"
            coverage[label] = "미실행 — 조회기가 없어 돌리지 않았다. 0건이 아니며 부재의 근거가 될 수 없다."
        elif src in failed:                 # 돌렸으나 질의가 전부 오류
            view[src] = "조회 실패(오류로 결과를 받지 못함)"
            coverage[label] = ("조회 실패 — 시도했으나 모두 오류로 끝났다"
                               f"({failed[src][:80]}). 0건이 아니며 부재의 근거가 될 수 없다.")
        else:
            n_q = len((hits.get("queries") or {}).get(src) or [])
            coverage[label] = f"실행 — 질의 {n_q}개, 히트 {len(hits.get(src) or [])}건"
    view["queries"] = queries
    view["coverage"] = coverage
    return view


def grade_originality(spec_result, judge, hits=None):
    """Stage 6: 4구간 + 확신도로 실질 독창성을 판정한다(로그 미투입)."""
    payload = {
        "spec": spec_result["spec"],
        "policy_type": spec_result["policy_type"],
        "knowledge_verdict": judge,
        "lookup": judge_lookup_view(hits),
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
            """오류를 삼키되 삼켰다는 사실은 남긴다. 통신 실패를 그냥 []로 돌리면
            '조회했는데 0건'과 구분되지 않아, 망 장애가 미발견 근거로 둔갑한다."""
            try:
                return fn(q) or [], None
            except Exception as e:
                return [], f"{type(e).__name__}: {e}"

        collected = {s: [] for s in fns}
        errors = {s: [] for s in fns}
        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {s: [ex.submit(_safe, fns[s], q) for q in queries[s]] if on[s] else []
                    for s in fns}
            for s in fns:
                for fut in futs[s]:
                    rows, err = fut.result()
                    collected[s] += rows
                    if err:
                        errors[s].append(err)
        dedup_key = {"fiscal": "name", "prism": "title", "bill": "name", "overseas": "url"}
        hits = {s: _dedup(collected[s], dedup_key[s])[:5] for s in fns}
        hits["queries"] = queries
        hits["profile"] = _profile_bits(hits, on)
        # 질의가 하나라도 있었는데 전부 오류였다면 그 통로는 '조회 실패'다.
        hits["failed"] = {s: errors[s][0] for s in fns
                          if on[s] and queries[s] and len(errors[s]) == len(queries[s])}
    grade = grade_originality(spec, judge, hits)
    return {"spec": spec, "judge": judge, "lookup": hits, "originality": grade}
