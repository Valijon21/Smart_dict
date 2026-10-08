from core.db.cache import _invalidate_cache
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

