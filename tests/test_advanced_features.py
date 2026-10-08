import core.db.connection as _conn
import sys
import time
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core.database as db
import core.database as _cdb
import services.tts_service as tts
from utils import text_search_utils
from ui.views.practice.practice_controller import PracticeWidget


@pytest.fixture(scope="module")
def app():
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)
    return _app


@pytest.fixture
def temp_db(tmp_path):
    test_db = tmp_path / "test_vocab.db"
    orig_path = _conn.DB_PATH
    _conn.DB_PATH = test_db
    _cdb.init_db()

    db.add_word("beautiful", "chiroyli, go'zal")
    db.add_word("accommodate", "joylashtirmoq")
    db.add_word("pronunciation", "talaffuz")
    db.add_word("library", "kutubxona")

    yield test_db
    _conn.DB_PATH = orig_path


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
    """Mashqda xato qilinganda sessiyaga yozilishi va holat boshqaruvi."""
    w = PracticeWidget("en_uz")
    w.start_practice()
    assert w.session.current is not None

    # Xato javob kiritamiz
    w.typing_mode.answer_input.setText("chiroylii")
    w.on_submit_clicked()

    assert w.session.session_wrong == 1
    assert len(w.session.session_mistake_word_ids) == 1
    assert w.session.current["id"] in w.session.session_mistake_word_ids
    assert w.is_waiting_for_enter is True


def test_practice_listening_mode_integration(app, temp_db):
    """Mashq trenajyorida Eshitib yozish (listening) rejimining to'g'ri ishlashi."""
    w = PracticeWidget("en_uz")
    w.start_practice()
    w.switch_mode("listening")
    assert w.quiz_mode == "listening"
    assert hasattr(w.listening_mode, "play_btn")
    assert hasattr(w.listening_mode, "slow_btn")


def test_retry_session_mistakes(app, temp_db):
    """Partiya yakunlanganda xatolar ustida qayta ishlash ishlashi."""
    w = PracticeWidget("en_uz")
    w.start_practice()
    initial_id = w.session.current["id"]

    # Xato qilamiz
    w.typing_mode.answer_input.setText("xato_javob")
    w.on_submit_clicked()

    assert w.session.session_mistake_word_ids == [initial_id]

    # "Xatolar ustida ishlash" logikasini tekshiramiz
    w.session.load_mistakes()
    assert w.session.current is not None
    assert w.session.current["id"] == initial_id
