"""
tests/test_irregular_verbs.py
Noto'g'ri fe'llar (Irregular Verbs) bo'limi uchun to'liq unit va integratsion testlar:
- Baza CRUD va statistika amallari
- Xizmat qatlami (Quiz, Typing, Match, Scramble generatorlari)
- Audio TTS tozalash funksiyalari
- GUI widget smoke tekshiruvi
"""
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.database as db
from services.irregular_verbs_service import (
    IrregularVerbsService, clean_verb_for_tts
)


@pytest.fixture(scope="module")
def app():
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)
    return _app


@pytest.fixture(autouse=True)
def setup_test_db():
    """Har bir test uchun bazani initsializatsiya qilish."""
    db.init_db()


class TestIrregularVerbsDatabase:
    """Baza darajasidagi barcha funksiyalar testi."""

    def test_seed_and_get_irregular_verbs(self):
        verbs = db.get_irregular_verbs(limit=200)
        assert len(verbs) >= 100
        first = verbs[0]
        assert "v1" in first
        assert "v2" in first
        assert "v3" in first
        assert "translation" in first

    def test_search_irregular_verbs(self):
        # 'break' so'zini qidirish
        results = db.get_irregular_verbs(search="break")
        assert any(v["v1"].lower() == "break" for v in results)

        # O'zbekcha tarjima bo'yicha qidirish
        res_uz = db.get_irregular_verbs(search="sindirmoq")
        assert any(v["v1"].lower() == "break" for v in res_uz)

    def test_filter_modes(self):
        verbs = db.get_irregular_verbs(filter_mode="all")
        assert len(verbs) > 0

        # Toggle favorite and test favorites filter
        v_id = verbs[0]["id"]
        is_fav = db.toggle_irregular_verb_favorite(v_id)
        assert is_fav is True

        fav_verbs = db.get_irregular_verbs(filter_mode="favorites")
        assert any(v["id"] == v_id for v in fav_verbs)

        # Toggle back
        db.toggle_irregular_verb_favorite(v_id)

    def test_toggle_learned(self):
        verbs = db.get_irregular_verbs(limit=1)
        v_id = verbs[0]["id"]
        is_learned = db.toggle_irregular_verb_learned(v_id)
        assert is_learned is True

        learned_verbs = db.get_irregular_verbs(filter_mode="learned")
        assert any(v["id"] == v_id for v in learned_verbs)

        # Toggle back
        db.toggle_irregular_verb_learned(v_id)

    def test_crud_operations(self):
        # 1. Add
        new_id = db.add_irregular_verb("test_v1", "test_v2", "test_v3", "sinov_tarjima")
        assert new_id > 0

        # 2. Get by ID
        verb = db.get_irregular_verb_by_id(new_id)
        assert verb is not None
        assert verb["v1"] == "test_v1"
        assert verb["translation"] == "sinov_tarjima"

        # 3. Update
        updated = db.update_irregular_verb(new_id, "test_v1_up", "test_v2_up", "test_v3_up", "yangi_tarjima")
        assert updated is True
        verb_up = db.get_irregular_verb_by_id(new_id)
        assert verb_up["v1"] == "test_v1_up"
        assert verb_up["translation"] == "yangi_tarjima"

        # 4. Delete
        deleted = db.delete_irregular_verb(new_id)
        assert deleted is True
        assert db.get_irregular_verb_by_id(new_id) is None

    def test_practice_recording_and_stats(self):
        verbs = db.get_irregular_verbs(limit=1)
        v_id = verbs[0]["id"]

        db.record_irregular_verb_practice(v_id, is_correct=True)
        stats = db.get_irregular_verbs_stats()
        assert stats["total"] > 0
        assert stats["total_practiced"] >= 1
        assert stats["total_correct"] >= 1
        assert stats["accuracy"] > 0


class TestIrregularVerbsService:
    """Xizmat qatlami va o'yin/mashq generatorlari testi."""

    def test_clean_verb_for_tts(self):
        assert clean_verb_for_tts("be(am,is,are)") == "be"
        assert clean_verb_for_tts("was/were") == "was or were"
        assert clean_verb_for_tts("break") == "break"
        assert clean_verb_for_tts("") == ""

    def test_generate_quiz_question(self):
        q = IrregularVerbsService.generate_quiz_question()
        assert q is not None
        assert "target" in q
        assert "question_v1" in q
        assert "correct_answer" in q
        assert len(q["options"]) == 4
        assert q["correct_answer"] in q["options"]

    def test_check_typing_answer(self):
        # Aniq moslik
        v2_ok, v3_ok = IrregularVerbsService.check_typing_answer("spoke", "spoken", "spoke", "spoken")
        assert v2_ok is True
        assert v3_ok is True

        # Slashli variantlar (was/were)
        v2_ok, v3_ok = IrregularVerbsService.check_typing_answer("was", "been", "was/were", "been")
        assert v2_ok is True
        assert v3_ok is True

        # Katta/kichik harflar va bo'sh joylar
        v2_ok, v3_ok = IrregularVerbsService.check_typing_answer("  SPOKE ", " Spoken ", "spoke", "spoken")
        assert v2_ok is True
        assert v3_ok is True

        # Noto'g'ri javob
        v2_ok, v3_ok = IrregularVerbsService.check_typing_answer("speaked", "spokened", "spoke", "spoken")
        assert v2_ok is False
        assert v3_ok is False

    def test_generate_match_game(self):
        cards = IrregularVerbsService.generate_match_game(pair_count=6)
        assert len(cards) == 12
        pair_ids = [c["pair_id"] for c in cards]
        # Har bir pair_id dan 2 tadan bo'lishi kerak
        for pid in set(pair_ids):
            assert pair_ids.count(pid) == 2

    def test_generate_scramble_game(self):
        s = IrregularVerbsService.generate_scramble_game()
        assert s is not None
        assert "target_word" in s
        assert "letters" in s
        assert sorted(s["letters"]) == sorted(list(s["target_word"]))


class TestIrregularVerbsWidgetSmoke:
    """GUI vidjetining xatosiz ochilishi va sahifalar almashishi."""

    def test_widget_creation_and_tabs(self, app):
        from ui.views.irregular_verbs_view import IrregularVerbsWidget

        widget = IrregularVerbsWidget()
        assert widget.stack.count() == 6

        # Barcha 6 ta tabni ketma-ket almashtirib ko'rish
        for tab_idx in range(6):
            widget.switch_tab(tab_idx)
            assert widget.stack.currentIndex() == tab_idx

        # Jadval ma'lumotlari mavjudligi
        assert widget.table.rowCount() > 0

        widget.close()
