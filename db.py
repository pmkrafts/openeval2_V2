"""SQLite access: schema and connection helpers (OpenEval2 / hotel schema).

Tables:
  reviews   — one row per cleaned complaint (empty negatives dropped at ingest).
              Facts only; status is DERIVED by config.status_* at query time.
  labels    — label_a / label_b for the labeled sample (two calls per row),
              optional gold_label (v2) and per-row error/flag state.
  ab_runs   — one row per prompt A/B run (v2).
  ab_labels— per-row labels of an A/B run, keyed by (run_id, review_id).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY,
    hotel       TEXT,
    nationality TEXT,
    rating      REAL,               -- Booking.com 1-10 scale (SPEC: 10-pt, not 5-pt)
    text        TEXT    NOT NULL,   -- Negative_Review (primary labeling text)
    text_pos    TEXT,               -- Positive_Review ("" when "No Positive")
    review_date TEXT,
    word_count  INTEGER NOT NULL    -- words in `text` (negative); 0 would mean empty (dropped)
);
CREATE TABLE IF NOT EXISTS labels (
    review_id  INTEGER PRIMARY KEY REFERENCES reviews (id),
    label_a    TEXT,                -- valid theme or NULL
    label_b    TEXT,
    agree      INTEGER,             -- 1 when config.labels_agree(label_a, label_b)
    llm_error  INTEGER NOT NULL DEFAULT 0,  -- call failed OR label sanitized to Other (TS13)
    error      TEXT,                -- human-readable reason (Flow 6 / TS13)
    gold_label TEXT                 -- v2: optional human truth; never overwrites A/B
);
CREATE TABLE IF NOT EXISTS ab_runs (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version TEXT    NOT NULL,
    n              INTEGER NOT NULL,
    cost           REAL    NOT NULL DEFAULT 0,
    p50_ms         REAL,
    created_at     TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS ab_labels (
    run_id    INTEGER NOT NULL REFERENCES ab_runs (run_id),
    review_id INTEGER NOT NULL REFERENCES reviews (id),
    label     TEXT,
    PRIMARY KEY (run_id, review_id)
);
"""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else config.default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def counts(db_path=None) -> dict:
    with connect(db_path) as conn:
        reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        labels = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
        gold = conn.execute(
            "SELECT COUNT(*) FROM labels WHERE gold_label IS NOT NULL"
        ).fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM ab_runs").fetchone()[0]
    return {"reviews": reviews, "labels": labels, "gold": gold, "ab_runs": runs}
