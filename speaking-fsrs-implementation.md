# 🚀 FSRS v5 va Talaffuz Trenajyori (Speaking Practice) — Implementatsiya Rejasi

> **Maqsad:** Dasturga zamonaviy Anki 24 standarti bo'lgan **FSRS v5** takrorlash algoritmini integratsiya qilish va mavjud nutqni baholash servisi asosida to'laqonli **"🎙️ Talaffuz Trenajyori" (Speaking Trainer)** yangi bo'limini yaratish.  
> **Status:** Tasdiqlangan (Socratic Gate o'tildi)

---

## 🏗️ Arxitektura va Bosqichlar

```
┌─────────────────────────────────────────────────────────────┐
│                    MainWindow (Sidebar)                     │
│  ... -> [🇬🇧→🇺🇿 EN-UZ] -> [🎙️ Talaffuz] -> [📖 Lug'at] ...  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Lazy loading
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       SpeakingWidget                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Manba Selektori: [Shaxsiy | CEFR A1-C2 | Irregular Verbs]│ │
│ │ So'z Kartasi: Target Word + Fonetika + Misol gap        │ │
│ │ 🔊 To'g'ri audio tinglash (Normal / 0.75x sekin)        │ │
│ │ 🎙️ Mikrofondan yozish + To'lqin animatsiyasi           │ │
│ │ 🎯 Natija: 0-100% Ball + Xatolarni vizual taqqoslash   │ │
│ │ 🔁 O'z ovozini qayta eshitish va solishtirish          │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│ services/speech_service.py   │ │ core/fsrs.py               │
│ (System.Speech tahlili,      │ │ (FSRS v5 algoritmi: S, D,  │
│  WAV audio yozish, solishtir)│ │  R=exp(-t/S), 19 weights)  │
└──────────────────────────────┘ └─────────────┬──────────────┘
                                               ▼
                                 ┌────────────────────────────┐
                                 │ core/database.py           │
                                 │ (progress: stability, diff,│
                                 │  SM-2 ➔ FSRS migratsiya)   │
                                 └────────────────────────────┘
```

---

## 📋 Vazifalar va Commitlar Rejasi

### 1-Bosqich: Mavjud O'zgarishlarni Git ga Saqlash
- [ ] Avvalgi audit, crash tuzatishlar va Noto'g'ri fe'llar modulini toza commit qilish.
- **Commit:** `feat(irregular-verbs): add irregular verbs module with quiz, typing, flashcards and games`

### 2-Bosqich: FSRS v5 Takrorlash Algoritmini Yaratish
- [ ] `core/fsrs.py` modulini yaratish (FSRS-5 formulalari, 19 parametrli vektor, R bashorati, 4 baho: Again, Hard, Good, Easy).
- [ ] `core/database.py` da `progress` jadvaliga `fsrs_stability`, `fsrs_difficulty`, `fsrs_reps`, `fsrs_lapses`, `fsrs_state` ustunlarini qo'shish.
- [ ] SM-2 ma'lumotlarini (ease_factor, interval) FSRS barqarorlik va qiyinlikka silliq konvertatsiya qilish funksiyasi.
- [ ] `tests/test_fsrs.py` testlarini yozish va tekshirish.
- **Commit:** `feat(fsrs): implement FSRS v5 spaced repetition algorithm with SM-2 migration`

### 3-Bosqich: "🎙️ Talaffuz Trenajyori" (Speaking View) Yangi Bo'limini Yaratish
- [ ] `ui/views/speaking_view.py` vidjetini ishlab chiqish:
  - Manbalar selektori: Shaxsiy lug'at, Oxford A1-A2, B1-B2, C1-C2, Noto'g'ri fe'llar, Zaif so'zlar.
  - Interaktiv mikrofon yozish tugmasi va jonli to'lqin indikatori.
  - Windows System.Speech bilan 100% oflayn solishtirish va 0-100% ball berish.
  - Foydalanuvchining o'z ovozini tinglash va to'g'ri talaffuz bilan solishtirish.
  - XP va gamifikatsiya integratsiyasi.
- [ ] `ui/main_window.py` ga `("🎙️  Talaffuz trenajyori", "speaking")` ni qo'shish va lazy factory ulash.
- [ ] `tests/test_speaking_view.py` GUI smoke testini yaratish.
- **Commit:** `feat(speaking): add interactive pronunciation and speaking trainer view`

### 4-Bosqich: Yakuniy Integratsiya, Spec va Build
- [ ] `VocabMaster.spec` fayliga `core.fsrs` va `ui.views.speaking_view` ni qo'shish.
- [ ] Barcha testlarni yashil o'tkazish va yakuniy commit qilish.
- **Commit:** `chore: update build specs and verification tests for FSRS and speaking trainer`
