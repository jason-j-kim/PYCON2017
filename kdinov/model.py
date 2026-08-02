"""데이터 모델과 한국어 표면형 정규화."""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any

# 필드별 증거 가중치. 제목에 걸린 것과 요약 끝에 스친 것은 같은 증거가 아니다.
FIELD_WEIGHT = {"title": 3.0, "keyword": 2.5, "toc": 2.0, "summary": 1.0}

# 축 용어의 매칭 종류별 감쇠.
TERM_WEIGHT = {"exact": 1.0, "syn": 0.75, "broad": 0.45}


def norm(s: str | None) -> str:
    """공백·기호 변이를 제거해 매칭 가능한 표면형으로 만든다.

    한국어 정책 문서는 '디지털 전환/디지털전환', 'AI/A.I./인공지능',
    'R&D/R·D' 처럼 같은 개념이 여러 표기로 나타난다. 공백과 구두점을
    지우고 대문자로 접으면 이 변이 대부분이 흡수된다.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("·", "").replace("‧", "").replace("ㆍ", "")
    s = re.sub(r"[\s\u200b]+", "", s)
    s = re.sub(r"[.\-_/()\[\]<>「」『』“”\"']", "", s)
    return s.upper()

# 단독으로 쓰이면 거의 모든 정책문서에 걸리는 일반 정책어.
# 이런 단어는 사람이 입력해도 판정 근거로 쓰지 않고, 복합어 안에서만 의미를 갖게 둔다.
GENERIC_POLICY_TERMS = {
    "정부", "국가", "공공", "정책", "사업", "제도", "계획", "전략", "방안",
    "대책", "과제", "추진", "지원", "구축", "개선", "강화", "확대", "제고",
    "활성화", "육성", "도입", "기반", "체계", "통합체계", "시스템", "플랫폼",
    "산업", "기술", "관리", "운영", "활용", "적용", "관련", "대응",
}
SHORT_TERM_ALLOWLIST = {"AI", "IP", "ESG", "R&D"}
_GENERIC_POLICY_NORMS = {norm(t) for t in GENERIC_POLICY_TERMS}
_SHORT_TERM_NORMS = {norm(t) for t in SHORT_TERM_ALLOWLIST}


def is_short_match_term(text: str | None) -> bool:
    n = norm(text)
    return bool(n and len(n) <= 2 and n in _SHORT_TERM_NORMS)


def is_usable_match_term(text: str | None, kind: str = "exact") -> bool:
    """판정·검색에 실제로 쓸 수 있는 용어인지 가른다.

    '지원', '정부', '구축' 같은 단독 일반어와 너무 짧은 표면형은
    후보 수를 폭발시키므로 제외한다. 단, AI/IP 같은 약어는 약하게 허용한다.
    """
    n = norm(text)
    if not n:
        return False
    if n in _GENERIC_POLICY_NORMS:
        return False
    if len(n) < 3 and n not in _SHORT_TERM_NORMS:
        return False
    if kind == "broad" and len(n) < 4 and n not in _SHORT_TERM_NORMS:
        return False
    return True


_KDI_TOPIC_BOILERPLATE = "KDI의 발간물을 다양한 연구 주제로 분류하여 제공합니다."


def clean_field_text(field_name: str, value: str | None) -> str:
    """검색 증거가 아닌 KDI 공통 안내문을 제거한다."""
    text = (value or "").strip()
    if field_name == "keyword" and _KDI_TOPIC_BOILERPLATE in text:
        text = text.split(_KDI_TOPIC_BOILERPLATE, 1)[1].strip()
    if field_name in ("toc", "summary"):
        text = re.sub(r"^열기\s*", "", text)
    return text

@dataclass
class Doc:
    """한 건의 발간물. 출처가 달라도 이 형태로 정규화된다."""
    doc_id: str
    source: str                  # kdi_api | eiec | prism | manual
    title: str
    url: str = ""
    date: str = ""               # YYYY-MM-DD 또는 YYYYMMDD
    keywords: str = ""
    toc: str = ""                # 목차. 제목과 요약 사이의 중간 증거층
    summary: str = ""
    kind: str = ""               # 연구보고서 / 정책연구시리즈 / 현안자료 ...
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def fields(self) -> dict[str, str]:
        return {"title": clean_field_text("title", self.title),
                "keyword": clean_field_text("keyword", self.keywords),
                "toc": clean_field_text("toc", self.toc),
                "summary": clean_field_text("summary", self.summary)}

    def year(self) -> str:
        m = re.search(r"(19|20)\d{2}", self.date or "")
        return m.group(0) if m else ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class AxisSpec:
    """정책 아이디어의 한 축. exact/syn/broad로 확신도를 구분해 선언한다."""
    name: str
    exact: list[str] = field(default_factory=list)
    syn: list[str] = field(default_factory=list)
    broad: list[str] = field(default_factory=list)

    def terms(self) -> list[tuple[str, str, float]]:
        """(용어, 종류, 가중치) 목록. 긴 복합어 우선 — 일반어 오탐 방지."""
        out = []
        for k in ("exact", "syn", "broad"):
            for t in getattr(self, k):
                if not is_usable_match_term(t, k):
                    continue
                weight = TERM_WEIGHT[k]
                if is_short_match_term(t):
                    weight *= 0.25
                out.append((t, k, weight))
        return sorted(out, key=lambda x: (-len(norm(x[0])), -x[2], x[0]))


@dataclass
class Idea:
    """검증 대상 정책 아이디어."""
    text: str
    axes: list[AxisSpec]
    financing: list[str] = field(default_factory=list)
    delivery: list[str] = field(default_factory=list)
    # 재현율 통제용. 사람이 손으로 찾아 확인한 '반드시 걸려야 하는' 문헌.
    known_positives: list[str] = field(default_factory=list)
    claims: dict[str, list[str]] = field(default_factory=dict)

    @property
    def axis_names(self) -> list[str]:
        return [a.name for a in self.axes]

    @classmethod
    def from_dict(cls, d: dict) -> "Idea":
        axes = []
        for name, spec in d["axes"].items():
            if isinstance(spec, list):        # 축약 표기: 전부 exact 취급
                axes.append(AxisSpec(name, exact=list(spec)))
            else:
                axes.append(AxisSpec(name, **spec))
        claims = {
            str(name): [str(v).strip() for v in values if str(v).strip()]
            for name, values in (d.get("claims") or {}).items()
        }
        return cls(text=d.get("idea", ""), axes=axes,
                   financing=d.get("financing", []),
                   delivery=d.get("delivery", []),
                   known_positives=d.get("known_positives", []),
                   claims=claims)
