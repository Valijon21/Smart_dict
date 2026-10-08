"""
Tests for Clipboard Monitor & ClipboardPopupDialog.
Verifies security/privacy filters, text validation, and toast dialog lifecycle.
"""
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.clipboard_service import ClipboardMonitor
from ui.dialogs.clipboard_popup_dialog import ClipboardPopupDialog


@pytest.fixture(scope="module")
def app():
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)
    return _app


# ==========================================
# 1. Security & Filter Tests
# ==========================================

def test_clipboard_filters_privacy_guards(app):
    monitor = ClipboardMonitor()
    monitor.enabled = True

    # Test cases that must be rejected for privacy/security:
    rejected_samples = [
        "https://example.com/api",
        "user@gmail.com",
        "def my_func():",
        "class UserModel:",
        "Bearer eyJhbGciOi...",
        "sk-proj1234567890abcdefg",
        "ghp_ABC1234567890defghijk",
        "4111 2222 3333 4444",
        "+998901234567",
        "1234567",
        "a",  # too short (< 2 chars)
        "this is a sentence with far too many words for lookup",  # > 3 words
        "a" * 45,  # too long (> 40 chars)
    ]

    with patch.object(monitor, "_show_popup") as mock_show:
        with patch("PyQt6.QtWidgets.QApplication.clipboard") as mock_cb:
            cb_mock = MagicMock()
            mock_cb.return_value = cb_mock

            for sample in rejected_samples:
                cb_mock.text.return_value = sample
                monitor._process_clipboard()
                assert mock_show.call_count == 0, f"Failed for sample: {sample}"


def test_clipboard_allows_valid_words(app):
    monitor = ClipboardMonitor()
    monitor.enabled = True

    with patch.object(monitor, "_show_popup") as mock_show:
        with patch("PyQt6.QtWidgets.QApplication.clipboard") as mock_cb:
            cb_mock = MagicMock()
            mock_cb.return_value = cb_mock

            with patch("services.global_dict_service.get_word_full_details") as mock_details:
                mock_details.return_value = {
                    "english": "perseverance",
                    "uzbek_translations": ["matonat"],
                    "phonetic": "pɜːsɪˈvɪərəns",
                    "examples": ["His perseverance paid off."],
                    "star": "2",
                }
                cb_mock.text.return_value = "perseverance"
                monitor._process_clipboard()
                assert mock_show.call_count == 1
                args, _ = mock_show.call_args
                assert args[0]["english"] == "perseverance"


# ==========================================
# 2. Popup Dialog Tests
# ==========================================

def test_clipboard_popup_initialization(app):
    word_data = {
        "english": "brilliant",
        "uzbek": "porloq, ajoyib",
        "phonetic": "ˈbrɪljənt",
        "example": "A brilliant idea.",
        "star": "3"
    }
    dlg = ClipboardPopupDialog(word_data)
    assert dlg.english == "brilliant"
    assert dlg.uzbek == "porloq, ajoyib"
    assert dlg.auto_close_timer.isActive() is True
    assert dlg.is_pinned is False

    # Test Pin toggle stops timer
    dlg._toggle_pin()
    assert dlg.is_pinned is True
    assert dlg.auto_close_timer.isActive() is False

    # Test Unpin restarts timer
    dlg._toggle_pin()
    assert dlg.is_pinned is False
    assert dlg.auto_close_timer.isActive() is True

    dlg.close()
