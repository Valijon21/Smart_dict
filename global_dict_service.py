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
import phonetics
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


def get_uzbek_search_patterns(q: str) -> list[str]:
    """
    O'zbekcha so'zlar uchun tutuq belgili va belgilisiz barcha variantlarni hosil qilish.
    (masalan: o'rganmoq / organmoq / o‘rganmoq / zo'r / zor / tog' / tog).
    """
    patterns = set()
    patterns.add(q)

    # 1. Barcha turdagi apostroflarni SQL '_' wildcard belgisiga aylantirish
    q_wild = q
    for ch in ["'", "‘", "’", "ʻ", "ʼ", "`", "´"]:
        q_wild = q_wild.replace(ch, "_")
    patterns.add(q_wild)

    # 2. Agar foydalanuvchi apostrofsiz yozgan bo'lsa (organmoq, ogil, zor, tog)
    # o va g harflaridan keyin '_' qo'yib variantlar hosil qilish
    if "_" not in q_wild:
        p1 = re.sub(r"o(?=[^aeiou\s]|$)", "o_", q, count=1)
        if p1 != q:
            patterns.add(p1)
        p2 = re.sub(r"g(?=[^aeiou\s]|$)", "g_", q, count=1)
        if p2 != q:
            patterns.add(p2)
        p3 = re.sub(r"o(?=[^aeiou\s]|$)", "o_", p2, count=1)
        if p3 != q and p3 != p1 and p3 != p2:
            patterns.add(p3)

    return list(patterns)


def search_universal_words(query: str, limit: int = 20) -> list[dict]:
    """
    100% aniqlikdagi universal ikki tomonlama qidiruv (Inglizcha ↔ O'zbekcha).
    Ham shaxsiy bazadan (vocab.db), ham 64,000 so'zlik akademik lug'atdan (db.sqlite3)
    eng mos natijalarni mukammal saralab qaytaradi.
    """
    q = query.strip().lower()
    if not q:
        return []

    uz_patterns = get_uzbek_search_patterns(q)
    results_map: dict[str, dict] = {}

    # 1. Shaxsiy baza (vocab.db) qidiruvi
    try:
        with db.get_conn() as conn:
            pers_clauses = ["LOWER(w.english) = ?", "LOWER(w.english) LIKE ? || '%'"]
            pers_params = [q, q]
            for p in uz_patterns:
                pers_clauses.extend(["LOWER(w.uzbek) = ?", "LOWER(w.uzbek) LIKE ? || '%'", "LOWER(w.uzbek) LIKE '%' || ? || '%'"])
                pers_params.extend([p, p, p])
            pers_clauses.append("LOWER(w.english) LIKE '%' || ? || '%'")
            pers_params.append(q)

            sql_pers = f"""
                SELECT w.*, p.box_level, p.next_review, p.correct_count, p.wrong_count
                FROM words w
                LEFT JOIN progress p ON p.word_id = w.id
                WHERE {" OR ".join(pers_clauses)}
                LIMIT ?
            """
            pers_params.append(limit)

            local_rows = conn.execute(sql_pers, tuple(pers_params)).fetchall()

            for r in local_rows:
                eng = r["english"]
                eng_lower = eng.lower()
                uz = r["uzbek"] or ""

                if eng_lower == q or any(uz.lower() == p for p in uz_patterns):
                    rank = 0
                elif eng_lower.startswith(q) or any(uz.lower().startswith(p) for p in uz_patterns):
                    rank = 1
                else:
                    rank = 2

                ph_info = phonetics.get_word_info(eng)
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
                    "match_rank": rank,
                }
    except Exception as e:
        logger.error(f"Shaxsiy bazadan universal qidiruvda xatolik: {e}")

    # 2. 64,000 so'zlik global lug'at (db.sqlite3) qidiruvi
    conn_g = get_db_connection()
    if conn_g:
        try:
            cur = conn_g.cursor()

            where_conds = ["we.word LIKE ? || '%'"]
            params = [q]
            for p in uz_patterns:
                where_conds.append("wz.word LIKE ? || '%'")
                params.append(p)
            where_conds.append("we.word LIKE '%' || ? || '%'")
            params.append(q)
            for p in uz_patterns:
                where_conds.append("wz.word LIKE '%' || ? || '%'")
                params.append(p)

            case_parts = ["WHEN LOWER(we.word) = ? THEN 0"]
            case_params = [q]
            for p in uz_patterns:
                case_parts.append("WHEN LOWER(wz.word) = ? THEN 0")
                case_params.append(p)
            case_parts.append("WHEN we.word LIKE ? || '%' THEN 1")
            case_params.append(q)
            for p in uz_patterns:
                case_parts.append("WHEN wz.word LIKE ? || '%' THEN 1")
                case_params.append(p)

            full_sql = f"""
                SELECT 
                    we.id, 
                    we.word, 
                    we.word_classword_class AS pos,
                    we.star,
                    we.example,
                    GROUP_CONCAT(wz.word, ', ') AS uzbek,
                    CASE {" ".join(case_parts)} ELSE 2 END as match_rank,
                    LENGTH(we.word) as word_len
                FROM word_entity we
                LEFT JOIN words_uz wz ON we.id = wz.word_id
                WHERE {" OR ".join(where_conds)}
                GROUP BY we.id
                ORDER BY 
                    match_rank ASC,
                    we.star DESC,
                    word_len ASC
                LIMIT ?
            """
            all_params = case_params + params + [limit]
            cur.execute(full_sql, tuple(all_params))

            for row in cur.fetchall():
                eng = row["word"]
                eng_lower = eng.lower()
                star_val = str(row["star"] or "0")
                uz_val = row["uzbek"] or ""
                ex_val = clean_html(row["example"]) if row["example"] else ""
                rank = row["match_rank"]

                if eng_lower in results_map:
                    existing = results_map[eng_lower]
                    if not existing["example"] and ex_val:
                        existing["example"] = ex_val
                    if not existing["pos"] and row["pos"]:
                        existing["pos"] = row["pos"]
                    existing["star"] = star_val
                    existing["source"] = "both"
                    if rank < existing["match_rank"]:
                        existing["match_rank"] = rank
                else:
                    info = phonetics.get_word_info(eng)
                    ph = info["phonetic"]
                    pos_val = row["pos"] or info["part_of_speech"]
                    results_map[eng_lower] = {
                        "id": row["id"],
                        "english": eng,
                        "pos": pos_val,
                        "star": star_val,
                        "uzbek": uz_val,
                        "example": ex_val,
                        "phonetic": ph,
                        "source": "global",
                        "is_in_study_list": False,
                        "local_id": None,
                        "box_level": 0,
                        "status": "new",
                        "match_rank": rank,
                    }
        except Exception as e:
            logger.error(f"Global bazadan universal qidiruvda xatolik: {e}")
        finally:
            conn_g.close()

    # 3. Yagona mukammal saralash:
    # 0 - Aniq moslik, 1 - Boshlanish, 2 - Qism mosligi
    # Shaxsiy o'rganish ro'yxatidagilar birinchi, yuqori Oxford yulduzlari, qisqaroq so'zlar
    sorted_items = sorted(
        results_map.values(),
        key=lambda x: (
            x["match_rank"],
            0 if x["is_in_study_list"] else 1,
            -int(x["star"]) if x["star"].isdigit() else 0,
            len(x["english"]),
        ),
    )

    return sorted_items[:limit]

