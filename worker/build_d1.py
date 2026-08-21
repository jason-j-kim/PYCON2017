#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""로컬 코퍼스 → Cloudflare D1 적재용 SQL 생성.

Workers는 26MB SQLite 파일을 번들할 수 없다(스크립트 크기 한도).
따라서 세 코퍼스를 D1(서버리스 SQLite)로 옮긴다.

  재정   web/api/fiscal.json          14,122 사업
  KDI    kdi/kdi.sqlite (docs)         7,362 발간물
  해외   overseas/opsi_policies.db     1,015 사례

사용(프로젝트 루트에서):
    python worker/build_d1.py                 # 전체
    python worker/build_d1.py --only kdi      # 하나만

산출: worker/d1/schema.sql, worker/d1/fiscal.sql, worker/d1/kdi.sql, worker/d1/opsi.sql
적재:
    wrangler d1 execute policy-corpus --remote --file=worker/d1/schema.sql
    wrangler d1 execute policy-corpus --remote --file=worker/d1/fiscal.sql
    ... (kdi, opsi 순서대로)
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "d1"
OUT.mkdir(exist_ok=True)

# D1은 한 번에 실행할 SQL 크기에 제약이 있어 여러 INSERT로 쪼갠다.
BATCH = 200

SCHEMA = """
DROP TABLE IF EXISTS fiscal;
CREATE TABLE fiscal (
  id       INTEGER PRIMARY KEY,
  name     TEXT NOT NULL,
  ministry TEXT,
  max_amt  INTEGER,      -- 정렬용: 시계열 최대 예산
  series   TEXT           -- JSON [{year,amount}]
);
CREATE INDEX ix_fiscal_name ON fiscal(name);

DROP TABLE IF EXISTS kdi;
CREATE TABLE kdi (
  id       TEXT PRIMARY KEY,
  title    TEXT NOT NULL,
  kind     TEXT,
  year     TEXT,
  keywords TEXT,
  content  TEXT,          -- title + keywords + toc + summary (검색 대상)
  url      TEXT
);
CREATE INDEX ix_kdi_title ON kdi(title);

DROP TABLE IF EXISTS opsi;
CREATE TABLE opsi (
  id       TEXT PRIMARY KEY,
  title    TEXT NOT NULL,
  country  TEXT,
  year     INTEGER,
  sector   TEXT,
  level    TEXT,
  content  TEXT,          -- 본문(검색 대상)
  url      TEXT
);
CREATE INDEX ix_opsi_title ON opsi(title);
""".strip()


def q(v):
    """SQL 리터럴. None은 NULL, 나머지는 작은따옴표 이스케이프."""
    if v is None or v == "":
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def clean(s, limit=None):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:limit] if limit else s


def write_inserts(path, table, cols, rows):
    """INSERT를 BATCH 단위로 나눠 파일에 쓴다."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"-- {table}: {len(rows)}행\n")
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            f.write(f"INSERT INTO {table} ({','.join(cols)}) VALUES\n")
            f.write(",\n".join("(" + ",".join(q(v) for v in r) + ")" for r in chunk))
            f.write(";\n")
    print(f"  {path.name}: {len(rows)}행 · {path.stat().st_size/1e6:.1f}MB")


def build_fiscal():
    src = ROOT / "web" / "api" / "fiscal.json"
    if not src.exists():
        print("  건너뜀: fiscal.json 없음")
        return
    data = json.loads(src.read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    rows = []
    for i, rec in enumerate(items):
        series = rec.get("series") or []
        max_amt = max((s.get("amount", 0) for s in series), default=0)
        rows.append((i, clean(rec.get("name")), clean(rec.get("ministry")),
                     int(max_amt), json.dumps(series, ensure_ascii=False)))
    write_inserts(OUT / "fiscal.sql", "fiscal",
                  ["id", "name", "ministry", "max_amt", "series"], rows)


def build_kdi():
    src = Path(sys.argv[sys.argv.index("--kdi") + 1]) if "--kdi" in sys.argv else None
    for cand in [src, ROOT / "kdi" / "kdi.sqlite", ROOT / "web" / "api" / "kdi.sqlite"]:
        if cand and cand.exists():
            src = cand
            break
    else:
        print("  건너뜀: kdi.sqlite 없음")
        return
    c = sqlite3.connect(str(src))
    c.row_factory = sqlite3.Row
    rows = []
    for r in c.execute("SELECT doc_id,title,kind,date,keywords,toc,summary,url FROM docs"):
        d = dict(r)
        # 검색 본문은 길이를 제한한다 — D1 용량과 조회 속도를 위해.
        content = clean(" ".join(filter(None, [
            d.get("title"), d.get("keywords"), d.get("toc"), d.get("summary")])), 4000)
        if not clean(d.get("title")):
            continue
        rows.append((d.get("doc_id"), clean(d.get("title")), clean(d.get("kind")),
                     clean(d.get("date"), 10), clean(d.get("keywords"), 500),
                     content, clean(d.get("url"), 300)))
    c.close()
    write_inserts(OUT / "kdi.sql", "kdi",
                  ["id", "title", "kind", "year", "keywords", "content", "url"], rows)


def build_opsi():
    for cand in [ROOT / "overseas" / "opsi_policies.db", ROOT / "web" / "api" / "opsi_policies.db"]:
        if cand.exists():
            src = cand
            break
    else:
        print("  건너뜀: opsi_policies.db 없음")
        return
    c = sqlite3.connect(str(src))
    c.row_factory = sqlite3.Row
    rows = []
    for r in c.execute("SELECT id,title,country,year,sector,level_of_government,"
                       "cleaned_content,source_url FROM cases"):
        d = dict(r)
        if not clean(d.get("title")):
            continue
        rows.append((d.get("id"), clean(d.get("title")), clean(d.get("country")),
                     d.get("year"), clean(d.get("sector"), 200),
                     clean(d.get("level_of_government"), 40),
                     clean(d.get("cleaned_content"), 4000), clean(d.get("source_url"), 300)))
    c.close()
    write_inserts(OUT / "opsi.sql", "opsi",
                  ["id", "title", "country", "year", "sector", "level", "content", "url"], rows)


def main():
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    (OUT / "schema.sql").write_text(SCHEMA + "\n", encoding="utf-8")
    print(f"생성 위치: {OUT}")
    print("  schema.sql")
    if only in (None, "fiscal"):
        build_fiscal()
    if only in (None, "kdi"):
        build_kdi()
    if only in (None, "opsi"):
        build_opsi()
    print("\n적재 순서:")
    print("  wrangler d1 execute policy-corpus --remote --file=worker/d1/schema.sql")
    for n in ("fiscal", "kdi", "opsi"):
        if (OUT / f"{n}.sql").exists():
            print(f"  wrangler d1 execute policy-corpus --remote --file=worker/d1/{n}.sql")


if __name__ == "__main__":
    main()
