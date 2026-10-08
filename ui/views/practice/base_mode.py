from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from typing import Dict, Any

class BasePracticeMode(QWidget):
    """Barcha mashq rejimlari uchun ota sinf."""
    
    # Kiritilgan javob to'g'ri/xato ekanligini bildirish uchun signal
    # bool: is_correct
    answer_submitted = pyqtSignal(bool)
    
    # Flashcard reytingi uchun signal (easy, good, hard)
    flashcard_rated = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_word: Dict[str, Any] | None = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        
    def set_word(self, word_data: Dict[str, Any], **kwargs):
        """Yangi so'zni UI ga o'rnatish. Har bir rejim o'zicha qayta yozadi."""
        if word_data and not isinstance(word_data, dict):
            word_data = dict(word_data)
        self.current_word = word_data
        
    def check_answer(self, *args, **kwargs):
        """Javobni tekshirish mantiqi."""
        pass
        
    def clear_ui(self):
        """UIni tozalash (yangi so'z oldidan)."""
        pass
        
    def get_focus_widget(self):
        """Sahifa ochilganda qaysi vidjet fokusni olishi kerak."""
        return None
        
    def apply_theme(self, theme):
        """Rejim UI qismini mavzuga moslash."""
        pass
