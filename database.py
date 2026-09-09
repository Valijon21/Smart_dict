"""
Vocab Master — ma'lumotlar bazasi qatlami.
SQLite orqali so'zlar, progress va statistika saqlanadi.
Dublikatlarni oldini olish: english UNIQUE COLLATE NOCASE.
"""
import sqlite3
import datetime
import csv
import json
import shutil
from pathlib import Path
from contextlib import contextmanager
import phonetics
from logger import get_logger, get_app_dir

logger = get_logger("database")


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
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        yield conn
        conn.commit()
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

            -- Tezkor qidiruv va filtrlar uchun SQLite indekslari
            CREATE INDEX IF NOT EXISTS idx_words_status ON words(status);
            CREATE INDEX IF NOT EXISTS idx_words_created ON words(created_at);
            CREATE INDEX IF NOT EXISTS idx_progress_next_review ON progress(next_review);
            CREATE INDEX IF NOT EXISTS idx_progress_wrong ON progress(wrong_count);
            CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
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
        ]:
            try:
                conn.execute(f"ALTER TABLE {col_table} ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

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

    # Mavjud so'zlarga bo'sh bo'lgan IPA va POS qiymatlarini avtomatik to'ldirish
    backfill_phonetics()


def backfill_phonetics() -> int:
    """Mavjud bazadagi so'zlarga bo'sh bo'lgan fonetik va POS qiymatlarini avtomatik to'ldirish."""
    updated = 0
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, english FROM words WHERE phonetic IS NULL OR phonetic = ''"
        ).fetchall()
        for r in rows:
            info = phonetics.get_word_info(r["english"])
            conn.execute(
                "UPDATE words SET phonetic = ?, part_of_speech = ? WHERE id = ?",
                (info["phonetic"], info["part_of_speech"], r["id"]),
            )
            updated += 1
    if updated > 0:
        logger.info(f"{updated} ta so'zga IPA transkripsiya va so'z turkumlari muvaffaqiyatli kiritildi.")
    return updated


# ---------- So'zlar bilan ishlash ----------

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
                INSERT INTO progress (word_id, next_review, ease_factor, interval_days, repetitions)
                VALUES (?, ?, 2.5, 0, 0)
                """,
                (word_id, datetime.date.today().isoformat()),
            )
            logger.info(f"Yangi so'z qo'shildi: ID={word_id}, '{english_n}' -> '{uzbek_n}' ({pos_val})")
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
    """(english, uzbek) yoki (english, uzbek, example) juftliklar ro'yxatini tezkor bitta tranzaksiyada qo'shadi."""
    added, duplicates, invalid = 0, 0, 0
    added_ids = []
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
                    INSERT INTO progress (word_id, next_review, ease_factor, interval_days, repetitions)
                    VALUES (?, ?, 2.5, 0, 0)
                    """,
                    (w_id, today_iso),
                )
                added += 1
                added_ids.append(w_id)
            except sqlite3.IntegrityError:
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

    if added:
        bump_daily_stat(new_words_added=added)
    logger.info(f"Tezkor bulk import yakunlandi: {added} qo'shildi, {duplicates} dublikat, {invalid} yaroqsiz")
    return {"added": added, "duplicates": duplicates, "invalid": invalid, "word_ids": added_ids}


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


def get_all_words(order_by: str = "created_at DESC") -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(f"SELECT * FROM words ORDER BY {order_by}").fetchall()


def get_words(limit: int = 50, order_by: str = "created_at DESC") -> list[sqlite3.Row]:
    """Cheklangan miqdordagi so'zlarni olish."""
    with get_conn() as conn:
        return conn.execute(f"SELECT * FROM words ORDER BY {order_by} LIMIT ?", (limit,)).fetchall()


def search_words(query: str = "", status_filter: str = "all", hard_only: bool = False) -> list[sqlite3.Row]:
    """So'zlarni qidirish va filtrlash."""
    clauses = []
    params = []

    if query.strip():
        q = f"%{query.strip().lower()}%"
        clauses.append("(LOWER(w.english) LIKE ? OR LOWER(w.uzbek) LIKE ?)")
        params.extend([q, q])

    if status_filter and status_filter != "all":
        clauses.append("w.status = ?")
        params.append(status_filter)

    if hard_only:
        clauses.append("(p.wrong_count > p.correct_count OR p.wrong_count >= 2)")

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT w.*, p.box_level, p.next_review, p.last_reviewed, p.correct_count, p.wrong_count
        FROM words w
        JOIN progress p ON p.word_id = w.id
        {where_sql}
        ORDER BY w.created_at DESC, w.id DESC
    """
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


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
    """So'zlar va ularning progress ma'lumotlarini 1 ta tezkor JOIN so'rovi bilan qaytaradi (N+1 yo'q)."""
    with get_conn() as conn:
        return conn.execute(
            f"""
            SELECT w.id, w.english, w.uzbek, w.status, w.example, w.created_at,
                   COALESCE(p.box_level, 0) as box_level,
                   COALESCE(p.correct_count, 0) as correct_count,
                   COALESCE(p.wrong_count, 0) as wrong_count
            FROM words w
            LEFT JOIN progress p ON p.word_id = w.id
            ORDER BY {order_by}
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


def record_sm2_review(word_id: int, quality: int) -> dict:
    """
    Anki SM-2 Spaced Repetition algoritmi:
    quality:
      5: Easy (Juda oson eslandi)
      4: Good (Yaxshi, me'yorida eslandi)
      3: Hard (Qiyinchilik bilan eslandi)
      0..2: Again/Wrong (Eslanmadi yoki xato)
    """
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT ease_factor, interval_days, repetitions, box_level, correct_count, wrong_count
            FROM progress WHERE word_id = ?
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

        q = max(0, min(5, quality))
        # SM-2 EF yangilash formulasi: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ef_prime = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        new_ef = max(1.3, round(ef_prime, 2))

        is_correct = (q >= 3)
        if q < 3:
            new_repetitions = 0
            new_interval = 1
            new_box = max(0, box - 1)
            w_cnt += 1
        else:
            if repetitions == 0:
                new_interval = 1
            elif repetitions == 1:
                new_interval = 6
            else:
                new_interval = max(1, round(interval * new_ef))
            new_repetitions = repetitions + 1
            new_box = min(5, box + 1)
            c_cnt += 1

        next_date = (datetime.date.today() + datetime.timedelta(days=new_interval)).isoformat()
        now_iso = datetime.datetime.now().isoformat()
        is_mastered = (new_box >= 5 or new_interval >= 21)

        conn.execute(
            """
            UPDATE progress SET
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
            (new_ef, new_interval, new_repetitions, new_box, c_cnt, w_cnt, now_iso, next_date, word_id),
        )

        status = "mastered" if is_mastered else ("learning" if new_box > 0 else "new")
        conn.execute("UPDATE words SET status=? WHERE id=?", (status, word_id))

    bump_daily_stat(practiced=1, correct=1 if is_correct else 0, wrong=0 if is_correct else 1)
    return {
        "word_id": word_id,
        "ease_factor": new_ef,
        "interval_days": new_interval,
        "repetitions": new_repetitions,
        "box_level": new_box,
        "next_review": next_date,
        "status": status,
    }


def record_answer(word_id: int, correct: bool):
    """Anki SM-2 ga muvofiqlashtirilgan javob yozish."""
    record_sm2_review(word_id, quality=4 if correct else 0)


def record_flashcard_answer(word_id: int, quality: str):
    """
    Flashcard javobini Anki SM-2 reytingi bo'yicha yozish:
    - 'hard': qiyin (quality=3)
    - 'good': yaxshi (quality=4)
    - 'easy': oson (quality=5)
    """
    q_map = {"hard": 3, "good": 4, "easy": 5}
    q_val = q_map.get(quality, 0)
    record_sm2_review(word_id, quality=q_val)


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


