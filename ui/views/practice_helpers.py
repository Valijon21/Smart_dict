"""
Vocab Master Pro — Practice View Helper Utilities.
Mashq trenajyori uchun yordamchi lingvistik analizatorlar va data generatorlar:
- Bo'sh joyni to'ldirish (Cloze Test) uchun gaplarni formatlash va maskalash
- Harf terish (Word Scramble) uchun harflarni aralashtirish
"""
import re
import random
from typing import TypedDict


class ClozeData(TypedDict):
    sentence_masked: str
    original_sentence: str
    target_token: str
    correct_tokens: list[str]
    uzbek_hint: str


def prepare_cloze_data(word_data: dict, global_example_fetcher=None) -> ClozeData | None:
    """Hozirgi so'z uchun misol gapni topish va bo'sh joy qilib formatlash."""
    if not word_data:
        return None

    eng = word_data.get("english", "").strip()
    uz = word_data.get("uzbek", "").strip()
    ex = word_data.get("example", "") or ""
    ex = ex.strip()

    # Agar misol gap bo'lmasa yoki juda qisqa bo'lsa, global qidiruvdan foydalanish
    if (not ex or len(ex) < 10) and global_example_fetcher:
        try:
            cand = global_example_fetcher(eng)
            if cand and len(cand) >= 10:
                ex = cand
        except Exception:
            pass

    # Agar hali ham misol bo'lmasa, kontekstli standart shablon yaratamiz
    if not ex or len(ex) < 8:
        ex = f"It is very important to learn how to use '{eng}' in your daily English sentences."

    clean_eng = re.escape(eng)
    stem = clean_eng
    if len(eng) > 4 and eng.endswith("e"):
        stem = re.escape(eng[:-1])
    elif len(eng) > 4 and eng.endswith("y"):
        stem = re.escape(eng[:-1])

    pattern = re.compile(rf"\b({clean_eng}\w*|{stem}\w*)\b", re.IGNORECASE)
    match = pattern.search(ex)

    blank_html = (
        "<span style='color: #38BDF8; font-weight: 800; background-color: rgba(56, 189, 248, 0.15); "
        "border-radius: 6px; padding: 2px 12px; border-bottom: 2px solid #38BDF8;'>&nbsp;[ &nbsp;______&nbsp; ]&nbsp;</span>"
    )

    if match:
        found_token = match.group(1)
        start, end = match.span(1)
        before = ex[:start]
        after = ex[end:]
        masked_sentence = f"{before}{blank_html}{after}"
        correct_tokens = [found_token.lower(), eng.lower()]
    else:
        found_token = eng
        masked_sentence = f"In English, the word {blank_html} translates to '{uz}'."
        correct_tokens = [eng.lower()]

    for alt in eng.split(","):
        alt_clean = alt.strip().lower()
        if alt_clean:
            correct_tokens.append(alt_clean)

    uz_first = uz.split(",")[0].strip()

    return {
        "sentence_masked": masked_sentence,
        "original_sentence": ex,
        "target_token": found_token,
        "correct_tokens": list(dict.fromkeys(correct_tokens)),
        "uzbek_hint": uz_first,
    }


def prepare_scramble_chars(word: str) -> list[str]:
    """Inglizcha so'z harflarini aralashtirib berish (Word Scramble)."""
    target = word.strip().lower()
    scrambled = [c for c in target if not c.isspace()]
    random.shuffle(scrambled)
    # Agar tasodifan asl so'z bilan bir xil bo'lib qolsa, teskari o'girish
    if "".join(scrambled) == target.replace(" ", "") and len(scrambled) > 2:
        scrambled.reverse()
    return scrambled
