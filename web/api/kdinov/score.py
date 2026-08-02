"""축 매칭, 공기(co-occurrence) 판정, 정책 벡터 방향 판정.

네 개의 독립적 신호를 만든다.
  1) coverage   — 어느 축이, 어느 필드에서, 얼마나 강하게 걸렸나
  2) cooccur    — 축들이 '같은 의미 단위 안에서' 만나는가 (정밀도의 핵심)
  3) direction  — 정책의 화살표가 같은 방향인가 (오탐의 최대 원인)
  4) instrument — 수단이 '다른 것으로 있음'인가 '아예 없음'인가

3번이 없으면 '중소기업 지원정책에 AI를 적용'과
'중소기업에 AI 교육을 지원'을 구별할 수 없다. 축은 셋 다 걸리지만
전자는 정부가 AI를 쓰는 이야기고 후자는 중소기업이 AI를 배우는 이야기다.
4번이 없으면 경합 문헌(N1)과 인용 가능한 근거 문헌(N3)이 뒤섞인다.
"""
from __future__ import annotations
import os, re, sys
from dataclasses import dataclass, field
from .model import Doc, Idea, AxisSpec, FIELD_WEIGHT, norm

# 형태소 분석기는 문장 분할에만 쓴다. 방향성 규칙은 표면형 정규식이므로
# 분석기가 없어도 판정 로직 전체가 동작한다. 네트워크 없는 샌드박스에서
# 설치가 안 될 수 있으므로 KDINOV_NO_KIWI=1 로 강제 퇴화시켜 시험할 수 있다.
if os.environ.get("KDINOV_NO_KIWI") or sys.version_info >= (3, 13):
    # kiwipiepy 0.23.x가 일부 Windows Python 3.13 런타임에서 네이티브
    # 크래시를 내므로, 이 조합에서는 검증된 정규식 분할로 퇴화시킨다.
    _KIWI = None
else:
    try:
        from kiwipiepy import Kiwi
        _KIWI = Kiwi()
    except Exception:                                # pragma: no cover
        _KIWI = None

# 목차 항목 구분자. 실제 KDI 목차는 '제1장'보다 '1.' '2.' 형태가 많고
# 한 줄로 붙어 오는 경우도 흔하다. 분할하지 않으면 목차 전체가 한 문장으로
# 취급되어 3축 공기가 무조건 성립하는 치명적 오탐이 난다.
_TOC_SPLIT = re.compile(
    r"(?:\n|·|;|/|\s\|\s"
    r"|제\s*\d+\s*[장절]"
    r"|(?:^|\s)\d{1,2}\s*[.)]"
    r"|(?:^|\s)[IVXivx]{1,4}\s*[.)]"
    r"|(?:^|\s)[가나다라마바사아자차카타파하]\s*[.)])")


def sentences(text: str) -> list[str]:
    if not text:
        return []
    if _KIWI is not None:
        try:
            return [s.text for s in _KIWI.split_into_sents(text)]
        except Exception:
            pass
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def toc_items(toc: str) -> list[str]:
    return [c.strip(" .·-") for c in _TOC_SPLIT.split(toc or "") if c and c.strip()]


# --------------------------------------------------------------------------
# 1) coverage
# --------------------------------------------------------------------------
@dataclass
class AxisHit:
    axis: str
    term: str
    kind: str            # exact | syn | broad
    fields: dict[str, float] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return max(self.fields.values()) if self.fields else 0.0

    @property
    def best_field(self) -> str:
        return max(self.fields, key=self.fields.get) if self.fields else ""


def coverage(doc: Doc, idea: Idea) -> dict[str, AxisHit]:
    best: dict[str, AxisHit] = {}
    normed = {f: norm(v) for f, v in doc.fields().items()}
    for ax in idea.axes:
        for term, kind, tw in ax.terms():
            nt = norm(term)
            if not nt:
                continue
            hits = {f: FIELD_WEIGHT[f] * tw for f, v in normed.items() if nt in v}
            if not hits:
                continue
            cand = AxisHit(ax.name, term, kind, hits)
            if ax.name not in best or cand.score > best[ax.name].score:
                best[ax.name] = cand
            break
    return best


# --------------------------------------------------------------------------
# 2) cooccur
# --------------------------------------------------------------------------
@dataclass
class Window:
    text: str
    where: str
    axes: set[str]


def windows(doc: Doc, idea: Idea) -> list[Window]:
    """축이 2개 이상 함께 등장하는 '의미 단위'를 강한 순으로 반환.

    키워드 필드는 제외한다. 키워드는 색인용 태그 뭉치이므로 그 안의
    공출현은 의미적 공기가 아니다. '중소기업'과 '인공지능'이 같은 태그
    목록에 있다는 사실은 두 개념이 연결됐다는 증거가 되지 못한다.
    """
    out: list[Window] = []
    units = [("title", [doc.title]),
             ("toc", toc_items(doc.toc)),
             ("summary", sentences(doc.summary))]
    for where, chunks in units:
        for ch in chunks:
            if not ch or not ch.strip():
                continue
            nch = norm(ch)
            got = {ax.name for ax in idea.axes
                   for t, _k, _w in ax.terms() if norm(t) and norm(t) in nch}
            if len(got) >= 2:
                out.append(Window(ch.strip(), where, got))
    out.sort(key=lambda w: (-len(w.axes), -FIELD_WEIGHT[w.where]))
    return out


# --------------------------------------------------------------------------
# 3) direction
# --------------------------------------------------------------------------
ADMIN_VERBS = "적용|활용|도입|이용|사용|접목|결합|동원"
TRANSFER_VERBS = {"지원", "제공", "공급", "지급", "보급", "무상", "부담",
                  "실시", "확대", "강화", "교부", "이수", "참여", "수강"}
_POLICY_TAIL = r"(?:지원|육성|진흥|보호|규제)?\s*(?:정책|사업|시책|제도|프로그램)"
# 영역어가 행정주체·행정작용을 수식하면 그 영역어는 수혜재가 아니라 행정도구다.
_ADMIN_HEAD = r"(?:기반|활용|적용|중심)\s*(?:의\s*)?(?:정부|정책|행정|공공|국가|부처)"


@dataclass
class Direction:
    verdict: str          # aligned | reversed | unclear
    reason: str
    rule: str = ""
    evidence: str = ""

    @property
    def penalty(self) -> float:
        return {"aligned": 0.0, "unclear": 0.15, "reversed": 0.75}[self.verdict]


def _find(a: AxisSpec | None, text: str) -> str | None:
    if a is None:
        return None
    nt = norm(text)
    for t, _k, _w in a.terms():
        if norm(t) and norm(t) in nt:
            return t
    return None


def _loose(term: str) -> str:
    """'디지털 전환'과 '디지털전환'을 함께 잡기 위해 공백을 유연화."""
    return r"\s*".join(re.escape(c) for c in term.replace(" ", ""))


def direction(win: Window, idea: Idea, domain_axis: str = "영역",
              instrument_axis: str = "수단",
              target_axis: str = "대상") -> Direction:
    """한 의미 단위 안에서 정책의 화살표 방향을 판정한다.

    규칙은 원문 표면형에 정규식으로 적용한다. 형태소 단위로 하면
    '인공지능'이 '인공'+'지능'으로 쪼개져 규칙이 발화하지 못한다.

    B(역전) 영역어+목적격+운용동사: 'AI 기술을 적용', '인공지능을 활용'
    C(역전) 대상어+정책/사업 복합: '중소기업 지원사업', '소상공인 정책'
    A(정렬) 영역어+수단어 복합 수식: 'AI 교육', '디지털 역량 훈련'
    D(정렬) 3축 + 이전동사 공기

    B를 A보다 먼저 본다. 'AI 기술을 적용'에서 '기술'이 수단 동의어로
    잡히면 A가 오발화하므로 역전 신호에 우선권을 준다.
    """
    ax = {a.name: a for a in idea.axes}
    txt = win.text
    d_term = _find(ax.get(domain_axis), txt)
    i_term = _find(ax.get(instrument_axis), txt)
    t_term = _find(ax.get(target_axis), txt)

    if d_term and re.search(
            _loose(d_term) + r"\s*(?:기술|기법|모형|솔루션|시스템)?\s*(?:을|를)"
            r"\s*(?:\S{0,8}\s*)?(?:" + ADMIN_VERBS + ")", txt):
        return Direction("reversed",
                         f"'{d_term}'가 운용동사의 목적어 — 행정의 도구",
                         "B", txt)

    if d_term and re.search(_loose(d_term) + r"\s*" + _ADMIN_HEAD, txt):
        return Direction("reversed",
                         f"'{d_term}'가 행정작용을 수식 — 행정의 도구",
                         "B2", txt)

    if t_term and re.search(_loose(t_term) + r"\s*" + _POLICY_TAIL, txt):
        return Direction("reversed",
                         f"'{t_term}' 뒤에 정책/사업 — 대상어가 수혜자가 아니라 정책 영역",
                         "C", txt)

    if d_term and i_term:
        if re.search(_loose(d_term) + r"\s*(?:\S{0,4}\s*)?" + _loose(i_term), txt):
            return Direction("aligned", f"'{d_term}'+'{i_term}' 복합 수식", "A", txt)

    if d_term and i_term and t_term and any(v in txt for v in TRANSFER_VERBS):
        return Direction("aligned", "3축 + 이전동사 공기", "D", txt)

    return Direction("unclear", "방향 단서 부족 — 사람 확인 필요", "", txt)


# --------------------------------------------------------------------------
# 4) 수단 프로파일 — '수단이 다름'과 '수단이 없음'을 가른다
# --------------------------------------------------------------------------
GENERIC_INSTRUMENTS = {
    "보조금", "바우처", "세액공제", "감면", "면제", "융자", "대출", "보증",
    "출자", "모태펀드", "펀드", "교육", "훈련", "컨설팅", "멘토링", "인증",
    "규제", "의무화", "표준", "공시", "조달", "정보제공", "인력양성",
    "역량강화", "인프라", "테스트베드", "쿠폰", "장려금", "수당", "비용지원",
}
PROPOSAL_MARKERS = {"정책제언", "정책 제언", "시사점", "제안", "방안",
                    "개선", "필요", "요구", "권고", "과제"}


def instrument_profile(doc: Doc, idea: Idea) -> dict:
    """이 문헌이 정책수단을 제안하는가, 그렇다면 우리 수단과 같은가.

    수단축이 비었을 때 그것이 '경합 수단이 있음'(N1)인지
    '수단 제안 자체가 없는 효과분석'(N3)인지를 가르는 근거가 된다.
    """
    ntext = norm(" ".join(doc.fields().values()))
    mine = {norm(t) for a in idea.axes if a.name == "수단"
            for t, _k, _w in a.terms() if norm(t)}
    found = {g for g in GENERIC_INSTRUMENTS if norm(g) in ntext}
    other = {g for g in found
             if not any(m in norm(g) or norm(g) in m for m in mine)}
    return {"any": bool(found), "found": sorted(found),
            "other": sorted(other),
            "proposes": any(norm(p) in ntext for p in PROPOSAL_MARKERS)}


def direction_agg(wins: list[Window], idea: Idea, top: int = 5) -> Direction | None:
    """상위 몇 개 창을 모두 보고 방향을 종합한다.

    창 하나로 판정하면 취약하다. 제목에는 단서가 없고 목차나 요약의
    특정 문장에만 역전 신호가 있는 경우가 실제로 흔하다. 역전 신호는
    하나만 있어도 진단적이므로 우선한다.
    """
    if not wins:
        return None
    got = [direction(w, idea) for w in wins[:top]]
    for want in ("reversed", "aligned"):
        for d in got:
            if d.verdict == want:
                return d
    return got[0]
