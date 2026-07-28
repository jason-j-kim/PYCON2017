#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OECD OPSI 수집 — 수동-통과(사람이 Cloudflare를 직접 통과) 모드.

봇이 몰래 우회하는 게 아니라, **사람이 실제 브라우저 창에서 Cloudflare를 한 번
통과**한 뒤 그 인증된 세션을 그대로 재사용해 수집만 자동화한다. 방어 가능한 방식.

동작:
  1. 실제 브라우저(가능하면 설치된 Chrome)를 '창 있는(headful)' 상태로 띄운다.
  2. OPSI 홈이 열리면, 사용자가 Cloudflare 확인("사람입니다" 등)을 직접 통과한다.
  3. 콘솔에서 Enter 를 누르면, 그 브라우저로 REST 주소를 이동하며 사례를 수집한다.
  · 프로필(overseas/.pw-profile)을 저장하므로 다음 실행부터는 대개 통과가 유지된다.

준비:
    pip install playwright
    python -m playwright install chromium     # (Chrome 채널 실패 시 대비)

사용:
    python overseas/opsi_scraper_manual.py --discover
    python overseas/opsi_scraper_manual.py --post-type case_study --max-pages 3
    python overseas/opsi_scraper_manual.py --post-type case_study            # 전체

유의: 사람이 정당하게 연 접근을 자동화하는 것이지만, 대상 사이트의 이용약관(ToS)은
      반드시 확인한다. 요청 간격을 지켜 서버를 존중한다.
"""
import argparse
import json
import logging
import random
import sqlite3
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright 필요:  pip install playwright  &&  python -m playwright install chromium")

from opsi_scraper import CONFIG, DB_PATH, init_db, upsert_case, parse_post

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("opsi-manual")

PROFILE_DIR = Path(__file__).resolve().parent / ".pw-profile"   # 통과 세션 저장(쿠키 유지)


def _fetch_json(page, url):
    """이미 통과한 페이지 '안에서' fetch(XHR)로 같은 도메인 API를 부른다.
    최상위 페이지 이동(navigation)과 달리 Cloudflare 재도전 없이 통과되는 게 핵심.
    반환: (data, meta). meta = {status, total, pages, body}."""
    try:
        res = page.evaluate(
            """async (u) => {
                const r = await fetch(u, {headers: {'Accept': 'application/json'},
                                          credentials: 'include'});
                return {status: r.status,
                        total: r.headers.get('x-wp-total'),
                        pages: r.headers.get('x-wp-totalpages'),
                        body: await r.text()};
            }""", url)
    except Exception as e:
        log.error("페이지 내 fetch 실패(%s): %s", url, e)
        return None, {}
    body = res.get("body", "") or ""
    if res.get("status", 0) >= 400 or "just a moment" in body[:400].lower():
        return None, res
    try:
        return json.loads(body), res
    except Exception:
        log.error("JSON 파싱 실패(%s): 본문 %s", url, body[:150].replace("\n", " "))
        return None, res


def fetch_json(page, url):
    """_fetch_json + Cloudflare 재도전 시 1회 사람 통과 후 재시도."""
    data, meta = _fetch_json(page, url)
    challenged = data is None and meta and (
        meta.get("status", 0) in (403, 429, 503)
        or "just a moment" in (meta.get("body", "")[:400].lower()))
    if challenged:
        print("\n  ※ Cloudflare 확인이 다시 떴을 수 있습니다. 브라우저 창에서 통과 후 Enter ▶ ",
              end="")
        try:
            input()
        except EOFError:
            page.wait_for_timeout(15000)
        data, meta = _fetch_json(page, url)
    return data, meta


def wait_for_human(page, base):
    page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
    print("\n" + "=" * 64)
    print(" 브라우저 창에서 Cloudflare 확인을 직접 통과하세요.")
    print("  · '사람입니다/확인' 체크가 보이면 클릭하고,")
    print("  · 사이트(OPSI 홈)가 정상적으로 보일 때까지 기다립니다.")
    print(" 통과되어 사이트가 보이면, 이 창으로 돌아와 Enter 를 누르세요.")
    print("=" * 64)
    try:
        input(" 통과 후 Enter ▶ ")
    except EOFError:
        time.sleep(20)   # 파이프 실행 등 input 불가 시: 20초 대기로 대체


def discover(page, base):
    data, _ = fetch_json(page, f"{base}/wp-json/wp/v2/types")
    if not data:
        log.error("types 를 못 읽음. 브라우저에 Cloudflare가 다시 떴는지 보고, 통과 후 재실행.")
        return
    print("\n=== 포스트 타입(CPT) ===")
    for slug, info in data.items():
        print(f"  · {slug:20s} rest_base={info.get('rest_base', slug):20s} {info.get('name','')}")
    tax, _ = fetch_json(page, f"{base}/wp-json/wp/v2/taxonomies")
    if tax:
        print("\n=== 분류(taxonomy) ===")
        for slug, info in tax.items():
            print(f"  · {slug:20s} rest_base={info.get('rest_base', slug)}")
    print("\n→ 사례 rest_base 를 --post-type, 국가/분야 slug 을 --tax-country/--tax-sector 로.")


def scrape(page, base, post_type, max_pages=None):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    page_no, saved, total_pages = 1, 0, None
    try:
        while True:
            if max_pages and page_no > max_pages:
                break
            url = (f"{base}/wp-json/wp/v2/{post_type}"
                   f"?per_page={CONFIG['per_page']}&page={page_no}&_embed=1")
            data, meta = fetch_json(page, url)
            if total_pages is None and meta:
                total_pages = meta.get("pages")
                if meta.get("total"):
                    log.info("전체 %s건 · 총 %s페이지", meta.get("total"), total_pages)
            if not data:
                log.info("데이터 없음/종료 (page=%d)", page_no)
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
            page.wait_for_timeout(int(random.uniform(1200, 2800)))  # 서버 존중
    finally:
        conn.close()
    log.info("완료: 총 %d건 UPSERT · DB=%s", saved, DB_PATH)


def main():
    ap = argparse.ArgumentParser(description="OECD OPSI 수집(수동-통과 모드)")
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--post-type")
    ap.add_argument("--tax-country")
    ap.add_argument("--tax-sector")
    ap.add_argument("--base-url")
    ap.add_argument("--max-pages", type=int)
    args = ap.parse_args()
    for k, v in (("base_url", args.base_url), ("post_type", args.post_type),
                 ("tax_country", args.tax_country), ("tax_sector", args.tax_sector)):
        if v:
            CONFIG[k] = v
    base = CONFIG["base_url"].rstrip("/")

    PROFILE_DIR.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        # 설치된 실제 Chrome을 우선 시도(자동화 탐지에 덜 걸림). 없으면 번들 Chromium.
        launch = dict(user_data_dir=str(PROFILE_DIR), headless=False,
                      args=["--disable-blink-features=AutomationControlled"])
        try:
            ctx = pw.chromium.launch_persistent_context(channel="chrome", **launch)
            log.info("설치된 Chrome 사용")
        except Exception:
            ctx = pw.chromium.launch_persistent_context(**launch)
            log.info("번들 Chromium 사용(Chrome 채널 없음)")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            wait_for_human(page, base)
            if args.discover:
                discover(page, base)
            else:
                scrape(page, base, CONFIG["post_type"], max_pages=args.max_pages)
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
