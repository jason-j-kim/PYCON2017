#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KDI 정책연구 코퍼스(SQLite) → kdi/kdi_corpus.db 의 reports 테이블로 임포트.

교수님 PC의 큰 SQLite(예: 50MB)를 여기로 보낼 필요 없이, 로컬에서 이 스크립트를
돌리면 검색에 필요한 필드만 뽑아 작은 kdi_corpus.db 를 만든다.
컬럼 이름은 자동 감지한다(한국어 컬럼명 포함). 먼저 --inspect 로 매핑을 확인하라.

사용:
    python kdi/import_kdi.py  C:\\path\\kdi.sqlite  --inspect
    python kdi/import_kdi.py  C:\\path\\kdi.sqlite
    python kdi/import_kdi.py  C:\\path\\kdi.sqlite  --table 보고서 --title 제목 --abstract 초록

자동 감지가 틀리면 위처럼 --table/--title/--abstract/--keywords/--org/--year/--url 로 지정.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

DST = Path(__file__).resolve().parent / "kdi_corpus.db"

# 후보 컬럼명(소문자 비교, 한국어 포함). 앞에 있을수록 우선.
CANDIDATES = {
    "title":    ["title", "제목", "보고서명", "논문제목", "과제명", "연구명", "subject", "name", "titl"],
    "abstract": ["abstract", "초록", "요약", "summary", "본문", "내용", "content", "contents",
                 "description", "개요", "요약문", "abst", "body", "text", "fulltext"],
    "keywords": ["keywords", "키워드", "keyword", "주제어", "tags", "태그", "kwd"],
    "org":      ["org", "organization", "organisation", "기관", "발간기관", "발행기관",
                 "author", "저자", "연구진", "연구책임자", "publisher", "부서"],
    "year":     ["year", "연도", "발간연도", "출판연도", "발행연도", "pub_year", "발간년도",
                 "date", "발간일", "발행일", "publish_date", "년도"],
    "url":      ["url", "link", "링크", "source_url", "원문", "원문링크", "permalink", "doi"],
}


def _tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]


def _cols(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _pick_table(conn, override):
    if override:
        return override
    best, best_n = None, -1
    for t in _tables(conn):
        if t.endswith(("_fts", "_data", "_idx", "_docsize", "_config", "_content")):
            continue  # FTS 보조 테이블 제외
        try:
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception:
            n = -1
        if n > best_n:
            best, best_n = t, n
    return best


def _auto_map(cols, overrides):
    low = {c.lower(): c for c in cols}
    mapping = {}
    for field, cands in CANDIDATES.items():
        if overrides.get(field):
            mapping[field] = overrides[field]
            continue
        hit = None
        for cand in cands:                      # 정확 일치 우선
            if cand in low:
                hit = low[cand]
                break
        if not hit:                             # 부분 일치
            for cand in cands:
                for lc, orig in low.items():
                    if cand in lc:
                        hit = orig
                        break
                if hit:
                    break
        if hit:
            mapping[field] = hit
    # title이 없으면 첫 TEXT 컬럼을 제목으로
    if "title" not in mapping and cols:
        mapping["title"] = cols[0]
    return mapping


def _year(v):
    m = re.search(r"\b(19|20)\d{2}\b", str(v or ""))
    return m.group(0) if m else None


def ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY, title TEXT, org TEXT, year TEXT, period TEXT,
            keywords TEXT, cleaned_content TEXT, url TEXT, raw_content TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()


UPSERT = """
INSERT INTO reports (id,title,org,year,period,keywords,cleaned_content,url,raw_content,imported_at)
VALUES (:id,:title,:org,:year,:period,:keywords,:cleaned_content,:url,:raw_content,CURRENT_TIMESTAMP)
ON CONFLICT(id) DO UPDATE SET
    title=excluded.title, org=excluded.org, year=excluded.year, period=excluded.period,
    keywords=excluded.keywords, cleaned_content=excluded.cleaned_content, url=excluded.url,
    raw_content=excluded.raw_content, imported_at=CURRENT_TIMESTAMP
"""


def _clean(v):
    return re.sub(r"\s+", " ", str(v)).strip() if v not in (None, "") else ""


def main():
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    src = argv[0]
    flags = {}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--inspect":
            flags["inspect"] = True
        elif a.startswith("--") and i + 1 < len(argv):
            flags[a[2:]] = argv[i + 1]
            i += 1
        i += 1

    s = sqlite3.connect(src)
    table = _pick_table(s, flags.get("table"))
    if not table:
        sys.exit("테이블을 찾지 못했습니다.")
    cols = _cols(s, table)
    overrides = {k: flags.get(k) for k in CANDIDATES}
    mapping = _auto_map(cols, overrides)

    n = s.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print(f"■ 소스: {src}")
    print(f"  테이블: {table}  ({n}행)")
    print(f"  전체 컬럼: {cols}")
    print(f"  자동 매핑:")
    for f in CANDIDATES:
        print(f"    {f:9s} ← {mapping.get(f, '(없음)')}")
    # abstract가 없으면 title 외 텍스트 컬럼들을 본문으로 합칠 예정
    text_cols = [c for c in cols if c not in mapping.values()]
    if "abstract" not in mapping:
        print(f"  ※ 초록 컬럼 미검출 → 다음 컬럼들을 본문으로 합칩니다: {text_cols[:8]}")

    if flags.get("inspect"):
        print("\n[--inspect] 위 매핑이 맞으면 --inspect 빼고 다시 실행하세요.")
        print("샘플 1행:")
        s.row_factory = sqlite3.Row
        row = s.execute(f'SELECT * FROM "{table}" LIMIT 1').fetchone()
        if row:
            for k in row.keys():
                v = _clean(row[k])
                print(f"    {k}: {v[:120]}{'…' if len(v) > 120 else ''}")
        s.close()
        return

    s.row_factory = sqlite3.Row
    d = sqlite3.connect(DST)
    ensure_schema(d)
    cnt = 0
    for r in s.execute(f'SELECT * FROM "{table}"'):
        r = dict(r)
        title = _clean(r.get(mapping.get("title", "")))
        abstract = _clean(r.get(mapping.get("abstract", ""))) if "abstract" in mapping else ""
        if not abstract:  # 초록 컬럼이 없으면 나머지 텍스트 컬럼 합치기
            abstract = " ".join(_clean(r.get(c)) for c in text_cols if _clean(r.get(c)))
        keywords = _clean(r.get(mapping.get("keywords", "")))
        org = _clean(r.get(mapping.get("org", "")))
        year = _year(r.get(mapping.get("year", "")))
        url = _clean(r.get(mapping.get("url", "")))
        if not title and not abstract:
            continue
        rid = url or title[:80] or f"kdi-{cnt}"
        cleaned = re.sub(r"\s+", " ", f"{title} {keywords} {abstract}").strip()
        d.execute(UPSERT, {
            "id": rid, "title": title, "org": org or None, "year": year, "period": year,
            "keywords": keywords or None, "cleaned_content": cleaned,
            "url": url or None, "raw_content": json.dumps(r, ensure_ascii=False),
        })
        cnt += 1
    d.commit()
    total = d.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    d.close()
    s.close()
    print(f"\n완료: 이번 {cnt}건 UPSERT · DB 전체 {total}건 · {DST}")


if __name__ == "__main__":
    main()
