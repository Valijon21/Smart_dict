import core.database as db
import core.gamification as gamification
from typing import Optional, List, Dict, Any

class PracticeSessionService:
    """
    Mashq sessiyasining biznes mantig'i (Business Logic) va holati (State) uchun xizmat qatlami.
    UI ushbu xizmat orqali orqa fon ma'lumotlari bilan ishlaydi.
    """
    def __init__(self, direction: str = "en_uz"):
        self.direction = direction
        
        # Holat (State)
        self.queue: List[dict] = []
        self.current: Optional[dict] = None
        self.custom_word_ids: Optional[List[int]] = None
        
        # Statistika
        self.session_correct = 0
        self.session_wrong = 0
        self.batch_total = 0
        self.consecutive_correct = 0
        self.session_mistake_word_ids: List[int] = []

    def get_daily_goal(self) -> int:
        return db.get_daily_goal()
        
    def get_today_progress(self) -> dict:
        return db.get_today_progress()
        
    def get_total_words(self) -> int:
        return db.word_count().get("total", 0)

    def load_latest_added(self):
        """Oxirgi qo'shilgan so'zlardan iborat partiyani yuklash."""
        goal = self.get_daily_goal()
        rows = db.get_latest_added_words(limit=goal)
        self._init_queue(rows)
        self.custom_word_ids = None

    def load_weak_words(self):
        """Eng zaif so'zlardan iborat partiyani yuklash."""
        rows = db.get_weak_words(limit=30)
        self._init_queue(rows)
        self.custom_word_ids = None

    def load_batch(self, word_ids: Optional[List[int]] = None):
        """Standart mashq partiyasini yuklash (FSRS/SM2 bo'yicha)."""
        goal = self.get_daily_goal()
        if word_ids is not None:
            self.custom_word_ids = word_ids
            
        if self.custom_word_ids:
            rows = db.get_practice_batch(word_ids=self.custom_word_ids)
        else:
            rows = db.get_practice_batch(limit=goal)
        
        self._init_queue(rows)

    def load_mistakes(self):
        """Faqat shu sessiyada xato qilingan so'zlarni qayta yuklash."""
        if not self.session_mistake_word_ids:
            return False
            
        rows = db.get_practice_batch(word_ids=self.session_mistake_word_ids)
        self.queue = list(rows)
        self.batch_total = len(self.queue)
        
        # Statistikalarni qisman tozalaymiz
        self.session_correct = 0
        self.session_wrong = 0
        self.session_mistake_word_ids.clear()
        
        self.current = self.queue.pop(0) if self.queue else None
        return True

    def _init_queue(self, rows):
        """Navbatni ishga tushirish va statistikalarni tozalash."""
        self.queue = list(rows)
        self.batch_total = len(self.queue)
        self.session_correct = 0
        self.session_wrong = 0
        self.consecutive_correct = 0
        self.session_mistake_word_ids.clear()
        self.current = self.queue.pop(0) if self.queue else None

    def pop_next_word(self) -> Optional[dict]:
        """Keyingi so'zni olish."""
        self.current = self.queue.pop(0) if self.queue else None
        return self.current

    def record_answer(self, is_correct: bool, quiz_mode: str) -> dict:
        """Javobni ma'lumotlar bazasiga va geymifikatsiyaga yozish."""
        if not self.current:
            return {}

        word_id = self.current["id"]
        
        # 1. DB ga javobni yozish (Progressni yangilash)
        db.record_answer(word_id, is_correct)
        
        # 2. Xato qilingan so'zlarni saqlab qolish
        if not is_correct and word_id not in self.session_mistake_word_ids:
            self.session_mistake_word_ids.append(word_id)
            
        # 3. Statistika
        if is_correct:
            self.session_correct += 1
            self.consecutive_correct += 1
        else:
            self.session_wrong += 1
            self.consecutive_correct = 0
            
        # 4. Geymifikatsiya XP berish
        res = gamification.record_practice_answer(
            is_correct=is_correct,
            mode=quiz_mode,
            consecutive_correct=self.consecutive_correct
        )
        return res

    def record_flashcard_answer(self, quality: str) -> dict:
        """Flashcard reytingini saqlash (easy, good, hard)."""
        if not self.current:
            return {}
            
        word_id = self.current["id"]
        db.record_flashcard_answer(word_id, quality)
        
        is_correct = quality in ["easy", "good"]
        if not is_correct and word_id not in self.session_mistake_word_ids:
            self.session_mistake_word_ids.append(word_id)
            
        if is_correct:
            self.session_correct += 1
            self.consecutive_correct += 1
        else:
            self.session_wrong += 1
            self.consecutive_correct = 0
            
        # Flashcard rejimi
        res = gamification.record_practice_answer(
            is_correct=is_correct,
            mode="flashcard",
            consecutive_correct=self.consecutive_correct
        )
        return res

    def get_random_distractors(self, count: int = 3) -> List[str]:
        """Multiple choice uchun chalg'ituvchi variantlarni olish."""
        if not self.current:
            return []
        target_lang = "uzbek" if self.direction == "en_uz" else "english"
        return db.get_random_distractors(self.current["id"], target_lang=target_lang, count=count)
