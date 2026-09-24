# ⚡ Noto'g'ri Fe'llar (Irregular Verbs) Bo'limi — Implementatsiya Rejasi

> **Maqsad:** Foydalanuvchi taqdim etgan `new__Irregular_verbs.docx` dagi 115 ta noto'g'ri fe'llar asosida dasturga yangi mustaqil bo'lim integratsiya qilish.  
> **Joylashuvi:** Asosiy chap menyuda `📖 Lug'at` ning tagida (`⚡ Noto'g'ri fe'llar`).  
> **Status:** Tasdiqlangan (Approved by Socratic Gate)

---

## 🏗️ Arxitektura va Komponentlar

```
┌─────────────────────────────────────────────────────────────┐
│                       MainWindow                            │
│  Sidebar: [Lug'at] -> [⚡ Noto'g'ri fe'llar]                │
└──────────────────────────────┬──────────────────────────────┘
                               │ Lazy loaded
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 IrregularVerbsWidget                        │
│ ┌───────────────────┬───────────────────┬─────────────────┐ │
│ │ 📋 Lug'at / Jadval│ 🎯 Mashqlar (Quiz)│ 🎮 O'yinlar     │ │
│ │ (V1,V2,V3,Tarjima)│ (Test, Typing, FC)│ (Match, Scramble│ │
│ └───────────────────┴───────────────────┴─────────────────┘ │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│ irregular_verbs_service.py   │ │ core/database.py           │
│ (TTS ketma-ketligi, Quiz/Game│ │ (irregular_verbs jadvali,  │
│  generatsiya, statistika)    │ │  CRUD, progress, seed)     │
└──────────────────────────────┘ └────────────────────────────┘
```

---

## 📋 Vazifalar Taqsimoti (Task Breakdown)

### 1-Vazifa: Ma'lumotlarni Tayyorlash va Bazaga Integratsiya
- [x] `new__Irregular_verbs.docx` dagi 115 ta fe'lni tozalangan `assets/irregular_verbs.json` fayliga chiqarish.
- [x] `core/database.py` da `irregular_verbs` jadvalini yaratish (V1, V2, V3, translation, learned, favorite, stats).
- [x] `seed_irregular_verbs_if_empty()` funksiyasini yozish (dastur ilk ishga tushganda avtomatik to'ldirish).
- [x] CRUD va progress boshqaruv metodlarini qo'shish.

### 2-Vazifa: Xizmat Qatlami (`services/irregular_verbs_service.py`)
- [x] Ma'lumotlarni saralash, qidirish va filtrlash logikasi.
- [x] Ovozli talaffuz (TTS) ketma-ketligi: V1 -> V2 -> V3 ni bitta tugma bilan talaffuz qilish va alohida eshitish.
- [x] 3-shaklni topish viktorinasi (Quiz generator - 4 ta variant).
- [x] Yozma sinov (Typing/Spelling generator).
- [x] Flashcard generator.
- [x] Match juftliklari generatori.
- [x] Harflarni aralashtirish (Scramble generator).

### 3-Vazifa: Foydalanuvchi Interfeysi (`ui/views/irregular_verbs_view.py`)
- [x] **Tab 1: 📋 Jadval & Qidiruv:**
  - V1, V2, V3, Tarjima ustunlari bilan zamonaviy jadval.
  - Jonli qidiruv (V1, V2, V3 yoki tarjima bo'yicha).
  - Filtrlash: Barchasi, O'rganilmagan, Yodlangan, Sevimli (⭐).
  - Yangi fe'l qo'shish / tahrirlash / o'chirish dialogi.
  - Statistika paneli (Jami, Yodlandi, O'rganilmoqda, Aniqlik).
- [x] **Tab 2: 🎯 Mashqlar (Quiz):**
  - 3 Shakl Viktorinasi (V1 beriladi, V2/V3 topiladi).
  - Yozma Sinov (Klaviaturada V2 va V3 kiritiladi, Enter bosiladi).
  - Flashcards (Kartochkani bosib aylantirish va ovozini eshitish).
- [x] **Tab 3: 🎮 O'yinlar:**
  - So'z Juftlash (Match Game - kartochkalarni bosib juftini topish).
  - Harflardan Yig'ish (Letter Scramble - tartibsiz harflardan so'z yasash).

### 4-Vazifa: Asosiy Oynaga Integratsiya va Lazy Loading
- [x] `ui/main_window.py` dagi `NAV_ITEMS` ro'yxatiga `("⚡  Noto'g'ri fe'llar", "irregular_verbs")` ni `📖 Lug'at` ning tagidan qo'shish.
- [x] `_page_factories` ga lazy factory bog'lash.
- [x] `theme_manager` bilan uyg'unlik (Dark/Light mavzularda avtomatik moslashish).

### 5-Vazifa: Testlar va Paketlash
- [x] `tests/test_irregular_verbs.py` unit va integratsion testlarini yozish.
- [x] `VocabMaster.spec` fayliga yangi modullarni qo'shish.
