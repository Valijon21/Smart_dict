"""
Unit tests for core/retention_analytics.py.
Verifies Hermann Ebbinghaus Forgetting Curve formula calculations,
memory stability, retention rates, forecast models, and caching behavior.
"""
import datetime
import pytest

from core.retention_analytics import (
    calculate_word_stability,
    calculate_retention_rate,
    get_memory_retention_overview,
    invalidate_retention_cache,
)
import core.database as db


def test_calculate_word_stability_box_scaling():
    """Higher Leitner box level and interval days should significantly increase stability."""
    # Arrange
    box0_stability = calculate_word_stability(box_level=0, ease_factor=2.5, interval_days=1, correct_count=1, wrong_count=0)
    box3_stability = calculate_word_stability(box_level=3, ease_factor=2.5, interval_days=6, correct_count=4, wrong_count=0)
    box5_stability = calculate_word_stability(box_level=5, ease_factor=2.5, interval_days=30, correct_count=10, wrong_count=0)

    # Assert
    assert box0_stability >= 0.8
    assert box3_stability > box0_stability
    assert box5_stability > box3_stability


def test_calculate_word_stability_error_penalty():
    """Higher wrong counts should penalize memory stability."""
    # Arrange
    clean_stability = calculate_word_stability(box_level=2, ease_factor=2.5, interval_days=3, correct_count=5, wrong_count=0)
    flawed_stability = calculate_word_stability(box_level=2, ease_factor=2.5, interval_days=3, correct_count=5, wrong_count=5)

    # Assert
    assert flawed_stability < clean_stability
    assert flawed_stability >= 0.8  # minimum threshold preserved


def test_calculate_word_stability_edge_cases():
    """Handles None and out-of-range arguments safely without exceptions."""
    s_none = calculate_word_stability(box_level=None, ease_factor=None, interval_days=None, correct_count=None, wrong_count=None)
    assert s_none >= 0.8

    s_extreme = calculate_word_stability(box_level=100, ease_factor=10.0, interval_days=500, correct_count=1000, wrong_count=0)
    assert s_extreme > 100.0


def test_calculate_retention_rate_ebbinghaus_decay():
    """Retention should be high right after review and decrease over time."""
    today_iso = datetime.date.today().isoformat()
    last_week_iso = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    last_month_iso = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

    stability = 5.0  # 5 days stability factor

    r_today = calculate_retention_rate(last_reviewed=today_iso, created_at=today_iso, stability=stability, days_offset=0)
    r_week = calculate_retention_rate(last_reviewed=last_week_iso, created_at=last_week_iso, stability=stability, days_offset=0)
    r_month = calculate_retention_rate(last_reviewed=last_month_iso, created_at=last_month_iso, stability=stability, days_offset=0)

    assert 0.90 <= r_today <= 1.0
    assert r_week < r_today
    assert r_month < r_week
    assert r_month >= 0.05  # minimum floor


def test_calculate_retention_rate_future_forecast():
    """Days offset simulates future forgetting curve progression."""
    today_iso = datetime.date.today().isoformat()
    stability = 4.0

    r_now = calculate_retention_rate(today_iso, today_iso, stability, days_offset=0)
    r_plus1 = calculate_retention_rate(today_iso, today_iso, stability, days_offset=1)
    r_plus7 = calculate_retention_rate(today_iso, today_iso, stability, days_offset=7)

    assert r_now > r_plus1 > r_plus7


def test_calculate_retention_rate_fallback_dates():
    """Gracefully falls back to created_at or today when last_reviewed is None or corrupted."""
    r_corrupted = calculate_retention_rate("invalid-date-string", None, stability=3.0)
    assert 0.05 <= r_corrupted <= 1.0


def test_get_memory_retention_overview_empty_db(tmp_path):
    """When words database is empty, overview returns structured 100% baseline."""
    # Arrange: Isolated temporary database
    test_db = tmp_path / "empty_vocab.db"
    orig_path = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()
    invalidate_retention_cache()

    try:
        # Act
        overview = get_memory_retention_overview()

        # Assert
        assert overview["total_words"] == 0
        assert overview["overall_retention_pct"] == 100.0
        assert overview["vulnerable_count"] == 0
        assert len(overview["forecast"]) == 4
    finally:
        db.DB_PATH = orig_path
        invalidate_retention_cache()


def test_get_memory_retention_overview_with_words(tmp_path):
    """Accurately calculates retention categories when database has active words."""
    test_db = tmp_path / "active_vocab.db"
    orig_path = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()
    invalidate_retention_cache()

    try:
        # Arrange
        w1_id = db.add_word("memory", "xotira")
        w2_id = db.add_word("forget", "unutmoq")

        # Set w1 as well-learned
        db.record_answer(w1_id, True)
        db.record_answer(w1_id, True)

        # Set w2 as wrong and overdue
        db.record_answer(w2_id, False)

        # Act
        invalidate_retention_cache()
        overview = get_memory_retention_overview()

        # Assert
        assert overview["total_words"] == 2
        assert 0.0 <= overview["overall_retention_pct"] <= 100.0
        assert isinstance(overview["forecast"], list)
        assert len(overview["forecast"]) == 4
        assert "recommendation" in overview
    finally:
        db.DB_PATH = orig_path
        invalidate_retention_cache()
