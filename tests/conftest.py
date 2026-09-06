"""Shared fixtures: a synthetic hotel-shaped CSV and a seeded temp database.

The whole suite runs without the real 227 MB Kaggle file or any LLM key: the CSV
is generated deterministically, ingest/API code is exercised for real, and the
`mock` labeler stands in for the LLM.

Synthetic shape (matches SPEC H1/H3, TS02–TS05):
  * shorts first  — 6 rows with < 4 words (short => needs_review, no LLM spend)
  * then 210 long complaint rows across 14 hotels, ratings 2–10,
    one "No Positive" row (kept), empty/"No Negative" rows interleaved at the end
    (dropped at ingest)
  => cleaned table = 216 rows, ids 1..216 (1–6 short).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "scripts", ROOT / "api"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config  # noqa: E402
import db as db_module  # noqa: E402
from scripts import ingest as ingest_module  # noqa: E402

SHORT_TEXTS = ["Dirty room", "Rude staff", "Great", "Bad", "Too hot", "Worst ever"]

# Long complaint templates — first keyword hit decides the mock label; every
# template must resolve deterministically. Ratings are 2–10 except OTHER_TPL
# rows (6–10) so agreeing-Other rows never trip the rating clash by accident.
ROOM_TPL = ("The room was clean and tidy and the bed was comfortable during our "
            "stay in the hotel downtown")
STAFF_TPL = ("The front desk staff were helpful and friendly during our entire "
             "stay at the reception")
FOOD_TPL = ("The breakfast buffet had good food and fresh coffee every single "
            "morning of our stay")
LOCATION_TPL = ("The location was convenient with easy access to the metro and "
                "the main shops nearby")
PRICE_TPL = ("Everything was too expensive and the price felt unfair for the "
             "quality that we received")
CLEAN_TPL = ("The sheets were dirty and the towels smelled strongly of mold "
             "during the whole trip")
OTHER_TPL = ("The overall experience was quite standard and fully acceptable "
             "during our short visit to the property")

LONG_TEMPLATES = [ROOM_TPL, STAFF_TPL, FOOD_TPL, LOCATION_TPL, PRICE_TPL,
                  CLEAN_TPL, OTHER_TPL]

HOTELS = [f"Hotel {c}" for c in "ABCDEFGHIJKLMN"]

COLUMNS = ["Hotel_Name", "Reviewer_Nationality", "Reviewer_Score",
           "Positive_Review", "Negative_Review", "Review_Date"]

N_SHORT = len(SHORT_TEXTS)
N_LONG = 210
N_EMPTY_NEG = 4          # blank or "No Negative" => dropped
TOTAL_ROWS = N_SHORT + N_LONG                       # 216 after ingest
FIRST_LONG_ID = N_SHORT + 1                         # 7


def long_text(i: int) -> str:
    return LONG_TEMPLATES[i % len(LONG_TEMPLATES)]


def long_rating(i: int) -> int:
    # OTHER template rows always land > 4 so mock Other/Other rows are ok
    if i % len(LONG_TEMPLATES) == 6:
        return 6 + (i % 5)
    return 2 + (i % 9)


def write_review_csv(path: Path, n_short: int = N_SHORT, n_long: int = N_LONG) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for i in range(n_short):                     # ids 1..6 after ingest
            writer.writerow([HOTELS[i % len(HOTELS)], "British",
                             3 + (i % 3), "Nice place", SHORT_TEXTS[i], "2024-01-01"])
        for i in range(n_long):                      # ids 7..216 after ingest
            pos = "The staff were okay overall" if i != 5 else "No Positive"
            writer.writerow([HOTELS[i % len(HOTELS)], "German",
                             long_rating(i), pos, long_text(i), "2024-01-02"])
        # dropped at ingest — never reach the DB or an LLM
        for i in range(N_EMPTY_NEG):
            neg = "" if i % 2 == 0 else "No Negative"
            writer.writerow([HOTELS[i % len(HOTELS)], "French", 7,
                             "Lovely view", neg, "2024-01-03"])


@pytest.fixture()
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "reviews.csv"
    write_review_csv(path)
    return path


@pytest.fixture()
def db_path(csv_path: Path, tmp_path: Path, monkeypatch) -> Path:
    """Temp DB seeded through the real ingest path; OPENEND_DB_PATH points at it."""
    path = tmp_path / "openeval2.sqlite3"
    monkeypatch.setenv("OPENEND_DB_PATH", str(path))
    ingest_module.ingest(csv_path, db_path=path)
    return path


@pytest.fixture()
def api_client(db_path):
    from fastapi.testclient import TestClient
    from api import app as app_module

    with TestClient(app_module.app) as client:
        yield client


@pytest.fixture()
def db_connect(db_path):
    return lambda: db_module.connect(db_path)


@pytest.fixture()
def insert_label(db_connect):
    """Directly store a labels row (bypasses the labeler) for rule-level tests."""
    def _insert(review_id: int, label_a: str | None, label_b: str | None,
                llm_error: int = 0, error: str | None = None, gold: str | None = None):
        agree = 1 if config.labels_agree(label_a, label_b) else 0
        with db_connect() as conn:
            conn.execute(
                "INSERT INTO labels (review_id, label_a, label_b, agree, llm_error, "
                "error, gold_label) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(review_id) DO UPDATE SET label_a=excluded.label_a, "
                "label_b=excluded.label_b, agree=excluded.agree, "
                "llm_error=excluded.llm_error, error=excluded.error, "
                "gold_label=excluded.gold_label",
                (review_id, label_a, label_b, agree, llm_error, error, gold))
    return _insert


@pytest.fixture()
def export_map(api_client):
    """id -> row dict from the unfiltered export CSV (BOM stripped)."""
    def _map():
        import io

        raw = api_client.get("/export.csv").content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))
        return {int(r["id"]): r for r in reader}
    return _map
