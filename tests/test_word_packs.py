"""
Unit tests for core/word_packs.py.
Verifies curated pre-made word packs structure, integrity, schemas, and retrieval.
"""
from core.word_packs import get_all_packs, get_pack, WORD_PACKS


def test_get_all_packs_not_empty():
    """Word packs registry must not be empty and contains curated collections."""
    packs = get_all_packs()
    assert isinstance(packs, list)
    assert len(packs) > 0


def test_unique_pack_ids():
    """All pack IDs must be unique across the application."""
    packs = get_all_packs()
    ids = [p["id"] for p in packs]
    assert len(ids) == len(set(ids)), f"Duplicate pack IDs found: {ids}"


def test_word_pack_schema():
    """Every pack must contain all required UI and metadata fields."""
    required_keys = {"id", "title", "icon", "level", "badge_color", "description", "words"}
    packs = get_all_packs()

    for pack in packs:
        missing = required_keys - set(pack.keys())
        assert not missing, f"Pack '{pack.get('id')}' missing keys: {missing}"
        assert isinstance(pack["words"], list)
        assert len(pack["words"]) >= 5, f"Pack '{pack['id']}' has too few words ({len(pack['words'])})"


def test_all_pack_words_have_valid_data():
    """Every word inside each pack must have valid non-empty english, uzbek, and example."""
    packs = get_all_packs()

    for pack in packs:
        for item in pack["words"]:
            assert "english" in item and item["english"].strip(), f"Invalid english in pack {pack['id']}"
            assert "uzbek" in item and item["uzbek"].strip(), f"Invalid uzbek in pack {pack['id']}"
            assert "example" in item, f"Missing example in pack {pack['id']}"


def test_get_pack_existing():
    """get_pack returns the exact dictionary for valid IDs."""
    first_pack = WORD_PACKS[0]
    p_id = first_pack["id"]

    retrieved = get_pack(p_id)
    assert retrieved is not None
    assert retrieved["id"] == p_id
    assert retrieved["title"] == first_pack["title"]


def test_get_pack_non_existent():
    """get_pack returns None when requested ID does not exist."""
    assert get_pack("non_existent_pack_xyz_123") is None
    assert get_pack("") is None
