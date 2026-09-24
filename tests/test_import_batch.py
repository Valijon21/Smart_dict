"""
Tests for unified import batch resolution (new + existing words) and multi-game practice integration.
"""
import pytest
import os
import sqlite3
from PyQt6.QtWidgets import QApplication

import core.database as db
from services import game_word_provider as gwp
from ui.games.match_game import MatchGameWidget
from ui.games.blitz_game import BlitzGameWidget
from ui.games.word_fall_game import WordFallGameWidget
from ui.games.crossword_game import CrosswordGameWidget
from ui.main_window import MainWindow


@pytest.fixture
def app_instance():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def temp_import_db(tmp_path, monkeypatch):
    """Izolyatsiya qilingan vaqtinchalik test ma'lumotlar bazasi."""
    db_file = tmp_path / "import_test.db"
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.init_db()
    gwp.invalidate_cache()
    yield db_file


def test_bulk_add_words_non_duplicating_resolution(temp_import_db):
    """Mavjud so'zlar dublikat qilinmasligi, lekin ID lari mashq to'plamiga birlashtirilishini tekshirish."""
    # 1. Avval bazaga 3 ta so'z kiritamiz
    id1 = db.add_word("apple", "olma")
    id2 = db.add_word("book", "kitob")
    id3 = db.add_word("car", "mashina")
    assert id1 and id2 and id3

    # 2. Endi import uchun 5 ta so'z beramiz (2 tasi yangi, 3 tasi bazada bor)
    import_pairs = [
        ("apple", "olma"),           # Mavjud
        ("sun", "quyosh"),           # Yangi
        ("book", "kitob"),           # Mavjud
        ("moon", "oy"),              # Yangi
        ("car", "mashina"),          # Mavjud
    ]

    summary = db.bulk_add_words(import_pairs, source="import")

    # Dublikat qo'shilmasligi kerak: yangi 2 ta, dublikat 3 ta
    assert summary["added"] == 2
    assert summary["duplicates"] == 3
    assert len(summary["word_ids"]) == 2
    assert len(summary["existing_ids"]) == 3

    # Jami to'plam barcha 5 ta so'zni o'z ichiga olishi kerak!
    all_batch = summary["all_batch_ids"]
    assert len(all_batch) == 5
    assert id1 in all_batch
    assert id2 in all_batch
    assert id3 in all_batch

    # Bazada jami so'zlar soni 5 ta bo'lishi kerak (3 ta eski + 2 ta yangi, dublikatsiz)
    assert db.get_total_word_count() == 5

    # Oxirgi import ID lari settingsda saqlanganini tekshirish
    saved_ids = db.get_last_import_word_ids()
    assert saved_ids == all_batch

    # Oxirgi import qilingan so'zlar qatorlarini olish
    imported_rows = db.get_last_imported_words()
    assert len(imported_rows) == 5
    eng_words = [r["english"] for r in imported_rows]
    assert "apple" in eng_words
    assert "sun" in eng_words
    assert "moon" in eng_words


def test_search_words_import_filter(temp_import_db):
    """Lug'atda status_filter='import' orqali oxirgi import so'zlarini ajratib olishni tekshirish."""
    db.add_word("zebra", "zebra")
    db.add_word("lion", "sher")

    batch = [
        ("computer", "kompyuter"),
        ("keyboard", "klaviatura"),
    ]
    summary = db.bulk_add_words(batch, source="import")
    assert summary["added"] == 2

    # 'import' filtri faqat import qilinganlarni qaytarishi kerak
    import_results = db.search_words(status_filter="import")
    assert len(import_results) == 2
    res_eng = [r["english"] for r in import_results]
    assert "computer" in res_eng
    assert "keyboard" in res_eng
    assert "zebra" not in res_eng

    # Qidiruv bilan birga ishlashini tekshirish
    filtered = db.search_words(query="comp", status_filter="import")
    assert len(filtered) == 1
    assert filtered[0]["english"] == "computer"


def test_game_word_provider_imported_source(temp_import_db):
    """GameWordProvider orqali o'yinlarda 'imported' to'plamini yuklashni tekshirish."""
    pairs = [
        ("water", "suv"),
        ("fire", "olov"),
        ("earth", "yer"),
        ("wind", "shamol"),
    ]
    db.bulk_add_words(pairs, source="import")
    gwp.invalidate_cache()

    sources = gwp.get_sources_for_category(gwp.CAT_PERSONAL)
    source_ids = [s["id"] for s in sources]
    assert "imported" in source_ids

    game_words = gwp.get_words_for_game(gwp.CAT_PERSONAL, "imported")
    assert len(game_words) >= 4
    eng_words = [w["english"] for w in game_words]
    assert "water" in eng_words
    assert "fire" in eng_words


def test_custom_words_in_games(app_instance, temp_import_db):
    """O'yinlar vidjetlarida set_custom_words ishlashini tekshirish."""
    id1 = db.add_word("tree", "daraxt")
    id2 = db.add_word("flower", "gul")
    id3 = db.add_word("forest", "o'rmon")
    id4 = db.add_word("leaf", "barg")
    ids = [id1, id2, id3, id4]

    # 1. MatchGameWidget
    match_game = MatchGameWidget()
    match_game.set_custom_words(ids)
    assert hasattr(match_game, "_custom_words")
    assert len(match_game._custom_words) == 4

    # 3. BlitzGameWidget
    blitz_game = BlitzGameWidget()
    blitz_game.set_custom_words(ids)
    assert hasattr(blitz_game, "_custom_words")
    assert len(blitz_game._custom_words) == 4

    # 4. WordFallGameWidget
    fall_game = WordFallGameWidget()
    fall_game.set_custom_words(ids)
    assert hasattr(fall_game, "_custom_words")
    assert len(fall_game._custom_words) == 4

    # 5. CrosswordGameWidget
    cross_game = CrosswordGameWidget()
    cross_game.set_custom_words(ids)
    assert hasattr(cross_game, "_custom_words")


def test_main_window_custom_practice_dispatch(app_instance, temp_import_db):
    """MainWindow start_custom_practice orqali barcha yo'nalishlar xatosiz ochilishini tekshirish."""
    win = MainWindow()
    id1 = db.add_word("star", "yulduz")
    id2 = db.add_word("galaxy", "galaktika")
    ids = [id1, id2]

    # EN -> UZ
    win.start_custom_practice(ids, "en_uz")
    assert win.current_page_key == "en_uz"

    # UZ -> EN
    win.start_custom_practice(ids, "uz_en")
    assert win.current_page_key == "uz_en"

    # Flashcard
    win.start_custom_practice(ids, "flashcard")
    assert win.current_page_key == "en_uz"
    assert win.get_or_create_page("en_uz").quiz_mode == "flashcard"

    # Match Game
    win.start_custom_practice(ids, "match")
    assert win.current_page_key == "match"

    # Blitz Game
    win.start_custom_practice(ids, "blitz")
    assert win.current_page_key == "blitz"

    # Dictionary Import
    win.start_custom_practice(ids, "dictionary_import")
    assert win.current_page_key == "dictionary"
    assert win.dictionary.current_filter == "import"

    win.close()
