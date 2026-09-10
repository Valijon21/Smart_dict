"""
Vocab Master Pro — Ebbinghaus Memory Retention Analytics Service.
Nemis psixologi Hermann Ebbinghaus'ning "Unutish egri chizig'i" (Forgetting Curve)
matematik formulasiga asoslangan tahliliy modul:
    R = exp(-delta_t / S)
Bu yerda:
- delta_t: so'nggi takrorlashdan buyon o'tgan vaqt (kunlarda);
- S: xotira barqarorligi (Memory Stability factor, kunlarda).
Leitner qutilari (Box 0-5), Anki SM-2 intervallari (interval_days, ease_factor)
va to'g'ri/xato javoblar nisbati asosida har bir so'zning xotirada saqlanish foizini,
kelgusi 7 kunlik unutish xavfi prognozini va zaiflashgan so'zlar ro'yxatini hisoblaydi.
"""
import math
import datetime
import time
from typing import Any

import database as db
from logger import get_logger

logger = get_logger("retention_analytics")

# Xotira egri chizig'i natijalari uchun TTL kesh (15 soniya)
_RETENTION_CACHE: dict | None = None
_RETENTION_CACHE_TIME: float = 0.0


def invalidate_retention_cache():
    """Baza ma'lumotlari yangilanganda keshni tozalash."""
    global _RETENTION_CACHE, _RETENTION_CACHE_TIME
    _RETENTION_CACHE = None
    _RETENTION_CACHE_TIME = 0.0


def calculate_word_stability(
    box_level: int,
    ease_factor: float,
    interval_days: int,
    correct_count: int,
    wrong_count: int
) -> float:
    """
    So'zning xotira barqarorligini (S - kunlarda) hisoblash.
    Box 5 dagi so'zlar barqarorligi 40-90 kun, yangi so'zlar esa 1-2 kun bo'ladi.
    """
    box = max(0, min(5, box_level or 0))
    ef = max(1.3, float(ease_factor or 2.5))
    iv = max(1, int(interval_days or 1))
    c_cnt = max(0, int(correct_count or 0))
    w_cnt = max(0, int(wrong_count or 0))

    # Birlamchi barqarorlik (Box va intervalga mutanosib)
    base_s = 1.5 * (1.0 + 0.5 * box) * (ef / 2.5) * max(1.0, float(iv) * 0.8)

    # Xatolar jarimasi
    if w_cnt > 0:
        penalty = (c_cnt + 1.0) / (c_cnt + w_cnt + 1.0)
        base_s *= max(0.35, penalty)

    return max(0.8, base_s)


def calculate_retention_rate(
    last_reviewed: str | None,
    created_at: str | None,
    stability: float,
    days_offset: int = 0
) -> float:
    """
    R = exp(-delta_t / S) formulasi bo'yicha saqlanish ko'rsatkichi (0.0 .. 1.0).
    days_offset: kelgusi kunlarni prognoz qilish uchun (+1, +3, +7).
    """
    today = datetime.date.today()

    ref_date = None
    if last_reviewed:
        try:
            ref_date = datetime.date.fromisoformat(last_reviewed[:10])
        except Exception:
            pass

    if not ref_date and created_at:
        try:
            ref_date = datetime.date.fromisoformat(created_at[:10])
        except Exception:
            pass

    if not ref_date:
        ref_date = today

    delta_days = (today - ref_date).days + days_offset
    delta_t = max(0.08, float(delta_days))  # hech bo'lmaganda bir necha soat

    # Hermann Ebbinghaus formulasi
    r = math.exp(-delta_t / max(0.8, stability))
    return min(1.0, max(0.05, r))


def get_memory_retention_overview() -> dict:
    """
    Foydalanuvchining butun lug'ati bo'yicha Ebbinghaus Xotira Tahlili:
    - O'rtacha saqlanish foizi (overall_retention_pct);
    - Barqaror (R >= 80%), Mustahkamlanayotgan (50% <= R < 80%), Zaif (R < 50%) so'zlar;
    - Kelgusi 7 kunlik prognoz;
    - Zudlik bilan takrorlash lozim bo'lgan zaif so'zlar ID lari.
    """
    global _RETENTION_CACHE, _RETENTION_CACHE_TIME
    now = time.time()
    if _RETENTION_CACHE is not None and (now - _RETENTION_CACHE_TIME) < 15.0:
        return _RETENTION_CACHE

    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT 
                w.id,
                w.english,
                w.uzbek,
                w.created_at,
                p.box_level,
                p.last_reviewed,
                p.next_review,
                p.correct_count,
                p.wrong_count,
                p.ease_factor,
                p.interval_days
            FROM words w
            LEFT JOIN progress p ON w.id = p.word_id
            """
        ).fetchall()

    if not rows:
        return {
            "total_words": 0,
            "overall_retention_pct": 100.0,
            "stable_count": 0,
            "consolidating_count": 0,
            "vulnerable_count": 0,
            "vulnerable_word_ids": [],
            "forecast": [
                {"label": "Bugun", "days": 0, "retention_pct": 100.0},
                {"label": "Ertaga", "days": 1, "retention_pct": 92.0},
                {"label": "+3 kun", "days": 3, "retention_pct": 82.0},
                {"label": "+7 kun", "days": 7, "retention_pct": 71.0},
            ],
            "recommendation": "Lug'atga so'zlar qo'shib mashq qilishni boshlang!"
        }

    total_words = len(rows)
    current_retentions = []
    forecast_retentions = {0: [], 1: [], 3: [], 7: []}

    stable_count = 0
    consolidating_count = 0
    vulnerable_count = 0
    vulnerable_ids = []

    today_str = datetime.date.today().isoformat()

    for r in rows:
        w_id = r["id"]
        box = r["box_level"] or 0
        ef = r["ease_factor"] or 2.5
        iv = r["interval_days"] or 1
        c_cnt = r["correct_count"] or 0
        w_cnt = r["wrong_count"] or 0
        last_rev = r["last_reviewed"]
        created = r["created_at"]
        next_rev = r["next_review"] or ""

        s = calculate_word_stability(box, ef, iv, c_cnt, w_cnt)
        r_current = calculate_retention_rate(last_rev, created, s, days_offset=0)

        # Agar takrorlash muddati o'tib ketgan bo'lsa (next_review <= bugun)
        is_past_due = bool(next_rev and next_rev[:10] <= today_str)
        if is_past_due and r_current > 0.65:
            r_current = 0.58  # Muddat kelganligi tufayli pasaytirish

        current_retentions.append(r_current)

        if r_current >= 0.78:
            stable_count += 1
        elif r_current >= 0.50:
            consolidating_count += 1
        else:
            vulnerable_count += 1
            vulnerable_ids.append(w_id)

        # Muddat o'tgan bo'lsa ham zaiflar ro'yxatiga olamiz
        if is_past_due and w_id not in vulnerable_ids:
            vulnerable_ids.append(w_id)

        # 7 kunlik prognoz uchun hisoblash
        for offset_day in (0, 1, 3, 7):
            r_future = calculate_retention_rate(last_rev, created, s, days_offset=offset_day)
            forecast_retentions[offset_day].append(r_future)

    avg_current_pct = round((sum(current_retentions) / total_words) * 100, 1)

    forecast = [
        {
            "label": "Bugun",
            "days": 0,
            "retention_pct": round((sum(forecast_retentions[0]) / total_words) * 100, 1)
        },
        {
            "label": "Ertaga",
            "days": 1,
            "retention_pct": round((sum(forecast_retentions[1]) / total_words) * 100, 1)
        },
        {
            "label": "+3 kun",
            "days": 3,
            "retention_pct": round((sum(forecast_retentions[3]) / total_words) * 100, 1)
        },
        {
            "label": "+7 kun",
            "days": 7,
            "retention_pct": round((sum(forecast_retentions[7]) / total_words) * 100, 1)
        }
    ]

    # Tavsiya matni
    if vulnerable_count == 0 and not vulnerable_ids:
        rec = "🌟 A'lo xotira! Barcha so'zlaringiz mustahkam saqlanmoqda. Yangi so'zlar qo'shishingiz mumkin."
    elif len(vulnerable_ids) <= 3:
        rec = f"👍 Yaxshi natija! {len(vulnerable_ids)} ta so'z unutish arafasida. Qisqa mashq bilan mustahkamlab oling."
    else:
        rec = f"⚠️ Diqqat: {len(vulnerable_ids)} ta so'z unutish xavfi ostida! Zudlik bilan 'Qutqarish' mashqini o'tkazing."

    result = {
        "total_words": total_words,
        "overall_retention_pct": avg_current_pct,
        "stable_count": stable_count,
        "consolidating_count": consolidating_count,
        "vulnerable_count": len(vulnerable_ids),
        "vulnerable_word_ids": vulnerable_ids,
        "forecast": forecast,
        "recommendation": rec
    }
    _RETENTION_CACHE = result
    _RETENTION_CACHE_TIME = now
    return result
