import pytest
from pathlib import Path
from utils.importer import (
    parse_line,
    parse_cells,
    parse_alternating_lines,
    parse_text,
    clean_result,
)


def test_standard_delimiters():
    assert parse_line("apple - olma") == ("apple", "olma")
    assert parse_line("apple – olma") == ("apple", "olma")
    assert parse_line("apple — olma") == ("apple", "olma")
    assert parse_line("apple : olma") == ("apple", "olma")
    assert parse_line("apple = olma") == ("apple", "olma")
    assert parse_line("apple => olma") == ("apple", "olma")
    assert parse_line("apple -> olma") == ("apple", "olma")
    assert parse_line("apple | olma") == ("apple", "olma")
    assert parse_line("apple ; olma") == ("apple", "olma")
    assert parse_line("apple ~ olma") == ("apple", "olma")
    assert parse_line("apple\tolma") == ("apple", "olma")
    assert parse_line("apple    olma") == ("apple", "olma")


def test_compound_words_not_split():
    # Chiziqcha bilan yoziladigan inglizcha so'zlar bo'linib ketmasligi kerak!
    assert parse_line("check-in - ro'yxatdan o'tish") == ("check-in", "ro'yxatdan o'tish")
    assert parse_line("well-known - mashhur") == ("well-known", "mashhur")
    assert parse_line("ice-cream - muzqaymoq") == ("ice-cream", "muzqaymoq")
    assert parse_line("father-in-law - qaynota") == ("father-in-law", "qaynota")


def test_phonetics_and_pos_extraction():
    assert parse_line("abandon [ə'bændən] - tark etmoq") == ("abandon", "tark etmoq")
    assert parse_line("abandon [ə'bændən] tark etmoq") == ("abandon", "tark etmoq")
    assert parse_line("abandon /ə'bændən/ tark etmoq") == ("abandon", "tark etmoq")
    assert parse_line("abandon (v.) - tark etmoq") == ("abandon", "tark etmoq")
    assert parse_line("abandon (verb) tark etmoq") == ("abandon", "tark etmoq")


def test_numbering_removal():
    assert parse_line("1. apple - olma") == ("apple", "olma")
    assert parse_line("1) apple - olma") == ("apple", "olma")
    assert parse_line("1 apple - olma") == ("apple", "olma")
    assert parse_line("№1 apple - olma") == ("apple", "olma")
    assert parse_line("[1] apple - olma") == ("apple", "olma")
    assert parse_line("• apple - olma") == ("apple", "olma")
    assert parse_line("- apple - olma") == ("apple", "olma")


def test_example_extraction():
    res1 = parse_line("apple - olma (masalan: I ate an apple)")
    assert res1 == ("apple", "olma", "I ate an apple")

    res2 = parse_line("apple - olma // He likes apples")
    assert res2 == ("apple", "olma", "He likes apples")

    res3 = parse_line("apple — olma — He ate an apple.")
    assert res3 == ("apple", "olma", "He ate an apple.")


def test_space_separated_words():
    assert parse_line("apple olma") == ("apple", "olma")
    assert parse_line("book kitob") == ("book", "kitob")
    assert parse_line("give up taslim bo'lmoq") == ("give up", "taslim bo'lmoq")


def test_cyrillic_uzbek():
    assert parse_line("apple - олма") == ("apple", "олма")
    assert parse_line("book - китоб") == ("book", "китоб")


def test_table_cells():
    # Header should return None
    assert parse_cells(["№", "English", "O'zbekcha"]) is None
    assert parse_cells(["Word", "Translation", "Example"]) is None

    # Numbered rows
    assert parse_cells(["1", "apple", "olma"]) == ("apple", "olma")
    assert parse_cells(["2", "abandon", "[ə'bændən]", "tark etmoq"]) == ("abandon", "tark etmoq")
    assert parse_cells(["3", "apple", "olma", "I ate an apple."]) == ("apple", "olma", "I ate an apple.")
    assert parse_cells(["book", "kitob"]) == ("book", "kitob")


def test_alternating_lines():
    lines = [
        "apple",
        "olma",
        "banana",
        "banan",
        "car",
        "mashina",
    ]
    pairs = parse_alternating_lines(lines)
    assert pairs == [
        ("apple", "olma"),
        ("banana", "banan"),
        ("car", "mashina"),
    ]


def test_parse_text_multi_formats():
    content = """
    # Lug'at ro'yxati
    1. apple - olma
    2. book : kitob
    3. check-in - ro'yxatdan o'tish
    abandon [ə'bændən] tark etmoq
    cat | mushuk
    dog ; kuchuk
    """
    pairs = parse_text(content)
    assert len(pairs) == 6
    eng_list = [p[0] for p in pairs]
    assert "apple" in eng_list
    assert "book" in eng_list
    assert "check-in" in eng_list
    assert "abandon" in eng_list
    assert "cat" in eng_list
    assert "dog" in eng_list
