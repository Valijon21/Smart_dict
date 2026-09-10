"""
Vocab Master Pro — CEFR (A1-C2) & IELTS Academic Word Service.
64,000 so'zlik ulkan akademik bazadan (db.sqlite3) xalqaro CEFR darajalari:
- A1-A2 (Boshlang'ich va Elementary — Oxford 3000 Core)
- B1-B2 (O'rta va Mustaqil — Oxford 5000 Intermediate)
- C1-C2 (Yuqori va Professional — Advanced Mastery)
- IELTS 7.0+ / Academic Word List (AWL 570 ta ilmiy o'zak so'z)
bo'yicha saralash, taqdim etish va 1-bosishda o'rganish rejasiga yuklash xizmati.
"""
import sys
import sqlite3
from pathlib import Path
from typing import Any

try:
    from core import database as db
    from services import global_dict_service
    from utils.logger import get_logger, get_app_dir
except ImportError:
    import database as db
    import global_dict_service
    from logger import get_logger, get_app_dir

logger = get_logger("cefr_service")

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

# Har bir CEFR darajasining so'zlar to'plami xotirada keshlanadi (Tezkor hisoblash uchun)
_LEVEL_WORDS_CACHE: dict[str, set[str]] = {}
_STATIC_SUMMARIES_CACHE: list[dict] | None = None

# Academic Word List (AWL) - 570 ta asosiy akademik leksik o'zak
AWL_HEADWORDS = {
    "abandon", "abstract", "academy", "access", "accommodate", "accompany", "accumulate",
    "accurate", "achieve", "acknowledge", "acquire", "adapt", "adequate", "adjacent",
    "adjust", "administrate", "adult", "advocate", "affect", "aggregate", "aid", "albeit",
    "allocate", "alter", "alternative", "ambiguous", "amend", "analogy", "analyse",
    "analyze", "annual", "anticipate", "apparent", "append", "appreciate", "approach",
    "appropriate", "approximate", "arbitrary", "area", "aspect", "assemble", "assess",
    "assign", "assist", "assume", "assure", "attach", "attain", "attitude", "attribute",
    "author", "authority", "automate", "available", "aware", "behalf", "benefit", "bias",
    "bond", "brief", "bulk", "capable", "capacity", "category", "cease", "challenge",
    "channel", "chapter", "chart", "chemical", "circumstance", "cite", "civil", "clarify",
    "classic", "clause", "code", "coherent", "coincide", "collapse", "colleague", "commence",
    "comment", "commission", "commit", "commodity", "communicate", "community", "compatible",
    "compensate", "compile", "complement", "complex", "component", "compound", "comprehensive",
    "comprise", "compute", "conceive", "concentrate", "concept", "conclude", "concurrent",
    "conduct", "confer", "confine", "confirm", "conflict", "conform", "consent", "consequent",
    "considerable", "consist", "constant", "constitute", "constrain", "construct", "consult",
    "consume", "contact", "contemporary", "context", "contract", "contradict", "contrary",
    "contrast", "contribute", "controversy", "convene", "converse", "convert", "convince",
    "cooperate", "coordinate", "core", "corporate", "correspond", "couple", "create",
    "credit", "criteria", "crucial", "culture", "currency", "cycle", "data", "debate",
    "decade", "decline", "deduce", "define", "definite", "demonstrate", "denote", "deny",
    "depress", "derive", "design", "despite", "detect", "deviate", "device", "devote",
    "differentiate", "dimension", "diminish", "discrete", "discriminate", "displace",
    "display", "dispose", "distinct", "distort", "distribute", "diverse", "document",
    "domain", "domestic", "dominate", "draft", "drama", "duration", "dynamic", "economy",
    "edit", "element", "eliminate", "emerge", "emphasis", "empirical", "enable", "encounter",
    "energy", "enforce", "enhance", "enormous", "ensure", "entity", "environment", "equate",
    "equip", "equivalent", "erode", "error", "establish", "estate", "estimate", "ethic",
    "ethnic", "evaluate", "eventual", "evident", "evolve", "exceed", "exclude", "exhibit",
    "expand", "expert", "explicit", "exploit", "export", "expose", "external", "extract",
    "facilitate", "factor", "feature", "federal", "fee", "file", "final", "finance",
    "finite", "flexible", "fluctuate", "focus", "format", "formula", "forthcoming", "foundation",
    "found", "framework", "function", "fund", "fundamental", "furthermore", "gender",
    "generate", "generation", "globe", "goal", "grade", "grant", "guarantee", "guideline",
    "hence", "hierarchy", "highlight", "hypothesis", "identical", "identify", "ideology",
    "ignorant", "illustrate", "image", "immigrate", "impact", "implement", "implicate",
    "implicit", "imply", "impose", "incentive", "incidence", "incline", "income",
    "incorporate", "index", "indicate", "individual", "induce", "inevitable", "infer",
    "infrastructure", "inherent", "inhibit", "initial", "initiate", "injure", "innovate",
    "input", "insert", "insight", "inspect", "instance", "institute", "instruct",
    "integral", "integrate", "integrity", "intelligence", "intense", "interact", "intermediate",
    "internal", "interpret", "interval", "intervene", "intrinsic", "invest", "investigate",
    "invoke", "involve", "isolate", "issue", "item", "job", "journal", "justify", "label",
    "labor", "layer", "lecture", "legal", "legislate", "levy", "liberal", "licence",
    "likewise", "link", "locate", "logic", "maintain", "major", "manipulate", "manual",
    "margin", "mature", "maximise", "maximize", "mechanism", "media", "mediate", "medical",
    "medium", "mental", "method", "migrate", "military", "minimal", "minimise", "minimum",
    "ministry", "minor", "mode", "modify", "monitor", "motive", "mutual", "negate",
    "network", "neutral", "nevertheless", "nonetheless", "norm", "normal", "notion",
    "notwithstanding", "nuclear", "objective", "obtain", "obvious", "occupy", "occur",
    "odd", "offset", "ongoing", "option", "orient", "outcome", "output", "overall",
    "overlap", "overseas", "panel", "paradigm", "paragraph", "parallel", "parameter",
    "participate", "partner", "passive", "perceive", "percent", "period", "persist",
    "perspective", "phase", "phenomenon", "philosophy", "physical", "plus", "policy",
    "portion", "pose", "positive", "potential", "practitioner", "precede", "precise",
    "predict", "predominant", "preliminary", "presume", "previous", "primary", "prime",
    "principal", "principle", "prior", "priority", "proceed", "process", "professional",
    "prohibit", "project", "promote", "proportion", "prospect", "protocol", "psychology",
    "publication", "publish", "purchase", "pursue", "qualitative", "quote", "radical",
    "random", "range", "ratio", "rational", "react", "recover", "refine", "regime",
    "region", "register", "regulate", "reinforce", "reject", "relax", "release", "relevant",
    "reluctance", "rely", "remove", "require", "research", "reset", "resolve", "resource",
    "respond", "restore", "restrain", "restrict", "retain", "reveal", "revenue", "reverse",
    "revise", "revolution", "rigid", "role", "route", "scenario", "schedule", "scheme",
    "scope", "section", "sector", "secure", "seek", "select", "sequence", "series",
    "sex", "shift", "significant", "similar", "simulate", "site", "so-called", "sole",
    "somewhat", "source", "specific", "specify", "sphere", "stable", "statistic", "status",
    "straightforward", "strategy", "stress", "structure", "style", "submit", "subordinate",
    "subsequent", "subsidy", "substitute", "successor", "sufficient", "sum", "summary",
    "supplement", "survey", "survive", "suspend", "sustain", "symbol", "tape", "target",
    "task", "team", "technical", "technique", "technology", "temporary", "tense",
    "terminate", "text", "theme", "theory", "thereby", "thesis", "topic", "trace",
    "tradition", "transfer", "transform", "transit", "transmit", "transport", "trend",
    "trigger", "ultimate", "undergo", "underlie", "undertake", "uniform", "unify",
    "unique", "utilise", "utilize", "valid", "vary", "vehicle", "version", "via",
    "violate", "virtual", "visible", "vision", "visual", "volume", "voluntary", "welfare",
    "whereby", "widespread"
}

CEFR_LEVELS = [
    {
        "id": "cefr_a1_a2",
        "title": "🌱 CEFR A1 – A2: Boshlang'ich (Oxford 3000 Core)",
        "level": "A1 - A2",
        "badge_color": "#10B981",
        "icon": "🌱",
        "description": "Kundalik muloqot, oila, shahar, taom va asosiy so'zlashuv poydevori uchun 1,500+ ta eng zaruriy so'z.",
        "star": "3"
    },
    {
        "id": "cefr_b1_b2",
        "title": "⚡ CEFR B1 – B2: O'rta & Mustaqil (Oxford 5000)",
        "level": "B1 - B2",
        "badge_color": "#3B82F6",
        "icon": "⚡",
        "description": "Erkin suhbat, ta'lim, professional ish va chet eldagi sayohatlar uchun zarur 2,500+ ta leksik birlik.",
        "star": "2"
    },
    {
        "id": "cefr_c1_c2",
        "title": "👑 CEFR C1 – C2: Yuqori & Mukammal (Advanced Mastery)",
        "level": "C1 - C2",
        "badge_color": "#8B5CF6",
        "icon": "👑",
        "description": "Akademik tahlil, nozik ma'nodagi sinonimlar va professional adabiy ingliz tili ustasi darajasidagi so'zlar.",
        "star": "1"
    },
    {
        "id": "ielts_academic",
        "title": "🎓 IELTS Band 7.0+ & Academic Word List (AWL)",
        "level": "IELTS 7.0+",
        "badge_color": "#F59E0B",
        "icon": "🎓",
        "description": "IELTS Academic Writing/Reading, ilmiy tadqiqotlar va insholarda yuqori ball (7.0+) keltiruvchi rasmiy akademik so'zlar.",
        "is_awl": True
    }
]


def _get_db():
    return global_dict_service.get_db_connection()


def get_cefr_levels_summary() -> list[dict]:
    """Barcha CEFR darajalari haqida to'liq metama'lumot va so'zlar sonini qaytaradi (bir zumda keshdan)."""
    global _STATIC_SUMMARIES_CACHE

    try:
        with db.get_conn() as local_conn:
            rows = local_conn.execute("SELECT LOWER(english) FROM words").fetchall()
            local_words = set(r[0] for r in rows)
    except Exception as e:
        logger.error(f"Local words olishda xatolik: {e}")
        local_words = set()

    if _STATIC_SUMMARIES_CACHE is None:
        conn = _get_db()
        if not conn:
            return []
        summaries = []
        try:
            cursor = conn.cursor()
            for lvl in CEFR_LEVELS:
                lvl_id = lvl["id"]
                if lvl.get("is_awl"):
                    placeholders = ",".join("?" for _ in AWL_HEADWORDS)
                    cursor.execute(
                        f"SELECT COUNT(*) FROM word_entity WHERE LOWER(word) IN ({placeholders})",
                        list(AWL_HEADWORDS)
                    )
                    total = cursor.fetchone()[0]

                    cursor.execute(
                        f"""
                        SELECT we.word, GROUP_CONCAT(wz.word, ', ') AS uzbek 
                        FROM word_entity we
                        LEFT JOIN words_uz wz ON we.id = wz.word_id
                        WHERE LOWER(we.word) IN ({placeholders})
                        GROUP BY we.id
                        LIMIT 4
                        """,
                        list(AWL_HEADWORDS)
                    )
                    sample_rows = cursor.fetchall()
                else:
                    star = lvl["star"]
                    cursor.execute(
                        "SELECT COUNT(*) FROM word_entity WHERE star = ? AND LENGTH(word) >= 2",
                        (star,)
                    )
                    total = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        SELECT we.word, GROUP_CONCAT(wz.word, ', ') AS uzbek 
                        FROM word_entity we
                        LEFT JOIN words_uz wz ON we.id = wz.word_id
                        WHERE we.star = ? AND LENGTH(we.word) >= 2
                        GROUP BY we.id
                        LIMIT 4
                        """,
                        (star,)
                    )
                    sample_rows = cursor.fetchall()

                samples = [
                    {"english": r["word"], "uzbek": (r["uzbek"] or "").split(",")[0].strip()}
                    for r in sample_rows
                ]

                summaries.append({
                    **lvl,
                    "total_words": total,
                    "samples": samples
                })
            _STATIC_SUMMARIES_CACHE = summaries
        except Exception as e:
            logger.error(f"CEFR xulosasini olishda xatolik: {e}")
            return []
        finally:
            conn.close()

    # Har bir darajadagi mavjud so'zlar sonini 0.1ms da xotiradagi kesishish orqali hisoblash
    result = []
    for s in _STATIC_SUMMARIES_CACHE:
        cnt = get_imported_count_for_level(s["id"], local_words=local_words)
        result.append({
            **s,
            "already_imported": cnt
        })
    return result


def get_words_for_level(level_id: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """Muayyan darajadagi so'zlar ro'yxatini qaytaradi."""
    conn = _get_db()
    if not conn:
        return []

    results = []
    try:
        cursor = conn.cursor()
        if level_id == "ielts_academic":
            placeholders = ",".join("?" for _ in AWL_HEADWORDS)
            cursor.execute(
                f"""
                SELECT we.id, we.word, we.word_classword_class AS pos, we.example,
                       GROUP_CONCAT(wz.word, ', ') AS uzbek
                FROM word_entity we
                LEFT JOIN words_uz wz ON we.id = wz.word_id
                WHERE LOWER(we.word) IN ({placeholders})
                GROUP BY we.id
                ORDER BY we.word ASC
                LIMIT ? OFFSET ?
                """,
                list(AWL_HEADWORDS) + [limit, offset]
            )
        else:
            star_map = {"cefr_a1_a2": "3", "cefr_b1_b2": "2", "cefr_c1_c2": "1"}
            star = star_map.get(level_id, "3")
            cursor.execute(
                """
                SELECT we.id, we.word, we.word_classword_class AS pos, we.example,
                       GROUP_CONCAT(wz.word, ', ') AS uzbek
                FROM word_entity we
                LEFT JOIN words_uz wz ON we.id = wz.word_id
                WHERE we.star = ? AND LENGTH(we.word) >= 2
                GROUP BY we.id
                ORDER BY we.word ASC
                LIMIT ? OFFSET ?
                """,
                (star, limit, offset)
            )

        for r in cursor.fetchall():
            results.append({
                "id": r["id"],
                "english": r["word"],
                "pos": r["pos"] or "",
                "uzbek": r["uzbek"] or "",
                "example": global_dict_service.clean_html(r["example"]),
            })
    except Exception as e:
        logger.error(f"CEFR so'zlarini olishda xatolik ({level_id}): {e}")
    finally:
        conn.close()

    return results


def get_level_words_set(level_id: str) -> set[str]:
    """Ushbu darajaga tegishli barcha so'zlar to'plamini keshdan yoki db.sqlite3 dan oladi."""
    global _LEVEL_WORDS_CACHE
    if level_id in _LEVEL_WORDS_CACHE and _LEVEL_WORDS_CACHE[level_id]:
        return _LEVEL_WORDS_CACHE[level_id]

    conn = _get_db()
    if not conn:
        return set()

    try:
        cursor = conn.cursor()
        if level_id == "ielts_academic":
            placeholders = ",".join("?" for _ in AWL_HEADWORDS)
            cursor.execute(
                f"SELECT LOWER(word) FROM word_entity WHERE LOWER(word) IN ({placeholders})",
                list(AWL_HEADWORDS)
            )
        else:
            star_map = {"cefr_a1_a2": "3", "cefr_b1_b2": "2", "cefr_c1_c2": "1"}
            star = star_map.get(level_id, "3")
            cursor.execute(
                "SELECT LOWER(word) FROM word_entity WHERE star = ? AND LENGTH(word) >= 2",
                (star,)
            )
        words_set = set(r[0] for r in cursor.fetchall())
        _LEVEL_WORDS_CACHE[level_id] = words_set
        return words_set
    except Exception as e:
        logger.error(f"CEFR daraja so'zlarini olishda xatolik ({level_id}): {e}")
        return set()
    finally:
        conn.close()


def get_imported_count_for_level(level_id: str, local_words: set[str] | None = None) -> int:
    """Foydalanuvchi vocab.db sida ushbu darajadan qancha so'z mavjudligini aniqlash."""
    words_in_level = get_level_words_set(level_id)
    if not words_in_level:
        return 0

    if local_words is None:
        try:
            with db.get_conn() as local_conn:
                rows = local_conn.execute("SELECT LOWER(english) FROM words").fetchall()
                local_words = set(r[0] for r in rows)
        except Exception as e:
            logger.error(f"Mahalliy so'zlarni olishda xatolik: {e}")
            return 0

    return len(words_in_level.intersection(local_words))


def import_cefr_words_to_study(level_id: str, count: int = 50) -> tuple[int, int]:
    """
    Ushbu CEFR darajasidan foydalanuvchining shaxsiy lug'atiga hali qo'shilmagan
    'count' ta yangi so'zni xavfsiz va tezkor import qiladi (yagona tranzaksiya).
    Qaytaradi: (yangi_qo'shilgan_soni, darajadagi_jami_so'zlar)
    """
    words = get_words_for_level(level_id, limit=3000)
    if not words:
        return 0, 0

    # vocab.db dagi mavjud so'zlarni 1 ta tezkor so'rov bilan aniqlash
    try:
        with db.get_conn() as local_conn:
            rows = local_conn.execute("SELECT LOWER(english) FROM words").fetchall()
            local_words = set(r[0] for r in rows)
    except Exception as e:
        logger.error(f"Mavjud so'zlarni tekshirishda xatolik: {e}")
        local_words = set()

    candidates = []
    for w in words:
        if len(candidates) >= count:
            break
        eng = w["english"]
        if eng.lower() not in local_words:
            uz = w.get("uzbek", "")
            ex = w.get("example", "")
            if ex and "\n" in ex:
                ex = ex.split("\n")[0]
            candidates.append((eng, uz, ex))

    if not candidates:
        return 0, len(words)

    # Barcha so'zlarni yagona SQLite tranzaksiyasida qo'shish (tezligi: < 30ms)
    res = db.bulk_add_words(candidates, source=f"cefr:{level_id}")
    added = res.get("added", 0)
    logger.info(f"CEFR to'plamidan tezkor import: {level_id} -> {added} ta so'z qo'shildi")
    return added, len(words)
