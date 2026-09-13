import sys
import time
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import database as db
import core.database as _cdb
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

    # So'zlar qo'shamiz
    db.add_word("apple", "olma")
    db.add_word("banana", "banan")
    db.add_word("cat", "mushuk")
    db.add_word("dog", "it")
    db.add_word("elephant", "fil")

    yield test_db
    _cdb.DB_PATH = orig_path


def test_practice_session_persistence(app, temp_db):
    """Boshqa bo'limga o'tib qaytganda sessiya reset bo'lmasligini tekshirish."""
    w = PracticeWidget("en_uz")
    assert w.current is not None
    initial_word = w.current["english"]
    initial_queue_len = len(w.queue)

    # 1-Enter: Birinchi so'zni xato qilib yuboramiz
    w.answer_input.setText("not_correct")
    w.check_answer()

    assert w.session_wrong == 1
    assert w.is_waiting_for_enter is True
    assert w.current["english"] == initial_word

    # Endi boshqa bo'limga o'tib qaytishni (resume_session) simulyatsiya qilamiz
    w.resume_session()

    # Sessiya to'liq saqlanib qolgan bo'lishi kerak
    assert w.current["english"] == initial_word
    assert len(w.queue) == initial_queue_len
    assert w.session_wrong == 1
    assert w.is_waiting_for_enter is True

    # 2-Enter: Foydalanuvchi to'g'ri javobni ko'rgach (0.4s dan so'ng) Enter bosadi
    time.sleep(0.4)
    w.check_answer()
    assert w.is_waiting_for_enter is False
    assert w.current["english"] != initial_word


def test_practice_mistake_waits_for_enter(app, temp_db):
    """Xato qilinganda to'g'ri javob ko'rinishi va faqat 2-Enter bosilganda o'tishi."""
    w = PracticeWidget("en_uz")
    cur_word = w.current

    # 1-Enter: Xato javob berish
    w.answer_input.setText("mutlaqo_notogri_javob")
    w.check_answer()

    # 1-Enter'dan so'ng darhol keyingisiga sakrab ketmasligi (debounce himoyasi)
    assert w.is_waiting_for_enter is True
    assert w.answer_input.isReadOnly() is True
    assert w.submit_btn.text() == "Davom etish ↵"
    assert cur_word["uzbek"] in w.feedback_label.text()

    # Agar 1-Enter bilan bir xil millisekundda takroriy event kelsa, u o'tkazilmaydi
    w.check_answer()
    assert w.is_waiting_for_enter is True

    # 2-Enter: Foydalanuvchi so'zni o'qib bo'lgach (masalan 0.4s o'tgach) Enter bosadi
    time.sleep(0.4)
    w.check_answer()

    assert w.is_waiting_for_enter is False
    assert w.answer_input.isReadOnly() is False
    assert w.submit_btn.text() == "Tekshirish ↵"
    assert w.current["id"] != cur_word["id"]

