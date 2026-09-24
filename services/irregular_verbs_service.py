"""
services/irregular_verbs_service.py
Noto'g'ri fe'llar (Irregular Verbs) uchun xizmat qatlami:
- Filtrlash va qidiruv
- TTS audio talaffuz boshqaruvi
- Mashqlar generatsiyasi (Quiz, Typing, Flashcards)
- O'yinlar generatsiyasi (Match, Letter Scramble)
"""
import random
import re
from typing import List, Dict, Optional, Tuple

import core.database as db
from services.tts_service import speak, clean_english_for_tts
from utils.logger import get_logger

logger = get_logger("irregular_verbs_service")


def clean_verb_for_tts(text: str) -> str:
    """Fe'l shaklini TTS uchun tozalash: 'be(am,is,are)' -> 'be', 'was/were' -> 'was or were'."""
    if not text:
        return ""
    t = str(text).strip()
    # Qavsni olib tashlash
    t = re.sub(r"\(.*?\)", "", t).strip()
    # Slashing
    t = t.replace("/", " or ")
    return t


def speak_verb_form(form_text: str):
    """Bitta shaklni audio talaffuz qilish."""
    cleaned = clean_verb_for_tts(form_text)
    if cleaned:
        speak(cleaned)


def speak_all_forms(v1: str, v2: str, v3: str):
    """Fe'lning barcha 3 ta shaklini ketma-ket talaffuz qilish (masalan: 'break, broke, broken')."""
    c1 = clean_verb_for_tts(v1)
    c2 = clean_verb_for_tts(v2)
    c3 = clean_verb_for_tts(v3)
    phrase = f"{c1}, ... {c2}, ... {c3}"
    speak(phrase)


class IrregularVerbsService:
    """Noto'g'ri fe'llar bilan ishlash bo'yicha asosiy xizmat sinfi."""

    @staticmethod
    def get_verbs(search: str = "", filter_mode: str = "all", limit: int = 500, offset: int = 0) -> List[Dict]:
        stats = db.get_irregular_verbs_stats()
        if stats.get("total", 0) < 50:
            with db.get_conn() as conn:
                conn.execute("DELETE FROM irregular_verbs")
                db.seed_irregular_verbs_from_json(conn)
        return db.get_irregular_verbs(search=search, filter_mode=filter_mode, limit=limit, offset=offset)

    @staticmethod
    def get_stats() -> Dict:
        st = db.get_irregular_verbs_stats()
        if st.get("total", 0) < 50:
            with db.get_conn() as conn:
                conn.execute("DELETE FROM irregular_verbs")
                db.seed_irregular_verbs_from_json(conn)
            st = db.get_irregular_verbs_stats()
        return st

    @staticmethod
    def toggle_favorite(verb_id: int) -> bool:
        return db.toggle_irregular_verb_favorite(verb_id)

    @staticmethod
    def toggle_learned(verb_id: int) -> bool:
        return db.toggle_irregular_verb_learned(verb_id)

    @staticmethod
    def add_verb(v1: str, v2: str, v3: str, translation: str) -> int:
        return db.add_irregular_verb(v1, v2, v3, translation)

    @staticmethod
    def update_verb(verb_id: int, v1: str, v2: str, v3: str, translation: str) -> bool:
        return db.update_irregular_verb(verb_id, v1, v2, v3, translation)

    @staticmethod
    def delete_verb(verb_id: int) -> bool:
        return db.delete_irregular_verb(verb_id)

    @staticmethod
    def record_practice(verb_id: int, is_correct: bool):
        db.record_irregular_verb_practice(verb_id, is_correct)

    # -------------------------------------------------------------
    # 🎯 MASHQLAR GENERATSIYASI
    # -------------------------------------------------------------

    @staticmethod
    def generate_quiz_question(filter_mode: str = "all") -> Optional[Dict]:
        """
        3-shakl viktorinasi (Quiz):
        V1 va tarjima beriladi. Foydalanuvchi to'g'ri (V2, V3) kombinatsiyasini 4 ta variantdan topadi.
        """
        all_verbs = db.get_all_irregular_verbs_for_practice(filter_mode=filter_mode)
        if len(all_verbs) < 4:
            all_verbs = db.get_all_irregular_verbs_for_practice(filter_mode="all")
        if len(all_verbs) < 4:
            return None

        target = random.choice(all_verbs)
        correct_answer = f"{target['v2']} / {target['v3']}"

        # 3 ta noto'g'ri (distractor) variant tanlash
        others = [v for v in all_verbs if v["id"] != target["id"]]
        random.shuffle(others)
        distractors = others[:3]

        options = [correct_answer]
        for d in distractors:
            # Haqiqiy boshqa fe'lning shakli yoki o'zgartirilgan shakl
            fake = f"{d['v2']} / {d['v3']}"
            if fake not in options:
                options.append(fake)

        # Agar variantlar 4 tadan kam bo'lsa, sintetik variantlar hosil qilish
        while len(options) < 4:
            fake_v2 = target["v1"] + "ed"
            fake_v3 = target["v1"] + "en"
            synth = f"{fake_v2} / {fake_v3}"
            if synth not in options:
                options.append(synth)
            else:
                options.append(f"{target['v2']}ed / {target['v3']}")

        random.shuffle(options)
        return {
            "target": target,
            "question_v1": target["v1"],
            "translation": target["translation"],
            "correct_answer": correct_answer,
            "options": options[:4],
        }

    @staticmethod
    def generate_typing_question(filter_mode: str = "all") -> Optional[Dict]:
        """
        Yozma sinov:
        V1 va tarjima beriladi, foydalanuvchi V2 va V3 ni klaviaturada yozadi.
        """
        all_verbs = db.get_all_irregular_verbs_for_practice(filter_mode=filter_mode)
        if not all_verbs:
            all_verbs = db.get_all_irregular_verbs_for_practice(filter_mode="all")
        if not all_verbs:
            return None

        target = random.choice(all_verbs)
        return {
            "target": target,
            "v1": target["v1"],
            "v2": target["v2"],
            "v3": target["v3"],
            "translation": target["translation"],
        }

    @staticmethod
    def check_typing_answer(user_v2: str, user_v3: str, correct_v2: str, correct_v3: str) -> Tuple[bool, bool]:
        """Yozma javoblarni tekshirish (katta/kichik harflar va bo'sh joylarni hisobga olmasdan)."""
        def norm(val: str) -> str:
            val = val.lower().strip()
            # qavs va slashlarni yagona standartga keltirish
            val = re.sub(r"\s+", "", val)
            return val

        # Agar variantlar slash bilan berilgan bo'lsa (masalan was/were)
        v2_clean = norm(user_v2)
        v3_clean = norm(user_v3)
        corr_v2_clean = norm(correct_v2)
        corr_v3_clean = norm(correct_v3)

        # was/were kabi ko'p variantlilarda birortasini yozsa ham qabul qilish
        v2_opts = [norm(p) for p in correct_v2.split("/")] if "/" in correct_v2 else [corr_v2_clean]
        v3_opts = [norm(p) for p in correct_v3.split("/")] if "/" in correct_v3 else [corr_v3_clean]

        v2_ok = (v2_clean in v2_opts) or (v2_clean == corr_v2_clean)
        v3_ok = (v3_clean in v3_opts) or (v3_clean == corr_v3_clean)

        return v2_ok, v3_ok

    # -------------------------------------------------------------
    # 🎮 O'YINLAR GENERATSIYASI
    # -------------------------------------------------------------

    @staticmethod
    def generate_match_game(pair_count: int = 6) -> List[Dict]:
        """
        Juftlash o'yini (Match Game):
        6 ta fe'l olinadi. Har biri uchun:
          - Kartochka A: V1 (Infinitive)
          - Kartochka B: V2 + V3 va Tarjima
        Jami 12 ta aralashtirilgan kartochka qaytariladi.
        """
        all_verbs = db.get_all_irregular_verbs_for_practice(filter_mode="all")
        if len(all_verbs) < pair_count:
            pair_count = max(2, len(all_verbs))
        selected = random.sample(all_verbs, pair_count)

        cards = []
        for v in selected:
            verb_id = v["id"]
            # A tomon: V1
            cards.append({
                "card_id": f"{verb_id}_v1",
                "pair_id": verb_id,
                "text": v["v1"],
                "subtext": "Infinitive (V1)",
                "type": "v1",
                "raw_verb": v,
            })
            # B tomon: V2 / V3 + Tarjima
            cards.append({
                "card_id": f"{verb_id}_forms",
                "pair_id": verb_id,
                "text": f"{v['v2']} / {v['v3']}",
                "subtext": v["translation"],
                "type": "forms",
                "raw_verb": v,
            })

        random.shuffle(cards)
        return cards

    @staticmethod
    def generate_scramble_game() -> Optional[Dict]:
        """
        Harflardan yig'ish (Letter Scramble):
        Bitta fe'l tanlanadi, uning V2 yoki V3 shakli harflarga bo'linib aralashtiriladi.
        """
        all_verbs = db.get_all_irregular_verbs_for_practice(filter_mode="all")
        if not all_verbs:
            return None

        # Faqat toza harflardan iborat shakllarni tanlash (slash yoki qavssiz)
        suitable = []
        for v in all_verbs:
            for form_key, form_label in [("v2", "Past Simple (V2)"), ("v3", "Past Participle (V3)")]:
                word = v[form_key].strip().lower()
                if word.isalpha() and 3 <= len(word) <= 10:
                    suitable.append((v, form_key, form_label, word))

        if not suitable:
            return None

        v, form_key, form_label, target_word = random.choice(suitable)
        letters = list(target_word)
        shuffled = letters.copy()

        # Bir xil bo'lib qolmasligi uchun tekshirish
        for _ in range(10):
            random.shuffle(shuffled)
            if "".join(shuffled) != target_word:
                break

        return {
            "verb": v,
            "target_word": target_word,
            "form_label": form_label,
            "v1": v["v1"],
            "translation": v["translation"],
            "letters": shuffled,
        }
