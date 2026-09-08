"""
Vocab Master Pro — Gamifikatsiya Tizimi (XP, Darajalar, Yutuqlar/Badges).
Foydalanuvchi motivatsiyasini oshirish uchun ballar, darajalar va sovrinlar tizimi.
"""
import math
import database as db
from logger import get_logger

logger = get_logger("gamification")

# Barcha standart yutuqlar ro'yxati
DEFAULT_ACHIEVEMENTS = [
    {
        "id": "first_step",
        "title": "Birinchi qadam",
        "description": "Dasturdagi ilk mashq savoliga to'g'ri javob berildi",
        "icon": "🌱",
        "category": "practice",
        "max_progress": 1,
    },
    {
        "id": "streak_3",
        "title": "Olov uchquni",
        "description": "3 kun ketma-ket kunlik rejani to'liq bajardingiz",
        "icon": "⚡",
        "category": "streak",
        "max_progress": 3,
    },
    {
        "id": "streak_7",
        "title": "Hafta qahramoni",
        "description": "7 kun uzluksiz kunlik reja mashqlarini bajardingiz",
        "icon": "🔥",
        "category": "streak",
        "max_progress": 7,
    },
    {
        "id": "sniper_10",
        "title": "Snayper",
        "description": "Bir sessiyada 10 ta so'zga ketma-ket xatosiz javob berildi",
        "icon": "🎯",
        "category": "skill",
        "max_progress": 10,
    },
    {
        "id": "sharp_ear",
        "title": "O'tkir quloq",
        "description": "Eshitib yozish (Listening) rejimida 25 ta to'g'ri javob berildi",
        "icon": "🎧",
        "category": "mode",
        "max_progress": 25,
    },
    {
        "id": "scramble_master",
        "title": "Harf ustasi",
        "description": "Harf terish (Scramble) rejimida 25 ta so'z to'g'ri yig'ildi",
        "icon": "🔤",
        "category": "mode",
        "max_progress": 25,
    },
    {
        "id": "collector_100",
        "title": "Kutubxonachi",
        "description": "Shaxsiy lug'at bazangizga 100 ta so'z jamlandi",
        "icon": "📚",
        "category": "collection",
        "max_progress": 100,
    },
    {
        "id": "mastered_50",
        "title": "Xotira vunderkindi",
        "description": "50 ta so'zni eng yuqori (Mastered) darajasiga yetkazdingiz",
        "icon": "👑",
        "category": "mastery",
        "max_progress": 50,
    },
]

_DEFAULT_ACH_MAP = {a["id"]: a for a in DEFAULT_ACHIEVEMENTS}

# Rejimlar bo'yicha bog'langan yutuqlar xaritasi (KISS & Open/Closed)
_MODE_ACHIEVEMENTS = {
    "listening": "sharp_ear",
    "scramble": "scramble_master",
}


def init_gamification():
    """Standart yutuqlarni bazaga yuklash."""
    db.init_default_achievements(DEFAULT_ACHIEVEMENTS)


def get_level_info(xp: int = None) -> dict:
    """
    Foydalanuvchi darajasi va keyingi darajagacha bo'lgan progressni hisoblaydi.
    Formula: Har bir daraja (Level L) uchun kerakli umumiy XP = (L - 1)^2 * 50 + (L - 1) * 50
    """
    if xp is None:
        xp = db.get_xp()

    level = 1
    while True:
        next_req = level * level * 50 + level * 50
        if xp < next_req:
            break
        level += 1

    prev_req = (level - 1) * (level - 1) * 50 + (level - 1) * 50 if level > 1 else 0
    next_req = level * level * 50 + level * 50

    xp_in_level = xp - prev_req
    xp_for_level = next_req - prev_req
    progress_pct = min(100, max(0, int(xp_in_level / xp_for_level * 100))) if xp_for_level > 0 else 100

    # Titul va rang
    if level < 5:
        title = "Boshlovchi"
        badge = "🟢"
        color = "#10B981"
    elif level < 10:
        title = "Qiziquvchi"
        badge = "🔵"
        color = "#3B82F6"
    elif level < 20:
        title = "O'quvchi"
        badge = "🟣"
        color = "#8B5CF6"
    elif level < 35:
        title = "Poliglot"
        badge = "🟠"
        color = "#F59E0B"
    else:
        title = "So'z Ustasi"
        badge = "👑"
        color = "#EF4444"

    return {
        "level": level,
        "title": title,
        "badge": badge,
        "color": color,
        "total_xp": xp,
        "xp_in_level": xp_in_level,
        "xp_needed": xp_for_level - xp_in_level,
        "next_level_xp": next_req,
        "progress_percent": progress_pct,
    }


def award_xp(amount: int) -> tuple[int, bool, str]:
    """
    To'g'ridan-to'g'ri foydalanuvchiga XP berish (Word Match, Mini vidjet yoki maxsus sovrinlar).
    Qaytaradi: (new_total_xp, level_up: bool, new_level_title: str)
    """
    old_level = get_level_info()["level"]
    new_total_xp = db.add_xp(amount)
    new_info = get_level_info(new_total_xp)
    level_up = new_info["level"] > old_level
    level_title = f"{new_info['badge']} {new_info['level']}-Daraja: {new_info['title']}"
    logger.info(f"Foydalanuvchiga +{amount} XP berildi. Yangi jami XP: {new_total_xp}")
    return new_total_xp, level_up, level_title


def record_practice_answer(is_correct: bool, mode: str, consecutive_correct: int) -> dict:
    """
    Mashqda javob berilganda chaqiriladi:
    - XP hisoblaydi va qo'shadi;
    - Bog'liq yutuqlarni tekshiradi;
    - Yangi ochilgan yutuqlar ro'yxatini qaytaradi.
    """
    xp_gained = 0
    unlocked = []

    old_level = get_level_info()["level"]

    if is_correct:
        # Qiyinroq rejimlarga ko'proq XP
        if mode in ("typing", "listening", "scramble"):
            xp_gained = 20
        else:
            xp_gained = 10

        new_total_xp = db.add_xp(xp_gained)

        # 1. Ilk to'g'ri javob
        if db.unlock_achievement("first_step"):
            unlocked.append(_get_ach_by_id("first_step"))

        # 2. Snayper (10 ketma-ket to'g'ri)
        if consecutive_correct >= 10:
            if db.unlock_achievement("sniper_10"):
                unlocked.append(_get_ach_by_id("sniper_10"))

        # 3. Rejimlar bo'yicha progress (DRY & Open/Closed)
        if mode in _MODE_ACHIEVEMENTS:
            ach_id = _MODE_ACHIEVEMENTS[mode]
            ach = db.get_achievement(ach_id)
            # Agar hali ochilmagan bo'lsa progressni oshiramiz
            if ach and not ach.get("unlocked_at"):
                new_p = ach["progress"] + 1
                if db.update_achievement_progress(ach_id, new_p):
                    unlocked.append(_get_ach_by_id(ach_id))

    new_level_info = get_level_info()
    level_up = new_level_info["level"] > old_level

    # Global yutuqlarni tekshirish (streak, so'zlar soni)
    global_unlocked = check_global_achievements()
    unlocked.extend(global_unlocked)

    return {
        "xp_gained": xp_gained,
        "total_xp": new_level_info["total_xp"],
        "level_info": new_level_info,
        "level_up": level_up,
        "unlocked_achievements": unlocked,
    }


def check_global_achievements() -> list[dict]:
    """Streak, lug'at hajmi va mastered so'zlar bilan bog'liq yutuqlarni tekshiradi."""
    unlocked = []

    # Streak
    streak = db.get_current_streak()
    if streak >= 3:
        if db.unlock_achievement("streak_3"):
            unlocked.append(_get_ach_by_id("streak_3"))
    if streak >= 7:
        if db.unlock_achievement("streak_7"):
            unlocked.append(_get_ach_by_id("streak_7"))

    # So'zlar soni
    counts = db.word_count()
    if counts["total"] >= 100:
        if db.unlock_achievement("collector_100"):
            unlocked.append(_get_ach_by_id("collector_100"))
    else:
        db.update_achievement_progress("collector_100", counts["total"])

    if counts["mastered"] >= 50:
        if db.unlock_achievement("mastered_50"):
            unlocked.append(_get_ach_by_id("mastered_50"))
    else:
        db.update_achievement_progress("mastered_50", counts["mastered"])

    return unlocked


def _get_ach_by_id(ach_id: str) -> dict:
    return _DEFAULT_ACH_MAP.get(
        ach_id,
        {"id": ach_id, "title": "Yangi Yutuq!", "icon": "🏆", "description": ""}
    )


def _find_ach_db(ach_id: str) -> dict | None:
    return db.get_achievement(ach_id)
