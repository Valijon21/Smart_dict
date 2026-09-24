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
            seed_irregular_verbs_from_json(conn)

        # Mavjud so'zlarga bo'sh bo'lgan IPA va POS qiymatlarini faqat birinchi startda to'ldirish (Tezkor yuklanish)
        bf_row = conn.execute("SELECT value FROM settings WHERE key='phonetics_backfilled_v1'").fetchone()
        if not bf_row or bf_row["value"] != "true":
            try:
                backfill_phonetics(conn)
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('phonetics_backfilled_v1', 'true')")
            except Exception as bf_err:
                logger.warning(f"Fonetikani to'ldirishda ogohlantirish: {bf_err}")


def migrate_sm2_to_fsrs_if_needed(conn: sqlite3.Connection) -> int:
    """Mavjud SM-2 takrorlash parametrlarini FSRS v5 barqarorlik va qiyinlik ko'rsatkichlariga avtomatik o'tkazish."""
    if FSRSv5 is None:
        return 0
    try:
        rows = conn.execute(
            """
            SELECT word_id, ease_factor, interval_days, repetitions, wrong_count, last_reviewed
            FROM progress
            WHERE (fsrs_stability IS NULL OR fsrs_stability = 0.0)
              AND (repetitions > 0 OR interval_days > 0 OR (ease_factor IS NOT NULL AND ease_factor != 2.5))
            """
        ).fetchall()

        if not rows:
            return 0

        updates = []
        for r in rows:
            card = FSRSv5.from_sm2(
                ease_factor=r["ease_factor"] if r["ease_factor"] is not None else 2.5,
                interval_days=r["interval_days"] if r["interval_days"] is not None else 0,
                repetitions=r["repetitions"] if r["repetitions"] is not None else 0,
                wrong_count=r["wrong_count"] if r["wrong_count"] is not None else 0,
                last_reviewed_str=r["last_reviewed"],
            )
            updates.append((
                card.stability,
                card.difficulty,
                card.reps,
                card.lapses,
                int(card.state),
                r["word_id"],
            ))

        conn.executemany(
            """
            UPDATE progress SET
                fsrs_stability = ?,
                fsrs_difficulty = ?,
                fsrs_reps = ?,
                fsrs_lapses = ?,
                fsrs_state = ?
            WHERE word_id = ?
            """,
            updates,
        )
        logger.info(f"FSRS v5 migratsiyasi: {len(updates)} ta so'z SM-2 dan FSRS modeliga muvaffaqiyatli o'tkazildi.")
        return len(updates)
    except Exception as e:
        logger.warning(f"FSRS migratsiyasida xatolik: {e}")
        return 0


def backfill_phonetics(conn: sqlite3.Connection | None = None) -> int:
    """Mavjud bazadagi so'zlarga bo'sh bo'lgan fonetik va POS qiymatlarini avtomatik to'ldirish."""
    if conn is not None:
        return _do_backfill_phonetics(conn)
    with get_conn() as c:
        return _do_backfill_phonetics(c)


def _do_backfill_phonetics(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT id, english FROM words WHERE phonetic IS NULL OR phonetic = ''"
    ).fetchall()
    if not rows:
        return 0
    updates = []
    for r in rows:
        info = phonetics.get_word_info(r["english"])
        updates.append((info["phonetic"], info["part_of_speech"], r["id"]))
    conn.executemany(
        "UPDATE words SET phonetic = ?, part_of_speech = ? WHERE id = ?",
        updates,
    )
    updated = len(updates)
    if updated > 0:
        logger.info(f"{updated} ta so'zga IPA transkripsiya va so'z turkumlari muvaffaqiyatli kiritildi.")
    return updated


# ---------- So'zlar bilan ishlash ----------

def _invalidate_cache():
    try:
        from core import retention_analytics
        retention_analytics.invalidate_retention_cache()
    except Exception:
        try:
            import retention_analytics
            retention_analytics.invalidate_retention_cache()
        except Exception:
            pass


def normalize(word: str) -> str:
    return " ".join(word.strip().lower().split())


def add_word(english: str, uzbek: str, source: str = "manual", example: str = "") -> int | None:
    """Yangi so'z qo'shadi. Muvaffaqiyatli bo'lsa word_id, dublikat bo'lsa None qaytaradi."""
    english_n = normalize(english)
    uzbek_n = uzbek.strip()
    example_n = example.strip()
    if not english_n or not uzbek_n:
        return None

    info = phonetics.get_word_info(english_n)
    phonetic_val = info["phonetic"]
    pos_val = info["part_of_speech"]

    with get_conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO words (english, uzbek, source, example, phonetic, part_of_speech, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (english_n, uzbek_n, source, example_n, phonetic_val, pos_val, datetime.datetime.now().isoformat()),
            )
            word_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO progress (word_id, next_review, ease_factor, interval_days, repetitions,
                                      fsrs_stability, fsrs_difficulty, fsrs_reps, fsrs_lapses, fsrs_state)
                VALUES (?, ?, 2.5, 0, 0, 0.0, 5.0, 0, 0, 0)
                """,
                (word_id, datetime.date.today().isoformat()),
            )
            logger.info(f"Yangi so'z qo'shildi: ID={word_id}, '{english_n}' -> '{uzbek_n}' ({pos_val})")
            _invalidate_cache()
            return word_id
        except sqlite3.IntegrityError:
            # Agar mavjud so'zda example yoki fonetika bo'lmasa, to'ldirish
            try:
                conn.execute(
                    """
                    UPDATE words SET 
                        example = CASE WHEN example IS NULL OR example='' THEN ? ELSE example END,
                        phonetic = CASE WHEN phonetic IS NULL OR phonetic='' THEN ? ELSE phonetic END,
                        part_of_speech = CASE WHEN part_of_speech IS NULL OR part_of_speech='' THEN ? ELSE part_of_speech END
                    WHERE english = ?
                    """,
                    (example_n, phonetic_val, pos_val, english_n),
                )
            except Exception:
                pass
            logger.debug(f"So'z dublikat (qo'shilmadi): '{english_n}'")
            return None


def bulk_add_words(pairs: list[tuple], source: str = "import") -> dict:
    """(english, uzbek) yoki (english, uzbek, example) juftliklar ro'yxatini tezkor bitta tranzaksiyada qo'shadi.
    Bazada oldindan mavjud so'zlarni dublikat qilmaydi, lekin ularni bazadan ajratib olib mashq to'plamiga birlashtiradi.
    """
    added, duplicates, invalid = 0, 0, 0
    added_ids = []
    batch_word_ids = []
    existing_ids = []
    seen_in_batch = set()
    now_iso = datetime.datetime.now().isoformat()
    today_iso = datetime.date.today().isoformat()

    with get_conn() as conn:
        for item in pairs:
            if not item or len(item) < 2:
                invalid += 1
                continue
            eng = item[0]
            uz = item[1]
            ex = item[2] if len(item) >= 3 else ""

            key = normalize(str(eng or ""))
            uz_str = str(uz or "").strip()
            ex_str = str(ex or "").strip()

            if not key or not uz_str:
                invalid += 1
                continue
            if key in seen_in_batch:
                duplicates += 1
                continue
            seen_in_batch.add(key)

            info = phonetics.get_word_info(key)
            phonetic_val = info["phonetic"]
            pos_val = info["part_of_speech"]

            try:
                cur = conn.execute(
                    """
                    INSERT INTO words (english, uzbek, source, example, phonetic, part_of_speech, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key, uz_str, source, ex_str, phonetic_val, pos_val, now_iso),
                )
                w_id = cur.lastrowid
                conn.execute(
                    """
                    INSERT INTO progress (word_id, next_review, ease_factor, interval_days, repetitions,
                                          fsrs_stability, fsrs_difficulty, fsrs_reps, fsrs_lapses, fsrs_state)
                    VALUES (?, ?, 2.5, 0, 0, 0.0, 5.0, 0, 0, 0)
                    """,
                    (w_id, today_iso),
                )
                added += 1
                added_ids.append(w_id)
                batch_word_ids.append(w_id)
            except sqlite3.IntegrityError:
                # Bazada mavjud so'zni bazaga qayta qo'shmaymiz, lekin uning mavjud ID sini topamiz
                # va mashq qilish uchun sessiya to'plamiga birlashtiramiz!
                existing_row = conn.execute("SELECT id FROM words WHERE LOWER(english) = LOWER(?)", (key,)).fetchone()
                if existing_row:
                    ex_id = existing_row[0]
                    batch_word_ids.append(ex_id)
                    existing_ids.append(ex_id)

                if ex_str or phonetic_val:
                    try:
                        conn.execute(
                            """
                            UPDATE words SET 
                                example = CASE WHEN example IS NULL OR example='' THEN ? ELSE example END,
                                phonetic = CASE WHEN phonetic IS NULL OR phonetic='' THEN ? ELSE phonetic END,
                                part_of_speech = CASE WHEN part_of_speech IS NULL OR part_of_speech='' THEN ? ELSE part_of_speech END
                            WHERE english = ?
                            """,
                            (ex_str, phonetic_val, pos_val, key),
                        )
                    except Exception:
                        pass
                duplicates += 1

    if batch_word_ids:
        try:
            set_setting("last_import_word_ids", ",".join(str(i) for i in batch_word_ids))
            set_setting("last_import_time", now_iso)
        except Exception as e:
            logger.warning(f"Oxirgi import sozlamasini saqlashda ogohlantirish: {e}")

    if added:
        bump_daily_stat(new_words_added=added)
        _invalidate_cache()
    logger.info(
        f"Tezkor bulk import yakunlandi: {added} yangi qo'shildi, "
        f"{len(existing_ids)} ta mavjud so'z birlashtirildi (jami {len(batch_word_ids)} ta mashqqa tayyor), "
        f"{duplicates} dublikat, {invalid} yaroqsiz"
    )
    return {
        "added": added,
        "duplicates": duplicates,
        "invalid": invalid,
        "word_ids": added_ids,
        "all_batch_ids": batch_word_ids,
        "existing_ids": existing_ids,
    }


def bulk_import_pack(pack_id: str, words_list: list[dict]) -> dict:
    """Tayyor so'z paketini import qiladi. Har bir so'zda english, uzbek, example bo'ladi."""
    items = [
        (w.get("english", ""), w.get("uzbek", ""), w.get("example", ""))
        for w in words_list
    ]
    return bulk_add_words(items, source=f"pack:{pack_id}")


def get_imported_pack_counts() -> dict[str, int]:
    """Qaysi to'plamdan nechta so'z yuklanganini qaytaradi."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT source, COUNT(*) as cnt
            FROM words
            WHERE source LIKE 'pack:%'
            GROUP BY source
            """
        ).fetchall()
        result = {}
        for r in rows:
            p_id = r["source"].replace("pack:", "")
            result[p_id] = r["cnt"]
        return result


def get_words_by_ids(word_ids: list[int]) -> list[sqlite3.Row]:
    """Berilgan word_id lar bo'yicha so'zlarni qaytaradi."""
    if not word_ids:
        return []
    placeholders = ",".join("?" for _ in word_ids)
    with get_conn() as conn:
        return conn.execute(
            f"""
            SELECT w.*, p.box_level, p.next_review, p.correct_count, p.wrong_count
            FROM words w JOIN progress p ON p.word_id = w.id
            WHERE w.id IN ({placeholders})
            ORDER BY w.id ASC
            """,
            tuple(word_ids),
        ).fetchall()


def get_last_import_word_ids() -> list[int]:
    """Oxirgi import qilingan barcha so'zlar (yangi qo'shilgan + bazadan topilgan) ID larini qaytaradi."""
    raw = get_setting("last_import_word_ids", "")
    if not raw:
        return []
    ids = []
    for piece in raw.split(","):
        piece = piece.strip()
        if piece.isdigit():
            ids.append(int(piece))
    if not ids:
        return []
    # Haqiqatda bazada mavjudligini tasdiqlash
    placeholders = ",".join("?" for _ in ids)
    with get_conn() as conn:
        valid_rows = conn.execute(
            f"SELECT id FROM words WHERE id IN ({placeholders})",
            tuple(ids)
        ).fetchall()
        valid_set = {r[0] for r in valid_rows}
    return [i for i in ids if i in valid_set]


def get_last_imported_words(limit: int = 500) -> list[sqlite3.Row]:
    """Oxirgi import qilingan so'zlarning to'liq qatorlarini tartiblangan holda qaytaradi."""
    ids = get_last_import_word_ids()
    if not ids:
        return []
    target_ids = ids[:limit] if limit > 0 else ids
    placeholders = ",".join("?" for _ in target_ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT w.*, p.box_level, p.next_review, p.last_reviewed, p.correct_count, p.wrong_count
            FROM words w JOIN progress p ON p.word_id = w.id
            WHERE w.id IN ({placeholders})
            """,
            tuple(target_ids)
        ).fetchall()
        row_map = {r["id"]: r for r in rows}
        return [row_map[i] for i in target_ids if i in row_map]


def get_latest_added_words(limit: int = 20) -> list[sqlite3.Row]:
    """Oxirgi qo'shilgan so'zlar ro'yxatini qaytaradi."""
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT w.*, p.box_level, p.next_review, p.correct_count, p.wrong_count
            FROM words w JOIN progress p ON p.word_id = w.id
            ORDER BY w.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_total_word_count() -> int:
    """Bazadagi jami so'zlar sonini qaytaradi."""
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM words").fetchone()
        return row[0] if row else 0


def get_all_words(order_by: str = "created_at DESC") -> list[sqlite3.Row]:
    """Barcha so'zlarni qaytaradi. order_by whitelist orqali SQL injection'dan himoyalangan."""
    safe_order = _safe_order_by(order_by, default="created_at DESC")
    with get_conn() as conn:
        return conn.execute(f"SELECT * FROM words ORDER BY {safe_order}").fetchall()


def get_words(limit: int = 50, order_by: str = "created_at DESC") -> list[sqlite3.Row]:
    """Cheklangan miqdordagi so'zlarni olish. order_by whitelist orqali SQL injection'dan himoyalangan."""
    safe_order = _safe_order_by(order_by, default="created_at DESC")
    with get_conn() as conn:
        return conn.execute(f"SELECT * FROM words ORDER BY {safe_order} LIMIT ?", (limit,)).fetchall()


def get_word_by_english(english: str) -> sqlite3.Row | None:
    """Inglizcha so'z bo'yicha bazadan qidirish."""
    eng_n = normalize(english)
    if not eng_n:
        return None
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT w.*, p.box_level, p.next_review, p.correct_count, p.wrong_count
            FROM words w LEFT JOIN progress p ON p.word_id = w.id
            WHERE LOWER(w.english) = LOWER(?)
            LIMIT 1
            """,
            (eng_n,),
        ).fetchone()


def get_words_by_english_batch(english_words: list[str]) -> dict[str, sqlite3.Row]:
    """Bir nechta inglizcha so'zlar bo'yicha shaxsiy bazadan 1 ta so'rov orqali ommaviy qidirish (0.5ms).
    Qaytaradi: {lower_english: row}
    """
    if not english_words:
        return {}
    clean_words = list(dict.fromkeys(normalize(w) for w in english_words if normalize(w)))
    if not clean_words:
        return {}

    placeholders = ",".join("?" for _ in clean_words)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT w.*, p.box_level, p.next_review, p.correct_count, p.wrong_count
            FROM words w LEFT JOIN progress p ON p.word_id = w.id
            WHERE LOWER(w.english) IN ({placeholders})
            """,
            tuple(clean_words),
        ).fetchall()
        return {r["english"].lower(): r for r in rows}


def search_words(query: str = "", status_filter: str = "all", hard_only: bool = False, limit: int | None = None) -> list[sqlite3.Row]:
    """So'zlarni qidirish va filtrlash (Inglizcha ↔ O'zbekcha universal qidiruv)."""
    clauses = []
    where_params = []
    order_params = []
    order_sql = "ORDER BY w.created_at DESC, w.id DESC"

    clean_q = query.strip()
    if clean_q:
        sp = text_search_utils.get_search_patterns(clean_q)
        q_norm = sp["clean"]
        exact_vars = sp["exact_variants"]
        prefix_vars = sp["prefix_patterns"]

        sub_clauses = [
            "LOWER(w.english) = ?",
            "LOWER(w.english) LIKE ? || '%'",
            "LOWER(w.english) LIKE '%' || ? || '%'"
        ]
        where_params.extend([q_norm, q_norm, q_norm])

        for v in exact_vars:
            sub_clauses.append("LOWER(w.uzbek) = ?")
            where_params.append(v)
            sub_clauses.append("LOWER(w.uzbek) LIKE ? || '%'")
            where_params.append(v)
            sub_clauses.append("LOWER(w.uzbek) LIKE '%, ' || ? || '%'")
            where_params.append(v)
            sub_clauses.append("LOWER(w.uzbek) LIKE '% ' || ? || '%'")
            where_params.append(v)
            if len(v) >= 3:
                sub_clauses.append("LOWER(w.uzbek) LIKE '%' || ? || '%'")
                where_params.append(v)

        clauses.append(f"({' OR '.join(sub_clauses)})")

        # Ko'p bosqichli professional ranking:
        # 0: Aniq moslik (Exact English yoki Exact Uzbek)
        case_parts = ["WHEN LOWER(w.english) = ? THEN 0"]
        order_params.append(q_norm)
        for v in exact_vars:
            case_parts.append("WHEN LOWER(w.uzbek) = ? THEN 0")
            order_params.append(v)

        # 1: Tarjima bo'laklarida aniq moslik (masalan: "kitob, darslik" -> "kitob")
        for v in exact_vars:
            case_parts.append("WHEN LOWER(w.uzbek) LIKE ? || ', %' OR LOWER(w.uzbek) LIKE '%, ' || ? || ', %' OR LOWER(w.uzbek) LIKE '%, ' || ? THEN 1")
            order_params.extend([v, v, v])

        # 2: Boshlanish mosligi (Prefix)
        case_parts.append("WHEN LOWER(w.english) LIKE ? || '%' THEN 2")
        order_params.append(q_norm)
        for p in prefix_vars:
            case_parts.append("WHEN LOWER(w.uzbek) LIKE ? || '%' THEN 2")
            order_params.append(p)

        order_sql = f"""
            ORDER BY 
                CASE {" ".join(case_parts)} ELSE 3 END ASC,
                w.created_at DESC, 
                w.id DESC
        """

    if status_filter == "import":
        imp_ids = get_last_import_word_ids()
        if imp_ids:
            ph = ",".join("?" for _ in imp_ids)
            clauses.append(f"w.id IN ({ph})")
            where_params.extend(imp_ids)
        else:
            clauses.append("1 = 0")
    elif status_filter and status_filter != "all":
        clauses.append("w.status = ?")
        where_params.append(status_filter)

    if hard_only:
        clauses.append("(p.wrong_count > p.correct_count OR p.wrong_count >= 2)")

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    limit_sql = f" LIMIT {int(limit)}" if limit else ""
    sql = f"""
        SELECT w.*, p.box_level, p.next_review, p.last_reviewed, p.correct_count, p.wrong_count
        FROM words w
        JOIN progress p ON p.word_id = w.id
        {where_sql}
        {order_sql}
        {limit_sql}
    """
    all_params = where_params + order_params
    with get_conn() as conn:
        results = conn.execute(sql, all_params).fetchall()
        # Levenshtein fuzzy search fallback: agar standart SQL qidiruv natija bermasa va so'z uzunligi >= 4 bo'lsa
        if not results and clean_q and len(clean_q) >= 4:
            fb_clauses = []
            fb_params = []
            if status_filter and status_filter != "all":
                fb_clauses.append("w.status = ?")
                fb_params.append(status_filter)
            if hard_only:
                fb_clauses.append("(p.wrong_count > p.correct_count OR p.wrong_count >= 2)")

            # Tezkor uzunlik chegarasi (SQL-level pruning): 
            # Levenshtein masofasi <= 2 bo'lgan so'zlar uzunligi faqat [len(q)-2, len(q)+5] oralig'ida bo'ladi
            max_dist = 1 if len(clean_q) <= 4 else 2
            min_l = max(1, len(clean_q) - max_dist)
            max_l = len(clean_q) + max_dist + 5

            fb_clauses.append("(LENGTH(w.english) BETWEEN ? AND ? OR LENGTH(w.uzbek) BETWEEN ? AND ?)")
            fb_params.extend([min_l, max_l, min_l, max_l])

            fb_where = ("WHERE " + " AND ".join(fb_clauses)) if fb_clauses else ""
            candidate_sql = f"""
                SELECT w.*, p.box_level, p.next_review, p.last_reviewed, p.correct_count, p.wrong_count
                FROM words w
                LEFT JOIN progress p ON p.word_id = w.id
                {fb_where}
                ORDER BY w.id DESC
                LIMIT 250
            """
            candidates = conn.execute(candidate_sql, fb_params).fetchall()
            fuzzy_matches = []
            q_lower = clean_q.lower()

            for cand in candidates:
                eng_w = (cand["english"] or "").lower()
                uz_w = (cand["uzbek"] or "").lower()

                # Tezkor pruning: agar har ikkala so'z uzunligi bo'yicha masofadan uzoq bo'lsa, hisoblamaslik
                if abs(len(q_lower) - len(eng_w)) > max_dist and abs(len(q_lower) - len(uz_w)) > max_dist:
                    continue

                d_eng = text_search_utils.levenshtein_distance(q_lower, eng_w)
                d_uz = text_search_utils.levenshtein_distance(q_lower, uz_w)
                min_d = min(d_eng, d_uz)

                # Uzbekcha vergul bilan ajratilgan qismlar bo'yicha ham tekshiramiz
                if min_d > max_dist and ("," in uz_w or ";" in uz_w):
                    for tok in re.split(r"[,;/]+", uz_w):
                        tok_clean = tok.strip()
                        if tok_clean and abs(len(q_lower) - len(tok_clean)) <= max_dist:
                            min_d = min(min_d, text_search_utils.levenshtein_distance(q_lower, tok_clean))
                            if min_d <= max_dist:
                                break

                if min_d <= max_dist:
                    fuzzy_matches.append((min_d, cand))

            fuzzy_matches.sort(key=lambda item: item[0])
            results = [item[1] for item in fuzzy_matches]
            if limit:
                results = results[:limit]

        return results


def get_words_by_status(status: str = "learning") -> list[sqlite3.Row]:
    """Berilgan status bo'yicha so'zlarni qaytaradi (masalan: 'learning', 'mastered')."""
    return search_words(status_filter=status)


def update_word(
    word_id: int,
    english: str,
    uzbek: str,
    example: str = "",
    phonetic: str = None,
    part_of_speech: str = None,
) -> bool:
    """So'zni tahrirlash (english, uzbek, example, phonetic, part_of_speech). Muvaffaqiyatli bo'lsa True qaytaradi."""
    eng_n = normalize(english)
    uz_n = uzbek.strip()
    ex_n = example.strip()
    if not eng_n or not uz_n:
        return False

    if phonetic is None or part_of_speech is None:
        import phonetics
        info = phonetics.get_word_info(eng_n)
        if phonetic is None:
            phonetic = info["phonetic"]
        if part_of_speech is None:
            part_of_speech = info["part_of_speech"]

    with get_conn() as conn:
        try:
            conn.execute(
                """
                UPDATE words
                SET english = ?, uzbek = ?, example = ?, phonetic = ?, part_of_speech = ?
                WHERE id = ?
                """,
                (eng_n, uz_n, ex_n, phonetic, part_of_speech, word_id),
            )
            logger.info(f"So'z tahrirlandi: ID={word_id}, '{eng_n}' -> '{uz_n}'")
            return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"So'zni tahrirlashda xatolik (dublikat): ID={word_id}, '{eng_n}': {e}")
            return False


def delete_word(word_id: int) -> bool:
    """So'zni bazadan butunlay o'chirish (progress avtomatik o'chadi)."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
        success = cur.rowcount > 0
        if success:
            logger.info(f"So'z o'chirildi: ID={word_id}")
            _invalidate_cache()
        else:
            logger.warning(f"O'chirish uchun so'z topilmadi: ID={word_id}")
        return success


def get_random_distractors(exclude_word_id: int, target_lang: str = "uzbek", count: int = 3) -> list[str]:
    """Variantli test uchun boshqa so'zlardan chalg'ituvchi variantlar tanlaydi."""
    column = "uzbek" if target_lang == "uzbek" else "english"
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT {column}
            FROM words
            WHERE id != ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (exclude_word_id, count),
        ).fetchall()
        return [r[column].split(",")[0].strip() for r in rows]


def get_words_with_progress(order_by: str = "w.id ASC") -> list[sqlite3.Row]:
    """So'zlar va ularning progress ma'lumotlarini 1 ta tezkor JOIN so'rovi bilan qaytaradi (N+1 yo'q).

    order_by parametri whitelist orqali SQL injection'dan himoyalangan.
    """
    safe_order = _safe_order_by(order_by, default="w.id ASC")
    with get_conn() as conn:
        return conn.execute(
            f"""
            SELECT w.id, w.english, w.uzbek, w.status, w.example, w.created_at,
                   COALESCE(p.box_level, 0) as box_level,
                   COALESCE(p.correct_count, 0) as correct_count,
                   COALESCE(p.wrong_count, 0) as wrong_count
            FROM words w
            LEFT JOIN progress p ON p.word_id = w.id
            ORDER BY {safe_order}
            """
        ).fetchall()


def export_to_csv(filepath: str | Path) -> int:
    """Barcha so'zlarni CSV faylga eksport qiladi (Excel uchun UTF-8 BOM bilan, 1 ta tezkor JOIN so'rovi)."""
    rows = get_words_with_progress(order_by="w.id ASC")
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "English", "Uzbek", "Example", "Status", "BoxLevel", "Correct", "Wrong", "CreatedAt"])
        for r in rows:
            writer.writerow([
                r["id"], r["english"], r["uzbek"], r["example"] or "",
                r["status"], r["box_level"], r["correct_count"], r["wrong_count"], r["created_at"]
            ])
    return len(rows)


def export_to_json(filepath: str | Path) -> int:
    """Barcha so'zlarni JSON formatida eksport qiladi (1 ta tezkor JOIN so'rovi)."""
    rows = get_words_with_progress(order_by="w.id ASC")
    data = [
        {
            "id": r["id"],
            "english": r["english"],
            "uzbek": r["uzbek"],
            "example": r["example"] or "",
            "status": r["status"],
            "box_level": r["box_level"],
            "correct_count": r["correct_count"],
            "wrong_count": r["wrong_count"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(data)


def word_count() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) AS new_c,
                SUM(CASE WHEN status='learning' THEN 1 ELSE 0 END) AS learning_c,
                SUM(CASE WHEN status='mastered' THEN 1 ELSE 0 END) AS mastered_c
            FROM words
            """
        ).fetchone()
        return {
            "total": row["total"] or 0,
            "new": row["new_c"] or 0,
            "learning": row["learning_c"] or 0,
            "mastered": row["mastered_c"] or 0,
        }


def get_practice_batch(mode_status: str = None, limit: int = 15, word_ids: list[int] = None) -> list[sqlite3.Row]:
    """Mashq uchun so'zlar: agar word_ids berilsa, aynan o'sha so'zlar qaytariladi.
    Aks holda eng avval muddati o'tgan so'zlar (Leitner box) va kerak bo'lsa partiya to'ldiriladi.
    Agar bazadagi so'zlar soni limitdan kam bo'lsa, foydalanuvchi so'ragan limit to'liq bajarilishi uchun
    so'zlar takrorlanib to'liq limit miqdoriga yetkaziladi."""
    if word_ids:
        return get_words_by_ids(word_ids)
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        rows = list(
            conn.execute(
                """
                SELECT w.*, 
                       COALESCE(p.box_level, 0) as box_level, 
                       COALESCE(p.next_review, ?) as next_review, 
                       COALESCE(p.correct_count, 0) as correct_count, 
                       COALESCE(p.wrong_count, 0) as wrong_count
                FROM words w 
                LEFT JOIN progress p ON p.word_id = w.id
                WHERE p.next_review <= ? OR p.next_review IS NULL
                ORDER BY p.next_review ASC
                LIMIT ?
                """,
                (today, today, limit),
            ).fetchall()
        )
        if len(rows) < limit:
            exclude_ids = [r["id"] for r in rows]
            if exclude_ids:
                placeholders = ",".join("?" for _ in exclude_ids)
                extra = conn.execute(
                    f"""
                    SELECT w.*, 
                           COALESCE(p.box_level, 0) as box_level, 
                           COALESCE(p.next_review, ?) as next_review, 
                           COALESCE(p.correct_count, 0) as correct_count, 
                           COALESCE(p.wrong_count, 0) as wrong_count
                    FROM words w 
                    LEFT JOIN progress p ON p.word_id = w.id
                    WHERE w.id NOT IN ({placeholders})
                    ORDER BY RANDOM()
                    LIMIT ?
                    """,
                    (today, *exclude_ids, limit - len(rows)),
                ).fetchall()
            else:
                extra = conn.execute(
                    """
                    SELECT w.*, 
                           COALESCE(p.box_level, 0) as box_level, 
                           COALESCE(p.next_review, ?) as next_review, 
                           COALESCE(p.correct_count, 0) as correct_count, 
                           COALESCE(p.wrong_count, 0) as wrong_count
                    FROM words w 
                    LEFT JOIN progress p ON p.word_id = w.id
                    ORDER BY RANDOM()
                    LIMIT ?
                    """,
                    (today, limit),
                ).fetchall()
            rows.extend(extra)

        # Agar bazada so'zlar soni so'ralgan limitdan kam bo'lsa ham,
        # foydalanuvchi belgilagan kunlik reja mashqini to'liq bajarish uchun
        # so'zlarni (avvalo past box_level va ko'p xato bo'lganlarni) takrorlab partiyani to'ldiramiz:
        if rows and len(rows) < limit:
            pool = sorted(
                rows,
                key=lambda r: (
                    r["box_level"] if r["box_level"] is not None else 0,
                    -(r["wrong_count"] if r["wrong_count"] is not None else 0)
                )
            )
            idx = 0
            while len(rows) < limit:
                rows.append(pool[idx % len(pool)])
                idx += 1

        return rows


BOX_INTERVALS_DAYS = [0, 1, 2, 4, 7, 14]  # Leitner box -> keyingi ko'rish oralig'i


def _apply_progress_update(conn: sqlite3.Connection, word_id: int, box: int, is_correct: bool, next_review: str):
    """Progress va so'z holatini xavfsiz yangilash (DRY)."""
    status = "mastered" if box >= 4 else ("learning" if box >= 1 else "new")
    today = datetime.date.today().isoformat()
    conn.execute(
        """
        UPDATE progress SET
            correct_count = correct_count + ?,
            wrong_count = wrong_count + ?,
            box_level = ?,
            last_reviewed = ?,
            next_review = ?
        WHERE word_id = ?
        """,
        (
            1 if is_correct else 0,
            0 if is_correct else 1,
            box,
            today,
            next_review,
            word_id,
        ),
    )
    conn.execute("UPDATE words SET status=? WHERE id=?", (status, word_id))


def record_fsrs_review(word_id: int, rating: int, desired_retention: float = 0.90) -> dict:
    """
    FSRS v5 (Free Spaced Repetition Scheduler) algoritmi orqali so'zni takrorlash va baholash.
    rating:
      1: AGAIN  (Eslay olmadi / xato)
      2: HARD   (Qiyinchilik bilan esladi)
      3: GOOD   (Yaxshi, o'z vaqtida esladi)
      4: EASY   (Juda oson va tez esladi)
    """
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT p.ease_factor, p.interval_days, p.repetitions, p.box_level, 
                   p.correct_count, p.wrong_count, p.last_reviewed,
                   p.fsrs_stability, p.fsrs_difficulty, p.fsrs_reps, p.fsrs_lapses, p.fsrs_state
            FROM progress p WHERE p.word_id = ?
            """,
            (word_id,),
        ).fetchone()
        if not row:
            return {}

        ef = row["ease_factor"] if row["ease_factor"] is not None else 2.5
        interval = row["interval_days"] if row["interval_days"] is not None else 0
        repetitions = row["repetitions"] if row["repetitions"] is not None else 0
        box = row["box_level"] if row["box_level"] is not None else 0
        c_cnt = row["correct_count"] or 0
        w_cnt = row["wrong_count"] or 0
        last_rev = row["last_reviewed"]

        # Rating tekshirish (1..4)
        r_val = int(rating)
        if r_val < 1:
            r_val = 1
        elif r_val > 4:
            r_val = 4

        card_s = row["fsrs_stability"]
        card_d = row["fsrs_difficulty"]
        card_reps = row["fsrs_reps"] or 0
        card_lapses = row["fsrs_lapses"] or 0
        card_st = row["fsrs_state"] or 0

        now = datetime.datetime.now()
        now_iso = now.isoformat()

        if FSRSv5 is not None:
            if (card_s is None or card_s == 0.0) and (repetitions > 0 or interval > 0 or (card_reps == 0 and repetitions > 0)):
                card = FSRSv5.from_sm2(
                    ease_factor=ef,
                    interval_days=interval,
                    repetitions=repetitions,
                    wrong_count=w_cnt,
                    last_reviewed_str=last_rev,
                )
            else:
                last_dt = None
                if last_rev:
                    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                        try:
                            last_dt = datetime.datetime.strptime(last_rev.strip(), fmt)
                            break
                        except Exception:
                            pass
                card = FSRSCard(
                    stability=float(card_s or 0.0),
                    difficulty=float(card_d if card_d is not None else 5.0),
                    reps=int(card_reps),
                    lapses=int(card_lapses),
                    state=CardState(card_st) if card_st in (0, 1, 2, 3) else CardState.NEW,
                    last_review=last_dt,
                )

            scheduler = FSRSv5(desired_retention=desired_retention)
            new_card, next_interval = scheduler.review_card(card, Rating(r_val), review_time=now)
        else:
            next_interval = max(1, interval * 2) if r_val >= 3 else 1
            new_card = FSRSCard(
                stability=float(next_interval),
                difficulty=5.0,
                reps=card_reps + (1 if r_val >= 3 else 0),
                lapses=card_lapses + (0 if r_val >= 3 else 1),
                state=CardState.REVIEW if r_val >= 3 else CardState.LEARNING,
            )

        # SM-2 ko'rsatkichlarini ham sinxron saqlash (To'liq teskari muvofiqlik)
        is_correct = (r_val >= 2)
        if r_val == 1:  # AGAIN
            new_reps = 0
            new_box = max(0, box - 1)
            w_cnt += 1
            new_ef = max(1.3, round(ef - 0.2, 2))
        else:
            new_reps = repetitions + 1
            new_box = min(5, box + 1)
            c_cnt += 1
            q_equiv = 3 if r_val == 2 else (4 if r_val == 3 else 5)
            ef_prime = ef + (0.1 - (5 - q_equiv) * (0.08 + (5 - q_equiv) * 0.02))
            new_ef = max(1.3, round(ef_prime, 2))

        next_date = (datetime.date.today() + datetime.timedelta(days=next_interval)).isoformat()
        is_mastered = (new_card.stability >= 21.0 or new_card.reps >= 5 or new_box >= 5)

        conn.execute(
            """
            UPDATE progress SET
                fsrs_stability = ?,
                fsrs_difficulty = ?,
                fsrs_reps = ?,
                fsrs_lapses = ?,
                fsrs_state = ?,
                ease_factor = ?,
                interval_days = ?,
                repetitions = ?,
                box_level = ?,
                correct_count = ?,
                wrong_count = ?,
                last_reviewed = ?,
                next_review = ?
            WHERE word_id = ?
            """,
            (
                round(new_card.stability, 4),
                round(new_card.difficulty, 2),
                new_card.reps,
                new_card.lapses,
                int(new_card.state),
                new_ef,
                next_interval,
                new_reps,
                new_box,
                c_cnt,
                w_cnt,
                now_iso,
                next_date,
                word_id,
            ),
        )

        status = "mastered" if is_mastered else ("learning" if (new_card.reps > 0 or new_box > 0) else "new")
        conn.execute("UPDATE words SET status=? WHERE id=?", (status, word_id))

    bump_daily_stat(practiced=1, correct=1 if is_correct else 0, wrong=0 if is_correct else 1)
    _invalidate_cache()
    return {
        "word_id": word_id,
        "rating": r_val,
        "fsrs_stability": round(new_card.stability, 2),
        "fsrs_difficulty": round(new_card.difficulty, 2),
        "fsrs_reps": new_card.reps,
        "fsrs_lapses": new_card.lapses,
        "fsrs_state": int(new_card.state),
        "ease_factor": new_ef,
        "interval_days": next_interval,
        "repetitions": new_reps,
        "box_level": new_box,
        "next_review": next_date,
        "status": status,
    }


def record_sm2_review(word_id: int, quality: int) -> dict:
    """
    Anki SM-2 Spaced Repetition algoritmi (FSRS v5 ga silliq yo'naltirilgan):
    quality:
      5: Easy (Juda oson) -> FSRS Easy (4)
      4: Good (Yaxshi)    -> FSRS Good (3)
      3: Hard (Qiyin)     -> FSRS Hard (2)
      0..2: Again (Xato)  -> FSRS Again (1)
    """
    if quality >= 5:
        r = 4
    elif quality == 4:
        r = 3
    elif quality == 3:
        r = 2
    else:
        r = 1
    return record_fsrs_review(word_id, rating=r)


def record_answer(word_id: int, correct: bool):
    """FSRS v5 ga muvofiqlashtirilgan javob yozish."""
    return record_fsrs_review(word_id, rating=3 if correct else 1)


def record_flashcard_answer(word_id: int, quality: str):
    """
    Flashcard javobini FSRS v5 reytingi bo'yicha yozish:
    - 'again' / 'wrong': xato (Rating.AGAIN = 1)
    - 'hard': qiyin (Rating.HARD = 2)
    - 'good': yaxshi (Rating.GOOD = 3)
    - 'easy': oson (Rating.EASY = 4)
    """
    q_map = {"again": 1, "wrong": 1, "hard": 2, "good": 3, "easy": 4}
    r_val = q_map.get(str(quality).lower(), 3)
    return record_fsrs_review(word_id, rating=r_val)


def get_fsrs_card(word_id: int):
    """Berilgan word_id bo'yicha FSRSCard xotira modelini qaytarish."""
    if FSRSCard is None:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT fsrs_stability, fsrs_difficulty, fsrs_reps, fsrs_lapses, fsrs_state,
                   last_reviewed, next_review, ease_factor, interval_days, repetitions, wrong_count
            FROM progress WHERE word_id = ?
            """,
            (word_id,),
        ).fetchone()
        if not row:
            return None

        card_s = row["fsrs_stability"]
        if (card_s is None or card_s == 0.0) and (row["repetitions"] or 0) > 0:
            return FSRSv5.from_sm2(
                ease_factor=row["ease_factor"] or 2.5,
                interval_days=row["interval_days"] or 0,
                repetitions=row["repetitions"] or 0,
                wrong_count=row["wrong_count"] or 0,
                last_reviewed_str=row["last_reviewed"],
            )

        last_dt = None
        if row["last_reviewed"]:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    last_dt = datetime.datetime.strptime(row["last_reviewed"].strip(), fmt)
                    break
                except Exception:
                    pass

        due_dt = None
        if row["next_review"]:
            try:
                due_dt = datetime.datetime.strptime(row["next_review"].strip(), "%Y-%m-%d")
            except Exception:
                pass

        return FSRSCard(
            stability=float(card_s or 0.0),
            difficulty=float(row["fsrs_difficulty"] if row["fsrs_difficulty"] is not None else 5.0),
            reps=int(row["fsrs_reps"] or 0),
            lapses=int(row["fsrs_lapses"] or 0),
            state=CardState(row["fsrs_state"]) if row["fsrs_state"] in (0, 1, 2, 3) else CardState.NEW,
            last_review=last_dt,
            due=due_dt,
        )


def get_fsrs_stats() -> dict:
    """FSRS v5 bo'yicha global xotira tahlili va samaradorlik statistikasi."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT fsrs_stability, fsrs_difficulty, fsrs_reps, fsrs_lapses, fsrs_state, last_reviewed
            FROM progress
            WHERE fsrs_reps > 0 OR fsrs_stability > 0
            """
        ).fetchall()

        if not rows:
            return {
                "total_learned": 0,
                "avg_stability_days": 0.0,
                "avg_difficulty": 5.0,
                "avg_retention_pct": 100.0,
                "relearning_count": 0,
                "review_count": 0,
            }

        stabs = [r["fsrs_stability"] or 0.0 for r in rows if r["fsrs_stability"] and r["fsrs_stability"] > 0]
        diffs = [r["fsrs_difficulty"] or 5.0 for r in rows if r["fsrs_difficulty"]]
        relearn = sum(1 for r in rows if r["fsrs_state"] == 3)
        review = sum(1 for r in rows if r["fsrs_state"] == 2)

        scheduler = FSRSv5() if FSRSv5 else None
        now = datetime.datetime.now()
        retentions = []

        if scheduler:
            for r in rows:
                if r["fsrs_stability"] and r["fsrs_stability"] > 0 and r["last_reviewed"]:
                    last_dt = None
                    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                        try:
                            last_dt = datetime.datetime.strptime(r["last_reviewed"].strip(), fmt)
                            break
                        except Exception:
                            pass
                    if last_dt:
                        card = FSRSCard(stability=r["fsrs_stability"], last_review=last_dt, state=CardState.REVIEW)
                        ret = scheduler.get_retrievability(card, now)
                        retentions.append(ret)

        avg_s = sum(stabs) / len(stabs) if stabs else 0.0
        avg_d = sum(diffs) / len(diffs) if diffs else 5.0
        avg_r = (sum(retentions) / len(retentions) * 100.0) if retentions else 92.0

        return {
            "total_learned": len(rows),
            "avg_stability_days": round(avg_s, 1),
            "avg_difficulty": round(avg_d, 1),
            "avg_retention_pct": round(avg_r, 1),
            "relearning_count": relearn,
            "review_count": review,
        }


def get_due_words(limit: int = 50) -> list[sqlite3.Row]:
    """Anki SM-2 bo'yicha bugun takrorlash muddati kelgan so'zlar ro'yxati."""
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT w.*, p.box_level, p.next_review, p.correct_count, p.wrong_count, p.ease_factor, p.interval_days
            FROM words w
            JOIN progress p ON p.word_id = w.id
            WHERE p.next_review <= ? OR p.next_review IS NULL
            ORDER BY p.next_review ASC, p.box_level ASC
            LIMIT ?
            """,
            (today, limit),
        ).fetchall()


def get_due_count() -> int:
    """Bugun takrorlash muddati kelgan so'zlar soni."""
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM progress WHERE next_review <= ? OR next_review IS NULL",
            (today,),
        ).fetchone()
        return row["cnt"] if row else 0


def get_accuracy_stats() -> dict:
    """Umumiy aniqlik statistikasi (to'g'ri / xato nisbati foizda)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT SUM(correct_count) as total_c, SUM(wrong_count) as total_w FROM progress"
        ).fetchone()
        c = row["total_c"] or 0
        w = row["total_w"] or 0
        total = c + w
        pct = round((c / total * 100), 1) if total > 0 else 0
        return {"correct": c, "wrong": w, "total": total, "percent": pct}


def get_box_distribution() -> dict:
    """Leitner Box 0 dan Box 5 gacha so'zlar soni taqsimoti."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT box_level, COUNT(*) as cnt FROM progress GROUP BY box_level"
        ).fetchall()
        dist = {i: 0 for i in range(6)}
        for r in rows:
            b = r["box_level"]
            if b in dist:
                dist[b] = r["cnt"]
        return dist


def backup_database(destination_path: str | Path) -> bool:
    """SQLite ma'lumotlar bazasini xavfsiz zaxira nusxasini yaratadi."""
    try:
        Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
        with get_conn() as src_conn:
            dest_conn = sqlite3.connect(str(destination_path))
            src_conn.backup(dest_conn)
            dest_conn.close()
        logger.info(f"Baza zaxira nusxasi yaratildi: {destination_path}")
        return True
    except Exception as e:
        logger.error(f"Zaxira nusxa yaratishda xatolik: {e}", exc_info=True)
        return False


def restore_database(source_path: str | Path) -> bool:
    """SQLite ma'lumotlar bazasini zaxira faylidan xavfsiz tiklaydi."""
    try:
        source_p = Path(source_path)
        if not source_p.exists():
            return False
        src_conn = sqlite3.connect(str(source_p))
        with get_conn() as dest_conn:
            src_conn.backup(dest_conn)
        src_conn.close()
        logger.info(f"Baza zaxiradan muvaffaqiyatli tiklandi: {source_path}")
        return True
    except Exception as e:
        logger.error(f"Bazani tiklashda xatolik: {e}", exc_info=True)
        return False


# ---------- Sozlamalar (kunlik reja) ----------

def get_setting(key: str, default: str = None) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


def get_daily_goal() -> int:
    return int(get_setting("daily_goal", "15"))


def set_daily_goal(n: int):
    set_setting("daily_goal", max(1, int(n)))


def get_today_progress() -> dict:
    """Bugungi kunlik reja bo'yicha progress: qancha mashq qilingan / maqsad."""
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT practiced FROM daily_stats WHERE date=?", (today,)
        ).fetchone()
    practiced = row["practiced"] if row else 0
    goal = get_daily_goal()
    return {
        "practiced": practiced,
        "goal": goal,
        "percent": min(100, int(practiced / goal * 100)) if goal else 0,
        "done": practiced >= goal,
    }


# ---------- Statistika ----------

def bump_daily_stat(practiced=0, correct=0, wrong=0, new_words_added=0):
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO daily_stats (date, practiced, correct, wrong, new_words_added) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET "
            "practiced=practiced+excluded.practiced, "
            "correct=correct+excluded.correct, "
            "wrong=wrong+excluded.wrong, "
            "new_words_added=new_words_added+excluded.new_words_added",
            (today, practiced, correct, wrong, new_words_added),
        )


def get_last_n_days(n: int = 7) -> list[sqlite3.Row]:
    start = (datetime.date.today() - datetime.timedelta(days=n - 1)).isoformat()
    with get_conn() as conn:
        rows = {
            r["date"]: r
            for r in conn.execute(
                "SELECT * FROM daily_stats WHERE date >= ? ORDER BY date ASC", (start,)
            ).fetchall()
        }
    result = []
    for i in range(n):
        d = (datetime.date.today() - datetime.timedelta(days=n - 1 - i)).isoformat()
        r = rows.get(d)
        result.append(
            {
                "date": d,
                "practiced": r["practiced"] if r else 0,
                "correct": r["correct"] if r else 0,
                "wrong": r["wrong"] if r else 0,
            }
        )
    return result


def get_current_streak() -> int:
    """Streak endi kunlik REJAGA yetgan kunlar bo'yicha hisoblanadi (shunchaki
    1 ta mashq emas) — bu foydalanuvchini har kuni maqsadga yetishga undaydi."""
    goal = get_daily_goal()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date FROM daily_stats WHERE practiced >= ? ORDER BY date DESC", (goal,)
        ).fetchall()
    dates = {r["date"] for r in rows}
    streak = 0
    d = datetime.date.today()
    # bugun mashq qilmagan bo'lsa ham, kechagi kundan hisoblashga ruxsat beramiz
    if d.isoformat() not in dates:
        d -= datetime.timedelta(days=1)
    while d.isoformat() in dates:
        streak += 1
        d -= datetime.timedelta(days=1)
    return streak


# ---------- Zaif so'zlar karantini (Weak Words) ----------

def get_weak_words(limit: int = 50) -> list[sqlite3.Row]:
    """
    Foydalanuvchi ko'p xato qilgan so'zlar (kamida 2 marta xato va to'g'ri/xato nisbati < 60%).
    Xatosi ko'p bo'lganlar birinchi bo'lib chiqadi.
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT w.*, p.box_level, p.next_review, p.last_reviewed, p.correct_count, p.wrong_count
            FROM words w
            JOIN progress p ON p.word_id = w.id
            WHERE p.wrong_count >= 2 
              AND (p.correct_count = 0 OR (CAST(p.correct_count AS FLOAT) / (p.correct_count + p.wrong_count)) < 0.6)
            ORDER BY (p.wrong_count - p.correct_count) DESC, p.wrong_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_weak_words_count() -> int:
    """Karantindagi zaif so'zlar soni."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM words w
            JOIN progress p ON p.word_id = w.id
            WHERE p.wrong_count >= 2 
              AND (p.correct_count = 0 OR (CAST(p.correct_count AS FLOAT) / (p.correct_count + p.wrong_count)) < 0.6)
            """
        ).fetchone()
        return row["cnt"] if row else 0


# ---------- Gamifikatsiya: XP va Yutuqlar (Achievements) ----------

def get_xp() -> int:
    """Foydalanuvchining umumiy to'plagan XP ballari."""
    try:
        return int(get_setting("user_xp", "0"))
    except (ValueError, TypeError):
        return 0


def add_xp(points: int) -> int:
    """Foydalanuvchiga XP ball qo'shadi va yangilangan jami XP ni qaytaradi."""
    current = get_xp()
    new_total = max(0, current + points)
    set_setting("user_xp", str(new_total))
    return new_total


def init_default_achievements(achievements_list: list[dict]):
    """Baza bo'sh bo'lsa standart yutuqlar ro'yxatini kiritadi."""
    with get_conn() as conn:
        for a in achievements_list:
            conn.execute(
                """
                INSERT OR IGNORE INTO achievements (id, title, description, icon, category, max_progress)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    a["id"],
                    a["title"],
                    a["description"],
                    a.get("icon", "🏆"),
                    a.get("category", "general"),
                    a.get("max_progress", 1),
                ),
            )


def get_all_achievements() -> list[dict]:
    """Barcha yutuqlar va ularning statusini qaytaradi."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM achievements ORDER BY unlocked_at DESC, id ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def unlock_achievement(ach_id: str) -> bool:
    """Yutuqni ochadi. Agar avval ochilmagan bo'lsa True, aks holda False qaytaradi."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE achievements SET unlocked_at = ?, progress = max_progress WHERE id = ? AND unlocked_at IS NULL",
            (now_str, ach_id),
        )
        return cur.rowcount > 0


def update_achievement_progress(ach_id: str, progress: int) -> bool:
    """Yutuq progressini yangilaydi. Agar limitga yetsa avtomatik ochiladi va True qaytaradi."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM achievements WHERE id = ?", (ach_id,)).fetchone()
        if not row:
            return False
        max_p = row["max_progress"]
        new_p = min(progress, max_p)
        if new_p >= max_p and not row["unlocked_at"]:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            conn.execute(
                "UPDATE achievements SET progress = ?, unlocked_at = ? WHERE id = ?",
                (new_p, now_str, ach_id),
            )
            return True
        else:
            conn.execute(
                "UPDATE achievements SET progress = ? WHERE id = ?",
                (new_p, ach_id),
            )
            return False


def get_achievement(ach_id: str) -> dict | None:
    """Yagona yutuqni ID bo'yicha tezkor qaytaradi."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM achievements WHERE id = ?", (ach_id,)).fetchone()
        return dict(row) if row else None


# ---------- Faollik issiqlik xaritasi (Activity Heatmap) & Zaif so'zlar ----------

def get_daily_activity_heatmap(days: int = 365) -> dict[str, int]:
    """So'nggi `days` kun ichidagi kunlik mashq qilingan so'zlar sonini {YYYY-MM-DD: count} ko'rinishida qaytaradi."""
    start_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date, practiced FROM daily_stats WHERE date >= ? ORDER BY date ASC",
            (start_date,)
        ).fetchall()
        return {r["date"]: r["practiced"] for r in rows}


def get_weakest_words(limit: int = 10) -> list[dict]:
    """Eng ko'p xato qilingan va unutilish ehtimoli yuqori zaif so'zlarni qaytaradi."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT w.id, w.english, w.uzbek, w.phonetic, w.part_of_speech, w.example,
                   COALESCE(p.wrong_count, 0) as wrong_count,
                   COALESCE(p.correct_count, 0) as correct_count,
                   COALESCE(p.ease_factor, 2.5) as ease_factor
            FROM words w
            LEFT JOIN progress p ON w.id = p.word_id
            WHERE COALESCE(p.wrong_count, 0) > 0 OR w.status = 'learning'
            ORDER BY wrong_count DESC, ease_factor ASC, w.id ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_random_smart_word() -> dict | None:
    """Bildirishnoma yoki vidjet uchun o'rganilayotgan yoki interval muddati yetgan so'zni qaytaradi."""
    with get_conn() as conn:
        # 1. Avval interval muddati yetgan so'zlardan
        row = conn.execute(
            """
            SELECT w.* FROM words w
            JOIN progress p ON w.id = p.word_id
            WHERE p.next_review <= DATE('now')
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
        if row:
            return dict(row)

        # 2. Keyin o'rganilayotgan (learning) so'zlardan
        row = conn.execute(
            "SELECT * FROM words WHERE status = 'learning' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        if row:
            return dict(row)

        # 3. Nihoyat, ixtiyoriy so'z
        row = conn.execute("SELECT * FROM words ORDER BY RANDOM() LIMIT 1").fetchone()
        return dict(row) if row else None


def record_blitz_score(score: int, correct: int, wrong: int) -> dict:
    """Blitz marafoni natijasini qayd etadi, agar yangi rekord bo'lsa yangilaydi."""
    prev_best = int(get_setting("blitz_best_score", "0") or "0")
    is_new_best = score > prev_best
    if is_new_best:
        set_setting("blitz_best_score", str(score))

    # Daily stats yangilash
    today = datetime.date.today().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO daily_stats (date, practiced, correct, wrong)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                practiced = practiced + ?,
                correct = correct + ?,
                wrong = wrong + ?
            """,
            (today, correct + wrong, correct, wrong, correct + wrong, correct, wrong),
        )

    return {
        "score": score,
        "is_new_best": is_new_best,
        "best_score": max(score, prev_best),
        "correct": correct,
        "wrong": wrong,
    }


# ==============================================================================
# XAVFSIZ MAHALLIY ZAXIRA TIZIMI (LOCAL ROLLING DATA VAULT)
# Windows formatlanganda yoki nosozliklarda so'zlar 100% saqlanib qolishi uchun
# ==============================================================================

BACKUP_DIR = DB_PATH.parent / "backups"


def get_backup_dir() -> Path:
    """Zaxiralar papkasini qaytaradi va mavjud bo'lmasa yaratadi."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def backup_database(target_path: str = None) -> bool:
    """
    Ma'lumotlar bazasini xavfsiz SQLite backup API orqali zaxiralaydi.
    WAL rejimini tozalab, bazaning yaxlit nusxasini yaratadi.
    """
    try:
        if target_path is None:
            today_str = datetime.date.today().isoformat()
            target_path = get_backup_dir() / f"vocab_backup_{today_str}.db"
        else:
            target_path = Path(target_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)

        with get_conn() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dest_conn = sqlite3.connect(str(target_path))
            try:
                conn.backup(dest_conn)
            finally:
                dest_conn.close()

        logger.info(f"Ma'lumotlar bazasi zaxirasi saqlandi: {target_path}")
        return True
    except Exception as e:
        logger.error(f"Baza zaxirasini olishda xatolik: {e}", exc_info=True)
        return False


def restore_database(source_path: str) -> bool:
    """
    Zaxira nusxasidan bazani xavfsiz qayta tiklaydi.
    """
    try:
        src = Path(source_path)
        if not src.exists() or src.stat().st_size == 0:
            logger.error(f"Tiklash uchun fayl topilmadi yoki bo'sh: {source_path}")
            return False

        # Fayl butunligini tekshirish
        test_conn = sqlite3.connect(str(src))
        try:
            cur = test_conn.cursor()
            cur.execute("PRAGMA integrity_check")
            res = cur.fetchone()
            if not res or res[0] != "ok":
                logger.error(f"Zaxira fayli shikastlangan (integrity check failed): {res}")
                return False
        finally:
            test_conn.close()

        # Favqulodda xavfsizlik nusxasi
        emergency_bak = get_backup_dir() / "pre_restore_snapshot.db"
        try:
            if DB_PATH.exists():
                shutil.copy2(DB_PATH, emergency_bak)
        except Exception:
            pass

        # Eskirgan WAL/SHM fayllarini tozalash
        for ext in (".db-wal", ".db-shm"):
            f = DB_PATH.with_suffix(ext)
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

        # Faylni nusxalash
        shutil.copy2(src, DB_PATH)
        logger.info(f"Baza zaxiradan to'liq tiklandi: {src} -> {DB_PATH}")
        return True
    except Exception as e:
        logger.error(f"Bazani zaxiradan tiklashda xatolik: {e}", exc_info=True)
        return False


def auto_backup_daily(keep_days: int = 14) -> str:
    """
    Dastur ishga tushganda avtomatik kunlik zaxira yaratadi.
    Eskirgan zaxiralarni avtomatik tozalab, disk hajmini tejaydi.
    """
    try:
        b_dir = get_backup_dir()
        today_str = datetime.date.today().isoformat()
        today_file = b_dir / f"vocab_backup_{today_str}.db"

        # Zaxira olish
        backup_database(str(today_file))

        # 14 kundan ortiq zaxiralarni tozalash
        all_backups = sorted(b_dir.glob("vocab_backup_*.db"), key=lambda p: p.stat().st_mtime)
        if len(all_backups) > keep_days:
            for old_f in all_backups[:-keep_days]:
                try:
                    old_f.unlink()
                    logger.info(f"Eski zaxira fayli o'chirildi: {old_f.name}")
                except Exception:
                    pass

        return str(today_file)
    except Exception as e:
        logger.warning(f"Avtomatik kunlik zaxira olishda xatolik: {e}")
        return ""


def list_local_backups() -> list[dict]:
    """Mavjud mahalliy zaxiralar ro'yxatini qaytaradi."""
    result = []
    try:
        b_dir = get_backup_dir()
        for f in sorted(b_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
            size_kb = round(f.stat().st_size / 1024, 1)
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            result.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size_kb": size_kb,
                "modified": mtime,
            })
    except Exception as e:
        logger.error(f"Zaxiralar ro'yxatini olishda xatolik: {e}")
    return result


# =====================================================================
# NOTO'G'RI FE'LLAR (IRREGULAR VERBS) MODULI VA MA'LUMOTLAR BAZASI
# =====================================================================

def seed_irregular_verbs_from_json(conn=None) -> int:
    """assets/irregular_verbs.json faylidan noto'g'ri fe'llarni bazaga yuklash."""
    import json
    if hasattr(sys, "_MEIPASS"):
        json_path = Path(sys._MEIPASS) / "assets" / "irregular_verbs.json"
    else:
        json_path = Path(__file__).resolve().parent.parent / "assets" / "irregular_verbs.json"

    items = []
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8-sig") as f:
                items = json.load(f)
        except Exception as e:
            logger.error(f"irregular_verbs.json o'qishda xatolik: {e}")

    if not items:
        # Fallback zaxira ro'yxati (agar JSON fayl topilmasa)
        items = [
            {"v1": "be", "v2": "was/were", "v3": "been", "translation": "bo'lmoq"},
            {"v1": "beat", "v2": "beat", "v3": "beaten", "translation": "urmoq"},
            {"v1": "become", "v2": "became", "v3": "become", "translation": "bo'lmoq"},
            {"v1": "begin", "v2": "began", "v3": "begun", "translation": "boshlamoq"},
            {"v1": "break", "v2": "broke", "v3": "broken", "translation": "sindirmoq"},
            {"v1": "bring", "v2": "brought", "v3": "brought", "translation": "keltirmoq"},
            {"v1": "build", "v2": "built", "v3": "built", "translation": "qurmoq"},
            {"v1": "buy", "v2": "bought", "v3": "bought", "translation": "sotib olmoq"},
            {"v1": "catch", "v2": "caught", "v3": "caught", "translation": "ushlamoq"},
            {"v1": "choose", "v2": "chose", "v3": "chosen", "translation": "tanlamoq"},
            {"v1": "come", "v2": "came", "v3": "come", "translation": "kelmoq"},
            {"v1": "do", "v2": "did", "v3": "done", "translation": "qilmoq"},
            {"v1": "drink", "v2": "drank", "v3": "drunk", "translation": "ichmoq"},
            {"v1": "drive", "v2": "drove", "v3": "driven", "translation": "haydamoq"},
            {"v1": "eat", "v2": "ate", "v3": "eaten", "translation": "yemoq"},
            {"v1": "find", "v2": "found", "v3": "found", "translation": "topmoq"},
            {"v1": "give", "v2": "gave", "v3": "given", "translation": "bermoq"},
            {"v1": "go", "v2": "went", "v3": "gone", "translation": "bormoq"},
            {"v1": "have", "v2": "had", "v3": "had", "translation": "ega bo'lmoq"},
            {"v1": "make", "v2": "made", "v3": "made", "translation": "yasamoq"},
            {"v1": "see", "v2": "saw", "v3": "seen", "translation": "ko'rmoq"},
            {"v1": "take", "v2": "took", "v3": "taken", "translation": "olmoq"},
            {"v1": "write", "v2": "wrote", "v3": "written", "translation": "yozmoq"},
        ]

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    insert_data = [
        (item["v1"].strip(), item["v2"].strip(), item["v3"].strip(), item.get("translation", "").strip(), now_str)
        for item in items
        if item.get("v1")
    ]

    query = """
        INSERT INTO irregular_verbs (v1, v2, v3, translation, created_at)
        VALUES (?, ?, ?, ?, ?)
    """

    if conn is not None:
        conn.executemany(query, insert_data)
        count = len(insert_data)
    else:
        with get_conn() as c:
            c.executemany(query, insert_data)
            count = len(insert_data)

    logger.info(f"Noto'g'ri fe'llar bazasiga {count} ta fe'l muvaffaqiyatli yuklandi.")
    return count


def get_irregular_verbs(search: str = "", filter_mode: str = "all", limit: int = 500, offset: int = 0) -> list[dict]:
    """Noto'g'ri fe'llar ro'yxatini filtrlash va qidirish bilan olish."""
    query = "SELECT * FROM irregular_verbs WHERE 1=1"
    params = []

    if filter_mode == "learned":
        query += " AND learned = 1"
    elif filter_mode == "unlearned":
        query += " AND learned = 0"
    elif filter_mode == "favorites":
        query += " AND favorite = 1"

    if search:
        s = f"%{search.strip()}%"
        query += " AND (v1 LIKE ? OR v2 LIKE ? OR v3 LIKE ? OR translation LIKE ?)"
        params.extend([s, s, s, s])

    query += " ORDER BY v1 ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_all_irregular_verbs_for_practice(filter_mode: str = "all") -> list[dict]:
    """Mashq va o'yinlar uchun barcha kerakli fe'llarni olish."""
    query = "SELECT * FROM irregular_verbs WHERE 1=1"
    params = []
    if filter_mode == "unlearned":
        query += " AND learned = 0"
    elif filter_mode == "favorites":
        query += " AND favorite = 1"
    query += " ORDER BY RANDOM()"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_irregular_verb_by_id(verb_id: int) -> dict | None:
    """ID bo'yicha bitta fe'lni olish."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM irregular_verbs WHERE id = ?", (verb_id,)).fetchone()
        return dict(row) if row else None


def add_irregular_verb(v1: str, v2: str, v3: str, translation: str) -> int:
    """Yangi noto'g'ri fe'l qo'shish."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO irregular_verbs (v1, v2, v3, translation, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (v1.strip(), v2.strip(), v3.strip(), translation.strip(), now_str),
        )
        return cur.lastrowid


def update_irregular_verb(verb_id: int, v1: str, v2: str, v3: str, translation: str) -> bool:
    """Mavjud noto'g'ri fe'lni tahrirlash."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE irregular_verbs
            SET v1 = ?, v2 = ?, v3 = ?, translation = ?
            WHERE id = ?
            """,
            (v1.strip(), v2.strip(), v3.strip(), translation.strip(), verb_id),
        )
        return cur.rowcount > 0


def delete_irregular_verb(verb_id: int) -> bool:
    """Noto'g'ri fe'lni bazadan o'chirish."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM irregular_verbs WHERE id = ?", (verb_id,))
        return cur.rowcount > 0


def toggle_irregular_verb_favorite(verb_id: int) -> bool:
    """Fe'lning sevimli (yulduzcha) holatini almashtirish."""
    with get_conn() as conn:
        conn.execute("UPDATE irregular_verbs SET favorite = 1 - favorite WHERE id = ?", (verb_id,))
        row = conn.execute("SELECT favorite FROM irregular_verbs WHERE id = ?", (verb_id,)).fetchone()
        return bool(row["favorite"]) if row else False


def toggle_irregular_verb_learned(verb_id: int) -> bool:
    """Fe'lning o'rganilgan holatini almashtirish."""
    with get_conn() as conn:
        conn.execute("UPDATE irregular_verbs SET learned = 1 - learned WHERE id = ?", (verb_id,))
        row = conn.execute("SELECT learned FROM irregular_verbs WHERE id = ?", (verb_id,)).fetchone()
        return bool(row["learned"]) if row else False


def record_irregular_verb_practice(verb_id: int, is_correct: bool):
    """Mashq natijasini qayd qilish."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        if is_correct:
            conn.execute(
                """
                UPDATE irregular_verbs
                SET practice_count = practice_count + 1,
                    correct_count = correct_count + 1,
                    last_practiced = ?
                WHERE id = ?
                """,
                (now_str, verb_id),
            )
        else:
            conn.execute(
                """
                UPDATE irregular_verbs
                SET practice_count = practice_count + 1,
                    last_practiced = ?
                WHERE id = ?
                """,
                (now_str, verb_id),
            )


def get_irregular_verbs_stats() -> dict:
    """Noto'g'ri fe'llar bo'yicha umumiy statistika."""
    with get_conn() as conn:
        total_row = conn.execute("SELECT COUNT(*) as c FROM irregular_verbs").fetchone()
        total = total_row["c"] if total_row else 0
        learned_row = conn.execute("SELECT COUNT(*) as c FROM irregular_verbs WHERE learned = 1").fetchone()
        learned = learned_row["c"] if learned_row else 0
        fav_row = conn.execute("SELECT COUNT(*) as c FROM irregular_verbs WHERE favorite = 1").fetchone()
        favorites = fav_row["c"] if fav_row else 0

        stats_row = conn.execute(
            """
            SELECT SUM(practice_count) as total_practiced, SUM(correct_count) as total_correct
            FROM irregular_verbs
            """
        ).fetchone()

        total_practiced = (stats_row["total_practiced"] if stats_row and stats_row["total_practiced"] else 0)
        total_correct = (stats_row["total_correct"] if stats_row and stats_row["total_correct"] else 0)
        accuracy = round((total_correct / total_practiced) * 100, 1) if total_practiced > 0 else 0.0

        return {
            "total": total,
            "learned": learned,
            "unlearned": max(0, total - learned),
            "favorites": favorites,
            "total_practiced": total_practiced,
            "total_correct": total_correct,
            "accuracy": accuracy,
        }




