"""Rule-level tests against config.py — the single source of truth (TS10–TS15)."""
import config
from scripts.label_sample import MockLabeler, sanitize_label


def test_agreeing_long_row_is_ok():
    assert config.status_for(word_count=10, label_a="Staff", label_b="Staff") == "ok"


def test_disagreement_is_needs_review():
    assert config.status_for(word_count=10, label_a="Staff", label_b="Room") == \
        config.STATUS_NEEDS_REVIEW


def test_short_text_wins_even_when_labels_agree():
    assert config.status_for(word_count=2, label_a="Staff", label_b="Staff") == \
        config.STATUS_NEEDS_REVIEW


def test_missing_or_invalid_labels_need_review():
    assert config.status_for(word_count=10, label_a=None, label_b="Staff") == \
        config.STATUS_NEEDS_REVIEW
    assert config.status_for(word_count=10, label_a="dirty", label_b="Staff") == \
        config.STATUS_NEEDS_REVIEW


def test_llm_error_forces_needs_review():
    assert config.status_for(word_count=10, label_a="Staff", label_b="Staff",
                             llm_error=True) == config.STATUS_NEEDS_REVIEW


def test_rating_clash_low_score_both_other():
    """TS14: rating <= 4 (10-pt) + both Other + long text => needs_review."""
    assert config.status_for(word_count=10, label_a="Other", label_b="Other",
                             rating=3) == config.STATUS_NEEDS_REVIEW
    assert config.status_for(word_count=10, label_a="Other", label_b="Other",
                             rating=4.0) == config.STATUS_NEEDS_REVIEW


def test_no_clash_on_high_score_or_different_labels():
    assert config.status_for(word_count=10, label_a="Other", label_b="Other",
                             rating=8) == "ok"
    assert config.status_for(word_count=10, label_a="Other", label_b="Room",
                             rating=2) == config.STATUS_NEEDS_REVIEW


def test_agree_only_when_both_valid_and_equal():
    assert config.labels_agree("Staff", "Staff") is True
    assert config.labels_agree("Staff", "Room") is False
    assert config.labels_agree("Staff", None) is False
    assert config.labels_agree("dirty", "dirty") is False  # invalid label


def test_unlabeled_status():
    assert config.status_unlabeled(10) == config.STATUS_UNLABELED
    assert config.status_unlabeled(2) == config.STATUS_NEEDS_REVIEW


def test_themes_are_hotel_themes_not_clothing():
    """H4: theme list is the hotel set."""
    assert config.THEMES == ["Location", "Staff", "Room", "Cleanliness",
                             "Food", "Price", "Other"]
    assert "Fit" not in config.THEMES and "Style" not in config.THEMES


def test_sanitize_invalid_label_to_other():
    """TS13: model garbage is stored as Other and flagged invalid."""
    assert sanitize_label("dirty!!!") == ("Other", True)
    assert sanitize_label("Staff") == ("Staff", False)
    assert sanitize_label(None) == (None, True)
    assert sanitize_label(' "Room" ') == ("Room", False)


def test_mock_labeler_deterministic_and_themed():
    labeler = MockLabeler()
    assert labeler.label("The bed was broken") == "Room"
    assert labeler.label("Rude front desk staff") == "Staff"
    assert labeler.label("Breakfast food was cold") == "Food"
    assert labeler.label("Too expensive for the price") == "Price"
    assert labeler.label("Unrelated neutral sentence here") == "Other"
    assert labeler.label("The sheets were dirty") == "Cleanliness"
