"""
tests/test_daily_quests.py
core/daily_quests.py uchun pytest smoke testlari.
Mavjud test_database.py dagi pattern: core.database.DB_PATH to'g'ridan-to'g'ri almashtiriladi.
"""
import sys
import json
import datetime
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import database as db
import core.database as _cdb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def temp_db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("quests_db")
    test_db = tmp / "test_quests.db"
    original_path = _cdb.DB_PATH
    _cdb.DB_PATH = test_db
    _cdb.init_db()
    yield test_db
    _cdb.DB_PATH = original_path


@pytest.fixture(autouse=True)
def clean_db(temp_db):
    """Har bir test oldidan DB tozalanadi va qayta initsializatsiya."""
    original = _cdb.DB_PATH
    _cdb.DB_PATH = temp_db
    with _cdb.get_conn() as conn:
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM progress")
        conn.execute("DELETE FROM daily_stats")
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM achievements")
    _cdb.init_db()
    yield
    _cdb.DB_PATH = original


# ---------------------------------------------------------------------------
# _generate_quests_for_date — deterministik quest yaratish
# ---------------------------------------------------------------------------
class TestGenerateQuestsForDate:
    def test_returns_exactly_3_quests(self):
        from core.daily_quests import _generate_quests_for_date
        quests = _generate_quests_for_date("2026-01-01")
        assert len(quests) == 3

    def test_deterministic_same_date(self):
        from core.daily_quests import _generate_quests_for_date
        q1 = _generate_quests_for_date("2026-01-01")
        q2 = _generate_quests_for_date("2026-01-01")
        assert [q["id"] for q in q1] == [q["id"] for q in q2]

    def test_each_quest_has_required_fields(self):
        from core.daily_quests import _generate_quests_for_date
        quests = _generate_quests_for_date("2026-03-10")
        required = {"id", "type", "title", "description", "icon", "target", "current", "reward_xp", "claimed"}
        for q in quests:
            assert required.issubset(q.keys())

    def test_quest_current_starts_at_zero(self):
        from core.daily_quests import _generate_quests_for_date
        for q in _generate_quests_for_date("2026-03-10"):
            assert q["current"] == 0

    def test_quest_claimed_starts_false(self):
        from core.daily_quests import _generate_quests_for_date
        for q in _generate_quests_for_date("2026-03-10"):
            assert q["claimed"] is False

    def test_quest_target_is_positive(self):
        from core.daily_quests import _generate_quests_for_date
        for q in _generate_quests_for_date("2026-03-10"):
            assert q["target"] > 0

    def test_reward_xp_is_positive(self):
        from core.daily_quests import _generate_quests_for_date
        for q in _generate_quests_for_date("2026-03-10"):
            assert q["reward_xp"] > 0


# ---------------------------------------------------------------------------
# get_daily_quests_state — holat olish
# ---------------------------------------------------------------------------
class TestGetDailyQuestsState:
    def test_returns_dict(self):
        from core.daily_quests import get_daily_quests_state
        state = get_daily_quests_state()
        assert isinstance(state, dict)

    def test_has_required_keys(self):
        from core.daily_quests import get_daily_quests_state
        state = get_daily_quests_state()
        assert "date" in state
        assert "quests" in state
        assert "bonus_claimed" in state

    def test_date_is_today(self):
        from core.daily_quests import get_daily_quests_state
        state = get_daily_quests_state()
        today = datetime.date.today().strftime("%Y-%m-%d")
        assert state["date"] == today

    def test_quests_is_list_of_3(self):
        from core.daily_quests import get_daily_quests_state
        state = get_daily_quests_state()
        assert isinstance(state["quests"], list)
        assert len(state["quests"]) == 3

    def test_bonus_not_claimed_initially(self):
        from core.daily_quests import get_daily_quests_state
        state = get_daily_quests_state()
        assert state["bonus_claimed"] is False

    def test_same_state_on_second_call(self):
        from core.daily_quests import get_daily_quests_state
        s1 = get_daily_quests_state()
        s2 = get_daily_quests_state()
        assert [q["id"] for q in s1["quests"]] == [q["id"] for q in s2["quests"]]


# ---------------------------------------------------------------------------
# record_quest_progress — progress yozish
# ---------------------------------------------------------------------------
class TestRecordQuestProgress:
    def test_returns_dict_with_keys(self):
        from core.daily_quests import record_quest_progress
        result = record_quest_progress("practice_words", 1)
        assert {"updated", "completed_quests", "state"}.issubset(result.keys())

    def test_zero_amount_returns_not_updated(self):
        from core.daily_quests import record_quest_progress
        result = record_quest_progress("practice_words", 0)
        assert result["updated"] is False

    def test_negative_amount_returns_not_updated(self):
        from core.daily_quests import record_quest_progress
        result = record_quest_progress("practice_words", -5)
        assert result["updated"] is False

    def test_valid_type_updates_progress(self):
        from core.daily_quests import get_daily_quests_state, record_quest_progress
        state = get_daily_quests_state()
        quest_type = state["quests"][0]["type"]
        result = record_quest_progress(quest_type, 1)
        assert result["updated"] is True

    def test_unknown_type_does_not_update(self):
        from core.daily_quests import record_quest_progress
        result = record_quest_progress("nonexistent_quest_type_xyz", 5)
        assert result["updated"] is False

    def test_completing_quest_adds_to_completed_list(self):
        from core.daily_quests import get_daily_quests_state, record_quest_progress
        state = get_daily_quests_state()
        q = state["quests"][0]
        result = record_quest_progress(q["type"], q["target"])
        assert len(result["completed_quests"]) >= 1

    def test_progress_capped_at_target(self):
        from core.daily_quests import get_daily_quests_state, record_quest_progress
        state = get_daily_quests_state()
        q = state["quests"][0]
        record_quest_progress(q["type"], q["target"] + 100)
        new_state = get_daily_quests_state()
        updated_q = next(x for x in new_state["quests"] if x["type"] == q["type"])
        assert updated_q["current"] <= q["target"]


# ---------------------------------------------------------------------------
# claim_quest_reward — mukofot olish
# ---------------------------------------------------------------------------
class TestClaimQuestReward:
    def _complete_first_quest(self):
        from core.daily_quests import get_daily_quests_state, record_quest_progress
        state = get_daily_quests_state()
        q = state["quests"][0]
        record_quest_progress(q["type"], q["target"])
        return q["id"]

    def test_claim_uncompleted_quest_fails(self):
        from core.daily_quests import get_daily_quests_state, claim_quest_reward
        state = get_daily_quests_state()
        q_id = state["quests"][0]["id"]
        result = claim_quest_reward(q_id)
        assert result["success"] is False

    def test_claim_completed_quest_succeeds(self):
        from core.daily_quests import claim_quest_reward
        q_id = self._complete_first_quest()
        result = claim_quest_reward(q_id)
        assert result["success"] is True

    def test_claim_twice_fails(self):
        from core.daily_quests import claim_quest_reward
        q_id = self._complete_first_quest()
        claim_quest_reward(q_id)
        result2 = claim_quest_reward(q_id)
        assert result2["success"] is False

    def test_claim_gives_xp(self):
        from core.daily_quests import claim_quest_reward
        q_id = self._complete_first_quest()
        result = claim_quest_reward(q_id)
        assert result.get("reward_xp", 0) > 0

    def test_claim_nonexistent_quest_fails(self):
        from core.daily_quests import claim_quest_reward
        result = claim_quest_reward("quest_nonexistent_id_xyz")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# claim_daily_bonus — kunlik bonus
# ---------------------------------------------------------------------------
class TestClaimDailyBonus:
    def _complete_all_quests(self):
        from core.daily_quests import get_daily_quests_state, record_quest_progress, claim_quest_reward
        state = get_daily_quests_state()
        for q in state["quests"]:
            record_quest_progress(q["type"], q["target"])
            claim_quest_reward(q["id"])

    def test_bonus_fails_without_completing_quests(self):
        from core.daily_quests import claim_daily_bonus
        result = claim_daily_bonus()
        assert result["success"] is False

    def test_bonus_succeeds_after_all_quests_claimed(self):
        from core.daily_quests import claim_daily_bonus
        self._complete_all_quests()
        result = claim_daily_bonus()
        assert result["success"] is True

    def test_bonus_gives_50_xp(self):
        from core.daily_quests import claim_daily_bonus, DAILY_BONUS_XP
        self._complete_all_quests()
        result = claim_daily_bonus()
        assert result["reward_xp"] == DAILY_BONUS_XP

    def test_bonus_cannot_be_claimed_twice(self):
        from core.daily_quests import claim_daily_bonus
        self._complete_all_quests()
        claim_daily_bonus()
        result2 = claim_daily_bonus()
        assert result2["success"] is False


# ---------------------------------------------------------------------------
# get_daily_summary — qisqacha holat
# ---------------------------------------------------------------------------
class TestGetDailySummary:
    def test_returns_dict(self):
        from core.daily_quests import get_daily_summary
        assert isinstance(get_daily_summary(), dict)

    def test_has_required_keys(self):
        from core.daily_quests import get_daily_summary
        required = {"date", "total_count", "completed_count", "claimed_count",
                    "all_completed", "all_claimed", "bonus_claimed", "quests"}
        assert required.issubset(get_daily_summary().keys())

    def test_total_count_is_3(self):
        from core.daily_quests import get_daily_summary
        assert get_daily_summary()["total_count"] == 3

    def test_initially_no_completions(self):
        from core.daily_quests import get_daily_summary
        summary = get_daily_summary()
        assert summary["completed_count"] == 0
        assert summary["claimed_count"] == 0
        assert summary["all_completed"] is False
        assert summary["all_claimed"] is False
