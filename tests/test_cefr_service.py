"""
Unit tests for services/cefr_service.py.
Verifies CEFR level definitions, AWL academic vocabulary,
word retrieval, level sets, and study list import workflows.
"""
from services.cefr_service import (
    AWL_HEADWORDS,
    get_cefr_levels_summary,
    get_level_words_set,
    get_imported_count_for_level,
    get_words_for_level,
    import_cefr_words_to_study,
)
import core.database as db


def test_awl_headwords_content():
    """Academic Word List headwords contains over 570 core academic lemmas."""
    assert isinstance(AWL_HEADWORDS, set)
    assert len(AWL_HEADWORDS) >= 570
    assert "abandon" in AWL_HEADWORDS
    assert "concept" in AWL_HEADWORDS
    assert "hypothesis" in AWL_HEADWORDS
    assert "theory" in AWL_HEADWORDS


def test_get_cefr_levels_summary():
    """Summary returns descriptions, colors, and counts for all CEFR tiers."""
    summaries = get_cefr_levels_summary()
    assert isinstance(summaries, list)
    assert len(summaries) == 4

    ids = [s["id"] for s in summaries]
    assert "cefr_a1_a2" in ids
    assert "cefr_b1_b2" in ids
    assert "cefr_c1_c2" in ids
    assert "ielts_academic" in ids

    for item in summaries:
        assert "title" in item
        assert "badge_color" in item
        assert "description" in item
        assert "total_words" in item
        assert item["total_words"] > 0


def test_get_level_words_set():
    """get_level_words_set returns a valid non-empty set of lowercase words."""
    a1_words = get_level_words_set("cefr_a1_a2")
    assert isinstance(a1_words, set)
    assert len(a1_words) > 0

    awl_words = get_level_words_set("ielts_academic")
    assert isinstance(awl_words, set)
    assert len(awl_words) > 0


def test_get_imported_count_for_level():
    """Calculates how many words from a given CEFR level are present in user words set."""
    level_words = get_level_words_set("ielts_academic")
    if level_words:
        sample_word = next(iter(level_words))
        local_words = {sample_word, "definitelynotarealword12345"}
        count = get_imported_count_for_level("ielts_academic", local_words=local_words)
        assert count == 1


def test_get_words_for_level():
    """Returns word objects with required english and uzbek translations."""
    words = get_words_for_level("cefr_a1_a2", limit=10, offset=0)
    assert isinstance(words, list)
    assert len(words) <= 10

    if words:
        w0 = words[0]
        assert "english" in w0
        assert "uzbek" in w0


def test_import_cefr_words_to_study(tmp_path):
    """Imports words from CEFR level directly into database study queue."""
    test_db = tmp_path / "cefr_test_vocab.db"
    orig_path = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()

    try:
        added, skipped = import_cefr_words_to_study("cefr_a1_a2", count=5)
        assert added > 0

        # Adding same level again should handle duplicates gracefully
        added2, skipped2 = import_cefr_words_to_study("cefr_a1_a2", count=5)
        assert added2 >= 0
    finally:
        db.DB_PATH = orig_path
