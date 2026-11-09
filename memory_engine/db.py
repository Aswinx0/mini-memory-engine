from __future__ import annotations

import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT    NOT NULL,
    subject       TEXT    NOT NULL,
    fact          TEXT    NOT NULL,
    embedding     BLOB    NOT NULL,
    source_text   TEXT,
    created_at    TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'active',
    superseded_by INTEGER,
    superseded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_user_status ON facts(user_id, status);
"""


@contextmanager
def connect(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)