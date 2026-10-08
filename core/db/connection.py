"""
Vocab Master — ma'lumotlar bazasi qatlami.
SQLite orqali so'zlar, progress va statistika saqlanadi.
Dublikatlarni oldini olish: english UNIQUE COLLATE NOCASE.
"""
import sys
import sqlite3
import datetime
import csv
import json
import re
import shutil
from pathlib import Path
from contextlib import contextmanager
try:
    from core import phonetics
except ImportError:
    import phonetics

try:
    from core.fsrs import FSRSv5, FSRSCard, Rating, CardState
except ImportError:
    try:
        from fsrs import FSRSv5, FSRSCard, Rating, CardState
    except ImportError:
        FSRSv5 = None
        FSRSCard = None
        Rating = None
        CardState = None

try:
    from utils.logger import get_logger, get_app_dir
    from utils import text_search_utils
except ImportError:
    from logger import get_logger, get_app_dir
    import text_search_utils

logger = get_logger("database")

# SQL ORDER BY whitelist — f-string injection xavfini bartaraf etadi.
# Yangi sort qiymati kerak bo'lsa, shu ro'yxatga qo'shing.
_ALLOWED_ORDER_BY: frozenset[str] = frozenset({
    "created_at DESC",
    "created_at ASC",
    "english ASC",
    "english DESC",
    "uzbek ASC",
    "uzbek DESC",
    "id ASC",
    "id DESC",
    "w.id ASC",
    "w.id DESC",
    "w.created_at DESC",
    "w.created_at ASC",
    "w.english ASC",
    "w.english DESC",
    "box_level ASC",
    "box_level DESC",
    "correct_count DESC",
    "wrong_count DESC",
    "status ASC",
    "status DESC",
})



def _safe_order_by(order_by: str, default: str = "created_at DESC") -> str:
    """Whitelist tekshirish: ruxsat etilmagan qiymat kelsa, default qaytariladi va warning yoziladi."""
    if order_by in _ALLOWED_ORDER_BY:
        return order_by
    logger.warning(
        "SQL injection himoyasi: ruxsatsiz order_by=%r rad etildi, default=%r ishlatiladi.",
        order_by, default,
    )
    return default


def _determine_db_path() -> Path:
    """
    Ma'lumotlar bazasini dasturning aynan yonida (portable) joylashtiradi.
    Agar avvalgi standart joyda (C:\\Users\\...\\VocabMaster\\vocab.db) baza bo'lsa,
    foydalanuvchi ma'lumotlari yo'qolmasligi uchun yangi joyga avtomatik ko'chirib o'tadi.
    """
    try:
        app_dir = get_app_dir()

        # 1. Agar data/vocab.db mavjud bo'lsa, undan foydalanamiz
        data_sub_db = app_dir / "data" / "vocab.db"
        if data_sub_db.exists():
            return data_sub_db

        local_db = app_dir / "vocab.db"
        if local_db.exists():
            return local_db

        # 2. Eski joylashuvdan migratsiya (C:\Users\<user>\VocabMaster\vocab.db)
        legacy_db = Path.home() / "VocabMaster" / "vocab.db"
        if legacy_db.exists() and legacy_db.stat().st_size > 0:
            try:
                local_db.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_db, local_db)
                logger.info(f"Mavjud baza eski joydan dastur yoniga muvaffaqiyatli ko'chirildi: {legacy_db} -> {local_db}")
                return local_db
            except Exception as err:
                logger.warning(f"Eski bazani ko'chirishda xatolik ({err}). Eski yo'ldan foydalaniladi: {legacy_db}")
                return legacy_db

        # 3. Yangi standart joylashuv — dasturning aynan yonida
        local_db.parent.mkdir(parents=True, exist_ok=True)
        # Yozish huquqini tekshirish
        test_file = local_db.parent / ".perm_check"
        test_file.touch()
        test_file.unlink()
        return local_db

    except (PermissionError, OSError) as e:
        fallback = Path.home() / "VocabMaster" / "vocab.db"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        logger.warning(f"Dastur papkasiga yozish huquqi mavjud emas ({e}). Baza User papkasida saqlanadi: {fallback}")
        return fallback


DB_PATH = _determine_db_path()


def get_db_path() -> Path:
    """Ma'lumotlar bazasi fayli yo'lini qaytaradi."""
    return DB_PATH


def get_db_dir() -> Path:
    """Ma'lumotlar bazasi joylashgan papkani qaytaradi."""
    return DB_PATH.parent


def _ensure_dir():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn():
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def init_db():
    logger.info(f"SQLite bazasi tekshirilmoqda (WAL mode): {DB_PATH}")
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT NOT NULL COLLATE NOCASE UNIQUE,
                uzbek TEXT NOT NULL,
                source TEXT DEFAULT 'manual',
                example TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'new'          -- new | learning | mastered
            );

            CREATE TABLE IF NOT EXISTS progress (
                word_id INTEGER PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                box_level INTEGER DEFAULT 0,       -- oddiy Leitner box: 0..5
                last_reviewed TEXT,
                next_review TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,             -- YYYY-MM-DD
                practiced INTEGER DEFAULT 0,
                correct INTEGER DEFAULT 0,
                wrong INTEGER DEFAULT 0,
                new_words_added INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                icon TEXT NOT NULL,
                category TEXT NOT NULL,
                unlocked_at TEXT,
                progress INTEGER DEFAULT 0,
                max_progress INTEGER DEFAULT 1
            );

            -- Noto'g'ri fe'llar (Irregular Verbs) jadvali
            CREATE TABLE IF NOT EXISTS irregular_verbs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                v1 TEXT NOT NULL COLLATE NOCASE,
                v2 TEXT NOT NULL,
                v3 TEXT NOT NULL,
                translation TEXT NOT NULL,
                learned INTEGER DEFAULT 0,
                favorite INTEGER DEFAULT 0,
                practice_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_practiced TEXT
            );

            -- Tezkor qidiruv va filtrlar uchun SQLite indekslari
            CREATE INDEX IF NOT EXISTS idx_words_status ON words(status);
            CREATE INDEX IF NOT EXISTS idx_words_created ON words(created_at);
            CREATE INDEX IF NOT EXISTS idx_progress_next_review ON progress(next_review);
            CREATE INDEX IF NOT EXISTS idx_progress_wrong ON progress(wrong_count);
            CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
            CREATE INDEX IF NOT EXISTS idx_iv_v1 ON irregular_verbs(v1);
            CREATE INDEX IF NOT EXISTS idx_iv_learned ON irregular_verbs(learned);
            CREATE INDEX IF NOT EXISTS idx_iv_favorite ON irregular_verbs(favorite);
            """
        )
        # Mavjud bazalar uchun xavfsiz migratsiyalar
        for col_table, col_name, col_type in [
            ("words", "example", "TEXT DEFAULT ''"),
            ("words", "phonetic", "TEXT DEFAULT ''"),
            ("words", "part_of_speech", "TEXT DEFAULT ''"),
            ("progress", "ease_factor", "REAL DEFAULT 2.5"),
            ("progress", "interval_days", "INTEGER DEFAULT 0"),
            ("progress", "repetitions", "INTEGER DEFAULT 0"),
            ("progress", "fsrs_stability", "REAL DEFAULT 0.0"),
            ("progress", "fsrs_difficulty", "REAL DEFAULT 5.0"),
            ("progress", "fsrs_reps", "INTEGER DEFAULT 0"),
            ("progress", "fsrs_lapses", "INTEGER DEFAULT 0"),
            ("progress", "fsrs_state", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE {col_table} ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_fsrs_stability ON progress(fsrs_stability)")
        except Exception:
            pass

        # Agar bazada eski SM-2 so'zlari bo'lsa, ularni FSRS v5 ga silliq o'tkazamiz
        from core.db.progress_repo import migrate_sm2_to_fsrs_if_needed
        migrate_sm2_to_fsrs_if_needed(conn)

        conn.executemany(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            [
                ("daily_goal", "15"),
                ("reminder_enabled", "true"),
                ("reminder_time", "20:00"),
                ("minimize_to_tray", "true"),
                ("tts_rate", "155"),
                ("tts_autoplay", "true"),
                ("sound_effects_enabled", "true"),
                ("user_xp", "0"),
                ("match_best_time", ""),
                ("floating_widget_interval", "15"),
                ("blitz_best_score", "0"),
                ("periodic_reminder_enabled", "true"),
                ("periodic_reminder_interval_min", "60"),
                ("audio_player_interval_sec", "4.0"),
            ],
        )
        # Agar ilgari match_best_time '0' bo'lib qolgan bo'lsa, tozalaymiz
        conn.execute("UPDATE settings SET value='' WHERE key='match_best_time' AND value='0'")

        # Noto'g'ri fe'llar jadvali bo'sh bo'lsa yoki kam bo'lsa, JSON'dan to'liq 115 ta fe'lni yuklash
        iv_count = conn.execute("SELECT COUNT(*) as cnt FROM irregular_verbs").fetchone()
        if not iv_count or iv_count["cnt"] < 50:
            if iv_count and iv_count["cnt"] > 0:
                conn.execute("DELETE FROM irregular_verbs")
            from core.db.irregular_verbs_repo import seed_irregular_verbs_from_json
            seed_irregular_verbs_from_json(conn)

        # Mavjud so'zlarga bo'sh bo'lgan IPA va POS qiymatlarini faqat birinchi startda to'ldirish (Tezkor yuklanish)
        bf_row = conn.execute("SELECT value FROM settings WHERE key='phonetics_backfilled_v1'").fetchone()
        if not bf_row or bf_row["value"] != "true":
            try:
                from core.db.progress_repo import backfill_phonetics
                backfill_phonetics(conn)
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('phonetics_backfilled_v1', 'true')")
            except Exception as bf_err:
                logger.warning(f"Fonetikani to'ldirishda ogohlantirish: {bf_err}")

