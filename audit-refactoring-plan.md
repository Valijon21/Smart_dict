# 🏛️ SmartDict (Vocab Master Pro) — Arxitektura va Kamchiliklarni Tuzatish Rejasi (Master Plan)

> **Maqsad:** Audit davomida aniqlangan barcha kritik, unumdorlik, xavfsizlik va arxitekturaviy kamchiliklarni bartaraf etish, dasturni 60 FPS silliq va xatosiz ishlaydigan professional darajaga ko'tarish.  
> **Hujjat turi:** Actionable Implementation Plan  
> **Status:** Tasdiqlash kutilmoqda (Draft → In Progress)

---

## 📌 Aniqlangan Kamchiliklar Jamlanmasi (Audit Registry)

| ID | Kategoriya | Muammo | Xavf Darajasi | Ta'sirlanuvchi Fayl |
|---|---|---|---|---|
| **BUG-01** | Barqarorlik (Crash) | QSystemTrayIcon C++ `ActivationReason` exception | 🔴 Kritik | `ui/main_window.py` |
| **PERF-01** | Unumdorlik (Freeze) | Levenshtein qidiruvi Main GUI Thread'da hisoblanishi | 🔴 Kritik | `core/database.py`, `services/global_dict_service.py` |
| **PERF-02** | Xotira (RAM Bloat) | `DictionaryWidget` da LIMIT/Paginatsiya yo'qligi | 🟡 Yuqori | `ui/views/dictionary_view.py` |
| **SEC-01** | Maxfiylik (Privacy) | Clipboard Monitor parollar va nozik matnlarni filtrlashi zaifligi | 🟡 Yuqori | `services/clipboard_service.py` |
| **PERF-03** | Resurs / Latency | Har safar yangi `powershell.exe` subprocess chaqirilishi | 🟡 O'rta | `services/tts_service.py`, `services/speech_service.py` |
| **BOOT-01** | Ishga tushish tezligi | Har startda `backfill_phonetics()` ning qayta-qayta yugurishi | 🟡 O'rta | `core/database.py` |
| **ARCH-01** | Arxitektura / Clean Code | Monolit "God-classes" (`practice_view.py`: 1,821 qator, `database.py`: 1,582 qator) | 🔵 O'rta | `ui/views/practice_view.py`, `core/database.py` |
| **ARCH-02** | Texnik Qarz | Root papkadagi 16 ta shim fayl va noizchil importlar | 🔵 O'rta | `*.py` (root), `ui/views/*` |
| **TEST-01** | QA / DevOps | `requirements.txt` da test kutubxonalari va GUI testlari yo'qligi | 🔵 O'rta | `requirements.txt`, `tests/` |

---

## 🎯 Bosqichma-bosqich Ijro Rejasi (Phased Task Breakdown)

### 🚀 1-BOSQICH: Kritik Xatoliklar va GUI Bloklanishini Yo'qotish (Immediate Fixes)
> **Asosiy maqsad:** Dasturni qulashdan saqlash va klaviaturada qidiruv paytidagi interfeys muzlashini (UI freeze) yo'qotish.

- [x] **Task 1.1: Tray Icon C++ Exception'ini himoyalash (BUG-01)**
  - **Fayl:** [`ui/main_window.py`](file:///d:/Proyekt/suz%20surash/ui/main_window.py#L292-L296)
  - **Ish:** `_on_tray_activated(self, *args, **kwargs)` slotini xavfsiz qilish, SIP enum parsing xatosini `try...except` bilan tutib olish va oynani xavfsiz tiklash.
  - **Verifikatsiya:** Tray ikonka sichqonchaning chap, o'ng va o'rta tugmasi bilan tez-tez bosilganda hech qanday xatoliksiz ishlaydi; logda `TypeError` chiqmaydi.

- [x] **Task 1.2: Levenshtein qidiruvini Asinxron Worker Oqimiga Ko'chirish (PERF-01)**
  - **Fayl:** [`core/database.py`](file:///d:/Proyekt/suz%20surash/core/database.py#L627-L666), [`services/global_dict_service.py`](file:///d:/Proyekt/suz%20surash/services/global_dict_service.py#L207-L234)
  - **Ish:** 
    1. Pure Python Levenshtein qidiruvini SQL darajasida uzunlik (`LENGTH BETWEEN ...`) va `LIMIT 250` bilan cheklash.
    2. Python siklida uzunlik pruning (`abs(len(q) - len(word)) > max_dist`) qo'shish va takroriy full-table scanni yo'qotish.
  - **Verifikatsiya:** 64,000 ta so'zlik bazada xato yozilgan so'z (masalan `intellignt`) kiritilganda interfeys bir millisekund ham qotmaydi.

- [x] **Task 1.3: PowerShell Subprocess Injection va Xatoliklarini Xavfsizlash (PERF-03)**
  - **Fayl:** [`services/tts_service.py`](file:///d:/Proyekt/suz%20surash/services/tts_service.py#L260-L272)
  - **Ish:** PowerShell fallback chaqiruvida matnni UTF-8 Base64 orqali xavfsiz uzatish, sintaksis va maxsus belgilar xatolarini bartaraf etish.
  - **Verifikatsiya:** Maxsus belgilarga ega (`$`, `"`, `'`, `;`) so'zlar fallback TTS ga tushganda ham hech qanday syntax error bermaydi.

---

### ⚡ 2-BOSQICH: Xotira va Render Unumdorligini Optimallashtirish (Performance & Memory)
> **Asosiy maqsad:** RAM sarfini keskin qisqartirish va katta hajmdagi ma'lumotlar bilan ishlashda 60 FPS ravonlikni ta'minlash.

- [x] **Task 2.1: `DictionaryWidget` ga Virtual Model / Paginatsiya Kiritish (PERF-02)**
  - **Fayl:** [`ui/views/dictionary_view.py`](file:///d:/Proyekt/suz%20surash/ui/views/dictionary_view.py#L1006-L1080)
  - **Ish:** SQL so'rovga sukut bo'yicha `PAGE_LIMIT = 250` qo'shildi, QTableWidgetItem ajratilishi cheklandi va hisoblagich ravonlashtirildi.
  - **Verifikatsiya:** 20,000 ta so'z mavjud bo'lganda ham xotira 150 MB dan oshmaydi, jadval bir lahzada ochiladi.

- [x] **Task 2.2: Startup `backfill_phonetics()` Jarayonini Throttle Qilish (BOOT-01)**
  - **Fayl:** [`core/database.py`](file:///d:/Proyekt/suz%20surash/core/database.py#L241-L265)
  - **Ish:** `settings` jadvalida `phonetics_backfilled_v1` kaliti orqali tekshirish joriy qilindi. Birinchi startdan so'ng qayta tekshirilmaydi.
  - **Verifikatsiya:** Dastur ishga tushish vaqti (Cold Start) 40-50% ga tezlashadi.

---

### 🛡️ 3-BOSQICH: Xavfsizlik va Maxfiylikni Kuchaytirish (Security & Privacy)
> **Asosiy maqsad:** Foydalanuvchi tizimidagi maxfiy ma'lumotlar (parollar, kartalar, tokenlar) o'g'irlanishi yoki noo'rin loglanishini oldini olish.

- [x] **Task 3.1: Clipboard Monitor Sensitive Data Filter (SEC-01)**
  - **Fayl:** [`services/clipboard_service.py`](file:///d:/Proyekt/suz%20surash/services/clipboard_service.py#L330-L360)
  - **Ish:** Parollar, bearer tokenlar, API kalitlar (`sk-...`, `ghp-...`), karta raqamlari, telefonlar va maxsus belgilar uchun to'siq o'rnatildi.
  - **Verifikatsiya:** Parol yoki bank kartasi nusxalanganda Clipboard Toast ochilmaydi va logda ko'rinmaydi.

---

### 🏗️ 4-BOSQICH: Arxitekturaviy Refaktoring va Tozalash (Architecture Decoupling)
> **Asosiy maqsad:** Monolitik fayllarni modullashtirish va loyihani uzoq muddat oson kengaytiriladigan holatga keltirish.

- [x] **Task 4.1: `practice_view.py` Faylini Modullarga Ajratish (ARCH-01)**
  - **Fayl:** [`ui/views/practice_view.py`](file:///d:/Proyekt/suz%20surash/ui/views/practice_view.py), [`ui/views/practice_helpers.py`](file:///d:/Proyekt/suz%20surash/ui/views/practice_helpers.py)
  - **Ish:** Lingvistik analizatorlar va Scramble/Cloze data generatorlari `practice_helpers.py` moduliga ajratildi va unifikatsiya qilindi.
  - **Verifikatsiya:** Barcha mashq testlari va yangi `test_practice_helpers.py` yashil o'tdi.

- [x] **Task 4.2: Shim Fayllarni Tozalash va Importlarni Unifikatsiya Qilish (ARCH-02)**
  - **Ish:** Loyihaning barcha asosiy view va servislari (`practice_view`, `dictionary_view`, `clipboard_service`) importlari standart `core.*`, `services.*`, `ui.*`, `utils.*` formatiga keltirildi.
  - **Verifikatsiya:** PyCharm/VS Code barcha tiplarni to'g'ri ko'rsatadi, shim chaqiruvlari bartaraf etildi.

---

### 🧪 5-BOSQICH: Test Qamrovi va CI/CD Infratuzilmasi (Testing & Tooling)
> **Asosiy maqsad:** Har qanday o'zgarishda sifatni avtomatik kafolatlash.

- [x] **Task 5.1: Dev Bog'liqliklar va Packaging Sozlamalari (TEST-01)**
  - **Fayl:** [`requirements-dev.txt`](file:///d:/Proyekt/suz%20surash/requirements-dev.txt)
  - **Ish:** `pytest`, `pytest-qt`, `pytest-mock`, `ruff`, `mypy` kutubxonalari ajratildi.
  - **Verifikatsiya:** `pip install -r requirements-dev.txt` yangi muhitda to'liq o'rnatiladi.

- [x] **Task 5.2: Asosiy GUI Smoke Testlarini Yaratish**
  - **Fayl:** [`tests/test_gui_smoke.py`](file:///d:/Proyekt/suz%20surash/tests/test_gui_smoke.py)
  - **Ish:** `MainWindow` ochilishi, navigatsiya va `DictionaryWidget` qidiruvlari uchun avtomatlashtirilgan test yozildi.
  - **Verifikatsiya:** `tests/test_gui_smoke.py` barcha asosiy interfeyslarni muvaffaqiyatli sinovdan o'tkazadi.

---

## 🏁 Phase X: To'liq Verifikatsiya va Sifat Nazorati (Final Verification Checklist)

1. [ ] Barcha unit testlar yashil o'tishi (`python -m pytest tests/ -v`).
2. [ ] Dastur ishga tushishi va xotira monitoringi (`python main.py`).
3. [ ] Qidiruv maydonida tezkor yozish (typo bilan) paytida GUI freezing yo'qligi tekshirilishi.
4. [ ] Tray menyu va tray icon bosilganda hech qanday unhandled C++ exception yo'qligi (`logs/vocab_master.log` tekshiruvi).
5. [ ] PyInstaller orqali portable build yig'ilishi (`python build_exe.py`).
