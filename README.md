# 🚀 SmartDict — Vocab Master Pro

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyQt6 / PySide6](https://img.shields.io/badge/GUI-PyQt6%20%2F%20PySide6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![SQLite3](https://img.shields.io/badge/Database-SQLite%20WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![FSRS-5](https://img.shields.io/badge/FSRS-v5%20Spaced%20Repetition-7C3AED?style=for-the-badge)
![Speech](https://img.shields.io/badge/Speech-Recognition%20&%20Evaluation-059669?style=for-the-badge)
![Irregular Verbs](https://img.shields.io/badge/Verbs-115%20Irregular%20Verbs-E11D48?style=for-the-badge)
![TTS Engine](https://img.shields.io/badge/TTS-Offline%20SAPI5-FF6F00?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%20Desktop-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**Ingliz va O'zbek tillari uchun professional, 100% oflayn intellektual lug'at, FSRS v5 (Anki 24+) xotira algoritmi, Speaking talaffuz trenajyori va audio o'rganish platformasi.**

*A commercial-grade, fully offline desktop English-Uzbek vocabulary mastery suite powered by Anki 24 FSRS v5, SuperMemo SM-2, Leitner 5-Box progression, offline speech recognition, and native audio synthesis.*

[Imkoniyatlar](#-imkoniyatlar-key-features) • [Yangilanishlar](#-songgi-yangilanishlar--ozgarishlar-latest-updates--changelog) • [O'rnatish](#-ornatish-va-ishga-tushirish-quickstart) • [Loyiha Strukturasi](#-loyiha-strukturasi-architecture) • [EXE Yaratish](#-standalone-exe-yaratish) • [Muallif](#-muallif-va-litsenziya)

---

</div>

## 📖 Loyiha Haqida (Overview)

**SmartDict (Vocab Master Pro)** — ingliz tilini mustaqil, tizimli va ilmiy asoslangan zamonaviy usullar bilan o'rganuvchilar uchun yaratilgan professional Windows desktop ilovasi. 

Ilova internetga ulanmasdan (**100% Offline**) ishlaydi, xotirada uzoq muddat saqlash uchun eng so'nggi **FSRS v5 (Free Spaced Repetition Scheduler)** va **Leitner 5-quti** algoritmlaridan foydalanadi, mikrofondan talaffuzni aniq baholovchi **Speaking Trenajyori**, 6 xil mashq rejimiga ega **115 ta Noto'g'ri Fe'llar (Irregular Verbs)** moduli, fon rejimida eshitib yodlash uchun **Hands-Free Audio Pleyer**, chop etiladigan vedomostlar (**Printable Worksheets**) va ko'zni charchatmaydigan 8 xil zamonaviy dizayn mavzulariga ega.

---

## 🌟 Imkoniyatlar (Key Features)

### 1. 🎧 Hands-Free Audio Pleyer (Fon Rejimida Eshitib Yodlash)
- **Ekran va Audio 100% Sinxron:** Ekranda ko'rsatilgan so'z bilan quloqchinda yangrayotgan talaffuz hech qachon adashmaydi.
- **Oraliq Pauza (Interval):** Har bir so'zdan keyin 1.0s dan 8.0s gacha sozlanuvchi pauza beriladi, foydalanuvchi so'z tarjimasini o'z xotirasida tiklashiga imkon beradi.
- **Filtrlar va Rejimlar:** Barcha so'zlar, Bugun takrorlanadigan (SM-2), Zaif so'zlar yoki yangi o'rganilayotganlar bo'yicha saralash.
- **Tugmalar:** Keyingi/Oldingi (0ms kechikish bilan ekranda aks etish), Tasodifiy (Shuffle), Takrorlash (Loop) va animatsion Audio Vizualizator.

### 2. 🧠 Ilmiy Xotira Algoritmlari (FSRS v5 & SM-2 & Leitner)
- **Anki 24+ FSRS v5 Algoritmi:** Zamonaviy *Free Spaced Repetition Scheduler*. Inson xotirasining Ebbinghaus egri chizig'i $R = (1 + \text{FACTOR} \cdot t / S)^{-\text{DECAY}}$ formulasi asosida har bir so'z uchun mustaqil Barqarorlik ($S$, kunlarda) va Qiyinlik ($D$, 1-10) parametrlarini yuritadi. So'zlarni 30-40% kamroq takrorlab 90%+ eslab qolish darajasini kafolatlaydi.
- **Silliq Migratsiya (Zero Data Loss):** Baza ishga tushganda eski SuperMemo SM-2 ma'lumotlari (`ease_factor`, `interval_days`, `repetitions`) avtomatik tarzda FSRS parametrlariga o'tkaziladi.
- **5 Qutili Leitner Tizimi:** So'zlar qutilar (Box 1 → Box 5) bo'ylab harakatlanadi; to'g'ri javob oldinga siljitadi, xato javob esa 1-qutiga qaytaradi.
- **Zaif So'zlar Banki (Error Quarantine):** Foydalanuvchi eng ko'p xato qilgan so'zlar avtomatik karantin ro'yxatiga olinadi.

### 3. 🎮 Interaktiv O'yinlar (Gamified Learning)
- ⚡ **Blitz Marathon:** 60 soniyali tezkor so'z marafoni. Ketma-ket to'g'ri javoblar uchun Combo Multiplier (x1.5, x2.0, x3.0), hayotlar soni va shaxsiy rekordlar jadvali.
- 🧩 **Word Match Game:** 4x4 va 6x6 katakli so'z va tarjima juftliklarini topish o'yini. Interaktiv kartochkalar, yorqin vizual effektlar va g'alaba fanfarlari.

### 4. ✍️ 6 Xil Maxsus Mashq Trenajyori (Professional Tizim)
- **6 ta Interaktiv Rejim:**
  1. **Yozma Mashq (Typing):** So'zning to'g'ri orfografiyasini klaviaturada terish orqali xotirada muhrlash.
  2. **4 Variantli Test (Multiple Choice):** Tezkor assotsiativ xotira va reflekslarni rivojlantirish.
  3. **Anki Uslubidagi Flashcard:** O'zini xolis baholash (*Qayta / Qiyin / Yaxshi / Oson*).
  4. **Eshitib Yozish (Listening Dictation):** Ovozli talaffuzni eshitib, so'zni to'g'ri yozish.
  5. **Harf Terish (Word Scramble):** Chalkash harflarni to'g'ri ketma-ketlikda yig'ish.
  6. **Bo'sh Joyni To'ldirish (Cloze / Sentence Completion):** Gap kontekstida yashirilgan so'zni topish (CEFR/IELTS uslubi, 1-harf maslahati bilan).
- **🛡️ 100% Sessiya Saqlanishi (State Persistence):** Mashq paytida boshqa bo'limlarga (`Dashboard`, `Lug'at`, `O'quvchi`, `Sozlamalar`) o'tib qaytganda sessiya noldan boshlanmaydi; to'xtagan so'z, qolgan navbat va to'plangan statistika to'liq saqlanadi (`resume_session()`).
- **⏸️ 2-Enter Mexanizmi:** Xato kiritilganda dastur avtomatik keyingi so'zga sakrab ketmaydi. 1-Enter javobni tekshiradi, to'g'ri javobni yorqin ko'rsatadi, misol va tarjimani o'qish imkonini beradi. Yana bir bor 2-Enter (yoki "Davom etish") bosilgandagina keyingi so'zga o'tadi (Qt debounce himoyasi bilan).
- **🔍 Harfma-harf Visual Diff & Typo Detektori:** Xato kiritilganda Levenshtein masofasi hisoblanadi. Agar 1-2 ta harfda adashilgan bo'lsa (`💡 Deyarli to'g'ri!`), foydalanuvchi kiritgan noto'g'ri harflar qizil o'chirilgan (`~~harf~~`), to'g'ri harflar yashil chizilgan (`<u>harf</u>`) holda ko'rsatiladi.
- **🐢 Sekin Talaffuz (0.75x Slow Speech):** Asosiy `🔊` karnay yonidagi `🐢` tugmasi uzun va murakkab inglizcha so'zlarni bo'g'inma-bo'g'in sekin tinglash imkonini beradi.
- **🎯 Partiya Xatolari Ustida Qayta Ishlash:** Partiya yakunida faqat xato qilingan so'zlardan iborat maxsus mashqni 1-bosish bilan boshlash imkoniyati (`retry_mistakes_btn`).
- **📳 Duolingo Uslubidagi Karta Silkinishi (Shake Animation):** Xato javob berilganda asosiy karta 300ms davomida mayin chap-o'ng silkinadi (`QPropertyAnimation`).

### 5. 📚 Aqlli Matn O'quvchi (Smart Reader)
- A2, B1, B2 darajadagi badiiy va ilmiy hikoyalar yoki foydalanuvchining shaxsiy matnlari.
- Matn ichidagi siz bilgan so'zlar avtomatik yashil/moviy tusda ajratib ko'rsatiladi.
- Istalgan so'zni 1-marta bosish orqali: IPA transkripsiyasi, kontekstli misol, talaffuz va bazaga qo'shish modali.

### 6. 🖨️ Chop Etiladigan Mashqlar Generatori (Printable Worksheets)
- O'qituvchilar va mustaqil o'rganuvchilar uchun A4 formatida chop etishga tayyor materiallar:
  - So'z va tarjima tutashtirish mashqlari (Matching Quiz)
  - Ko'p variantli yozma testlar (Multiple Choice Sheet)
  - Bo'sh o'rinlarni to'ldirish (Fill-in-the-blanks)
  - O'qituvchi uchun javoblar kaliti (Answer Key) bilan birga PDF / HTML eksport.

### 7. 📊 Analitika va GitHub-Uslubidagi Faollik Taqvimi
- **365-kunlik Faollik Taqvimi (Heatmap):** Har bir kungi mashqlar intensivligini yashil kvadratlar orqali vizualizatsiya qiladi.
- **Statistika Ko'rsatkichlari:** Jami so'zlar, o'zlashtirilgan foiz, o'rganilayotganlar, kunlik streak (uzluksiz o'qish zanjiri).

### 8. 🏆 Mukofotlar va Gamifikatsiya (XP & Badges)
- Har bir mashq uchun XP (Tajriba ballari).
- 5 ta unvon: *Boshlovchi (Novice) → O'quvchi (Apprentice) → Bilimdon (Scholar) → Poliglot (Polyglot) → So'z Ustasi (Word Master)*.
- Maxsus nishonlar: Snayper, Tungi Boyqush, 7 Kunlik Olov, Lug'at Ustasi va boshqalar.

### 9. 🎨 8 ta Yuqori Sifatli Rang Mavzulari (Theme Switcher)
- 🌌 **Midnight Indigo:** Chuqur tungi binafsha-moviy.
- ⚡ **Cyberpunk Neon:** Futuristik elektrik neon va fuksiya.
- 🌲 **Emerald Forest:** Sokin, ko'zni charchatmaydigan zumrad yashil.
- 🌅 **Warm Sunset:** Issiq qahva, espresso va amber.
- 🖤 **OLED Pure Black:** Mutlaq qora (#000000) batareya tejamkor fon.
- 🌊 **Nordic Ocean:** Skandinaviya qutb dengizi moviyligi.
- 🧛 **Dracula Crimson:** Klassik to'q binafsha va neon qirmizi.
- ☀️ **Light Elegant:** Kunduzgi o'qish uchun toza oq va sokin kumush rejim.

### 10. ⚡ Stay-on-Top Tezkor So'z Qo'shish & Mini Vidjet
- Brauzer yoki kitob o'qiyotganda `Ctrl+Shift+A` yoki `Ctrl+Shift+V` bosib, dasturga kirmasdan tezda yangi so'z saqlash.
- Ekran burchagida turuvchi ixcham **Mini Floating Widget** (`Ctrl+Shift+W`).

### 11. 🎙️ Oflayn Audio Podcast Eksport (.wav)
- So'zlarni audio (.wav) faylga yozib olib, telefon yoki pleyeringizda yo'lda, sportda va internetsiz quloqchin orqali tinglang.
- Oraliq pauzani (1.0s dan 8.0s gacha), o'zbekcha tarjimani va misol gaplarni qo'shish imkoniyati.

### 12. 🎙️ Speaking & Talaffuz Trenajyori (Mustaqil Asosiy Bo'lim)
- **Asosiy Chap Menyuda Mustaqil Trenajyor:** Foydalanuvchi to'g'ridan-to'g'ri yon panel orqali Speaking bo'limiga kirib talaffuzini mashq qiladi.
- **4 Xil So'z Manbai:** Shaxsiy lug'at, xatosi ko'p so'zlar, 115 ta noto'g'ri fe'llar va yangi so'zlar to'plami.
- **Dual-Speed TTS:** 1.0x normal tezlik (`R`) va 0.75x sekinlashtirilgan namuna (`S`) orqali urg'u va fonetikani aniq eshitish.
- **Ovoz Yozish & Darhol Qayta Tinglash:** 4 soniyalik jonli taymer, mikrofon yozuvi va `P` tugmasi orqali o'z ovozini darhol tinglab, namunaga solishtirish.
- **Windows Speech & Oflayn Akustik Baholash:** 0–100% aniqlik bali (A'lo, Yaxshi, Qayta sinash) va real vaqt tavsiyalari.

### 13. 🔍 Universal Spotlight & Levenshtein Fuzzy Qidiruv (`Alt + Space`)
- **⚡ Imlo Xatolariga Chidamli (Universal Fuzzy Search):** Ham shaxsiy lug'atda, ham 64,000+ so'zlik Global akademik bazada foydalanuvchi so'zni xato yozsa ham (`wunderful` → `wonderful`, `beutiful` → `beautiful`, `accomodate` → `accommodate`), Levenshtein tahrir masofasi orqali eng yaqin so'zlar ~25-30ms da topiladi.
- **💡 Lug'at Oynasida Aqlli Tavsiya Bannerlari:** Shaxsiy bazada topilmagan so'zlar 64k global bazadan avtomatik aniqlanib, 1-bosish bilan o'rganish ro'yxatiga qo'shish tugmasi bilan taklif qilinadi.
- **Spotlight Kartasi:** Istalgan joydan `Alt + Space` yoki `Ctrl + Shift + F` orqali ochiladi.
- So'zlar, tarjimalar, misollar va teglarni 0ms kechikish bilan topish, talaffuz qilish va 1-bosish bilan lug'atga yangi so'z qo'shish.

### 14. 🌧️ "Word Fall" va 🧩 "Lug'at Krossvordi" Yangi O'yinlari
- **Word Fall:** Ekranning yuqorisidan tushayotgan so'zlarni vaqtida yozib yo'q qilish arkadasi (3 ta jon, combo tizimi).
- **Lug'at Krossvordi:** Bazadagi so'zlardan avtomatik kesishuvchi krossvord panjarasini yaratuvchi algoritm.
- *Qat'iy Gamifikatsiya qoidasi:* Hech qanday so'z topilmasa (0 ball), XP berilmaydi!

### 15. 🛡️ Mahalliy Data Vault (Formatdan Himoyalangan Avto-Zaxira)
- Windows tizimi qayta o'rnatilganda (format qilinganda) foydalanuvchining oylar davomida yig'gan lug'ati va statistikasi yo'qolib ketmasligi uchun dastur yonidagi `backups/` papkasida 100% lokal xavfsiz avtomatik zaxira nusxalari yuritiladi. Hech qanday tashqi serverlarga ma'lumot yuborilmaydi.

### 16. ⚡ Noto'g'ri Fe'llar Moduli (Irregular Verbs Mastery - 115 ta Fe'l)
- **Asosiy Menyudagi Maxsus Bo'lim:** Ingliz tilidagi 115 ta eng muhim noto'g'ri fe'llarning barcha 3 ta shakli (V1, V2, V3) va o'zbekcha tarjimalari.
- **6 ta Interaktiv O'quv Rejimi:**
  1. *Jadval & Audio:* Barcha shakllarni alohida yoki ketma-ket tinglash, saralash, sevimlilarga qo'shish va CRUD tahrirlash.
  2. *3-shakl Viktorinasi (Quiz):* Tasodifiy berilgan V1/V2/V3 shakli bo'yicha qolgan shakllarini 4 variantdan topish.
  3. *Yozma Sinov (Typing):* Fe'l shakllarini klaviaturada terish orqali orfografiyani mukammallashtirish.
  4. *Aylanuvchi Flashcardlar (3D Flip):* Old tomonida V1 shakli va audio, orqa tomonida V2, V3, tarjima va misol gaplar.
  5. *So'z Juftlash O'yini (Match Game):* V1 va V2/V3 shakllari yoki tarjimalarini topish.
  6. *Harflardan Yig'ish (Letter Scramble):* Chalkash harflardan to'g'ri fe'lni terish.

---

## 🆕 So'nggi Yangilanishlar & O'zgarishlar (Latest Updates & Changelog)

### v3.6 — 2026-09-24 📥 Professional Import, Dublikatsiz Birlashtirish & Multi-Game Integratsiyasi

#### 🔄 Aqlli Dublikatsiz Import & Sessiya Birlashtirishi (Smart Batch Resolution)
- **Muammo:** Oldin foydalanuvchi import qilgan ro'yxatdagi so'zlar bazada allaqachon mavjud bo'lsa, ular dublikat deb tashlab yuborilar va mashq to'plamidan tushib qolardi (foydalanuvchi to'liq ro'yxatini mashq qila olmasdi).
- **Yechim:** Yangi algoritmi bazada mavjud so'zlarni ikkinchi marta bazaga qo'shmaydi (bazani toza saqlaydi), lekin ularning mavjud ID larini bazadan ajratib olib, yangi qo'shilgan so'zlar bilan birga yagona mashq to'plamiga birlashtiradi (`all_batch_ids`).
- Foydalanuvchiga aniq statistika taqdim etiladi: `✅ N ta yangi so'z qo'shildi | 🔄 M ta mavjud so'z bazadan birlashtirildi (Jami N+M ta so'z mashqqa tayyor!)`.

#### 📖 Lug'atda "📥 Oxirgi import" Alohida Filtr & Boshqaruv Paneli
- Lug'at filtrlari qatoriga yangi `📥 Oxirgi import` tugmasi qo'shildi (`ui/views/dictionary_view.py`);
- Tanlanganda faqat oxirgi import qilingan so'zlar to'plami ajratib ko'rsatiladi;
- Jadval ustida tezkor harakatlar paneli paydo bo'lib, import qilingan so'zlarni darhol mashq qilish yoki o'yinlarda mustahkamlash imkonini beradi;
- Lug'at boshqaruv paneli tepasiga universal `⚡ Mashq qilish ▾` (EN→UZ, UZ→EN, Flashcard, Speaking) va `🎮 O'yinlar ▾` (Match, Blitz, Word Fall, Krossvord) menyu tugmalari o'rnatildi.

#### 🎮 Barcha O'yinlar va Mashqlar bilan To'liq Integratsiya
- Import oynasidan (`ui/dialogs/import_dialog.py`) chiqmasdan turib:
  1. `🇬🇧→🇺🇿 EN → UZ Test`
  2. `🇺🇿→🇬🇧 UZ → EN Test`
  3. `🎴 Flashcard (Anki uslubi)`
  4. `🎙️ Speaking Trenajyori (AI talaffuz baholash)`
  5. `🎮 So'z Juftlash (Match Game)`
  6. `⚡ Blitz Marafon`
  7. `🌧️ Word Fall`
  8. `📖 Lug'atda ko'rish (Ajratilgan holda)`
- `GameSourceSelector` va `game_word_provider` da `CAT_PERSONAL` ostida `📥 Oxirgi import qilinganlar` manbasi joriy etildi (barcha mini-o'yinlar import qilingan so'zlarni to'g'ridan-to'g'ri o'ynash imkoniga ega bo'ldi).

#### 🧪 177 ta Avtomatlashtirilgan Testlar (100% Yashil)
- `tests/test_import_batch.py` orqali dublikatsiz import, filtrlar, o'yin integratsiyasi va marshrutlash to'liq tekshirildi;
- Barcha 177 ta test 100% muvaffaqiyatli o'tdi (`177 passed in 11.14s`).

---

### v3.5 — 2026-09-24 🧠 FSRS v5 Algoritmi & ⚡ Noto'g'ri Fe'llar Moduli

#### 🧠 Anki 24 FSRS v5 (Free Spaced Repetition Scheduler) Integratsiyasi
- Eski SuperMemo SM-2 o'rniga eng so'nggi FSRS-5 algoritmi joriy etildi (`core/fsrs.py`);
- Ebbinghaus retrievability formulasi $R = (1 + \text{FACTOR} \cdot t / S)^{-\text{DECAY}}$ bo'yicha aniq xotira hisob-kitobi;
- Har bir so'z uchun mustaqil Barqarorlik ($S$, kunlarda), Qiyinlik ($D$, 1-10), Reps va Lapses parametrlari;
- So'zlarni 30-40% kamroq takrorlab, 90%+ xotirada saqlash darajasiga erishish;
- `migrate_sm2_to_fsrs_if_needed`: mavjud foydalanuvchilarning oldingi SM-2 natijalari avtomatik ravishda FSRS ga o'tkaziladi (nol ma'lumot yo'qotilishi).

#### ⚡ Noto'g'ri Fe'llar (Irregular Verbs) To'liq Bo'limi
- Chap asosiy menyuda "Lug'at" ostiga `⚡ Noto'g'ri fe'llar` bo'limi qo'shildi (`ui/views/irregular_verbs_view.py`);
- 115 ta noto'g'ri fe'llar bazasi (`assets/irregular_verbs.json` va SQLite `irregular_verbs` jadvali);
- 6 ta interaktiv rejim: Jadval & Audio, Quiz, Typing, Aylanuvchi Flashcardlar, Juftlash va Harf terish o'yinlari;
- Chiroyli scoped CSS dizayn, label border-bleed xatolaridan to'liq xoli.

#### 🧪 172 ta Avtomatlashtirilgan Testlar (100% Yashil)
- Loyiha bo'yicha barcha 172 ta test 100% muvaffaqiyatli o'tdi (`172 passed in 9.40s`).

---

### v3.0 — 2026-09-14 🎯 Senior-Level Mashq Trenajyori & Universal Fuzzy Qidiruv

#### 🛡️ Sessiyani Saqlash (State Persistence across Navigation)
- Yon paneldagi boshqa sahifalarga (`Dashboard`, `Lug'at`, `O'quvchi`, `O'yinlar` va h.k.) o'tib qaytganda trenajor sessiyasi qaytadan boshlanmaydi;
- Qolgan so'zlar navbati (`queue`), ballar, progress va kiritish maydoni fokusi to'liq saqlanadi (`resume_session()`).
- Yuqori panelga partiyani o'z xohishi bilan qayta boshlash uchun qulay "🔄 Qayta boshlash" tugmasi joylashtirildi.

#### ⏸️ 2-Enter Xatolarni Tahlil Qilish Mexanizmi
- Xato javob berilganda dastur 2-3 soniyada avtomatik keyingi so'zga sakrab ketmaydi;
- **1-Enter:** Javobni tekshiradi, to'g'ri so'zni qizil/yashil ranglarda ko'rsatadi, tugma yashil "Davom etish ↵" ga aylanadi;
- Foydalanuvchi so'z tarjimasi, IPA transkripsiyasi va misol gapini bemalol o'qib, `Space` orqali talaffuzni qayta tinglashi mumkin;
- **2-Enter:** Keyingi so'zga o'tish uchun ikkinchi marta Enter (yoki "Davom etish") bosiladi (Qt event-bubbling va 0.35s debounce himoyasi bilan).

#### 🔍 Harfma-harf Visual Diff va Typo (Imlo Xatosi) Aniqlovchisi
- Yozma mashqda xato qilinsa, Levenshtein tahrir algoritmi farqni harfma-harf hisoblaydi;
- 1-2 ta harfda adashilganda `💡 Deyarli to'g'ri! (1 ta harfda adashdingiz)` yorlig'i chiqadi;
- Foydalanuvchi kiritgan ortiqcha/xato harflar qizil o'chirilgan, to'g'ri harflar yashil tagiga chizilgan holda ko'rgazmali solishtiriladi (`Siz: ~~acommodate~~ → Asli: ac<u>c</u>ommodate`).

#### 🐢 Sekin Talaffuz (0.75x Slow Audio)
- Asosiy `🔊` karnay yoniga yangi yashil `🐢` tugmasi joylashtirildi;
- SAPI5 nutq tezligini ~0.75x ga sekinlashtirib, uzun va murakkab so'zlarni bo'g'inma-bo'g'in aniq eshittiradi.

#### 🎯 Partiya Xatolari Ustida Qayta Ishlash (Retry Session Mistakes)
- Partiyada adashilgan barcha so'zlar ro'yxati avtomatik yuritiladi;
- Partiya yakunida `🎯 Xatolar ustida ishlash (N ta so'z)` tugmasi paydo bo'lib, faqat xato so'zlardan iborat yangi maqsadli mashqni boshlaydi.

#### ⚡ Universal Levenshtein Fuzzy Search (Shaxsiy + 64,000 Global Lug'at)
- Ham shaxsiy bazada, ham 64k global akademik bazada xatolik bilan qidirilganda (`wunderful` → `wonderful`, `beutiful` → `beautiful`, `accomodate` → `accommodate`) ~25-30ms da eng yaqin so'zlar topiladi;
- Lug'at oynasida imlo xatosi bo'yicha maxsus ko'rgazmali sariq/binafsha tavsiya bannerlari va 1-bosish bilan bazaga qo'shish joriy etildi;
- Spotlight tezkor qidiruviga (Ctrl+F) to'liq integratsiya qilindi.

#### 📳 Duolingo Uslubidagi Karta Silkinishi (Card Shake Animation)
- Xato javob kiritilganda `quiz_card` kartasi 300ms davomida mayin chapga-o'ngga silkinadi (`QPropertyAnimation`).

#### 🧪 145 ta Avtomatlashtirilgan Testlar
- Barcha yangi imkoniyatlar uchun pytest testlari yozildi va barcha 145 ta test 100% yashil o'tdi.

---

### v2.5 — 2026-09-10 🔧 UI Aniqlik Yaxshilanishlari

#### 🔍 Spotlight Qidiruv — "➕ Qo'shish" Tugmasi To'liq Ko'rinishi
- **Muammo:** `QListWidget` ichidagi har bir natija kartida o'ng tomondagi "➕ Qo'shish" (yashil) tugmasi ba'zan viewport chegarasidan tashqariga chiqib ketib, faqat 12px yashil tirqish ko'rinar edi. Gorizontal scrollbar paydo bo'lar, pastki qatorlar qisman kesilardi.
- **Sabab:** `lbl_uz` (o'zbekcha tarjima `QLabel`) kengligini cheklamasdan, `item.setSizeHint(w.sizeHint())` bilan uzun tarjimalar (masalan, 704px) butun `QListWidget`ni kengaytirar edi.
- **Yechim:**
  - `lbl_uz.setSizePolicy(Ignored, Preferred)` — uzun tarjimalar endi kenglikni bo'zmaydi; hover tooltipda to'liq matn ko'rinadi.
  - `SpotlightResultItemWidget.sizeHint() → QSize(0, 56)` — `QListWidget` viewport kengligiga mos ravishda sozlanadi.
  - O'ng qismidagi badge + tugma alohida `right_container QWidget` ichiga `AlignRight | AlignVCenter` bilan joylashtirildi.
  - `setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)` — gorizontal scrollbar butunlay olib tashlandi.
  - Dialog kengligi `760 × 530px`ga kengaytirildi.
  - `lbl_action_hint` (pastki panel) ham `Ignored` size policy va tooltip bilan ta'minlandi.

---

### v2.4 — 2026-09-09 🎤 Mikrofon + Kunlik Missiyalar

#### 🎙️ Mashq Ekraniga Mikrofon Tugmasi
- `practice_view.py` dagi har bir so'z yoniga **mikrofon tugmasi** qo'shildi.
- Mavjud `speech_service.py` bilan to'liq ulangan: foydalanuvchi o'z talaffuzini real vaqtda sinab ko'rishi mumkin.
- Oflayn Windows System.Speech API orqali talaffuz yozib olinadi va to'g'ri TTS namunasi bilan taqqoslanadi.

#### 🎯 Kunlik Missiyalar va Battle Pass tizimi
- Har kuni avtomatik yangilanadigan **3 ta dinamik vazifa** tizimi (`daily_quests_service.py`).
- XP mukofotlari, Battle Pass rivojlanishi va streak tizimi bilan integratsiya.
- Yutuqlar (`achievements_dialog.py`) bilan parallel ishlaydi.

---

### v2.3 — 2026-09-08 🎧 Audio Pleyer Kengaytmasi

#### 🎧 Audio Pleyerga To'plamlar va Paketlar Qo'shildi
- **Mavzular bo'yicha tinglash:** 50+ tematik kategoriyalar (Travel, Business, Science…) audio rejimda tinglanishi mumkin.
- **CEFR / IELTS Paketlari:** A1-C2 va IELTS Academic (AWL) so'z to'plamlarini hands-free audio tarzda o'rganish.
- **Avto-tanlab olish muammosi tuzatildi:** Tab yoki ro'yxat bosishida audio avto-boshlanib ketish (regression) bartaraf etildi — endi faqat ▶️ Play tugmasi bosilganda audio boshlanadi.

---

### v2.2 — 2026-09-07 🔎 Aqlli Ikki Tomonlama Qidiruv

#### 🔍 Inglizcha va O'zbekcha Qidiruvda Muammolar Tuzatildi
- **Muammo:** O'zbekcha so'z kiritilganda ba'zan faqat inglizcha natijalar chiqar edi; apostrofli so'zlar (`don't`, `o'qituvchi`) to'g'ri topilmasdi.
- **Yechim:** `text_search_utils.py` da multi-tier ranking tizimi va apostrof normalizatsiya algoritmi joriy etildi:
  - `Rank 0`: Aniq to'liq moslik (inglizcha yoki o'zbekcha)
  - `Rank 1`: Boshidan mos keluvchi (prefix)
  - `Rank 2`: Ichki qismda mos keluvchi (substring)
  - `Rank 3`: Normallashtirilgan (apostrofsiz, kichik harf) qidiruv
- Qidiruv natijalarida shaxsiy lug'at har doim global 64k lug'atdan ustun turadi.

---

### v2.1 — 2026-09-06 📦 EXE Paketi Stabilligi

#### 🛠️ Standalone EXE Xatosi Tuzatildi
- `NameError: name 'sys' is not defined` xatosi `topic_words_view.py` va boshqa modullarda bartaraf etildi.
- `PyInstaller` spec fayli (`VocabMaster.spec`) optimallashtirilib, barcha yashirin importlar aniq ko'rsatildi.
- `build_exe.py` yangilandi — `hiddenimports`, `datas` va `pathex` to'liq to'g'rilandi.

---

### v2.0 — 2026-09-05 🎮 O'yinlar va To'plamlar

#### 🎧 Hands-Free Audio Pleyer Yaxshilanishlari
- **Mukammal Markazlashtirish:** So'z, fonetik nishon, tarjima va misol gaplar barcha ekran kengliklarida gorizontal markaz.
- **Matn Tozalash:** Misol gaplar boshidagi `•`, `*`, `-`, `"` belgilar to'liq tozalanib chiroyli `" ... "` shakliga keltirildi.
- **Aqlli 2 Qatorli Formatlash:** Uzun tarjimalar mantiqiy vergullar bo'yicha 2 qatorga ajratiladi.
- **Yangi Audio Vizualizator:** 24 ta yumaloqlangan to'lqinlar animatsiyasi, `260 × 28px` ixcham format.
- **🎙️ Podcast (.wav) Eksport** modali to'g'ridan-to'g'ri pleyer panelida.

#### 🎮 O'yinlarda So'z Manba Tanlash
- Barcha 4 ta o'yin (Blitz, Match, Word Fall, Crossword) uchun so'z manbasi tanlash qo'shildi: shaxsiy lug'at, mavzular, CEFR paketlari.

---

## 🛠️ Texnologiyalar (Tech Stack)

| Yo'nalish | Ishlatilgan Texnologiya |
|---|---|
| **Dasturlash Tili** | Python 3.10+ / 3.11+ |
| **Foydalanuvchi Interfeysi (GUI)** | PyQt6 / PySide6 |
| **Xotira Algoritmi** | Anki 24 FSRS v5 + SuperMemo SM-2 + Leitner 5-Box |
| **Ma'lumotlar Bazasi** | SQLite 3 (WAL rejimi, ACID, Tranzaksiyalar) |
| **Nutqni Tanish (STT)** | Windows System.Speech + WAV Akustik Tahlil (100% oflayn) |
| **Audio Talaffuz (TTS)** | Windows SAPI5 (win32com) + pyttsx3 + System.Speech |
| **Ovoz Effektlari** | NumPy + Pygame / Wave sintez (100% oflayn SFX) |
| **Distribyutsiya / Packaging** | PyInstaller (Standalone EXE) |

---

## 🚀 O'rnatish va Ishga Tushirish (Quickstart)

### 1. Repozitoriyni klonlash
```bash
git clone https://github.com/Valijon21/Smart_dict.git
cd Smart_dict
```

### 2. Virtual muhit yaratish va faollashtirish
**Windows PowerShell:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Kutubxonalarni o'rnatish
```powershell
pip install -r requirements.txt
```

### 4. Dasturni ishga tushirish
```powershell
python main.py
```
*yoki qulaylik uchun `run.bat` faylini ikki marta bosing.*

---

## 📁 Loyiha Strukturasi (Layered Architecture)

```text
Smart_dict/
├── core/                         # 🧠 Biznes-mantiq va ma'lumotlar bazasi
│   ├── database.py               # SQLite WAL ulanishi, FSRS/SM-2 va avto-zaxira
│   ├── fsrs.py                   # Anki 24 FSRS v5 xotira va takrorlash dvigateli
│   ├── gamification.py           # XP tizimi, darajalar, streaklar va yutuqlar
│   ├── retention_analytics.py    # Xotira egri chizig'i va takrorlash analitikasi
│   ├── phonetics.py              # IPA transkripsiya va fonetik tahlil dvigateli
│   └── word_packs.py             # Saralangan mavzuli to'plamlar bazasi
│
├── services/                     # ⚙️ Tashqi tizimlar, Audio, Nutq va Servislar
│   ├── tts_service.py            # SAPI5 & pyttsx3 oflayn nutq sintezi (1.0x & 0.75x)
│   ├── speech_service.py         # Windows Speech & WAV mikrofondan baholash
│   ├── irregular_verbs_service.py# Noto'g'ri fe'llar test, quiz va o'yin generatorlari
│   ├── sound_effects.py          # Oflayn sintetik audio effektlar (Wave SFX)
│   ├── cefr_service.py           # CEFR (A1-C2) & IELTS 64,000+ so'zlik qidiruv xizmati
│   ├── topic_service.py          # Mavzuli kategoriyalar xizmati
│   ├── clipboard_service.py      # Tizim buferi (clipboard) kuzatuvchisi
│   └── global_dict_service.py    # Katta lug'at qidiruv xizmati
│
├── ui/                           # 🎨 Foydalanuvchi Interfeysi (PyQt6)
│   ├── main_window.py            # Asosiy oyna qobig'i, sidebar, lazy factory, tray
│   ├── theme_manager.py          # 8 xil rang mavzulari va dinamik CSS
│   ├── views/                    # Asosiy to'liq ekranli sahifalar
│   │   ├── dashboard_view.py     # Analitika va faollik taqvimi (Heatmap)
│   │   ├── dictionary_view.py    # Lug'at jadvali, 60 FPS delegat va qidiruv
│   │   ├── practice_view.py      # 6 xil mashq trenajyori
│   │   ├── irregular_verbs_view.py # ⚡ Noto'g'ri fe'llar (6 ta rejimli modul)
│   │   ├── audio_player_view.py  # Hands-Free audio pleyer
│   │   ├── reader_view.py        # Aqlli kitob o'quvchi
│   │   ├── topic_words_view.py   # Mavzuli so'zlar bo'limi
│   │   └── settings_view.py      # Sozlamalar sahifasi
│   ├── games/                    # Ta'limiy interaktiv o'yinlar
│   │   ├── blitz_game.py         # 60s Blitz marafon
│   │   ├── match_game.py         # So'z juftlash o'yini
│   │   ├── word_fall_game.py     # Word Fall arkadasi
│   │   └── crossword_game.py     # Lug'at krossvordi
│   ├── dialogs/                  # Modal oynalar va popup oynalar
│   │   ├── word_packs_dialog.py  # CEFR & Tayyor to'plamlar modali
│   │   ├── quick_capture_dialog.py # Tezkor so'z qo'shish (Ctrl+Shift+A)
│   │   ├── spotlight_search_dialog.py # Spotlight qidiruv (Alt+Space)
│   │   ├── achievements_dialog.py# Medallar va yutuqlar oynasi
│   │   ├── worksheet_dialog.py   # Chop etiladigan A4 testlar generatori
│   │   └── import_dialog.py      # Fayldan so'z yuklash
│   └── components/               # Qayta ishlatiluvchi UI vidjetlari
│       └── mini_widget.py        # Suzuvchi ish stoli mini vidjeti
│
├── utils/                        # 🛠️ Yordamchi umumiy modullar
│   ├── logger.py                 # Professional log tizimi (Rotating file + console)
│   ├── text_search_utils.py      # Levenshtein fuzzy tahrir algoritmi va harfma-harf Visual Diff
│   ├── importer.py               # CSV, JSON, TXT fayllarni o'qish/yozish
│   ├── reader_data.py            # Badiiy matnlar namunalari
│   └── single_instance.py        # IPC QLocalServer yagona instansiya boshqaruvi
│
├── tests/                        # 🧪 Avtomatlashtirilgan testlar to'plami
│   ├── test_fsrs.py              # FSRS-5 algoritmi va xotira regressiya testlari
│   ├── test_irregular_verbs.py   # Noto'g'ri fe'llar bazasi va o'yinlar testlari
│   ├── test_database.py          # Baza, migratsiyalar va SQL xavfsizlik testlari
│   └── ...                       # Boshqa modul va servis testlari
│
├── assets/                       # Rasmlar, piktogrammalar va irregular_verbs.json
├── backups/                      # Avtomatik zaxira nusxalari
├── logs/                         # Dastur ishlash loglari
├── main.py                       # Toza kirish nuqtasi va ishga tushirish
├── build_exe.py                  # Standalone .exe yig'ish skripti
└── requirements.txt              # Kerakli Python kutubxonalari
```

---

## 🧪 Avtomatlashtirilgan Testlar (Quality Assurance)

Loyiha barqarorligi va regressiya xatolarining oldini olish uchun 177 ta avtomatik pytest testlari bilan ta'minlangan:

```powershell
python -m pytest tests -v
```
Barcha 177 ta test 100% muvaffaqiyatli o'tadi (`177 passed in 11.14s`).

---

## 📦 Standalone EXE Yaratish

Dasturni kompyuterida Python o'rnatilmagan har qanday Windows foydalanuvchisi uchun bitta mustaqil `.exe` faylga yig'ish:

```powershell
python build_exe.py
```
Yig'ish yakunlangach, tayyor `SmartDict.exe` fayli `dist/` papkasida paydo bo'ladi.

---

## ⌨️ Klaviatura Qisqa Tugmalari (Hotkeys)

| Tugmalar | Vazifasi |
|---|---|
| `Ctrl + F` / `Alt + Space` | 🔍 Aqlli universal qidiruv paneli (Spotlight Search, Typo-tolerant) |
| `Space` | Mashqda talaffuzni qayta tinglash / Flashcard ag'darish / Pleyerda Play-Pause / Speakingda yozish |
| `Enter` | 1-Enter: Javobni tekshirish / 2-Enter: Xatoni o'rgangach keyingi so'zga o'tish |
| `R` | Speaking trenajyorida to'g'ri talaffuz namunasini tinglash |
| `S` | Speaking trenajyorida sekinlashtirilgan (0.75x) namunani tinglash |
| `P` | Speaking trenajyorida o'z ovozini darhol qayta eshitish |
| `Ctrl + Shift + A` | Tezkor so'z qo'shish (Quick Capture) |
| `1, 2, 3, 4` | 4 Variantli test rejimida variantni tanlash |
| `Esc` | Modal oynalarni yopish |

---

## 🔒 Xavfsizlik va Ma'lumotlar Maxfiyligi
- **100% Maxfiy:** Foydalanuvchining barcha so'zlari va statistikasi faqatgina lokal kompyuterdagi `vocab.db` faylida saqlanadi.
- **Tashqi serverlarga ma'lumot yuborilmaydi:** Hech qanday tashqi telemetriya yoki shaxsiy ma'lumot uzatilishi mavjud emas.
- **Zaxira Nusxalash:** Barcha so'zlarni istalgan payt CSV va JSON formatlarida xavfsiz eksport qilish mumkin.

---

## 👨‍💻 Muallif va Litsenziya

- **Muallif:** [Valijon](https://github.com/Valijon21)
- **GitHub Repozitoriy:** [Smart_dict](https://github.com/Valijon21/Smart_dict.git)
- **Litsenziya:** MIT License. Erkin foydalanish, o'zgartirish va tarqatish mumkin.
