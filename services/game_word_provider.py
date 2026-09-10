"""
Vocab Master Pro — Game Word Provider Service.
Barcha 4 ta o'yin (Word Match, Blitz, Word Fall, Crossword) uchun yagona so'z manbasi:
1. Shaxsiy lug'at (vocab.db)
2. 36 ta Tematik mavzular (services.topic_service)
3. Tayyor so'z to'plamlari (core.word_packs)
4. CEFR va IELTS darajalari (services.cefr_service)
"""
import random
import re
from typing import Any

try:
    from core import database as db
    from core import word_packs
    from services import topic_service
    from services import cefr_service
    from utils.logger import get_logger
except ImportError:
    import database as db
    import word_packs
    import topic_service
    import cefr_service
    from logger import get_logger

logger = get_logger("game_word_provider")

# Asosiy toifalar
CAT_PERSONAL = "personal"
CAT_TOPICS = "topics"
CAT_PACKS = "packs"
CAT_CEFR = "cefr"

CATEGORIES = [
    {"id": CAT_PERSONAL, "title": "📚 Shaxsiy Lug'at", "icon": "📚"},
    {"id": CAT_TOPICS, "title": "🏷️ 36 ta Mavzu", "icon": "🏷️"},
    {"id": CAT_PACKS, "title": "📦 Tayyor To'plamlar", "icon": "📦"},
    {"id": CAT_CEFR, "title": "🎯 CEFR & IELTS", "icon": "🎯"},
]

# Kesh xotirasi: (cat, source_id) -> list[dict]
_CACHE: dict[tuple[str, str], list[dict]] = {}


def get_available_categories() -> list[dict]:
    """Mavjud barcha asosiy toifalar ro'yxatini qaytaradi."""
    return CATEGORIES


def get_sources_for_category(category_id: str) -> list[dict]:
    """
    Muayyan toifaga tegishli barcha ichki to'plamlar ro'yxatini qaytaradi.
    Format: [{"id": ..., "title": ..., "count": ...}]
    """
    if category_id == CAT_PERSONAL:
        total_count = 0
        try:
            total_count = db.get_total_word_count()
        except Exception:
            pass
        due_count = 0
        try:
            due_count = db.get_due_count()
        except Exception:
            pass
        weak_count = 0
        try:
            weak_count = db.get_weak_words_count()
        except Exception:
            pass
        learning_count = 0
        try:
            learning_count = len(db.get_words_by_status("learning"))
        except Exception:
            pass
        return [
            {"id": "all", "title": f"📚 Barcha so'zlar ({total_count} ta)", "count": total_count},
            {"id": "due", "title": f"🧠 Bugun takrorlash kerak ({due_count} ta)", "count": due_count},
            {"id": "weak", "title": f"⚠️ Zaif / xato so'zlar ({weak_count} ta)", "count": weak_count},
            {"id": "learning", "title": f"🌱 O'rganilayotgan so'zlar ({learning_count} ta)", "count": learning_count},
        ]

    elif category_id == CAT_TOPICS:
        topics = topic_service.get_all_topics()
        results = []
        for t in topics:
            w_count = len(t.get("words", []))
            emoji = t.get("emoji", "🏷️")
            title_uz = t.get("title_uz", t.get("title", ""))
            results.append({
                "id": t["id"],
                "title": f"{emoji} {title_uz} ({w_count} ta)",
                "count": w_count
            })
        return results

    elif category_id == CAT_PACKS:
        packs = word_packs.get_all_packs()
        results = []
        for p in packs:
            w_count = len(p.get("words", []))
            icon = p.get("icon", "📦")
            results.append({
                "id": p["id"],
                "title": f"{icon} {p.get('title', '')} ({w_count} ta)",
                "count": w_count
            })
        return results

    elif category_id == CAT_CEFR:
        return [
            {"id": "cefr_a1_a2", "title": "🟢 A1 - A2 (Elementary / Boshlang'ich)", "count": 3000},
            {"id": "cefr_b1_b2", "title": "🔵 B1 - B2 (Intermediate / O'rta)", "count": 2500},
            {"id": "cefr_c1_c2", "title": "🟣 C1 - C2 (Advanced / Yuqori)", "count": 2000},
            {"id": "ielts_academic", "title": "🎓 IELTS Academic (AWL 570)", "count": 570},
        ]

    return []


def get_words_for_game(
    category_id: str,
    source_id: str,
    limit: int = 100,
    min_len: int = 0,
    max_len: int = 999,
    alpha_only: bool = False
) -> list[dict]:
    """
    O'yinlar uchun so'zlarni tozalangan va standartlashtirilgan ko'rinishda qaytaradi.
    Standart lug'at formati:
    {
        "id": int | str,
        "english": str,
        "uzbek": str,
        "phonetic": str,
        "part_of_speech": str
    }
    """
    cache_key = (category_id, source_id)
    raw_words: list[dict] = []

    if cache_key in _CACHE:
        raw_words = _CACHE[cache_key]
    else:
        raw_words = _load_source_words(category_id, source_id)
        if raw_words:
            _CACHE[cache_key] = raw_words

    # Agar tanlangan to'plam bo'sh bo'lsa, xavfsiz zaxira (fallback)
    if not raw_words:
        raw_words = _get_fallback_words()

    # O'yin filtrlari (Krossvord yoki boshqa cheklovlar uchun)
    filtered: list[dict] = []
    for w in raw_words:
        eng = w.get("english", "").strip()
        uz = w.get("uzbek", "").strip()
        if not eng or not uz:
            continue

        if min_len > 0 and len(eng) < min_len:
            continue
        if max_len < 999 and len(eng) > max_len:
            continue
        if alpha_only and not eng.isalpha():
            continue

        filtered.append(w)

    # Agar filtr juda qattiq bo'lib kam so'z qolsa (masalan krossvordda),
    # filtrni yumshatib birinchi mos keluvchilarni qo'shish
    if len(filtered) < 6 and alpha_only:
        for w in raw_words:
            eng = w.get("english", "").strip()
            clean_eng = eng.replace(" ", "")
            if 3 <= len(clean_eng) <= 8 and clean_eng.isalpha():
                filtered.append({
                    **w,
                    "english": clean_eng
                })
            if len(filtered) >= 15:
                break

    if limit > 0 and len(filtered) > limit:
        return filtered[:limit]
    return filtered


def get_words_for_source(category_id: str, source_id: str, limit: int = 0) -> list[dict]:
    """
    Audio Player, Podcast eksport yoki umumiy o'rganish uchun to'plamdagi so'zlarni
    barcha misol gaplari (example) va fonetikasi bilan to'liq qaytaradi.
    """
    cache_key = (category_id, source_id)
    if cache_key in _CACHE:
        raw_words = _CACHE[cache_key]
    else:
        raw_words = _load_source_words(category_id, source_id)
        if raw_words:
            _CACHE[cache_key] = raw_words

    if not raw_words:
        raw_words = _get_fallback_words()

    if limit > 0 and len(raw_words) > limit:
        return list(raw_words[:limit])
    return list(raw_words)


def _load_source_words(category_id: str, source_id: str) -> list[dict]:
    """Manba turiga qarab so'zlarni bazadan yoki xizmatdan yuklash."""
    results: list[dict] = []

    try:
        if category_id == CAT_PERSONAL:
            if source_id == "due":
                rows = db.get_due_words(limit=500)
                if not rows:
                    rows = db.get_all_words()
            elif source_id == "weak":
                rows = db.get_weakest_words(limit=100)
                if not rows:
                    rows = db.get_weak_words(limit=100)
                if not rows:
                    rows = db.get_all_words()
            elif source_id == "learning":
                rows = db.get_words_by_status("learning")
                if not rows:
                    rows = db.get_words_with_progress()
                if not rows:
                    rows = db.get_all_words()
            else:
                rows = db.get_all_words()

            for idx, r in enumerate(rows, 1):
                d = dict(r) if not isinstance(r, dict) else r
                results.append({
                    "id": d.get("id", idx),
                    "english": d.get("english", "").strip(),
                    "uzbek": d.get("uzbek", "").strip(),
                    "phonetic": d.get("phonetic", ""),
                    "part_of_speech": d.get("part_of_speech", "word"),
                    "example": d.get("example", "").strip(),
                })

        elif category_id == CAT_TOPICS:
            topic_details = topic_service.get_topic_words_details(source_id)
            for idx, item in enumerate(topic_details, 1):
                eng = item.get("english", "").strip()
                uz = item.get("uzbek", "").strip()
                if eng and uz:
                    results.append({
                        "id": f"topic_{source_id}_{idx}",
                        "english": eng,
                        "uzbek": uz,
                        "phonetic": item.get("phonetic", ""),
                        "part_of_speech": item.get("pos", "word"),
                        "example": item.get("example", "").strip(),
                    })

        elif category_id == CAT_PACKS:
            pack = word_packs.get_pack(source_id)
            if pack and "words" in pack:
                for idx, w in enumerate(pack["words"], 1):
                    results.append({
                        "id": f"pack_{source_id}_{idx}",
                        "english": w.get("english", "").strip(),
                        "uzbek": w.get("uzbek", "").strip(),
                        "phonetic": w.get("phonetic", ""),
                        "part_of_speech": "word",
                        "example": w.get("example", "").strip(),
                    })

        elif category_id == CAT_CEFR:
            cefr_words = cefr_service.get_words_for_level(source_id, limit=300)
            for idx, w in enumerate(cefr_words, 1):
                eng = w.get("english", "").strip()
                uz = w.get("uzbek", "").strip()
                if eng and uz:
                    results.append({
                        "id": f"cefr_{source_id}_{idx}",
                        "english": eng,
                        "uzbek": uz,
                        "phonetic": w.get("phonetic", ""),
                        "part_of_speech": w.get("pos", "word"),
                        "example": w.get("example", "").strip(),
                    })

    except Exception as e:
        logger.error(f"So'zlarni yuklashda xatolik ({category_id}, {source_id}): {e}", exc_info=True)

    return results


def _get_fallback_words() -> list[dict]:
    """Har qanday vaziyatda o'yin qotib qolmasligini ta'minlovchi zaxira so'zlar."""
    try:
        packs = word_packs.get_all_packs()
        if packs and "words" in packs[0]:
            return [
                {
                    "id": -idx,
                    "english": w["english"],
                    "uzbek": w["uzbek"],
                    "phonetic": "",
                    "part_of_speech": "word",
                }
                for idx, w in enumerate(packs[0]["words"][:50], 1)
            ]
    except Exception:
        pass

    return [
        {"id": -1, "english": "apple", "uzbek": "olma", "phonetic": "/ˈæp.əl/", "part_of_speech": "noun"},
        {"id": -2, "english": "book", "uzbek": "kitob", "phonetic": "/bʊk/", "part_of_speech": "noun"},
        {"id": -3, "english": "computer", "uzbek": "kompyuter", "phonetic": "/kəmˈpjuː.tər/", "part_of_speech": "noun"},
        {"id": -4, "english": "water", "uzbek": "suv", "phonetic": "/ˈwɔː.tər/", "part_of_speech": "noun"},
        {"id": -5, "english": "learn", "uzbek": "o'rganmoq", "phonetic": "/lɜːn/", "part_of_speech": "verb"},
        {"id": -6, "english": "friend", "uzbek": "do'st", "phonetic": "/frend/", "part_of_speech": "noun"},
        {"id": -7, "english": "family", "uzbek": "oila", "phonetic": "/ˈfæm.əl.i/", "part_of_speech": "noun"},
        {"id": -8, "english": "success", "uzbek": "muvaffaqiyat", "phonetic": "/səkˈses/", "part_of_speech": "noun"},
    ]


def clear_cache():
    """Keshni tozalash."""
    global _CACHE
    _CACHE.clear()
