#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OPSI 해외 코퍼스 점검기(코퍼스 체커).

수집한 overseas/opsi_policies.db 안에 무엇이 들었는지 세어보고 검색한다.
(읽기 전용 — DB를 바꾸지 않는다.)

사용:
    python overseas/check_corpus.py                     # 요약(건수·국가·연도·본문 유무)
    python overseas/check_corpus.py basic income        # 키워드 검색(축 B와 같은 방식)
    python overseas/check_corpus.py --list 20           # 최근 임포트 20건 제목
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "opsi_policies.db"


def _conn():
    if not DB.exists():
        sys.exit(f"DB 없음: {DB}\n먼저 import_cases.py로 사례를 넣으세요.")
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def summary(c):
    total = c.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    # 본문(problem/solution 등)이 제목보다 길면 '본문 있음'으로 간주
    with_body = c.execute(
        "SELECT COUNT(*) FROM cases WHERE LENGTH(COALESCE(cleaned_content,'')) "
        "> LENGTH(COALESCE(title,'')) + 20").fetchone()[0]
    with_country = c.execute(
        "SELECT COUNT(*) FROM cases WHERE country IS NOT NULL AND country<>''").fetchone()[0]
    print(f"■ OPSI 코퍼스: 총 {total}건  ·  {DB}")
    print(f"  - 본문 보강됨: {with_body}건  ·  제목만: {total - with_body}건")
    print(f"  - 국가 정보 있음: {with_country}건")

    def top(col, label):
        rows = c.execute(
            f"SELECT COALESCE(NULLIF({col},''),'(없음)') k, COUNT(*) n "
            f"FROM cases GROUP BY k ORDER BY n DESC LIMIT 12").fetchall()
        if rows:
            print(f"\n  [{label}]")
            for r in rows:
                print(f"    {r['n']:>4}  {r['k']}")

    top("country", "국가 상위")
    top("year", "연도")
    top("level_of_government", "정부 수준")


def search(c, query):
    """축 B와 동일한 방식: 영어 토큰으로 title/cleaned_content/country LIKE 검색."""
    import re
    toks = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", query)]
    if not toks:
        # 한글 등은 통째로 LIKE
        toks = [query.strip().lower()]
    where = " OR ".join(
        ["LOWER(cleaned_content) LIKE ? OR LOWER(title) LIKE ? OR LOWER(country) LIKE ?"] * len(toks))
    params = []
    for t in toks:
        params += [f"%{t}%"] * 3
    rows = c.execute(f"SELECT * FROM cases WHERE {where} LIMIT 200", params).fetchall()
    scored = []
    for d in rows:
        hay = f"{d['title'] or ''} {d['cleaned_content'] or ''} {d['country'] or ''}".lower()
        s = sum(1 for t in toks if t in hay)
        if s:
            scored.append((s, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    print(f"■ '{query}' 검색: {len(scored)}건 매칭 (상위 15 표시)\n")
    for s, d in scored[:15]:
        loc = " · ".join(x for x in [d["country"], str(d["year"] or "")] if x and x != "None")
        print(f"  [{s}] {d['title']}")
        if loc:
            print(f"        {loc}")
        print(f"        {d['source_url']}")


def listing(c, n):
    rows = c.execute(
        "SELECT title, country, source_url FROM cases ORDER BY scraped_at DESC LIMIT ?",
        (n,)).fetchall()
    print(f"■ 최근 임포트 {len(rows)}건\n")
    for r in rows:
        print(f"  · {r['title']}  ({r['country'] or '?'})")


def main():
    args = sys.argv[1:]
    c = _conn()
    try:
        if not args:
            summary(c)
        elif args[0] == "--list":
            listing(c, int(args[1]) if len(args) > 1 else 20)
        else:
            search(c, " ".join(args))
    finally:
        c.close()


if __name__ == "__main__":
    main()
