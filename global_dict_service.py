"""
Vocab Master Pro — Global 64,000 Offline Dictionary Service.
Longman / Oxford standartidagi 64,000 so'zlik ulkan akademik inglizcha-o'zbekcha
lug'at bazasi (db.sqlite3) bilan tezkor, xavfsiz va aqlli ishlash xizmati.

Imkoniyatlari:
- 64,000 ta so'zdan 1-5 millisekundlik tezkor qidiruv (Prefix + Substring)
- Barcha o'zbekcha tarjimalar, misollar, kollokatsiyalar, farqlar va sinonimlarni olish
- 1-bosishda foydalanuvchining shaxsiy o'rganish rejasiga (vocab.db) import qilish
"""
import re
import html
import sqlite3
from pathlib import Path
from typing import Any

import database as db
from logger import get_logger

logger = get_logger("global_dict_service")

DB_PATH = Path(r"D:\Proyekt\suz surash\db.sqlite3")


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
    64,000 so'zlik lug'atdan tezkor qidiruv.
    Avval so'z boshidan moslik (prefix), so'ngra substring qidiriladi.
    """
    q = query.strip().lower()
    if not q:
        return []

    conn = get_db_connection()
    if not conn:
        return []

    results: list[dict] = []
    seen_ids = set()

    try:
        cursor = conn.cursor()

        # 1. Boshlanish mosligi (Prefix match - eng yuqori prioritet va indeksli)
        cursor.execute(
            """
            SELECT 
                we.id, 
                we.word, 
                we.word_classword_class AS pos,
                we.star,
                we.example,
                GROUP_CONCAT(wz.word, ', ') AS uzbek
            FROM word_entity we
            LEFT JOIN words_uz wz ON we.id = wz.word_id
            WHERE we.word LIKE ? || '%'
            GROUP BY we.id
            ORDER BY 
                CASE WHEN LOWER(we.word) = ? THEN 0 ELSE 1 END,
                LENGTH(we.word) ASC,
                we.star DESC
            LIMIT ?
            """,
            (q, q, limit)
        )

        for row in cursor.fetchall():
            w_id = row["id"]
            seen_ids.add(w_id)
            results.append({
                "id": w_id,
                "english": row["word"],
                "pos": row["pos"] or "",
                "star": row["star"] or "0",
                "uzbek": row["uzbek"] or "",
                "example": clean_html(row["example"]),
                "source": "global",
            })

        # 2. Agar limit to'lmagan bo'lsa va so'z kamida 3 harfli bo'lsa, qidiruvni kengaytirish
        remaining = limit - len(results)
        if remaining > 0 and len(q) >= 3:
            cursor.execute(
                """
                SELECT 
                    we.id, 
                    we.word, 
                    we.word_classword_class AS pos,
                    we.star,
                    we.example,
                    GROUP_CONCAT(wz.word, ', ') AS uzbek
                FROM word_entity we
                LEFT JOIN words_uz wz ON we.id = wz.word_id
                WHERE we.word LIKE '%' || ? || '%' AND we.id NOT IN ({})
                GROUP BY we.id
                ORDER BY LENGTH(we.word) ASC
                LIMIT ?
                """.format(",".join(str(i) for i in seen_ids) if seen_ids else "0"),
                (q, remaining)
            )

            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "english": row["word"],
                    "pos": row["pos"] or "",
                    "star": row["star"] or "0",
                    "uzbek": row["uzbek"] or "",
                    "example": clean_html(row["example"]),
                    "source": "global",
                })

    except Exception as e:
        logger.error(f"Global qidiruvda xatolik: {e}")
    finally:
        conn.close()

    # Foydalanuvchining shaxsiy bazasida (vocab.db) mavjudligini belgilash
    if results:
        for r in results:
            local_word = db.get_word_by_english(r["english"])
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

        return {
            "id": w_id,
            "english": eng_word,
            "pos": we_row["word_classword_class"] or "",
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
