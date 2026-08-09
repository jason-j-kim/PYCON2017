#!/usr/bin/env python3
"""
KWCI L3 — K-소비재 통합 토픽·키워드 사전 (푸드 · 뷰티 · 패션)

세 도메인을 한 파일로 낸다. 셋은 L1 에서 이미 한 벌로 다뤄졌고(품목 마스터
928개, 패널 7,875칸), L3 에서도 같은 문법·같은 국가·같은 위약 구조를 써야
도메인 간 비교가 성립한다.

품목이 아니라 일반 토픽
----------------------
앞선 kfood_dict 는 동결 품목 30개를 1:1 로 번역했다. 그 방식은 선정 재량이
없다는 장점이 있지만, 사람이 실제로 검색하는 말과 어긋난다. 아무도
"Korean instant rice" 를 검색하지 않는다.

여기서는 수출 품목을 앵커가 아니라 **참고**로 쓴다. 어떤 범주가 실제로
크고 중요한지를 품목 구성이 알려주고(K-Beauty 는 330499 기초화장품이 77.8억$
로 도메인의 78%, K-Fashion 은 장신구·부속품·티셔츠·가방·선글라스 순),
질의는 소비자의 말로 짓는다. 각 개념의 ref_hs 에 근거 품목을 남긴다.

손으로 쓰지 않고 조합한다
------------------------
40개 개념 x 11개 언어를 손으로 쓰면 오타와 어색한 직역이 반드시 섞이고,
어느 셀이 문제인지 사후에 알 수 없다. 더 나쁜 것은 위약 비교가 깨진다는
점이다 — "한국 화장품"과 "프랑스 화장품"을 따로 쓰면 두 질의의 자연스러움이
달라져, 차이가 관심의 차이인지 표현의 차이인지 구분되지 않는다.

그래서 lexicon.py 의 조합기를 쓴다.

    질의 = 원산지 형용사(6종) x 범주 명사(33종) x 언어별 어순·성 일치

원산지만 바꾸면 위약이 나온다. 같은 명사, 같은 어순, 같은 자연스러움이
보장되므로 한국 계열과 위약 계열의 유일한 차이가 원산지가 된다. 이것이
위약검정이 요구하는 조건이다.

조합되지 않는 것만 개별 표기한다 — 외래어로 굳은 말(kimchi · soju ·
tteokbokki · mukbang · glass skin)과 국제 브랜드어(K-food · K-beauty ·
K-fashion). 10개뿐이다.

산출: kconsumer_dict.csv (기존 486행 사전과 40열 동일)

사용법
------
  python build_consumer_dict.py                # 생성 + 요약
  python build_consumer_dict.py --review JP    # 국가별 전체 질의
  python build_consumer_dict.py --concepts     # 개념 목록 + 근거 품목
  python build_consumer_dict.py --placebo      # 한국 계열 vs 위약 계열 대조
  python build_consumer_dict.py --merge BASE.csv   # 기존 사전과 병합
  python build_consumer_dict.py --freeze       # sha256 동결
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import COUNTRIES, HEADER, trends_url, write, freeze   # noqa: E402
from lexicon import compose, selftest                              # noqa: E402

OUT = HERE / "kconsumer_dict.csv"
LOCK = HERE / "kconsumer_dict.lock.json"
MERGED = HERE / "KWCI_dictionary_merged.csv"

# ── 조합되지 않는 질의 ──────────────────────────────────────────────
# 외래어로 굳었거나(kimchi) 국제 브랜드어(K-beauty)라 원산지+명사 구조가
# 아니다. 로마자권은 한 형태를 공유하고 비로마자권만 표기를 바꾼다.
def _atom(latin: str, ja: str, th: str, ar: str) -> dict:
    d = {lg: latin for lg in ("en", "vi", "id", "fr", "de", "pt", "es", "tr")}
    d.update({"ja": ja, "th": th, "ar": ar})
    return d


ATOM = {
    "K-food": _atom("K-food", "K-food", "K-food", "K-food"),
    "K-beauty": _atom("K-beauty", "K-beauty", "K-beauty", "K-beauty"),
    "K-fashion": _atom("K-fashion", "K-fashion", "K-fashion", "K-fashion"),
    "mukbang": _atom("mukbang", "モッパン", "มุกบัง", "موكبانغ"),
    "kimchi": _atom("kimchi", "韓国キムチ", "กิมจิ", "كيمتشي"),
    "soju": _atom("soju", "韓国焼酎", "โซจู", "سوجو"),
    "tteokbokki": _atom("tteokbokki", "トッポギ", "ต๊อกบกกี", "توكبوكي"),
    "gochujang": _atom("gochujang", "コチュジャン", "โกชูจัง", "غوتشوجانغ"),
    "glass skin": _atom("glass skin", "ガラス肌", "ผิวกระจก", "بشرة زجاجية"),
    "ginseng": {"en": "Korean ginseng", "ja": "高麗人参",
                "vi": "nhân sâm Hàn Quốc", "th": "โสมเกาหลี",
                "id": "ginseng Korea", "fr": "ginseng coréen",
                "de": "koreanischer Ginseng", "pt": "ginseng coreano",
                "es": "ginseng coreano", "tr": "Kore ginsengi",
                "ar": "جينسنغ كوري"},
}

# ── 개념 ────────────────────────────────────────────────────────────
# (id, 도메인, 이름, 방식, 사양, 근거품목, 자국제외, topic후보)
#   방식 "C" -> 사양 = (원산지, 명사키)   조합기가 만든다
#   방식 "A" -> 사양 = ATOM 키            개별 표기
C, A = "C", "A"
CONCEPTS = [
    # ══ K-FOOD ═══════════════════════════════════════════════════════
    ("KFOOD_G01", "KFOOD", "한국 음식", C, ("KR", "food"), "", None, True),
    ("KFOOD_G02", "KFOOD", "K-food", A, "K-food", "", None, True),
    ("KFOOD_G03", "KFOOD", "한국 요리법", C, ("KR", "recipe"), "", None, False),
    ("KFOOD_G04", "KFOOD", "한식당", C, ("KR", "restaurant"), "", None, False),
    ("KFOOD_G05", "KFOOD", "먹방", A, "mukbang", "", None, True),
    ("KFOOD_G06", "KFOOD", "한국 길거리음식", C, ("KR", "street_food"), "", None, False),
    ("KFOOD_E01", "KFOOD", "김치", A, "kimchi", "200599", None, True),
    ("KFOOD_E02", "KFOOD", "라면", C, ("KR", "instant_noodles"), "190230", None, True),
    ("KFOOD_E03", "KFOOD", "소주", A, "soju", "220890·220870", None, True),
    ("KFOOD_E04", "KFOOD", "떡볶이", A, "tteokbokki", "", None, True),
    ("KFOOD_E05", "KFOOD", "한국 치킨", C, ("KR", "chicken"), "", None, False),
    ("KFOOD_E06", "KFOOD", "한국 과자", C, ("KR", "snacks"), "190590·170490", None, False),
    ("KFOOD_E07", "KFOOD", "김", C, ("KR", "seaweed"), "121221", None, False),
    ("KFOOD_E08", "KFOOD", "고추장", A, "gochujang", "210390", None, True),
    ("KFOOD_E09", "KFOOD", "인삼", A, "ginseng", "121120", None, True),
    ("KFOOD_P01", "KFOOD", "[위약] 일식", C, ("JP", "food"), "", "JP", True),
    ("KFOOD_P02", "KFOOD", "[위약] 중식", C, ("CN", "food"), "", None, True),
    ("KFOOD_P03", "KFOOD", "[위약] 태국음식", C, ("TH", "food"), "", "TH", True),
    # ══ K-BEAUTY ═════════════════════════════════════════════════════
    ("KBEAUTY_G01", "KBEAUTY", "한국 화장품", C, ("KR", "cosmetics"), "", None, True),
    ("KBEAUTY_G02", "KBEAUTY", "K-beauty", A, "K-beauty", "", None, True),
    ("KBEAUTY_G03", "KBEAUTY", "한국 스킨케어 루틴", C, ("KR", "skincare_routine"),
     "330499", None, False),
    ("KBEAUTY_G04", "KBEAUTY", "한국 화장품 브랜드", C, ("KR", "cosmetics_brand"),
     "", None, False),
    ("KBEAUTY_G05", "KBEAUTY", "한국 메이크업", C, ("KR", "makeup_tutorial"),
     "330410·330420", None, False),
    ("KBEAUTY_G06", "KBEAUTY", "글래스 스킨", A, "glass skin", "", None, True),
    ("KBEAUTY_E01", "KBEAUTY", "세럼·에센스", C, ("KR", "serum"), "330499", None, False),
    ("KBEAUTY_E02", "KBEAUTY", "시트마스크", C, ("KR", "sheet_mask"), "330499", None, False),
    ("KBEAUTY_E03", "KBEAUTY", "선크림", C, ("KR", "sunscreen"), "330499", None, False),
    ("KBEAUTY_E04", "KBEAUTY", "쿠션 파운데이션", C, ("KR", "cushion"),
     "330491·961620", None, False),
    ("KBEAUTY_E05", "KBEAUTY", "립틴트", C, ("KR", "lip_tint"), "330410", None, False),
    ("KBEAUTY_E06", "KBEAUTY", "클렌징", C, ("KR", "cleanser"), "340130", None, False),
    ("KBEAUTY_E07", "KBEAUTY", "헤어케어", C, ("KR", "haircare"), "330590·330510",
     None, False),
    ("KBEAUTY_E08", "KBEAUTY", "향수", C, ("KR", "perfume"), "330300·330790", None, False),
    ("KBEAUTY_P01", "KBEAUTY", "[위약] 일본 화장품", C, ("JP", "cosmetics"), "",
     "JP", True),
    ("KBEAUTY_P02", "KBEAUTY", "[위약] 프랑스 화장품", C, ("FR", "cosmetics"), "",
     "FR", True),
    # ══ K-FASHION ════════════════════════════════════════════════════
    ("KFASHION_G01", "KFASHION", "한국 패션", C, ("KR", "fashion"), "", None, True),
    ("KFASHION_G02", "KFASHION", "K-fashion", A, "K-fashion", "", None, True),
    ("KFASHION_G03", "KFASHION", "한국 스타일 코디", C, ("KR", "style"), "", None, False),
    ("KFASHION_G04", "KFASHION", "한국 패션 브랜드", C, ("KR", "fashion_brand"), "",
     None, False),
    ("KFASHION_G05", "KFASHION", "아이돌 패션", C, ("KR", "idol_fashion"), "",
     None, False),
    ("KFASHION_G06", "KFASHION", "한국 스트릿웨어", C, ("KR", "streetwear"), "",
     None, False),
    ("KFASHION_G07", "KFASHION", "한국 옷 쇼핑몰", C, ("KR", "online_shop"), "",
     None, False),
    ("KFASHION_E01", "KFASHION", "가방", C, ("KR", "bag"), "420222·420221·420292",
     None, False),
    ("KFASHION_E02", "KFASHION", "선글라스", C, ("KR", "sunglasses"), "900410",
     None, False),
    ("KFASHION_E03", "KFASHION", "스니커즈", C, ("KR", "sneakers"), "640411·640419",
     None, False),
    ("KFASHION_E04", "KFASHION", "티셔츠", C, ("KR", "tshirt"), "610910·610990",
     None, False),
    ("KFASHION_E05", "KFASHION", "주얼리", C, ("KR", "jewelry"), "711319·711719",
     None, False),
    ("KFASHION_E06", "KFASHION", "모자", C, ("KR", "hat"), "650500", None, False),
    ("KFASHION_E07", "KFASHION", "아우터", C, ("KR", "outerwear"), "620240", None, False),
    ("KFASHION_P01", "KFASHION", "[위약] 일본 패션", C, ("JP", "fashion"), "",
     "JP", True),
    ("KFASHION_P02", "KFASHION", "[위약] 이탈리아 패션", C, ("IT", "fashion"), "",
     "IT", True),
]

# 개념별 잔여 위험. 사전이 못 잡는 것을 사전 안에 적어 둔다.
RISK = {
    "KFOOD_E02": "'ramen' 단독은 일식이다. 전 언어에서 한국 수식어를 붙였으나 "
                 "그만큼 검색량이 줄어 과소측정 가능",
    "KFOOD_E01": "일본은 자국산 김치를 대량 생산해 JP 신호에 국산 수요가 섞인다",
    "KFOOD_E03": "일본어 焼酎 는 일본 소주다. 韓国焼酎 로 한정했으나 ソジュ 표기와 "
                 "분산될 수 있음",
    "KFOOD_E07": "일본어 のり 단독은 일본산 김. 韓国のり 로 한정",
    "KFOOD_G05": "먹방은 한국 기원어지만 이미 국제 장르명이 되어 비한국 콘텐츠를 "
                 "포함한다 — 도메인 귀속이 약해지는 방향",
    "KFOOD_P01": "위약이지만 한식·일식은 대체재이자 보완재라 부호가 양쪽 다 가능 "
                 "— 계수 부호까지 함께 볼 것",
    "KBEAUTY_G06": "'glass skin' 은 한국 기원이나 글로벌 뷰티 용어로 확산돼 "
                   "도메인 귀속이 약하다",
    "KBEAUTY_E04": "쿠션은 한국이 만든 제형이라 원산지 수식 없이도 한국 신호일 수 "
                   "있다 — 수식어를 붙여 과소측정될 위험",
    "KFASHION_G07": "'한국 옷 쇼핑몰'은 플랫폼 브랜드명(무신사 등)으로 검색이 "
                    "분산될 수 있음",
    "KFASHION_E05": "주얼리 대역의 L1 대응 품목 711319 는 금 시세에 좌우된다 — "
                    "L1 과 L3 의 괴리가 클 것으로 예상",
    "KFASHION_G05": "아이돌 패션은 K-Pop 도메인과 겹친다. KPOP 계열과의 상관을 "
                    "먼저 확인할 것",
}

# 일본은 거의 모든 한식·한국 뷰티 범주에 자국 대응물이 있어 오염 위험이 가장 크다.
JP_AMBIGUOUS = {"KFOOD_E01", "KFOOD_E02", "KFOOD_E03", "KFOOD_E07"}


def query(cid_kind: str, spec, lang: str) -> str:
    if cid_kind == C:
        return compose(lang, spec[0], spec[1])
    return ATOM[spec][lang]


def build() -> list[dict]:
    rows: list[dict] = []
    for cc, (cname, lang) in COUNTRIES.items():
        for cid, dom, label, kind, spec, ref, skip, topic in CONCEPTS:
            if skip == cc:
                continue                       # 자국이 대상인 위약은 무의미
            q = query(kind, spec, lang)
            rows.append({
                "measurement_unit_id": f"{cc}|{dom}|{cid}",
                "country_code": cc,
                "domain_code": dom,
                "concept_id": cid,
                "entity_id": "",
                "final_unit_type": "keyword",
                "final_query": q,
                "topic_mid": "",
                "query_language": lang,
                "selection_basis": ("EXPORT_REFERENCED" if ref else "MODE_GRAMMAR"),
                "selection_status": "RULE_SELECTED",
                "validation_status": "PENDING_EMPIRICAL",
                "signal_status": "UNKNOWN",
                "confidence_level": "PENDING",
                "empirical_validation_status": "NOT_YET_TESTED",
                "technical_status": ("PENDING_TOPIC_EXTRACTION" if topic
                                     else "PENDING_DOM_EXTRACTION"),
                "technical_attempt_count": "",
                "extraction_method": ("COMPOSED" if kind == C else "ATOMIC_LEXEME"),
                "model_consensus": "", "model_confidence": "", "score_margin": "",
                "exact_validated_other_countries": "",
                "official_name_check": "",
                "topic_mid_format_check": "N/A",
                "ambiguity_flag": ("JP_DOMESTIC_COUNTERPART"
                                   if cc == "JP" and cid in JP_AMBIGUOUS else ""),
                "selection_rule": ("ORIGIN-NOUN-COMPOSED-1.0" if kind == C
                                   else "ATOMIC-LEXEME-1.0"),
                "second_pass_decision": "NOT_REQUIRED",
                "second_pass_confidence": "",
                "final_review_status": "PENDING_EMPIRICAL_VALIDATION",
                "concept_valid_keyword_count": "",
                "concept_low_keyword_count": "",
                "concept_valid_keyword_countries": "",
                "concept_low_keyword_countries": "",
                "fallback_query": "",
                "source_url": trends_url(cc, q),
                "inclusion_reason": (
                    f"{label} · 수출 참고 HS {ref} · {cname}({lang}) "
                    f"{'조합' if kind == C else '외래어'}"
                    if ref else
                    f"{label} · 소비양식 문법 · {cname}({lang}) "
                    f"{'조합' if kind == C else '외래어'}"),
                "review_reason": "",
                "remaining_risk": RISK.get(cid, ""),
                "notes": label + (" · TOPIC 후보" if topic else ""),
                "source_record_set": "KCONSUMER_COMPOSED_V1",
            })
    return rows


def summary(rows: list[dict]) -> None:
    print(f"\n{'=' * 72}\nK-소비재 통합 사전  {len(rows)}행"
          f"  =  {len(COUNTRIES)}개국 x 개념 {len(CONCEPTS)}종 - 자국위약\n")
    for dom in ("KFOOD", "KBEAUTY", "KFASHION"):
        cs = [c for c in CONCEPTS if c[1] == dom]
        g = sum(1 for c in cs if "_G" in c[0])
        e = sum(1 for c in cs if "_E" in c[0])
        p = sum(1 for c in cs if "_P" in c[0])
        n = sum(1 for r in rows if r["domain_code"] == dom)
        print(f"  {dom:<10}개념 {len(cs):>2}  (일반 {g} · 범주 {e} · 위약 {p})"
              f"   {n:>4}행")
    comp = sum(1 for r in rows if r["extraction_method"] == "COMPOSED")
    ref = sum(1 for r in rows if r["selection_basis"] == "EXPORT_REFERENCED")
    top = sum(1 for r in rows
              if r["technical_status"] == "PENDING_TOPIC_EXTRACTION")
    print(f"\n  생성      조합 {comp}  ·  외래어 {len(rows) - comp}")
    print(f"  근거      수출 참고 {ref}  ·  소비양식 문법 {len(rows) - ref}")
    print(f"  실측대기  TOPIC 후보 {top}  ·  keyword 전용 {len(rows) - top}")
    print(f"  오염표시  {sum(1 for r in rows if r['ambiguity_flag'])}행 (일본 자국 대응물)")
    print(f"  검색 언어 11종  ·  MID 0 (지어내지 않았다)")


def concepts_view() -> None:
    print(f"\n개념 {len(CONCEPTS)}종 — 근거와 생성 방식\n")
    cur = ""
    for cid, dom, label, kind, spec, ref, skip, topic in CONCEPTS:
        if dom != cur:
            print(f"\n  [{dom}]")
            cur = dom
        how = (f"조합 {spec[0]}x{spec[1]}" if kind == C else f"외래어 {spec}")
        print(f"    {cid:<16}{label:<18}{how:<30}"
              f"{('HS ' + ref) if ref else '문법'}"
              + ("  TOPIC후보" if topic else ""))
    print("\n  '조합' 은 원산지 형용사 x 범주 명사로 만들어진다. 원산지만 바꾸면")
    print("  위약이 되므로 한국 계열과 위약 계열의 유일한 차이가 원산지다.")


def placebo_view(rows: list[dict]) -> None:
    print("\n한국 계열 vs 위약 계열 — 같은 명사, 원산지만 다르다\n")
    pairs = [("food", "KFOOD", ("KR", "JP", "CN", "TH")),
             ("cosmetics", "KBEAUTY", ("KR", "JP", "FR")),
             ("fashion", "KFASHION", ("KR", "JP", "IT"))]
    for noun, dom, origins in pairs:
        print(f"  [{dom} / {noun}]")
        for lg in ("en", "ja", "fr", "de", "es", "th", "vi", "ar"):
            line = "  |  ".join(compose(lg, o, noun) for o in origins)
            print(f"    {lg:<4}{line}")
        print()
    print("  어휘 난이도·어순·성 일치가 계열 간 동일하다. 차이가 관심의 차이인지")
    print("  표현의 차이인지 구분되지 않는 문제가 구조적으로 제거된다.")


def review(rows: list[dict], cc: str) -> None:
    sel = [r for r in rows if r["country_code"] == cc]
    if not sel:
        sys.exit(f"{cc} 는 사전에 없습니다. 가능한 값: {', '.join(COUNTRIES)}")
    nm, lg = COUNTRIES[cc]
    print(f"\n{nm}({cc}) · 검색 언어 {lg} · {len(sel)}행\n")
    cur = ""
    for r in sel:
        if r["domain_code"] != cur:
            print(f"  [{r['domain_code']}]")
            cur = r["domain_code"]
        flag = "   [오염주의]" if r["ambiguity_flag"] else ""
        print(f"    {r['concept_id']:<16}{r['final_query']}{flag}")


def merge(rows: list[dict], base: Path) -> None:
    with base.open(encoding="utf-8-sig") as f:
        old = list(csv.DictReader(f))
    mine = {r["domain_code"] for r in rows}
    other = [r for r in old if r["domain_code"] not in mine]
    out = other + rows
    with MERGED.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    import collections
    print(f"\n병합  {MERGED.name}  {len(out)}행")
    for d, n in collections.Counter(r["domain_code"] for r in out).most_common():
        print(f"    {d:<12}{n:>5}")
    print("\n  기존 사전의 KPOP·KVIDEO·KTOURISM 은 그대로 두었다. 이 사전은")
    print("  KFOOD·KBEAUTY·KFASHION 만 채우므로 충돌하는 concept_id 가 없다.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", metavar="CC", help="국가별 전체 질의")
    ap.add_argument("--concepts", action="store_true", help="개념 목록 + 근거")
    ap.add_argument("--placebo", action="store_true", help="한국 vs 위약 대조")
    ap.add_argument("--merge", metavar="BASE.csv", help="기존 사전과 병합")
    ap.add_argument("--freeze", action="store_true", help="sha256 동결")
    args = ap.parse_args()

    bad = selftest()
    if bad:
        print("어휘표 자체검사 실패:")
        for b in bad:
            print("  ", b)
        return 1

    rows = build()
    write(rows, OUT)

    if args.review:
        review(rows, args.review.upper())
        return 0
    if args.concepts:
        concepts_view()
        return 0
    if args.placebo:
        placebo_view(rows)
        return 0

    summary(rows)
    if args.merge:
        base = Path(args.merge)
        if not base.exists():
            sys.exit(f"{base} 를 찾을 수 없습니다.")
        merge(rows, base)
    if args.freeze:
        freeze(rows, OUT, LOCK, {
            "domains": ["KFOOD", "KBEAUTY", "KFASHION"],
            "concepts": [c[0] for c in CONCEPTS],
            "export_reference": "top_items.csv (item_master.lock.json 27b210b3...)",
            "generation": "lexicon.py 원산지x명사 조합 + 외래어 10종",
        })
    print(f"\n= {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
