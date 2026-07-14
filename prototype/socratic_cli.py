#!/usr/bin/env python3
"""소크라테스 문답법 아이디어 평가 — CLI (socratic/engine.py의 터미널 프런트엔드).

백엔드로 Claude Code CLI(`claude -p`)를 사용한다. Claude Pro/Max 구독으로
로그인되어 있으면 그대로 동작하며, API 키가 필요 없다.

사용법:
    claude /login   # 최초 1회, Pro 구독 계정으로 로그인
    python prototype/socratic_cli.py
    python prototype/socratic_cli.py --w-orig 0.5 --w-prac 0.3 --w-acc 0.2

대화 중 'q'를 입력하면 남은 문답을 건너뛰고 바로 채점으로 넘어간다.
세션이 끝나면 대화 로그와 평가 결과가 JSON 파일로 저장된다.
"""

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socratic import engine


def print_report(result, weights):
    total_score = engine.weighted_total(result, weights)

    print("\n" + "=" * 60)
    print("평가 결과")
    print("=" * 60)
    for c in engine.CRITERIA:
        d = result["criteria"][c]
        print(f"\n[{engine.CRITERIA_KO[c]}] {d['final']}/10 (가중치 {weights[c]})")
        print(f"  체크리스트 {d['checklist']['total']}/10 · "
              f"종합판단 {d['holistic']['score']}/10 → 평균 {d['final']}")
        print(f"  종합판단 근거: {d['holistic']['rationale']}")
        for item_id, entry in d["checklist"]["items"].items():
            mark = "O" if entry["met"] else "X"
            print(f"  [{mark}] {engine.CHECKLIST_LABELS[c][item_id]} — {entry['evidence']}")
    print(f"\n종합 점수 (가중 평균): {total_score:.1f}/10")

    print("\n[강점]")
    for s in result["strengths"]:
        print(f"  - {s}")
    print("\n[개선 제안]")
    for s in result["suggestions"]:
        print(f"  - {s}")
    print(f"\n[격려]\n  {result['encouragement']}")
    return total_score


def main():
    parser = argparse.ArgumentParser(description="소크라테스 문답법 아이디어 평가 프로토타입")
    parser.add_argument("--w-orig", type=float, default=0.35, help="독창성 가중치")
    parser.add_argument("--w-prac", type=float, default=0.35, help="실용성 가중치")
    parser.add_argument("--w-acc", type=float, default=0.30, help="수용태도 가중치")
    args = parser.parse_args()

    weights = {"originality": args.w_orig, "practicality": args.w_prac,
               "acceptance": args.w_acc}
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        parser.error(f"가중치의 합은 1이어야 합니다 (현재 {sum(weights.values())})")

    if shutil.which("claude") is None:
        sys.exit(
            "claude CLI를 찾을 수 없습니다.\n"
            "설치: https://claude.com/claude-code  → 설치 후 `claude /login` 으로 "
            "Pro 구독 계정에 로그인하세요. (API 키 불필요)"
        )

    print("아이디어를 자유롭게 서술하세요. (입력 후 Enter)")
    idea = input("> ").strip()
    if not idea:
        sys.exit("아이디어가 비어 있습니다.")

    turn = 1
    transcript_log = [f"[턴 {turn}] 제안자: {idea}"]

    try:
        for _, stage_label, n_turns, directive in engine.STAGES:
            print(f"\n--- {stage_label} 단계 ---")
            for _ in range(n_turns):
                print("\n(질문 생성 중...)", end="\r")
                question = engine.ask_questioner(transcript_log, directive)
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

    print("\n채점 중...")
    result = engine.grade("\n\n".join(transcript_log))
    total_score = print_report(result, weights)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"session_{stamp}.json")
    out.write_text(
        json.dumps(
            {
                "idea": idea,
                "weights": weights,
                "transcript": transcript_log,
                "evaluation": result,
                "weighted_total": round(total_score, 2),
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n세션 저장: {out}")


if __name__ == "__main__":
    main()
