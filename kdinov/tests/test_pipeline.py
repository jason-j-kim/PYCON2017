"""회귀 테스트.

각 케이스는 1차 실행에서 실제로 오판정이 났던 지점이다. 규칙을 고칠 때
여기가 깨지면 이전에 고친 오탐이 되살아난 것이다.
"""
import json, os, sys, pathlib
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from kdinov.model import Idea, Doc, clean_field_text, norm
from kdinov.score import (toc_items, windows, direction_agg, coverage,
                          instrument_profile)
from kdinov.sources import load_jsonl, parse_archive
from kdinov.verdict import assess, check_recall, evidence_grade, policy_package_key, summarize

HERE = pathlib.Path(__file__).parent
IDEA = Idea.from_dict(json.loads(
    (HERE.parent / "ideas" / "sme_ai_edu.json").read_text(encoding="utf-8")))
CORPUS = load_jsonl(str(HERE / "corpus.jsonl"))
BY_TITLE = {d.title: d for d in CORPUS}


def A(title):
    return assess(BY_TITLE[title], IDEA)


# ---------------------------------------------------------------- 정규화
@pytest.mark.parametrize("a,b", [
    ("디지털 전환", "디지털전환"),
    ("A.I.", "AI"),
    ("경제·사회", "경제사회"),
    ("인 공 지 능", "인공지능"),
])
def test_norm_absorbs_surface_variation(a, b):
    assert norm(a) == norm(b)


# ---------------------------------------------------------------- 목차 분할
def test_toc_split_on_arabic_numbering():
    """'1. 2. 3.' 번호 목차가 통째로 한 단위가 되면 3축 공기가 무조건 성립한다.

    1차 실행에서 실제로 발생한 최악의 오탐 원인.
    """
    toc = ("1. 문제제기 2. 공공부문 AI 활용 현황 "
           "3. 중소기업 지원정책의 대상 선별 시 AI 적용의 유용성 탐색 4. 결론")
    items = toc_items(toc)
    assert len(items) == 4
    assert any("중소기업 지원정책" in i for i in items)
    assert not any(len(i) > 60 for i in items)


def test_toc_split_on_jang():
    assert len(toc_items("제1장 서론 제2장 분석 제3장 결론")) == 3


# ---------------------------------------------------------------- 공기 창
def test_keyword_bag_is_not_a_cooccurrence_window():
    """키워드는 색인 태그 뭉치다. 같은 태그 목록에 있다는 건 의미적 연결이 아니다."""
    d = Doc(doc_id="x", source="t", title="무관한 제목",
            keywords="중소기업 인공지능 교육", summary="", toc="")
    assert all(w.where != "keyword" for w in windows(d, IDEA))


def test_window_requires_two_axes():
    d = Doc(doc_id="x", source="t", title="중소기업 금융정책 연구")
    assert windows(d, IDEA) == []


# ---------------------------------------------------------------- 방향성
def test_direction_reversed_rule_C_policy_tail():
    """'중소기업 지원정책에 AI를 적용' — 대상어가 수혜자가 아니라 정책 영역."""
    a = A("AI 기술, 지원정책의 효과를 높일 수 있을까?")
    assert a.direction.verdict == "reversed"
    assert a.direction.rule in ("B", "C")
    assert a.code == "N3", "역전이면 N0으로 올라가서는 안 된다"


def test_direction_reversed_rule_B2_admin_head():
    """'AI 기반 정부 지원' — 영역어가 행정작용을 수식."""
    a = A("AI 기반 정부 지원 통합체계 구축방안")
    assert a.direction.verdict == "reversed"
    assert a.code == "N3"


def test_direction_aligned_compound():
    """'중소기업 CEO 대상 AI 교육 지원' — 영역어+수단어 복합."""
    a = A("중소기업의 AI 도입 및 활용에 관한 사례분석과 시사점")
    assert a.direction.verdict == "aligned"
    assert a.code == "N0"


def test_direction_survives_morpheme_split():
    """'인공지능'은 kiwi가 '인공/지능'으로 쪼갠다. 표면형 정규식이라야 잡힌다."""
    d = Doc(doc_id="x", source="t",
            title="정책집행에 인공지능을 활용하는 방안",
            summary="정부는 정책 집행 과정에 인공지능을 활용한다.")
    dr = direction_agg(windows(d, IDEA) or
                       [__import__("kdinov.score", fromlist=["Window"]).Window(
                           d.title, "title", {"영역", "수단"})], IDEA)
    assert dr is not None and dr.verdict == "reversed"


# ---------------------------------------------------------------- 역할
def test_enacted_document_outranks_evidence():
    """시행령 입법예고는 '근거'가 아니라 '실행'이다. 신규성의 직접 반증."""
    a = A("AI 산업 육성 강화를 위한 「AI기본법 시행령」 개정안 입법예고")
    assert a.role == "실행"
    assert a.code == "N1"


def test_competing_when_same_instrument_proposed():
    a = A("중소기업의 AI 도입 및 활용에 관한 사례분석과 시사점")
    assert a.role == "경합"


def test_evidence_when_no_instrument_proposed():
    """효과분석만 있고 수단 제안이 없으면 경합이 아니라 인용 가능한 근거다."""
    a = A("기업의 디지털 전환과 생산성: 기업규모별 격차를 중심으로")
    assert a.role == "근거"
    assert "수단" not in a.hits


def test_precedent_when_domain_differs_but_design_overlaps():
    """영역(AI)은 없지만 무상·자부담·바우처 설계가 있으면 선례다."""
    a = A("직업훈련 바우처의 노동시장 성과에 관한 연구")
    assert a.role == "선례"
    assert set(a.notes) & {"영역이 다름 — 재원·전달체계 설계의 참조로 활용"}


def test_irrelevant_dropped():
    for t in ("부동산 PF 구조개선 방안에 관한 연구",
              "외국인 근로자 유입의 경제적 영향과 이주 결정요인 분석",
              "제약 산업에서의 정부 정책 효과 분석과 시사점"):
        a = A(t)
        assert a.code == "N4", f"{t} 는 무관해야 한다 (현재 {a.code})"


# ---------------------------------------------------------------- 수단 프로파일
def test_instrument_profile_detects_other_instruments():
    p = instrument_profile(BY_TITLE["제약 산업에서의 정부 정책 효과 분석과 시사점"],
                           IDEA)
    assert p["any"] and "모태펀드" in p["found"]


# ---------------------------------------------------------------- 재현율
def test_recall_pass():
    aa = [assess(d, IDEA) for d in CORPUS]
    r = check_recall(CORPUS, IDEA, aa)
    assert r.ok and r.rate == 1.0


def test_recall_void_blocks_conclusion():
    """확인된 문헌을 놓치면 종합 판정은 VOID여야 한다."""
    idea = Idea.from_dict({**json.loads(
        (HERE.parent / "ideas" / "sme_ai_edu.json").read_text(encoding="utf-8")),
        "known_positives": ["존재하지 않는 보고서 제목"]})
    aa = [assess(d, idea) for d in CORPUS]
    s = summarize(aa, check_recall(CORPUS, idea, aa), len(CORPUS), idea=idea)
    assert s["overall"] == "VOID"


def test_recall_catches_scoring_suppression():
    """코퍼스에는 있으나 채점이 N4로 떨어뜨려도 재현 실패로 잡아야 한다."""
    idea = Idea.from_dict({
        "idea": "무관한 축",
        "axes": {"대상": ["원자력"], "수단": ["폐기물처분"], "영역": ["핵연료"]},
        "known_positives": ["중소기업의 AI 도입 및 활용에 관한 사례분석과 시사점"]})
    aa = [assess(d, idea) for d in CORPUS]
    r = check_recall(CORPUS, idea, aa)
    assert not r.ok, "코퍼스에 있어도 표면화되지 않으면 실패로 처리해야 한다"


# ---------------------------------------------------------------- 종합
def test_refined_overlap_is_O1_for_this_idea():
    aa = [assess(d, IDEA) for d in CORPUS]
    s = summarize(aa, check_recall(CORPUS, IDEA, aa), len(CORPUS), idea=IDEA)
    assert s["overall"] == "O1"
    assert s["decision"]["confidence"]["code"] in ("E1", "E2")
    assert s["by_role"]["실행"] >= 1


# ---------------------------------------------------------------- API 파싱
def test_parse_archive_handles_single_dict():
    """결과 1건일 때 ARCHIVE가 list가 아니라 dict로 오는 API가 흔하다."""
    payload = {"TOTAL_COUNT": "1", "ARCHIVE": {
        "PUB_NM_KORN": "테스트 보고서", "SUMM_KORN": "요약",
        "DETAIL_PAGE": "https://x/1", "ISSU_DT": "20250101"}}
    docs = parse_archive(payload, "A")
    assert len(docs) == 1 and docs[0].title == "테스트 보고서"


def test_parse_archive_skips_untitled():
    assert parse_archive({"ARCHIVE": [{"SUMM_KORN": "제목 없음"}]}, "A") == []


def test_kdi_topic_boilerplate_is_not_search_evidence():
    raw = ("연구 주제 거시 금융 법경제 규제 노동 교육 산업 국제경제 재정 복지 "
           "KDI의 발간물을 다양한 연구 주제로 분류하여 제공합니다. 재정투자사업평가")
    assert clean_field_text("keyword", raw) == "재정투자사업평가"

def test_policy_package_groups_subtitle_variants():
    a = Doc("a", "kdi", "지역 회복력 기본계획: 재원 조달 방안", date="2025")
    b = Doc("b", "kdi", "지역 회복력 기본계획: 전달체계 지침", date="2026")
    assert policy_package_key(a) == policy_package_key(b)


def test_evidence_grade_never_claims_full_text_from_summary():
    doc = Doc("x", "kdi", "제목", summary="가" * 800)
    assert evidence_grade(doc)["grade"] == "A"
    assert evidence_grade(doc)["label"] == "충분한 요약"