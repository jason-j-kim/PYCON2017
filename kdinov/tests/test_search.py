import json
import pathlib

from kdinov.model import Idea
from kdinov.search import CorpusIndex, search_docs, terms_from_idea, terms_from_query
from kdinov.sources import load_jsonl

HERE = pathlib.Path(__file__).parent


def test_terms_from_idea_includes_axes_and_design_terms():
    idea = Idea.from_dict(json.loads(
        (HERE.parent / "ideas" / "sme_ai_edu.json").read_text(encoding="utf-8")))

    terms = terms_from_idea(idea)
    labels = {t.text: t.label for t in terms}

    assert labels["중소기업"] == "대상.exact"
    assert labels["역량강화"] == "수단.syn"
    assert labels["전액지원"] == "재원"
    assert labels["바우처"] == "전달체계"


def test_search_docs_ranks_policy_idea_candidates():
    idea = Idea.from_dict(json.loads(
        (HERE.parent / "ideas" / "sme_ai_edu.json").read_text(encoding="utf-8")))
    corpus = load_jsonl(str(HERE / "corpus.jsonl"))

    hits = search_docs(corpus, terms_from_idea(idea), limit=3)
    titles = [h.doc.title for h in hits]

    assert "중소기업의 AI 도입 및 활용에 관한 사례분석과 시사점" in titles
    assert all(h.score > 0 for h in hits)
    assert hits == sorted(hits, key=lambda h: (-h.score, h.doc.date, h.doc.title))


def test_terms_from_query_strips_common_particles():
    terms = terms_from_query("중소기업에 AI 교육을 무상으로 지원")
    texts = {t.text for t in terms}

    assert {"중소기업", "AI"} <= texts
    assert {"교육", "무상", "지원"}.isdisjoint(texts)


def test_corpus_index_shortlists_before_precise_assessment():
    from kdinov.model import Doc

    idea = Idea.from_dict({
        "idea": "청년 대상 주거 바우처",
        "axes": {
            "대상": ["청년가구"],
            "수단": ["주거바우처"],
            "영역": ["주거안정"],
        },
    })
    corpus = [
        Doc("1", "t", "청년가구 주거안정 주거바우처"),
        Doc("2", "t", "청년가구 고용 현황"),
        Doc("3", "t", "농업 생산성 보고서"),
    ]

    selection = CorpusIndex(corpus).candidates(idea, single_axis_limit=1)

    assert selection.candidate_count == 2
    assert selection.multi_axis_count == 1
    assert [doc.doc_id for doc in selection.docs] == ["1", "2"]