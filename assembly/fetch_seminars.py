#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국회 토론회 레이더 - 일일 수집기.

열린국회정보(open.assembly.go.kr) Open API에서 국회의원 세미나/토론회 일정을
받아 정규화한 뒤 docs/seminars.json 으로 저장한다. 이 JSON 을 index.html 이
window.__DATA_URL__ 로 읽어 표시한다.

키는 코드에 두지 않는다. 환경변수 ASSEMBLY_API_KEY 로 주입한다.
(GitHub Actions 에서는 Secrets -> env 로 전달)

사용:
    ASSEMBLY_API_KEY=xxxx python assembly/fetch_seminars.py
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))

# 열린국회정보 서비스 ID.
#  - SEMINAR  : 국회의원 세미나 일정 (예정/일정)
#  - HOSTING  : 세미나 개최현황 (발제자/토론자 등 지난 행사 정보)
# 필요시 env 로 덮어쓸 수 있다.
SERVICES = {
    "seminar": os.environ.get("ASSEMBLY_SERVICE_SEMINAR", "nfcoioopazrwmjrgs"),
    "hosting": os.environ.get("ASSEMBLY_SERVICE_HOSTING", "nbqbmccpamsvwebkn"),
}
BASE = "https://open.assembly.go.kr/portal/openapi/{service}"
PAGE_SIZE = 100
MAX_PAGES = 10  # 안전장치: 최대 1000건

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "seminars.json")


def pick(row, *names):
    """후보 필드명들 중 처음으로 값이 있는 것을 문자열로 반환."""
    for name in names:
        v = row.get(name)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def clean_date(value):
    s = re.sub(r"[.]", "-", str(value or ""))
    m = re.search(r"(\d{4})-?(\d{1,2})-?(\d{1,2})", s)
    if not m:
        return str(value or "").strip()
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def extract_time(value):
    m = re.search(r"(\d{1,2}:\d{2})", str(value or ""))
    return m.group(1) if m else ""


def normalize(row, kind=""):
    """index.html 의 normalizeEvent 와 동일한 출력 형태로 맞춘다."""
    raw_date = pick(row, "SDATE", "HOST_DT", "date", "DATE", "SEMINAR_DATE",
                    "EVENT_DT", "EVT_DT", "START_DE", "FR_DT", "DT")
    time = pick(row, "STIME", "time", "TIME", "SEMINAR_TIME", "EVENT_TIME",
                "EVT_TIME", "START_TIME") or extract_time(raw_date)
    return {
        "title": pick(row, "TITLE", "title", "SEMINAR_TITLE", "EVENT_TITLE",
                      "EVT_NM", "EVENT_NM", "BBS_SJ", "SJ"),
        "date": clean_date(raw_date),
        "time": time,
        "place": pick(row, "LOCATION", "HOST_PLACE_NAME", "place", "PLACE",
                      "SEMINAR_PLACE", "EVENT_PLACE", "EVT_PLACE", "PLC", "LC"),
        "host": pick(row, "NAME", "HOST_INS_NAME", "host", "HOST", "HOST_NM",
                     "MNA_NM", "POLY_NM", "RPRS_NM", "HG_NM"),
        "cohost": pick(row, "cohost", "COHOST", "JOINT_HOST", "ORGANIZER",
                       "ORGNZT_NM", "SPONSOR"),
        "committee": pick(row, "committee", "COMMITTEE", "CMIT_NM",
                          "COMMITTEE_NM", "CMT_NM"),
        "link": pick(row, "LINK", "DETAIL_VIEW_URL", "link", "URL",
                     "DETAIL_URL", "HMPG_URL"),
        "text": pick(row, "DESCRIPTION", "text", "CONTENT", "SUMMARY",
                     "RM", "DESC", "CN"),
        "presenters": pick(row, "presenters", "ATTENDANCE_NAME1"),
        "discussants": pick(row, "discussants", "ATTENDANCE_NAME2"),
        "kind": kind,
    }


def result_code(payload):
    """open.assembly.go.kr 응답의 head.RESULT.CODE 를 추출 (에러 봉투 처리)."""
    def walk(v):
        if isinstance(v, list):
            for item in v:
                code = walk(item)
                if code:
                    return code
        elif isinstance(v, dict):
            if "RESULT" in v and isinstance(v["RESULT"], dict):
                return v["RESULT"].get("CODE")
            for item in v.values():
                code = walk(item)
                if code:
                    return code
        return None
    return walk(payload)


def extract_rows(payload):
    """응답 어디에 있든 row 배열을 모아서 반환."""
    rows = []

    def walk(v):
        if isinstance(v, list):
            for item in v:
                walk(item)
        elif isinstance(v, dict):
            if isinstance(v.get("row"), list):
                rows.extend(v["row"])
            for item in v.values():
                walk(item)
    walk(payload)
    return rows


def fetch_service(service_id, key, kind):
    """한 서비스에서 전 페이지를 받아 정규화 리스트로 반환."""
    out = []
    for p_index in range(1, MAX_PAGES + 1):
        params = {
            "KEY": key,
            "Type": "json",
            "pIndex": p_index,
            "pSize": PAGE_SIZE,
        }
        url = BASE.format(service=service_id)
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        try:
            payload = resp.json()
        except ValueError:
            raise RuntimeError(f"{service_id}: JSON 이 아닌 응답: {resp.text[:200]}")

        code = result_code(payload)
        if code and code not in ("INFO-000",):
            # INFO-200 = 데이터 없음(정상 종료), 그 외는 키/권한 오류 등
            if code == "INFO-200":
                break
            raise RuntimeError(f"{service_id}: API 오류 코드 {code}")

        rows = extract_rows(payload)
        if not rows:
            break
        out.extend(normalize(r, kind) for r in rows)
        if len(rows) < PAGE_SIZE:
            break
    return out


def dedup(events):
    seen = set()
    result = []
    for e in events:
        key = (
            re.sub(r"\s+", "", e["title"]),
            e["date"],
            re.sub(r"\s+", "", e["place"]),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(e)
    return result


def main():
    key = os.environ.get("ASSEMBLY_API_KEY", "").strip()
    if not key:
        sys.stderr.write(
            "ERROR: ASSEMBLY_API_KEY 환경변수가 없습니다. "
            "GitHub Secrets 또는 .env 로 설정하세요.\n"
        )
        return 1

    events = []
    errors = []
    for kind, service_id in (("upcoming", SERVICES["seminar"]),
                             ("past", SERVICES["hosting"])):
        try:
            fetched = fetch_service(service_id, key, kind)
            sys.stderr.write(f"{service_id} ({kind}): {len(fetched)}건\n")
            events.extend(fetched)
        except Exception as exc:  # noqa: BLE001 - 한 서비스 실패가 전체를 막지 않게
            errors.append(f"{service_id}: {exc}")
            sys.stderr.write(f"WARN {service_id}: {exc}\n")

    events = [e for e in events if e["title"] or e["date"]]
    events = dedup(events)

    if not events and errors:
        sys.stderr.write("수집된 행사가 없고 모든 서비스가 실패했습니다. JSON 미갱신.\n")
        return 2

    out = {
        "generatedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "count": len(events),
        "events": events,
    }
    os.makedirs(os.path.dirname(os.path.abspath(OUT_PATH)), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"저장: {OUT_PATH} ({len(events)}건)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
