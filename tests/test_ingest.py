"""Ingest tests (SPEC H1–H3, TS02–TS05)."""
import sqlite3

from conftest import FIRST_LONG_ID, N_EMPTY_NEG, TOTAL_ROWS

import db as db_module


def test_ingest_count_and_drop(db_path):
    """H1/H3: 216 complaints in; the 4 empty/'No Negative' rows never reach the DB."""
    with db_module.connect(db_path) as conn:
        n = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        empties = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE text = '' OR text IS NULL").fetchone()[0]
        zero_wc = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE word_count = 0").fetchone()[0]
    assert n == TOTAL_ROWS
    assert empties == 0
    assert zero_wc == 0
    assert N_EMPTY_NEG == 4  # fixture sanity: empties were actually present in the CSV


def test_no_positive_row_kept_with_empty_positive(db_path):
    """TS04: a 'No Positive' row stays when the negative exists; text_pos == ''."""
    with db_module.connect(db_path) as conn:
        row = conn.execute(
            "SELECT text, text_pos, word_count FROM reviews WHERE id = ?",
            (FIRST_LONG_ID + 5,),  # fixture long row i == 5 had 'No Positive'
        ).fetchone()
    assert row is not None
    assert row["text_pos"] == ""
    assert len(row["text"]) > 0


def test_word_count_matches_negative_text(db_path):
    """D7/TS05: word_count = words in the negative text, for every row."""
    with db_module.connect(db_path) as conn:
        rows = conn.execute("SELECT text, word_count FROM reviews").fetchall()
    for r in rows:
        assert r["word_count"] == len(r["text"].split())


def test_deterministic_sample_same_ids(csv_path, tmp_path):
    """TS02: --sample N --seed 42 twice yields the same ids both times."""
    import sqlite3

    from scripts.ingest import ingest

    def _ingest(name: str) -> list[int]:
        path = tmp_path / f"{name}.sqlite3"
        ingest(csv_path, db_path=path, sample=50, seed=42)
        with sqlite3.connect(path) as conn:
            return [r[0] for r in conn.execute("SELECT id FROM reviews ORDER BY id")]

    assert _ingest("a.sqlite3") == _ingest("b.sqlite3")


def test_missing_columns_rejected(tmp_path):
    """Ingest raises cleanly on a CSV without the hotel columns."""
    from scripts.ingest import ingest
    import pandas as pd

    bad = tmp_path / "bad.csv"
    pd.DataFrame({"Something_Else": [1]}).to_csv(bad, index=False)
    try:
        ingest(bad, db_path=tmp_path / "bad.sqlite3")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "missing required columns" in str(exc)
