"""로컬 KDI SQLite DB에서 정책 아이디어 후보 문헌을 찾는다.

`judge`는 판정까지 내리는 명령이고, 이 모듈은 그보다 앞단의 탐색 도구다.
DB에 들어온 문헌을 네트워크 없이 훑어 아이디어 축 용어가 어디서 걸렸는지
사람이 바로 볼 수 있게 만든다.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from .model import (Doc, FIELD_WEIGHT, Idea, TERM_WEIGHT, norm,
                    is_short_match_term, is_usable_match_term)

DESIGN_TERM_WEIGHT = 0.4


@dataclass(frozen=True)
class SearchTerm:
    text: str
    label: str
    weight: float = 1.0


@dataclass
class SearchHit:
    doc: Doc
    score: float
    matched: dict[str, list[str]] = field(default_factory=dict)
    snippet: str = ""


@dataclass
class CandidateSelection:
    """빠른 색인이 정밀 판정기로 넘길 문헌 묶음."""
    docs: list[Doc]
    candidate_count: int
    multi_axis_count: int
    truncated: bool = False


@dataclass
class _IndexedDoc:
    doc: Doc
    fields: dict[str, str]


class CorpusIndex:
    """서버 시작 때 한 번 정규화해 반복 전수 정밀 판정을 피한다."""

    def __init__(self, corpus: list[Doc]):
        self.corpus = corpus
        self.entries = [
            _IndexedDoc(doc, {name: norm(text) for name, text in doc.fields().items()})
            for doc in corpus
        ]

    def candidates(self, idea: Idea, max_precise: int = 600,
                   single_axis_limit: int = 120) -> CandidateSelection:
        axes = {
            axis.name: [(norm(text), weight) for text, _kind, weight in axis.terms()]
            for axis in idea.axes
        }
        ranked: list[tuple[int, float, int, Doc]] = []
        for pos, entry in enumerate(self.entries):
            axis_count = 0
            score = 0.0
            for terms in axes.values():
                best = 0.0
                for nterm, weight in terms:
                    if not nterm:
                        continue
                    for field, ntext in entry.fields.items():
                        if nterm in ntext:
                            best = max(best, FIELD_WEIGHT[field] * weight)
                if best:
                    axis_count += 1
                    score += best
            if axis_count:
                ranked.append((axis_count, score, pos, entry.doc))

        ranked.sort(key=lambda row: (-row[0], -row[1], row[3].date, row[3].title))
        multi = [row for row in ranked if row[0] >= 2]
        single = [row for row in ranked if row[0] == 1][:single_axis_limit]
        chosen = multi + single

        known = [norm(value) for value in idea.known_positives if norm(value)]
        if known:
            selected_positions = {row[2] for row in chosen}
            for pos, entry in enumerate(self.entries):
                key = norm(f"{entry.doc.title} {entry.doc.doc_id} {entry.doc.url}")
                if pos not in selected_positions and any(value in key for value in known):
                    chosen.append((3, float("inf"), pos, entry.doc))
                    selected_positions.add(pos)

        chosen.sort(key=lambda row: (-row[0], -row[1], row[3].date, row[3].title))
        truncated = len(chosen) > max_precise
        chosen = chosen[:max_precise]
        return CandidateSelection(
            docs=[row[3] for row in chosen],
            candidate_count=len(ranked),
            multi_axis_count=len(multi),
            truncated=truncated,
        )

    def search(self, terms: list[SearchTerm], limit: int = 20) -> list[SearchHit]:
        hits: list[SearchHit] = []
        terms = [t for t in _dedupe_terms(terms) if is_usable_match_term(t.text)]
        normalized = [(term, norm(term.text)) for term in terms]
        for entry in self.entries:
            matched: dict[str, list[str]] = {}
            score = 0.0
            best_snippet = ""
            raw_fields = entry.doc.fields()
            for field, ntext in entry.fields.items():
                if not ntext:
                    continue
                for term, nterm in normalized:
                    if nterm not in ntext:
                        continue
                    matched.setdefault(field, []).append(f"{term.text}({term.label})")
                    score += FIELD_WEIGHT[field] * term.weight
                    if not best_snippet:
                        best_snippet = _snippet(raw_fields[field], term.text)
            if score:
                hits.append(SearchHit(entry.doc, round(score, 2), matched, best_snippet))
        hits.sort(key=lambda h: (-h.score, h.doc.date, h.doc.title))
        return hits[:limit]


def terms_from_idea(idea: Idea) -> list[SearchTerm]:
    """축 정의 파일에서 검색어 목록을 만든다.

    축 용어는 판정과 같은 exact/syn/broad 가중치를 쓰고, 재원·전달체계는
    판정축은 아니지만 탐색 힌트로 약하게 더한다.
    """
    out: list[SearchTerm] = []
    for ax in idea.axes:
        for text, kind, weight in ax.terms():
            out.append(SearchTerm(text, f"{ax.name}.{kind}", weight))
    for text in idea.financing:
        if is_usable_match_term(text):
            weight = DESIGN_TERM_WEIGHT * (0.25 if is_short_match_term(text) else 1.0)
            out.append(SearchTerm(text, "재원", weight))
    for text in idea.delivery:
        if is_usable_match_term(text):
            weight = DESIGN_TERM_WEIGHT * (0.25 if is_short_match_term(text) else 1.0)
            out.append(SearchTerm(text, "전달체계", weight))
    for name, values in idea.claims.items():
        for text in values:
            if is_usable_match_term(text):
                out.append(SearchTerm(text, name, 0.55))
    return _dedupe_terms(out)


def terms_from_query(query: str) -> list[SearchTerm]:
    """간단한 자유문 검색어를 만든다.

    한국어 형태소 분석에 의존하지 않고 공백·쉼표 단위로 자른다. 조사까지
    완벽히 제거하려는 순간 정밀도가 흔들리므로, 자유문은 빠른 탐색용으로만
    두고 정식 검증은 아이디어 JSON을 쓰게 한다.
    """
    raw = re.split(r"[\s,;/]+", query or "")
    return _dedupe_terms(
        [SearchTerm(_strip_particle(t), "query", TERM_WEIGHT["exact"]) for t in raw
         if is_usable_match_term(_strip_particle(t))]
    )


def search_docs(corpus: list[Doc], terms: list[SearchTerm],
                limit: int = 20) -> list[SearchHit]:
    """문헌 필드별 가중치를 반영해 후보를 점수순으로 반환한다."""
    return CorpusIndex(corpus).search(terms, limit)

def format_hits(hits: list[SearchHit], total: int) -> str:
    lines = [f"검색 결과 {len(hits)}건 / 코퍼스 {total}건", ""]
    for i, hit in enumerate(hits, 1):
        doc = hit.doc
        lines.append(f"{i}. [{hit.score:g}] {doc.title}")
        lines.append(f"   {doc.kind or doc.source} {doc.year()} {doc.url}".rstrip())
        fields = ", ".join(
            f"{field}: {'/'.join(terms[:5])}" for field, terms in hit.matched.items()
        )
        lines.append(f"   매칭 {fields}")
        if hit.snippet:
            lines.append(f"   > {hit.snippet}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _dedupe_terms(terms: list[SearchTerm]) -> list[SearchTerm]:
    out: dict[str, SearchTerm] = {}
    for term in terms:
        key = norm(term.text)
        if not key:
            continue
        prev = out.get(key)
        if prev is None or term.weight > prev.weight:
            out[key] = term
    return list(out.values())


def _strip_particle(token: str) -> str:
    token = token.strip()
    for suffix in ("에게", "에서", "으로", "로", "을", "를", "은", "는", "이", "가", "에"):
        if len(token) > len(suffix) + 1 and token.endswith(suffix):
            return token[:-len(suffix)]
    return token


def _snippet(text: str, term: str, radius: int = 80) -> str:
    nterm = norm(term)
    if not text or not nterm:
        return ""
    for m in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
        start, end = max(0, m.start() - radius), min(len(text), m.end() + radius)
        return text[start:end].strip()
    return text[:radius * 2].strip()

