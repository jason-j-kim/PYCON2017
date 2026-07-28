#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OECD OPSI(공공부문 혁신 관측소) 정책 사례 수집 → 로컬 SQLite 아카이브.

해외 정책 선례를 무료·주권적으로 확보하기 위한 데이터 파이프라인.
OPSI 사이트는 WordPress이므로 REST API(/wp-json/wp/v2/<post_type>)로 사례를
페이지 단위로 받아, 본문 HTML을 정제해 opsi_policies.db(테이블 cases)에 UPSERT한다.

사용법:
    python overseas/opsi_scraper.py --discover        # REST 경로·사례 타입 탐지(먼저 실행)
    python overseas/opsi_scraper.py                    # 전체 수집
    python overseas/opsi_scraper.py --max-pages 3      # 앞 3페이지만(시험)
    python overseas/opsi_scraper.py --post-type case_study --tax-country country

주의:
  · 실행 환경에서 oecd-opsi.org 로 나가는 네트워크가 열려 있어야 한다.
  · 실제 CPT 이름·분류(country/sector/year)는 사이트마다 다르므로, --discover 결과를
    보고 아래 CONFIG(또는 인자)로 맞춘다. 확정 전에는 일부 필드가 비어 있을 수 있다.
  · 대상 서버를 존중한다 — 요청 간 지연·재시도를 둔다. robots.txt·이용약관을 확인할 것.
"""
import argparse
import json
import logging
import random
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests 가 필요합니다:  pip install requests beautifulsoup4")
try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("beautifulsoup4 가 필요합니다:  pip install beautifulsoup4")

# ── 설정(사이트 확정 후 여기 또는 CLI 인자로 조정) ────────────────────────
CONFIG = {
    "base_url": "https://oecd-opsi.org",
    # OPSI 사례의 WordPress 커스텀 포스트 타입(CPT). --discover 로 실제 이름 확인.
    "post_type": "case_study",
    "per_page": 100,               # WordPress REST 최대 100
    "timeout": 30,
    "sleep_min": 1.2,              # 요청 간 지연(초) — 서버 존중
    "sleep_max": 3.0,
    "max_retries": 4,
    "backoff_base": 2.0,           # 재시도 대기: base^n 초
    # 분류(taxonomy)·필드 이름 — 사이트마다 다르다. _embed 결과에서 매칭에 쓴다.
    "tax_country": "country",      # 국가 분류 slug 후보
    "tax_sector": "sector",        # 분야 분류 slug 후보
    "acf_year_keys": ["year", "introduction_year", "start_year"],  # 연도 후보 필드
}
DB_PATH = Path(__file__).resolve().parent / "opsi_policies.db"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("opsi")


# ── DB ────────────────────────────────────────────────────────────────────
def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id              TEXT PRIMARY KEY,
            title           TEXT,
            country         TEXT,
            sector          TEXT,
            year            INTEGER,
            raw_content     TEXT,
            cleaned_content TEXT,
            source_url      TEXT,
            scraped_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
    conn.commit()


def upsert_case(conn, rec):
    """id 기준 UPSERT — 있으면 갱신, 없으면 삽입(중복 방지). scraped_at 갱신."""
    conn.execute("""
        INSERT INTO cases (id, title, country, sector, year,
                           raw_content, cleaned_content, source_url, scraped_at)
        VALUES (:id, :title, :country, :sector, :year,
                :raw_content, :cleaned_content, :source_url, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title, country=excluded.country, sector=excluded.sector,
            year=excluded.year, raw_content=excluded.raw_content,
            cleaned_content=excluded.cleaned_content, source_url=excluded.source_url,
            scraped_at=CURRENT_TIMESTAMP
    """, rec)


# ── HTTP (재시도·지연) ─────────────────────────────────────────────────────
def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "application/json"})
    return s


def polite_sleep():
    time.sleep(random.uniform(CONFIG["sleep_min"], CONFIG["sleep_max"]))


def get_json(session, url, params=None):
    """GET → JSON. 429·5xx·커넥션 오류 시 지수 백오프로 재시도.
    반환: (data, headers). 4xx(429 제외)면 (None, resp.headers)."""
    for attempt in range(1, CONFIG["max_retries"] + 1):
        try:
            r = session.get(url, params=params, timeout=CONFIG["timeout"])
        except (requests.ConnectionError, requests.Timeout) as e:
            wait = CONFIG["backoff_base"] ** attempt
            log.warning("연결 오류(%s) — %.0f초 후 재시도 (%d/%d)",
                        e.__class__.__name__, wait, attempt, CONFIG["max_retries"])
            time.sleep(wait)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            wait = CONFIG["backoff_base"] ** attempt
            log.warning("HTTP %d — %.0f초 후 재시도 (%d/%d)",
                        r.status_code, wait, attempt, CONFIG["max_retries"])
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            log.error("HTTP %d %s", r.status_code, url)
            return None, r.headers
        try:
            return r.json(), r.headers
        except ValueError:
            log.error("JSON 파싱 실패: %s", url)
            return None, r.headers
    log.error("재시도 초과: %s", url)
    return None, {}


# ── 탐지 모드: 어떤 REST 경로·CPT가 있는지 알아본다 ──────────────────────────
def discover(session):
    base = CONFIG["base_url"].rstrip("/")
    log.info("REST 루트 탐지: %s/wp-json/wp/v2/types", base)
    data, _ = get_json(session, f"{base}/wp-json/wp/v2/types")
    if not data:
        log.error("wp/v2/types 를 못 읽음. 이 사이트가 WordPress REST를 열지 않았을 수 있음.")
        log.error("→ 브라우저로 %s/wp-json/ 을 열어 사용 가능한 경로를 확인하세요.", base)
        return
    print("\n=== 사용 가능한 포스트 타입(CPT) ===")
    for slug, info in data.items():
        rest = info.get("rest_base") or slug
        print(f"  · {slug:20s} rest_base={rest:20s} {info.get('name','')}")
    print("\n→ 사례에 해당하는 rest_base 를 --post-type 값으로 쓰세요.")
    log.info("분류(taxonomy) 탐지: %s/wp-json/wp/v2/taxonomies", base)
    tax, _ = get_json(session, f"{base}/wp-json/wp/v2/taxonomies")
    if tax:
        print("\n=== 사용 가능한 분류(taxonomy) ===")
        for slug, info in tax.items():
            print(f"  · {slug:20s} rest_base={info.get('rest_base', slug)}")
        print("\n→ 국가·분야 분류의 slug 를 --tax-country / --tax-sector 로 지정하세요.")


# ── 정제 ──────────────────────────────────────────────────────────────────
def clean_html(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _pick_year(text_fields):
    """연도 후보 문자열들에서 19xx/20xx 4자리 연도를 뽑는다."""
    for v in text_fields:
        if v is None:
            continue
        m = re.search(r"\b(19|20)\d{2}\b", str(v))
        if m:
            return int(m.group(0))
    return None


def extract_terms(post, tax_slug):
    """_embedded['wp:term'] 에서 특정 분류(tax_slug)의 용어 이름들을 모은다."""
    names = []
    for group in (post.get("_embedded", {}) or {}).get("wp:term", []) or []:
        for term in group or []:
            if term.get("taxonomy") == tax_slug and term.get("name"):
                names.append(term["name"])
    return ", ".join(dict.fromkeys(names)) if names else None


def parse_post(post):
    """WordPress REST 사례 1건 → cases 레코드 dict."""
    title = (post.get("title") or {}).get("rendered", "")
    raw = (post.get("content") or {}).get("rendered", "")
    acf = post.get("acf") or {}
    year = _pick_year(
        [acf.get(k) for k in CONFIG["acf_year_keys"]]
        + [post.get("date", "")]  # 최후: 게시일 연도
    )
    return {
        "id": str(post.get("id")),
        "title": clean_html(title),
        "country": extract_terms(post, CONFIG["tax_country"]),
        "sector": extract_terms(post, CONFIG["tax_sector"]),
        "year": year,
        "raw_content": raw,
        "cleaned_content": clean_html(raw),
        "source_url": post.get("link"),
    }


# ── 수집 루프(페이징) ──────────────────────────────────────────────────────
def scrape(session, conn, max_pages=None):
    base = CONFIG["base_url"].rstrip("/")
    endpoint = f"{base}/wp-json/wp/v2/{CONFIG['post_type']}"
    page, saved, total_pages = 1, 0, None
    log.info("수집 시작: %s (per_page=%d)", endpoint, CONFIG["per_page"])
    while True:
        if max_pages and page > max_pages:
            log.info("최대 페이지(%d) 도달 — 중단", max_pages)
            break
        data, headers = get_json(session, endpoint, params={
            "per_page": CONFIG["per_page"], "page": page, "_embed": "1"})
        if total_pages is None:
            total_pages = headers.get("X-WP-TotalPages")
            total = headers.get("X-WP-Total")
            if total:
                log.info("전체 사례 %s건 · 총 %s페이지", total, total_pages)
        if not data:
            # 마지막 페이지 초과 시 WP는 400(rest_post_invalid_page_number)을 준다 → 정상 종료
            log.info("더 이상 데이터 없음 — 종료(page=%d)", page)
            break
        for post in data:
            try:
                rec = parse_post(post)
                if not rec["id"]:
                    continue
                upsert_case(conn, rec)
                saved += 1
            except Exception as e:
                log.warning("사례 파싱 실패(id=%s): %s", post.get("id"), e)
        conn.commit()
        log.info("page %s%s 저장 완료 · 누적 %d건",
                 page, f"/{total_pages}" if total_pages else "", saved)
        if total_pages and page >= int(total_pages):
            break
        page += 1
        polite_sleep()
    log.info("완료: 총 %d건 UPSERT · DB=%s", saved, DB_PATH)
    return saved


# ── main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="OECD OPSI 정책 사례 수집기")
    ap.add_argument("--discover", action="store_true", help="REST 경로·CPT·분류 탐지")
    ap.add_argument("--post-type", help="사례 CPT rest_base (기본 %s)" % CONFIG["post_type"])
    ap.add_argument("--tax-country", help="국가 분류 slug")
    ap.add_argument("--tax-sector", help="분야 분류 slug")
    ap.add_argument("--base-url", help="사이트 주소(기본 %s)" % CONFIG["base_url"])
    ap.add_argument("--max-pages", type=int, help="시험용: 앞 N페이지만")
    args = ap.parse_args()

    if args.base_url:
        CONFIG["base_url"] = args.base_url
    if args.post_type:
        CONFIG["post_type"] = args.post_type
    if args.tax_country:
        CONFIG["tax_country"] = args.tax_country
    if args.tax_sector:
        CONFIG["tax_sector"] = args.tax_sector

    session = make_session()
    if args.discover:
        discover(session)
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        scrape(session, conn, max_pages=args.max_pages)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
