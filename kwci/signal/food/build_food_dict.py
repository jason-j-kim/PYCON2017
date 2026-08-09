#!/usr/bin/env python3
"""
KWCI L3 — K-Food 토픽·키워드 사전 생성

기존 486행 사전에는 KFOOD 도메인 코드 자체가 없다(KPOP 396 · KVIDEO 54 ·
KTOURISM 36). 반면 L1 에서 K-Food 는 동결 후보 928개 중 649개(70%)로 가장
두꺼운 도메인이다. L1 이 있는 도메인에 L3 가 없고 L3 가 있는 도메인에 L1 이
없어, 지금은 S3 회귀를 돌릴 수 있는 도메인이 하나도 없다. 이 사전이 그 첫
접점이다.

관광 사전과 다른 점 — 문법을 짜지 않는다
----------------------------------------
관광은 의도어 문법을 설계해야 했다. K-Food 는 그럴 필요가 없다. 이미
동결된 대표품목 30개가 있다(item_master sha256 27b210b3...). 사전을 여기에
걸면 선정 재량이 원천적으로 사라진다.

    개념 = 동결된 top_items 30품목  ->  소비자 검색어로 번역
    질의 = 개념  x  18개국 현지어

HS 190230 을 "ramyeon" 으로 옮기는 것은 선정이 아니라 번역이다. 무엇을
넣을지는 2026-07 에 해시로 잠갔고 여기서는 검색창의 말로 바꾸기만 한다.

30품목이 그대로 30개념이 되지는 않는다. 두 가지 조정이 있고 둘 다 규칙이다.

  (a) 소비자 검색어가 없는 품목은 뺀다. 냉동 참치·고등어·게, 정제당, 조제
      분유는 B2B 원재료라 검색 대상이 아니다. 이 판정은 검정 결과가 아니라
      품목 성격이므로 사후 선택이 아니다. EXCLUDED 에 사유를 남긴다.
  (b) 잔여 분류(n.e.c.) 는 뺀다. 210690·200899 는 각각 9.0억·6.4억$ 로 크지만
      "그 밖의 것" 이라 단일 소비자 개념으로 번역할 수 없다. 큰 값을 버리는
      쪽이 잘못된 개념에 붙이는 것보다 낫다.

위약
----
같은 문법을 이웃 요리에 적용한다(일식·중식·태국음식). "한국 음식 검색이
늘었다"는 아시아 음식 전반의 유행이거나 건강식 붐일 수 있다. 위약에서도
계수가 유의하면 통제가 불충분한 것이므로 결과를 채택하지 않는다.

topic MID
---------
지어내지 않는다. 기존 사전에 KFOOD 행이 없어 승계할 검증된 MID 가 하나도
없으므로, 358행 전부 keyword 로 낸다. 다만 고유 개체로 볼 만한 개념
(김치·고추장·소주·인삼·라면·각국 요리)은 TOPIC 후보로 표시해 DOM 실측 때
MID 를 우선 채택하게 한다.

산출: kfood_dict.csv (기존 40열 스키마 그대로)

사용법
------
  python build_food_dict.py                # 생성 + 요약
  python build_food_dict.py --review JP    # 특정 국가 전체 행
  python build_food_dict.py --mapping      # HS -> 개념 대응표
  python build_food_dict.py --dropped      # 사전에 넣지 않은 품목과 사유
  python build_food_dict.py --freeze       # 생성 후 sha256 동결
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import COUNTRIES, trends_url, write, freeze   # noqa: E402

OUT = HERE / "kfood_dict.csv"
LOCK = HERE / "kfood_dict.lock.json"
DOMAIN = "KFOOD"

# ── 개념 ────────────────────────────────────────────────────────────
# (concept_id, 이름, [연결된 HS], topic후보, 자국제외, {언어: 질의})
# HS 가 빈 것은 도메인 수준 개념(C) 과 위약(P) 이다.
CONCEPTS = [
    # 도메인 수준 — 소비 양식 3종(관심 · 가정조리 · 외식)
    ("KFOOD_C01", "한국 음식 일반", [], True, None, {
        "en": "Korean food",              "ja": "韓国料理",
        "vi": "món ăn Hàn Quốc",          "th": "อาหารเกาหลี",
        "id": "makanan Korea",            "fr": "cuisine coréenne",
        "de": "koreanisches Essen",       "pt": "comida coreana",
        "es": "comida coreana",           "tr": "Kore yemekleri",
        "ar": "الطعام الكوري",
    }),
    ("KFOOD_C02", "한국 요리법 (가정조리)", [], False, None, {
        "en": "Korean recipe",            "ja": "韓国料理 レシピ",
        "vi": "công thức món Hàn",        "th": "สูตรอาหารเกาหลี",
        "id": "resep masakan Korea",      "fr": "recette coréenne",
        "de": "koreanisches Rezept",      "pt": "receita coreana",
        "es": "receta coreana",           "tr": "Kore yemek tarifi",
        "ar": "وصفات كورية",
    }),
    ("KFOOD_C03", "한식당 (외식)", [], False, None, {
        "en": "Korean restaurant",        "ja": "韓国料理店",
        "vi": "nhà hàng Hàn Quốc",        "th": "ร้านอาหารเกาหลี",
        "id": "restoran Korea",           "fr": "restaurant coréen",
        "de": "koreanisches Restaurant",  "pt": "restaurante coreano",
        "es": "restaurante coreano",      "tr": "Kore restoranı",
        "ar": "مطعم كوري",
    }),
    # 품목 — 동결 top_items 에서 번역
    ("KFOOD_I01", "라면", ["190230"], True, None, {
        "en": "Korean ramen",             "ja": "韓国ラーメン",
        "vi": "mì Hàn Quốc",              "th": "รามยอน เกาหลี",
        "id": "ramyeon Korea",            "fr": "ramen coréen",
        "de": "koreanische Ramen",        "pt": "lámen coreano",
        "es": "ramen coreano",            "tr": "Kore ramyeon",
        "ar": "راميون كوري",
    }),
    ("KFOOD_I02", "김치", ["200599"], True, None, {
        "en": "kimchi",                   "ja": "韓国キムチ",
        "vi": "kimchi",                   "th": "กิมจิ",
        "id": "kimchi",                   "fr": "kimchi",
        "de": "Kimchi",                   "pt": "kimchi",
        "es": "kimchi",                   "tr": "kimchi",
        "ar": "كيمتشي",
    }),
    ("KFOOD_I03", "김 (조미김)", ["121221"], False, None, {
        "en": "Korean seaweed snack",     "ja": "韓国のり",
        "vi": "rong biển Hàn Quốc",       "th": "สาหร่ายเกาหลี",
        "id": "rumput laut Korea",        "fr": "algues coréennes",
        "de": "koreanische Algen",        "pt": "alga coreana",
        "es": "alga coreana",             "tr": "Kore yosunu",
        "ar": "أعشاب بحرية كورية",
    }),
    ("KFOOD_I04", "고추장·소스", ["210390"], True, None, {
        "en": "gochujang",                "ja": "コチュジャン",
        "vi": "tương ớt Hàn Quốc",        "th": "โกชูจัง",
        "id": "gochujang",                "fr": "gochujang",
        "de": "Gochujang",                "pt": "gochujang",
        "es": "gochujang",                "tr": "gochujang",
        "ar": "غوتشوجانغ",
    }),
    ("KFOOD_I05", "소주", ["220890", "220870"], True, None, {
        "en": "soju",                     "ja": "韓国焼酎",
        "vi": "rượu soju",                "th": "โซจู",
        "id": "soju",                     "fr": "soju",
        "de": "Soju",                     "pt": "soju",
        "es": "soju",                     "tr": "soju",
        "ar": "سوجو",
    }),
    ("KFOOD_I06", "한국 과자", ["190590", "190410", "170490"], False, None, {
        "en": "Korean snacks",            "ja": "韓国お菓子",
        "vi": "bánh kẹo Hàn Quốc",        "th": "ขนมเกาหลี",
        "id": "snack Korea",              "fr": "snacks coréens",
        "de": "koreanische Snacks",       "pt": "snacks coreanos",
        "es": "snacks coreanos",          "tr": "Kore atıştırmalıkları",
        "ar": "وجبات خفيفة كورية",
    }),
    ("KFOOD_I07", "인삼·홍삼", ["121120"], True, None, {
        "en": "Korean ginseng",           "ja": "高麗人参",
        "vi": "nhân sâm Hàn Quốc",        "th": "โสมเกาหลี",
        "id": "ginseng Korea",            "fr": "ginseng coréen",
        "de": "koreanischer Ginseng",     "pt": "ginseng coreano",
        "es": "ginseng coreano",          "tr": "Kore ginsengi",
        "ar": "جينسنغ كوري",
    }),
    ("KFOOD_I08", "커피믹스", ["210111"], False, None, {
        "en": "Korean instant coffee",    "ja": "韓国 インスタントコーヒー",
        "vi": "cà phê hòa tan Hàn Quốc",  "th": "กาแฟสำเร็จรูป เกาหลี",
        "id": "kopi instan Korea",        "fr": "café instantané coréen",
        "de": "koreanischer Instantkaffee", "pt": "café instantâneo coreano",
        "es": "café instantáneo coreano", "tr": "Kore hazır kahve",
        "ar": "قهوة كورية سريعة التحضير",
    }),
    ("KFOOD_I09", "어묵", ["160420"], False, None, {
        "en": "Korean fish cake",         "ja": "韓国おでん",
        "vi": "chả cá Hàn Quốc",          "th": "ลูกชิ้นปลาเกาหลี",
        "id": "fish cake Korea",          "fr": "gâteau de poisson coréen",
        "de": "koreanischer Fischkuchen", "pt": "bolinho de peixe coreano",
        "es": "pastel de pescado coreano", "tr": "Kore balık keki",
        "ar": "كعك السمك الكوري",
    }),
    ("KFOOD_I10", "한국 맥주", ["220300"], False, None, {
        "en": "Korean beer",              "ja": "韓国ビール",
        "vi": "bia Hàn Quốc",             "th": "เบียร์เกาหลี",
        "id": "bir Korea",                "fr": "bière coréenne",
        "de": "koreanisches Bier",        "pt": "cerveja coreana",
        "es": "cerveza coreana",          "tr": "Kore birası",
        "ar": "بيرة كورية",
    }),
    ("KFOOD_I11", "즉석밥", ["190490"], False, None, {
        "en": "Korean instant rice",      "ja": "韓国 レトルトご飯",
        "vi": "cơm ăn liền Hàn Quốc",     "th": "ข้าวสำเร็จรูปเกาหลี",
        "id": "nasi instan Korea",        "fr": "riz instantané coréen",
        "de": "koreanischer Instantreis", "pt": "arroz instantâneo coreano",
        "es": "arroz instantáneo coreano", "tr": "Kore hazır pirinç",
        "ar": "أرز كوري سريع التحضير",
    }),
    ("KFOOD_I12", "한국 딸기", ["081010"], False, None, {
        "en": "Korean strawberry",        "ja": "韓国いちご",
        "vi": "dâu tây Hàn Quốc",         "th": "สตรอว์เบอร์รี่เกาหลี",
        "id": "stroberi Korea",           "fr": "fraise coréenne",
        "de": "koreanische Erdbeeren",    "pt": "morango coreano",
        "es": "fresa coreana",            "tr": "Kore çileği",
        "ar": "فراولة كورية",
    }),
    ("KFOOD_I13", "한국 아이스크림", ["210500"], False, None, {
        "en": "Korean ice cream",         "ja": "韓国アイス",
        "vi": "kem Hàn Quốc",             "th": "ไอศกรีมเกาหลี",
        "id": "es krim Korea",            "fr": "glace coréenne",
        "de": "koreanisches Eis",         "pt": "sorvete coreano",
        "es": "helado coreano",           "tr": "Kore dondurması",
        "ar": "آيس كريم كوري",
    }),
    ("KFOOD_I14", "한국 음료", ["220299", "220210"], False, None, {
        "en": "Korean drinks",            "ja": "韓国ドリンク",
        "vi": "đồ uống Hàn Quốc",         "th": "เครื่องดื่มเกาหลี",
        "id": "minuman Korea",            "fr": "boissons coréennes",
        "de": "koreanische Getränke",     "pt": "bebidas coreanas",
        "es": "bebidas coreanas",         "tr": "Kore içecekleri",
        "ar": "مشروبات كورية",
    }),
    # 위약 — 같은 문법을 이웃 요리에
    ("KFOOD_P01", "[위약] 일식", [], True, "JP", {
        "en": "Japanese food",            "ja": "",
        "vi": "món ăn Nhật Bản",          "th": "อาหารญี่ปุ่น",
        "id": "makanan Jepang",           "fr": "cuisine japonaise",
        "de": "japanisches Essen",        "pt": "comida japonesa",
        "es": "comida japonesa",          "tr": "Japon yemekleri",
        "ar": "الطعام الياباني",
    }),
    ("KFOOD_P02", "[위약] 태국 음식", [], True, "TH", {
        "en": "Thai food",                "ja": "タイ料理",
        "vi": "món ăn Thái",              "th": "",
        "id": "makanan Thailand",         "fr": "cuisine thaïlandaise",
        "de": "thailändisches Essen",     "pt": "comida tailandesa",
        "es": "comida tailandesa",        "tr": "Tayland yemekleri",
        "ar": "الطعام التايلاندي",
    }),
    ("KFOOD_P03", "[위약] 중식", [], True, None, {
        "en": "Chinese food",             "ja": "中華料理",
        "vi": "món ăn Trung Quốc",        "th": "อาหารจีน",
        "id": "makanan Cina",             "fr": "cuisine chinoise",
        "de": "chinesisches Essen",       "pt": "comida chinesa",
        "es": "comida china",             "tr": "Çin yemekleri",
        "ar": "الطعام الصيني",
    }),
]

# 동결 30품목 중 사전에 넣지 않은 것. 검정 결과가 아니라 품목 성격에 의한
# 판정이므로 사후 선택이 아니다.
EXCLUDED = {
    "210690": (901, "잔여분류(n.e.c.) — 홍삼가공품·건강기능식품·소스가 뒤섞여 "
                    "단일 소비자 개념으로 번역 불가"),
    "200899": (636, "잔여분류(n.e.c.) — 과실·견과 조제품 일반"),
    "030487": (255, "냉동 참치 필레 — 원양어업 B2B, 소비자 검색 대상 아님"),
    "030343": (191, "냉동 가다랑어 — 동상"),
    "170199": (182, "정제당 — B2B 원료"),
    "030354": (84, "냉동 고등어 — B2B"),
    "190110": (84, "조제분유 — 소비재지만 한류 귀속이 아니라 안전성·품질 신뢰 "
                   "기반. 검색어가 브랜드로 갈려 도메인 개념이 성립하지 않음"),
    "030633": (82, "활게·냉장게 — B2B"),
    "030359": (81, "기타 냉동어류 — B2B"),
    "030614": (80, "냉동게 — B2B"),
    "030383": (71, "냉동 이빨고기 — B2B"),
    "030389": (70, "기타 냉동어류 — B2B"),
}

# 개념별 오염 위험. 사전이 못 잡는 것을 사전 안에 적어 둔다.
RISK = {
    "KFOOD_I01": "'ramen' 단독은 일식을 가리킨다. 전 언어에서 한국 수식어를 "
                 "붙였으나 그만큼 검색량이 줄어 과소측정 가능",
    "KFOOD_I02": "일본은 자국산 김치를 대량 생산해 JP 신호에 국산 수요가 섞인다",
    "KFOOD_I05": "일본어 焼酎 는 일본 소주다. 韓国焼酎 로 한정했으나 ソジュ 표기와 "
                 "분산될 수 있음",
    "KFOOD_I03": "일본어 のり 단독은 일본산 김. 韓国のり 로 한정",
    "KFOOD_I06": "과자는 HS 3개 통합 개념이라 품목 대응이 1:1 이 아니다",
    "KFOOD_I09": "직역어라 실제 검색되지 않을 가능성이 높다 — 실증에서 탈락 예상",
    "KFOOD_I12": "신선 딸기는 계절성이 극단적이라 월별 원계열로는 추세 판독 불가",
    "KFOOD_I14": "'한국 음료'는 총칭이라 특정 제품 검색과 어긋날 수 있음",
    "KFOOD_P01": "위약이지만 한식·일식은 대체재이자 보완재라 부호가 양쪽 다 "
                 "가능 — 계수 부호까지 함께 볼 것",
}

# 일본은 거의 모든 한식 범주에 자국 대응물이 있어 오염 위험이 가장 크다.
JP_AMBIGUOUS = {"KFOOD_I01", "KFOOD_I02", "KFOOD_I03", "KFOOD_I05"}


def build() -> list[dict]:
    rows: list[dict] = []
    for cc, (cname, lang) in COUNTRIES.items():
        for cid, label, hs, topic_cand, skip_geo, terms in CONCEPTS:
            if skip_geo == cc:
                continue                       # 자국 요리 위약은 무의미
            q = terms.get(lang, "")
            if not q:
                continue
            rows.append({
                "measurement_unit_id": f"{cc}|{DOMAIN}|{cid}",
                "country_code": cc,
                "domain_code": DOMAIN,
                "concept_id": cid,
                "entity_id": "",
                "final_unit_type": "keyword",
                "final_query": q,
                "topic_mid": "",
                "query_language": lang,
                "selection_basis": ("FROZEN_ITEM_MASTER" if hs else "RULE_GRAMMAR"),
                "selection_status": "RULE_SELECTED",
                "validation_status": "PENDING_EMPIRICAL",
                "signal_status": "UNKNOWN",
                "confidence_level": "PENDING",
                "empirical_validation_status": "NOT_YET_TESTED",
                "technical_status": ("PENDING_TOPIC_EXTRACTION" if topic_cand
                                     else "PENDING_DOM_EXTRACTION"),
                "technical_attempt_count": "",
                "extraction_method": "RULE_GENERATED",
                "model_consensus": "", "model_confidence": "", "score_margin": "",
                "exact_validated_other_countries": "",
                "official_name_check": "",
                "topic_mid_format_check": "N/A",
                "ambiguity_flag": ("JP_DOMESTIC_COUNTERPART"
                                   if cc == "JP" and cid in JP_AMBIGUOUS else ""),
                "selection_rule": ("ITEM-MASTER-TRANSLATED-1.0" if hs
                                   else "GRAMMAR-LOCALIZED-1.0"),
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
                    f"동결 품목 {'·'.join(hs)} 의 소비자 검색어 번역 x {cname}({lang})"
                    if hs else
                    f"의도어 문법 {cid}({label}) x {cname}({lang})"),
                "review_reason": "",
                "remaining_risk": RISK.get(cid, ""),
                "notes": label + (" · TOPIC 후보" if topic_cand else ""),
                "source_record_set": "KFOOD_ITEM_MASTER_V1",
            })
    return rows


def summary(rows: list[dict]) -> None:
    item = [c for c in CONCEPTS if c[2]]
    gen = [c for c in CONCEPTS if not c[2] and not c[4] and "P" not in c[0][6:8]]
    pla = [c for c in CONCEPTS if c[0].startswith("KFOOD_P")]
    print(f"\n{'=' * 70}\nK-Food 사전  {len(rows)}행  =  "
          f"{len(COUNTRIES)}개국 x 개념 {len(CONCEPTS)}종 - 자국위약 2\n")
    print(f"  개념 구성   품목 {len(item)}  ·  도메인 수준 {len(CONCEPTS)-len(item)-len(pla)}"
          f"  ·  위약 {len(pla)}")
    covered = sum(1 for c in CONCEPTS for _ in c[2])
    print(f"  동결 품목   30 중 {covered} 를 {len(item)} 개념으로 번역"
          f"  ·  {len(EXCLUDED)} 제외 (--dropped)")

    print("\n  개념별")
    for cid, label, hs, tc, skip, _ in CONCEPTS:
        n = sum(1 for r in rows if r["concept_id"] == cid)
        src = "·".join(hs) if hs else "—"
        print(f"    {cid:<12}{label:<18}{src:<22}{n:>3}행"
              + ("  TOPIC후보" if tc else "")
              + (f"  {skip} 제외" if skip else ""))

    tc_rows = sum(1 for r in rows
                  if r["technical_status"] == "PENDING_TOPIC_EXTRACTION")
    amb = sum(1 for r in rows if r["ambiguity_flag"])
    print(f"\n  단위     keyword {len(rows)}  (승계 가능한 검증 MID 가 없다)")
    print(f"  실측대기 TOPIC 후보 {tc_rows}  ·  keyword 전용 {len(rows) - tc_rows}")
    print(f"  오염표시 {amb}행  (일본 자국 대응물)")


def mapping() -> None:
    print("\n동결 top_items 30품목 -> 개념 대응\n")
    print(f"  {'HS':<9}{'백만$':>8}  {'개념':<28}상태")
    val = {"190230": 1362, "200599": 178, "121221": 477, "210390": 373,
           "220890": 111, "220870": 97, "190590": 401, "190410": 68,
           "170490": 99, "121120": 82, "210111": 157, "160420": 89,
           "220300": 79, "190490": 165, "081010": 68, "210500": 98,
           "220299": 604, "220210": 168}
    seen = set()
    for cid, label, hs, *_ in CONCEPTS:
        for h in hs:
            print(f"  {h:<9}{val.get(h, 0):>8,}  {cid} {label:<18}채택")
            seen.add(h)
    print()
    for h, (v, why) in sorted(EXCLUDED.items(), key=lambda x: -x[1][0]):
        print(f"  {h:<9}{v:>8,}  {'—':<28}제외")
    tot_in = sum(val.get(h, 0) for h in seen)
    tot_out = sum(v for v, _ in EXCLUDED.values())
    print(f"\n  채택 {len(seen)}품목 {tot_in:,}백만$  ·  "
          f"제외 {len(EXCLUDED)}품목 {tot_out:,}백만$"
          f"  ({tot_in/(tot_in+tot_out)*100:.0f}% 포괄)")


def dropped() -> None:
    print(f"\n사전에 넣지 않은 동결 품목 {len(EXCLUDED)}건\n")
    for h, (v, why) in sorted(EXCLUDED.items(), key=lambda x: -x[1][0]):
        print(f"  {h}  {v:>6,}백만$   {why}")
    print("\n  이 판정은 검정 결과가 아니라 품목 성격에 의한 것이므로 사후 선택이")
    print("  아니다. 품목 마스터는 그대로 두고 사전에서만 제외한다 — L1 지수는")
    print("  30품목 전부로 계속 산출된다.")


def review(rows: list[dict], cc: str) -> None:
    sel = [r for r in rows if r["country_code"] == cc]
    if not sel:
        sys.exit(f"{cc} 는 사전에 없습니다. 가능한 값: {', '.join(COUNTRIES)}")
    nm, lg = COUNTRIES[cc]
    print(f"\n{nm}({cc}) · 검색 언어 {lg} · {len(sel)}행\n")
    for r in sel:
        flag = "  [오염주의]" if r["ambiguity_flag"] else ""
        print(f"  {r['concept_id']:<12}{r['final_query']}{flag}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", metavar="CC", help="해당 국가 전체 행 출력")
    ap.add_argument("--mapping", action="store_true", help="HS -> 개념 대응표")
    ap.add_argument("--dropped", action="store_true", help="제외 품목과 사유")
    ap.add_argument("--freeze", action="store_true", help="생성 후 sha256 동결")
    args = ap.parse_args()

    rows = build()
    write(rows, OUT)

    if args.review:
        review(rows, args.review.upper())
        return 0
    if args.mapping:
        mapping()
        return 0
    if args.dropped:
        dropped()
        return 0

    summary(rows)
    if args.freeze:
        freeze(rows, OUT, LOCK, {
            "domain": DOMAIN,
            "concepts": [c[0] for c in CONCEPTS],
            "anchored_to": "item_master.lock.json sha256 27b210b3...",
            "excluded_items": {h: w for h, (_, w) in EXCLUDED.items()},
        })
    print(f"\n= {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
