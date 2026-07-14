#!/usr/bin/env python3
"""인간 심사위원용 인쇄 채점표 생성기.

시뮬레이션 시행 2개(세션 A/B)를 골라, AI 점수는 일절 표기하지 않은(블라인드)
인쇄용 HTML을 만든다. 대화 전문 + AI와 동일한 루브릭의 수기 기입란 포함.
브라우저로 열어 Ctrl+P로 인쇄한다.

사용법 (저장소 루트에서):
    python simulation/make_judge_sheet.py \
        --a simulation/results/trial_04_creative.json \
        --b simulation/results/trial_05_banal.json \
        -o simulation/judge_sheet.html
"""

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from socratic import engine

BANDS = [
    ("0~2", "회피·공허한 주장. 근거가 거의 없고 같은 질문에 두 번 이상 모호하게 답함"),
    ("3~4", "주장은 있으나 뒷받침이 빈약. 구체성 없이 일반론으로 답함"),
    ("5~6", "구체적 근거를 일부 제시하고 논리를 대체로 유지하나 빈틈이 여럿 남음"),
    ("7~8", "일관된 논증 + 검증 가능한 근거 + 자기 약점 인식이 모두 나타남"),
    ("9~10", "반례와 전제 공격까지 정합적으로 소화하며 심사위원을 설득해 냄"),
]


def esc(s):
    return html.escape(s)


def transcript_html(record):
    rows = []
    for line in record["transcript"]:
        # "[턴 N] 역할...: 내용" 형식
        head, _, body = line.partition(": ")
        cls = "q" if "질문자" in head else "a"
        rows.append(
            f'<div class="turn {cls}"><span class="turn-head">{esc(head)}</span>'
            f'{esc(body)}</div>'
        )
    return "\n".join(rows)


def checklist_table(criterion):
    rows = []
    for item_id, label, desc in engine.CHECKLIST_ITEMS[criterion]:
        rows.append(
            f"<tr><td class='iid'>{item_id}</td>"
            f"<td><b>{esc(label)}</b><br><span class='desc'>{esc(desc)}</span></td>"
            f"<td class='chk'>&#9744; 충족<br>&#9744; 불충족</td>"
            f"<td class='evid'>턴&nbsp;____<br><span class='desc'>근거:</span></td></tr>"
        )
    return (
        "<table class='cl'>"
        "<tr><th style='width:7%'>번호</th><th>항목 (충족 판정에는 턴 번호 필수)</th>"
        "<th style='width:13%'>판정</th><th style='width:26%'>근거 턴·메모</th></tr>"
        + "".join(rows) + "</table>"
    )


def session_html(tag, record, holistic_only=False):
    parts = [f"<div class='pagebreak'></div><h1>세션 {tag} — 대화 전문</h1>"]
    parts.append(f"<div class='ideabox'><b>제안된 아이디어</b><br>{esc(record['idea'])}</div>")
    parts.append(transcript_html(record))

    if holistic_only:
        parts.append(f"<div class='pagebreak'></div><h1>세션 {tag} — 채점표 (종합판단)</h1>")
        parts.append(
            "<p class='note'>숙련된 심사위원으로서 <b>전체적 인상</b>으로 채점하십시오 — "
            "답변의 논리적 흐름, 태도의 진정성, 논증 전체의 설득력을 통합해서 "
            "판단하되, 근거는 대화의 턴 번호를 인용해 적으십시오. 약점의 솔직한 "
            "인정은 감점이 아니라 가점 요인입니다. 채점 대상은 아이디어 자체가 "
            "아니라 <b>제안자의 답변</b>입니다.</p>"
        )
        band_rows = "".join(f"<tr><td class='iid'>{b}</td><td>{esc(d)}</td></tr>" for b, d in BANDS)
        parts.append(f"<table class='cl bands'><tr><th style='width:12%'>점수 밴드</th><th>기준</th></tr>{band_rows}</table>")
        crit_hint = {
            "originality": "기존 해법과의 차별을 입증했는가",
            "practicality": "실행 가능성을 입증했는가",
            "acceptance": "사용자·이해관계자가 받아들일 근거를 입증했는가",
        }
        for c in engine.CRITERIA:
            parts.append(
                f"<div class='holistic'><h2>{engine.CRITERIA_KO[c]} "
                f"<span class='desc'>({crit_hint[c]})</span> &nbsp;&nbsp; "
                f"점수: ________ / 10</h2>"
                "<div class='writeline'></div><div class='writeline'></div>"
                "<div class='writeline'></div></div>"
            )
        return "\n".join(parts)

    parts.append(f"<div class='pagebreak'></div><h1>세션 {tag} — 채점표 1: 체크리스트 (규정 심사)</h1>")
    parts.append(
        "<p class='note'>각 항목에 대해 \"이 사건이 대화에 실제로 있었는가\"만 판정하십시오. "
        "인상·종합 평가가 아니라 사실 판정입니다. <b>충족으로 판정하려면 근거가 되는 턴 번호를 "
        "반드시 기입</b>하십시오. 인용할 턴을 특정할 수 없으면 불충족입니다. 애매하면 불충족으로 "
        "판정합니다. 판정 대상은 아이디어 자체가 아니라 <b>제안자의 답변</b>입니다.</p>"
    )
    for c in engine.CRITERIA:
        parts.append(f"<h2>{engine.CRITERIA_KO[c]}</h2>")
        parts.append(checklist_table(c))
        parts.append(
            f"<p class='subtotal'>{engine.CRITERIA_KO[c]} 충족 개수: ______ / 10</p>"
        )

    parts.append(f"<div class='pagebreak'></div><h1>세션 {tag} — 채점표 2: 종합판단 (전체 인상)</h1>")
    parts.append(
        "<p class='note'>이번에는 체크리스트를 잊고, 숙련된 심사위원으로서 <b>전체적 인상</b>으로 "
        "채점하십시오 — 답변의 논리적 흐름, 태도의 진정성, 논증 전체의 설득력을 통합해서 "
        "판단하되, 근거는 대화의 턴을 인용해 적으십시오. 약점의 솔직한 인정은 감점이 아니라 "
        "가점 요인입니다.</p>"
    )
    band_rows = "".join(f"<tr><td class='iid'>{b}</td><td>{esc(d)}</td></tr>" for b, d in BANDS)
    parts.append(f"<table class='cl bands'><tr><th style='width:12%'>점수 밴드</th><th>기준</th></tr>{band_rows}</table>")
    for c in engine.CRITERIA:
        parts.append(
            f"<div class='holistic'><h2>{engine.CRITERIA_KO[c]} &nbsp;&nbsp; "
            f"점수: ________ / 10</h2>"
            "<div class='writeline'></div><div class='writeline'></div>"
            "<div class='writeline'></div></div>"
        )
    return "\n".join(parts)


def build(records, holistic_only=False):
    style = """
    @page { size: A4; margin: 18mm 16mm; }
    body { font-family: "Batang", "Noto Serif KR", serif; color: #000;
           font-size: 10.5pt; line-height: 1.55; max-width: 180mm; margin: 0 auto; }
    h1 { font-size: 14pt; border-bottom: 2px solid #000; padding-bottom: 4px; }
    h2 { font-size: 12pt; margin: 14px 0 6px; }
    .pagebreak { page-break-before: always; }
    .cover { text-align: center; margin-top: 40mm; }
    .cover h1 { border: 0; font-size: 20pt; }
    .field { margin: 10px auto; width: 70%; text-align: left; }
    .field span { display: inline-block; width: 30%; }
    .fill { display: inline-block; border-bottom: 1px solid #000; width: 60%; height: 1.2em; }
    .inst { text-align: left; margin: 18mm auto 0; width: 90%; font-size: 10pt; }
    .inst li { margin-bottom: 6px; }
    .ideabox { border: 1.5px solid #000; padding: 8px 12px; margin: 10px 0; }
    .turn { margin: 7px 0; padding: 5px 9px; border: 0.5px solid #999; }
    .turn.q { background: #f0f0f0; }
    .turn-head { display: block; font-weight: bold; font-size: 9pt; }
    table.cl { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
    table.cl th, table.cl td { border: 0.5px solid #000; padding: 4px 6px;
                               vertical-align: top; text-align: left; }
    table.cl th { background: #e8e8e8; }
    .iid { text-align: center; font-weight: bold; }
    .chk { white-space: nowrap; }
    .desc { font-size: 8.5pt; color: #333; }
    .evid { min-height: 3em; }
    .subtotal { text-align: right; font-weight: bold; margin: 6px 0 16px; }
    .note { font-size: 9.5pt; border-left: 3px solid #000; padding-left: 8px; }
    .bands td, .bands th { font-size: 9pt; }
    .holistic { margin: 12px 0 20px; page-break-inside: avoid; }
    .writeline { border-bottom: 0.5px solid #555; height: 1.9em; }
    """
    tags = [chr(ord("A") + i) for i in range(len(records))]
    n, tag_str = len(records), "세션 " + ", ".join(tags)
    cover = f"""
    <div class="cover">
      <h1>아이디어 평가 세션 — 인간 심사위원 채점표</h1>
      <p>소크라테스 문답 기반 평가 시스템 검증 실험</p>
      <div class="field"><span>심사위원 성명</span><span class="fill"></span></div>
      <div class="field"><span>소속</span><span class="fill"></span></div>
      <div class="field"><span>일자</span><span class="fill"></span></div>
      <div class="inst">
        <h2>심사 지침</h2>
        <ol>
          <li>이 채점표에는 서로 다른 아이디어 평가 세션 <b>{n}개({tag_str})</b>의
              대화 전문이 실려 있습니다. 각 세션은 제안자가 아이디어를 제출하고
              12개의 질문에 답한 기록입니다.</li>
          <li>채점 대상은 아이디어 자체가 아니라 <b>제안자가 질문에 얼마나 잘
              답했는가</b> — 방어의 성실성과 논리적 견고함 — 입니다.</li>
          <li>세션마다 <b>① 대화 전문 통독 → ② 채점표 기입</b> 순서로
              진행하십시오. 한 세션을 끝낸 뒤 다음 세션으로 넘어가십시오.</li>
          <li>다른 심사위원과 상의하지 마십시오.</li>
          <li>동일한 대화에 대한 AI의 채점 결과가 존재하지만 <b>비공개</b>입니다.
              모든 심사위원의 채점이 끝난 뒤 대조합니다.</li>
        </ol>
      </div>
    </div>
    """
    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        "<title>인간 심사위원 채점표</title>"
        f"<style>{style}</style></head><body>"
        + cover
        + "".join(session_html(t, r, holistic_only) for t, r in zip(tags, records))
        + "</body></html>"
    )


def main():
    parser = argparse.ArgumentParser(description="인간 심사위원 채점표 생성")
    parser.add_argument("--sessions", nargs="+", required=True,
                        help="세션 순서대로 시행 JSON 경로들 (A, B, C, ...)")
    parser.add_argument("-o", "--out", default="simulation/judge_sheet.html")
    parser.add_argument("--holistic-only", action="store_true",
                        help="체크리스트 없이 종합판단(감) 채점표만 생성")
    args = parser.parse_args()

    records = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.sessions]
    out = Path(args.out)
    out.write_text(build(records, args.holistic_only), encoding="utf-8")
    print(f"생성 완료: {out}")
    for i, r in enumerate(records):
        print(f"세션 {chr(ord('A')+i)} = 시행 {r['trial']} ({r['label']}) — AI 점수는 문서에 없음")


if __name__ == "__main__":
    main()
