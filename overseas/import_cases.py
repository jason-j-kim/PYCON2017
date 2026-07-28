#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사람이 수집한 해외 정책사례(JSON)를 로컬 DB(opsi_policies.db)로 넣는 임포터.

Claude in Chrome(교수님 실제 브라우저 세션) 등으로 OPSI Case Study를 추출해
아래 형식의 JSON 파일로 저장하면, 이 스크립트가 표준 스키마로 UPSERT한다.
(스크래핑 없음 — 사람이 정당하게 연 브라우저로 얻은 데이터를 정리만 한다.)

입력 JSON 형식(배열):
[
  {
    "source_url": "https://oecd-opsi.org/innovations/....",   (필수 · id로도 사용)
    "title": "정책·혁신 이름",
    "country": "United Kingdom",
    "level_of_government": "central",
    "year": 2022,
    "sector": "문화, 복지",              (분야·태그, 쉼표로)
    "problem": "해결하려는 문제",
    "solution": "무엇을 어떻게 했는가(본문)",
    "results": "성과·영향",
    "organization": "주관 기관"
  },
  ...
]

사용:
    python overseas/import_cases.py cases.json
    python overseas/import_cases.py cases1.json cases2.json     (여러 파일)
"""
import glob
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "opsi_policies.db"

BASE_COLS = ["id", "title", "country", "sector", "year",
             "raw_content", "cleaned_content", "source_url", "scraped_at"]
EXTRA_COLS = {"level_of_government": "TEXT", "organization": "TEXT", "results": "TEXT"}


def ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, title TEXT, country TEXT, sector TEXT, year INTEGER,
            raw_content TEXT, cleaned_content TEXT, source_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    have = {r[1] for r in conn.execute("PRAGMA table_info(cases)")}
    for col, typ in EXTRA_COLS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE cases ADD COLUMN {col} {typ}")
    conn.commit()


def _slug_id(rec):
    url = (rec.get("source_url") or "").strip().rstrip("/")
    if url:
        seg = url.split("/")[-1]
        return seg or re.sub(r"[^0-9a-zA-Z]", "-", url)[-64:]
    # URL이 없으면 제목으로 안정 id 생성
    return re.sub(r"\s+", "-", (rec.get("title") or "no-title")).strip("-")[:64]


def _year(v):
    if v in (None, ""):
        return None
    m = re.search(r"\b(19|20)\d{2}\b", str(v))
    return int(m.group(0)) if m else None


def _compose_text(rec):
    """검색용 순수 텍스트: 제목·문제·해법·성과를 합친다(우리 grader가 대조에 쓴다)."""
    parts = []
    for k in ("title", "problem", "solution", "results"):
        v = (rec.get(k) or "").strip()
        if v:
            parts.append(v)
    return re.sub(r"\s+", " ", " \n".join(parts)).strip()


def upsert(conn, rec):
    row = {
        "id": (rec.get("id") or _slug_id(rec)),
        "title": (rec.get("title") or "").strip(),
        "country": (rec.get("country") or "").strip() or None,
        "sector": (rec.get("sector") or "").strip() or None,
        "year": _year(rec.get("year")),
        "raw_content": json.dumps(rec, ensure_ascii=False),   # 원본 레코드 보존
        "cleaned_content": _compose_text(rec),
        "source_url": (rec.get("source_url") or "").strip() or None,
        "level_of_government": (rec.get("level_of_government") or "").strip() or None,
        "organization": (rec.get("organization") or "").strip() or None,
        "results": (rec.get("results") or "").strip() or None,
    }
    conn.execute("""
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
    """, row)
    return row["id"]


def load_records(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):                 # {"cases":[...]} 또는 단건 dict 허용
        data = data.get("cases") or data.get("results") or [data]
    if not isinstance(data, list):
        raise ValueError(f"{path}: JSON 배열이 아닙니다.")
    return data


def _expand(args):
    """인자를 파일 목록으로 확장한다: 파일 · 와일드카드(cases*.json) · 폴더 모두 허용.
    (Windows cmd는 와일드카드를 안 풀어주므로 여기서 직접 처리한다.)"""
    out = []
    for a in args:
        if os.path.isdir(a):
            out += sorted(glob.glob(os.path.join(a, "*.json")))
        else:
            hit = sorted(glob.glob(a))
            out += hit if hit else [a]
    # 중복 경로 제거(순서 유지)
    return list(dict.fromkeys(out))


def main():
    files = _expand([a for a in sys.argv[1:] if not a.startswith("-")])
    if not files:
        print(__doc__)
        sys.exit("입력 JSON 파일을 지정하세요.")
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        total = 0
        for f in files:
            recs = load_records(f)
            n = 0
            for rec in recs:
                if not isinstance(rec, dict):
                    continue
                upsert(conn, rec)
                n += 1
            conn.commit()
            print(f"  {f}: {n}건 반영")
            total += n
        cnt = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        print(f"완료: 이번 {total}건 UPSERT · DB 전체 {cnt}건 · {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
