import sys
import time
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import database as db
import core.database as _cdb
import tts
from utils import text_search_utils
from ui.views.practice_view import PracticeWidget


@pytest.fixture(scope="module")
def app():
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)
    return _app


@pytest.fixture
def temp_db(tmp_path):
    test_db = tmp_path / "test_vocab.db"
    orig_path = _cdb.DB_PATH
    _cdb.DB_PATH = test_db
    _cdb.init_db()

    db.add_word("beautiful", "chiroyli, go'zal")
    db.add_word("accommodate", "joylashtirmoq")
    db.add_word("pronunciation", "talaffuz")
    db.add_word("library", "kutubxona")

    yield test_db
    _cdb.DB_PATH = orig_path


def test_levenshtein_distance():
    """Levenshtein masofasini to'g'ri hisoblash testi."""
    assert text_search_utils.levenshtein_distance("apple", "apple") == 0
    assert text_search_utils.levenshtein_distance("Apple", "apple") == 0
    assert text_search_utils.levenshtein_distance("cat", "cut") == 1
    assert text_search_utils.levenshtein_distance("accomodate", "accommodate") == 1
    assert text_search_utils.levenshtein_distance("beutiful", "beautiful") == 1
    assert text_search_utils.levenshtein_distance("", "test") == 4
    assert text_search_utils.levenshtein_distance("test", "") == 4


def test_compute_visual_diff_typo():
    """1-2 ta harf farqi bo'lganda typo aniqlanishi va HTML belgilanishi."""
    diff = text_search_utils.compute_visual_diff("accomodate", "accommodate")
    assert diff["is_typo"] is True
    assert diff["distance"] == 1
    assert "1 ta harfda adashdingiz" in diff["tip_message"]
    assert "underline" in diff["expected_diff_html"]

    # 2 ta harf farqi
    diff2 = text_search_utils.compute_visual_diff("beutifull", "beautiful")
    assert diff2["is_typo"] is True
    assert diff2["distance"] == 2
    assert "2 ta harfda adashdingiz" in diff2["tip_message"]

    # Butunlay boshqa so'z bo'lsa typo bo'lmasligi kerak
    diff3 = text_search_utils.compute_visual_diff("banana", "beautiful")
    assert diff3["is_typo"] is False
    assert diff3["tip_message"] == ""


def test_fuzzy_search_in_database(temp_db):
    """Bazada xato yozilgan so'zni Levenshtein fuzzy search orqali topish."""
    # "beutiful" -> "beautiful" ni topishi kerak
    res1 = db.search_words("beutiful")
    assert len(res1) >= 1
    assert res1[0]["english"].lower() == "beautiful"

    # "accomodate" -> "accommodate" ni topishi kerak
    res2 = db.search_words("accomodate")
    assert len(res2) >= 1
    assert res2[0]["english"].lower() == "accommodate"


def test_fuzzy_search_in_global_dict():
    """64,000 so'zlik global lug'atda xato yozilgan so'zlarni Levenshtein orqali topish."""
    import services.global_dict_service as gds
    res1 = gds.search_global_words("wunderful", limit=3)
    assert len(res1) >= 1
    assert res1[0]["english"].lower() == "wonderful"

    res2 = gds.search_global_words("beutiful", limit=3)
    assert len(res2) >= 1
    assert res2[0]["english"].lower() == "beautiful"


def test_practice_visual_diff_and_shake(app, temp_db):
    """Mashqda xato qilinganda visual diff chiqishi va karta silkinishi."""
    w = PracticeWidget("en_uz")
    assert w.current is not None

    # Xato javob kiritamiz
    w.answer_input.setText("chiroylii")
    w.check_answer()

    assert w.session_wrong == 1
    assert len(w.session_mistake_word_ids) == 1
    assert w.current["id"] in w.session_mistake_word_ids

    # Feedback matnida xato va visual diff elementlari borligini tekshiramiz
    fb_text = w.feedback_label.text()
    assert "❌ To'g'ri javob" in fb_text
    assert "Davom etish uchun" in fb_text


def test_practice_slow_audio_btn(app, temp_db):
    """Mashq oynasida 🐢 sekin audio tugmasi mavjudligi va bosilishi."""
    w = PracticeWidget("en_uz")
    assert hasattr(w, "slow_audio_btn")
    assert w.slow_audio_btn.text() == "🐢"

    # play_slow_audio chaqirilganda xatolik chiqmasligi
    w.play_slow_audio()
    # speak_slow tts moduli orqali chaqirilishi
    tts.speak_slow("test")


def test_retry_session_mistakes(app, temp_db):
    """Partiya yakunlanganda xatolar ustida qayta ishlash tugmasi ishlashi."""
    w = PracticeWidget("en_uz")
    initial_id = w.current["id"]

    # Xato qilamiz
    w.answer_input.setText("xato_javob")
    w.check_answer()

    # Navbatni bo'shatamiz va partiya yakunlangan holatni chaqiramiz
    w.queue = []
    w.is_waiting_for_enter = False
    w.next_word()

    assert not w.retry_mistakes_btn.isHidden()
    assert "1 ta so'z" in w.retry_mistakes_btn.text()

    # "Xatolar ustida ishlash" tugmasini bosamiz
    w.retry_session_mistakes()

    assert w.current is not None
    assert w.current["id"] == initial_id
    assert "Partiyadagi xatolar" in w.mode_label.text()
