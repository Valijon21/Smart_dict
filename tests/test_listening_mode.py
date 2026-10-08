"""
Tests for Listening Mode (Eshitib yozish mashq rejimi).
Covers normalization, answer evaluation, and ListeningModeWidget UI behavior.
"""
import sys
from pathlib import Path
import pytest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.views.practice.listening_mode import (
    normalize_listening_text,
    check_listening_answer,
    ListeningModeWidget
)


@pytest.fixture(scope="module")
def app():
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)
    return _app


# ==========================================
# 1. Normalization & Logic Tests
# ==========================================

def test_normalize_listening_text():
    assert normalize_listening_text("") == ""
    assert normalize_listening_text(None) == ""
    assert normalize_listening_text("  Apple!  ") == "apple"
    assert normalize_listening_text("don't") == "don't"
    assert normalize_listening_text("Hello, World 123") == "helloworld123"


def test_check_listening_answer_exact():
    word = {"english": "courage", "uzbek": "jasorat"}
    assert check_listening_answer("courage", word) is True
    assert check_listening_answer(" COURAGE ", word) is True
    assert check_listening_answer("fear", word) is False


def test_check_listening_answer_multi_options():
    word_slash = {"english": "autumn / fall", "uzbek": "kuz"}
    assert check_listening_answer("autumn", word_slash) is True
    assert check_listening_answer("fall", word_slash) is True
    assert check_listening_answer("summer", word_slash) is False

    word_comma = {"english": "hi, hello", "uzbek": "salom"}
    assert check_listening_answer("hi", word_comma) is True
    assert check_listening_answer("hello", word_comma) is True
    assert check_listening_answer("bye", word_comma) is False


def test_check_listening_answer_empty():
    assert check_listening_answer("", {"english": "test"}) is False
    assert check_listening_answer("test", {}) is False
    assert check_listening_answer(None, {"english": "test"}) is False


# ==========================================
# 2. Widget UI & Signal Tests
# ==========================================

def test_listening_widget_initialization(app):
    widget = ListeningModeWidget()
    assert widget.play_btn is not None
    assert widget.slow_btn is not None
    assert widget.answer_input is not None
    assert widget.get_focus_widget() == widget.answer_input
    assert widget.answer_input.placeholderText() != ""


def test_listening_widget_set_word(app):
    widget = ListeningModeWidget()
    word = {"english": "butterfly", "uzbek": "kapalak"}

    with patch("services.tts_service.speak") as mock_speak:
        widget.set_word(word)
        assert widget.current_word == word
        # Text includes translation and character count (butterfly = 9 chars)
        assert "kapalak" in widget.hint_label.text()
        assert "9 ta harf" in widget.hint_label.text()
        assert widget.answer_input.isEnabled() is True
        assert widget.answer_input.text() == ""


def test_listening_widget_correct_submission(app):
    widget = ListeningModeWidget()
    word = {"english": "knowledge", "uzbek": "bilim"}
    widget.set_word(word)

    received_signals = []
    widget.answer_submitted.connect(lambda is_correct: received_signals.append(is_correct))

    widget.answer_input.setText("Knowledge")
    widget.check_answer()

    assert len(received_signals) == 1
    assert received_signals[0] is True
    assert widget.answer_input.isEnabled() is False
    assert "#10B981" in widget.answer_input.styleSheet()


def test_listening_widget_incorrect_submission(app):
    widget = ListeningModeWidget()
    word = {"english": "knowledge", "uzbek": "bilim"}
    widget.set_word(word)

    received_signals = []
    widget.answer_submitted.connect(lambda is_correct: received_signals.append(is_correct))

    widget.answer_input.setText("ignorance")
    widget.check_answer()

    assert len(received_signals) == 1
    assert received_signals[0] is False
    assert widget.answer_input.isEnabled() is False
    assert "#EF4444" in widget.answer_input.styleSheet()


def test_listening_widget_audio_trigger(app):
    widget = ListeningModeWidget()
    word = {"english": "pronounce", "uzbek": "talaffuz qilmoq"}
    widget.set_word(word)

    with patch("services.tts_service.speak") as mock_speak:
        widget.play_audio()
        mock_speak.assert_called_with("pronounce", slow=False)

        widget.play_slow_audio()
        mock_speak.assert_called_with("pronounce", slow=True)
