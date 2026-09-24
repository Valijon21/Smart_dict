"""
Unit tests for services/topic_service.py.
Verifies thematic topics registry, progress calculations,
word details extraction, and batch topic imports into study queue.
"""
from services.topic_service import (
    get_all_topics,
    get_topic_by_id,
    get_all_topics_progress,
    get_topic_progress,
    get_topic_words_details,
    batch_add_topic_to_study,
)
import core.database as db


def test_get_all_topics_structure():
    """Topics registry contains essential vocabulary categories with valid schemas."""
    topics = get_all_topics()
    assert isinstance(topics, list)
    assert len(topics) >= 5

    required_keys = {"id", "title", "title_uz", "description", "emoji", "color", "words"}
    for topic in topics:
        missing = required_keys - set(topic.keys())
        assert not missing, f"Topic '{topic.get('id')}' missing keys: {missing}"
        assert len(topic["words"]) > 0


def test_get_topic_by_id_found():
    """Retrieves specific topic by unique ID."""
    all_topics = get_all_topics()
    target_id = all_topics[0]["id"]

    topic = get_topic_by_id(target_id)
    assert topic is not None
    assert topic["id"] == target_id
    assert "title" in topic
    assert "title_uz" in topic


def test_get_topic_by_id_not_found():
    """Returns None for non-existent topic ID."""
    assert get_topic_by_id("non_existent_topic_id_999") is None
    assert get_topic_by_id("") is None


def test_get_topic_progress_calculation():
    """Calculates learned words vs total words in a topic."""
    topics = get_all_topics()
    t0 = topics[0]
    total_in_topic = len(t0["words"])

    # When user has not learned any word
    learned, total = get_topic_progress(t0["id"], user_words_set=set())
    assert learned == 0
    assert total == total_in_topic

    # When user has learned some words from the topic
    some_words = set(list(t0["words"])[:3])
    learned2, total2 = get_topic_progress(t0["id"], user_words_set=some_words)
    assert learned2 == min(3, total_in_topic)
    assert total2 == total_in_topic


def test_get_topic_words_details():
    """Returns formatted list of word objects for UI presentation."""
    topics = get_all_topics()
    t0_id = topics[0]["id"]

    details = get_topic_words_details(t0_id)
    assert isinstance(details, list)
    assert len(details) > 0

    w0 = details[0]
    assert "english" in w0
    assert "uzbek" in w0


def test_batch_add_topic_to_study(tmp_path):
    """Imports an entire topic category into user study database."""
    test_db = tmp_path / "topic_test_vocab.db"
    orig_path = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()

    try:
        topics = get_all_topics()
        t0_id = topics[0]["id"]

        added, total = batch_add_topic_to_study(t0_id)
        assert added > 0
        assert total > 0

        # Adding same topic again should not crash and skips existing words
        added2, total2 = batch_add_topic_to_study(t0_id)
        assert added2 == 0
    finally:
        db.DB_PATH = orig_path
