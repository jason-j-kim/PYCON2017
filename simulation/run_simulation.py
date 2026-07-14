#!/usr/bin/env python3
"""5-에이전트 시뮬레이션: 시스템 안정성 테스트.

에이전트 5개가 독립적으로 움직인다:
  ① 제안자 (아이디어 생성 + 질문에 답변, 품질 프로필 지정)
  ② 질문자 (소크라테스 문답)
  ③ 규정 심사위원 (기준별 체크리스트 사실 판정)
  ④ 종합 심사위원 (전체 인상 채점)
  ⑤ 재판장 (두 심사위원 결과 검토 + 최종 판정문)

진부(banal)/창의(creative) 프로필의 아이디어를 교대로 생성해 전체 세션을
자동 진행하고, 결과를 simulation/results/에 저장한다.

사용법 (저장소 루트에서):
    python simulation/run_simulation.py --pairs 5          # 진부 5 + 창의 5
    python simulation/run_simulation.py --pairs 1 --max-questions 3   # 스모크 테스트
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socratic import engine

RESULTS_DIR = Path(__file__).parent / "results"

PROFILES = {
    "banal": (
        "당신의 프로필: 평범한 제안자. 이미 세상에 흔히 있는 뻔한 아이디어를 "
        "제안한다. 답변은 성실하지만 깊이가 없다 — 구체적 수치나 실제 사례 대신 "
        "'많은 사람들이 좋아할 것 같다' 같은 일반론으로 답하고, 기존 서비스와의 "
        "차이를 물으면 '더 편리하다' 수준으로만 답한다. 약점을 지적받으면 "
        "마지못해 짧게 인정하고 구체적 보완책은 내지 못한다."
    ),
    "creative": (
        "당신의 프로필: 뛰어난 제안자. 참신하고 남들이 생각하지 못한 아이디어를 "
        "제안한다. 답변에는 구체적 수치, 실제 사례, 검증 가능한 근거를 담는다. "
        "기존 해법을 실명으로 비교하며 차별점을 명확히 하고, 반례에는 정면으로 "
        "대응한다. 약점은 지적받기 전에 스스로 인정하고 구체적 보완책을 함께 "
        "제시한다. 실행 계획은 자원·비용·단계까지 숫자로 말한다."
    ),
}


# 시행별 도메인 지정 — 병렬 실행 시에도 아이디어가 겹치지 않게 한다
DOMAINS = ["교육", "건강·의료", "환경", "교통", "식품", "주거", "여가·문화",
           "금융", "농업", "노인 돌봄", "육아", "반려동물", "재난 안전", "중고 거래"]


def proposer(profile, request):
    prompt = f"<제안자 프로필>\n{profile}\n</제안자 프로필>\n\n{request}"
    return engine.call_claude(prompt, engine.PROPOSER_PROMPT_FILE)


def generate_idea(profile, used_ideas, trial_no):
    domain = DOMAINS[(trial_no - 1) % len(DOMAINS)]
    avoid = ""
    if used_ideas:
        avoid = ("\n지금까지 나온 아이디어와 겹치지 않게 하라:\n- "
                 + "\n- ".join(used_ideas))
    return proposer(
        profile,
        f"'{domain}' 분야에서 프로필에 맞는 품질의 아이디어를 1~3문장으로 "
        f"제안하라. 아이디어 내용만 출력하라.{avoid}",
    )


def answer_question(profile, transcript_log, question):
    return proposer(
        profile,
        "<지금까지의 대화>\n" + "\n\n".join(transcript_log) + "\n</지금까지의 대화>\n\n"
        f"질문자의 마지막 질문에 프로필에 맞게 답하라. 답변만 출력하라.\n"
        f"질문: {question}",
    )


def run_trial(label, trial_no, used_ideas, max_questions=None):
    profile = PROFILES[label]
    t0 = time.time()
    idea = generate_idea(profile, used_ideas, trial_no)
    print(f"  아이디어: {idea[:70]}", flush=True)

    turn = 1
    transcript_log = [f"[턴 {turn}] 제안자: {idea}"]
    asked = 0
    for _, stage_label, n_turns, directive in engine.STAGES:
        for _ in range(n_turns):
            if max_questions is not None and asked >= max_questions:
                break
            question = engine.ask_questioner(transcript_log, directive)
            turn += 1
            transcript_log.append(f"[턴 {turn}] 질문자({stage_label}): {question}")
            answer = answer_question(profile, transcript_log, question)
            turn += 1
            transcript_log.append(f"[턴 {turn}] 제안자: {answer}")
            asked += 1
            print(f"  문답 {asked} ({stage_label}) 완료", flush=True)
        if max_questions is not None and asked >= max_questions:
            break

    transcript = "\n\n".join(transcript_log)
    print("  채점 중 (규정+종합 심사위원)...", flush=True)
    result = engine.grade(transcript)
    print("  재판장 판정 중...", flush=True)
    synthesis = engine.synthesize(transcript, result)
    total = round(engine.weighted_total(result, engine.DEFAULT_WEIGHTS), 2)

    record = {
        "trial": trial_no,
        "label": label,
        "idea": idea,
        "transcript": transcript_log,
        "evaluation": result,
        "synthesis": synthesis,
        "weighted_total": total,
        "elapsed_sec": round(time.time() - t0),
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"trial_{trial_no:02d}_{label}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    scores = " · ".join(
        f"{engine.CRITERIA_KO[c]} {result['criteria'][c]['final']}"
        f"(체크 {result['criteria'][c]['checklist']['total']}/종합 "
        f"{result['criteria'][c]['holistic']['score']})"
        for c in engine.CRITERIA
    )
    print(f"  → 종합 {total}/10 | {scores} | {record['elapsed_sec']}초", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description="5-에이전트 안정성 시뮬레이션")
    parser.add_argument("--pairs", type=int, default=5, help="진부/창의 쌍의 수")
    parser.add_argument("--start-pair", type=int, default=1,
                        help="시작 쌍 번호 (병렬 실행 시 작업 분할용)")
    parser.add_argument("--max-questions", type=int, default=None,
                        help="세션당 질문 수 제한 (스모크 테스트용; 기본은 전체 12개)")
    args = parser.parse_args()

    used_ideas = []
    for pair in range(args.start_pair, args.start_pair + args.pairs):
        for offset, label in ((1, "banal"), (2, "creative")):
            trial_no = (pair - 1) * 2 + offset
            print(f"\n=== 시행 {trial_no} [{label}] ===", flush=True)
            record = run_trial(label, trial_no, used_ideas, args.max_questions)
            used_ideas.append(f"({record['label']}) {record['idea'][:60]}")
    print("\n시뮬레이션 완료. 리포트 생성: python simulation/report.py", flush=True)


if __name__ == "__main__":
    main()
