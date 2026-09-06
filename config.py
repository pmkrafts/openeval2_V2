"""Shared constants, rules, and status logic for OpenEval2 (hotel reviews).

Single source of truth for the labeling/status rules so scripts, API, UI, and
tests never drift apart. Status is always DERIVED here — never stored.

Rule source: DOCS/OpenEval2-HOTEL-SPEC.md §5 and OpenEval2-REQUIREMENTS-FLOW.md.
Scores are Booking.com 1–10 (not 1–5) — see SPEC §5.5.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def default_db_path() -> Path:
    """SQLite location; override per process with OPENEND_DB_PATH (tests do)."""
    return Path(os.environ.get("OPENEND_DB_PATH", PROJECT_ROOT / "data" / "openeval2.sqlite3"))


# --- Dataset ---------------------------------------------------------------
CSV_COLUMNS = [
    "Hotel_Name",
    "Reviewer_Nationality",
    "Reviewer_Score",
    "Positive_Review",
    "Negative_Review",
    "Review_Date",
]

EMPTY_SENTINELS = {"No Negative", "No Positive"}

# --- Sampling / labeling ---------------------------------------------------
SAMPLE_SIZE = 200        # rows sent to the LLM, two independent calls each (SPEC §2)
AB_SAMPLE_SIZE = 200     # per-prompt ids for prompt A/B (SPEC: 100–200 per prompt)
WORD_MIN = 4             # word_count below this => needs_review regardless of labels

# Themes: hotel, not clothing (SPEC §4). Invalid model output is sanitized to
# "Other" in the labeler AND flagged needs_review (SPEC rule TS13).
THEMES = ["Location", "Staff", "Room", "Cleanliness", "Food", "Price", "Other"]

RATING_MIN, RATING_MAX = 1, 10        # Booking.com 10-point scale
RATING_CLASH_MAX = 4.0                # v2 clash: rating <= 4 ... (SPEC §5.5)
HOTELS_TOP_N = 50                     # /hotels caps at the 50 most frequent

# Metrics (v2)
GOLD_MIN_FOR_AGREEMENT = 30           # agree_with_gold null until gold_count >= 30

# --- Statuses --------------------------------------------------------------
STATUS_OK = "ok"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_UNLABELED = "unlabeled"
STATUSES = (STATUS_OK, STATUS_NEEDS_REVIEW, STATUS_UNLABELED)


# --- Rules -----------------------------------------------------------------
def is_valid_theme(label: str | None) -> bool:
    return label in THEMES


def labels_agree(label_a, label_b) -> bool:
    """SPEC §5.3: agree = label_a == label_b AND both are in the theme list."""
    return (
        label_a is not None
        and label_b is not None
        and is_valid_theme(label_a)
        and is_valid_theme(label_b)
        and label_a == label_b
    )


def rating_clash(label_a, label_b, rating) -> bool:
    """SPEC §5.5 (v2): rating <= 4 on the 10-point scale AND both labels Other
    AND word_count >= 4 -> needs_review. (word_count >= 4 is guaranteed by the
    caller — a short row is already needs_review.)"""
    if rating is None:
        return False
    return (
        rating <= RATING_CLASH_MAX
        and label_a == "Other"
        and label_b == "Other"
        and is_valid_theme(label_a)
        and is_valid_theme(label_b)
    )


def status_for(word_count: int | None, label_a=None, label_b=None,
               llm_error: bool = False, rating=None) -> str:
    """Status of a labeled row. Order matters (SPEC §5.4 / TS-rules):

    needs_review if word_count < 4 OR a labeler errored/flagged OR a label is
    missing OR a label is not a theme OR labels disagree OR (v2) rating clash.
    Otherwise ok.
    """
    if word_count is not None and word_count < WORD_MIN:
        return STATUS_NEEDS_REVIEW
    if llm_error:
        return STATUS_NEEDS_REVIEW
    if label_a is None or label_b is None:
        return STATUS_NEEDS_REVIEW
    if not (is_valid_theme(label_a) and is_valid_theme(label_b)):
        return STATUS_NEEDS_REVIEW
    if label_a != label_b:
        return STATUS_NEEDS_REVIEW
    if rating_clash(label_a, label_b, rating):
        return STATUS_NEEDS_REVIEW
    return STATUS_OK


def status_unlabeled(word_count: int | None) -> str:
    """Status of a row never sent to the labeler.

    Short texts still demand review (zero LLM spend — word_count is computed at
    ingest); everything else stays unlabeled.
    """
    if word_count is not None and word_count < WORD_MIN:
        return STATUS_NEEDS_REVIEW
    return STATUS_UNLABELED
