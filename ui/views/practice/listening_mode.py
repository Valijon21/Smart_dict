"""
Listening Mode Widget — Eshitib yozish mashq rejimi.
Foydalanuvchi inglizcha so'zning talaffuzini eshitadi va uni yozib kiritadi.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtCore import Qt, QTimer
from ui.views.practice.base_mode import BasePracticeMode
from services import tts_service
import re


def normalize_listening_text(text: str) -> str:
    """Tekshirish uchun so'zni normallashtirish."""
    if not text:
        return ""
    return re.sub(r"[^a-zA-Z0-9']", "", text.strip().lower())


def check_listening_answer(user_text: str, current_word: dict) -> bool:
    """Foydalanuvchi javobini tekshirish."""
    if not user_text or not current_word:
        return False
    target_raw = current_word.get("english", "")
    user_norm = normalize_listening_text(user_text)

    # Asosiy so'zni solishtirish
    target_norm = normalize_listening_text(target_raw)
    if user_norm == target_norm:
        return True

    # Agar vergul yoki slesh bilan ajratilgan variantlar bo'lsa
    parts = [normalize_listening_text(p) for p in re.split(r"[,/]+", target_raw) if p.strip()]
    return user_norm in parts


class ListeningModeWidget(BasePracticeMode):
    """
    Eshitib yozish rejimi vidjeti:
    - Ovozli talaffuzni qayta tinglash tugmalari (Normal va Sekin 0.75x)
    - Maslahat / Yordam (o'zbekcha tarjimasi va harflar soni)
    - Kiritish maydoni (QLineEdit)
    """

    def __init__(self, direction="en_uz", parent=None):
        super().__init__(parent)
        self.direction = direction

        # Audio boshqaruv paneli
        self.audio_row = QHBoxLayout()
        self.audio_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.audio_row.setSpacing(12)

        self.play_btn = QPushButton("🔊 Qayta tinglash (Space)")
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self.play_audio)
        self.audio_row.addWidget(self.play_btn)

        self.slow_btn = QPushButton("🐢 Sekin (0.75x)")
        self.slow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slow_btn.clicked.connect(self.play_slow_audio)
        self.audio_row.addWidget(self.slow_btn)

        self.layout.addLayout(self.audio_row)

        # Yordamchi maslahat (O'zbekcha tarjima va harf soni)
        self.hint_label = QLabel("")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: #A5B4FC; font-size: 14px; font-weight: 600;")
        self.layout.addWidget(self.hint_label)

        # Kiritish maydoni
        self.answer_input = QLineEdit()
        self.answer_input.setPlaceholderText("Eshitgan inglizcha so'zni yozing va Enter bosing...")
        self.answer_input.returnPressed.connect(self.on_enter_pressed)
        self.layout.addWidget(self.answer_input)

        self.sub_hint = QLabel("💡 Maslahat: Enter ↵ — Tekshirish | Space — Qayta tinglash")
        self.sub_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_hint.setStyleSheet("color: #6B7280; font-size: 12px;")
        self.layout.addWidget(self.sub_hint)

    def set_word(self, word_data, **kwargs):
        super().set_word(word_data, **kwargs)
        self.clear_ui()
        if self.current_word:
            uz = self.current_word.get("uzbek", "")
            eng = self.current_word.get("english", "")
            char_count = len(re.sub(r"\s+", "", eng))
            self.hint_label.setText(f"💡 Yordam: \"{uz}\"  •  {char_count} ta harf")
            # Yangi so'z o'rnatilganda avtomatik ovoz chiqarish
            QTimer.singleShot(150, self.play_audio)

    def clear_ui(self):
        self.answer_input.clear()
        self.answer_input.setEnabled(True)
        self.answer_input.setStyleSheet("")

    def get_focus_widget(self):
        return self.answer_input

    def on_enter_pressed(self):
        self.check_answer()

    def play_audio(self):
        if self.current_word and self.current_word.get("english"):
            tts_service.speak(self.current_word["english"], slow=False)

    def play_slow_audio(self):
        if self.current_word and self.current_word.get("english"):
            tts_service.speak(self.current_word["english"], slow=True)

    def check_answer(self, **kwargs):
        if not self.current_word:
            return

        user_text = self.answer_input.text().strip()
        is_correct = check_listening_answer(user_text, self.current_word)

        if is_correct:
            self.answer_input.setStyleSheet("border: 2px solid #10B981; background-color: #064E3B; color: white;")
        else:
            self.answer_input.setStyleSheet("border: 2px solid #EF4444; background-color: #7F1D1D; color: white;")

        self.answer_input.setEnabled(False)
        self.answer_submitted.emit(is_correct)

    def apply_theme(self, t):
        bg_card_sec = getattr(t, "bg_card_secondary", "#1E1E2E")
        self.play_btn.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
            f"padding: 10px 18px; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        self.slow_btn.setStyleSheet(
            f"QPushButton {{ background-color: {bg_card_sec}; "
            f"color: #10B981; border: 1px solid #059669; border-radius: 8px; "
            f"padding: 10px 16px; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: #065F46; color: white; }}"
        )
        self.answer_input.setStyleSheet(
            f"QLineEdit {{ background-color: {bg_card_sec}; "
            f"color: {t.text_main}; border: 2px solid {t.border}; "
            f"border-radius: 10px; padding: 14px 16px; font-size: 16px; }} "
            f"QLineEdit:focus {{ border: 2px solid {t.primary}; background-color: {t.bg_app}; }}"
        )
