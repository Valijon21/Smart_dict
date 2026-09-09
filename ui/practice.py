import random
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QGridLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent

import database as db
import tts
import sound_effects
import gamification
import theme_manager
import phonetics
import global_dict_service
from logger import get_logger

logger = get_logger("practice")


def _pill_badge(text: str, bg: str, fg: str, border: str = None) -> QLabel:
    """Mashq statistikasi uchun zamonaviy chip yorlig'i."""
    lbl = QLabel(text)
    b_css = f"border: 1px solid {border};" if border else "border: none;"
    lbl.setStyleSheet(
        f"background-color: {bg}; color: {fg}; {b_css}"
        f"border-radius: 9px; padding: 5px 12px; font-size: 12px; font-weight: 600;"
    )
    return lbl


class PracticeWidget(QWidget):
    """direction: 'en_uz' -> ingliz so'zi ko'rsatiladi, o'zbekchasi so'raladi
                  'uz_en' -> teskarisi"""

    def __init__(self, direction: str = "en_uz", on_finish_refresh=None):
        super().__init__()
        self.direction = direction
        self.on_finish_refresh = on_finish_refresh
        self.queue: list = []
        self.current = None
        self.custom_word_ids: list[int] | None = None
        self.session_correct = 0
        self.session_wrong = 0
        self.batch_total = 0
        self.consecutive_correct = 0
        self.is_checking = False
        self.quiz_mode = "typing"  # "typing" | "choice" | "flashcard" | "listening" | "scramble" | "cloze"
        self.current_options = []
        self.card_flipped = False
        self.scramble_tiles_data = []
        self.scramble_typed_chars = []
        self.cloze_data: dict | None = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- 1. Header va Rejim tanlash ---
        top_header_row = QHBoxLayout()
        title = "Ingliz → O'zbek" if direction == "en_uz" else "O'zbek → Ingliz"
        header = QLabel(f"⚡ Mashq trenajyori: {title}")
        header.setStyleSheet("color: white; font-size: 20px; font-weight: 700;")
        top_header_row.addWidget(header)
        top_header_row.addStretch()

        # Mashq usullari
        self.mode_btn_typing = QPushButton("✍️ Yozma")
        self.mode_btn_typing.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn_typing.setStyleSheet(self._mode_type_style(True))
        self.mode_btn_typing.clicked.connect(lambda: self.set_quiz_mode("typing"))

        self.mode_btn_choice = QPushButton("🎯 4 ta variant")
        self.mode_btn_choice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn_choice.setStyleSheet(self._mode_type_style(False))
        self.mode_btn_choice.clicked.connect(lambda: self.set_quiz_mode("choice"))

        self.mode_btn_flashcard = QPushButton("🎴 Flashcard")
        self.mode_btn_flashcard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn_flashcard.setStyleSheet(self._mode_type_style(False))
        self.mode_btn_flashcard.clicked.connect(lambda: self.set_quiz_mode("flashcard"))

        self.mode_btn_listening = QPushButton("🎧 Eshitib yozish")
        self.mode_btn_listening.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn_listening.setStyleSheet(self._mode_type_style(False))
        self.mode_btn_listening.clicked.connect(lambda: self.set_quiz_mode("listening"))

        self.mode_btn_scramble = QPushButton("🔤 Harf terish")
        self.mode_btn_scramble.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn_scramble.setStyleSheet(self._mode_type_style(False))
        self.mode_btn_scramble.clicked.connect(lambda: self.set_quiz_mode("scramble"))

        self.mode_btn_cloze = QPushButton("🧩 Bo'sh joy")
        self.mode_btn_cloze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_btn_cloze.setStyleSheet(self._mode_type_style(False))
        self.mode_btn_cloze.clicked.connect(lambda: self.set_quiz_mode("cloze"))

        top_header_row.addWidget(self.mode_btn_typing)
        top_header_row.addWidget(self.mode_btn_choice)
        top_header_row.addWidget(self.mode_btn_flashcard)
        top_header_row.addWidget(self.mode_btn_listening)
        top_header_row.addWidget(self.mode_btn_scramble)
        top_header_row.addWidget(self.mode_btn_cloze)
        layout.addLayout(top_header_row)

        # --- 2. Yuqori statistika paneli (Chiplar va Progress bar) ---
        self.stat_frame = QFrame()
        self.stat_frame.setStyleSheet(
            "background-color: #1A1A2E; border-radius: 12px; border: 1px solid #2E2850;"
        )
        stat_layout = QVBoxLayout(self.stat_frame)
        stat_layout.setContentsMargins(16, 12, 16, 12)
        stat_layout.setSpacing(10)

        # Badges row: Qoldi | Reja | Bugun | To'g'ri | Xato
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)

        self.badge_remaining = _pill_badge("📌 Qoldi: 0", "#0C2D48", "#38BDF8", "#0284C7")
        self.badge_goal = _pill_badge("🎯 Kunlik reja: 0", "#251C48", "#C4B5FD", "#6366F1")
        self.badge_today = _pill_badge("🔥 Bugun: 0 / 0", "#1E1B4B", "#A5B4FC", "#4338CA")
        self.badge_correct = _pill_badge("✅ To'g'ri: 0", "#062E1F", "#34D399", "#059669")
        self.badge_wrong = _pill_badge("❌ Xato: 0", "#381A1A", "#F87171", "#7F1D1D")

        badges_row.addWidget(self.badge_remaining)
        badges_row.addWidget(self.badge_goal)
        badges_row.addWidget(self.badge_today)
        badges_row.addWidget(self.badge_correct)
        badges_row.addWidget(self.badge_wrong)
        badges_row.addStretch()

        self.mode_label = QLabel("📚 Rejim: Kunlik reja mashqi")
        self.mode_label.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: 500;")
        badges_row.addWidget(self.mode_label)

        self.filter_latest_btn = QPushButton("🆕 Faqat oxirgi so'zlar")
        self.filter_latest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_latest_btn.setStyleSheet(
            "QPushButton { background-color: #312E81; color: #C7D2FE; border: 1px solid #4338CA;"
            "border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4338CA; color: white; }"
        )
        self.filter_latest_btn.clicked.connect(self.load_latest_added)
        badges_row.addWidget(self.filter_latest_btn)

        self.filter_weak_btn = QPushButton("⚠️ Zaif so'zlar")
        self.filter_weak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_weak_btn.setStyleSheet(
            "QPushButton { background-color: #4C1D1D; color: #FCA5A5; border: 1px solid #7F1D1D;"
            "border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #7F1D1D; color: white; }"
        )
        self.filter_weak_btn.clicked.connect(self.load_weak_words)
        badges_row.addWidget(self.filter_weak_btn)

        self.all_words_btn = QPushButton("✖ Kunlik rejaga qaytish")
        self.all_words_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_words_btn.setStyleSheet(
            "QPushButton { background-color: #374151; color: white; border-radius: 6px; padding: 4px 10px; font-size: 12px; }"
            "QPushButton:hover { background-color: #4B5563; }"
        )
        self.all_words_btn.clicked.connect(self.reset_to_all)
        self.all_words_btn.setVisible(False)
        badges_row.addWidget(self.all_words_btn)

        stat_layout.addLayout(badges_row)

        # Progress bar (Gradientli progress satri)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Progress: %v / %m ta so'z (%p%)")
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #12121C;
                border: 1px solid #232338;
                border-radius: 7px;
                height: 16px;
                text-align: center;
                color: white;
                font-size: 11px;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #10B981);
                border-radius: 6px;
            }
            """
        )
        stat_layout.addWidget(self.progress_bar)
        layout.addWidget(self.stat_frame)

        # --- 3. Asosiy Interaktiv Karta ---
        self.quiz_card = QFrame()
        self.quiz_card.setStyleSheet(
            "background-color: #1E1E2E; border-radius: 16px; border: 1px solid #2A2A3C;"
        )
        card_layout = QVBoxLayout(self.quiz_card)
        card_layout.setContentsMargins(36, 28, 36, 28)
        card_layout.setSpacing(18)

        # So'z darajasi yorlig'i (Box va Status)
        self.word_info_badge = QLabel("")
        self.word_info_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_info_badge.setStyleSheet("color: #818CF8; font-size: 12px; font-weight: 600;")
        card_layout.addWidget(self.word_info_badge)

        # So'z ko'rsatish qatori (va katta 🔊 audio tugmasi)
        word_row = QHBoxLayout()
        word_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        word_row.setSpacing(14)

        self.word_label = QLabel("")
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setStyleSheet("color: white; font-size: 36px; font-weight: 700;")
        word_row.addWidget(self.word_label)

        self.audio_btn = QPushButton("🔊")
        self.audio_btn.setToolTip("Ovozli talaffuz (Klaviatura: Space)")
        self.audio_btn.setFixedSize(42, 42)
        self.audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audio_btn.setStyleSheet(
            "QPushButton { background-color: #24243A; color: #818CF8; border: 1px solid #3730A3; "
            "border-radius: 21px; font-size: 20px; }"
            "QPushButton:hover { background-color: #4F46E5; color: white; border-color: #818CF8; }"
        )
        self.audio_btn.clicked.connect(self.play_audio)
        word_row.addWidget(self.audio_btn)

        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setToolTip("O'z talaffuzingizni sinash va baholash")
        self.mic_btn.setFixedSize(42, 42)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setStyleSheet(
            "QPushButton { background-color: #24243A; color: #F43F5E; border: 1px solid #881337; "
            "border-radius: 21px; font-size: 18px; }"
            "QPushButton:hover { background-color: #E11D48; color: white; border-color: #FB7185; }"
        )
        self.mic_btn.clicked.connect(self.check_pronunciation)
        word_row.addWidget(self.mic_btn)

        card_layout.addLayout(word_row)

        # Fonetik transkripsiya (IPA) va So'z turkumi (POS) qatori
        self.phonetic_row_widget = QWidget()
        self.phonetic_row = QHBoxLayout(self.phonetic_row_widget)
        self.phonetic_row.setContentsMargins(0, 0, 0, 0)
        self.phonetic_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phonetic_row.setSpacing(8)

        self.phonetic_label = QLabel("")
        self.phonetic_label.setStyleSheet("color: #A5B4FC; font-size: 14px; font-weight: 500;")
        self.phonetic_row.addWidget(self.phonetic_label)

        self.pos_badge = QLabel("")
        self.pos_badge.setStyleSheet(
            "background-color: #312E81; color: #C7D2FE; font-size: 12px; font-weight: 700; "
            "border-radius: 4px; padding: 2px 6px;"
        )
        self.phonetic_row.addWidget(self.pos_badge)
        self.phonetic_row_widget.setVisible(False)
        card_layout.addWidget(self.phonetic_row_widget)

        # 1-usul: Yozma kiritish maydoni (Typing)
        self.typing_container = QWidget()
        typing_layout = QVBoxLayout(self.typing_container)
        typing_layout.setContentsMargins(0, 0, 0, 0)
        typing_layout.setSpacing(10)

        self.answer_input = QLineEdit()
        self.answer_input.setPlaceholderText("Tarjimasini yozing va Enter bosing...")
        self.answer_input.setStyleSheet(
            "QLineEdit { background-color: #151521; color: white; border: 2px solid #2A2A3C;"
            "border-radius: 10px; padding: 14px 16px; font-size: 16px; }"
            "QLineEdit:focus { border: 2px solid #6366F1; background-color: #1A1A2A; }"
        )
        self.answer_input.returnPressed.connect(self.check_answer)
        typing_layout.addWidget(self.answer_input)

        hint_input = QLabel("💡 Maslahat: Javobni yozgach Enter ↵ bosing | Space — Talaffuzni qayta tinglash")
        hint_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_input.setStyleSheet("color: #6B7280; font-size: 12px;")
        typing_layout.addWidget(hint_input)

        card_layout.addWidget(self.typing_container)

        # 2-usul: 4 ta Variantli test (Multiple Choice)
        self.choice_container = QWidget()
        choice_layout = QGridLayout(self.choice_container)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        choice_layout.setSpacing(12)

        self.choice_buttons = []
        for i in range(4):
            btn = QPushButton("")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._choice_btn_style("normal"))
            btn.clicked.connect(lambda checked, idx=i: self.check_choice(idx))
            choice_layout.addWidget(btn, i // 2, i % 2)
            self.choice_buttons.append(btn)

        self.choice_container.setVisible(False)
        card_layout.addWidget(self.choice_container)

        # 3-usul: Flashcard (Aylanuvchi karta — Anki uslubi)
        self.flashcard_container = QWidget()
        flash_layout = QVBoxLayout(self.flashcard_container)
        flash_layout.setContentsMargins(0, 0, 0, 0)
        flash_layout.setSpacing(14)

        self.flip_btn = QPushButton("🔄 Javobni ko'rsatish (Klaviatura: Space)")
        self.flip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.flip_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border-radius: 10px; padding: 14px; font-size: 15px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        self.flip_btn.clicked.connect(self.flip_flashcard)
        flash_layout.addWidget(self.flip_btn)

        self.answer_reveal_box = QFrame()
        self.answer_reveal_box.setStyleSheet(
            "background-color: #151521; border-radius: 12px; border: 1px solid #2A2A3C;"
        )
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
        self.rate_hard_btn.setStyleSheet(
            "QPushButton { background-color: #7F1D1D; color: white; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #991B1B; }"
        )
        self.rate_hard_btn.clicked.connect(lambda: self.grade_flashcard("hard"))

        self.rate_good_btn = QPushButton("🟡 2. Yaxshi (Eslab qoldim)")
        self.rate_good_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_good_btn.setStyleSheet(
            "QPushButton { background-color: #92400E; color: white; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #B45309; }"
        )
        self.rate_good_btn.clicked.connect(lambda: self.grade_flashcard("good"))

        self.rate_easy_btn = QPushButton("🟢 3. Oson (Mustahkamlandi)")
        self.rate_easy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rate_easy_btn.setStyleSheet(
            "QPushButton { background-color: #065F46; color: white; border-radius: 8px; padding: 12px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #047857; }"
        )
        self.rate_easy_btn.clicked.connect(lambda: self.grade_flashcard("easy"))

        rating_btns.addWidget(self.rate_hard_btn)
        rating_btns.addWidget(self.rate_good_btn)
        rating_btns.addWidget(self.rate_easy_btn)
        reveal_layout.addLayout(rating_btns)

        self.answer_reveal_box.setVisible(False)
        flash_layout.addWidget(self.answer_reveal_box)

        self.flashcard_container.setVisible(False)
        card_layout.addWidget(self.flashcard_container)

        # 4-usul: Harflarni terish (Word Scramble / Anagram)
        self.scramble_container = QWidget()
        scramble_layout = QVBoxLayout(self.scramble_container)
        scramble_layout.setContentsMargins(0, 0, 0, 0)
        scramble_layout.setSpacing(14)

        self.scramble_answer_display = QLabel("")
        self.scramble_answer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scramble_answer_display.setStyleSheet(
            "background-color: #151521; color: #10B981; font-size: 26px; font-weight: 800; "
            "letter-spacing: 4px; border: 2px dashed #4F46E5; border-radius: 12px; padding: 14px;"
        )
        scramble_layout.addWidget(self.scramble_answer_display)

        self.scramble_tiles_container = QWidget()
        self.scramble_tiles_layout = QHBoxLayout(self.scramble_tiles_container)
        self.scramble_tiles_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scramble_tiles_layout.setSpacing(8)
        scramble_layout.addWidget(self.scramble_tiles_container)

        scramble_actions_row = QHBoxLayout()
        scramble_actions_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scramble_actions_row.setSpacing(12)

        self.scramble_back_btn = QPushButton("⌫ Bitta o'chirish (Backspace)")
        self.scramble_back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scramble_back_btn.setStyleSheet(
            "QPushButton { background-color: #2E2E3E; color: #E5E7EB; border: 1px solid #4B5563; "
            "border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #374151; }"
        )
        self.scramble_back_btn.clicked.connect(self._scramble_backspace)
        scramble_actions_row.addWidget(self.scramble_back_btn)

        self.scramble_clear_btn = QPushButton("🧹 Hammasini tozalash")
        self.scramble_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scramble_clear_btn.setStyleSheet(
            "QPushButton { background-color: #2E2E3E; color: #E5E7EB; border: 1px solid #4B5563; "
            "border-radius: 6px; padding: 8px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #374151; }"
        )
        self.scramble_clear_btn.clicked.connect(self._scramble_clear)
        scramble_actions_row.addWidget(self.scramble_clear_btn)

        scramble_layout.addLayout(scramble_actions_row)
        self.scramble_container.setVisible(False)
        card_layout.addWidget(self.scramble_container)

        # 5-usul: Gap ichida bo'sh joyni to'ldirish (Cloze / Sentence Completion)
        self.cloze_container = QWidget()
        cloze_layout = QVBoxLayout(self.cloze_container)
        cloze_layout.setContentsMargins(0, 0, 0, 0)
        cloze_layout.setSpacing(12)

        self.cloze_sentence_frame = QFrame()
        self.cloze_sentence_frame.setStyleSheet(
            "background-color: #151521; border-radius: 12px; border: 1.5px solid #3730A3;"
        )
        cloze_sentence_layout = QVBoxLayout(self.cloze_sentence_frame)
        cloze_sentence_layout.setContentsMargins(18, 16, 18, 16)
        cloze_sentence_layout.setSpacing(8)

        self.cloze_sentence_display = QLabel("")
        self.cloze_sentence_display.setWordWrap(True)
        self.cloze_sentence_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cloze_sentence_display.setStyleSheet("font-size: 18px; color: #FFFFFF; font-weight: 500;")
        cloze_sentence_layout.addWidget(self.cloze_sentence_display)

        self.cloze_hint_lbl = QLabel("")
        self.cloze_hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cloze_hint_lbl.setStyleSheet("font-size: 13px; color: #A5B4FC; font-weight: 600;")
        cloze_sentence_layout.addWidget(self.cloze_hint_lbl)
        cloze_layout.addWidget(self.cloze_sentence_frame)

        self.cloze_input = QLineEdit()
        self.cloze_input.setPlaceholderText("Bo'sh joydagi so'zni yozing va Enter bosing...")
        self.cloze_input.setStyleSheet(
            "QLineEdit { background-color: #151521; color: white; border: 2px solid #2A2A3C;"
            "border-radius: 10px; padding: 14px 16px; font-size: 16px; }"
            "QLineEdit:focus { border: 2px solid #6366F1; background-color: #1A1A2A; }"
        )
        self.cloze_input.returnPressed.connect(self.check_answer)
        cloze_layout.addWidget(self.cloze_input)

        cloze_actions_row = QHBoxLayout()
        cloze_actions_row.setSpacing(10)

        self.cloze_hint_btn = QPushButton("💡 1-harfni ko'rsatish")
        self.cloze_hint_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cloze_hint_btn.setStyleSheet(
            "QPushButton { background-color: #2E2E3E; color: #FCD34D; border: 1px solid #D97706; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #78350F; color: white; }"
        )
        self.cloze_hint_btn.clicked.connect(self._cloze_show_first_letter)
        cloze_actions_row.addWidget(self.cloze_hint_btn)

        cloze_hint_info = QLabel("Maslahat: Enter ↵ — Tekshirish  |  Space — Talaffuz")
        cloze_hint_info.setStyleSheet("color: #6B7280; font-size: 12px;")
        cloze_actions_row.addWidget(cloze_hint_info)
        cloze_actions_row.addStretch()

        cloze_layout.addLayout(cloze_actions_row)
        self.cloze_container.setVisible(False)
        card_layout.addWidget(self.cloze_container)

        # Feedback (✅ To'g'ri / ❌ Xato)
        self.feedback_label = QLabel("")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setStyleSheet("font-size: 15px; font-weight: 600; min-height: 28px;")
        card_layout.addWidget(self.feedback_label)

        # Misol gap va kontekst paneli (💡 Example Sentence)
        self.example_card = QFrame()
        self.example_card.setStyleSheet(
            "background-color: #131322; border: 1px solid #3730A3; border-radius: 10px;"
        )
        ex_layout = QVBoxLayout(self.example_card)
        ex_layout.setContentsMargins(16, 10, 16, 10)
        self.example_text_lbl = QLabel("")
        self.example_text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_text_lbl.setWordWrap(True)
        self.example_text_lbl.setStyleSheet("color: #C4B5FD; font-size: 14px; font-style: italic;")
        ex_layout.addWidget(self.example_text_lbl)
        self.example_card.setVisible(False)
        card_layout.addWidget(self.example_card)

        # Pastki amallar qatori
        btn_row = QHBoxLayout()
        self.restart_btn = QPushButton("🔄 Keyingi partiyani boshlash")
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; border: none; border-radius: 10px; padding: 12px 28px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #059669; }"
        )
        self.restart_btn.clicked.connect(self.load_batch)
        self.restart_btn.setVisible(False)
        btn_row.addWidget(self.restart_btn)

        btn_row.addStretch()
        self.submit_btn = QPushButton("Tekshirish ↵")
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border: none; border-radius: 10px; padding: 12px 28px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        self.submit_btn.clicked.connect(self.check_answer)
        btn_row.addWidget(self.submit_btn)
        card_layout.addLayout(btn_row)

        layout.addWidget(self.quiz_card)
        layout.addStretch()

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

        self.load_batch()

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "stat_frame"):
            self.stat_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        if hasattr(self, "quiz_card"):
            self.quiz_card.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 16px; border: 1px solid {t.border};")
        if hasattr(self, "answer_input"):
            self.answer_input.setStyleSheet(
                f"QLineEdit {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 2px solid {t.border}; "
                f"border-radius: 10px; padding: 14px 16px; font-size: 16px; }} "
                f"QLineEdit:focus {{ border: 2px solid {t.primary}; background-color: {t.bg_app}; }}"
            )
        if hasattr(self, "answer_reveal_box"):
            self.answer_reveal_box.setStyleSheet(f"background-color: {t.bg_card_secondary}; border-radius: 12px; border: 1px solid {t.border};")
        if hasattr(self, "scramble_answer_display"):
            self.scramble_answer_display.setStyleSheet(
                f"background-color: {t.bg_card_secondary}; color: #10B981; font-size: 26px; font-weight: 800; "
                f"letter-spacing: 4px; border: 2px dashed {t.primary}; border-radius: 12px; padding: 14px;"
            )
        if hasattr(self, "example_card"):
            self.example_card.setStyleSheet(f"background-color: {t.bg_card_secondary}; border: 1px solid {t.border}; border-radius: 10px;")
        if hasattr(self, "quiz_mode"):
            self.mode_btn_typing.setStyleSheet(self._mode_type_style(self.quiz_mode == "typing"))
            self.mode_btn_choice.setStyleSheet(self._mode_type_style(self.quiz_mode == "choice"))
            self.mode_btn_flashcard.setStyleSheet(self._mode_type_style(self.quiz_mode == "flashcard"))
            self.mode_btn_listening.setStyleSheet(self._mode_type_style(self.quiz_mode == "listening"))
            self.mode_btn_scramble.setStyleSheet(self._mode_type_style(self.quiz_mode == "scramble"))
            if hasattr(self, "mode_btn_cloze"):
                self.mode_btn_cloze.setStyleSheet(self._mode_type_style(self.quiz_mode == "cloze"))
        if hasattr(self, "cloze_sentence_frame"):
            self.cloze_sentence_frame.setStyleSheet(
                f"background-color: {t.bg_card_secondary}; border-radius: 12px; border: 1.5px solid {t.border};"
            )
        if hasattr(self, "cloze_input"):
            self.cloze_input.setStyleSheet(
                f"QLineEdit {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 2px solid {t.border}; "
                f"border-radius: 10px; padding: 14px 16px; font-size: 16px; }} "
                f"QLineEdit:focus {{ border: 2px solid {t.primary}; background-color: {t.bg_app}; }}"
            )
        if hasattr(self, "cloze_sentence_display"):
            self.cloze_sentence_display.setStyleSheet(f"font-size: 18px; color: {t.text_main}; font-weight: 500;")
        if hasattr(self, "choice_buttons") and getattr(self, "quiz_mode", "") == "choice" and not getattr(self, "is_checking", False):
            for btn in self.choice_buttons:
                btn.setStyleSheet(self._choice_btn_style("normal"))

    def _mode_type_style(self, active: bool) -> str:
        t = theme_manager.get_active_theme()
        if active:
            return (
                f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
                f"border-radius: 8px; padding: 7px 16px; font-size: 12px; font-weight: 600; }}"
            )
        return (
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_muted}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 7px 16px; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {t.bg_card}; color: {t.text_main}; border-color: {t.primary}; }}"
        )

    def _choice_btn_style(self, state: str = "normal") -> str:
        t = theme_manager.get_active_theme()
        if state == "correct":
            return (
                "QPushButton { background-color: #064E3B; color: #34D399; border: 2px solid #10B981;"
                "border-radius: 10px; padding: 16px 20px; font-size: 16px; font-weight: 600; text-align: left; }"
            )
        elif state == "wrong":
            return (
                "QPushButton { background-color: #7F1D1D; color: #FCA5A5; border: 2px solid #EF4444;"
                "border-radius: 10px; padding: 16px 20px; font-size: 16px; font-weight: 600; text-align: left; }"
            )
        return (
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 10px; padding: 16px 20px; font-size: 16px; font-weight: 500; text-align: left; }} "
            f"QPushButton:hover {{ background-color: {t.bg_card}; border-color: {t.primary}; color: {t.primary_light}; }}"
        )

    def set_quiz_mode(self, mode: str):
        self.quiz_mode = mode
        logger.info(f"Mashq usuli o'zgartirildi: '{mode}' ({self.direction})")
        self.mode_btn_typing.setStyleSheet(self._mode_type_style(mode == "typing"))
        self.mode_btn_choice.setStyleSheet(self._mode_type_style(mode == "choice"))
        self.mode_btn_flashcard.setStyleSheet(self._mode_type_style(mode == "flashcard"))
        self.mode_btn_listening.setStyleSheet(self._mode_type_style(mode == "listening"))
        self.mode_btn_scramble.setStyleSheet(self._mode_type_style(mode == "scramble"))
        if hasattr(self, "mode_btn_cloze"):
            self.mode_btn_cloze.setStyleSheet(self._mode_type_style(mode == "cloze"))

        has_word = bool(self.queue or self.current)
        self.typing_container.setVisible(mode in ("typing", "listening"))
        self.submit_btn.setVisible(mode in ("typing", "listening", "scramble", "cloze") and has_word)
        self.choice_container.setVisible(mode == "choice")
        self.flashcard_container.setVisible(mode == "flashcard")
        self.scramble_container.setVisible(mode == "scramble")
        if hasattr(self, "cloze_container"):
            self.cloze_container.setVisible(mode == "cloze")

        if self.current:
            self._render_current_mode()

    def _show_example(self):
        """Mavjud bo'lsa so'zning misol gapini ko'rsatish."""
        if not self.current:
            self.example_card.setVisible(False)
            return
        ex = self.current["example"] if "example" in self.current.keys() and self.current["example"] else ""
        if ex:
            self.example_text_lbl.setText(f"💡 <b>Misol:</b> <i>\"{ex}\"</i>")
            self.example_card.setVisible(True)
        else:
            self.example_card.setVisible(False)

    def _setup_scramble(self):
        """Harflarni terish mashqini tayyorlash."""
        if not self.current:
            return
        target = self.current["english"].strip().lower()

        # Eski tugmalarni tozalash
        while self.scramble_tiles_layout.count():
            item = self.scramble_tiles_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.scramble_tiles_data = []
        self.scramble_typed_chars = []

        scrambled = [c for c in target if not c.isspace()]
        random.shuffle(scrambled)
        # Agar tasodifan asl so'z bilan bir xil bo'lib qolsa
        if "".join(scrambled) == target.replace(" ", "") and len(scrambled) > 2:
            scrambled.reverse()

        for idx, char in enumerate(scrambled):
            btn = QPushButton(char.upper())
            btn.setFixedSize(46, 46)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color: #242044; color: #E0E7FF; border: 2px solid #4F46E5; "
                "border-radius: 8px; font-size: 19px; font-weight: 700; }"
                "QPushButton:hover { background-color: #4F46E5; color: white; }"
                "QPushButton:disabled { background-color: #161622; color: #4B5563; border-color: #2A2A3C; }"
            )
            btn.clicked.connect(lambda _, i=idx: self._scramble_click_tile(i))
            self.scramble_tiles_layout.addWidget(btn)
            self.scramble_tiles_data.append({"char": char, "btn": btn, "used": False})

        self._update_scramble_display()

    def _scramble_click_tile(self, tile_idx: int):
        if tile_idx >= len(self.scramble_tiles_data) or self.is_checking:
            return
        item = self.scramble_tiles_data[tile_idx]
        if item["used"]:
            return
        item["used"] = True
        item["btn"].setEnabled(False)
        self.scramble_typed_chars.append({"char": item["char"], "tile_idx": tile_idx})
        self._update_scramble_display()

        # Agar barcha harflar terilgan bo'lsa, avtomatik tekshiramiz
        target_len = len([c for c in self.current["english"].strip() if not c.isspace()])
        if len(self.scramble_typed_chars) == target_len:
            self.check_answer()

    def _scramble_backspace(self):
        if not self.scramble_typed_chars or self.is_checking:
            return
        last = self.scramble_typed_chars.pop()
        tile_idx = last["tile_idx"]
        if 0 <= tile_idx < len(self.scramble_tiles_data):
            self.scramble_tiles_data[tile_idx]["used"] = False
            self.scramble_tiles_data[tile_idx]["btn"].setEnabled(True)
        self._update_scramble_display()

    def _scramble_clear(self):
        if self.is_checking:
            return
        for item in self.scramble_tiles_data:
            item["used"] = False
            item["btn"].setEnabled(True)
        self.scramble_typed_chars = []
        self._update_scramble_display()

    def _update_scramble_display(self):
        if not self.current:
            return
        target_len = len([c for c in self.current["english"].strip() if not c.isspace()])
        typed_str = "".join([x["char"] for x in self.scramble_typed_chars]).upper()
        remaining_slots = max(0, target_len - len(self.scramble_typed_chars))
        slots_str = "  ".join(list(typed_str) + ["_"] * remaining_slots)
        self.scramble_answer_display.setText(slots_str)

    def _prepare_cloze_data(self) -> dict | None:
        """Hozirgi so'z uchun misol gapni topish va bo'sh joy qilib formatlash."""
        if not self.current:
            return None

        eng = self.current["english"].strip()
        uz = self.current["uzbek"].strip()
        ex = self.current["example"] if "example" in self.current.keys() and self.current["example"] else ""
        ex = ex.strip()

        # Agar misol gap bo'lmasa yoki juda qisqa bo'lsa, global 64k lug'atdan qidiramiz
        if not ex or len(ex) < 10:
            try:
                g_matches = global_dict_service.search_global_words(eng, limit=1)
                if g_matches and g_matches[0].get("example"):
                    cand = g_matches[0]["example"].strip()
                    if cand.startswith("•") or cand.startswith(""):
                        cand = cand[1:].strip()
                    if len(cand) >= 10:
                        ex = cand
            except Exception as e:
                logger.debug(f"Global misol qidirishda xatolik: {e}")

        # Agar hali ham misol bo'lmasa, grammatik to'g'ri kontekstli shablon yaratamiz
        if not ex or len(ex) < 8:
            ex = f"It is very important to learn how to use '{eng}' in your daily English sentences."

        # Gap ichidan target so'z yoki uning grammatik shakllarini qidiramiz
        clean_eng = re.escape(eng)
        stem = clean_eng
        if len(eng) > 4 and eng.endswith("e"):
            stem = re.escape(eng[:-1])
        elif len(eng) > 4 and eng.endswith("y"):
            stem = re.escape(eng[:-1])

        pattern = re.compile(rf"\b({clean_eng}\w*|{stem}\w*)\b", re.IGNORECASE)
        match = pattern.search(ex)

        if match:
            found_token = match.group(1)
            start, end = match.span(1)
            before = ex[:start]
            after = ex[end:]
            blank_html = "<span style='color: #38BDF8; font-weight: 800; background-color: rgba(56, 189, 248, 0.15); border-radius: 6px; padding: 2px 12px; border-bottom: 2px solid #38BDF8;'>&nbsp;[ &nbsp;______&nbsp; ]&nbsp;</span>"
            masked_sentence = f"{before}{blank_html}{after}"
            correct_tokens = [found_token.lower(), eng.lower()]
        else:
            found_token = eng
            blank_html = "<span style='color: #38BDF8; font-weight: 800; background-color: rgba(56, 189, 248, 0.15); border-radius: 6px; padding: 2px 12px; border-bottom: 2px solid #38BDF8;'>&nbsp;[ &nbsp;______&nbsp; ]&nbsp;</span>"
            masked_sentence = f"In English, the word {blank_html} translates to '{uz}'."
            correct_tokens = [eng.lower()]

        for alt in eng.split(","):
            alt_clean = alt.strip().lower()
            if alt_clean:
                correct_tokens.append(alt_clean)

        uz_first = uz.split(",")[0].strip()

        return {
            "sentence_masked": masked_sentence,
            "original_sentence": ex,
            "target_token": found_token,
            "correct_tokens": list(dict.fromkeys(correct_tokens)),
            "uzbek_hint": uz_first,
        }

    def _setup_cloze(self):
        """Bo'sh joyni to'ldirish (Cloze) mashqini sozlash."""
        self.cloze_data = self._prepare_cloze_data()
        if not self.cloze_data:
            return

        self.cloze_sentence_display.setText(self.cloze_data["sentence_masked"])
        tok_len = len(self.cloze_data["target_token"])
        pos_val = self.current["part_of_speech"] if ("part_of_speech" in self.current.keys() and self.current["part_of_speech"]) else ""
        pos_txt = f"[{pos_val}]" if pos_val else ""
        self.cloze_hint_lbl.setText(
            f"💡 Tarjima: \"{self.cloze_data['uzbek_hint']}\"  •  {pos_txt}  •  {tok_len} ta harf"
        )
        self.cloze_input.clear()
        self.cloze_input.setPlaceholderText(f"Bo'sh joydagi so'zni yozing ({tok_len} ta harf)...")
        self.cloze_input.setEnabled(True)
        self.cloze_input.setFocus()
        self.cloze_hint_btn.setEnabled(True)
        self.cloze_hint_btn.setText("💡 1-harfni ko'rsatish")

    def _cloze_show_first_letter(self):
        """Cloze rejimida foydalanuvchiga yordam sifatida birinchi harfni ko'rsatish."""
        if not hasattr(self, "cloze_data") or not self.cloze_data:
            return
        tok = self.cloze_data.get("target_token", "")
        if tok:
            first_c = tok[0].upper()
            self.cloze_hint_btn.setText(f"💡 Bosh harfi: '{first_c}...'")
            self.cloze_hint_btn.setEnabled(False)
            if not self.cloze_input.text():
                self.cloze_input.setText(first_c.lower())
                self.cloze_input.setFocus()

    def check_pronunciation(self):
        """Hozirgi so'z uchun Windows Native talaffuzni sinash dialogini ochish."""
        if not self.current:
            return
        import speech_recognizer
        speech_recognizer.open_pronunciation_dialog(self.current, parent=self)

    def play_audio(self):
        if not self.isVisible():
            return
        if self.current:
            word = self.current["english"]
            logger.info(f"Mashq karnay tugmasi bosildi: '{word}' (rejim: {self.quiz_mode}, yo'nalish: {self.direction})")

            self.audio_btn.setText("🔈")
            self.audio_btn.setStyleSheet(
                "QPushButton { background-color: #4F46E5; color: white; border: 2px solid #818CF8; "
                "border-radius: 21px; font-size: 20px; width: 42px; height: 42px; }"
            )
            QTimer.singleShot(350, self._revert_practice_audio_btn)
            tts.speak(word)

    def _revert_practice_audio_btn(self):
        try:
            self.audio_btn.setText("🔊")
            self.audio_btn.setStyleSheet(
                "QPushButton { background-color: #24243A; color: #818CF8; border: 1px solid #3730A3; "
                "border-radius: 21px; font-size: 20px; width: 42px; height: 42px; }"
                "QPushButton:hover { background-color: #4F46E5; color: white; border-color: #818CF8; }"
            )
        except RuntimeError:
            pass

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            if self.quiz_mode == "flashcard" and not self.card_flipped:
                self.flip_flashcard()
                event.accept()
                return
            else:
                self.play_audio()
                event.accept()
                return

        if self.quiz_mode == "choice" and not self.is_checking:
            key_map = {Qt.Key.Key_1: 0, Qt.Key.Key_2: 1, Qt.Key.Key_3: 2, Qt.Key.Key_4: 3}
            if event.key() in key_map:
                self.check_choice(key_map[event.key()])
                event.accept()
                return

        if self.quiz_mode == "flashcard" and self.card_flipped and not self.is_checking:
            if event.key() == Qt.Key.Key_1:
                self.grade_flashcard("hard")
                event.accept()
                return
            elif event.key() == Qt.Key.Key_2:
                self.grade_flashcard("good")
                event.accept()
                return
            elif event.key() == Qt.Key.Key_3:
                self.grade_flashcard("easy")
                event.accept()
                return

        if self.quiz_mode == "scramble" and not self.is_checking:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.scramble_typed_chars:
                    self.check_answer()
                    event.accept()
                    return
            if event.key() == Qt.Key.Key_Backspace:
                self._scramble_backspace()
                event.accept()
                return
            key_text = event.text().lower()
            if key_text and key_text.isalpha():
                for idx, tile in enumerate(self.scramble_tiles_data):
                    if not tile["used"] and tile["char"].lower() == key_text:
                        self._scramble_click_tile(idx)
                        event.accept()
        if self.quiz_mode == "cloze" and not self.is_checking:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.check_answer()
                event.accept()
                return

        super().keyPressEvent(event)

    def set_custom_words(self, word_ids: list[int] | None):
        self.custom_word_ids = list(word_ids) if word_ids else None
        self.load_batch()

    def reset_to_all(self):
        self.custom_word_ids = None
        self.load_batch()

    def load_latest_added(self):
        goal = db.get_daily_goal()
        rows = db.get_latest_added_words(limit=goal)
        if rows:
            self.set_custom_words([r["id"] for r in rows])

    def load_weak_words(self):
        rows = db.get_weak_words(limit=30)
        if rows:
            self.set_custom_words([r["id"] for r in rows])
            self.mode_label.setText(f"⚠️ Zaif so'zlar: {len(rows)} ta so'z")
        else:
            self.feedback_label.setText("✅ Zaif so'zlar yo'q! Barcha so'zlar yaxshi o'zlashtirilgan.")
            self.feedback_label.setStyleSheet("color: #10B981; font-size: 14px; font-weight: 600;")

    def load_batch(self):
        """Sozlamalarda kiritilgan kunlik maqsad (daily_goal) miqdoridagi so'zlarni yuklaydi."""
        self.is_checking = False
        goal = db.get_daily_goal()

        if self.custom_word_ids:
            self.queue = list(db.get_practice_batch(word_ids=self.custom_word_ids))
            self.mode_label.setText(f"🎯 Maxsus partiya: {len(self.queue)} ta so'z")
            self.all_words_btn.setVisible(True)
            self.filter_latest_btn.setVisible(False)
            self.filter_weak_btn.setVisible(False)
        else:
            self.queue = list(db.get_practice_batch(limit=goal))
            self.mode_label.setText(f"📚 Rejim: Kunlik reja bo'yicha ({len(self.queue)} ta so'z)")
            self.all_words_btn.setVisible(False)
            self.filter_latest_btn.setVisible(True)
            self.filter_weak_btn.setVisible(True)

        self.batch_total = len(self.queue)
        self.session_correct = 0
        self.session_wrong = 0

        self.progress_bar.setMaximum(max(self.batch_total, 1))
        self.progress_bar.setValue(0)

        self.next_word()

    def next_word(self):
        self.is_checking = False
        self.card_flipped = False

        if not self.queue:
            total_words = db.word_count().get("total", 0)
            goal = db.get_daily_goal()
            prog = db.get_today_progress()
            self.progress_bar.setValue(self.batch_total)
            self.badge_remaining.setText("📌 Qoldi: 0")
            self.badge_goal.setText(f"🎯 Kunlik reja: {goal}")
            self.badge_today.setText(f"🔥 Bugun: {prog['practiced']} / {goal}")
            self.badge_correct.setText(f"✅ To'g'ri: {self.session_correct}")
            self.badge_wrong.setText(f"❌ Xato: {self.session_wrong}")

            if self.custom_word_ids:
                self.word_label.setText("🎉 Maxsus partiya yakunlandi!")
                self.feedback_label.setText(
                    f"Natija: {self.session_correct} to'g'ri, {self.session_wrong} xato "
                    f"({len(self.custom_word_ids)} ta yangi so'zdan)"
                )
            elif total_words == 0:
                self.word_label.setText("Lug'at bo'sh")
                self.feedback_label.setText("Hozircha so'zlar yo'q. 'So'z import qilish' bo'limidan so'z qo'shing!")
            else:
                acc = round((self.session_correct / max(self.batch_total, 1)) * 100) if self.batch_total else 0
                self.word_label.setText("🎉 Partiya muvaffaqiyatli yakunlandi!")
                self.feedback_label.setText(
                    f"🎯 Aniqlik: {acc}%  |  ✅ {self.session_correct} to'g'ri  |  ❌ {self.session_wrong} xato"
                )

            self.word_info_badge.setText("")
            self.phonetic_row_widget.setVisible(False)
            self.audio_btn.setVisible(False)
            self.mic_btn.setVisible(False)
            self.answer_input.clear()
            self.answer_input.setEnabled(False)
            self.submit_btn.setVisible(False)
            self.choice_container.setVisible(False)
            self.flashcard_container.setVisible(False)
            self.scramble_container.setVisible(False)
            if hasattr(self, "cloze_container"):
                self.cloze_container.setVisible(False)
            self.example_card.setVisible(False)
            self.restart_btn.setVisible(total_words > 0 or bool(self.custom_word_ids))

            if self.on_finish_refresh:
                self.on_finish_refresh()
            return

        self.current = self.queue.pop(0)
        self.audio_btn.setVisible(True)
        self.mic_btn.setVisible(True)

        remaining = len(self.queue) + 1
        done = self.batch_total - remaining
        self.progress_bar.setValue(done)

        goal = db.get_daily_goal()
        prog = db.get_today_progress()
        self.badge_remaining.setText(f"📌 Qoldi: {remaining}")
        self.badge_goal.setText(f"🎯 Kunlik reja: {goal}")
        self.badge_today.setText(f"🔥 Bugun: {prog['practiced']} / {goal}")
        self.badge_correct.setText(f"✅ To'g'ri: {self.session_correct}")
        self.badge_wrong.setText(f"❌ Xato: {self.session_wrong}")

        self.restart_btn.setVisible(False)
        self.typing_container.setVisible(self.quiz_mode in ("typing", "listening"))
        self.submit_btn.setVisible(self.quiz_mode in ("typing", "listening", "scramble", "cloze"))
        self.choice_container.setVisible(self.quiz_mode == "choice")
        self.flashcard_container.setVisible(self.quiz_mode == "flashcard")
        self.scramble_container.setVisible(self.quiz_mode == "scramble")
        if hasattr(self, "cloze_container"):
            self.cloze_container.setVisible(self.quiz_mode == "cloze")

        self._render_current_mode()

    def _render_current_mode(self):
        if not self.current:
            return
        self.example_card.setVisible(False)
        self.feedback_label.setText("")
        self.is_checking = False

        box = self.current["box_level"] if "box_level" in self.current.keys() and self.current["box_level"] is not None else 0
        st = self.current["status"] if "status" in self.current.keys() and self.current["status"] else "new"
        st_label = {"new": "Yangi so'z", "learning": "O'rganilmoqda", "mastered": "O'zlashtirilgan"}.get(st, st)

        # IPA Fonetika va So'z turkumi ma'lumotlarini yuklash
        eng_word = self.current["english"]
        ph_info = phonetics.get_word_info(eng_word)
        ph_val = self.current["phonetic"] if "phonetic" in self.current.keys() and self.current["phonetic"] else ph_info["phonetic"]
        pos_val = self.current["part_of_speech"] if "part_of_speech" in self.current.keys() and self.current["part_of_speech"] else ph_info["part_of_speech"]
        self.phonetic_label.setText(ph_val)
        self.pos_badge.setText(f"[{pos_val}]")
        self.phonetic_row_widget.setVisible(self.direction == "en_uz" or self.quiz_mode == "flashcard")

        if self.quiz_mode == "listening":
            self.word_label.setText("🎧 Tinglang va yozing")
            self.word_label.setStyleSheet("color: #A5B4FC; font-size: 30px; font-weight: 700;")
            uz = self.current["uzbek"]
            eng_len = len(self.current["english"].strip())
            self.word_info_badge.setText(f"💡 Yordam: \"{uz}\"  •  {eng_len} ta harf  •  Box {box} ({st_label})")
            self.answer_input.setPlaceholderText("Eshitgan inglizcha so'zni yozing...")
            self.answer_input.clear()
            self.answer_input.setEnabled(True)
            self.answer_input.setFocus()
            self.submit_btn.setEnabled(True)
            self.play_audio()

        elif self.quiz_mode == "scramble":
            self.word_label.setText(self.current["uzbek"])
            self.word_label.setStyleSheet("color: white; font-size: 32px; font-weight: 700;")
            eng_len = len([c for c in self.current["english"].strip() if not c.isspace()])
            self.word_info_badge.setText(f"🔤 Harflarni to'g'ri tering ({eng_len} ta harf)  •  Box {box} ({st_label})")
            self._setup_scramble()
            self.submit_btn.setEnabled(True)

        elif self.quiz_mode == "choice":
            shown = self.current["english"] if self.direction == "en_uz" else self.current["uzbek"]
            self.word_label.setText(shown)
            self.word_label.setStyleSheet("color: white; font-size: 36px; font-weight: 700;")
            self.word_info_badge.setText(f"⭐ Leitner Box {box}  •  {st_label}")
            self._setup_choices()

        elif self.quiz_mode == "flashcard":
            shown = self.current["english"] if self.direction == "en_uz" else self.current["uzbek"]
            self.word_label.setText(shown)
            self.word_label.setStyleSheet("color: white; font-size: 36px; font-weight: 700;")
            self.word_info_badge.setText(f"⭐ Leitner Box {box}  •  {st_label}")
            self._setup_flashcard()

        elif self.quiz_mode == "cloze":
            self.word_label.setText("🧩 Gap ichidagi bo'sh joy")
            self.word_label.setStyleSheet("color: #38BDF8; font-size: 30px; font-weight: 700;")
            self.word_info_badge.setText(f"⭐ Leitner Box {box}  •  {st_label}")
            self._setup_cloze()
            self.submit_btn.setEnabled(True)

        else: # typing
            shown = self.current["english"] if self.direction == "en_uz" else self.current["uzbek"]
            self.word_label.setText(shown)
            self.word_label.setStyleSheet("color: white; font-size: 36px; font-weight: 700;")
            self.word_info_badge.setText(f"⭐ Leitner Box {box}  •  {st_label}")
            self.answer_input.setPlaceholderText("Tarjimasini yozing va Enter bosing...")
            self.answer_input.clear()
            self.answer_input.setEnabled(True)
            self.answer_input.setFocus()
            self.submit_btn.setEnabled(True)
            if self.direction == "en_uz" and db.get_setting("tts_autoplay", "true") == "true":
                self.play_audio()

    def _setup_choices(self):
        if not self.current:
            return
        target_lang = "uzbek" if self.direction == "en_uz" else "english"
        correct_answer = self.current[target_lang].split(",")[0].strip()

        distractors = db.get_random_distractors(self.current["id"], target_lang=target_lang, count=3)
        while len(distractors) < 3:
            distractors.append(f"Variant {len(distractors) + 1}")

        options = [correct_answer] + distractors
        random.shuffle(options)
        self.current_options = options

        for i, opt in enumerate(options):
            btn = self.choice_buttons[i]
            btn.setText(f"[{i+1}]  {opt}")
            btn.setStyleSheet(self._choice_btn_style("normal"))
            btn.setEnabled(True)

    def _setup_flashcard(self):
        self.card_flipped = False
        self.flip_btn.setVisible(True)
        self.answer_reveal_box.setVisible(False)

    def flip_flashcard(self):
        if not self.current:
            return
        self.card_flipped = True
        self.flip_btn.setVisible(False)

        trans = self.current["uzbek"] if self.direction == "en_uz" else self.current["english"]
        self.reveal_trans_label.setText(trans)
        box = self.current["box_level"] if "box_level" in self.current.keys() and self.current["box_level"] is not None else 0
        self.reveal_info_label.setText(f"Leitner Darajasi: Box {box} | O'zingizni baholang:")
        self.answer_reveal_box.setVisible(True)
        self._show_example()

        if self.direction == "uz_en":
            self.play_audio()

    def _handle_answer_result(self, is_correct: bool):
        if is_correct:
            self.consecutive_correct += 1
            sound_effects.play_correct()
        else:
            self.consecutive_correct = 0
            sound_effects.play_wrong()

        res = gamification.record_practice_answer(
            is_correct=is_correct,
            mode=self.quiz_mode,
            consecutive_correct=self.consecutive_correct,
        )

        if res.get("unlocked_achievements"):
            new_ach = res["unlocked_achievements"][0]
            self.mode_label.setText(f"🎉 Yangi yutuq: {new_ach['icon']} {new_ach['title']}!")
            self.mode_label.setStyleSheet("color: #FBBF24; font-size: 13px; font-weight: 700;")
        elif is_correct:
            xp_txt = f"+{res['xp_gained']} XP"
            self.mode_label.setText(f"⭐ {xp_txt}  •  Jami: {res['total_xp']} XP")
            self.mode_label.setStyleSheet("color: #A5B4FC; font-size: 12px; font-weight: 600;")

    def grade_flashcard(self, quality: str):
        if not self.current or self.is_checking:
            return
        self.is_checking = True
        logger.info(f"Flashcard baholandi: ID={self.current['id']}, '{self.current['english']}' -> {quality}")
        db.record_flashcard_answer(self.current["id"], quality)
        self._show_example()

        is_correct = quality in ("good", "easy")
        self._handle_answer_result(is_correct)

        if is_correct:
            self.session_correct += 1
            self.feedback_label.setText("✅ O'zlashtirildi!")
            self.feedback_label.setStyleSheet("color: #10B981; font-size: 15px; font-weight: 600;")
        else:
            self.session_wrong += 1
            self.feedback_label.setText("🔄 Qayta takrorlanadi")
            self.feedback_label.setStyleSheet("color: #EF4444; font-size: 15px; font-weight: 600;")

        QTimer.singleShot(900, self.next_word)

    def check_choice(self, chosen_idx: int):
        if not self.current or self.is_checking or chosen_idx >= len(self.current_options):
            return
        self.is_checking = True
        chosen_answer = self.current_options[chosen_idx]

        target_lang = "uzbek" if self.direction == "en_uz" else "english"
        expected = self.current[target_lang]
        expected_options = [e.strip().lower() for e in expected.split(",")]

        is_correct = chosen_answer.strip().lower() in expected_options
        db.record_answer(self.current["id"], is_correct)
        self.phonetic_row_widget.setVisible(True)
        self._show_example()
        self._handle_answer_result(is_correct)

        for i, opt in enumerate(self.current_options):
            btn = self.choice_buttons[i]
            btn.setEnabled(False)
            if opt.strip().lower() in expected_options:
                btn.setStyleSheet(self._choice_btn_style("correct"))
            elif i == chosen_idx and not is_correct:
                btn.setStyleSheet(self._choice_btn_style("wrong"))

        if is_correct:
            self.session_correct += 1
            self.feedback_label.setText("✅ To'g'ri!")
            self.feedback_label.setStyleSheet("color: #10B981; font-size: 15px; font-weight: 600;")
            QTimer.singleShot(1200, self.next_word)
        else:
            self.session_wrong += 1
            self.feedback_label.setText(f"❌ To'g'ri javob: {expected}")
            self.feedback_label.setStyleSheet("color: #EF4444; font-size: 15px; font-weight: 600;")
            QTimer.singleShot(2400, self.next_word)

    def check_answer(self):
        if not self.current or self.is_checking:
            return

        if self.quiz_mode == "scramble":
            user_answer = "".join([x["char"] for x in self.scramble_typed_chars]).strip().lower()
            expected_display = self.current["english"]
            expected_options = [expected_display.strip().replace(" ", "").lower()]
        elif self.quiz_mode == "cloze":
            user_answer = self.cloze_input.text().strip().lower()
            expected_display = self.cloze_data["target_token"] if hasattr(self, "cloze_data") and self.cloze_data else self.current["english"]
            expected_options = self.cloze_data["correct_tokens"] if hasattr(self, "cloze_data") and self.cloze_data else [self.current["english"].lower()]
        elif self.quiz_mode == "listening":
            user_answer = self.answer_input.text().strip().lower()
            expected_display = self.current["english"]
            expected_options = [expected_display.strip().lower()]
        else:
            user_answer = self.answer_input.text().strip().lower()
            expected_display = (
                self.current["uzbek"] if self.direction == "en_uz" else self.current["english"]
            )
            expected_options = [e.strip().lower() for e in expected_display.split(",")]

        if not user_answer:
            return

        self.is_checking = True
        self.answer_input.setEnabled(False)
        if hasattr(self, "cloze_input"):
            self.cloze_input.setEnabled(False)
        if hasattr(self, "cloze_hint_btn"):
            self.cloze_hint_btn.setEnabled(False)
        self.submit_btn.setEnabled(False)

        is_correct = user_answer in expected_options
        db.record_answer(self.current["id"], is_correct)
        self.phonetic_row_widget.setVisible(True)
        if self.quiz_mode != "cloze":
            self._show_example()
        self._handle_answer_result(is_correct)

        if is_correct:
            self.session_correct += 1
            self.feedback_label.setText("✅ To'g'ri!")
            self.feedback_label.setStyleSheet("color: #10B981; font-size: 16px; font-weight: 700;")
            if self.quiz_mode in ("listening", "scramble"):
                self.word_label.setText(f"✅ {self.current['english']}")
            elif self.quiz_mode == "cloze" and hasattr(self, "cloze_data") and self.cloze_data:
                orig = self.cloze_data["original_sentence"]
                tok = self.cloze_data["target_token"]
                highlighted = re.sub(rf"\b{re.escape(tok)}\b", f"<span style='color: #10B981; font-weight: 800; text-decoration: underline;'>{tok}</span>", orig, flags=re.IGNORECASE)
                self.cloze_sentence_display.setText(highlighted)
                self.word_label.setText(f"✅ {self.current['english']}")
                self.play_audio()
            QTimer.singleShot(1400, self.next_word)
        else:
            self.session_wrong += 1
            self.feedback_label.setText(f"❌ To'g'ri javob: {expected_display}")
            self.feedback_label.setStyleSheet("color: #EF4444; font-size: 16px; font-weight: 700;")
            if self.quiz_mode in ("listening", "scramble"):
                self.word_label.setText(f"❌ {self.current['english']}")
                self.play_audio()
            elif self.quiz_mode == "cloze" and hasattr(self, "cloze_data") and self.cloze_data:
                orig = self.cloze_data["original_sentence"]
                tok = self.cloze_data["target_token"]
                highlighted = re.sub(rf"\b{re.escape(tok)}\b", f"<span style='color: #10B981; font-weight: 800; text-decoration: underline;'>{tok}</span>", orig, flags=re.IGNORECASE)
                self.cloze_sentence_display.setText(highlighted)
                self.word_label.setText(f"❌ {self.current['english']}")
                self.play_audio()
            QTimer.singleShot(2600, self.next_word)
