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


def get_daily_activity_heatmap(days: int = 365) -> dict[str, int]:
    """So'nggi `days` kun ichidagi kunlik mashq qilingan so'zlar sonini {YYYY-MM-DD: count} ko'rinishida qaytaradi."""
    start_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date, practiced FROM daily_stats WHERE date >= ? ORDER BY date ASC",
            (start_date,)
        ).fetchall()
        return {r["date"]: r["practiced"] for r in rows}

