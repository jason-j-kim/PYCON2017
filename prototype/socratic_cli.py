#!/usr/bin/env python3
"""소크라테스 문답법 아이디어 평가 — 1단계 프롬프트 프로토타입 CLI.

질문자(대화 진행)와 채점자(루브릭 채점)를 별도 LLM 호출로 분리한다.
질문자는 점수를 모르고, 채점자는 대화에 참여하지 않는다.

사용법:
    export ANTHROPIC_API_KEY=sk-...
    python socratic_cli.py
    python socratic_cli.py --w-orig 0.5 --w-prac 0.3 --w-acc 0.2

대화 중 'q'를 입력하면 남은 문답을 건너뛰고 바로 채점으로 넘어간다.
세션이 끝나면 대화 로그와 평가 결과가 JSON 파일로 저장된다.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-8"
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

# 채점 결과 스키마 — 수치 범위는 스키마로 강제할 수 없으므로 프롬프트 루브릭이 담당한다.
_CRITERION = {
    "type": "object",
    "properties": {
        "specificity": {"type": "integer", "description": "구체성 0~4"},
        "consistency": {"type": "integer", "description": "논리적 일관성 0~3"},
        "self_awareness": {"type": "integer", "description": "자기 인식 0~3"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "각 점수의 근거. 반드시 턴 번호를 인용",
        },
    },
    "required": ["specificity", "consistency", "self_awareness", "evidence"],
    "additionalProperties": False,
}

GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "originality": _CRITERION,
        "practicality": _CRITERION,
        "acceptance": _CRITERION,
        "strengths": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
        "encouragement": {"type": "string"},
    },
    "required": [
        "originality", "practicality", "acceptance",
        "strengths", "suggestions", "encouragement",
    ],
    "additionalProperties": False,
}


def ask_questioner(client, system_prompt, messages, stage_directive):
    """질문자 호출. 단계 지시는 mid-conversation system 메시지로 주입해
    캐시된 대화 프리픽스를 깨지 않는다. 스트리밍으로 출력."""
    request_messages = messages + [{"role": "system", "content": stage_directive}]
    parts = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=request_messages,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            parts.append(text)
        final = stream.get_final_message()
    print()
    if final.stop_reason == "refusal":
        raise RuntimeError("질문자 요청이 안전상의 이유로 거부되었습니다.")
    return "".join(parts), request_messages


def grade(client, grader_prompt, transcript):
    """채점자 호출. 대화 로그 전체를 넘기고 스키마 강제 JSON으로 받는다."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=grader_prompt,
        output_config={"format": {"type": "json_schema", "schema": GRADE_SCHEMA}},
        messages=[{
            "role": "user",
            "content": "다음 아이디어 평가 세션의 대화 로그를 루브릭에 따라 채점하라.\n\n"
                       + transcript,
        }],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("채점 요청이 안전상의 이유로 거부되었습니다.")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def criterion_total(c):
    return c["specificity"] + c["consistency"] + c["self_awareness"]


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

    questioner_prompt = (PROMPT_DIR / "questioner_system.md").read_text(encoding="utf-8")
    grader_prompt = (PROMPT_DIR / "grader_system.md").read_text(encoding="utf-8")

    client = anthropic.Anthropic()

    print("아이디어를 자유롭게 서술하세요. (입력 후 Enter)")
    idea = input("> ").strip()
    if not idea:
        sys.exit("아이디어가 비어 있습니다.")

    # transcript_log: 채점자에게 넘길 턴 번호 붙은 기록
    # messages: 질문자 API 호출용 대화 이력 (단계 지시 system 메시지 포함)
    turn = 1
    transcript_log = [f"[턴 {turn}] 제안자: {idea}"]
    messages = [{"role": "user", "content": idea}]

    try:
        for _, stage_label, n_turns, directive in STAGES:
            print(f"\n--- {stage_label} 단계 ---")
            for _ in range(n_turns):
                print("\n질문자: ", end="", flush=True)
                question, messages = ask_questioner(
                    client, questioner_prompt, messages, directive
                )
                turn += 1
                transcript_log.append(f"[턴 {turn}] 질문자({stage_label}): {question}")
                messages.append({"role": "assistant", "content": question})

                answer = input("\n제안자> ").strip()
                if answer.lower() == "q":
                    raise KeyboardInterrupt
                turn += 1
                transcript_log.append(f"[턴 {turn}] 제안자: {answer}")
                messages.append({"role": "user", "content": answer})
    except KeyboardInterrupt:
        print("\n(문답을 종료하고 채점으로 넘어갑니다)")

    transcript = "\n\n".join(transcript_log)
    print("\n채점 중...")
    result = grade(client, grader_prompt, transcript)
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
    try:
        main()
    except anthropic.AuthenticationError:
        sys.exit("API 키가 유효하지 않습니다. ANTHROPIC_API_KEY를 확인하세요.")
    except anthropic.APIConnectionError:
        sys.exit("네트워크 오류입니다. 연결을 확인하고 다시 시도하세요.")
    except anthropic.APIStatusError as e:
        sys.exit(f"API 오류 ({e.status_code}): {e.message}")
