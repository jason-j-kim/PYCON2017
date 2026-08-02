import json
import pathlib

from kdinov.web import analyze_payload, idea_from_payload, load_corpus

HERE = pathlib.Path(__file__).parent


def test_web_analyze_payload_returns_four_axis_decision():
    data = json.loads((HERE.parent / "ideas" / "sme_ai_edu.json").read_text(encoding="utf-8"))
    corpus = load_corpus(demo=True)

    result = analyze_payload(data, corpus)

    decision = result["summary"]["decision"]
    assert result["summary"]["overall"] == "O1"
    assert "novelty" not in result["metrics"]
    assert decision["overlap"]["code"] == "O1"
    assert decision["materialDifference"]["code"].startswith("M")
    assert decision["combination"]["code"] == "C2"
    assert decision["confidence"]["code"] in ("E1", "E2")
    assert result["metrics"]["mentionCount"] >= 6
    assert result["documents"][0]["atomicRelations"]


def test_idea_from_web_payload_accepts_textareas():
    idea = idea_from_payload({
        "idea": "중소기업에 AI 교육",
        "axes": {
            "대상": {"exact": "중소기업, 소상공인"},
            "수단": {"exact": "교육\n훈련"},
            "영역": {"exact": "AI, 인공지능"},
        },
        "financing": "무상, 전액지원",
        "delivery": "바우처",
        "known_positives": "중소기업의 AI 도입 및 활용에 관한 사례분석과 시사점",
    })

    assert idea.text == "중소기업에 AI 교육"
    assert idea.axes[0].exact == ["중소기업", "소상공인"]
    assert idea.axes[1].exact == ["교육", "훈련"]
    assert idea.financing == ["무상", "전액지원"]

def test_load_corpus_requires_existing_real_db(tmp_path):
    missing = tmp_path / "missing.sqlite"

    try:
        load_corpus(str(missing), demo=False)
    except SystemExit as exc:
        assert "DB 파일이 없습니다" in str(exc)
    else:
        raise AssertionError("missing real DB must not be created silently")

    assert not missing.exists()


def test_missing_design_is_unknown_not_difference():
    from kdinov.model import Doc

    payload = {
        "idea": "중소기업 AI 교육을 지역 모듈형 바우처로 제공",
        "axes": {
            "대상": {"exact": "중소기업"},
            "수단": {"exact": "AI 교육"},
            "영역": {"exact": "인공지능"},
        },
        "financing": "성과연동기금",
        "delivery": "지역 모듈형 바우처",
    }
    corpus = [Doc(
        "prior", "kdi", "중소기업 인공지능 AI 교육 지원 방안",
        summary="중소기업에 인공지능 교육을 제안한다.", kind="연구보고서",
    )]

    result = analyze_payload(payload, corpus)
    decision = result["summary"]["decision"]

    assert decision["overlap"]["code"] == "O1"
    assert decision["materialDifference"]["code"] == "M3"
    assert "미언급" in decision["materialDifference"]["message"]

def test_same_core_and_design_is_direct_package_overlap():
    from kdinov.model import Doc

    payload = {
        "idea": "중소기업 AI 교육",
        "axes": {
            "대상": {"exact": "중소기업"},
            "수단": {"exact": "AI 교육"},
            "영역": {"exact": "인공지능"},
        },
        "financing": "성과연동기금",
        "delivery": "지역 모듈형 바우처",
    }
    corpus = [Doc(
        "prior", "kdi", "중소기업 인공지능 AI 교육 지원 방안",
        summary="성과연동기금으로 지역 모듈형 바우처를 제공하자.", kind="연구보고서",
    )]

    result = analyze_payload(payload, corpus)
    decision = result["summary"]["decision"]

    assert decision["overlap"]["code"] == "O0"
    assert decision["combination"]["code"] == "C0"

def test_one_weak_design_match_does_not_prove_difference():
    from kdinov.model import Doc

    payload = {
        "idea": "분산형 생존 인프라",
        "axes": {
            "대상": {"exact": "생존 인프라"},
            "수단": {"exact": "오프그리드"},
            "영역": {"exact": "회복탄력성"},
        },
        "financing": "공공투자, 민관협력, 성과연동기금",
        "delivery": "모듈, 지역 단위, 분산형",
    }
    corpus = [Doc(
        "prior", "kdi", "생존 인프라 오프그리드 회복탄력성 방안",
        summary="공공투자 가능성을 검토한다.", kind="연구보고서",
    )]

    result = analyze_payload(payload, corpus)
    decision = result["summary"]["decision"]

    assert decision["overlap"]["code"] == "O1"
    assert decision["materialDifference"]["code"] != "M1"

def test_idea_payload_accepts_additional_atomic_claims():
    idea = idea_from_payload({
        "idea": "지역 회복력 정책",
        "axes": {"대상": {}, "수단": {}, "영역": {}},
        "claims": {
            "문제": "공급망 단절, 필수 기능 붕괴",
            "작동원리": "지역 순환",
        },
    })

    assert idea.claims["문제"] == ["공급망 단절", "필수 기능 붕괴"]
    assert idea.claims["작동원리"] == ["지역 순환"]