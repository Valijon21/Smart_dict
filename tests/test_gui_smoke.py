"""
Vocab Master Pro — GUI Smoke Tests.
Verifies MainWindow lifecycle, page navigation, and crash resilience.
"""
import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core.database as _cdb


@pytest.fixture(scope="module")
def app():
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)
    return _app


@pytest.fixture
def temp_db(tmp_path):
    test_db = tmp_path / "test_vocab_smoke.db"
    orig_path = _cdb.DB_PATH
    _cdb.DB_PATH = test_db
    _cdb.init_db()

    # Namunaviy so'zlar qo'shamiz
    _cdb.add_word("apple", "olma")
    _cdb.add_word("book", "kitob")
    _cdb.add_word("courage", "jasorat")

    yield test_db
    _cdb.DB_PATH = orig_path


def test_main_window_creation(app, temp_db):
    from ui.main_window import MainWindow
    window = MainWindow()
    assert window is not None
    assert window.windowTitle().startswith("Vocab Master Pro")

    # Sahifalarni almashtirish testi
    window.switch_page("dictionary")
    assert window.current_page_key == "dictionary"

    window.switch_page("dashboard")
    assert window.current_page_key == "dashboard"

    # Tray activation xavfsizligi testi
    window._on_tray_activated()
    window._on_tray_activated(1)
    window._on_tray_activated("invalid_c_plus_plus_object")

    window.close()


def test_dictionary_widget_smoke(app, temp_db):
    from ui.views.dictionary_view import DictionaryWidget
    dw = DictionaryWidget()
    assert dw is not None
    dw.search_input.setText("app")
    dw.load_words()
    assert dw.table.rowCount() >= 1

    # Bo'sh qidiruv
    dw.search_input.setText("")
    dw.load_words()
    assert dw.table.rowCount() >= 3

    dw.close()
