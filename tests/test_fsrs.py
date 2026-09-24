"""
tests/test_fsrs.py
FSRS v5 (Free Spaced Repetition Scheduler) testi.
"""
import sys
import datetime
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.fsrs import FSRSv5, FSRSCard, Rating, CardState
import core.database as db


def test_fsrs_initial_ratings():
    scheduler = FSRSv5(desired_retention=0.90)
    card = FSRSCard()

    # Again
    c_again, iv_again = scheduler.review_card(card, Rating.AGAIN)
    assert c_again.state == CardState.LEARNING
    assert c_again.lapses == 1
    assert iv_again == 1

    # Good
    c_good, iv_good = scheduler.review_card(card, Rating.GOOD)
    assert c_good.state == CardState.REVIEW
    assert c_good.reps == 1
    assert c_good.stability > 1.0
    assert iv_good >= 2

    # Easy
    c_easy, iv_easy = scheduler.review_card(card, Rating.EASY)
    assert c_easy.stability > c_good.stability
    assert iv_easy > iv_good


def test_fsrs_memory_decay():
    scheduler = FSRSv5(desired_retention=0.90)
    now = datetime.datetime.now()
    card = FSRSCard(stability=10.0, state=CardState.REVIEW, last_review=now)

    # 0 kun o'tganda retention = 1.0 (100%)
    r0 = scheduler.get_retrievability(card, now)
    assert pytest.approx(r0, abs=0.01) == 1.0

    # S=10 kun o'tganda retention = 0.90 (90%)
    r_s = scheduler.get_retrievability(card, now + datetime.timedelta(days=10))
    assert pytest.approx(r_s, abs=0.02) == 0.90

    # 30 kun o'tganda retention ancha pasayadi (< 80%)
    r_30 = scheduler.get_retrievability(card, now + datetime.timedelta(days=30))
    assert r_30 < 0.80

    # 60 kun o'tganda retention 70% dan pastga tushadi
    r_60 = scheduler.get_retrievability(card, now + datetime.timedelta(days=60))
    assert r_60 < 0.70


def test_from_sm2_conversion():
    # Oddiy SM-2 yangi so'z
    c_new = FSRSv5.from_sm2(ease_factor=2.5, interval_days=0, repetitions=0)
    assert c_new.state == CardState.NEW

    # O'rganilgan SM-2 so'z (iv=10 kun, ef=2.5)
    c_learned = FSRSv5.from_sm2(ease_factor=2.5, interval_days=10, repetitions=3, wrong_count=1)
    assert c_learned.state == CardState.REVIEW
    assert c_learned.stability >= 9.0
    assert c_learned.reps == 3
    assert c_learned.lapses == 1


@pytest.fixture
def temp_db(tmp_path):
    test_db = tmp_path / "fsrs_test.db"
    orig_path = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()
    yield test_db
    db.DB_PATH = orig_path


def test_fsrs_database_integration(temp_db):
    w_id = db.add_word("ubiquitous", "hamma joyda mavjud", example="Smartphones are ubiquitous.")
    assert w_id is not None

    # Ilk takrorlash: GOOD
    res1 = db.record_fsrs_review(w_id, rating=Rating.GOOD)
    assert res1["fsrs_reps"] == 1
    assert res1["fsrs_stability"] > 0
    assert res1["interval_days"] >= 1
    assert res1["status"] in ("learning", "mastered")

    # get_fsrs_card tekshirish
    card = db.get_fsrs_card(w_id)
    assert card is not None
    assert card.reps == 1
    assert card.stability > 0

    # SM-2 orqali takrorlash (EASY)
    res2 = db.record_sm2_review(w_id, quality=5)
    assert res2["fsrs_reps"] == 2
    assert res2["fsrs_stability"] > res1["fsrs_stability"]

    # FSRS statistikasini tekshirish
    stats = db.get_fsrs_stats()
    assert stats["total_learned"] >= 1
    assert stats["avg_retention_pct"] > 50.0
