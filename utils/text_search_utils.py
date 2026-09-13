"""
Vocab Master Pro — Smart Search & Linguistic Utilities.
O'zbek va Ingliz tillari uchun universal qidiruv, transliteratsiya va ranking yordamchilari.

Imkoniyatlar:
- Kirill ↔ Lotin o'zbekcha transliteratsiya (китоб -> kitob, ўрганмоқ -> o'rganmoq)
- Tutuq va apostrof variantlari (' ‘ ’ ʻ ʼ ` ´ \ufffd) bilan xatosiz qidiruv
- Apostrofsiz kiritilgan so'zlarni aqlli kengaytirish (organmoq -> o'rganmoq, tog -> tog')
- Aniq va professional ko'p bosqichli ranking (Exact > Token > Prefix > Substring)
"""
import re
import html
import difflib
from typing import TypedDict

CYR_TO_LAT: dict[str, str] = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'j',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': "'", 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ў': "o'", 'ғ': "g'", 'қ': 'q', 'ҳ': 'h'
}

APOSTROPHE_CHARS = ["'", "‘", "’", "ʻ", "ʼ", "`", "´", "?", "\ufffd"]
APOSTROPHE_REGEX = re.compile(r"['‘’ʻʼ`´\?\ufffd]")

# O'zbek tilidagi eng ko'p uchraydigan tutuq belgili va o'/g' li so'zlar xaritasi
COMMON_UZ_VARIANTS: dict[str, list[str]] = {
    "mano": ["ma'no", "ma‘no", "maʻno"],
    "talim": ["ta'lim", "ta‘lim", "taʻlim"],
    "sher": ["she'r", "she‘r", "sheʻno"],
    "sanat": ["san'at", "san‘at", "sanʻat"],
    "masul": ["mas'ul", "mas‘ul", "masʻul"],
    "etibor": ["e'tibor", "e‘tibor", "eʻtibor"],
    "surat": ["sur'at", "sur‘at"],
    "tasir": ["ta'sir", "ta‘sir"],
    "vada": ["va'da", "va‘da"],
    "tam": ["ta'm", "ta‘m"],
    "alo": ["a'lo", "a‘lo"],
    "togri": ["to'g'ri", "to‘g‘ri", "toʻgʻri"],
    "dost": ["do'st", "do‘st", "doʻst"],
    "kormoq": ["ko'rmoq", "ko‘rmoq"],
    "bolmoq": ["bo'lmoq", "bo‘lmoq"],
    "kop": ["ko'p", "ko‘p"],
    "yol": ["yo'l", "yo‘l"],
    "qol": ["qo'l", "qo‘l"],
    "yoq": ["yo'q", "yo‘q"],
    "zor": ["zo'r", "zo‘r"],
    "ogir": ["og'ir", "og‘ir", "ogʻir"],
    "ogil": ["o'g'il", "o‘g‘il", "oʻgʻil"],
    "yomgir": ["yomg'ir", "yomg‘ir"],
    "tugilmoq": ["tug'ilmoq", "tug‘ilmoq"],
    "qorqmoq": ["qo'rqmoq", "qo‘rqmoq"],
    "qoriqchi": ["qo'riqchi", "qo‘riqchi"],
    "bosh": ["bo'sh", "bo‘sh"],
    "kocha": ["ko'cha", "ko‘cha"],
}


def cyrillic_to_latin(text: str) -> str:
    """Kirillcha o'zbekcha yozuvni lotinchaga o'girish."""
    if not text:
        return ""
    res = []
    for ch in text.lower():
        res.append(CYR_TO_LAT.get(ch, ch))
    return "".join(res)


def normalize_search_query(text: str) -> str:
    """Qidiruv so'zini tozalash va standart holatga keltirish."""
    if not text:
        return ""
    q = text.strip().lower()
    q = re.sub(r"\s+", " ", q)
    return q


class SearchPatterns(TypedDict):
    clean: str
    is_cyrillic: bool
    exact_variants: list[str]
    prefix_patterns: list[str]
    substring_patterns: list[str]


def get_search_patterns(query: str) -> SearchPatterns:
    """
    Qidiruv so'zi uchun o'zbek va ingliz tillarida eng aniq SQL shablonlarini hosil qilish.
    Apostroflar, kirill yozuvi, o'/g' harflari va tutuq belgilarini to'liq qamrab oladi.
    """
    q = normalize_search_query(query)
    if not q:
        return {
            "clean": "",
            "is_cyrillic": False,
            "exact_variants": [],
            "prefix_patterns": [],
            "substring_patterns": [],
        }

    is_cyr = any('\u0400' <= ch <= '\u04FF' for ch in q)
    base_queries = [q]
    if is_cyr:
        lat = cyrillic_to_latin(q)
        if lat and lat != q:
            base_queries.append(lat)

    exact_variants: list[str] = []
    prefix_patterns: list[str] = []
    substring_patterns: list[str] = []
    seen_exact = set()
    seen_prefix = set()
    seen_sub = set()

    def add_exact(v: str):
        v = v.strip().lower()
        if v and v not in seen_exact:
            seen_exact.add(v)
            exact_variants.append(v)

    def add_prefix(p: str):
        p = p.strip().lower()
        if p and p not in seen_prefix:
            seen_prefix.add(p)
            prefix_patterns.append(p)

    def add_sub(s: str):
        s = s.strip().lower()
        if s and s not in seen_sub:
            seen_sub.add(s)
            substring_patterns.append(s)

    for base in base_queries:
        add_exact(base)
        add_prefix(base)
        if len(base) >= 3:
            add_sub(base)

        has_ap = bool(APOSTROPHE_REGEX.search(base))
        if has_ap:
            # Har xil apostrof gliflari bilan variantlar
            base_clean = APOSTROPHE_REGEX.sub("", base)
            add_exact(base_clean)
            add_prefix(base_clean)
            if len(base_clean) >= 3:
                add_sub(base_clean)

            # Standart apostroflar (' ‘ ʻ) bilan exact variantlar
            for ap in ["'", "‘", "ʻ"]:
                ap_ver = APOSTROPHE_REGEX.sub(ap, base)
                add_exact(ap_ver)
                add_prefix(ap_ver)
        else:
            # 1. Lug'atdagi tayyor variantlar mavjud bo'lsa
            if base in COMMON_UZ_VARIANTS:
                for v in COMMON_UZ_VARIANTS[base]:
                    add_exact(v)
                    add_prefix(v)

            # 2. So'z 'o' bilan boshlansa va undosh kelsa (organmoq -> o'rganmoq)
            if base.startswith("o") and len(base) > 1 and base[1] not in "aeiou'":
                for ap in ["'", "‘", "ʻ"]:
                    o_ver = f"o{ap}{base[1:]}"
                    add_exact(o_ver)
                    add_prefix(o_ver)

            # 3. So'z 'g' bilan tugasa (tog -> tog', bog -> bog', yog -> yog')
            if base.endswith("g") and len(base) <= 6:
                for ap in ["'", "‘", "ʻ"]:
                    g_ver = f"{base}{ap}"
                    add_exact(g_ver)
                    add_prefix(g_ver)

            # 4. Suffix yoki ildizdagi o' (masalan: ko'r, bo'l, do'st, qo'l, yo'l, xo'jalik)
            if not base.startswith("o"):
                for prefix in ["bo", "ko", "to", "do", "zo", "qo", "yo", "cho", "sho", "xo"]:
                    if base.startswith(prefix) and len(base) > len(prefix):
                        tail = base[len(prefix):]
                        if prefix == "to" and tail.startswith("b"):
                            continue
                        if tail[0] not in "aeiou":
                            for ap in ["'", "‘"]:
                                add_exact(f"{prefix[:-1]}o{ap}{tail}")
                                add_prefix(f"{prefix[:-1]}o{ap}{tail}")

            # 5. So'z ichidagi g' (masalan: tugishganlik -> tug'ishganlik, yomgir -> yomg'ir)
            if "g" in base and not base.endswith("g"):
                for ap in ["'", "‘"]:
                    p_g = re.sub(r"([ouia])g([a-z])", rf"\1g{ap}\2", base)
                    if p_g != base:
                        add_exact(p_g)
                        add_prefix(p_g)

    return {
        "clean": q,
        "is_cyrillic": is_cyr,
        "exact_variants": exact_variants,
        "prefix_patterns": prefix_patterns,
        "substring_patterns": substring_patterns,
    }


def calculate_match_rank(query: str, english: str, uzbek: str, patterns: SearchPatterns | None = None) -> int:
    """
    Qidiruv natijasi uchun aniqlik darajasini (Rank: 0 eng yaxshi) hisoblash:
    - 0: Aniq moslik (Exact match English yoki Uzbek)
    - 1: Vergul/bo'shliq bilan ajratilgan tarjima qismlarida aniq moslik
    - 2: Boshlanish mosligi (Prefix match English yoki Uzbek)
    - 3: Ichki moslik (Substring match)
    """
    q_norm = normalize_search_query(query)
    if not q_norm:
        return 3

    if patterns is None:
        patterns = get_search_patterns(q_norm)

    eng_low = (english or "").strip().lower()
    uz_low = (uzbek or "").strip().lower()

    # 1. Aniq moslik (Rank 0)
    if eng_low == q_norm:
        return 0
    if any(uz_low == v for v in patterns["exact_variants"]):
        return 0

    # 2. Tarjima bo'laklari (token) bo'yicha aniq moslik (Rank 1)
    # Masalan: "kitob, darslik" -> "kitob" tokeni aniq mos
    uz_tokens = [re.sub(r"^[^\w]+|[^\w]+$", "", t.strip()) for t in re.split(r"[,;/]+", uz_low) if t.strip()]
    for token in uz_tokens:
        if token == q_norm or any(token == v for v in patterns["exact_variants"]):
            return 1

    # 3. Boshlanish mosligi (Rank 2)
    if eng_low.startswith(q_norm):
        return 2
    for p in patterns["prefix_patterns"]:
        if uz_low.startswith(p):
            return 2
        for token in uz_tokens:
            if token.startswith(p):
                return 2

    # 4. Qism mosligi (Rank 3)
    return 3


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Ikki so'z orasidagi Levenshtein (tahrirlash) masofasini hisoblash.
    Katta-kichik harf farqlari inobatga olinmaydi.
    """
    s1, s2 = (s1 or "").lower(), (s2 or "").lower()
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = list(range(len(s1) + 1))
    for i2, c2 in enumerate(s2):
        new_distances = [i2 + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                new_distances.append(distances[i1])
            else:
                new_distances.append(1 + min(distances[i1], distances[i1 + 1], new_distances[-1]))
        distances = new_distances
    return distances[-1]


def compute_visual_diff(user_input: str, expected: str) -> dict:
    """
    Kiritilgan javob bilan to'g'ri javob orasidagi farqlarni harfma-harf aniqlash.
    Qaytaradi:
    - is_typo: bool (kichik imlo xatosi bo'lsa True: masofa 1-2)
    - distance: int (Levenshtein masofasi)
    - expected_diff_html: str (to'g'ri so'zdagi o'zgarishlar/tushib qolgan harflar yashil rangda)
    - user_diff_html: str (foydalanuvchi kiritgan xato/ortiqcha harflar qizil rangda o'chirilgan)
    - tip_message: str (foydalanuvchi uchun qulay tushuntirish xabari)
    """
    u_raw = (user_input or "").strip()
    e_raw = (expected or "").strip()
    u = u_raw.lower()
    e = e_raw.lower()

    dist = levenshtein_distance(u, e)
    # Typo agar masofa 1 bo'lsa (harf uzunligi >=3) yoki 2 bo'lsa (harf uzunligi >=4)
    is_typo = (dist == 1 and len(e) >= 3) or (dist == 2 and len(e) >= 4)

    matcher = difflib.SequenceMatcher(None, u_raw, e_raw)
    u_parts: list[str] = []
    e_parts: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        u_chunk = html.escape(u_raw[i1:i2])
        e_chunk = html.escape(e_raw[j1:j2])

        if tag == 'equal':
            u_parts.append(u_chunk)
            e_parts.append(e_chunk)
        elif tag == 'replace':
            u_parts.append(f'<span style="color:#EF4444; text-decoration:line-through; font-weight:700;">{u_chunk}</span>')
            e_parts.append(f'<span style="color:#10B981; font-weight:700; text-decoration:underline;">{e_chunk}</span>')
        elif tag == 'delete':
            u_parts.append(f'<span style="color:#EF4444; text-decoration:line-through; font-weight:700;">{u_chunk}</span>')
        elif tag == 'insert':
            e_parts.append(f'<span style="color:#10B981; font-weight:700; text-decoration:underline;">{e_chunk}</span>')

    tip_msg = ""
    if is_typo:
        count_str = "1 ta" if dist == 1 else "2 ta"
        tip_msg = f"💡 Deyarli to'g'ri! ({count_str} harfda adashdingiz)"

    return {
        "is_typo": is_typo,
        "distance": dist,
        "expected_diff_html": "".join(e_parts),
        "user_diff_html": "".join(u_parts),
        "tip_message": tip_msg,
    }

