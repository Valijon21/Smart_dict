from PyQt6.QtWidgets import QLabel, QLineEdit
from PyQt6.QtCore import Qt
from ui.views.practice.base_mode import BasePracticeMode
import re

def check_user_answer(user_text, current_word, direction):
    target = current_word["uzbek"] if direction == "en_uz" else current_word["english"]
    # Oddiy tozalash va solishtirish
    user_t = re.sub(r'[^a-z0-9]', '', user_text.lower().strip())
    target_t = re.sub(r'[^a-z0-9]', '', target.lower().strip())
    
    # Agar vergul bilan ajratilgan sinonimlar bo'lsa
    if target_t == "": return False
    
    parts = [re.sub(r'[^a-z0-9]', '', p.strip()) for p in target.lower().split(',')]
    return user_t in parts or user_t == target_t

class TypingModeWidget(BasePracticeMode):
    def __init__(self, direction="en_uz", parent=None):
        super().__init__(parent)
        self.direction = direction
        
        self.answer_input = QLineEdit()
        self.answer_input.setPlaceholderText("Tarjimasini yozing va Enter bosing...")
        self.answer_input.returnPressed.connect(self.on_enter_pressed)
        self.layout.addWidget(self.answer_input)

        self.hint_input = QLabel("💡 Maslahat: Javobni yozgach Enter ↵ bosing | Space — Talaffuzni qayta tinglash")
        self.hint_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_input.setStyleSheet("color: #6B7280; font-size: 12px;")
        self.layout.addWidget(self.hint_input)

    def set_word(self, word_data, **kwargs):
        super().set_word(word_data, **kwargs)
        self.clear_ui()

    def clear_ui(self):
        self.answer_input.clear()
        self.answer_input.setEnabled(True)
        self.answer_input.setStyleSheet("")
        
    def get_focus_widget(self):
        return self.answer_input

    def on_enter_pressed(self):
        self.check_answer()

    def check_answer(self, **kwargs):
        if not self.current_word:
            return
            
        user_text = self.answer_input.text().strip()
        is_correct = check_user_answer(user_text, self.current_word, self.direction)
        
        if is_correct:
            self.answer_input.setStyleSheet("border: 2px solid #10B981; background-color: #064E3B; color: white;")
        else:
            self.answer_input.setStyleSheet("border: 2px solid #EF4444; background-color: #7F1D1D; color: white;")
            
        self.answer_input.setEnabled(False)
        self.answer_submitted.emit(is_correct)
        
    def apply_theme(self, t):
        self.answer_input.setStyleSheet(
            f"QLineEdit {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 2px solid {t.border}; "
            f"border-radius: 10px; padding: 14px 16px; font-size: 16px; }} "
            f"QLineEdit:focus {{ border: 2px solid {t.primary}; background-color: {t.bg_app}; }}"
        )
