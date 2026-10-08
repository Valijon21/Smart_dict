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

