"""
tests/test_gamification.py
core/gamification.py uchun pytest smoke testlari.
Mavjud test_database.py dagi pattern: core.database.DB_PATH to'g'ridan-to'g'ri almashtiriladi.
"""
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import database as db
import core.database as _cdb


# ---------------------------------------------------------------------------
# Fixtures — test_database.py dagi pattern bilan bir xil
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def temp_db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("gami_db")
    test_db = tmp / "test_gamification.db"
    original_path = _cdb.DB_PATH
    _cdb.DB_PATH = test_db
    _cdb.init_db()
    yield test_db
    _cdb.DB_PATH = original_path


@pytest.fixture(autouse=True)
def clean_db(temp_db):
    """Har bir test oldidan DB tozalanadi."""
    original = _cdb.DB_PATH
    _cdb.DB_PATH = temp_db
    with _cdb.get_conn() as conn:
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM progress")
        conn.execute("DELETE FROM daily_stats")
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM achievements")
    # Standart settings qayta yuklanadi
    _cdb.init_db()
    yield
    _cdb.DB_PATH = original


# ---------------------------------------------------------------------------
# get_level_info — daraja hisoblash
# ---------------------------------------------------------------------------
class TestGetLevelInfo:
    def test_zero_xp_is_level_1(self):
        from core.gamification import get_level_info
        info = get_level_info(xp=0)
        assert info["level"] == 1

    def test_returns_required_keys(self):
        from core.gamification import get_level_info
        info = get_level_info(xp=0)
        required = {"level", "title", "badge", "color", "total_xp",
                    "xp_in_level", "xp_needed", "next_level_xp", "progress_percent"}
        assert required.issubset(info.keys())

    def test_higher_xp_higher_level(self):
        from core.gamification import get_level_info
        assert get_level_info(xp=10000)["level"] > get_level_info(xp=0)["level"]

    def test_progress_percent_between_0_and_100(self):
        from core.gamification import get_level_info
        for xp in (0, 50, 500, 5000):
            assert 0 <= get_level_info(xp=xp)["progress_percent"] <= 100

    def test_level_1_title_is_boshlovchi(self):
        from core.gamification import get_level_info
        assert get_level_info(xp=0)["title"] == "Boshlovchi"

    @pytest.mark.parametrize("xp", [0, 100, 500, 1000, 5000])
    def test_total_xp_matches_input(self, xp):
        from core.gamification import get_level_info
        assert get_level_info(xp=xp)["total_xp"] == xp

    def test_level_2_at_100xp(self):
        from core.gamification import get_level_info
        # Formula: level 1->2 = 1*1*50 + 1*50 = 100
        assert get_level_info(xp=100)["level"] == 2

    def test_level_1_at_99xp(self):
        from core.gamification import get_level_info
        assert get_level_info(xp=99)["level"] == 1


# ---------------------------------------------------------------------------
# award_xp — XP qo'shish
# ---------------------------------------------------------------------------
class TestAwardXp:
    def test_positive_amount_increases_xp(self):
        from core.gamification import award_xp
        new_total, _, _ = award_xp(100)
        assert new_total >= 100

    def test_zero_amount_no_level_up(self):
        from core.gamification import award_xp
        _, level_up, _ = award_xp(0)
        assert level_up is False

    def test_negative_amount_no_level_up(self):
        from core.gamification import award_xp
        _, level_up, _ = award_xp(-10)
        assert level_up is False

    def test_returns_tuple_of_three(self):
        from core.gamification import award_xp
        result = award_xp(50)
        assert len(result) == 3

    def test_level_up_flag_when_crossing_threshold(self):
        from core.gamification import award_xp
        # Level 1->2: 100 XP kerak. 100 bersamiz level_up True bo'lishi kerak
        _, level_up, _ = award_xp(100)
        assert level_up is True

    def test_level_title_is_nonempty_string(self):
        from core.gamification import award_xp
        _, _, title = award_xp(10)
        assert isinstance(title, str) and len(title) > 0


# ---------------------------------------------------------------------------
# record_practice_answer — mashq javobi yozish
# ---------------------------------------------------------------------------
class TestRecordPracticeAnswer:
    def test_correct_answer_gives_xp(self):
        from core.gamification import record_practice_answer
        result = record_practice_answer(is_correct=True, mode="multiple_choice", consecutive_correct=1)
        assert result["xp_gained"] > 0

    def test_wrong_answer_gives_no_xp(self):
        from core.gamification import record_practice_answer
        result = record_practice_answer(is_correct=False, mode="multiple_choice", consecutive_correct=0)
        assert result["xp_gained"] == 0

    def test_typing_mode_gives_more_xp_than_mc(self):
        from core.gamification import record_practice_answer
        r_typing = record_practice_answer(is_correct=True, mode="typing", consecutive_correct=1)
        r_mc = record_practice_answer(is_correct=True, mode="multiple_choice", consecutive_correct=1)
        assert r_typing["xp_gained"] >= r_mc["xp_gained"]

    def test_returns_required_keys(self):
        from core.gamification import record_practice_answer
        result = record_practice_answer(is_correct=True, mode="typing", consecutive_correct=1)
        required = {"xp_gained", "total_xp", "level_info", "level_up", "unlocked_achievements"}
        assert required.issubset(result.keys())

    def test_unlocked_achievements_is_list(self):
        from core.gamification import record_practice_answer
        result = record_practice_answer(is_correct=True, mode="typing", consecutive_correct=1)
        assert isinstance(result["unlocked_achievements"], list)

    def test_sniper_achievement_at_10_consecutive(self):
        from core.gamification import record_practice_answer, init_gamification
        init_gamification()  # Yutuqlarni DB ga yuklash
        result = record_practice_answer(is_correct=True, mode="typing", consecutive_correct=10)
        ach_ids = [a.get("id") for a in result["unlocked_achievements"]]
        assert "sniper_10" in ach_ids

    def test_sniper_not_unlocked_at_9_consecutive(self):
        from core.gamification import record_practice_answer, init_gamification
        init_gamification()
        result = record_practice_answer(is_correct=True, mode="typing", consecutive_correct=9)
        ach_ids = [a.get("id") for a in result["unlocked_achievements"]]
        assert "sniper_10" not in ach_ids


# ---------------------------------------------------------------------------
# check_global_achievements — global yutuqlar
# ---------------------------------------------------------------------------
class TestCheckGlobalAchievements:
    def test_returns_list(self):
        from core.gamification import check_global_achievements
        result = check_global_achievements()
        assert isinstance(result, list)

    def test_collector_100_not_unlocked_with_few_words(self):
        from core.gamification import check_global_achievements, init_gamification
        init_gamification()
        for i in range(5):
            db.add_word(f"word{i}", f"tarjima{i}")
        result = check_global_achievements()
        ach_ids = [a.get("id") for a in result]
        assert "collector_100" not in ach_ids
