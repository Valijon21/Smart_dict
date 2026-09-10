# CODEBASE.md — SmartDict (Vocab Master Pro)

> AI yordamchi uchun loyiha arxitekturasi, qatlamlar va fayl bog'liqliklari haritasi.
> Har sessiyada codebase'ni qayta tahlil qilmaslik uchun bu faylni birinchi o'qing.

---

## 📌 Loyiha haqida

**SmartDict** — Python 3.11 + PyQt6 asosida qurilgan Windows desktop ilovasi.
- 100% oflayn; internet kerak emas
- SQLite WAL rejimi; bitta `vocab.db` fayl
- SuperMemo SM-2 + Leitner 5-quti algoritmlari
- SAPI5 TTS (pywin32 orqali)

---

## 🗂️ Arxitektura — Qatlamlar

```
SmartDict/
├── core/           ← Biznes logikasi (DB, algoritmlar, gamification)
├── services/       ← Core'ni UI ga ko'prik qiluvchi service qatlami
├── ui/             ← PyQt6 widgetlari va viewlari
│   ├── views/      ← Asosiy sahifalar (MainWindow ga embed bo'ladi)
│   ├── dialogs/    ← Modal oynalar
│   ├── games/      ← O'yin widgetlari
│   └── components/ ← Qayta ishlatiladigan kichik widgetlar
├── utils/          ← Yordamchi funksiyalar (import, logging, qidiruv)
├── tests/          ← pytest smoke testlar
└── *.py (root)     ← Backward-compat shim fayllar (sys.modules trick)
```

---

## 🧩 Fayl Bog'liqliklari (Dependency Map)

### Shim Pattern (Muhim!)
Root papkasidagi kichik `.py` fayllar (masalan `database.py`, `tts.py`)
**faqat redirect** qiladi — haqiqiy logika `core/` yoki `services/` da:

```python
# Root database.py (217 bytes)
import sys, importlib
_impl = importlib.import_module("core.database")
sys.modules[__name__] = _impl
```

Bu `97` ta `import database as db` chaqiriqni buzmasdan arxitektura o'zgartirishga imkon beradi.

**Shim fayllar ro'yxati (root):**
| Shim fayl | Haqiqiy modul |
|-----------|--------------|
| `database.py` | `core/database.py` |
| `tts.py` | `services/tts_service.py` |
| `phonetics.py` | `core/phonetics.py` |
| `gamification.py` | `core/gamification.py` |
| `daily_quests_service.py` | `services/daily_quests_service.py` |
| `cefr_service.py` | `services/cefr_service.py` |
| `clipboard_monitor.py` | `services/clipboard_service.py` |
| `global_dict_service.py` | `services/global_dict_service.py` |
| `importer.py` | `utils/importer.py` |
| `logger.py` | `utils/logger.py` |
| `reader_data.py` | `utils/reader_data.py` |
| `sound_effects.py` | `services/sound_effects.py` |
| `text_search_utils.py` | `utils/text_search_utils.py` |
| `theme_manager.py` | `ui/theme_manager.py` |
| `topic_service.py` | `services/topic_service.py` |
| `word_packs.py` | `core/word_packs.py` |

---

## 📂 Modullar Tavsifi

### `core/` — Biznes logikasi
| Fayl | Vazifasi | Hajm |
|------|----------|------|
| `database.py` | SQLite CRUD, SM-2 review, SQL injection whitelist | 56KB |
| `phonetics.py` | IPA transkripsiya lug'ati, POS inference | 45KB |
| `word_packs.py` | CEFR/IELTS/topik so'z to'plamlari | 48KB |
| `gamification.py` | XP tizimi, darajalar, yutuqlar (badges) | 8KB |
| `daily_quests.py` | Kunlik missiyalar, battle pass, bonus | 10KB |
| `retention_analytics.py` | SM-2 eslab qolish analitikasi, kesh | 8KB |

### `services/` — Service qatlami
| Fayl | Vazifasi | Hajm |
|------|----------|------|
| `tts_service.py` | TTS: SAPI5 (Windows) + pyttsx3 fallback | 24KB |
| `speech_service.py` | Mikrofon, talaffuz tekshirish | 23KB |
| `global_dict_service.py` | Cambridge/Oxford lug'at API (oflayn JSON) | 16KB |
| `topic_service.py` | Topik so'zlar servisi, filtr, qidiruv | 27KB |
| `cefr_service.py` | CEFR/IELTS darajali so'zlar boshqaruvi | 19KB |
| `sound_effects.py` | WAV yaratish (standart lib: wave, math, struct) | 5KB |
| `clipboard_service.py` | Clipboard kuzatuvchi, avtomatik qo'shish | 16KB |
| `game_word_provider.py` | O'yinlar uchun so'z manba selektori | 12KB |

### `ui/views/` — Asosiy sahifalar
| Fayl | Sahifa | Hajm |
|------|--------|------|
| `dashboard_view.py` | Dashboard, statistika, streak | 75KB |
| `practice_view.py` | 6 ta mashq rejimi (typing, MC, flashcard...) | 75KB |
| `dictionary_view.py` | Lug'at, CRUD, import/eksport | 55KB |
| `audio_player_view.py` | Hands-free audio pleyer | 44KB |
| `topic_words_view.py` | Topik va CEFR so'zlari sahifasi | 31KB |
| `reader_view.py` | Aqlli matn o'quvchi | 29KB |
| `settings_view.py` | Sozlamalar | 36KB |

### `ui/games/` — O'yin widgetlari
| Fayl | O'yin |
|------|-------|
| `blitz_game.py` | ⚡ Blitz Marathon (60 soniya) |
| `match_game.py` | 🧩 Word Match (juftlik topish) |
| `crossword_game.py` | 📝 Krossvord |
| `word_fall_game.py` | 🎮 Word Fall |

### `ui/dialogs/` — Modal oynalar
| Fayl | Dialog |
|------|--------|
| `spotlight_search_dialog.py` | 🔍 Spotlight (Ctrl+F) aqlli qidiruv |
| `word_packs_dialog.py` | 📦 So'z paketlar do'koni |
| `import_dialog.py` | 📂 CSV/TXT import |
| `quick_capture_dialog.py` | ⚡ Tezkor so'z qo'shish |
| `achievements_dialog.py` | 🏆 Yutuqlar oynasi |
| `worksheet_dialog.py` | 🖨️ Printable worksheets |

### `ui/components/` — Qayta ishlatiladigan widgetlar
| Fayl | Vazifasi |
|------|----------|
| `mini_widget.py` | Fon rejimidagi mini widget (system tray) |
| `daily_quests_widget.py` | Kunlik missiyalar paneli |
| `game_source_selector.py` | O'yin uchun so'z manba tanlash |

### `utils/` — Yordamchilar
| Fayl | Vazifasi |
|------|----------|
| `text_search_utils.py` | Kirill↔Lotin, apostrof, ko'p bosqichli ranking |
| `logger.py` | Strukturlangan logging, `app_dir` aniqlash |
| `importer.py` | CSV/TXT so'z import logikasi |
| `reader_data.py` | Matn o'quvchi uchun hikoyalar ma'lumoti |

---

## 🗄️ Ma'lumotlar Bazasi Sxemasi

```sql
words        -- english (UNIQUE NOCASE), uzbek, source, example, phonetic, part_of_speech, status, created_at
progress     -- word_id FK, correct_count, wrong_count, box_level, ease_factor, interval_days, repetitions, next_review
daily_stats  -- date (PK), practiced, correct, wrong, new_words_added
settings     -- key (PK), value  [daily_goal, tts_rate, user_xp, daily_quests_state, ...]
achievements -- id (PK), title, description, icon, category, unlocked_at, progress, max_progress
```

**DB joylashuvi:** `vocab.db` dastur yonida (portable).
**SQL Injection:** `_safe_order_by()` + `_ALLOWED_ORDER_BY` frozenset whitelist.

---

## 🧪 Test Qamrovi

```
tests/
├── test_database.py      — 29 test: CRUD, SM-2, SQL whitelist, backup
├── test_phonetics.py     — 27 test: IPA, POS, suffix inference
├── test_search.py        — 20 test: Kirill↔Lotin, apostrof, ranking
├── test_gamification.py  — 27 test: XP, darajalar, yutuqlar
└── test_daily_quests.py  — 33 test: quest lifecycle, bonus, summary
```

**Jami: 136 test | Barcha green | ~3.5s**

```bash
# Barcha testlarni ishga tushirish
python -m pytest tests/ -v
```

**Fixture pattern:** `core.database.DB_PATH` ni vaqtinchalik faylga almashtiramiz.
`monkeypatch.setenv` ishlamaydi — `_determine_db_path()` env o'zgaruvchisini tekshirmaydi.

---

## 🔑 Muhim Konventsiyalar

1. **Yangi funksiya** → `core/` ga yozing, kerak bo'lsa `services/` da re-export qiling
2. **Root shim fayllari** → hech qachon o'zgartirmang (backward compat)
3. **SQL injection** → yangi `ORDER BY` ustun qo'shsangiz `_ALLOWED_ORDER_BY` ga ham qo'shing
4. **Katta o'zgarish** → alohida branch oching (loyiha qoidasi)
5. **Yangi test** → `core.database.DB_PATH` fixture patternini ishlating
6. **Loglash** → `get_logger("modul_nomi")` dan foydalaning, `print()` emas

---

## 🏗️ Kirish nuqtasi

```bash
python main.py          # Dasturni ishga tushirish
python -m pytest tests/ # Barcha testlar
python build_exe.py     # PyInstaller EXE yaratish
```

`main.py` → `ui/main_window.py` (MainWindow) → Views lazy load qilinadi.
