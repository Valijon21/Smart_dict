# Vocab Master Pro — Professional Lug'at va Intellektual Trenajyor

Ingliz tili so'z boyligini kengaytirish, mustahkamlash va eslab qolish uchun yaratilgan 100% oflayn, zamonaviy desktop ilova (Windows).

---

## 🌟 Asosiy Imkoniyatlar

1. **Intellektual Mashq Rejimlari (Spaced Repetition & Leitner):**
   - ✍️ **Yozma mashq (Typing):** So'zning to'liq yozilishini xotirada mustahkamlash.
   - 🎯 **4 ta Variantli test (Multiple Choice):** Tezkor intuitsiyani rivojlantirish.
   - 🎴 **Anki uslubidagi Flashcard:** O'zini-o'zi baholash (Qiyin / Yaxshi / Oson).
   - 🎧 **Eshitib yozish (Listening Dictation):** Ovozli talaffuzni eshitib so'zni yozish.
   - 🔤 **Harf terish (Word Scramble / Anagram):** Harflarni tartib bilan terish orqali orfografiyani o'rganish.

2. **Oflayn Audio Talaffuz (TTS):**
   - Windows SAPI5 (win32com) orqali yashin tezligida, internetga ulanmasdan toza ona tili talaffuzi.
   - Zaxira pyttsx3 va PowerShell System.Speech integratsiyasi.

3. **🎨 6 ta Zamonaviy Vizual Mavzu (Theme Switcher):**
   - **Midnight Indigo:** Chuqur tungi binafsha-ko'k.
   - **Cyberpunk Neon:** Futuristik elektrik moviy va fuksiya.
   - **Emerald Forest:** Sokin quyuq zumrad yashil.
   - **Warm Sunset:** Issiq qahva, espresso va amber.
   - **OLED Pure Black:** Mutlaq qora (#000000) energiya tejamkor fon.
   - **Nordic Ocean:** Shimoliy qutb va chuqur okean moviyligi.

4. **📚 Aqlli O'qish Rejimi (Smart Reader):**
   - A2, B1, B2 darajasidagi saralangan hikoyalar yoki shaxsiy matnlar.
   - Matndagi siz bilgan so'zlar avtomatik moviy rangda yoritiladi.
   - Istalgan so'z ustiga bosganda: tarjima, misol gap, audio va 1-bosishda bazaga qo'shish.

5. **🏆 Gamifikatsiya (XP, Darajalar, Yutuqlar):**
   - Har bir to'g'ri javob uchun XP ballari, 5 ta daraja unvoni (Boshlovchi → Poliglot → So'z Ustasi).
   - 8 ta maxsus unvon va nishonlar (Snayper, Olov uchquni, Kutubxonachi va hk.).

6. **⚡ Tezkor So'z Qo'shish (Quick Capture Stay-on-top):**
   - Brauzer yoki kitob o'qiyotganda `Ctrl+Shift+A` yoki `Ctrl+Shift+V` bosib, dasturni ochmasdan tezda yangi so'zni bazaga saqlash.

7. **⚠️ Zaif So'zlar Karantini (Smart Error Bank):**
   - Foydalanuvchi eng ko'p xato qilgan so'zlarni alohida aniqlab, qayta takrorlatish filtri.

8. **📦 Saralangan So'z To'plamlari (Curated Word Packs):**
   - Oltin 100 ta so'z, IELTS 7.5+ Academic, IT & Software Engineering to'plamlari. Barcha so'zlar tarjimasi va misol gapi (example) bilan ta'minlangan.

9. **🛡️ SQLite WAL & Yuqori Ishonchlilik:**
   - Write-Ahead Logging (WAL) rejimi va xavfsiz zaxira (Backup/Restore).
   - JSON va CSV eksport (Excel bilan UTF-8-BOM to'liq mos).

---

## 🚀 Ishga Tushirish (Development)

```powershell
# Virtual muhitni faollashtirish
.\venv\Scripts\activate

# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# Dasturni ishga tushirish
python main.py
```

---

## 📁 Loyiha Strukturasi

```
VocabMaster/
├── main.py                  # Ilovaning kirish nuqtasi va Single Instance Guard
├── database.py              # SQLite WAL qatlami, Leitner algoritmi, indekslar va statistika
├── tts.py                   # Oflayn TTS audio drayveri (SAPI5 + pyttsx3)
├── importer.py              # .txt, .csv va .docx aqlli parseri
├── gamification.py          # XP ballari, darajalar va yutuqlar tizimi
├── sound_effects.py         # Toza sinus to'lqinli sintetik audio effektlar
├── theme_manager.py         # 6 ta vizual mavzular boshqaruvi
├── word_packs.py            # Saralangan lug'at to'plamlari
├── reader_data.py           # Aqlli o'qish uchun hikoyalar korpusi
├── logger.py                # Aylanuvchi faylli log tizimi
├── ui/
│   ├── main_window.py       # Asosiy oyna, sidebar, system tray va taymerlar
│   ├── dashboard.py         # Analitika, progress va QPainter grafiklari
│   ├── dictionary.py        # Lug'at jadvali, 160ms debounce qidiruv, audio
│   ├── practice.py          # 5 xil mashq trenajyori (Yozma, Test, Karta, Audio, Scramble)
│   ├── reader.py            # Aqlli o'qish va so'z inspektori
│   ├── import_dialog.py     # Fayl importi (.txt/.csv/.docx) va tezkor mashq
│   ├── settings_page.py     # Kunlik reja, mavzular, audio va zaxira sozlamalari
│   ├── quick_capture.py     # Stay-on-top tezkor kiritish modali
│   ├── achievements_dialog.py # Yutuqlar va nishonlar modali
│   └── word_packs_dialog.py # Tayyor to'plamlar kartalari
└── VocabMaster.spec         # PyInstaller konfiguratsiya fayli
```
