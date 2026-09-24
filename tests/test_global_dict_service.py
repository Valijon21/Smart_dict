"""
Unit tests for services/global_dict_service.py.
Verifies offline dictionary search, HTML cleaning, example formatting,
word details lookups, and study queue synchronization.
"""
from services.global_dict_service import (
    clean_html,
    clean_examples,
    get_uzbek_search_patterns,
    search_global_words,
    get_word_full_details,
    add_to_study_list,
)
import core.database as db


def test_clean_html_removes_tags():
    """clean_html strips HTML tags and escapes special characters."""
    html_input = "<p>This is <b>bold</b> and <i>italic</i> &amp; text.</p>"
    cleaned = clean_html(html_input)
    assert "<p>" not in cleaned
    assert "<b>" not in cleaned
    assert "bold and italic" in cleaned


def test_clean_html_handles_empty_and_none():
    """clean_html returns empty string for empty input or None."""
    assert clean_html("") == ""
    assert clean_html(None) == ""
    assert clean_html("   ") == ""


def test_clean_examples_extraction():
    """Extracts clean example sentences from raw string."""
    raw = "1. He is a brave man.\n2. She made a brave decision."
    examples = clean_examples(raw)
    assert isinstance(examples, list)
    assert len(examples) == 2
    assert "brave" in examples[0]

    # None and empty
    assert clean_examples(None) == []
    assert clean_examples("") == []


def test_get_uzbek_search_patterns():
    """Generates search variations for apostrophes and accents."""
    patterns = get_uzbek_search_patterns("ko'rmoq")
    assert isinstance(patterns, list)
    assert len(patterns) > 0


def test_search_global_words_and_details():
    """Searches offline dictionary and retrieves word full details."""
    results = search_global_words("abandon", limit=5)
    assert isinstance(results, list)

    if results:
        w = results[0]
        assert "english" in w
        assert "abandon" in w["english"].lower()

        # Test details lookup
        details = get_word_full_details(english=w["english"])
        assert details is not None
        assert details["english"].lower() == w["english"].lower()


def test_add_to_study_list(tmp_path):
    """Adds a word from the global dictionary directly to user vocabulary database."""
    test_db = tmp_path / "global_dict_test_vocab.db"
    orig_path = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()

    try:
        success, msg, w_id = add_to_study_list("diligent", "tirishqoq, g'ayratli", "He is a diligent student.")
        assert success is True
        assert w_id > 0

        # Adding same word again reports already added
        success2, msg2, w_id2 = add_to_study_list("diligent", "tirishqoq", "")
        assert success2 is False
    finally:
        db.DB_PATH = orig_path
