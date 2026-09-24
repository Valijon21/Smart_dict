"""
Unit tests for ui.views.practice_helpers.
Verifies cloze sentence generation, target token extraction, and word scramble shuffling.
"""
from ui.views.practice_helpers import prepare_cloze_data, prepare_scramble_chars


def test_prepare_cloze_data_direct_match():
    word_data = {
        "english": "abandon",
        "uzbek": "tashlab ketmoq",
        "example": "He had to abandon his car in the snow.",
    }
    res = prepare_cloze_data(word_data)
    assert res is not None
    assert res["target_token"].lower() == "abandon"
    assert "______" in res["sentence_masked"]
    assert "tashlab ketmoq" in res["uzbek_hint"]
    assert "abandon" in res["correct_tokens"]


def test_prepare_cloze_data_inflected_form():
    word_data = {
        "english": "accommodate",
        "uzbek": "joylashtirmoq",
        "example": "The hotel accommodated over five hundred guests.",
    }
    res = prepare_cloze_data(word_data)
    assert res is not None
    assert "accommodated" in res["target_token"].lower()
    assert "accommodated" in res["correct_tokens"]
    assert "accommodate" in res["correct_tokens"]


def test_prepare_cloze_data_fallback_template():
    word_data = {
        "english": "perseverance",
        "uzbek": "matonat",
        "example": "",
    }
    res = prepare_cloze_data(word_data)
    assert res is not None
    assert "perseverance" in res["correct_tokens"]
    assert "______" in res["sentence_masked"]


def test_prepare_scramble_chars():
    word = "beautiful"
    chars = prepare_scramble_chars(word)
    assert len(chars) == len(word)
    assert sorted(chars) == sorted(list(word.lower()))
