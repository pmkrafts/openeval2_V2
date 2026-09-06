"""Load the Kaggle 515k-hotel CSV into the `reviews` table (OpenEval2).

Usage:
    python scripts/ingest.py path/to/Hotel_Reviews.csv [--db DB] [--replace]
                            [--sample 50000] [--seed 42]

Rules (SPEC §2, §5.2 / H1–H3, TS02–TS05):
  * requires exactly the hotel columns; raise if any are missing
  * a deterministic random sample of `--sample` rows (seed 42 => same ids twice)
  * "No Negative" / blank Negative_Review -> row DROPPED (complaints-only table;
    that text is never seen by an LLM)
  * "No Positive" / blank Positive_Review -> stored as ""
  * rating is kept as REAL on Booking's 1-10 scale (floats exist in the source)
  * word_count = words in the negative text (0 would mean empty => dropped)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as a script

import pandas as pd

import config
import db as db_module

RENAME = {
    "Hotel_Name": "hotel",
    "Reviewer_Nationality": "nationality",
    "Reviewer_Score": "rating",
    "Positive_Review": "text_pos",
    "Negative_Review": "text",
    "Review_Date": "review_date",
}


def _norm(value) -> str:
    """Strip and normalize sentinel empties to "" (SPEC §2)."""
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text in config.EMPTY_SENTINELS else text


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in config.CSV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    out = df[config.CSV_COLUMNS].rename(columns=RENAME).copy()
    out["text"] = out["text"].map(_norm)
    out["text_pos"] = out["text_pos"].map(_norm)
    out = out[out["text"].str.len() > 0]               # drop empty negatives (D6)
    out["word_count"] = out["text"].str.split().str.len()
    out["rating"] = pd.to_numeric(out["rating"], errors="coerce")
    for col in ("hotel", "nationality", "review_date"):
        out[col] = out[col].where(out[col].notna(), None)
    return out


def rows_for_insert(cleaned: pd.DataFrame) -> list[tuple]:
    return [
        (
            None if pd.isna(r.hotel) else str(r.hotel),
            None if pd.isna(r.nationality) else str(r.nationality),
            None if pd.isna(r.rating) else float(r.rating),
            str(r.text),
            str(r.text_pos),
            None if pd.isna(r.review_date) else str(r.review_date),
            int(r.word_count),
        )
        for r in cleaned.itertuples(index=False)
    ]


def ingest(csv_path: str | Path, db_path=None, replace: bool = False,
           sample: int | None = None, seed: int = 42) -> tuple[int, int]:
    """Insert cleaned rows; returns (rows_read, rows_inserted)."""
    db_module.init_db(db_path)
    raw = pd.read_csv(csv_path)
    n_read = len(raw)
    if sample is not None:
        n_read_total = len(raw)
        if sample < n_read_total:
            raw = raw.sample(n=sample, random_state=seed)   # TS02: same ids twice
    rows = rows_for_insert(_clean(raw))
    with db_module.connect(db_path) as conn:
        if replace:
            conn.execute("DELETE FROM ab_labels")
            conn.execute("DELETE FROM ab_runs")
            conn.execute("DELETE FROM labels")
            conn.execute("DELETE FROM reviews")
        conn.executemany(
            "INSERT INTO reviews (hotel, nationality, rating, text, text_pos, review_date, word_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return n_read, len(rows)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="path to the Kaggle Hotel_Reviews CSV")
    parser.add_argument("--db", default=None,
                        help="sqlite path (default: OPENEND_DB_PATH or data/openeval2.sqlite3)")
    parser.add_argument("--replace", action="store_true", help="wipe existing tables first")
    parser.add_argument("--sample", type=int, default=None,
                        help="deterministic random sample size (SPEC: 50000)")
    parser.add_argument("--seed", type=int, default=42, help="sampling seed")
    args = parser.parse_args(argv)
    n_read, n = ingest(args.csv, db_path=args.db, replace=args.replace,
                       sample=args.sample, seed=args.seed)
    target = args.db or config.default_db_path()
    print(f"read {n_read} rows; ingested {n} complaints -> {target}")


if __name__ == "__main__":
    main()
