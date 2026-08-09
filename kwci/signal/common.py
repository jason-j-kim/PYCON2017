#!/usr/bin/env python3
"""
KWCI L3 — 사전 공용 규약

국가 명단·40열 스키마·Trends URL 규칙은 도메인마다 같아야 한다. 도메인별
파일에 복사해 두면 한쪽만 고쳐져 사전이 갈라진다. 여기 한 벌만 둔다.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

# L1 패널의 기준연도(2018)와 시작점을 맞춘다. 같은 기준연도로 지수화할 수 있다.
DATE_RANGE = "2018-01-01 2026-08-09"

# ── 국가 → 검색 언어 ────────────────────────────────────────────────
# 기존 486행 사전의 18개국. 언어는 "그 나라 사람이 실제로 검색창에 쓰는 말"
# 기준이며 공용어와 다를 수 있다. IN·MY 는 공식 다국어 국가지만 웹 검색은
# 영어가 지배적이라 en 으로 둔다(이 판단은 규칙이 아니라 재량이므로 각 행의
# remaining_risk 에 기록한다).
#
# 중국은 없다. Google Trends 가 차단된 시장이라 신호가 구조적으로 결측이며,
# L1 에서 K-Food·K-Beauty·K-Fashion 수출 상위 시장인 것과 대비되는 사각지대다.
COUNTRIES = {
    "US": ("미국", "en"),        "GB": ("영국", "en"),
    "AU": ("호주", "en"),        "ZA": ("남아공", "en"),
    "IN": ("인도", "en"),        "MY": ("말레이시아", "en"),
    "JP": ("일본", "ja"),        "VN": ("베트남", "vi"),
    "TH": ("태국", "th"),        "ID": ("인도네시아", "id"),
    "FR": ("프랑스", "fr"),      "DE": ("독일", "de"),
    "BR": ("브라질", "pt"),      "MX": ("멕시코", "es"),
    "AR": ("아르헨티나", "es"),  "TR": ("튀르키예", "tr"),
    "AE": ("아랍에미리트", "ar"), "SA": ("사우디아라비아", "ar"),
}

# 기존 486행 사전과 40열 동일. 순서까지 같아야 그대로 이어붙는다.
HEADER = [
    "measurement_unit_id", "country_code", "domain_code", "concept_id",
    "entity_id", "final_unit_type", "final_query", "topic_mid",
    "query_language", "selection_basis", "selection_status",
    "validation_status", "signal_status", "confidence_level",
    "empirical_validation_status", "technical_status",
    "technical_attempt_count", "extraction_method", "model_consensus",
    "model_confidence", "score_margin", "exact_validated_other_countries",
    "official_name_check", "topic_mid_format_check", "ambiguity_flag",
    "selection_rule", "second_pass_decision", "second_pass_confidence",
    "final_review_status", "concept_valid_keyword_count",
    "concept_low_keyword_count", "concept_valid_keyword_countries",
    "concept_low_keyword_countries", "fallback_query", "source_url",
    "inclusion_reason", "review_reason", "remaining_risk", "notes",
    "source_record_set",
]


def trends_url(geo: str, q: str) -> str:
    return (f"https://trends.google.com/trends/explore"
            f"?date={quote(DATE_RANGE)}&geo={geo}"
            f"&q={quote(q, safe='')}&hl=en")


def write(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def freeze(rows: list[dict], out: Path, lock: Path, extra: dict) -> None:
    """품목 마스터와 같은 규약. 결과를 보고 질의를 고치면 검정이 무효가 된다."""
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    body = {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": out.name,
        "sha256": digest,
        "rows": len(rows),
        "countries": len(COUNTRIES),
        "excluded": {"CN": "Google Trends 차단 — 신호 구조적 결측"},
        "note": "사전등록: 신호 수집·회귀 결과를 보고 이 질의를 수정하면 검정이 "
                "무효가 된다. 실증 실패(무신호)로 인한 탈락은 결과가 아니라 "
                "기술적 사유이므로 예외이며 technical_status 에 기록한다.",
    }
    body.update(extra)
    lock.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\n동결 완료  {lock.name}\n  sha256 {digest}")
