#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OPSI Obsidian Vault export(.sqlite) → 우리 코퍼스 DB(opsi_policies.db)로 임포트.

교수님이 OPSI 전체를 Obsidian Vault로 정리해 SQLite로 내보낸 파일
(예: OPSIObsidianVault20260731.sqlite, cases 테이블 1000+건, 본문 전문 포함)을
우리 축 B 스키마(cases)로 UPSERT한다. 본문 전 필드를 합쳐 검색용
cleaned_content를 만들므로 매칭 품질이 높다.

사용:
    python overseas/import_obsidian_vault.py OPSIObsidianVault20260731.sqlite
    python overseas/import_obsidian_vault.py vault.sqlite --db overseas/opsi_policies.db
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

DEFAULT_DST = Path(__file__).resolve().parent / "opsi_policies.db"

# Vault의 본문 필드(순서대로 합쳐 검색 텍스트를 만든다)
BODY_FIELDS = [
    "purpose_overview", "key_content", "innovation_elements", "results_impact",
    "challenges_failures", "success_factors", "replicability", "lessons",
]


def ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, title TEXT, country TEXT, sector TEXT, year INTEGER,
            raw_content TEXT, cleaned_content TEXT, source_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    have = {r[1] for r in conn.execute("PRAGMA table_info(cases)")}
    for col in ("level_of_government", "organization", "results"):
        if col not in have:
            conn.execute(f"ALTER TABLE cases ADD COLUMN {col} TEXT")
    conn.commit()


def _year(v):
    m = re.search(r"\b(19|20)\d{2}\b", str(v or ""))
    return int(m.group(0)) if m else None


def _compose(row):
    parts = [(row.get("title") or "").strip()]
    for f in BODY_FIELDS:
        v = (row.get(f) or "").strip()
        if v:
            parts.append(v)
    return re.sub(r"\s+", " ", " \n".join(p for p in parts if p)).strip()


def _slug_id(row):
    rid = (row.get("id") or "").strip()
    if rid:
        return rid
    url = (row.get("source_url") or "").strip().rstrip("/")
    if url:
        return url.split("/")[-1]
    return re.sub(r"\s+", "-", (row.get("title") or "no-title")).strip("-")[:64]


UPSERT = """
INSERT INTO cases (id,title,country,sector,year,raw_content,cleaned_content,
                   source_url,level_of_government,organization,results,scraped_at)
VALUES (:id,:title,:country,:sector,:year,:raw_content,:cleaned_content,
        :source_url,:level_of_government,:organization,:results,CURRENT_TIMESTAMP)
ON CONFLICT(id) DO UPDATE SET
    title=excluded.title, country=excluded.country, sector=excluded.sector,
    year=excluded.year, raw_content=excluded.raw_content,
    cleaned_content=excluded.cleaned_content, source_url=excluded.source_url,
    level_of_government=excluded.level_of_government,
    organization=excluded.organization, results=excluded.results,
    scraped_at=CURRENT_TIMESTAMP
"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        sys.exit(__doc__)
    src = args[0]
    dst = DEFAULT_DST
    if "--db" in sys.argv:
        dst = Path(sys.argv[sys.argv.index("--db") + 1])

    s = sqlite3.connect(src)
    s.row_factory = sqlite3.Row
    rows = [dict(r) for r in s.execute("SELECT * FROM cases").fetchall()]
    s.close()

    d = sqlite3.connect(dst)
    ensure_schema(d)
    n = 0
    for r in rows:
        rec = {
            "id": _slug_id(r),
            "title": (r.get("title") or "").strip(),
            "country": (r.get("country") or "").strip() or None,
            "sector": (r.get("sector") or "").strip() or None,
            "year": _year(r.get("year_launched") or r.get("year")),
            "raw_content": json.dumps(r, ensure_ascii=False),
            "cleaned_content": _compose(r),
            "source_url": (r.get("source_url") or "").strip() or None,
            "level_of_government": (r.get("government_level")
                                    or r.get("level_of_government") or "").strip() or None,
            "organization": (r.get("organisation")
                             or r.get("organization") or "").strip() or None,
            "results": (r.get("results_impact") or r.get("results") or "").strip() or None,
        }
        if not rec["title"] and not rec["source_url"]:
            continue
        d.execute(UPSERT, rec)
        n += 1
    d.commit()
    total = d.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    withbody = d.execute(
        "SELECT COUNT(*) FROM cases WHERE LENGTH(COALESCE(cleaned_content,''))"
        " > LENGTH(COALESCE(title,'')) + 20").fetchone()[0]
    d.close()
    print(f"완료: 이번 {n}건 UPSERT · DB 전체 {total}건(본문 있음 {withbody}건) · {dst}")


if __name__ == "__main__":
    main()
