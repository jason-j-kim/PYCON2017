"""Rule-based decomposition of raw policy ideas into novelty-check axes.

The web app needs a useful first draft before a real KDI mirror exists. This
module deliberately stays offline: it extracts target, instrument, and domain
terms from the user's Korean policy text, then lets the same local search and
judgment pipeline run on the available corpus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from .model import norm

AXES = ("대상", "수단", "영역")
MAX_TERMS = {"exact": 6, "syn": 10, "broad": 8}

STOP_PHRASES = {
    "기존", "정책", "정책은", "새로운", "통한", "대한", "위한", "삼습니다",
    "구축", "육성", "개념", "국가", "정부", "공공", "지원", "방안", "대책",
    "체계", "통합체계", "시스템", "플랫폼", "글로벌", "시장", "최우선", "중심",
}

FINANCING_HINTS = [
    "무상", "전액지원", "보조금", "바우처", "세액공제", "공공조달", "공공투자",
    "민관협력", "R&D", "기금", "펀드", "목적세", "재정지원", "인센티브",
]

DELIVERY_HINTS = [
    "직접공급", "위탁", "플랫폼", "바우처", "패키지", "모듈", "표준", "인증",
    "지역 단위", "도시 단위", "클러스터", "센터", "원스톱", "데이터", "오프그리드",
]

TARGET_SUFFIXES = (
    "기업", "소상공인", "청년", "노인", "고령자", "예술인", "농가", "가구", "근로자",
    "지역", "도시", "권역", "산업", "인프라", "시설", "학교", "병원", "계층", "주민",
)
INSTRUMENT_SUFFIXES = (
    "지원", "육성", "표준화", "표준", "구축", "도입", "전환", "수출", "패키지",
    "모듈", "팩토리", "시스템", "플랫폼", "인증", "조달", "투자", "훈련", "교육",
)
DOMAIN_HINTS = (
    "기후", "재난", "안보", "공급망", "에너지", "식량", "수자원", "물", "교육", "보건",
    "문화", "예술", "복지", "주거", "교통", "노동", "환경", "산업정책", "디지털", "AI",
)


@dataclass(frozen=True)
class Concept:
    triggers: tuple[str, ...]
    axes: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)
    financing: tuple[str, ...] = ()
    delivery: tuple[str, ...] = ()
    note: str = ""


CONCEPTS: tuple[Concept, ...] = (
    Concept(
        triggers=("오프그리드", "생존 인프라", "survival infrastructure", "미니 팩토리", "물 식량 에너지"),
        axes={
            "대상": {
                "exact": ("분산형 생존 인프라", "생존 인프라"),
                "syn": ("필수 기능", "필수 인프라", "핵심기반시설", "재난 취약지역", "위기 대응 지역"),
                "broad": ("지역 자립", "도시 회복력", "필수 서비스", "기초 인프라"),
            },
            "수단": {
                "exact": ("오프그리드", "자립 모듈", "미니 팩토리", "초소형 모듈", "분산형 인프라"),
                "syn": ("마이크로그리드", "독립형 마이크로그리드", "분산에너지", "자립형 에너지", "물-에너지-식량", "모듈 표준화", "순환 시스템"),
                "broad": ("회복탄력성 산업", "재난안전 산업", "인프라 패키지", "공급망 회복력", "분산 시스템"),
            },
            "영역": {
                "exact": ("극한 기후", "지정학적 단절", "생존 경제", "재난 대비", "회복탄력성"),
                "syn": ("기후위기", "재난", "안보 경제", "공급망 단절", "필수 기능 붕괴", "에너지 안보", "식량 안보", "물 안보"),
                "broad": ("기후 적응", "경제안보", "에너지 안보", "식량 안보", "수자원", "재난 안전", "스마트시티"),
            },
        },
        financing=("재난안전 산업", "회복탄력성 수출", "공공조달", "공공투자", "민관협력", "R&D", "표준화"),
        delivery=("오프그리드", "모듈", "패키지", "미니 팩토리", "지역 단위", "도시 단위", "분산형"),
        note="생존 인프라/오프그리드 계열의 전용 확장어를 적용했습니다.",
    ),
    Concept(
        triggers=("AI", "인공지능", "디지털 전환", "디지털전환"),
        axes={
            "수단": {"syn": ("AI 기반", "인공지능 활용", "데이터 기반", "플랫폼")},
            "영역": {"exact": ("AI", "인공지능"), "broad": ("디지털", "디지털 전환", "정보화")},
        },
        financing=("R&D", "바우처", "세액공제"),
        delivery=("플랫폼", "데이터", "컨설팅"),
    ),
    Concept(
        triggers=("중소기업", "소상공인", "중견기업"),
        axes={"대상": {"exact": ("중소기업",), "syn": ("소상공인", "중견기업", "영세기업")}},
    ),
    Concept(
        triggers=("교육", "훈련", "인력양성", "역량강화"),
        axes={"수단": {"exact": ("교육", "훈련"), "syn": ("인력양성", "역량강화", "재교육")}},
        delivery=("위탁", "바우처", "온라인 교육"),
    ),
    Concept(
        triggers=("기본소득", "기회소득", "수당", "현금지원"),
        axes={"수단": {"exact": ("기본소득",), "syn": ("기회소득", "사회수당", "현금지원", "소득보장")}},
        financing=("보편", "선별", "재정지원", "목적세"),
        delivery=("현금", "월정액", "정기지급"),
    ),
)


BROAD_BY_DOMAIN = {
    "기후": ("기후위기", "기후 적응", "탄소중립"),
    "재난": ("재난 안전", "재난 대응", "회복탄력성"),
    "안보": ("경제안보", "공급망 안보", "국가안보"),
    "공급망": ("공급망 회복력", "공급망 단절", "경제안보"),
    "에너지": ("에너지 안보", "분산에너지", "전력망"),
    "식량": ("식량 안보", "농식품", "푸드테크"),
    "물": ("물 안보", "수자원", "물 관리"),
    "수자원": ("물 안보", "수자원", "물 관리"),
    "스마트시티": ("스마트시티", "도시 인프라", "도시 회복력"),
    "교육": ("교육", "직업훈련", "인력양성"),
    "보건": ("보건의료", "공공보건", "의료서비스"),
    "복지": ("사회복지", "소득보장", "취약계층"),
    "문화": ("문화예술", "문화정책", "예술인복지"),
    "교통": ("교통 인프라", "광역교통", "모빌리티"),
    "주거": ("주거복지", "주택정책", "도시정책"),
    "노동": ("고용", "노동시장", "직업훈련"),
    "환경": ("환경정책", "순환경제", "탄소중립"),
    "산업정책": ("산업정책", "첨단산업", "신산업"),
    "디지털": ("디지털 전환", "정보화", "데이터 경제"),
    "AI": ("AI", "인공지능", "디지털 전환"),
}


def decompose_policy_idea(text: str) -> dict:
    """Return a draft Idea JSON that the web form can edit and analyze."""
    cleaned = _clean_text(text)
    draft = _empty(cleaned)
    notes: list[str] = []
    if not cleaned:
        draft["_auto"] = {"confidence": 0.0, "notes": ["아이디어 문장이 비어 있습니다."]}
        return draft

    quoted = _quoted_phrases(cleaned)
    _place_quoted_terms(draft, quoted)

    for concept in CONCEPTS:
        if _has_any(cleaned, concept.triggers):
            _merge_concept(draft, concept)
            if concept.note:
                notes.append(concept.note)

    phrases = _candidate_phrases(cleaned)
    _classify_phrases(draft, phrases)
    _add_financing_delivery(draft, cleaned)
    _trim(draft)

    filled = sum(
        bool(draft["axes"][axis][kind])
        for axis in AXES
        for kind in ("exact", "syn", "broad")
    )
    confidence = min(0.92, 0.22 + filled * 0.07)
    if not draft["axes"]["대상"]["exact"]:
        notes.append("대상이 약합니다. 누가/무엇을 바꾸는 정책인지 exact에 1개 이상 보강하세요.")
    if not draft["axes"]["수단"]["exact"]:
        notes.append("수단이 약합니다. 지원·규제·인프라·조달·교육 등 정책 도구를 exact에 보강하세요.")
    if not draft["axes"]["영역"]["exact"]:
        notes.append("영역이 약합니다. 산업·교육·보건·기후·안보처럼 평가 분야를 exact에 보강하세요.")
    notes.append("자동 분해는 초안입니다. exact는 좁게, broad는 검색 확장용으로만 두는 것이 좋습니다.")
    draft["_auto"] = {"confidence": round(confidence, 2), "notes": _unique(notes)}
    return draft


def _empty(text: str) -> dict:
    return {
        "idea": _headline(text),
        "axes": {
            axis: {"exact": [], "syn": [], "broad": []}
            for axis in AXES
        },
        "financing": [],
        "delivery": [],
        "known_positives": [],
    }


def _clean_text(text: str) -> str:
    text = re.sub(r"[*_#>`]+", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _headline(text: str) -> str:
    if not text:
        return ""
    first = re.split(r"[\n.!?。]\s*", text.strip(), maxsplit=1)[0]
    first = re.sub(r"\([^가-힣)]*[A-Za-z][^)]*\)", "", first).strip()
    return first[:120]


def _quoted_phrases(text: str) -> list[str]:
    pairs = [
        ("'", "'"), ('"', '"'), ("‘", "’"), ("“", "”"), ("「", "」"), ("『", "』"),
    ]
    found: list[str] = []
    for left, right in pairs:
        found += re.findall(re.escape(left) + r"([^" + re.escape(right) + r"]{2,80})" + re.escape(right), text)
    return [_tidy_phrase(p) for p in found if _tidy_phrase(p)]


def _place_quoted_terms(draft: dict, phrases: Iterable[str]) -> None:
    for phrase in phrases:
        n = norm(phrase)
        if not n:
            continue
        if any(k in n for k in ("지원", "표준", "모듈", "팩토리", "패키지", "수출", "오프그리드")):
            _add(draft, "수단", "exact", phrase)
        elif any(k in n for k in ("기후", "재난", "안보", "경제", "회복", "공급망")):
            _add(draft, "영역", "exact", phrase)
        else:
            _add(draft, "대상", "exact", phrase)


def _merge_concept(draft: dict, concept: Concept) -> None:
    for axis, groups in concept.axes.items():
        for kind, terms in groups.items():
            for term in terms:
                _add(draft, axis, kind, term)
    for term in concept.financing:
        _add_list(draft["financing"], term)
    for term in concept.delivery:
        _add_list(draft["delivery"], term)


def _candidate_phrases(text: str) -> list[str]:
    compact = re.sub(r"\([^가-힣)]*[A-Za-z][^)]*\)", " ", text)
    compact = re.sub(r"[,:;()\[\]{}<>/]+", " ", compact)
    compact = re.sub(r"\b(및|그리고|또는)\b|(?<=[가-힣])(와|과|로|으로)(?=\s)", " ", compact)
    chunks = re.findall(r"[가-힣A-Za-z0-9&·\-]+(?:\s+[가-힣A-Za-z0-9&·\-]+){0,3}", compact)
    return [_tidy_phrase(c) for c in chunks if _usable_phrase(c)]


def _classify_phrases(draft: dict, phrases: list[str]) -> None:
    for phrase in phrases:
        n = norm(phrase)
        if not n:
            continue
        if _ends_or_contains(phrase, TARGET_SUFFIXES):
            _add(draft, "대상", "syn" if len(phrase) <= 6 else "exact", phrase)
        if _ends_or_contains(phrase, INSTRUMENT_SUFFIXES):
            _add(draft, "수단", "syn" if len(phrase) <= 6 else "exact", phrase)
        for hint in DOMAIN_HINTS:
            if norm(hint) in n:
                _add(draft, "영역", "exact" if len(hint) >= 3 else "syn", hint)
                for broad in BROAD_BY_DOMAIN.get(hint, ()):  # controlled expansion
                    _add(draft, "영역", "broad", broad)


def _add_financing_delivery(draft: dict, text: str) -> None:
    for term in FINANCING_HINTS:
        if _has_any(text, (term,)):
            _add_list(draft["financing"], term)
    for term in DELIVERY_HINTS:
        if _has_any(text, (term,)):
            _add_list(draft["delivery"], term)


def _extract_claims(draft: dict, text: str) -> None:
    """원문에서 추가 정책설계 원자를 보수적으로 추출한다."""
    markers = {
        "문제": ("위기", "격차", "부족", "단절", "붕괴", "취약", "위험", "문제"),
        "작동원리": ("연계", "결합", "순환", "표준화", "분산", "자립", "통합"),
        "적용조건": ("지역", "도시", "소득", "연령", "재난", "위기", "취약"),
        "집행단계": ("시범", "법제화", "도입", "확대", "시행", "구축"),
        "기대결과": ("회복", "자립", "안정", "생존", "성장", "감소", "개선"),
    }
    phrases = _candidate_phrases(text)
    for name, hints in markers.items():
        for phrase in phrases:
            if any(norm(hint) in norm(phrase) for hint in hints):
                _add_list(draft["claims"][name], phrase)
        draft["claims"][name] = draft["claims"][name][:4]

def _trim(draft: dict) -> None:
    for axis in AXES:
        for kind, limit in MAX_TERMS.items():
            values = _unique(draft["axes"][axis][kind])
            values = [v for v in values if not _too_generic(v)]
            draft["axes"][axis][kind] = values[:limit]
    draft["financing"] = _unique(draft["financing"])[:8]
    draft["delivery"] = _unique(draft["delivery"])[:8]


def _add(draft: dict, axis: str, kind: str, term: str) -> None:
    term = _tidy_phrase(term)
    if term and not _too_generic(term):
        _add_list(draft["axes"][axis][kind], term)


def _add_list(values: list[str], term: str) -> None:
    term = _tidy_phrase(term)
    if term and norm(term) not in {norm(v) for v in values}:
        values.append(term)


def _tidy_phrase(value: str) -> str:
    value = re.sub(r"\([^가-힣)]*[A-Za-z][^)]*\)", "", value or "")
    value = re.sub(r"^[\-–—:;,.\s]+|[\-–—:;,.\s]+$", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _usable_phrase(value: str) -> bool:
    value = _tidy_phrase(value)
    if len(value) < 2 or len(value) > 42:
        return False
    if _too_generic(value):
        return False
    return bool(re.search(r"[가-힣A-Za-z]", value))


def _too_generic(value: str) -> bool:
    n = norm(value)
    if not n or len(n) < 2:
        return True
    return any(norm(stop) == n for stop in STOP_PHRASES)


def _unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = _tidy_phrase(value)
        key = norm(value)
        if value and key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _has_any(text: str, needles: Iterable[str]) -> bool:
    ntext = norm(text)
    return any(norm(needle) in ntext for needle in needles if norm(needle))


def _ends_or_contains(phrase: str, suffixes: tuple[str, ...]) -> bool:
    n = norm(phrase)
    return any(n.endswith(norm(s)) or norm(s) in n for s in suffixes)

