"""
core/database.py uchun pytest smoke testlar.

Maqsad:
  - Asosiy CRUD operatsiyalari ishlashini tekshirish.
  - SM-2 algoritmining asosiy mantiqini tekshirish.
  - SQL injection whitelist himoyasini tekshirish.
  - Zaxira (backup) funksiyasini tekshirish.

Ishga tushirish:
    pytest tests/test_database.py -v
"""
import sys
import sqlite3
from pathlib import Path

import pytest

# Loyiha ildiz papkasini Python yo'liga qo'shish
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Shim orqali import (core.database'ga yo'naltiriladi)
import database as db
from core.database import _safe_order_by, _ALLOWED_ORDER_BY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def temp_db(tmp_path_factory):
    """
    Har bir test moduli uchun alohida vaqtinchalik SQLite bazasi.
    Asosiy vocab.db'ga hech qanday ta'sir qilmaydi.
    """
    tmp = tmp_path_factory.mktemp("db")
    test_db = tmp / "test_vocab.db"

    # core.database.DB_PATH ni vaqtinchalik fayl bilan almashtirish
    original_path = db.DB_PATH
    import core.database as _cdb
    _cdb.DB_PATH = test_db
    _cdb.init_db()
    yield test_db
    # Qayta tiklash
    _cdb.DB_PATH = original_path


@pytest.fixture(autouse=True)
def clean_db(temp_db):
    """Har bir test oldidan words jadvali tozalanadi."""
    import core.database as _cdb
    original = _cdb.DB_PATH
    _cdb.DB_PATH = temp_db
    with _cdb.get_conn() as conn:
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM progress")
        conn.execute("DELETE FROM daily_stats")
    yield
    _cdb.DB_PATH = original


# ---------------------------------------------------------------------------
# 1. Ma'lumotlar bazasi — CRUD
# ---------------------------------------------------------------------------

class TestAddWord:
    """add_word() funksiyasi — asosiy so'z qo'shish."""

    def test_add_simple_word(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        word_id = db.add_word("apple", "olma")
        assert word_id is not None and word_id > 0

    def test_add_duplicate_returns_none(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("book", "kitob")
        result = db.add_word("book", "kitob")
        assert result is None, "Dublikat so'z None qaytarishi kerak"

    def test_add_word_with_example(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        wid = db.add_word("run", "yugurmoq", example="She runs every morning.")
        assert wid is not None
        row = db.get_word_by_english("run")
        assert row is not None
        assert row["example"] == "She runs every morning."

    def test_add_word_case_insensitive_unique(self, temp_db):
        """COLLATE NOCASE — katta/kichik harf farqi dublikat hisoblanishi kerak."""
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("Hello", "Salom")
        result = db.add_word("hello", "salom")
        assert result is None, "Katta harfli variant ham dublikat sifatida tanilishi kerak"


class TestGetWords:
    """get_all_words(), get_words(), word_count() — o'qish operatsiyalari."""

    def test_get_all_words_empty(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        rows = db.get_all_words()
        assert isinstance(rows, list)
        assert len(rows) == 0

    def test_get_all_words_after_insert(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("cat", "mushuk")
        db.add_word("dog", "it")
        rows = db.get_all_words()
        assert len(rows) == 2

    def test_get_words_limit(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        for i in range(10):
            db.add_word(f"word{i}", f"so'z{i}")
        rows = db.get_words(limit=5)
        assert len(rows) <= 5

    def test_word_count_returns_dict(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("tree", "daraxt")
        result = db.word_count()
        assert isinstance(result, dict)
        assert "total" in result
        assert result["total"] >= 1


class TestDeleteWord:
    """delete_word() — o'chirish operatsiyasi."""

    def test_delete_existing_word(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        wid = db.add_word("table", "stol")
        assert wid is not None
        deleted = db.delete_word(wid)
        assert deleted is True
        assert db.get_word_by_english("table") is None

    def test_delete_nonexistent_word_returns_false(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        result = db.delete_word(999999)
        assert result is False


class TestGetWordByEnglish:
    """get_word_by_english() — inglizcha so'z bo'yicha qidirish."""

    def test_found(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("mountain", "tog'")
        row = db.get_word_by_english("mountain")
        assert row is not None
        assert row["uzbek"] == "tog'"

    def test_not_found_returns_none(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        row = db.get_word_by_english("nonexistent_xyz_word")
        assert row is None

    def test_case_insensitive_lookup(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("River", "daryo")
        row = db.get_word_by_english("river")
        assert row is not None


class TestSearchWords:
    """search_words() — qidiruv funksiyasi."""

    def test_search_by_english(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("school", "maktab")
        db.add_word("teacher", "o'qituvchi")
        results = db.search_words("school")
        assert any(r["english"].lower() == "school" for r in results)

    def test_search_empty_query_returns_all(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("sun", "quyosh")
        db.add_word("moon", "oy")
        results = db.search_words("")
        assert len(results) >= 2

    def test_search_no_results(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        results = db.search_words("xxxxxxxxxnotarealword")
        assert results == []


# ---------------------------------------------------------------------------
# 2. SQL Injection Whitelist himoyasi
# ---------------------------------------------------------------------------

class TestSafeOrderBy:
    """_safe_order_by() — whitelist tekshirish."""

    def test_allowed_values_pass_through(self):
        for allowed in _ALLOWED_ORDER_BY:
            result = _safe_order_by(allowed, default="created_at DESC")
            assert result == allowed, f"'{allowed}' whitelist'da bo'lishi kerak, lekin qaytarilmadi"

    def test_malicious_input_rejected(self):
        malicious = "1; DROP TABLE words; --"
        result = _safe_order_by(malicious, default="created_at DESC")
        assert result == "created_at DESC", "Zararli input default bilan almashtirilishi kerak"

    def test_empty_string_rejected(self):
        result = _safe_order_by("", default="created_at DESC")
        assert result == "created_at DESC"

    def test_unknown_column_rejected(self):
        result = _safe_order_by("password ASC", default="english ASC")
        assert result == "english ASC"

    def test_whitelist_contains_expected_defaults(self):
        assert "created_at DESC" in _ALLOWED_ORDER_BY
        assert "english ASC" in _ALLOWED_ORDER_BY
        assert "w.id ASC" in _ALLOWED_ORDER_BY
        assert "w.id DESC" in _ALLOWED_ORDER_BY


# ---------------------------------------------------------------------------
# 3. SM-2 Algoritmi — record_sm2_review()
# ---------------------------------------------------------------------------

class TestSM2Review:
    """SM-2 spaced repetition algoritmi mantiqiy tekshiruvi."""

    def _add_and_get_id(self, temp_db, english="test_word", uzbek="sinov"):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        wid = db.add_word(english, uzbek)
        return wid

    def test_quality_5_increases_box(self, temp_db):
        """To'g'ri javob (quality=5) box_level'ni oshirishi kerak."""
        wid = self._add_and_get_id(temp_db, "perfect", "mukammal")
        result = db.record_sm2_review(wid, quality=5)
        assert isinstance(result, dict)
        assert result.get("box_level", 0) >= 1

    def test_quality_0_resets_box(self, temp_db):
        """Noto'g'ri javob (quality=0) box_level'ni 0 ga qaytarishi kerak."""
        wid = self._add_and_get_id(temp_db, "forget", "unutmoq")
        # Avval bir marta to'g'ri qil
        db.record_sm2_review(wid, quality=5)
        # Keyin xato
        result = db.record_sm2_review(wid, quality=0)
        assert result.get("box_level", -1) == 0, "Noto'g'ri javobdan so'ng box 0 bo'lishi kerak"

    def test_review_result_has_required_keys(self, temp_db):
        """record_sm2_review() natijasi zarur kalitlarni o'z ichiga olishi kerak."""
        wid = self._add_and_get_id(temp_db, "check", "tekshirmoq")
        result = db.record_sm2_review(wid, quality=4)
        for key in ("box_level", "next_review", "word_id"):
            assert key in result, f"Kalit '{key}' natijada yo'q. Mavjud kalitlar: {list(result.keys())}"


# ---------------------------------------------------------------------------
# 4. Backup funksiyasi
# ---------------------------------------------------------------------------

class TestBackup:
    """backup_database() — zaxira nusxa olish."""

    def test_backup_creates_file(self, temp_db, tmp_path):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        backup_path = tmp_path / "backup_test.db"
        result = db.backup_database(backup_path)
        assert result is True
        assert backup_path.exists()
        assert backup_path.stat().st_size > 0

    def test_backup_is_valid_sqlite(self, temp_db, tmp_path):
        """Zaxira fayli to'g'ri SQLite formatida bo'lishi kerak."""
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        backup_path = tmp_path / "backup_valid.db"
        db.backup_database(backup_path)
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "words" in tables
        assert "progress" in tables


# ---------------------------------------------------------------------------
# 5. get_words_with_progress()
# ---------------------------------------------------------------------------

class TestGetWordsWithProgress:
    """get_words_with_progress() — JOIN so'rovi va progress ma'lumotlari."""

    def test_returns_list(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        result = db.get_words_with_progress()
        assert isinstance(result, list)

    def test_includes_added_word(self, temp_db):
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("ocean", "okean")
        rows = db.get_words_with_progress()
        english_values = [r["english"] for r in rows]
        assert "ocean" in english_values

    def test_box_level_default_zero(self, temp_db):
        """Yangi qo'shilgan so'z box_level=0 bo'lishi kerak."""
        import core.database as _cdb
        _cdb.DB_PATH = temp_db
        db.add_word("wind", "shamol")
        rows = db.get_words_with_progress()
        wind = next((r for r in rows if r["english"] == "wind"), None)
        assert wind is not None
        assert wind["box_level"] == 0
