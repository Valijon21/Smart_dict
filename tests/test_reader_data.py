"""
Unit tests for utils/reader_data.py.
Verifies smart reader stories database, schema consistency,
content length, paragraphs formatting, and unique identifiers.
"""
from utils.reader_data import CURATED_STORIES


def test_curated_stories_not_empty():
    """Curated reader stories collection must contain reading material."""
    assert isinstance(CURATED_STORIES, list)
    assert len(CURATED_STORIES) >= 4


def test_curated_stories_unique_ids():
    """Every story must have a distinct, non-empty identifier."""
    ids = [s["id"] for s in CURATED_STORIES]
    assert len(ids) == len(set(ids)), f"Duplicate story IDs found: {ids}"


def test_curated_stories_schema():
    """Each story entry must have all required UI fields and valid levels."""
    required_keys = {"id", "title", "level", "description", "content"}
    valid_levels = {"A1", "A2", "B1", "B2", "C1", "C2"}

    for story in CURATED_STORIES:
        missing = required_keys - set(story.keys())
        assert not missing, f"Story '{story.get('id')}' missing keys: {missing}"

        # Level should mention a CEFR code
        level_str = story["level"]
        assert any(lvl in level_str for lvl in valid_levels), f"Invalid level format: {level_str}"


def test_curated_stories_content_structure():
    """Stories must have meaningful content divided into readable paragraphs."""
    for story in CURATED_STORIES:
        content = story["content"].strip()
        assert len(content) >= 150, f"Story '{story['id']}' content too short ({len(content)} chars)"

        # Check for paragraph breaks (\n\n)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        assert len(paragraphs) >= 2, f"Story '{story['id']}' should have at least 2 paragraphs"
