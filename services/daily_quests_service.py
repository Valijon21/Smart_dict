"""
Vocab Master Pro — Daily Quests Service.
Foydalanuvchi mashq, o'yin va talaffuz harakatlarini kunlik missiyalar bilan bog'lovchi xizmat.
"""
from core.daily_quests import (
    get_daily_quests_state,
    record_quest_progress,
    claim_quest_reward,
    claim_daily_bonus,
    get_daily_summary,
    DAILY_BONUS_XP,
)

__all__ = [
    "get_daily_quests_state",
    "record_quest_progress",
    "claim_quest_reward",
    "claim_daily_bonus",
    "get_daily_summary",
    "DAILY_BONUS_XP",
]
