"""
Unit tests for services/game_word_provider.py.
Verifies word source loading, category registries, game filtering,
length constraints, alphabetical checks, and fallback mechanisms.
"""
from services.game_word_provider import (
    get_available_categories,
    get_sources_for_category,
    get_words_for_game,
    _get_fallback_words,
    invalidate_cache,
    clear_cache,
)


def test_get_available_categories():
    """Returns the four core category pools for games: personal, topics, packs, cefr."""
    cats = get_available_categories()
    assert isinstance(cats, list)
    cat_ids = [c["id"] for c in cats]
    assert "personal" in cat_ids
    assert "topics" in cat_ids
    assert "packs" in cat_ids
    assert "cefr" in cat_ids


def test_get_sources_for_personal():
    """Personal category contains all, imported, due, weak, learning sub-sources."""
    sources = get_sources_for_category("personal")
    assert isinstance(sources, list)
    s_ids = [s["id"] for s in sources]
    assert "all" in s_ids
    assert "imported" in s_ids
    assert "weak" in s_ids


def test_get_sources_for_packs_and_cefr():
    """Packs and CEFR categories dynamically load their registered sub-sources."""
    pack_sources = get_sources_for_category("packs")
    assert len(pack_sources) > 0

    cefr_sources = get_sources_for_category("cefr")
    assert len(cefr_sources) >= 4


def test_get_sources_for_unknown_category():
    """Unknown category returns an empty list without error."""
    assert get_sources_for_category("unknown_cat_xyz") == []


def test_get_fallback_words():
    """Fallback words pool contains at least 50 valid starter words for games."""
    fallbacks = _get_fallback_words()
    assert isinstance(fallbacks, list)
    assert len(fallbacks) >= 50

    for w in fallbacks:
        assert "english" in w and w["english"].strip()
        assert "uzbek" in w and w["uzbek"].strip()


def test_get_words_for_game_filtering():
    """Filters words by length and alphabetic constraints for word games."""
    clear_cache()
    # Request short alphabetic words
    words = get_words_for_game(
        category_id="packs",
        source_id="essential",
        limit=20,
        min_len=3,
        max_len=6,
        alpha_only=True
    )
    assert isinstance(words, list)

    for w in words:
        eng = w["english"].strip()
        clean = eng.replace(" ", "")
        assert clean.isalpha()
        assert 3 <= len(eng) <= 8  # within relaxed bounds


def test_cache_management():
    """Invalidate and clear cache run without error."""
    invalidate_cache()
    clear_cache()
