"""
core/fsrs.py
Free Spaced Repetition Scheduler (FSRS) v5 — Professional Implementation.
Anki 23.10+ va 24+ ochiq standartiga asoslangan zamonaviy xotira algoritmi.

SuperMemo SM-2 bilan taqqoslaganda:
- Inson xotirasini 90%+ aniqlik bilan modellashtiradi (Ebbinghaus Retrievability: R = (1 + factor * t / S)^(-decay));
- 30-40% kamroq takrorlashlar bilan bir xil yoki undan yuqori eslab qolish darajasini (retention) ta'minlaydi;
- Har bir so'z uchun alohida Barqarorlik (Stability - kunlarda) va Qiyinlik (Difficulty: 1-10) parametrlarini yuritadi.
"""
import math
import datetime
from enum import IntEnum
from dataclasses import dataclass
from typing import Tuple, Optional


class Rating(IntEnum):
    AGAIN = 1  # Eslay olmadi / xato (Lapse)
    HARD = 2   # Qiyinchilik bilan esladi (Unutayozgan)
    GOOD = 3   # O'z vaqtida, normal esladi (Standart)
    EASY = 4   # Juda oson va ikkilanmay esladi


class CardState(IntEnum):
    NEW = 0
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


# FSRS-5 Standart 19 ta optimallashtirilgan og'irlik parametrlari
DEFAULT_WEIGHTS = (
    0.40255, 1.18385, 3.173, 15.69105,  # w0..w3: Boshlang'ich barqarorlik (Initial Stability: Again, Hard, Good, Easy)
    7.1949, 0.5345,                     # w4..w5: Boshlang'ich qiyinlik (Initial Difficulty)
    1.4604, 0.0046,                     # w6..w7: Qiyinlik o'zgarishi va o'rtacha regressiya
    1.54575, 0.1192, 1.01925,           # w8..w10: Muvaffaqiyatli takrorlashdagi barqarorlik o'sishi
    1.9395, 0.11, 0.29605, 0.22695,     # w11..w14: Lapse (unutilganda) barqarorlik tiklanishi
    0.56655, 2.0844,                    # w15..w16: Hard va Easy bonus koeffitsientlari
    0.5, 0.63                           # w17..w18: Decay va faktor parametrlari
)

DECAY = 0.5
FACTOR = 19.0 / 81.0  # R(S, S) = 0.90 bo'lishini ta'minlovchi matematik faktor


@dataclass
class FSRSCard:
    """FSRS xotira holati modeli."""
    stability: float = 0.0       # S: Barqarorlik (R=90% gacha bo'lgan kunlar)
    difficulty: float = 5.0      # D: Qiyinlik shkalasi (1.0 = eng oson, 10.0 = eng qiyin)
    reps: int = 0                # Muvaffaqiyatli takrorlashlar soni
    lapses: int = 0              # Unutilishlar soni
    state: CardState = CardState.NEW
    last_review: Optional[datetime.datetime] = None
    due: Optional[datetime.datetime] = None


class FSRSv5:
    """FSRS v5 rejalashtiruvchi dvigateli."""

    def __init__(self, desired_retention: float = 0.90, weights: tuple = DEFAULT_WEIGHTS):
        if not (0.70 <= desired_retention <= 0.98):
            desired_retention = 0.90
        self.desired_retention = desired_retention
        self.w = weights

    # -------------------------------------------------------------
    # MATEMATIK FORMULALAR
    # -------------------------------------------------------------

    def get_retrievability(self, card: FSRSCard, now: Optional[datetime.datetime] = None) -> float:
        """Hozirgi paytda kartaning xotirada saqlanib qolish ehtimolini hisoblash: R in [0, 1]."""
        if card.state == CardState.NEW or card.stability <= 0 or not card.last_review:
            return 0.0

        if now is None:
            now = datetime.datetime.now()

        elapsed_days = max(0.0, (now - card.last_review).total_seconds() / 86400.0)
        return math.pow(1.0 + FACTOR * (elapsed_days / card.stability), -DECAY)

    def next_interval(self, stability: float) -> int:
        """Ko'zlangan retention (masalan 90%) ga erishish uchun keyingi intervalni hisoblash (kunlarda)."""
        if stability <= 0.0:
            return 1
        interval = (stability / FACTOR) * (math.pow(self.desired_retention, -1.0 / DECAY) - 1.0)
        return max(1, round(interval))

    def _init_stability(self, rating: Rating) -> float:
        """Ilk baholashda barqarorlik (w0..w3)."""
        idx = int(rating) - 1
        return max(0.1, self.w[idx])

    def _init_difficulty(self, rating: Rating) -> float:
        """Ilk baholashda qiyinlik (w4..w5): D0(G) = w4 - exp(w5 * (G - 1)) + 1."""
        d = self.w[4] - math.exp(self.w[5] * (int(rating) - 1)) + 1.0
        return max(1.0, min(10.0, d))

    def _next_difficulty(self, d: float, rating: Rating) -> float:
        """Qiyinlikni yangilash va boshlang'ich o'rtachaga regressiya: D' = w7*D0(3) + (1-w7)*(D + deltaD)."""
        delta = -self.w[6] * (int(rating) - 3)
        d_next = d + delta
        # Regressiya
        d_target = self.w[4] - math.exp(self.w[5] * 2) + 1.0
        d_reverted = self.w[7] * d_target + (1.0 - self.w[7]) * d_next
        return max(1.0, min(10.0, d_reverted))

    def _next_recall_stability(self, d: float, s: float, r: float, rating: Rating) -> float:
        """Muvaffaqiyatli eslaganda (Hard, Good, Easy) barqarorlik o'sishi."""
        hard_penalty = self.w[15] if rating == Rating.HARD else 1.0
        easy_bonus = self.w[16] if rating == Rating.EASY else 1.0

        # Anki FSRS: Bir xil kunda / qisqa vaqt oralig'ida qayta takrorlanganda ham (r ~ 1.0)
        # minimal o'sish koeffitsienti kafolatlanadi (r_eff <= 0.98)
        r_eff = min(r, 0.98) if r >= 0.98 else r

        # FSRS-5 Stability recall formula
        growth = (
            math.exp(self.w[8]) *
            (11.0 - d) *
            math.pow(s, -self.w[9]) *
            (math.exp(self.w[10] * (1.0 - r_eff)) - 1.0) *
            hard_penalty *
            easy_bonus + 1.0
        )
        return max(0.1, s * growth)

    def _next_forget_stability(self, d: float, s: float, r: float) -> float:
        """Xato qilganda (Again - Lapse) barqarorlikning tiklanishi."""
        s_forget = (
            self.w[11] *
            math.pow(d, -self.w[12]) *
            (math.pow(s + 1.0, self.w[13]) - 1.0) *
            math.exp(self.w[14] * (1.0 - r))
        )
        return max(0.1, min(s, s_forget))

    # -------------------------------------------------------------
    # ASOSIY TAKRORLASH METODI
    # -------------------------------------------------------------

    def review_card(
        self,
        card: FSRSCard,
        rating: Rating,
        review_time: Optional[datetime.datetime] = None
    ) -> Tuple[FSRSCard, int]:
        """
        Kartani baholash va yangi FSRS holatini hamda keyingi kun intervalini qaytarish.
        Qaytaradi: (yangilangan_card, keyingi_interval_kun)
        """
        if review_time is None:
            review_time = datetime.datetime.now()

        r = self.get_retrievability(card, review_time)

        new_card = FSRSCard(
            stability=card.stability,
            difficulty=card.difficulty,
            reps=card.reps,
            lapses=card.lapses,
            state=card.state,
            last_review=review_time,
        )

        if card.state == CardState.NEW:
            new_card.difficulty = self._init_difficulty(rating)
            new_card.stability = self._init_stability(rating)
            if rating == Rating.AGAIN:
                new_card.state = CardState.LEARNING
                new_card.lapses += 1
                interval = 1
            else:
                new_card.state = CardState.REVIEW
                new_card.reps += 1
                interval = self.next_interval(new_card.stability)
        else:
            new_card.difficulty = self._next_difficulty(card.difficulty, rating)

            if rating == Rating.AGAIN:
                new_card.stability = self._next_forget_stability(card.difficulty, card.stability, r)
                new_card.state = CardState.RELEARNING
                new_card.lapses += 1
                interval = 1
            else:
                new_card.stability = self._next_recall_stability(card.difficulty, card.stability, r, rating)
                new_card.state = CardState.REVIEW
                new_card.reps += 1
                interval = self.next_interval(new_card.stability)

        new_card.due = review_time + datetime.timedelta(days=interval)
        return new_card, interval

    # -------------------------------------------------------------
    # SM-2 ➔ FSRS SILIQ MIGRATSIYA
    # -------------------------------------------------------------

    @staticmethod
    def from_sm2(
        ease_factor: float = 2.5,
        interval_days: int = 0,
        repetitions: int = 0,
        wrong_count: int = 0,
        last_reviewed_str: Optional[str] = None
    ) -> FSRSCard:
        """
        Eski SuperMemo SM-2 ma'lumotlarini yo'qotmasdan FSRS v5 parametrlariga konvertatsiya qilish.
        """
        ef = max(1.3, float(ease_factor or 2.5))
        iv = max(0, int(interval_days or 0))
        reps = max(0, int(repetitions or 0))
        lapses = max(0, int(wrong_count or 0))

        # Difficulty: SM-2 ease_factor [1.3 .. 2.8] -> FSRS [10.0 .. 1.0]
        # ef = 2.5 -> d ≈ 3.5; ef = 1.3 -> d = 10.0; ef = 2.8 -> d = 1.0
        normalized_ef = max(0.0, min(1.0, (ef - 1.3) / 1.5))
        difficulty = round(10.0 - normalized_ef * 9.0, 2)

        # Stability: Kunlik interval bilan bog'liq (S ≈ iv * 0.95)
        if iv > 0:
            stability = round(max(0.5, float(iv) * 0.95), 2)
            state = CardState.REVIEW
        elif reps > 0:
            stability = 1.0
            state = CardState.LEARNING
        else:
            stability = 0.0
            state = CardState.NEW

        last_dt = None
        if last_reviewed_str:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    last_dt = datetime.datetime.strptime(last_reviewed_str.strip(), fmt)
                    break
                except Exception:
                    pass

        due_dt = None
        if last_dt and iv > 0:
            due_dt = last_dt + datetime.timedelta(days=iv)

        return FSRSCard(
            stability=stability,
            difficulty=difficulty,
            reps=reps,
            lapses=lapses,
            state=state,
            last_review=last_dt,
            due=due_dt,
        )
