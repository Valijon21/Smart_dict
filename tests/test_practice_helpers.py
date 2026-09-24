"""
Unit tests for ui.views.practice_helpers.
Verifies cloze sentence generation, target token extraction, and word scramble shuffling.
"""
from ui.views.practice_helpers import (
    prepare_cloze_data, prepare_scramble_chars,
    extract_answer_options, check_user_answer, get_best_match_target
)


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


def test_extract_answer_options():
    # Parenthesis removal and preservation
    opts1 = extract_answer_options("Think (have an opinion)")
    assert "think" in opts1
    assert "think (have an opinion)" in opts1

    # Slashes
    opts2 = extract_answer_options("Seem / Appear")
    assert "seem" in opts2
    assert "appear" in opts2

    # Uzbek with slashes and commas
    opts3 = extract_answer_options("eslamoq / yodda tutmoq, yodlamoq")
    assert "eslamoq" in opts3
    assert "yodda tutmoq" in opts3
    assert "yodlamoq" in opts3


def test_check_user_answer():
    # Direct match with parenthesis in expected
    assert check_user_answer("think", "Think (have an opinion)")
    assert check_user_answer("Think", "Think (have an opinion)")
    assert check_user_answer("to think", "Think (have an opinion)")

    # Slash options
    assert check_user_answer("seem", "Seem / Appear")
    assert check_user_answer("appear", "Seem / Appear")
    assert check_user_answer("eslamoq", "eslamoq / yodda tutmoq")
    assert check_user_answer("yodda tutmoq", "eslamoq / yodda tutmoq")

    # Apostrophe variations
    assert check_user_answer("deb o'ylamoq", "deb oʻylamoq")
    assert check_user_answer("deb oylamoq", "deb o'ylamoq")
    assert check_user_answer("ko'rmoq", "ko‘rmoq")

    # Incorrect answers
    assert not check_user_answer("wrong", "Think (have an opinion)")
    assert not check_user_answer("", "Think")


def test_get_best_match_target():
    assert get_best_match_target("thinck", "Think (have an opinion)") == "think"
    assert get_best_match_target("seemm", "Seem / Appear") == "seem"
    assert get_best_match_target("apearr", "Seem / Appear") == "appear"

