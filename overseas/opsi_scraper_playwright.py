#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OECD OPSI 수집 — Playwright(진짜 브라우저) 판. Cloudflare 봇차단 우회용.

opsi_scraper.py(requests 판)가 Cloudflare "Just a moment..." 챌린지에 막힐 때 쓴다.
헤드리스 Chromium으로 사이트를 먼저 열어 Cloudflare 통과(clearance 쿠키 획득) 후,
같은 브라우저 컨텍스트로 WordPress REST API를 페이지 단위 호출한다. 파싱·DB 저장
로직은 opsi_scraper.py 를 그대로 재사용한다(같은 opsi_policies.db).

준비:
    pip install playwright
    playwright install chromium

사용:
    python overseas/opsi_scraper_playwright.py --discover
    python overseas/opsi_scraper_playwright.py --post-type case_study --max-pages 3
    python overseas/opsi_scraper_playwright.py --post-type case_study --headful   # 차단 심할 때

유의:
  · 이는 사람이 브라우저로 여는 것과 같은 접근이나, Cloudflare 봇보호를 지나는 것이므로
    대상 사이트의 이용약관(ToS)을 확인하고 요청 간격을 지켜 존중해서 쓴다.
  · KDI 등 기관이라면, 대량 수집 전 OECD OPSI에 데이터 제공을 공식 문의하는 편이 가장 안전하다.
"""
import argparse
import logging
import random
import sqlite3
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright 가 필요합니다:  pip install playwright  &&  playwright install chromium")

# 파싱·DB·설정은 requests 판과 공유(중복 방지).
from opsi_scraper import (CONFIG, DB_PATH, init_db, upsert_case, parse_post, _UA)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("opsi-pw")


def _pass_cloudflare(page, base, wait_s=45):
    """홈페이지를 열어 Cloudflare 챌린지를 통과할 때까지 기다린다."""
    log.info("Cloudflare 통과 시도: %s", base)
    page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
    for i in range(wait_s):
        title = (page.title() or "").lower()
        if "just a moment" not in title and "attention required" not in title:
            log.info("Cloudflare 통과됨(제목: %s)", page.title()[:40])
            return True
        page.wait_for_timeout(1000)
    log.warning("Cloudflare 통과 확인 실패(%d초). --headful 로 다시 시도해 보세요.", wait_s)
    return False


def _req_json(ctx, url):
    resp = ctx.request.get(url, timeout=CONFIG["timeout"] * 1000)
    if not resp.ok:
        log.error("HTTP %d %s | %s", resp.status, url, (resp.text() or "")[:200].replace("\n", " "))
        return None, {}
    try:
        return resp.json(), resp.headers
    except Exception:
        log.error("JSON 파싱 실패: %s", url)
        return None, {}


def discover(ctx, base):
    data, _ = _req_json(ctx, f"{base}/wp-json/wp/v2/types")
    if not data:
        log.error("types 를 못 읽음. --headful 로 재시도하거나 /wp-json/ 을 브라우저로 확인.")
        return
    print("\n=== 포스트 타입(CPT) ===")
    for slug, info in data.items():
        print(f"  · {slug:20s} rest_base={info.get('rest_base', slug):20s} {info.get('name','')}")
    tax, _ = _req_json(ctx, f"{base}/wp-json/wp/v2/taxonomies")
    if tax:
        print("\n=== 분류(taxonomy) ===")
        for slug, info in tax.items():
            print(f"  · {slug:20s} rest_base={info.get('rest_base', slug)}")
    print("\n→ 사례 rest_base 를 --post-type, 국가/분야 slug 을 --tax-country/--tax-sector 로.")


def scrape(ctx, base, post_type, max_pages=None):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    page_no, saved, total_pages = 1, 0, None
    try:
        while True:
            if max_pages and page_no > max_pages:
                break
            url = (f"{base}/wp-json/wp/v2/{post_type}"
                   f"?per_page={CONFIG['per_page']}&page={page_no}&_embed=1")
            data, headers = _req_json(ctx, url)
            if total_pages is None and headers:
                total_pages = headers.get("x-wp-totalpages")
                if headers.get("x-wp-total"):
                    log.info("전체 %s건 · 총 %s페이지", headers.get("x-wp-total"), total_pages)
            if not data:
                break
            for post in data:
                try:
                    rec = parse_post(post)
                    if rec["id"]:
                        upsert_case(conn, rec)
                        saved += 1
                except Exception as e:
                    log.warning("파싱 실패(id=%s): %s", post.get("id"), e)
            conn.commit()
            log.info("page %s%s 저장 · 누적 %d건",
                     page_no, f"/{total_pages}" if total_pages else "", saved)
            if total_pages and page_no >= int(total_pages):
                break
            page_no += 1
    finally:
        conn.close()
    log.info("완료: 총 %d건 UPSERT · DB=%s", saved, DB_PATH)


def main():
    ap = argparse.ArgumentParser(description="OECD OPSI 수집(Playwright 판)")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--post-type", help="사례 CPT rest_base (기본 %s)" % CONFIG["post_type"])
    ap.add_argument("--tax-country")
    ap.add_argument("--tax-sector")
    ap.add_argument("--base-url")
    ap.add_argument("--max-pages", type=int)
    ap.add_argument("--headful", action="store_true", help="브라우저 창을 띄워 실행(차단 심할 때)")
    args = ap.parse_args()

    if args.base_url:
        CONFIG["base_url"] = args.base_url
    if args.post_type:
        CONFIG["post_type"] = args.post_type
    if args.tax_country:
        CONFIG["tax_country"] = args.tax_country
    if args.tax_sector:
        CONFIG["tax_sector"] = args.tax_sector
    base = CONFIG["base_url"].rstrip("/")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headful)
        ctx = browser.new_context(
            user_agent=_UA, locale="en-US", viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        _pass_cloudflare(page, base)
        # 살짝 지연(사람스러운 간격)
        page.wait_for_timeout(int(random.uniform(800, 1800)))
        if args.discover:
            discover(ctx, base)
        else:
            scrape(ctx, base, CONFIG["post_type"], max_pages=args.max_pages)
        browser.close()


if __name__ == "__main__":
    main()
