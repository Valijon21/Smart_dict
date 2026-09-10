"""
Vocab Master Pro — Global 64,000 Offline Dictionary Service.
Longman / Oxford standartidagi 64,000 so'zlik ulkan akademik inglizcha-o'zbekcha
lug'at bazasi (db.sqlite3) bilan tezkor, xavfsiz va aqlli ishlash xizmati.

Imkoniyatlari:
- 64,000 ta so'zdan 1-5 millisekundlik tezkor qidiruv (Prefix + Substring)
- Barcha o'zbekcha tarjimalar, misollar, kollokatsiyalar, farqlar va sinonimlarni olish
- 1-bosishda foydalanuvchining shaxsiy o'rganish rejasiga (vocab.db) import qilish
"""
import sys
import re
import html
import sqlite3
from pathlib import Path
from typing import Any

try:
    from core import database as db
    from core import phonetics
    from utils.logger import get_logger, get_app_dir
    from utils import text_search_utils
except ImportError:
    import database as db
    import phonetics
    from logger import get_logger, get_app_dir
    import text_search_utils

logger = get_logger("global_dict_service")

def _find_global_db_path() -> Path:
    app_db = get_app_dir() / "db.sqlite3"
    if app_db.exists():
        return app_db
    import sys
    if hasattr(sys, "_MEIPASS"):
        mei_db = Path(sys._MEIPASS) / "db.sqlite3"
        if mei_db.exists():
            return mei_db
    root_db = Path(__file__).resolve().parent.parent / "db.sqlite3"
    if root_db.exists():
        return root_db
    return app_db

DB_PATH = _find_global_db_path()


def get_db_connection() -> sqlite3.Connection | None:
    """db.sqlite3 fayliga ulanish hosil qilish."""
    if not DB_PATH.exists():
        logger.warning(f"Global lug'at bazasi topilmadi: {DB_PATH}")
        return None
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Global lug'atga ulanishda xatolik: {e}")
        return None


def clean_html(raw_html: str | None) -> str:
    """HTML teglar va maxsus belgilarni toza matnga aylantirish."""
    if not raw_html:
        return ""
    s = html.unescape(raw_html)
    s = s.replace("&nbsp;", " ").replace("<br>", "\n").replace("<br/>", "\n").replace("</p>", "\n")
    s = re.sub(r"<[^>]+>", "", s)
    lines = [line.strip() for line in s.split("\n") if line.strip()]
    return "\n".join(lines)


def clean_examples(raw_text: str | None) -> list[str]:
    """Misol gaplarni qatorlarga ajratib tozalash."""
    if not raw_text:
        return []
    cleaned = clean_html(raw_text)
    items = []
    for line in cleaned.split("\n"):
        line = line.strip()
        if line.startswith("•") or line.startswith("-") or line.startswith("*"):
            line = line.lstrip("•-* ").strip()
        if line and len(line) > 3:
            items.append(line)
    return items


def search_global_words(query: str, limit: int = 25) -> list[dict]:
    """
    64,000 so'zlik akademik lug'atdan tezkor va aqlli ikki tomonlama qidiruv (Inglizcha ↔ O'zbekcha).
    Aniq moslik (Rank 0), so'z birikmalari (Rank 1), so'z boshi (Rank 2) va qism mosliklarini
    mukammal tartibda saralaydi.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    conn = get_db_connection()
    if not conn:
        return []

    results: list[dict] = []

    try:
        cursor = conn.cursor()
        sp = text_search_utils.get_search_patterns(clean_q)
        q_norm = sp["clean"]
        exact_vars = sp["exact_variants"]
        prefix_vars = sp["prefix_patterns"]

        where_clauses = ["we.word LIKE ? || '%'"]
        where_params = [q_norm]

        for p in prefix_vars:
            where_clauses.append("wz.word LIKE ? || '%'")
            where_params.append(p)
            where_clauses.append("wz.word LIKE '%, ' || ? || '%'")
            where_params.append(p)

        if len(q_norm) >= 3:
            where_clauses.append("we.word LIKE '%' || ? || '%'")
            where_params.append(q_norm)
            for p in prefix_vars:
                where_clauses.append("wz.word LIKE '%' || ? || '%'")
                where_params.append(p)

        # Ko'p bosqichli professional ranking:
        # Rank 0: Aniq moslik (Exact English yoki Exact Uzbek)
        case_parts = ["WHEN LOWER(we.word) = ? THEN 0"]
        case_params = [q_norm]
        for v in exact_vars:
            case_parts.append("WHEN LOWER(wz.word) = ? THEN 0")
            case_params.append(v)

        # Rank 1: Tarjima bo'laklarida aniq moslik (masalan: "kitob, darslik" -> "kitob")
        for v in exact_vars:
            case_parts.append("WHEN wz.word LIKE ? || ', %' OR wz.word LIKE '%, ' || ? || ', %' OR wz.word LIKE '%, ' || ? THEN 1")
            case_params.extend([v, v, v])

        # Rank 2: Boshlanish mosligi (Prefix)
        case_parts.append("WHEN we.word LIKE ? || '%' THEN 2")
        case_params.append(q_norm)
        for p in prefix_vars:
            case_parts.append("WHEN wz.word LIKE ? || '%' THEN 2")
            case_params.append(p)

        # Rank 3: So'z chegarasi mosligi
        for p in prefix_vars:
            case_parts.append("WHEN wz.word LIKE '%, ' || ? || '%' OR wz.word LIKE '% ' || ? || '%' THEN 3")
            case_params.extend([p, p])

        sql = f"""
            SELECT 
                we.id, 
                we.word, 
                we.word_classword_class AS pos,
                we.star,
                we.example,
                GROUP_CONCAT(wz.word, ', ') AS uzbek,
                CASE {" ".join(case_parts)} ELSE 4 END as match_rank,
                LENGTH(we.word) as word_len
            FROM word_entity we
            LEFT JOIN words_uz wz ON we.id = wz.word_id
            WHERE {" OR ".join(where_clauses)}
            GROUP BY we.id
            ORDER BY 
                match_rank ASC,
                we.star DESC,
                word_len ASC
            LIMIT ?
        """
        all_params = case_params + where_params + [limit]
        cursor.execute(sql, tuple(all_params))

        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "english": row["word"],
                "pos": row["pos"] or "",
                "star": str(row["star"] or "0"),
                "uzbek": row["uzbek"] or "",
                "example": clean_html(row["example"]),
                "source": "global",
                "match_rank": row["match_rank"],
            })

    except Exception as e:
        logger.error(f"Global qidiruvda xatolik: {e}")
    finally:
        conn.close()

    # Foydalanuvchining shaxsiy bazasida (vocab.db) mavjudligini belgilash (Batch 1 ta so'rov)
    if results:
        eng_list = [r["english"] for r in results]
        local_map = db.get_words_by_english_batch(eng_list) if hasattr(db, "get_words_by_english_batch") else {}
        for r in results:
            eng_lower = r["english"].strip().lower()
            local_word = local_map.get(eng_lower)
            r["is_in_study_list"] = local_word is not None
            if local_word:
                r["local_id"] = local_word["id"]

    return results


def get_word_full_details(word_id: int | None = None, english: str | None = None) -> dict | None:
    """
    So'z haqida to'liq ensiklopedik ma'lumotlarni qaytaradi:
    - O'zbekcha tarjimalari
    - Barcha misol gaplari
    - Turg'un birikmalari (Collocations)
    - So'zlar farqi (Differences, masalan: abandon or desert?)
    - Sinonimlar tahlili (Thesaurus)
    - Iboralar (Phrases)
    - Grammatika (Grammar)
    """
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        if word_id:
            cursor.execute("SELECT * FROM word_entity WHERE id = ?", (word_id,))
        elif english:
            cursor.execute("SELECT * FROM word_entity WHERE LOWER(word) = LOWER(?) LIMIT 1", (english.strip(),))
        else:
            return None

        we_row = cursor.fetchone()
        if not we_row:
            return None

        w_id = we_row["id"]
        eng_word = we_row["word"]

        # 1. O'zbekcha tarjimalar
        cursor.execute("SELECT word FROM words_uz WHERE word_id = ?", (w_id,))
        uzbek_list = [r["word"].strip() for r in cursor.fetchall() if r["word"]]

        # 2. Misollar
        examples = []
        if we_row["example"]:
            examples.extend(clean_examples(we_row["example"]))
        if we_row["examples"]:
            examples.extend(clean_examples(we_row["examples"]))
        if we_row["more_examples"]:
            examples.extend(clean_examples(we_row["more_examples"]))

        # 3. Turg'un birikmalar (Collocations)
        cursor.execute("SELECT body FROM collocation WHERE word_id = ?", (w_id,))
        collocations = [clean_html(r["body"]) for r in cursor.fetchall() if r["body"]]

        # 4. So'zlar farqi (Difference)
        cursor.execute("SELECT word, body FROM difference WHERE word_id = ?", (w_id,))
        differences = [
            {"title": r["word"], "body": clean_html(r["body"])}
            for r in cursor.fetchall() if r["body"]
        ]

        # 5. Tezaurus va sinonimlar (Thesaurus)
        cursor.execute("SELECT body FROM thesaurus WHERE word_id = ?", (w_id,))
        thesaurus = [clean_html(r["body"]) for r in cursor.fetchall() if r["body"]]

        # 6. Grammatika eslatmalari
        cursor.execute("SELECT body FROM grammar WHERE word_id = ?", (w_id,))
        grammar_notes = [clean_html(r["body"]) for r in cursor.fetchall() if r["body"]]

        # 7. Iboralar (Phrases)
        cursor.execute(
            """
            SELECT p.p_word, GROUP_CONCAT(pt.word, ', ') AS tr
            FROM phrases p
            LEFT JOIN phrases_translate pt ON p.p_id = pt.phrase_id
            WHERE p.p_word_id = ?
            GROUP BY p.p_id
            LIMIT 10
            """,
            (w_id,)
        )
        phrases = [
            {"phrase": r["p_word"], "translation": clean_html(r["tr"]) if r["tr"] else ""}
            for r in cursor.fetchall()
        ]

        local_word = db.get_word_by_english(eng_word)
        ph_info = phonetics.get_word_info(eng_word) if hasattr(phonetics, "get_word_info") else {"phonetic": "", "part_of_speech": ""}
        phonetic_val = ph_info.get("phonetic", "")
        pos_val = (we_row["word_classword_class"] or "") or ph_info.get("part_of_speech", "")

        return {
            "id": w_id,
            "english": eng_word,
            "phonetic": phonetic_val,
            "pos": pos_val,
            "star": we_row["star"] or "0",
            "uzbek_translations": uzbek_list,
            "uzbek_str": ", ".join(uzbek_list),
            "examples": examples,
            "collocations": collocations,
            "differences": differences,
            "thesaurus": thesaurus,
            "grammar_notes": grammar_notes,
            "phrases": phrases,
            "is_in_study_list": local_word is not None,
            "local_word": dict(local_word) if local_word else None,
        }

    except Exception as e:
        logger.error(f"So'z to'liq ma'lumotlarini olishda xatolik: {e}")
        return None
    finally:
        conn.close()


def add_to_study_list(english: str, uzbek: str = None, example: str = None) -> tuple[bool, str, int]:
    """
    Global lug'atdagi so'zni foydalanuvchining shaxsiy o'rganish bazasiga (vocab.db) qo'shish.
    Qaytaradi: (success: bool, message: str, word_id: int)
    """
    eng = english.strip()
    if not eng:
        return False, "So'z kiritilmagan", -1

    # Agar so'z allaqachon mavjud bo'lsa
    existing = db.get_word_by_english(eng)
    if existing:
        return False, f"'{eng}' allaqachon shaxsiy o'rganish ro'yxatingizda mavjud!", existing["id"]

    # Agar uzbek yoki example berilmagan bo'lsa, db.sqlite3 dan to'liq tortib olamiz
    if not uzbek or not example:
        details = get_word_full_details(english=eng)
        if details:
            if not uzbek:
                uzbek = details["uzbek_str"]
            if not example and details["examples"]:
                example = details["examples"][0]

    if not uzbek:
        uzbek = "Tarjimasi belgilanmagan"

    try:
        new_id = db.add_word(english=eng, uzbek=uzbek, example=example or "", source="global_dict")
        logger.info(f"Global lug'atdan shaxsiy bazaga qo'shildi: '{eng}' (ID: {new_id})")
        return True, f"'{eng}' shaxsiy o'rganish ro'yxatingizga muvaffaqiyatli qo'shildi!", new_id
    except Exception as e:
        logger.error(f"Shaxsiy ro'yxatga qo'shishda xatolik: {e}")
        return False, str(e), -1


def get_uzbek_search_patterns(q: str) -> list[str]:
    """
    O'zbekcha so'zlar uchun tutuq belgili va belgilisiz barcha variantlarni hosil qilish.
    (Backward-compatible wrapper for text_search_utils).
    """
    sp = text_search_utils.get_search_patterns(q)
    return sp["exact_variants"] + sp["prefix_patterns"]


def search_universal_words(query: str, limit: int = 20) -> list[dict]:
    """
    100% aniqlikdagi universal ikki tomonlama qidiruv (Inglizcha ↔ O'zbekcha).
    Ham shaxsiy bazadan (vocab.db), ham 64,000 so'zlik akademik lug'atdan (db.sqlite3)
    eng mos natijalarni mukammal saralab qaytaradi.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    local_rows = db.search_words(query=clean_q, limit=limit)
    global_rows = search_global_words(query=clean_q, limit=limit)

    results_map: dict[str, dict] = {}

    for r in local_rows:
        eng = r["english"]
        eng_lower = eng.lower().strip()
        uz = r["uzbek"] or ""
        ph_info = phonetics.get_word_info(eng)
        m_rank = text_search_utils.calculate_match_rank(clean_q, eng, uz)
        results_map[eng_lower] = {
            "id": r["id"],
            "english": eng,
            "pos": r["part_of_speech"] or ph_info["part_of_speech"],
            "star": "0",
            "uzbek": uz,
            "example": r["example"] or "",
            "phonetic": r["phonetic"] or ph_info["phonetic"],
            "source": "personal",
            "is_in_study_list": True,
            "local_id": r["id"],
            "box_level": r["box_level"] if r["box_level"] is not None else 0,
            "status": r["status"] or "learning",
            "match_rank": m_rank,
        }

    for g in global_rows:
        eng = g["english"]
        eng_lower = eng.lower().strip()
        if eng_lower in results_map:
            existing = results_map[eng_lower]
            if not existing["example"] and g.get("example"):
                existing["example"] = g["example"]
            if not existing["pos"] and g.get("pos"):
                existing["pos"] = g["pos"]
            existing["star"] = g.get("star", "0")
            existing["source"] = "both"
            g_rank = g.get("match_rank", text_search_utils.calculate_match_rank(clean_q, eng, g.get("uzbek", "")))
            if g_rank < existing["match_rank"]:
                existing["match_rank"] = g_rank
        else:
            info = phonetics.get_word_info(eng)
            results_map[eng_lower] = {
                "id": g["id"],
                "english": eng,
                "pos": g.get("pos") or info["part_of_speech"],
                "star": g.get("star", "0"),
                "uzbek": g.get("uzbek", ""),
                "example": g.get("example", ""),
                "phonetic": info["phonetic"],
                "source": "global",
                "is_in_study_list": g.get("is_in_study_list", False),
                "local_id": g.get("local_id"),
                "box_level": 0,
                "status": "new",
                "match_rank": g.get("match_rank", text_search_utils.calculate_match_rank(clean_q, eng, g.get("uzbek", ""))),
            }

    sorted_items = sorted(
        results_map.values(),
        key=lambda x: (
            x["match_rank"],
            0 if x["is_in_study_list"] else 1,
            -int(x["star"]) if str(x.get("star", "0")).isdigit() else 0,
            len(x["english"]),
        ),
    )

    return sorted_items[:limit]

