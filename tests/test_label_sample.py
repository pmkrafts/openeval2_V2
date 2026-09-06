"""Label-sample tests (H5, TS44): mock provider is offline and deterministic."""
from conftest import N_LONG, N_SHORT, TOTAL_ROWS

import db as db_module
from scripts.label_sample import label_sample


def test_label_sample_labels_200_rows_twice(db_path, monkeypatch):
    """H5: 200 rows end up with label_a AND label_b, no NULLs, zero errors."""
    monkeypatch.setenv("OPENEND_DB_PATH", str(db_path))
    result = label_sample(db_path=db_path, count=200, seed=42, provider="mock")
    assert result["labeled"] == 200
    assert result["errors"] == 0
    with db_module.connect(db_path) as conn:
        n = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
        nulls = conn.execute(
            "SELECT COUNT(*) FROM labels WHERE label_a IS NULL OR label_b IS NULL"
        ).fetchone()[0]
        bad_themes = conn.execute(
            "SELECT COUNT(*) FROM labels WHERE label_a NOT IN "
            "('Location','Staff','Room','Cleanliness','Food','Price','Other')"
        ).fetchone()[0]
    assert n == 200
    assert nulls == 0
    assert bad_themes == 0


def test_mock_rerun_with_force_is_deterministic(db_path, monkeypatch):
    """Same seed + force => identical stored pairs (TS02-style, offline TS44)."""
    def _pairs() -> list[tuple]:
        label_sample(db_path=db_path, count=200, seed=7, provider="mock", force=True)
        with db_module.connect(db_path) as conn:
            return sorted(tuple(r) for r in conn.execute(
                "SELECT review_id, label_a, label_b FROM labels").fetchall())

    first = _pairs()
    second = _pairs()
    assert first == second
    assert len(first) == 200


def test_short_texts_can_be_labeled_but_stay_needs_review(db_path, insert_label,
                                                          api_client):
    """Labeling a short row never flips it to ok (S3)."""
    insert_label(1, "Room", "Room")  # id 1 = "Dirty room" (2 words)
    body = api_client.get("/rows", params={"limit": 2000}).json()
    row = next(r for r in body["rows"] if r["id"] == 1)
    assert row["status"] == "needs_review"
    assert row["label_a"] == "Room" and row["label_b"] == "Room"


def test_sample_only_unlabeled_rows_by_default(db_path):
    label_sample(db_path=db_path, count=200, seed=42, provider="mock")
    result = label_sample(db_path=db_path, count=200, seed=42, provider="mock")
    # 216 rows total, 200 labeled -> only 16 remain to sample; no duplicate labels
    assert result["sample"] == TOTAL_ROWS - 200 == N_SHORT + N_LONG - 200
