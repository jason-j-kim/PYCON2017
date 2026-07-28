#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apolitical 정책 사례 수집 → 로컬 SQLite (opsi_scraper.py 와 같은 구조).

※ 상태: 스캐폴드(구조 확정 필요). OPSI(WordPress REST)와 달리 Apolitical은 공개
  REST API가 불명확하고 상당 콘텐츠가 로그인·JS 렌더 뒤에 있을 수 있다. 그래서:
    1) 먼저 robots.txt·이용약관을 확인한다(--check 로 robots 확인).
    2) 실제 목록/상세 페이지 구조를 브라우저 개발자도구로 확인한 뒤,
       LISTING_URL·선택자(SELECTORS)를 채운다(아래 TODO).
    3) JS로만 렌더되면 requests+bs4로는 부족 → Playwright(headless) 경로로 전환.
  OPSI 파이프라인과 동일한 스키마(cases)를 쓰되 DB 파일만 다르다(apolitical_cases.db).

사용법:
    python overseas/apolitical_scraper.py --check         # robots.txt 확인(먼저)
    python overseas/apolitical_scraper.py --max-pages 2   # (구조 확정 후) 시험 수집
"""
import argparse
import logging
import random
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("의존성 필요:  pip install requests beautifulsoup4")

CONFIG = {
    "base_url": "https://apolitical.co",
    # TODO(확정): 정책 사례 목록 페이지 URL 패턴(페이지 번호 {page} 포함).
    "listing_url": "https://apolitical.co/en/solution_articles?page={page}",
    "timeout": 30, "sleep_min": 1.5, "sleep_max": 3.5,
    "max_retries": 4, "backoff_base": 2.0,
    # TODO(확정): 실제 페이지 구조에 맞춘 CSS 선택자.
    "selectors": {
        "card": "article",              # 목록의 사례 카드
        "link": "a",                    # 카드 안 상세 링크
        "title": "h1",                  # 상세 페이지 제목
        "body": "main",                 # 상세 페이지 본문 컨테이너
    },
}
DB_PATH = Path(__file__).resolve().parent / "apolitical_cases.db"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("apolitical")


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, title TEXT, country TEXT, sector TEXT, year INTEGER,
            raw_content TEXT, cleaned_content TEXT, source_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()


def upsert_case(conn, rec):
    conn.execute("""
        INSERT INTO cases (id,title,country,sector,year,raw_content,cleaned_content,source_url,scraped_at)
        VALUES (:id,:title,:country,:sector,:year,:raw_content,:cleaned_content,:source_url,CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET title=excluded.title, country=excluded.country,
            sector=excluded.sector, year=excluded.year, raw_content=excluded.raw_content,
            cleaned_content=excluded.cleaned_content, source_url=excluded.source_url,
            scraped_at=CURRENT_TIMESTAMP""", rec)


def clean_html(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"})
    return s


def check_robots():
    """robots.txt 를 읽어 우리 UA가 base_url 를 크롤링해도 되는지 확인한다."""
    url = urljoin(CONFIG["base_url"], "/robots.txt")
    rp = RobotFileParser(); rp.set_url(url)
    try:
        rp.read()
    except Exception as e:
        log.error("robots.txt 읽기 실패: %s", e); return
    allowed = rp.can_fetch(_UA, CONFIG["listing_url"].format(page=1))
    log.info("robots.txt(%s) 기준 목록 크롤링 허용 여부: %s", url, "허용" if allowed else "불허")
    log.info("※ robots 허용과 별개로 이용약관(ToS)도 반드시 확인할 것.")


def fetch(session, url):
    for attempt in range(1, CONFIG["max_retries"] + 1):
        try:
            r = session.get(url, timeout=CONFIG["timeout"])
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(CONFIG["backoff_base"] ** attempt); continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(CONFIG["backoff_base"] ** attempt); continue
        if r.status_code >= 400:
            log.error("HTTP %d %s", r.status_code, url); return None
        return r.text
    return None


def scrape(session, conn, max_pages=None):
    log.warning("⚠ 이 스크레이퍼는 스캐폴드입니다 — CONFIG['listing_url']·selectors 를 "
                "실제 사이트 구조로 확정한 뒤 사용하세요(로그인·JS 렌더면 Playwright 필요).")
    sel = CONFIG["selectors"]
    page, saved = 1, 0
    while True:
        if max_pages and page > max_pages:
            break
        html = fetch(session, CONFIG["listing_url"].format(page=page))
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(sel["card"])
        if not cards:
            log.info("목록에서 카드를 못 찾음(선택자 확인 필요) — 종료(page=%d)", page); break
        for card in cards:
            a = card.select_one(sel["link"])
            href = a.get("href") if a else None
            if not href:
                continue
            detail_url = urljoin(CONFIG["base_url"], href)
            dhtml = fetch(session, detail_url)
            if not dhtml:
                continue
            dsoup = BeautifulSoup(dhtml, "html.parser")
            title_el = dsoup.select_one(sel["title"])
            body_el = dsoup.select_one(sel["body"])
            rec = {
                "id": re.sub(r"[^0-9a-zA-Z]", "-", detail_url)[-64:],  # URL 기반 안정 ID
                "title": clean_html(str(title_el)) if title_el else "",
                "country": None, "sector": None, "year": None,  # TODO: 사이트에서 추출
                "raw_content": str(body_el) if body_el else "",
                "cleaned_content": clean_html(str(body_el)) if body_el else "",
                "source_url": detail_url,
            }
            upsert_case(conn, rec); saved += 1
            time.sleep(random.uniform(CONFIG["sleep_min"], CONFIG["sleep_max"]))
        conn.commit()
        log.info("page %d 저장 · 누적 %d건", page, saved)
        page += 1
    log.info("완료: %d건 · DB=%s", saved, DB_PATH)


def main():
    ap = argparse.ArgumentParser(description="Apolitical 정책 사례 수집기(스캐폴드)")
    ap.add_argument("--check", action="store_true", help="robots.txt 크롤링 허용 확인")
    ap.add_argument("--max-pages", type=int, help="시험용: 앞 N페이지만")
    args = ap.parse_args()
    session = make_session()
    if args.check:
        check_robots(); return
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn); scrape(session, conn, max_pages=args.max_pages)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
