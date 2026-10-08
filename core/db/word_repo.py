from core.db.connection import get_conn, _safe_order_by
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
from core.db.cache import _invalidate_cache
from core.db.settings_repo import get_setting, set_setting
from core.db.stats_repo import bump_daily_stat
from core.db.settings_repo import set_setting
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



_INVISIBLE_CHARS = re.compile(r'[\x00-\x1f\x7f-\x9f\u200b\uFEFF]')


def normalize(word: str) -> str:
    cleaned = _INVISIBLE_CHARS.sub("", str(word or "")).strip().lower()
    cleaned = cleaned.replace("‘", "'").replace("’", "'").replace("`", "'")
    return " ".join(cleaned.split())


def add_word(english: str, uzbek: str, source: str = "manual", example: str = "") -> int | None:
    """Yangi so'z qo'shadi. Muvaffaqiyatli bo'lsa word_id, dublikat bo'lsa None qaytaradi."""
    english_n = normalize(english)
    uzbek_n = _INVISIBLE_CHARS.sub("", str(uzbek or "")).strip()
    example_n = _INVISIBLE_CHARS.sub("", str(example or "")).strip()
    if not english_n or not uzbek_n:
        return None

    if uzbek_n.count("(") > uzbek_n.count(")"):
        uzbek_n += ")"
    if english_n.count("(") > english_n.count(")"):
        english_n += ")"

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
            uz_str = _INVISIBLE_CHARS.sub("", str(uz or "")).strip()
            ex_str = _INVISIBLE_CHARS.sub("", str(ex or "")).strip()

            if uz_str.count("(") > uz_str.count(")"):
                uz_str += ")"
            if key.count("(") > key.count(")"):
                key += ")"

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

