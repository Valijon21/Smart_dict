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


def normalize_answer_token(text: str) -> str:
    """Apostroflar, ko'rinmas belgilar va ortiqcha bo'shliqlarni standartlashtirish."""
    if not text:
        return ""
    # Ko'rinmas zero-width belgilarni tozalash
    text = re.sub(r"[\u200b-\u200f\ufeff\u202a-\u202e\xa0]", "", text)
    # Barcha turdagi apostroflarni bitta standart ' ga keltirish
    text = re.sub(r"['‘’ʻʼ`´\?\ufffd]", "'", text)
    # Ortiqcha bo'shliqlarni bittaga keltirish
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def extract_answer_options(raw_text: str) -> list[str]:
    """
    Kiritilgan javob yoki kutilayotgan so'zdan barcha mumkin bo'lgan to'g'ri variantlarni ajratib olish.
    Qo'llab-quvvatlaydi:
    - Vergul va nuqta-vergul bilan ajratilgan sinonimlar: 'eslamoq, yodlamoq'
    - Slesh (/) bilan ajratilgan muqobillar: 'Seem / Appear', 'eslamoq / yodda tutmoq'
    - Qavs ichidagi izohlar: 'Think (have an opinion)' -> 'think', 'think (have an opinion)'
    - 'to' yuklamasi bilan boshlanuvchi fe'llar: 'to think' -> 'think'
    - Har xil turdagi apostroflarni birlashtirish
    """
    if not raw_text:
        return []

    cleaned_raw = re.sub(r"[\u200b-\u200f\ufeff\u202a-\u202e\xa0]", "", raw_text).strip()
    parts = [p.strip() for p in re.split(r"[,;]+", cleaned_raw) if p.strip()]
    all_options: set[str] = set()

    for part in parts:
        subparts = [sp.strip() for sp in part.split("/") if sp.strip()]
        norm_part = normalize_answer_token(part)
        if norm_part:
            all_options.add(norm_part)
            no_paren = re.sub(r"\(.*?\)", "", norm_part).strip()
            no_paren = re.sub(r"\s+", " ", no_paren)
            if no_paren:
                all_options.add(no_paren)
                if no_paren.startswith("to "):
                    all_options.add(no_paren[3:].strip())
            if norm_part.startswith("to "):
                all_options.add(norm_part[3:].strip())

        for sub in subparts:
            norm_sub = normalize_answer_token(sub)
            if norm_sub:
                all_options.add(norm_sub)
                no_paren_sub = re.sub(r"\(.*?\)", "", norm_sub).strip()
                no_paren_sub = re.sub(r"\s+", " ", no_paren_sub)
                if no_paren_sub:
                    all_options.add(no_paren_sub)
                    if no_paren_sub.startswith("to "):
                        all_options.add(no_paren_sub[3:].strip())
                if norm_sub.startswith("to "):
                    all_options.add(norm_sub[3:].strip())

    return [opt for opt in all_options if opt]


def check_user_answer(user_input: str, expected_text: str) -> bool:
    """Foydalanuvchi javobini barcha variantlar (sinonimlar, qavslar, apostroflar) bo'yicha tekshirish."""
    user_norm = normalize_answer_token(user_input)
    if not user_norm:
        return False

    valid_options = extract_answer_options(expected_text)
    if user_norm in valid_options:
        return True

    # Agar foydalanuvchi 'to think' deb yozgan bo'lsa, 'think' kutilgan bo'lsa
    if user_norm.startswith("to ") and user_norm[3:].strip() in valid_options:
        return True

    # Kutilgan variantlar ichida 'to ...' bo'lsa yoki apostrofsiz yozilgan bo'lsa
    user_no_apostrophe = user_norm.replace("'", "")
    for opt in valid_options:
        if opt.startswith("to ") and opt[3:].strip() == user_norm:
            return True
        if opt.replace("'", "") == user_no_apostrophe:
            return True

    return False


def get_best_match_target(user_input: str, expected_display: str) -> str:
    """Typo (visual diff) uchun kutilgan so'zning foydalanuvchi javobiga eng yaqin qismini topish."""
    import difflib
    options = extract_answer_options(expected_display)
    if not options:
        return expected_display
    u_norm = normalize_answer_token(user_input)
    # Eng yuqori o'xshashlikka ega bo'lgan variantni tanlash
    best = max(
        options,
        key=lambda opt: (difflib.SequenceMatcher(None, u_norm, opt).ratio(), -abs(len(opt) - len(u_norm)))
    )
    return best

