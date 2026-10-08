import random
from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton
from PyQt6.QtCore import Qt
from ui.views.practice.base_mode import BasePracticeMode

class ChoiceModeWidget(BasePracticeMode):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.choice_buttons = []
        self.current_options = []
        self.correct_index = -1
        
        choice_layout = QGridLayout(self)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        choice_layout.setSpacing(12)

        for i in range(4):
            btn = QPushButton("")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self.check_choice(idx))
            choice_layout.addWidget(btn, i // 2, i % 2)
            self.choice_buttons.append(btn)

    def set_word(self, word_data, distractors=None, direction="en_uz", **kwargs):
        super().set_word(word_data, **kwargs)
        self.clear_ui()
        if not self.current_word or distractors is None:
            return
            
        trans = self.current_word["uzbek"] if direction == "en_uz" else self.current_word["english"]
        
        # 3 ta xato va 1 ta to'g'ri javobni aralashtirish
        options = distractors[:3]
        options.append(trans)
        random.shuffle(options)
        
        self.current_options = options
        self.correct_index = options.index(trans)
        
        for i, opt in enumerate(options):
            if i < len(self.choice_buttons):
                self.choice_buttons[i].setText(opt)

    def clear_ui(self):
        self.current_options = []
        self.correct_index = -1
        for btn in self.choice_buttons:
            btn.setText("")
            btn.setEnabled(True)
            self._apply_btn_style(btn, "normal")

    def check_choice(self, idx: int):
        if not self.current_word or self.correct_index < 0:
            return
            
        is_correct = (idx == self.correct_index)
        
        # Tugmalar holatini ko'rsatish
        for i, btn in enumerate(self.choice_buttons):
            btn.setEnabled(False)
            if i == self.correct_index:
                self._apply_btn_style(btn, "correct")
            elif i == idx and not is_correct:
                self._apply_btn_style(btn, "wrong")
            else:
                self._apply_btn_style(btn, "disabled")
                
        self.answer_submitted.emit(is_correct)
        
    def check_answer(self, **kwargs):
        # Multiple choice enter tugmasini qo'llab-quvvatlamaydi, 
        # foydalanuvchi variantlardan birini bosishi kerak.
        pass
        
    def apply_theme(self, t):
        self.theme = t
        for btn in self.choice_buttons:
            if btn.isEnabled():
                self._apply_btn_style(btn, "normal")

    def _apply_btn_style(self, btn, state: str):
        t = getattr(self, "theme", None)
        bg = "#2E2E3E"
        fg = "white"
        border = "#4B5563"
        hover_bg = "#374151"
        
        if t:
            bg = t.bg_card_secondary
            fg = t.text_main
            border = t.border
            hover_bg = t.bg_card
            
        if state == "normal":
            btn.setStyleSheet(f"QPushButton {{ background-color: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 10px; padding: 18px; font-size: 16px; font-weight: 600; }} QPushButton:hover {{ background-color: {hover_bg}; }}")
        elif state == "correct":
            btn.setStyleSheet("QPushButton { background-color: #064E3B; color: white; border: 2px solid #10B981; border-radius: 10px; padding: 18px; font-size: 16px; font-weight: 600; }")
        elif state == "wrong":
            btn.setStyleSheet("QPushButton { background-color: #7F1D1D; color: white; border: 2px solid #EF4444; border-radius: 10px; padding: 18px; font-size: 16px; font-weight: 600; }")
        elif state == "disabled":
            disabled_bg = "#1A1A2E" if getattr(t, "is_dark", True) else "#F3F4F6"
            disabled_fg = "#6B7280" if getattr(t, "is_dark", True) else "#9CA3AF"
            btn.setStyleSheet(f"QPushButton {{ background-color: {disabled_bg}; color: {disabled_fg}; border: 1px solid {border}; border-radius: 10px; padding: 18px; font-size: 16px; font-weight: 600; }}")
