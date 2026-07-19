#!/usr/bin/env python3
"""질문자 지침 3안 비교 시뮬레이션.

공정한 비교를 위해 아이디어와 제안자 페르소나를 고정하고, 질문자 지침만
바꿔서 세션을 돌린다: 3안 × (진부, 창의) = 6세션.
각 세션은 12문답 완주 → 이원 채점 → 대화 계량 분석까지 수행한다.

사용법 (저장소 루트에서):
    python simulation/run_variants.py --variant v1   # 한 안만 (병렬 분할용)
    python simulation/run_variants.py                # 3안 전부 순차
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socratic import engine
from simulation.run_simulation import PROFILES, answer_question

RESULTS_DIR = Path(__file__).parent / "results_variants"
ANALYST_FILE = Path(__file__).parent / "analyst_system.md"
VARIANT_DIR = Path("socratic/prompts/variants")

VARIANTS = {
    "v1": ("논박형", VARIANT_DIR / "questioner_v1_elenchus.md"),
    "v2": ("산파술형", VARIANT_DIR / "questioner_v2_maieutics.md"),
    "v3": ("변증법 절차형", VARIANT_DIR / "questioner_v3_dialectic.md"),
}

# 아이디어 고정 — 세 안이 완전히 같은 출발점에서 시작하게 한다
FIXED_IDEAS = {
    "banal": "회의실 예약을 관리하는 사내 웹 프로그램을 만들면 어떨까 합니다. "
             "직원들이 온라인으로 회의실을 예약하고 현황을 볼 수 있게 하는 거예요.",
    "creative": "약국마다 유효기간이 임박해 폐기되는 일반의약품 재고를 실시간으로 "
                "등록하게 하고, 인근 약국끼리 재고를 이전·정산해 폐기율을 줄이는 "
                "약국 간 B2B 재고 교환 플랫폼을 제안합니다.",
}


def analyze_dialogue(transcript):
    prompt = (
        "<대화 로그>\n" + transcript + "\n</대화 로그>\n\n"
        "질문자의 발화를 계측 정의에 따라 분석하라. 아래 형태의 JSON 하나만 출력하라.\n"
        '{"acknowledgments": 0, "evasion_callouts": 0, "choice_format_questions": 0, '
        '"tools_used": ["명료화"], "tone": "..."}'
    )
    last = None
    for _ in range(2):
        text = engine.call_claude(prompt, ANALYST_FILE)
        try:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(m.group(0))
            for k in ("acknowledgments", "evasion_callouts",
                      "choice_format_questions", "tools_used", "tone"):
                assert k in data
            return data
        except Exception as e:
            last = e
    raise RuntimeError(f"분석 파싱 실패: {last}")


def run_session(vkey, label):
    vname, vfile = VARIANTS[vkey]
    profile = PROFILES[label]
    idea = FIXED_IDEAS[label]
    t0 = time.time()

    turn = 1
    transcript_log = [f"[턴 {turn}] 제안자: {idea}"]
    asked = 0
    for _, stage_label, n_turns, directive in engine.STAGES:
        for _ in range(n_turns):
            question = engine.ask_questioner(transcript_log, directive, vfile)
            turn += 1
            transcript_log.append(f"[턴 {turn}] 질문자({stage_label}): {question}")
            answer = answer_question(profile, transcript_log, question)
            turn += 1
            transcript_log.append(f"[턴 {turn}] 제안자: {answer}")
            asked += 1
            print(f"  [{vkey}/{label}] 문답 {asked}/12 ({stage_label})", flush=True)

    transcript = "\n\n".join(transcript_log)
    print(f"  [{vkey}/{label}] 채점 중...", flush=True)
    result = engine.grade(transcript)
    print(f"  [{vkey}/{label}] 대화 분석 중...", flush=True)
    analysis = analyze_dialogue(transcript)
    total = round(engine.weighted_total(result, engine.DEFAULT_WEIGHTS), 2)

    record = {
        "variant": vkey, "variant_name": vname, "label": label, "idea": idea,
        "transcript": transcript_log, "evaluation": result, "analysis": analysis,
        "weighted_total": total, "elapsed_sec": round(time.time() - t0),
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{vkey}_{label}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [{vkey}/{label}] 완료 → 종합 {total}/10 ({record['elapsed_sec']}초)", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=list(VARIANTS), default=None,
                        help="특정 안만 실행 (병렬 분할용)")
    args = parser.parse_args()

    targets = [args.variant] if args.variant else list(VARIANTS)
    for vkey in targets:
        for label in ("banal", "creative"):
            print(f"\n=== {vkey} ({VARIANTS[vkey][0]}) · {label} ===", flush=True)
            run_session(vkey, label)
    print("\n완료. 리포트: python simulation/variants_report.py", flush=True)


if __name__ == "__main__":
    main()
