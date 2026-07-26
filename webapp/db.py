"""세션·대화·평가 저장소 (SQLite, 표준 라이브러리만 사용)."""

import datetime
import json
import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path(__file__).parent / "sessions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    idea          TEXT NOT NULL,
    weights       TEXT NOT NULL,          -- JSON
    stage_index   INTEGER NOT NULL DEFAULT 0,
    q_in_stage    INTEGER NOT NULL DEFAULT 0,  -- 현재 단계에서 던진 질문 수
    status        TEXT NOT NULL DEFAULT 'active',  -- active | graded
    profile       TEXT NOT NULL DEFAULT '원본',    -- 원본 | 정책 (수정판)
    originality        TEXT,                        -- 축 B 결과 JSON (NULL=미실행)
    originality_status TEXT NOT NULL DEFAULT 'none',-- none|pending|done|error
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    seq         INTEGER NOT NULL,        -- 턴 번호 (채점 근거 인용에 쓰임)
    role        TEXT NOT NULL,           -- proposer | questioner
    stage       TEXT,                    -- 질문자 턴의 단계 표시 이름
    content     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
    session_id     TEXT PRIMARY KEY REFERENCES sessions(id),
    result         TEXT NOT NULL,        -- JSON
    weighted_total REAL NOT NULL
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _conn() as conn:
        conn.executescript(SCHEMA)
        # 기존 DB 마이그레이션: 없는 컬럼을 추가한다(기존 행은 기본값).
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)")}
        if "profile" not in cols:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN profile TEXT NOT NULL DEFAULT '원본'"
            )
        if "originality" not in cols:
            # 축 B(선례 조사) 결과 JSON. NULL=미실행/진행중.
            conn.execute("ALTER TABLE sessions ADD COLUMN originality TEXT")
        if "originality_status" not in cols:
            # none | pending | done | error
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN originality_status TEXT "
                "NOT NULL DEFAULT 'none'"
            )


def create_session(idea, weights, profile="원본"):
    sid = uuid.uuid4().hex[:12]
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, idea, weights, profile, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, idea, json.dumps(weights), profile,
             datetime.datetime.now().isoformat()),
        )
    return sid


def count_sessions_today():
    today = datetime.date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE created_at >= ?", (today,)
        ).fetchone()
    return row["n"]


def get_session(sid):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    return dict(row) if row else None


def update_progress(sid, stage_index, q_in_stage):
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET stage_index = ?, q_in_stage = ? WHERE id = ?",
            (stage_index, q_in_stage, sid),
        )


def set_status(sid, status):
    with _conn() as conn:
        conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, sid))


def add_turn(sid, seq, role, stage, content):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO turns (session_id, seq, role, stage, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, seq, role, stage, content),
        )


def get_turns(sid):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT seq, role, stage, content FROM turns "
            "WHERE session_id = ? ORDER BY seq", (sid,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_evaluation(sid, result, total):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO evaluations (session_id, result, weighted_total) "
            "VALUES (?, ?, ?)",
            (sid, json.dumps(result, ensure_ascii=False), total),
        )


def set_originality_status(sid, status):
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET originality_status = ? WHERE id = ?", (status, sid)
        )


def save_originality(sid, data):
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET originality = ?, originality_status = 'done' "
            "WHERE id = ?",
            (json.dumps(data, ensure_ascii=False), sid),
        )


def get_originality(sid):
    """{'status': ..., 'result': dict|None} 반환."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT originality, originality_status FROM sessions WHERE id = ?", (sid,)
        ).fetchone()
    if not row:
        return None
    result = json.loads(row["originality"]) if row["originality"] else None
    return {"status": row["originality_status"], "result": result}


def get_evaluation(sid):
    with _conn() as conn:
        row = conn.execute(
            "SELECT result, weighted_total FROM evaluations WHERE session_id = ?",
            (sid,),
        ).fetchone()
    if not row:
        return None
    return {"result": json.loads(row["result"]), "weighted_total": row["weighted_total"]}
