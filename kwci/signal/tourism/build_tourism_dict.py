#!/usr/bin/env python3
"""
KWCI L3 — K-관광 토픽·키워드 사전 생성

기존 486행 사전의 KTOURISM 대역은 국가당 2행뿐이고, 36행 중 33행이 영어
질의다. KPOP은 고유명(BLACKPINK)이라 언어 중립이지만 관광은 아니다. 일본인은
"South Korea tourism"이 아니라 "韓国 旅行"으로 검색한다. 지금 상태로는 각국의
영어 검색 가능 소수층을 재고 있고 그 비율은 국가마다 다르므로, 브리핑 통찰 ①
("두 개의 자")이 요구하는 횡단 비교가 성립하지 않는다.

설계 원칙
--------
1. 손으로 고르지 않는다.  "이 검색어는 한류다"라고 선언하면 L1에서 BEC·RCA로
   쌓은 방법론적 결백이 L3에서 무너진다. 사전은 다음 곱으로 기계 생성한다.

       질의 = 의도어 문법(고정 10종) x 국가별 현지어(공식 언어)

   의도어 문법은 목적지를 가리지 않는 닫힌 집합이다. 한국에만 적용되는
   특별한 어휘가 없으므로 연구자 재량이 들어갈 자리가 없다.

2. 같은 문법을 위약 목적지에 적용한다.  일본·태국행 여행 검색이 P01/P02 다.
   "한국 여행 검색이 늘었다"는 코로나 회복이나 전반적 해외여행 붐일 수 있다.
   같은 국가에서 같은 문법으로 잰 일본·태국 계열을 통제하지 않으면 한국
   고유의 인력(引力)을 분리할 수 없다. 위약에서도 계수가 유의하면 통제가
   불충분한 것이므로 결과를 채택하지 않는다.

3. topic MID 를 지어내지 않는다.  MID 는 Trends DOM 에서 실측해야 얻는다.
   기존 사전에서 이미 검증된 MID 두 개만 승계하고(언어 중립이므로 국가 간
   이전 가능), 나머지는 keyword 단위로 낸다. 지명·위약은 의도어가 붙어야
   여행 의도를 재므로 애초에 topic 이 아니라 keyword 가 맞다 — "Seoul"
   단독은 뉴스 관심을 재고 "ソウル 旅行"은 여행 의도를 잰다.

중국
----
제외한다. Google Trends 가 차단된 시장이라 신호가 구조적으로 결측이다.
L1 에서 중국이 K-Beauty·K-Fashion 수출 1위인 것과 대비되는 측정 사각지대이며,
조용히 빼면 표본이 편향되므로 문서에 명시한다. 기존 486행 사전에도 중국은
없어 국가 명단은 그대로 18개국을 쓴다.

산출: ktourism_dict.csv (기존 40열 스키마 그대로)  ·  --merge 시 병합본

사용법
------
  python build_tourism_dict.py                 # 생성 + 요약
  python build_tourism_dict.py --review JP     # 특정 국가 전체 행 출력
  python build_tourism_dict.py --conflicts     # 기존 36행과의 충돌만 출력
  python build_tourism_dict.py --merge BASE.csv  # 기존 사전과 병합
  python build_tourism_dict.py --freeze        # 생성 후 sha256 동결
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import COUNTRIES, HEADER, trends_url, write, freeze  # noqa: E402

OUT = HERE / "ktourism_dict.csv"
LOCK = HERE / "ktourism_dict.lock.json"
MERGED = HERE / "KWCI_dictionary_merged.csv"

DOMAIN = "KTOURISM"
TOPIC_C02 = "/g/11h_5y_9w7"            # 기존 사전에서 IN·SA 로 검증된 MID
TOPIC_S03 = "/g/11t7fqrvlx"            # 기존 사전에서 AR 로 검증, US 는 fallback 으로 보유

# ── 의도어 문법 ─────────────────────────────────────────────────────
# 목적지를 가리지 않는 닫힌 집합. C=일반관심 · S=여행행위 · D=지명 · P=위약
# skip_geo: 자국이 목적지가 되는 조합은 무의미하므로 제외(일본에서 일본 여행).
CONCEPTS = [
    ("KTOURISM_C02", "한국 관광 일반", "topic", TOPIC_C02, None, {
        "en": "South Korea tourism",       "ja": "韓国 観光",
        "vi": "du lịch Hàn Quốc",          "th": "ท่องเที่ยว เกาหลีใต้",
        "id": "pariwisata Korea Selatan",  "fr": "tourisme Corée du Sud",
        "de": "Südkorea Tourismus",        "pt": "turismo na Coreia do Sul",
        "es": "turismo en Corea del Sur",  "tr": "Güney Kore turizm",
        "ar": "السياحة في كوريا الجنوبية",
    }),
    ("KTOURISM_S01", "항공권 (이동)", "keyword", None, None, {
        "en": "flights to Korea",          "ja": "韓国 航空券",
        "vi": "vé máy bay đi Hàn Quốc",    "th": "ตั๋วเครื่องบิน เกาหลี",
        "id": "tiket pesawat ke Korea",    "fr": "vol Corée du Sud",
        "de": "Flug Südkorea",             "pt": "passagem aérea Coreia do Sul",
        "es": "vuelos a Corea del Sur",    "tr": "Güney Kore uçak bileti",
        "ar": "تذاكر طيران إلى كوريا الجنوبية",
    }),
    ("KTOURISM_S02", "숙박", "keyword", None, None, {
        "en": "Seoul hotels",              "ja": "ソウル ホテル",
        "vi": "khách sạn Seoul",           "th": "โรงแรม โซล",
        "id": "hotel Seoul",               "fr": "hôtel Séoul",
        "de": "Hotel Seoul",               "pt": "hotéis em Seul",
        "es": "hoteles en Seúl",           "tr": "Seul otel",
        "ar": "فنادق سيول",
    }),
    ("KTOURISM_S03", "투어 패키지", "topic", TOPIC_S03, None, {
        "en": "Korea tour packages",       "ja": "韓国 ツアー",
        "vi": "tour Hàn Quốc",             "th": "ทัวร์ เกาหลี",
        "id": "paket tour Korea",          "fr": "séjour Corée du Sud",
        "de": "Südkorea Pauschalreise",    "pt": "pacote de viagem Coreia do Sul",
        "es": "paquete turístico Corea del Sur", "tr": "Güney Kore turu",
        "ar": "رحلات كوريا الجنوبية",
    }),
    ("KTOURISM_S04", "비자·입국", "keyword", None, None, {
        "en": "Korea visa",                "ja": "韓国 ビザ",
        "vi": "visa Hàn Quốc",             "th": "วีซ่า เกาหลี",
        "id": "visa Korea",                "fr": "visa Corée du Sud",
        "de": "Südkorea Visum",            "pt": "visto Coreia do Sul",
        "es": "visa Corea del Sur",        "tr": "Güney Kore vizesi",
        "ar": "تأشيرة كوريا الجنوبية",
    }),
    ("KTOURISM_D01", "서울", "keyword", None, None, {
        "en": "Seoul travel",              "ja": "ソウル 旅行",
        "vi": "du lịch Seoul",             "th": "เที่ยว โซล",
        "id": "wisata Seoul",              "fr": "voyage Séoul",
        "de": "Seoul Reise",               "pt": "viagem para Seul",
        "es": "viaje a Seúl",              "tr": "Seul gezisi",
        "ar": "السفر إلى سيول",
    }),
    ("KTOURISM_D02", "부산", "keyword", None, None, {
        "en": "Busan travel",              "ja": "釜山 旅行",
        "vi": "du lịch Busan",             "th": "เที่ยว ปูซาน",
        "id": "wisata Busan",              "fr": "voyage Busan",
        "de": "Busan Reise",               "pt": "viagem para Busan",
        "es": "viaje a Busan",             "tr": "Busan gezisi",
        "ar": "السفر إلى بوسان",
    }),
    ("KTOURISM_D03", "제주", "keyword", None, None, {
        "en": "Jeju Island travel",        "ja": "済州島 旅行",
        "vi": "du lịch đảo Jeju",          "th": "เที่ยว เชจู",
        "id": "wisata Pulau Jeju",         "fr": "voyage île de Jeju",
        "de": "Jeju Reise",                "pt": "viagem para Jeju",
        "es": "viaje a Jeju",              "tr": "Jeju gezisi",
        "ar": "السفر إلى جيجو",
    }),
    ("KTOURISM_P01", "[위약] 일본 여행", "keyword", None, "JP", {
        "en": "Japan travel",              "ja": "",
        "vi": "du lịch Nhật Bản",          "th": "เที่ยว ญี่ปุ่น",
        "id": "wisata Jepang",             "fr": "voyage Japon",
        "de": "Japan Reise",               "pt": "viagem para o Japão",
        "es": "viaje a Japón",             "tr": "Japonya gezisi",
        "ar": "السفر إلى اليابان",
    }),
    ("KTOURISM_P02", "[위약] 태국 여행", "keyword", None, "TH", {
        "en": "Thailand travel",           "ja": "タイ 旅行",
        "vi": "du lịch Thái Lan",          "th": "",
        "id": "wisata Thailand",           "fr": "voyage Thaïlande",
        "de": "Thailand Reise",            "pt": "viagem para a Tailândia",
        "es": "viaje a Tailandia",         "tr": "Tayland gezisi",
        "ar": "السفر إلى تايلاند",
    }),
]

# 기존 486행 사전이 이 두 개념을 영어 질의로 이미 담고 있다. 현지어로 바꾸면
# 같은 concept_id 에 두 행이 생기므로 병합 시 택일해야 한다.
EXISTING = {"KTOURISM_C02", "KTOURISM_S03"}

# 개념별 잔여 위험. 사전이 못 잡는 것을 사전 안에 적어 둔다.
RISK = {
    "KTOURISM_S04": "무비자 국가(US·GB·FR·DE·JP·AU 등)에서는 K-ETA 검색이 "
                    "대부분이라 입국 의도 강도가 국가별로 비대칭",
    "KTOURISM_S02": "숙박은 서울로 고정 — 지방 체류 의도를 놓친다",
    "KTOURISM_D02": "Busan 은 영화제·엑스포 유치 뉴스로 여행 무관 급등 가능",
    "KTOURISM_P01": "위약이지만 한일 노선은 대체재 관계라 음(-)의 상관 가능 — "
                    "계수 부호까지 함께 볼 것",
}


def build() -> list[dict]:
    rows: list[dict] = []
    for cc, (cname, lang) in COUNTRIES.items():
        for cid, label, unit, mid, skip_geo, terms in CONCEPTS:
            if skip_geo == cc:
                continue                      # 자국 목적지 위약은 무의미
            local = terms.get(lang, "")
            if not local:
                continue
            # topic MID 를 승계하는 개념은 topic 으로, 아니면 현지어 keyword 로.
            # 승계 MID 가 있어도 현지어 질의는 fallback 에 남겨 대조 가능하게 둔다.
            is_topic = unit == "topic" and mid
            query = mid if is_topic else local
            rows.append({
                "measurement_unit_id": f"{cc}|{DOMAIN}|{cid}",
                "country_code": cc,
                "domain_code": DOMAIN,
                "concept_id": cid,
                "entity_id": "",
                "final_unit_type": "topic" if is_topic else "keyword",
                "final_query": query,
                "topic_mid": mid or "",
                "query_language": "und" if is_topic else lang,
                "selection_basis": "RULE_GRAMMAR",
                "selection_status": "RULE_SELECTED",
                "validation_status": ("INHERITED_VALIDATED_MID" if is_topic
                                      else "PENDING_EMPIRICAL"),
                "signal_status": "UNKNOWN",
                "confidence_level": "INHERITED" if is_topic else "PENDING",
                "empirical_validation_status": "NOT_YET_TESTED",
                "technical_status": ("NOT_TECHNICAL" if is_topic
                                     else "PENDING_DOM_EXTRACTION"),
                "technical_attempt_count": "",
                "extraction_method": ("MID_PROPAGATED" if is_topic
                                      else "RULE_GENERATED"),
                "model_consensus": "", "model_confidence": "",
                "score_margin": "",
                "exact_validated_other_countries": ("IN,SA" if cid == "KTOURISM_C02"
                                                    else "AR" if cid == "KTOURISM_S03"
                                                    else ""),
                "official_name_check": "",
                "topic_mid_format_check": "PASS" if is_topic else "N/A",
                "ambiguity_flag": "",
                "selection_rule": "GRAMMAR-LOCALIZED-1.0",
                "second_pass_decision": "NOT_REQUIRED",
                "second_pass_confidence": "",
                "final_review_status": "PENDING_EMPIRICAL_VALIDATION",
                "concept_valid_keyword_count": "",
                "concept_low_keyword_count": "",
                "concept_valid_keyword_countries": "",
                "concept_low_keyword_countries": "",
                "fallback_query": local if is_topic else "",
                "source_url": trends_url(cc, query),
                "inclusion_reason": f"의도어 문법 {cid}({label}) x {cname} 현지어({lang})",
                "review_reason": ("기존 사전에 같은 concept_id 가 영어 질의로 존재 — "
                                  "병합 시 택일 필요" if cid in EXISTING else ""),
                "remaining_risk": RISK.get(cid, ""),
                "notes": label,
                "source_record_set": "KTOURISM_GRAMMAR_V1",
            })
    return rows


def summary(rows: list[dict]) -> None:
    print(f"\n{'=' * 70}\nK-관광 사전  {len(rows)}행  =  "
          f"{len(COUNTRIES)}개국 x 개념 {len(CONCEPTS)}종 - 자국위약 제외\n")
    langs: dict[str, list[str]] = {}
    for cc, (_, lg) in COUNTRIES.items():
        langs.setdefault(lg, []).append(cc)
    print(f"  검색 언어 {len(langs)}종")
    for lg, ccs in sorted(langs.items()):
        print(f"    {lg:<4}{' '.join(ccs)}")

    print(f"\n  개념별")
    for cid, label, unit, mid, skip, _ in CONCEPTS:
        n = sum(1 for r in rows if r["concept_id"] == cid)
        u = "topic(승계)" if (unit == "topic" and mid) else "keyword"
        print(f"    {cid:<16}{label:<18}{u:<14}{n:>3}행"
              + (f"   {skip} 제외" if skip else ""))

    top = sum(1 for r in rows if r["final_unit_type"] == "topic")
    print(f"\n  단위  topic {top}  ·  keyword {len(rows) - top}")
    print(f"  검증  MID 승계 {top}  ·  실증 대기 {len(rows) - top}")
    print("\n  * 지어낸 MID 는 없다. 신규 개념은 전부 keyword 로 내고")
    print("    Trends DOM 실측 후 topic 승격 여부를 정한다.")


def conflicts(rows: list[dict]) -> None:
    c = [r for r in rows if r["review_reason"]]
    print(f"\n기존 사전과 concept_id 가 겹치는 행: {len(c)}\n")
    print(f"  {'국가':<5}{'개념':<16}{'신규 질의':<32}{'기존 질의'}")
    for r in c:
        old = ("South Korea tourism" if r["concept_id"] == "KTOURISM_C02"
               else "Korea tour packages")
        new = r["fallback_query"] or r["final_query"]
        print(f"  {r['country_code']:<5}{r['concept_id']:<16}{new:<32}{old} (en)")
    print("\n  기존 행은 실증을 통과했으나 33/36 이 영어 질의라 비영어권에서는")
    print("  영어 검색 가능 소수층을 잰다. --merge 는 신규(현지어)를 채택하고")
    print("  기존 행을 탈락 목록으로 출력한다. 반대로 가려면 --merge --keep-old.")


def merge(rows: list[dict], base: Path, keep_old: bool) -> None:
    with base.open(encoding="utf-8-sig") as f:
        old = list(csv.DictReader(f))
    other = [r for r in old if r["domain_code"] != DOMAIN]
    old_t = [r for r in old if r["domain_code"] == DOMAIN]

    if keep_old:
        new = [r for r in rows if r["concept_id"] not in EXISTING]
        kept, dropped = old_t, [r for r in rows if r["concept_id"] in EXISTING]
    else:
        new, kept = rows, []
        dropped = old_t

    out = other + kept + new
    with MERGED.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    print(f"\n병합  {MERGED.name}  {len(out)}행")
    print(f"  비관광 유지      {len(other):>4}")
    print(f"  관광 기존 유지   {len(kept):>4}")
    print(f"  관광 신규        {len(new):>4}")
    print(f"  탈락             {len(dropped):>4}"
          + ("  (기존 영어 질의 행)" if not keep_old else "  (신규 현지어 행)"))
    if dropped and not keep_old:
        print("\n  탈락한 기존 행은 실증을 통과했던 자료다. 사유를 남긴다:")
        print("    비영어권 33행이 영어 질의라 횡단 비교 불가 — 현지어로 대체")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", metavar="CC", help="해당 국가 전체 행 출력")
    ap.add_argument("--conflicts", action="store_true", help="기존 사전과의 충돌만")
    ap.add_argument("--merge", metavar="BASE.csv", help="기존 486행 사전과 병합")
    ap.add_argument("--keep-old", action="store_true",
                    help="--merge 시 충돌 행을 기존(영어) 쪽으로 유지")
    ap.add_argument("--freeze", action="store_true", help="생성 후 sha256 동결")
    args = ap.parse_args()

    rows = build()
    write(rows, OUT)

    if args.review:
        cc = args.review.upper()
        sel = [r for r in rows if r["country_code"] == cc]
        if not sel:
            sys.exit(f"{cc} 는 사전에 없습니다. 가능한 값: {', '.join(COUNTRIES)}")
        nm, lg = COUNTRIES[cc]
        print(f"\n{nm}({cc}) · 검색 언어 {lg} · {len(sel)}행\n")
        for r in sel:
            q = r["fallback_query"] or r["final_query"]
            print(f"  {r['concept_id']:<16}{r['final_unit_type']:<9}{q}")
            if r["final_unit_type"] == "topic":
                print(f"  {'':<16}{'':<9}MID {r['topic_mid']} (현지어는 fallback)")
        return 0

    if args.conflicts:
        conflicts(rows)
        return 0

    summary(rows)
    if args.merge:
        base = Path(args.merge)
        if not base.exists():
            sys.exit(f"{base} 를 찾을 수 없습니다.")
        merge(rows, base, args.keep_old)
    if args.freeze:
        freeze(rows, OUT, LOCK, {
            "domain": DOMAIN,
            "concepts": [c[0] for c in CONCEPTS],
        })
    print(f"\n= {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
