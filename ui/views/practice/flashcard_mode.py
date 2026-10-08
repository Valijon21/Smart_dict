from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import Qt
from ui.views.practice.base_mode import BasePracticeMode

class FlashcardModeWidget(BasePracticeMode):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.flip_btn = QPushButton("🔄 Javobni ko'rsatish (Klaviatura: Space)")
        self.flip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.flip_btn.clicked.connect(self.on_flip)
        self.layout.addWidget(self.flip_btn)

        self.answer_reveal_box = QFrame()
        reveal_layout = QVBoxLayout(self.answer_reveal_box)
        reveal_layout.setContentsMargins(20, 18, 20, 18)
        reveal_layout.setSpacing(12)

        self.reveal_trans_label = QLabel("")
        self.reveal_trans_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reveal_trans_label.setStyleSheet("color: #10B981; font-size: 28px; font-weight: 700;")
        reveal_layout.addWidget(self.reveal_trans_label)

        self.reveal_info_label = QLabel("")
        self.reveal_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reveal_info_label.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        reveal_layout.addWidget(self.reveal_info_label)

        rating_btns = QHBoxLayout()
        rating_btns.setSpacing(12)

        self.rate_hard_btn = QPushButton("🔴 1. Qiyin (Bugun qaytariladi)")
        self.rate_hard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_hard_btn.clicked.connect(lambda: self.on_rate("hard"))
        rating_btns.addWidget(self.rate_hard_btn)

        self.rate_good_btn = QPushButton("🟡 2. Yaxshi (Eslab qoldim)")
        self.rate_good_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_good_btn.clicked.connect(lambda: self.on_rate("good"))
        rating_btns.addWidget(self.rate_good_btn)

        self.rate_easy_btn = QPushButton("🟢 3. Oson (Mustahkamlandi)")
        self.rate_easy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_easy_btn.clicked.connect(lambda: self.on_rate("easy"))
        rating_btns.addWidget(self.rate_easy_btn)

        reveal_layout.addLayout(rating_btns)
        
        self.layout.addWidget(self.answer_reveal_box)
        self.clear_ui()

    def set_word(self, word_data, direction="en_uz", **kwargs):
        super().set_word(word_data, **kwargs)
        self.clear_ui()
        if not self.current_word:
            return
            
        trans = self.current_word["uzbek"] if direction == "en_uz" else self.current_word["english"]
        self.reveal_trans_label.setText(trans)
        
        ex = self.current_word.get("example", "")
        self.reveal_info_label.setText(f"💡 {ex}" if ex else "")

    def clear_ui(self):
        self.flip_btn.setVisible(True)
        self.answer_reveal_box.setVisible(False)
        
    def on_flip(self):
        self.flip_btn.setVisible(False)
        self.answer_reveal_box.setVisible(True)
        
    def check_answer(self, **kwargs):
        # Space bosilganda flip qilamiz
        if self.flip_btn.isVisible():
            self.on_flip()
            
    def on_rate(self, quality: str):
        self.flashcard_rated.emit(quality)
        
    def apply_theme(self, t):
        self.flip_btn.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 10px; padding: 14px; font-size: 15px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {t.primary_light if not t.is_dark else '#4338CA'}; }}"
        )
        self.answer_reveal_box.setStyleSheet(f"background-color: {t.bg_card_secondary}; border-radius: 12px; border: 1px solid {t.border};")
        
        if t.is_dark:
            self.rate_hard_btn.setStyleSheet("QPushButton { background-color: #7F1D1D; color: white; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background-color: #991B1B; }")
            self.rate_good_btn.setStyleSheet("QPushButton { background-color: #92400E; color: white; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background-color: #B45309; }")
            self.rate_easy_btn.setStyleSheet("QPushButton { background-color: #065F46; color: white; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background-color: #047857; }")
        else:
            self.rate_hard_btn.setStyleSheet("QPushButton { background-color: #FEE2E2; color: #B91C1C; border: 1px solid #FCA5A5; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background-color: #FECACA; }")
            self.rate_good_btn.setStyleSheet("QPushButton { background-color: #FEF3C7; color: #B45309; border: 1px solid #FCD34D; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background-color: #FDE68A; }")
            self.rate_easy_btn.setStyleSheet("QPushButton { background-color: #DCFCE7; color: #15803D; border: 1px solid #86EFAC; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; } QPushButton:hover { background-color: #BBF7D0; }")
