"""
tests/test_speaking_view.py
Speaking & Talaffuz Trenajyori (SpeakingWidget) uchun testlar.
"""
import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core.database as db
import ui.theme_manager as theme_manager
from ui.views.speaking_view import SpeakingWidget

# Headless / GUI testlar uchun QApplication yagona nusxasi
app = QApplication.instance()
if not app:
    app = QApplication([])


@pytest.fixture
def temp_speaking_db(tmp_path):
    test_db = tmp_path / "speaking_test.db"
    orig_path = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()

    # Test uchun bir nechta so'zlar
    db.add_word("ubiquitous", "hamma joyda mavjud", example="Smartphones are ubiquitous.")
    db.add_word("perseverance", "qat'iyat, sabot", example="Success requires perseverance.")
    db.add_word("eloquent", "notiq, fasih", example="She gave an eloquent speech.")

    yield test_db
    db.DB_PATH = orig_path


def test_speaking_widget_initialization(temp_speaking_db):
    widget = SpeakingWidget()
    assert widget is not None
    assert len(widget.words_list) >= 3
    assert widget.current_word is not None
    assert widget.current_word["english"] in ("ubiquitous", "perseverance", "eloquent")


def test_speaking_widget_navigation(temp_speaking_db):
    widget = SpeakingWidget()
    initial_word = widget.current_word["english"]

    # Keyingi so'zga o'tish
    widget._next_word()
    next_word = widget.current_word["english"]
    assert next_word != initial_word or len(widget.words_list) == 1

    # Oldingi so'zga qaytish
    widget._prev_word()
    assert widget.current_word["english"] == initial_word


def test_speaking_widget_filters(temp_speaking_db):
    widget = SpeakingWidget()

    # Noto'g'ri fe'llar filtrini tanlash (index 2)
    widget.combo_filter.setCurrentIndex(2)
    assert widget.combo_filter.currentIndex() == 2
    assert len(widget.words_list) > 0
    assert " — " in widget.current_word["english"]  # V1 — V2 — V3 formati

    # Barcha so'zlarga qaytish (index 0)
    widget.combo_filter.setCurrentIndex(0)
    assert len(widget.words_list) >= 3


def test_speaking_widget_score_evaluation(temp_speaking_db):
    widget = SpeakingWidget()
    assert widget.session_practiced == 0

    # Simulyatsiya: 92% ball bilan muvaffaqiyatli tahlil
    widget._on_speech_finished({"status": "ok", "score": 92, "message": "Muvaffaqiyatli tanildi"})
    assert widget.session_practiced == 1
    assert 92 in widget.session_scores
    assert widget.lbl_score_badge.text() == "🎯 Aniqlik: 92%"
    assert "92%" in widget.lbl_stat_avg.text()

    # Simulyatsiya: 70% ball
    widget._on_speech_finished({"status": "ok", "score": 70, "message": "Yaxshi talaffuz"})
    assert widget.session_practiced == 2
    assert widget.lbl_score_badge.text() == "🎯 Aniqlik: 70%"
    assert "81%" in widget.lbl_stat_avg.text()  # (92 + 70) / 2 = 81


def test_speaking_widget_theme_application(temp_speaking_db):
    widget = SpeakingWidget()
    for theme in theme_manager.get_all_themes():
        widget.apply_theme(theme)
        assert widget.card_main.objectName() == "speaking_hero_card"
