"""
Vocab Master Pro — Kunlik Missiyalar va Battle Pass Tizimi (Daily Quests).
Har kuni 00:00 da yangilanadigan dinamik 3 ta vazifa va kunlik Super Bonus (XP).
"""
import datetime
import hashlib
import json
from typing import Any
import database as db
import gamification
from logger import get_logger

logger = get_logger("daily_quests")

# Har bir toifa uchun vazifalar banki
QUEST_POOL_PRACTICE = [
    {
        "id_suffix": "p_words_10",
        "type": "practice_words",
        "title": "So'z mashqi",
        "description": "Bugun mashqda 10 ta so'zni to'g'ri toping",
        "icon": "📚",
        "target": 10,
        "reward_xp": 25,
    },
    {
        "id_suffix": "p_words_15",
        "type": "practice_words",
        "title": "Faol o'quvchi",
        "description": "Bugun mashqda 15 ta so'zga to'g'ri javob bering",
        "icon": "🎯",
        "target": 15,
        "reward_xp": 35,
    },
    {
        "id_suffix": "p_streak_5",
        "type": "practice_streak",
        "title": "Snayper mashqi",
        "description": "Mashqda ketma-ket 5 ta so'zga xatosiz javob bering",
        "icon": "⚡",
        "target": 5,
        "reward_xp": 25,
    },
    {
        "id_suffix": "p_words_20",
        "type": "practice_words",
        "title": "Lug'at marafoni",
        "description": "Bugun 20 ta so'z mashqini muvaffaqiyatli yakunlang",
        "icon": "🔥",
        "target": 20,
        "reward_xp": 40,
    },
]

QUEST_POOL_GAMES = [
    {
        "id_suffix": "g_score_50",
        "type": "game_score",
        "title": "O'yin ustasi",
        "description": "Mini-o'yinlarda jami 50 ball to'plang",
        "icon": "🎮",
        "target": 50,
        "reward_xp": 30,
    },
    {
        "id_suffix": "g_blitz_5",
        "type": "blitz_words",
        "title": "Tezkor Blitz",
        "description": "Blitz marafon o'yinida 5 ta so'zni to'g'ri toping",
        "icon": "⚡",
        "target": 5,
        "reward_xp": 25,
    },
    {
        "id_suffix": "g_match_1",
        "type": "match_game",
        "title": "Juftliklar chempioni",
        "description": "So'zlarni juftlash o'yinida kamida 1 marta g'alaba qozoning",
        "icon": "🧩",
        "target": 1,
        "reward_xp": 25,
    },
    {
        "id_suffix": "g_score_80",
        "type": "game_score",
        "title": "Arena rekordchisi",
        "description": "Mini-o'yinlarda jami 80 ball to'plang",
        "icon": "🏆",
        "target": 80,
        "reward_xp": 40,
    },
]

QUEST_POOL_AUDIO_SPECIAL = [
    {
        "id_suffix": "s_mic_1",
        "type": "pronunciation",
        "title": "Talaffuz sinovi",
        "description": "Kamida 1 ta so'z talaffuzini mikrofonda sinab ko'ring",
        "icon": "🎙️",
        "target": 1,
        "reward_xp": 20,
    },
    {
        "id_suffix": "s_mic_2",
        "type": "pronunciation",
        "title": "Ovozli mashq",
        "description": "Mikrofon orqali 2 ta so'z talaffuzini tekshiring",
        "icon": "🎙️",
        "target": 2,
        "reward_xp": 30,
    },
    {
        "id_suffix": "s_listen_5",
        "type": "listening_words",
        "title": "O'tkir quloq",
        "description": "Eshitib yozish (Listening) rejimida 5 ta so'z toping",
        "icon": "🎧",
        "target": 5,
        "reward_xp": 25,
    },
    {
        "id_suffix": "s_flash_5",
        "type": "flashcard_words",
        "title": "Xotira charxi",
        "description": "Flashcard rejimida 5 ta so'zni takrorlang",
        "icon": "🎴",
        "target": 5,
        "reward_xp": 20,
    },
]

DAILY_BONUS_XP = 50


def _get_today_str() -> str:
    """Bugungi sanani YYYY-MM-DD formatida qaytaradi."""
    return datetime.date.today().strftime("%Y-%m-%d")


def _generate_quests_for_date(date_str: str) -> list[dict]:
    """Berilgan sana uchun deterministik 3 ta dinamik vazifa hosil qiladi."""
    def pick_item(pool: list[dict], salt: str) -> dict:
        h = hashlib.md5(f"{date_str}_{salt}".encode("utf-8")).hexdigest()
        idx = int(h, 16) % len(pool)
        raw = pool[idx]
        return {
            "id": f"quest_{date_str}_{raw['id_suffix']}",
            "type": raw["type"],
            "title": raw["title"],
            "description": raw["description"],
            "icon": raw["icon"],
            "target": raw["target"],
            "current": 0,
            "reward_xp": raw["reward_xp"],
            "claimed": False,
        }

    q1 = pick_item(QUEST_POOL_PRACTICE, "cat_practice")
    q2 = pick_item(QUEST_POOL_GAMES, "cat_games")
    q3 = pick_item(QUEST_POOL_AUDIO_SPECIAL, "cat_audio")
    return [q1, q2, q3]


def get_daily_quests_state() -> dict:
    """
    Bugungi kunlik missiyalar holatini oladi.
    Agar kun o'zgargan bo'lsa yoki yangi bo'lsa, avtomatik yangi 3 ta vazifani shakllantiradi.
    """
    today = _get_today_str()
    raw_json = db.get_setting("daily_quests_state", "{}")
    state = {}
    try:
        state = json.loads(raw_json) if raw_json else {}
    except Exception as e:
        logger.error(f"Kunlik missiyalar JSON o'qishda xatolik: {e}")
        state = {}

    if not isinstance(state, dict) or state.get("date") != today or "quests" not in state:
        # Yangi kun — yangi vazifalar to'plamini shakllantiramiz
        quests = _generate_quests_for_date(today)
        state = {
            "date": today,
            "bonus_claimed": False,
            "bonus_reward_xp": DAILY_BONUS_XP,
            "quests": quests,
        }
        _save_daily_quests_state(state)

    return state


def _save_daily_quests_state(state: dict):
    """Holatni bazaga xavfsiz saqlash."""
    try:
        raw_json = json.dumps(state, ensure_ascii=False)
        db.set_setting("daily_quests_state", raw_json)
    except Exception as e:
        logger.error(f"Kunlik missiyalar saqlashda xatolik: {e}")


def record_quest_progress(quest_type: str, amount: int = 1) -> dict:
    """
    Faoliyat bo'yicha (mashq, o'yin, talaffuz) missiya progressini oshirish.
    Qaytaradi: {
        "updated": bool,
        "completed_quests": list[dict],
        "state": dict
    }
    """
    if amount <= 0:
        return {"updated": False, "completed_quests": [], "state": get_daily_quests_state()}

    state = get_daily_quests_state()
    quests = state.get("quests", [])
    updated = False
    newly_completed = []

    for q in quests:
        if q.get("type") == quest_type:
            cur = q.get("current", 0)
            target = q.get("target", 1)
            was_done = cur >= target

            new_val = min(target, cur + amount)
            if new_val != cur:
                q["current"] = new_val
                updated = True
                if not was_done and new_val >= target:
                    newly_completed.append(q)
                    logger.info(f"Kunlik vazifa bajarildi: {q['title']}")

    if updated:
        _save_daily_quests_state(state)

    return {
        "updated": updated,
        "completed_quests": newly_completed,
        "state": state,
    }


def claim_quest_reward(quest_id: str) -> dict:
    """
    Bajarilgan vazifa uchun XP sovrinini olish.
    Qaytaradi: {
        "success": bool,
        "reward_xp": int,
        "new_total_xp": int,
        "level_up": bool,
        "level_title": str,
        "all_quests_claimed": bool,
        "message": str
    }
    """
    state = get_daily_quests_state()
    quests = state.get("quests", [])

    target_quest = None
    for q in quests:
        if q.get("id") == quest_id:
            target_quest = q
            break

    if not target_quest:
        return {"success": False, "message": "Vazifa topilmadi", "reward_xp": 0}

    if target_quest.get("claimed", False):
        return {"success": False, "message": "Bu mukofot avval olingan", "reward_xp": 0}

    cur = target_quest.get("current", 0)
    target = target_quest.get("target", 1)
    if cur < target:
        return {"success": False, "message": "Vazifa hali to'liq bajarilmagan", "reward_xp": 0}

    # Mukofot berish
    xp = target_quest.get("reward_xp", 20)
    target_quest["claimed"] = True
    _save_daily_quests_state(state)

    new_total, level_up, level_title = gamification.award_xp(xp)

    # Barcha 3 ta vazifa olinganligini tekshirish
    all_claimed = all(q.get("claimed", False) for q in quests)

    return {
        "success": True,
        "reward_xp": xp,
        "new_total_xp": new_total,
        "level_up": level_up,
        "level_title": level_title,
        "all_quests_claimed": all_claimed,
        "message": f"+{xp} XP qo'shildi!",
    }


def claim_daily_bonus() -> dict:
    """
    Kunlik Battle Pass Super Bonusini (+50 XP) olish (faqat 3 ta vazifa olingach ochiladi).
    """
    state = get_daily_quests_state()
    quests = state.get("quests", [])

    if state.get("bonus_claimed", False):
        return {"success": False, "message": "Kunlik super bonus allaqachon olingan!", "reward_xp": 0}

    all_claimed = len(quests) > 0 and all(q.get("claimed", False) for q in quests)
    if not all_claimed:
        return {"success": False, "message": "Barcha 3 ta kunlik vazifani yig'ishingiz kerak!", "reward_xp": 0}

    bonus_xp = state.get("bonus_reward_xp", DAILY_BONUS_XP)
    state["bonus_claimed"] = True
    _save_daily_quests_state(state)

    new_total, level_up, level_title = gamification.award_xp(bonus_xp)

    return {
        "success": True,
        "reward_xp": bonus_xp,
        "new_total_xp": new_total,
        "level_up": level_up,
        "level_title": level_title,
        "message": f"Tabriklaymiz! Kunlik Super Bonus: +{bonus_xp} XP qo'shildi!",
    }


def get_daily_summary() -> dict:
    """
    UI uchun sodda qisqacha ma'lumot qaytaradi.
    """
    state = get_daily_quests_state()
    quests = state.get("quests", [])
    completed_count = sum(1 for q in quests if q.get("current", 0) >= q.get("target", 1))
    claimed_count = sum(1 for q in quests if q.get("claimed", False))

    return {
        "date": state.get("date", _get_today_str()),
        "total_count": len(quests),
        "completed_count": completed_count,
        "claimed_count": claimed_count,
        "all_completed": completed_count == len(quests) and len(quests) > 0,
        "all_claimed": claimed_count == len(quests) and len(quests) > 0,
        "bonus_claimed": state.get("bonus_claimed", False),
        "bonus_reward_xp": state.get("bonus_reward_xp", DAILY_BONUS_XP),
        "quests": quests,
    }
