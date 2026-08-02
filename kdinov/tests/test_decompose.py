import json

from kdinov.decompose import decompose_policy_idea
from kdinov.web import analyze_payload, load_corpus

SURVIVAL_TEXT = """
극단적 위기 시대를 대비한 '분산형 생존 인프라(Survival Infrastructure)' 산업.
오프그리드 자립 모듈 표준화와 물, 식량, 에너지 순환 시스템을 구축하고
재난 대비·회복탄력성 수출 패키지로 육성한다.
"""


def test_decompose_survival_infrastructure_axes():
    draft = decompose_policy_idea(SURVIVAL_TEXT)

    assert "생존 인프라" in draft["axes"]["대상"]["exact"]
    assert "오프그리드" in draft["axes"]["수단"]["exact"]
    assert "회복탄력성" in draft["axes"]["영역"]["exact"]
    assert "생존 경제" not in draft["axes"]["대상"]["exact"]
    assert "마이크로그리드" in draft["axes"]["수단"]["syn"]
    assert draft["_auto"]["confidence"] > 0.5


def test_decomposed_payload_can_be_analyzed_in_demo_corpus():
    draft = decompose_policy_idea(SURVIVAL_TEXT)
    corpus = load_corpus(demo=True)

    result = analyze_payload(draft, corpus)

    assert result["idea"]
    assert result["metrics"]["searchHitCount"] >= 0
    assert result["summary"]["n_corpus"] == len(corpus)
