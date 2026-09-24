"""
Vocab Master Pro — Intellektual so'z import qilish tizimi (Smart Importer).
.txt, .csv, .docx, .xlsx, .pdf fayllar va to'g'ridan-to'g'ri matndan so'zlarni
aqlli, moslashuvchan va xatosiz ajratib oladi.

Qo'llab-quvvatlanadigan formatlar:
    1. Standart ajratuvchilar:
       apple - olma
       apple – olma (en-dash)
       apple — olma (em-dash)
       apple : olma
       apple = olma
       apple => olma
       apple -> olma
       apple | olma (pipe)
       apple ; olma (semicolon)
       apple ~ olma
       apple    olma (tab yoki 2+ bo'sh joy)
    2. Chiziqcha (hyphen) bilan yoziladigan murakkab so'zlar:
       check-in - ro'yxatdan o'tish
       well-known - mashhur
       ice-cream - muzqaymoq
    3. Transkripsiya va so'z turkumlari:
       abandon [ə'bændən] - tark etmoq
       abandon [ə'bændən] tark etmoq (chiziqchasiz)
       abandon /ə'bændən/ tark etmoq
       abandon (v.) - tark etmoq
       abandon (verb) tark etmoq
    4. Raqamlash va markerlar:
       1. apple - olma
       1) apple - olma
       [1] apple - olma
       №1 apple - olma
       • apple - olma
    5. Misol gaplar:
       apple - olma (masalan: I ate an apple)
       apple - olma // I ate an apple
       apple — olma — He ate an apple.
    6. Probel bilan ajratilgan so'zlar:
       apple olma
       book kitob
       give up taslim bo'lmoq
    7. Ketma-ket (alternating) qatorlar:
       Line 1: apple
       Line 2: olma
    8. Jadvallar (.docx, .xlsx, .csv):
       Ustunlar: [№, EN, UZ, EX] yoki [EN, Transcription, UZ, EX]
"""
import re
import csv
from pathlib import Path

# Raqamlash va markerlarni tozalash (masalan: "1. ", "№1 ", "• ", "- ")
_LEADING_NUM_PATTERN = re.compile(
    r"^\s*(?:(?:№|no\.?|#)\s*\d+(?:[\.\)\-\]]|\s+)|\d+(?:[\.\)\-\]]|\s+)|\[\d+\]|[-*•>~–—])\s*",
    re.IGNORECASE,
)

# Fonetik transkripsiyalarni aniqlash: [ə'bændən] yoki /ə'bændən/
_TRANSCRIPTION_PATTERN = re.compile(r"(\[[^\]]+\]|/[^/]+/)")

# So'z turkumi belgilari: (v.), (n.), (adj.), (verb), (noun)
_POS_PATTERN = re.compile(
    r"\(\s*(?:v|n|adj|adv|prep|conj|pron|num|art|int|verb|noun|adjective|adverb|phr\.?\s*v\.?)\.?\s*\)",
    re.IGNORECASE,
)

# Jadvallardagi sarlavha (header) so'zlarini filtrlash
_HEADER_KEYWORDS = {
    "№", "no", "no.", "#", "num", "number", "id", "tartib",
    "english", "en", "word", "words", "so'z", "soz", "vocabulary", "term", "ibora",
    "uzbek", "uz", "tarjima", "translation", "meaning", "manosi", "ma'nosi", "izoh",
    "transcription", "phonetic", "ipa", "talaffuz", "transkripsiya",
    "pos", "part of speech", "turkum", "so'z turkumi",
    "example", "examples", "misol", "misollar", "sentence", "gap"
}


# Sarlavhalar va bo'lim nomlari (masalan: "Unit 1", "Lesson 2", "Chapter 3", "Mavzu 4")
_TITLE_PATTERN = re.compile(
    r"^(?:unit|lesson|chapter|part|module|topic|bosh|bob|mavzu|dars)\s*\d+.*$",
    re.IGNORECASE,
)


def clean_result(eng: str, uz: str, example: str = "", phonetic: str = "") -> tuple:
    """Inglizcha va o'zbekcha so'zlarni ortiqcha belgi va qo'shtirnoqlardan tozalaydi."""
    eng = re.sub(r"^[\"'\(\[]+|[\"'\]\)]+$", "", eng).strip()
    uz = re.sub(r"^[\"'\(\[]+|[\"'\]\)]+$", "", uz).strip()
    # O'zbekcha tarjima boshidagi tasodifiy ajratuvchilarni tozalash
    uz = re.sub(r"^[-–—:=~|>]\s*", "", uz).strip()

    # O'zbekcha qism ichida misol gap bo'lsa (masalan: "olma — He ate an apple")
    if "—" in uz and not example:
        u_parts = uz.split("—", 1)
        uz = u_parts[0].strip()
        example = u_parts[1].strip()
    elif "--" in uz and not example:
        u_parts = uz.split("--", 1)
        uz = u_parts[0].strip()
        example = u_parts[1].strip()

    if example:
        return eng, uz, example
    return eng, uz


def parse_line(raw_line: str) -> tuple | None:
    """Bitta qatordan (english, uzbek) yoki (english, uzbek, example) ni aqlli ajratadi."""
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None

    # Bo'lim sarlavhalarini o'tkazib yuborish (masalan: "Unit 1: Vocabulary")
    if _TITLE_PATTERN.match(line):
        return None

    # 1. Boshidagi raqamlash va markerlarni tozalash ("1. apple - olma" -> "apple - olma")
    line = _LEADING_NUM_PATTERN.sub("", line).strip()
    if not line:
        return None

    phonetic = ""
    example = ""

    # 2. Qavs ichidagi misol gaplarni ajratib olish: (masalan: ...) yoki (ex: ...)
    ex_match = re.search(r"\((?:masalan|misol|ex|example|e\.g\.?):?\s*([^)]+)\)", line, re.IGNORECASE)
    if ex_match:
        example = ex_match.group(1).strip()
        line = line[:ex_match.start()] + " " + line[ex_match.end():]
        line = line.strip()

    # 3. // bilan ajratilgan misol gap
    if "//" in line:
        parts = line.split("//", 1)
        line = parts[0].strip()
        if not example:
            example = parts[1].strip()

    # 4. So'z turkumlarini tozalash: (v.), (n.), (verb)
    line = _POS_PATTERN.sub(" ", line).strip()

    # 5. Transkripsiyalarni tekshirish: [ə'bændən] yoki /ə'bændən/
    trans_match = _TRANSCRIPTION_PATTERN.search(line)
    if trans_match:
        phonetic = trans_match.group(1).strip()
        before_trans = line[:trans_match.start()].strip()
        after_trans = line[trans_match.end():].strip()
        # Transkripsiyadan keyingi ajratuvchilarni tozalash
        after_trans_clean = re.sub(r"^\s*(?:[-–—:=~|>]|\s+)\s*", "", after_trans).strip()
        if before_trans and after_trans_clean:
            return clean_result(before_trans, after_trans_clean, example, phonetic)
        # Agar transkripsiya boshqa joyda bo'lsa, satrdan olib tashlaymiz
        line = line[:trans_match.start()] + " " + line[trans_match.end():]
        line = line.strip()

    # 6. Yuqori aniqlikdagi qat'iy ajratuvchilar: ->, =>, |, ;, =, :, ~, tab, 2+ probel
    strong_delims = [
        r"\s*(?:->|=>|-->|==>|→)\s*",
        r"\t+",
        r"\s{2,}",
        r"\s*\|\s*",
        r"\s*;\s*",
        r"\s*=\s*",
        r"\s*:\s*",
        r"\s*~\s*",
    ]
    for pattern in strong_delims:
        parts = re.split(pattern, line, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return clean_result(parts[0], parts[1], example, phonetic)

    # 7. Atrofida kamida bitta probel bo'lgan chiziqchalar (" - ", " -", "- ")
    # Bu "check-in", "well-known", "ice-cream" so'zlarining o'rtasidan bo'linib ketishining oldini oladi!
    dash_match = re.search(r"(?<=\S)\s+[-–—]\s+|\s+[-–—]\s*(?=\S)|(?<=\S)\s*[-–—]\s+", line)
    if dash_match:
        eng = line[:dash_match.start()].strip()
        uz = line[dash_match.end():].strip()
        if eng and uz:
            return clean_result(eng, uz, example, phonetic)

    # 8. Ehtiyotkor vergul ajratuvchisi (agar chap qism qisqa so'z bo'lsa)
    if "," in line:
        parts = line.split(",", 1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            words0 = parts[0].strip().split()
            if 1 <= len(words0) <= 4:
                return clean_result(parts[0], parts[1], example, phonetic)

    # 9. 3 qismli chiziqcha: "apple — olma — He ate an apple."
    parts_dash = re.split(r"\s*[-–—]\s*", line)
    if len(parts_dash) >= 3:
        eng = parts_dash[0].strip()
        uz = parts_dash[1].strip()
        ex = " ".join(parts_dash[2:]).strip()
        return clean_result(eng, uz, ex or example, phonetic)

    # 10. Hech qanday belgisiz, faqat probel bilan ajratilgan so'zlar
    # Masalan: "apple olma", "book kitob", "give up taslim bo'lmoq"
    words = line.split()
    if len(words) >= 2:
        first_word = words[0].strip(".,;:?!")
        if re.match(r"^[a-zA-Z\'-]+$", first_word):
            if len(words) == 2:
                return clean_result(words[0], words[1], example, phonetic)
            if len(words) >= 3:
                second_word = words[1].strip(".,;:?!")
                if re.match(r"^[a-zA-Z\'-]+$", second_word) and len(words) >= 4:
                    eng = f"{words[0]} {words[1]}"
                    uz = " ".join(words[2:])
                    return clean_result(eng, uz, example, phonetic)
                else:
                    eng = words[0]
                    uz = " ".join(words[1:])
                    return clean_result(eng, uz, example, phonetic)

    return None


def parse_cells(cells: list[str]) -> tuple | None:
    """Jadvallar (Docx, Excel, CSV) dagi kataklar qatorini intellektual tahlil qiladi."""
    cleaned = [c.strip() for c in cells if c and str(c).strip() and str(c).strip().lower() != "none"]
    if not cleaned:
        return None

    # Agar barcha kataklar sarlavha so'zlari bo'lsa, qatorni o'tkazib yuborish
    if all(c.lower() in _HEADER_KEYWORDS for c in cleaned):
        return None

    # Agar birinchi katak faqat tartib raqam bo'lsa (masalan "1", "№1", "2."), uni olib tashlaymiz
    if re.match(r"^\s*(?:№|no\.?|#)?\s*\d+\.?\s*$", cleaned[0], re.IGNORECASE):
        cleaned = cleaned[1:]

    if len(cleaned) < 2:
        if len(cleaned) == 1:
            return parse_line(cleaned[0])
        return None

    # Sarlavhani raqam olingandan keyin yana bir bor tekshirish
    if cleaned[0].lower() in _HEADER_KEYWORDS and cleaned[1].lower() in _HEADER_KEYWORDS:
        return None

    eng = cleaned[0]
    ex = ""

    if len(cleaned) == 2:
        uz = cleaned[1]
    elif len(cleaned) == 3:
        # Agar o'rta ustun transkripsiya yoki so'z turkumi bo'lsa
        if _TRANSCRIPTION_PATTERN.search(cleaned[1]) or _POS_PATTERN.search(f"({cleaned[1]})"):
            uz = cleaned[2]
        else:
            uz = cleaned[1]
            ex = cleaned[2]
    else:
        # 4 yoki undan ko'p ustunlar: [EN, Phonetics, UZ, EX] yoki [EN, UZ, EX, ...]
        if _TRANSCRIPTION_PATTERN.search(cleaned[1]) or _POS_PATTERN.search(f"({cleaned[1]})"):
            uz = cleaned[2]
            ex = cleaned[3] if len(cleaned) >= 4 else ""
        else:
            uz = cleaned[1]
            ex = cleaned[2]

    return clean_result(eng, uz, ex)


def parse_alternating_lines(lines: list[str]) -> list[tuple]:
    """Ketma-ket navbatma-navbat (1-qator: EN, 2-qator: UZ) yozilgan so'zlarni bog'laydi."""
    cleaned = [line.strip() for line in lines if line and line.strip() and not line.strip().startswith("#")]
    if len(cleaned) < 2:
        return []

    # Toq bo'lsa, oxirgi to'liqsiz qatorni kesib tashlash
    if len(cleaned) % 2 != 0:
        cleaned = cleaned[:-1]

    pairs = []
    temp_pairs = []
    is_valid = True

    for i in range(0, len(cleaned), 2):
        en = _LEADING_NUM_PATTERN.sub("", cleaned[i]).strip()
        uz = _LEADING_NUM_PATTERN.sub("", cleaned[i + 1]).strip()
        # Inglizcha so'z juda uzun bo'lib ketmasligi kerak (odatda 1-5 so'z)
        if not en or not uz or len(en.split()) > 6:
            is_valid = False
            break
        temp_pairs.append((en, uz))

    if is_valid and len(temp_pairs) >= 1:
        return temp_pairs
    return []


def parse_text_lines(lines: list[str]) -> list[tuple]:
    """Matn qatorlari ro'yxatini to'liq tahlil qilib juftliklar ro'yxatini qaytaradi."""
    pairs = []
    seen = set()

    for line in lines:
        parsed = parse_line(line)
        if parsed:
            key = parsed[0].lower()
            if key not in seen:
                seen.add(key)
                pairs.append(parsed)

    # Agar oddiy qatorlar bo'yicha deyarli hech narsa topilmasa, navbatma-navbat (alternating) rejimini tekshiramiz
    non_empty = [l.strip() for l in lines if l.strip()]
    if (len(pairs) == 0 or len(pairs) < len(non_empty) * 0.25) and len(non_empty) >= 2:
        alt_pairs = parse_alternating_lines(non_empty)
        if len(alt_pairs) > len(pairs):
            return alt_pairs

    return pairs


def parse_text(content: str) -> list[tuple]:
    """To'g'ridan-to'g'ri matn (nusxalangan / paste qilingan) ma'lumotlarini ajratadi."""
    if not content or not content.strip():
        return []
    return parse_text_lines(content.splitlines())


def read_text_safely(path: str | Path) -> str:
    """Turli xil kodlashlardagi (utf-8, cp1251, cp1254, latin-1, utf-16) fayllarni xatosiz o'qiydi."""
    path = Path(path)
    for enc in ("utf-8-sig", "utf-8", "cp1251", "cp1254", "latin-1", "utf-16"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_txt(path: str | Path) -> list[tuple]:
    """Matnli (.txt) fayllarni o'qiydi."""
    text = read_text_safely(path)
    return parse_text(text)


def parse_csv(path: str | Path) -> list[tuple]:
    """CSV fayllarni turli ajratuvchilar bilan xatosiz o'qiydi."""
    text = read_text_safely(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    # Delimiter aniqlash
    sample = "\n".join(lines[:10])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    pairs = []
    seen = set()
    reader = csv.reader(lines, delimiter=delimiter)
    for row in reader:
        if not row:
            continue
        parsed = parse_cells(row)
        if parsed:
            key = parsed[0].lower()
            if key not in seen:
                seen.add(key)
                pairs.append(parsed)

    # Agar CSV reader bilan kam so'z chiqsa, oddiy qator tahlili bilan to'ldiramiz
    if len(pairs) == 0:
        return parse_text(text)

    return pairs


def parse_docx(path: str | Path) -> list[tuple]:
    """Word (.docx) hujjatlaridagi jadvallar va paragraflardan so'zlarni ajratadi."""
    import docx

    doc = docx.Document(str(path))
    pairs = []
    seen = set()

    # 1. Jadvallarni o'qish
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            parsed = parse_cells(cells)
            if parsed:
                key = parsed[0].lower()
                if key not in seen:
                    seen.add(key)
                    pairs.append(parsed)

    # 2. Paragraflarni o'qish
    para_lines = []
    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        style_name = str(getattr(p.style, "name", "") or "").lower()
        if "heading" in style_name or "title" in style_name or "subtitle" in style_name:
            continue
        para_lines.append(txt)
        parsed = parse_line(txt)
        if parsed:
            key = parsed[0].lower()
            if key not in seen:
                seen.add(key)
                pairs.append(parsed)

    # Agar jadvallar bo'lmasa va oddiy qatordan kam chiqsa, navbatma-navbat tekshiramiz
    if not pairs and para_lines:
        pairs = parse_alternating_lines(para_lines)

    return pairs


def parse_xlsx(path: str | Path) -> list[tuple]:
    """Excel (.xlsx, .xls) jadvallaridan so'zlarni ajratadi."""
    import openpyxl

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    pairs = []
    seen = set()

    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            if not row:
                continue
            cells = [str(c).strip() for c in row if c is not None and str(c).strip() != "None"]
            if not cells:
                continue
            if len(cells) == 1:
                parsed = parse_line(cells[0])
            else:
                parsed = parse_cells(cells)

            if parsed:
                key = parsed[0].lower()
                if key not in seen:
                    seen.add(key)
                    pairs.append(parsed)

    wb.close()
    return pairs


def parse_pdf(path: str | Path) -> list[tuple]:
    """PDF (.pdf) hujjatlaridan matnni ajratib olib so'zlarni tahlil qiladi."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    lines = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            lines.extend(text.splitlines())

    return parse_text_lines(lines)


def parse_file(path: str | Path) -> list[tuple]:
    """Fayl kengaytmasiga qarab tegishli tahlilchini ishga tushiradi."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fayl topilmadi: {path}")

    suffix = path.suffix.lower()
    if suffix == ".txt":
        return parse_txt(path)
    elif suffix == ".csv":
        return parse_csv(path)
    elif suffix == ".docx":
        return parse_docx(path)
    elif suffix in (".xlsx", ".xlsm", ".xltx"):
        return parse_xlsx(path)
    elif suffix == ".pdf":
        return parse_pdf(path)
    else:
        # Boshqa noma'lum fayllar uchun xavfsiz matn sifatida o'qishga urinish
        try:
            return parse_txt(path)
        except Exception:
            raise ValueError(
                f"Qo'llab-quvvatlanmaydigan fayl turi: {suffix} "
                "(.txt, .csv, .docx, .xlsx yoki .pdf kerak)"
            )
