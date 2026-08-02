"""판정 결과 출력. 근거 문장을 반드시 함께 보인다.

판정은 사람이 뒤집을 수 있어야 한다. 그러려면 왜 그렇게 판정했는지의
증거 문장이 눈앞에 있어야 한다. 점수만 보여주는 출력은 검증 불가능하다.
"""
from __future__ import annotations
from .verdict import Assessment, Recall, CODES, ROLES

BADGE = {"aligned": "정렬", "reversed": "역전", "unclear": "불명"}
ARROW = {"aligned": "→", "reversed": "↔", "unclear": "?"}


def to_markdown(idea_text: str, assessments: list[Assessment],
                recall: Recall, summary: dict) -> str:
    L = [f"# 정책 신규성 검증: {idea_text}", ""]
    L += [f"- 코퍼스 {summary['n_corpus']:,}건 대조 · 중첩 후보 {summary['n_flagged']}건",
          f"- 재현율 통제 **{recall.rate:.0%}** "
          f"({len(recall.found)}/{len(recall.expected)})"
          + ("" if recall.ok else f" — 누락: {recall.missed}"),
          f"- **판정 {summary['overall']}** — {summary['message']}", ""]
    if summary["overall"] == "VOID":
        L += ["> 재현율이 1.0이 아닙니다. 아래는 참고용이며 신규성 결론의 "
              "근거로 쓸 수 없습니다. 코퍼스 확보 단계를 먼저 점검하십시오.", ""]
    d = ", ".join(f"{k} {v}건" for k, v in summary["by_code"].items() if v)
    r = ", ".join(f"{k} {v}건" for k, v in summary["by_role"].items() if v)
    L += [f"- 중첩도 분포: {d or '없음'}", f"- 역할 분포: {r or '없음'}", ""]

    for role in ("실행", "경합", "근거", "선례"):
        grp = [a for a in assessments if a.flagged and a.role == role]
        if not grp:
            continue
        L += [f"## {role} — {ROLES[role]}", ""]
        for a in sorted(grp, key=lambda x: (x.code, -x.score)):
            doc = a.doc
            L += [f"### [{a.code}] {doc.title}",
                  f"`{doc.kind or doc.source}` {doc.year()} · 점수 {a.score} · "
                  f"축 {'/'.join(f'{k}@{v}' for k, v in a.axes_at.items()) or '없음'}"]
            if a.direction:
                L.append(f"방향 {ARROW[a.direction.verdict]} "
                         f"{BADGE[a.direction.verdict]}"
                         + (f" (규칙 {a.direction.rule})" if a.direction.rule else "")
                         + f" — {a.direction.reason}")
            if a.window:
                L += ["", f"> {a.window.text.strip()[:400]}"]
            for n in a.notes:
                L.append(f"- {n}")
            if doc.url:
                L.append(f"- <{doc.url}>")
            L.append("")
    return "\n".join(L)


def to_console(assessments: list[Assessment], summary: dict) -> str:
    L = [f"코퍼스 {summary['n_corpus']}건 · 후보 {summary['n_flagged']}건 "
         f"· 재현율 {summary['recall']:.0%}", ""]
    for a in sorted([x for x in assessments if x.flagged],
                    key=lambda x: (x.code, -x.score)):
        dr = ARROW[a.direction.verdict] if a.direction else " "
        L.append(f"[{a.code}/{a.role}] {a.score:>5} {dr} {a.doc.title[:52]}")
        L.append(f"          축 {'/'.join(f'{k}@{v}' for k, v in a.axes_at.items())}")
        for n in a.notes[:2]:
            L.append(f"          · {n}")
    L.append(f"\n=> {summary['overall']}: {summary['message']}")
    return "\n".join(L)
