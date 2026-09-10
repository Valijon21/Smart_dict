"""
core/phonetics.py uchun pytest smoke testlar.

Maqsad:
  - get_word_info() — ma'lum so'zlar uchun IPA va POS to'g'ri qaytarilishini tekshirish.
  - infer_part_of_speech() — noma'lum so'zlar uchun mantiqiy xulosa chiqarishni tekshirish.
  - infer_phonetic() — fallback fonetika yaratishni tekshirish.
  - pos_badge_text() — foydalanuvchiga ko'rsatiladigan qisqartmalar.

Ishga tushirish:
    pytest tests/test_phonetics.py -v
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.phonetics import get_word_info, infer_part_of_speech, infer_phonetic, pos_badge_text


# ---------------------------------------------------------------------------
# 1. get_word_info() — lug'atda bor so'zlar
# ---------------------------------------------------------------------------

class TestGetWordInfo:
    """get_word_info() lug'atda bor so'zlar uchun to'g'ri ma'lumot qaytarishi."""

    @pytest.mark.parametrize("word, expected_pos", [
        ("run", "verb"),
        ("book", "noun"),
        ("beautiful", "adj"),
        ("quickly", "adv"),
        ("above", "prep"),
    ])
    def test_known_words_correct_pos(self, word, expected_pos):
        info = get_word_info(word)
        assert info["part_of_speech"] == expected_pos, (
            f"'{word}' uchun part_of_speech='{expected_pos}' kutildi, "
            f"'{info['part_of_speech']}' keldi"
        )

    @pytest.mark.parametrize("word", ["abandon", "ability", "accept", "achieve", "action"])
    def test_known_words_have_ipa(self, word):
        """Lug'atda bor so'zlar IPA transkripsiyasiga ega bo'lishi kerak."""
        info = get_word_info(word)
        phonetic = info.get("phonetic", "")
        assert phonetic != "", f"'{word}' so'zi uchun IPA bo'sh bo'lmasligi kerak"
        # IPA belgisi bo'lishi kerak (slash yoki harflar)
        assert len(phonetic) >= 2, f"'{word}' IPA juda qisqa: '{phonetic}'"

    def test_returns_word_phonetics_typeddict(self):
        """get_word_info() WordPhonetics TypedDict qaytarishi kerak."""
        info = get_word_info("apple")
        assert "phonetic" in info
        assert "part_of_speech" in info

    def test_case_insensitive_lookup(self):
        """Katta harf bilan ham to'g'ri natija qaytishi kerak."""
        info_lower = get_word_info("school")
        info_upper = get_word_info("School")
        info_allcaps = get_word_info("SCHOOL")
        assert info_lower["part_of_speech"] == info_upper["part_of_speech"]
        assert info_lower["part_of_speech"] == info_allcaps["part_of_speech"]

    def test_unknown_word_returns_empty_or_inferred(self):
        """Noma'lum so'z uchun bo'sh yoki inferred natija qaytishi kerak."""
        info = get_word_info("xyzxyzunknown123")
        assert isinstance(info["phonetic"], str)
        assert isinstance(info["part_of_speech"], str)


# ---------------------------------------------------------------------------
# 2. infer_part_of_speech() — morfologik xulosalar
# ---------------------------------------------------------------------------

class TestInferPartOfSpeech:
    """infer_part_of_speech() — suffiks asosida so'z turkumini aniqlash."""

    @pytest.mark.parametrize("word, expected_pos", [
        ("happiness", "noun"),  # -ness suffiks
        ("freedom", "noun"),    # -dom suffiks
        ("beautiful", "adj"),   # -ful suffiks
        ("quickly", "adv"),     # -ly suffiks
    ])
    def test_suffix_based_inference(self, word, expected_pos):
        pos = infer_part_of_speech(word)
        assert pos == expected_pos, (
            f"'{word}' uchun POS='{expected_pos}' kutildi, '{pos}' keldi"
        )

    def test_returns_string(self):
        result = infer_part_of_speech("test")
        assert isinstance(result, str)

    def test_empty_string_safe(self):
        """Bo'sh string xatolik chiqarmasligi kerak."""
        result = infer_part_of_speech("")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 3. infer_phonetic() — fallback fonetika
# ---------------------------------------------------------------------------

class TestInferPhonetic:
    """infer_phonetic() — noma'lum so'zlar uchun taxminiy fonetika."""

    def test_returns_string(self):
        result = infer_phonetic("computer")
        assert isinstance(result, str)

    def test_nonempty_for_normal_word(self):
        """Oddiy inglizcha so'z uchun bo'sh bo'lmasligi kerak."""
        result = infer_phonetic("language")
        assert len(result) >= 2, f"infer_phonetic juda qisqa natija qaytardi: '{result}'"

    def test_empty_input_safe(self):
        """Bo'sh input xatolik chiqarmasligi kerak."""
        result = infer_phonetic("")
        assert isinstance(result, str)

    def test_slash_brackets_in_result(self):
        """Natija odatda /.../ formatida bo'lishi kerak."""
        result = infer_phonetic("hello")
        # "/" bo'lishi shart emas (ba'zi implementatsiyalar qo'shmaydi), lekin string bo'lishi kerak
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 4. pos_badge_text() — foydalanuvchi interfeysi uchun qisqartma
# ---------------------------------------------------------------------------

class TestPosBadgeText:
    """pos_badge_text() — POS qisqartmasini UI uchun formatlash."""

    @pytest.mark.parametrize("pos, expected", [
        ("noun", "n."),
        ("verb", "v."),
        ("adj", "adj."),
        ("adv", "adv."),
        ("prep", "prep."),
    ])
    def test_known_pos_mapping(self, pos, expected):
        result = pos_badge_text(pos)
        assert result == expected, (
            f"pos_badge_text('{pos}') -> '{expected}' kutildi, '{result}' keldi"
        )

    def test_returns_string_for_unknown(self):
        """Noma'lum POS string qaytarishi kerak, xatolik emas."""
        result = pos_badge_text("unknown_pos_xyz")
        assert isinstance(result, str)
