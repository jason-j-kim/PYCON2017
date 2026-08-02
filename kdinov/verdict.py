"""판정.

출력은 두 축이다. 한 축으로는 부족하다는 것이 1차 실행에서 드러났다.

  code — 중첩의 정도 (N0 동일 … N4 무관). 신규성 주장의 위협 크기.
  role — 이 문헌을 어떻게 쓸 것인가.
           경합  이미 같은 수단을 제안함 → 차별화 논증 대상
           근거  효과분석만 있고 수단 제안 없음 → 인용해서 정당화에 씀
           선례  영역은 다르나 설계(재원·전달체계)의 참조 사례
           무관

'수단축이 비었다'는 사실이 N1(경합)과 N3(근거) 중 어느 쪽인지는
축 매칭만으로 알 수 없다. 그 문헌이 다른 수단을 제안하는지를 따로
봐야 한다. 이것이 instrument_profile의 존재 이유다.

핵심 원칙: '아무것도 안 걸렸다'는 결론은 재현율이 증명되기 전까지 무효다.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from .model import Doc, Idea, norm, FIELD_WEIGHT, TERM_WEIGHT
from .score import (coverage, windows, direction_agg, instrument_profile,
                    AxisHit, Direction, Window)

CODES = {
    "N0": "동일 — 3축이 한 자리에서 일치. 신규 아님",
    "N1": "부분중첩 — 축 하나가 상이하거나 흩어져 있음",
    "N2": "주변 — 축 하나만 강하게 겹침",
    "N3": "인접 — 영역만 중첩",
    "N4": "무관",
}
ENACTED_KINDS = ("정책자료", "법령", "시행령", "입법예고", "보도자료",
                 "고시", "훈령", "업무계획", "대책")
ROLES = {
    "실행": "이미 제도화·집행 단계 — 신규성의 직접 반증",
    "경합": "같은 수단을 이미 제안 — 차별화 논증 필요",
    "근거": "효과분석·현황진단으로 수단 제안 없음 — 인용 가능",
    "선례": "영역은 다르나 설계 참조 가능",
    "무관": "",
}
COOCCUR_BONUS = 1.6


@dataclass
class Assessment:
    doc: Doc
    code: str
    role: str
    score: float                       # 0~100 정규화
    hits: dict[str, AxisHit]
    window: Window | None
    direction: Direction | None
    instruments: dict = field(default_factory=dict)
    design: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def axes_at(self) -> dict[str, str]:
        return {a: h.best_field for a, h in self.hits.items()}

    @property
    def flagged(self) -> bool:
        return self.code != "N4"


def _normalize(raw: float, n_axes: int) -> float:
    ceiling = n_axes * FIELD_WEIGHT["title"] * TERM_WEIGHT["exact"] * COOCCUR_BONUS
    return round(min(100.0, 100.0 * raw / ceiling), 1)


def assess(doc: Doc, idea: Idea) -> Assessment:
    hits = coverage(doc, idea)
    wins = windows(doc, idea)
    win = wins[0] if wins else None
    # 제목의 명시적 역전 표현(AI 기반 정부 등)은 2축 공기창이 없어도 강한 신호다.
    title_direction = direction_agg([Window(doc.title, "title", set())], idea)
    dr = title_direction if title_direction and title_direction.verdict == "reversed" else direction_agg(wins, idea)
    prof = instrument_profile(doc, idea)
    notes: list[str] = []

    n_axes = len(idea.axes)
    raw = sum(h.score for h in hits.values())

    if win and len(win.axes) == n_axes:
        raw *= COOCCUR_BONUS
        notes.append(f"{n_axes}축이 한 단위에서 공기 ({win.where})")
    elif win:
        raw *= 1.2
    elif len(hits) >= 2:
        notes.append("축이 서로 다른 위치에 흩어져 있음 — 우연 공출현 가능")

    if dr:
        raw *= (1.0 - dr.penalty)

    covered = set(hits)
    missing = set(idea.axis_names) - covered
    title_axes = {a for a, h in hits.items() if h.best_field == "title"}
    strong = {a for a, h in hits.items() if h.kind in ("exact", "syn")}

    # ---- code: 중첩의 정도
    if dr and dr.verdict == "reversed":
        code = "N3" if "영역" in covered else "N4"
        notes.append(f"정책 벡터 역전({dr.rule}): {dr.reason}")
        notes.append("역전이므로 동일정책으로 보지 않고 인접으로 강등")
    elif not missing and (len(title_axes) == n_axes or
                          (win and len(win.axes) == n_axes)):
        code = "N0"
    elif not missing:
        code = "N1"
        notes.append("3축이 모두 존재하나 한 단위에서 만나지 않음 — 본문 확인 필요")
    elif len(missing) == 1:
        code = "N1" if len(strong) >= 2 else "N2"
    elif covered and "영역" in covered:
        code = "N3"
    elif len(covered) == 1:
        code = "N2" if next(iter(covered)) != "영역" else "N3"
    else:
        code = "N4"

    # ---- role: 어떻게 쓸 것인가
    allfields = norm(" ".join(doc.fields().values()))
    fin = [t for t in idea.financing if norm(t) and norm(t) in allfields]
    dlv = [t for t in idea.delivery if norm(t) and norm(t) in allfields]
    design = {
        "specified": len(idea.financing) + len(idea.delivery),
        "matched": len(fin) + len(dlv),
        "financing": fin,
        "delivery": dlv,
    }
    same_instrument = "수단" in covered
    is_enacted = any(k in (doc.kind or "") for k in ENACTED_KINDS)

    if code == "N4":
        role = "무관"
    elif is_enacted and code in ("N0", "N1"):
        # 법령·시행령·보도자료는 '논의'가 아니라 '집행'이다.
        # 신규성 검증에서 가장 강한 반증이므로 별도 등급으로 분리한다.
        role = "실행"
        notes.append("연구문헌이 아니라 집행문서 — 이미 제도화 단계")
    elif "영역" in missing:
        if fin or dlv:
            role = "선례"
            notes.append("영역이 다름 — 재원·전달체계 설계의 참조로 활용")
        else:
            role, code = "무관", "N4"
            notes.append("영역축 불일치 + 설계 참조점 없음 — 무관으로 강등")
    elif dr and dr.verdict == "reversed":
        role = "근거"
    elif same_instrument and prof["proposes"]:
        role = "경합"
    elif prof["other"] and "수단" in missing and len(covered) >= 2:
        role = "경합"
        notes.append("다른 수단을 제안: " + ", ".join(prof["other"][:6]))
    else:
        role = "근거"

    if role == "근거" and code in ("N1", "N2", "N3"):
        notes.append("수단 제안이 없거나 약함 — 신규성 유지하며 인용 가능")

    if fin:
        notes.append("재원 언급: " + ", ".join(fin))
    if dlv:
        notes.append("전달체계 언급: " + ", ".join(dlv))
    if code in ("N0", "N1") and not fin and not dlv:
        notes.append("재원·전달체계 미언급 → 설계 파라미터에 신규성 여지")

    return Assessment(
        doc=doc, code=code, role=role, score=_normalize(raw, n_axes),
        hits=hits, window=win, direction=dr, instruments=prof,
        design=design, notes=notes,
    )


# --------------------------------------------------------------------------
# 재현율 통제
# --------------------------------------------------------------------------
@dataclass
class Recall:
    expected: list[str]
    found: list[str]

    @property
    def missed(self) -> list[str]:
        return [e for e in self.expected if e not in self.found]

    @property
    def rate(self) -> float:
        return 1.0 if not self.expected else len(self.found) / len(self.expected)

    @property
    def ok(self) -> bool:
        return not self.missed


def check_recall(corpus: list[Doc], idea: Idea,
                 assessments: list[Assessment] | None = None) -> Recall:
    """known_positives가 (1) 코퍼스에 있고 (2) N4로 버려지지 않았는지 확인.

    두 단계를 모두 봐야 한다. 코퍼스에는 있는데 채점 규칙이 N4로 떨어뜨리면
    사람 눈에는 보이지 않으므로 재현 실패와 다를 바 없다.
    """
    def key(d: Doc) -> str:
        return norm(f"{d.title} {d.doc_id} {d.url}")

    in_corpus = {e: any(norm(e) in key(d) for d in corpus)
                 for e in idea.known_positives}
    surfaced = in_corpus
    if assessments is not None:
        kept = [a for a in assessments if a.flagged]
        surfaced = {e: in_corpus[e] and any(norm(e) in key(a.doc) for a in kept)
                    for e in idea.known_positives}
    return Recall(list(idea.known_positives),
                  [e for e, ok in surfaced.items() if ok])


def substantive_novelty(assessments: list[Assessment], recall: Recall,
                         idea: Idea | None = None,
                         truncated: bool = False) -> dict:
    """언급량과 별도로 실질 설계의 독창성을 판정한다."""
    kept = [a for a in assessments if a.flagged]
    direct = [a for a in kept if a.code in ("N0", "N1")]
    enacted = [a for a in direct if a.role == "실행"]
    competing = [a for a in direct if a.role == "경합"]
    specified = sum(len(values) for values in (idea.financing, idea.delivery)) if idea else 0
    required_design_matches = 1 if specified <= 1 else 2
    design_overlap = [
        a for a in direct if a.design.get("matched", 0) >= required_design_matches
    ]

    if not recall.ok:
        level, score = "판단 보류", None
        message = "확인 문헌 재현에 실패해 실질 독창성을 결론 낼 수 없습니다."
    elif truncated:
        level, score = "판단 보류", None
        message = "정밀 후보가 안전 상한을 넘어 일부만 판정했습니다. exact 축을 좁혀야 합니다."
    elif direct and specified and not design_overlap:
        level, score = "차별화 가능", 72
        caution = " 기존 집행문서와의 차이를 원문에서 확인해야 합니다." if enacted else ""
        message = (f"유사 주제 문헌은 {len(direct)}건이지만 입력한 재원·전달체계와 직접 "
                   f"겹치는 문헌은 없습니다. 언급량과 별개로 설계 차별성이 남습니다.{caution}")
    elif enacted:
        level, score = "낮음", 10
        message = f"직접 중첩 집행문서 {len(enacted)}건이 있어 이미 제도화된 내용입니다."
    elif competing and design_overlap:
        level, score = "낮음", 25
        message = f"같은 수단과 설계 파라미터까지 겹치는 경합 문헌 {len(design_overlap)}건이 있습니다."
    elif direct and not specified:
        level, score = "판단 보류", None
        message = (f"직접 유사 문헌 {len(direct)}건이 있습니다. 실질적으로 새로운지를 가리려면 "
                   "재원 또는 전달체계를 입력해야 합니다.")
    elif direct:
        level, score = "차별화 검토", 55
        message = "직접 유사 문헌과 일부 설계 중첩이 있어 차이점을 문헌별로 확인해야 합니다."
    else:
        level, score = "높음", 90
        message = "빠른 후보에서는 언급이 있어도 동일 대상·수단·영역의 직접 중첩은 확인되지 않았습니다."

    return {
        "level": level,
        "score": score,
        "message": message,
        "directDocuments": len(direct),
        "designSpecified": specified,
        "designOverlapDocuments": len(design_overlap),
    }


FINANCING_CATALOG = {
    "공공투자", "국비", "지방비", "보조금", "바우처", "기금", "펀드",
    "융자", "대출", "세액공제", "공공조달", "민관협력", "자부담", "목적세",
}
DELIVERY_CATALOG = {
    "직접공급", "위탁", "바우처", "플랫폼", "센터", "클러스터", "공공조달",
    "지역 단위", "도시 단위", "온라인", "모듈", "패키지", "인증", "의무화",
}
RELATION_PRIORITY = {"동일": 4, "부분 동일": 3, "명시적 차이": 2,
                     "미언급": 1, "확인 불가": 0, "미지정": -1}


def evidence_grade(doc: Doc) -> dict:
    fields = doc.fields()
    summary_len = len(fields.get("summary", ""))
    toc_len = len(fields.get("toc", ""))
    combined = sum(len(value) for value in fields.values())
    if summary_len >= 500:
        grade, label = "A", "충분한 요약"
    elif summary_len >= 100:
        grade, label = "B", "부분 요약"
    elif toc_len >= 300:
        grade, label = "C", "목차 중심"
    else:
        grade, label = "D", "제한된 텍스트"
    return {"grade": grade, "label": label, "summaryChars": summary_len,
            "tocChars": toc_len, "combinedChars": combined}


def _all_text(doc: Doc) -> str:
    return norm(" ".join(doc.fields().values()))


def _design_relation(doc: Doc, specified: list[str], matched: list[str],
                     catalog: set[str]) -> dict:
    if not specified:
        return {"status": "미지정", "matched": [], "alternatives": []}
    if matched:
        status = "동일" if len(matched) == len(specified) else "부분 동일"
        return {"status": status, "matched": matched, "alternatives": []}
    text = _all_text(doc)
    mine = {norm(value) for value in specified if norm(value)}
    alternatives = sorted(
        value for value in catalog
        if norm(value) in text and not any(
            n in norm(value) or norm(value) in n for n in mine
        )
    )
    if alternatives:
        return {"status": "명시적 차이", "matched": [],
                "alternatives": alternatives[:5]}
    return {"status": "미언급", "matched": [], "alternatives": []}


def atomic_relations(a: Assessment, idea: Idea) -> dict[str, dict]:
    relations: dict[str, dict] = {}
    for axis in idea.axes:
        hit = a.hits.get(axis.name)
        if hit:
            status = "동일" if hit.kind in ("exact", "syn") else "부분 동일"
            relations[axis.name] = {
                "status": status, "matched": [hit.term],
                "where": hit.best_field,
            }
        elif axis.name == "수단" and a.instruments.get("other") and len(a.hits) >= 2:
            relations[axis.name] = {
                "status": "명시적 차이", "matched": [],
                "alternatives": a.instruments.get("other", [])[:5],
            }
        else:
            relations[axis.name] = {"status": "미언급", "matched": []}

    relations["재원"] = _design_relation(
        a.doc, idea.financing, a.design.get("financing", []), FINANCING_CATALOG)
    relations["전달체계"] = _design_relation(
        a.doc, idea.delivery, a.design.get("delivery", []), DELIVERY_CATALOG)

    text = _all_text(a.doc)
    for name, values in idea.claims.items():
        usable = [value for value in values if norm(value)]
        if not usable:
            relations[name] = {"status": "미지정", "matched": []}
            continue
        matched = [value for value in usable if norm(value) in text]
        relations[name] = {
            "status": "동일" if len(matched) == len(usable) else
                      ("부분 동일" if matched else "미언급"),
            "matched": matched,
        }
    return relations


def policy_package_key(doc: Doc) -> str:
    title = re.sub(r"(?:19|20)\d{2}(?:\s*[~\-]\s*(?:19|20)?\d{2})?", "", doc.title or "")
    title = re.sub(r"[<「『\[].*?[>」』\]]", "", title)
    title = re.split(r"\s*[:：]\s*", title, maxsplit=1)[0]
    title = re.sub(r"제?\s*\d+\s*(?:권|호|차|편)", "", title)
    key = norm(title)
    return key or norm(doc.doc_id) or "UNKNOWN"


def build_policy_packages(assessments: list[Assessment], idea: Idea) -> list[dict]:
    grouped: dict[str, list[Assessment]] = {}
    for assessment in assessments:
        if assessment.flagged:
            grouped.setdefault(policy_package_key(assessment.doc), []).append(assessment)

    packages: list[dict] = []
    for key, members in grouped.items():
        combined: dict[str, dict] = {}
        for member in members:
            for name, relation in atomic_relations(member, idea).items():
                previous = combined.get(name)
                if previous is None or RELATION_PRIORITY[relation["status"]] > RELATION_PRIORITY[previous["status"]]:
                    combined[name] = relation
        packages.append({
            "packageId": key[:80],
            "title": members[0].doc.title,
            "documents": len(members),
            "years": sorted({m.doc.year() for m in members if m.doc.year()}),
            "relations": combined,
            "score": max(m.score for m in members),
            "roles": sorted({m.role for m in members}),
        })
    packages.sort(key=lambda p: (-p["score"], p["title"]))
    return packages


def _specified_dimensions(idea: Idea) -> tuple[list[str], list[str]]:
    core = [axis.name for axis in idea.axes if axis.terms()]
    essential = list(core)
    if idea.financing:
        essential.append("재원")
    if idea.delivery:
        essential.append("전달체계")
    return core, essential


def refined_decision(assessments: list[Assessment], recall: Recall, idea: Idea,
                     candidate_count: int, truncated: bool) -> tuple[dict, list[dict]]:
    packages = build_policy_packages(assessments, idea)
    core, essential = _specified_dimensions(idea)

    def covered(package, names):
        return {name for name in names
                if package["relations"].get(name, {}).get("status") in ("동일", "부분 동일")}

    core_coverages = [(package, covered(package, core)) for package in packages]
    essential_coverages = [(package, covered(package, essential)) for package in packages]
    full_essential = [package for package, got in essential_coverages if set(essential) <= got]
    full_core = [package for package, got in core_coverages if set(core) <= got]
    union_core = set().union(*(got for _package, got in core_coverages)) if core_coverages else set()

    if full_essential and essential:
        overlap = {"code": "O0", "label": "동일 설계 확인",
                   "message": "한 정책 패키지에서 지정된 핵심 설계가 함께 확인됐습니다."}
    elif full_core:
        overlap = {"code": "O1", "label": "핵심 구조 중첩",
                   "message": "대상·수단·영역은 한 정책 패키지에서 겹치지만 세부 설계는 완전히 확인되지 않았습니다."}
    elif core and set(core) <= union_core:
        overlap = {"code": "O2", "label": "구성요소 분산",
                   "message": "핵심 구성요소는 여러 정책 패키지에 나뉘어 있으나 동일 결합은 확인되지 않았습니다."}
    elif packages or candidate_count:
        overlap = {"code": "O3", "label": "관련 문헌만 확인",
                   "message": "문제·분야 또는 일부 수단만 관련된 문헌이 확인됐습니다."}
    else:
        overlap = {"code": "O4", "label": "관련 선행정책 미확인",
                   "message": "현재 검색 범위에서 관련 후보를 확인하지 못했습니다."}

    close = [package for package, got in core_coverages if len(got) >= min(2, len(core))]
    differences = []
    unresolved = []
    for package in close:
        for name in essential:
            status = package["relations"].get(name, {}).get("status")
            if status == "명시적 차이":
                differences.append((package["title"], name))
            elif status in ("미언급", "확인 불가"):
                unresolved.append((package["title"], name))
    if differences:
        material = {"code": "M1", "label": "본질적 차이 관찰",
                    "message": f"가까운 정책 패키지에서 다른 수단·재원·전달체계 {len(differences)}개를 확인했습니다.",
                    "observed": len(differences), "unresolved": len(unresolved)}
    elif unresolved:
        material = {"code": "M3", "label": "차이 확인 불가",
                    "message": "가까운 문헌에 세부 설계가 미언급되어 차이를 독창성 근거로 사용할 수 없습니다.",
                    "observed": 0, "unresolved": len(unresolved)}
    else:
        material = {"code": "M2", "label": "본질적 차이 미확인",
                    "message": "현재 텍스트에서는 본질적인 설계 차이가 명시적으로 확인되지 않았습니다.",
                    "observed": 0, "unresolved": 0}

    if overlap["code"] == "O0":
        combination = {"code": "C0", "label": "동일 결합 존재",
                       "message": "지정된 구성요소가 한 정책 패키지에 함께 존재합니다."}
    elif overlap["code"] == "O2":
        combination = {"code": "C1", "label": "새로운 결합 가능성",
                       "message": "개별 구성요소는 알려졌지만 동일한 결합 구조는 확인되지 않았습니다."}
    elif overlap["code"] == "O1":
        combination = {"code": "C2", "label": "결합 차이 검토 필요",
                       "message": "핵심 구조가 유사하므로 원문에서 결합 방식의 차이를 확인해야 합니다."}
    else:
        combination = {"code": "C3", "label": "결합 판단 근거 부족",
                       "message": "비교 가능한 핵심 구성요소가 충분하지 않습니다."}

    relevant = sorted((a for a in assessments if a.flagged), key=lambda a: -a.score)[:10]
    grades = [evidence_grade(a.doc)["grade"] for a in relevant]
    strong = sum(grade in ("A", "B") for grade in grades)
    if not recall.ok or truncated:
        confidence = {"code": "E3", "label": "판단 보류",
                      "message": "재현율 또는 후보 범위가 충분하지 않습니다."}
    elif grades and "A" in grades and strong / len(grades) >= 0.6:
        confidence = {"code": "E1", "label": "요약·목차 근거 충분",
                      "message": "상위 후보 다수에 비교 가능한 요약 또는 목차가 있습니다. 원문 확인 전 잠정판정입니다."}
    elif grades:
        confidence = {"code": "E2", "label": "제한된 텍스트",
                      "message": "상위 후보의 일부가 제목·목차 중심이므로 확정판정할 수 없습니다."}
    else:
        confidence = {"code": "E3", "label": "판단 보류",
                      "message": "비교 가능한 근거 문헌이 부족합니다."}

    decision = {
        "scope": "KDI 수록자료",
        "overlap": overlap,
        "materialDifference": material,
        "combination": combination,
        "confidence": confidence,
        "conclusion": (
            f"{overlap['code']} {overlap['label']} · {combination['label']} · "
            f"증거 {confidence['code']}. KDI 수록자료 범위의 잠정판정입니다."
        ),
        "warning": "미언급은 차이로 인정하지 않았으며, 원문이 없는 경우 독창성을 확정하지 않습니다.",
    }
    return decision, packages


def summarize(assessments: list[Assessment], recall: Recall,
              n_corpus: int = 0, idea: Idea | None = None,
              candidate_count: int | None = None,
              precise_count: int | None = None,
              truncated: bool = False) -> dict:
    kept = [a for a in assessments if a.flagged]
    order = ["N0", "N1", "N2", "N3"]
    candidate_count = len(kept) if candidate_count is None else candidate_count
    if idea is None:
        decision = {
            "scope": "KDI 수록자료",
            "overlap": {"code": "O4", "label": "판정 정보 부족", "message": "아이디어 정보가 없습니다."},
            "materialDifference": {"code": "M3", "label": "차이 확인 불가", "message": "아이디어 정보가 없습니다."},
            "combination": {"code": "C3", "label": "결합 판단 근거 부족", "message": "아이디어 정보가 없습니다."},
            "confidence": {"code": "E3", "label": "판단 보류", "message": "아이디어 정보가 없습니다."},
            "conclusion": "판단 보류", "warning": "",
        }
        packages = []
    else:
        decision, packages = refined_decision(
            assessments, recall, idea, candidate_count, truncated)
    return {
        "overall": "VOID" if (not recall.ok or truncated) else decision["overlap"]["code"],
        "message": decision["conclusion"],
        "decision": decision,
        "packages": packages,
        "recall": recall.rate,
        "n_corpus": n_corpus, "n_flagged": len(kept),
        "candidate_count": candidate_count,
        "precise_count": len(assessments) if precise_count is None else precise_count,
        "truncated": truncated,
        "by_code": {c: sum(1 for a in kept if a.code == c) for c in order},
        "by_role": {r: sum(1 for a in kept if a.role == r)
                    for r in ("실행", "경합", "근거", "선례")},
    }