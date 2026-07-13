#!/usr/bin/env python3
"""소크라테스 문답법 아이디어 평가 — 1단계 프롬프트 프로토타입 CLI.

백엔드로 Claude Code CLI(`claude -p`)를 사용한다. Claude Pro/Max 구독으로
로그인되어 있으면 그대로 동작하며, API 키가 필요 없다.

질문자(대화 진행)와 채점자(루브릭 채점)를 별도 호출로 분리한다.
질문자는 점수를 모르고, 채점자는 대화에 참여하지 않는다.

사용법:
    claude /login   # 최초 1회, Pro 구독 계정으로 로그인
    python socratic_cli.py
    python socratic_cli.py --w-orig 0.5 --w-prac 0.3 --w-acc 0.2

대화 중 'q'를 입력하면 남은 문답을 건너뛰고 바로 채점으로 넘어간다.
세션이 끝나면 대화 로그와 평가 결과가 JSON 파일로 저장된다.
"""

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"

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

CRITERIA = ("originality", "practicality", "acceptance")
SUBSCORES = ("specificity", "consistency", "self_awareness")


def call_claude(prompt, system_prompt):
    """Claude Code CLI를 헤드리스로 호출한다. 도구를 모두 끄고 순수 대화만 시킨다."""
    cmd = [
        "claude", "-p",
        "--system-prompt", system_prompt,
        "--tools", "",
        "--no-session-persistence",
        "--output-format", "text",
    ]
    result = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI 오류: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def ask_questioner(system_prompt, transcript_log, stage_directive):
    """대화 로그 전체 + 현재 단계 지시를 넘겨 다음 질문 하나를 받는다."""
    prompt = (
        "<대화 기록>\n" + "\n\n".join(transcript_log) + "\n</대화 기록>\n\n"
        f"<현재 단계 지시>\n{stage_directive}\n</현재 단계 지시>\n\n"
        "위 대화에 이어서, 시스템 프롬프트의 규칙에 따라 질문자의 다음 발화를 "
        "출력하라. 발화 내용만 출력하고 다른 설명은 붙이지 마라."
    )
    return call_claude(prompt, system_prompt)


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


def grade(grader_prompt, transcript):
    """채점자 호출. 대화 로그 전체를 넘기고 JSON으로 받는다. 파싱 실패 시 1회 재시도."""
    prompt = (
        "다음 아이디어 평가 세션의 대화 로그를 시스템 프롬프트의 루브릭에 따라 "
        "채점하라.\n\n<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
        "결과는 아래 형태의 JSON **하나만** 출력하라. 코드 펜스나 설명 없이 "
        "JSON으로 시작해서 JSON으로 끝나야 한다.\n" + GRADE_FORMAT
    )
    last_error = None
    for _ in range(2):
        text = call_claude(prompt, grader_prompt)
        try:
            return parse_grade_json(text)
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            last_error = e
    raise RuntimeError(f"채점 결과 파싱 실패: {last_error}")


def criterion_total(c):
    return sum(c[s] for s in SUBSCORES)


def print_report(result, weights):
    w_orig, w_prac, w_acc = weights
    scores = {
        "독창성": (criterion_total(result["originality"]), w_orig, result["originality"]),
        "실용성": (criterion_total(result["practicality"]), w_prac, result["practicality"]),
        "수용태도": (criterion_total(result["acceptance"]), w_acc, result["acceptance"]),
    }
    weighted_total = sum(total * w for total, w, _ in scores.values())

    print("\n" + "=" * 60)
    print("평가 결과")
    print("=" * 60)
    for name, (total, w, detail) in scores.items():
        print(f"\n[{name}] {total}/10 (가중치 {w})")
        print(f"  구체성 {detail['specificity']}/4 · "
              f"일관성 {detail['consistency']}/3 · "
              f"자기 인식 {detail['self_awareness']}/3")
        for ev in detail["evidence"]:
            print(f"  - {ev}")
    print(f"\n종합 점수 (가중 평균): {weighted_total:.1f}/10")

    print("\n[강점]")
    for s in result["strengths"]:
        print(f"  - {s}")
    print("\n[개선 제안]")
    for s in result["suggestions"]:
        print(f"  - {s}")
    print(f"\n[격려]\n  {result['encouragement']}")
    return weighted_total


def main():
    parser = argparse.ArgumentParser(description="소크라테스 문답법 아이디어 평가 프로토타입")
    parser.add_argument("--w-orig", type=float, default=0.35, help="독창성 가중치")
    parser.add_argument("--w-prac", type=float, default=0.35, help="실용성 가중치")
    parser.add_argument("--w-acc", type=float, default=0.30, help="수용태도 가중치")
    args = parser.parse_args()

    weights = (args.w_orig, args.w_prac, args.w_acc)
    if abs(sum(weights) - 1.0) > 1e-6:
        parser.error(f"가중치의 합은 1이어야 합니다 (현재 {sum(weights)})")

    if shutil.which("claude") is None:
        sys.exit(
            "claude CLI를 찾을 수 없습니다.\n"
            "설치: https://claude.com/claude-code  → 설치 후 `claude /login` 으로 "
            "Pro 구독 계정에 로그인하세요. (API 키 불필요)"
        )

    questioner_prompt = (PROMPT_DIR / "questioner_system.md").read_text(encoding="utf-8")
    grader_prompt = (PROMPT_DIR / "grader_system.md").read_text(encoding="utf-8")

    print("아이디어를 자유롭게 서술하세요. (입력 후 Enter)")
    idea = input("> ").strip()
    if not idea:
        sys.exit("아이디어가 비어 있습니다.")

    turn = 1
    transcript_log = [f"[턴 {turn}] 제안자: {idea}"]

    try:
        for _, stage_label, n_turns, directive in STAGES:
            print(f"\n--- {stage_label} 단계 ---")
            for _ in range(n_turns):
                print("\n(질문 생성 중...)", end="\r")
                question = ask_questioner(questioner_prompt, transcript_log, directive)
                turn += 1
                transcript_log.append(f"[턴 {turn}] 질문자({stage_label}): {question}")
                print(f"질문자: {question}      ")

                answer = input("\n제안자> ").strip()
                if answer.lower() == "q":
                    raise KeyboardInterrupt
                turn += 1
                transcript_log.append(f"[턴 {turn}] 제안자: {answer}")
    except KeyboardInterrupt:
        print("\n(문답을 종료하고 채점으로 넘어갑니다)")

    transcript = "\n\n".join(transcript_log)
    print("\n채점 중...")
    result = grade(grader_prompt, transcript)
    weighted_total = print_report(result, weights)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"session_{stamp}.json")
    out.write_text(
        json.dumps(
            {
                "idea": idea,
                "weights": {"originality": weights[0], "practicality": weights[1],
                            "acceptance": weights[2]},
                "transcript": transcript_log,
                "evaluation": result,
                "weighted_total": round(weighted_total, 2),
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n세션 저장: {out}")


if __name__ == "__main__":
    main()
