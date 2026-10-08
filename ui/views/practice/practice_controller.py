from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QStackedWidget, QProgressBar, QMessageBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

from services.practice_session_service import PracticeSessionService
from services import sound_effects
from services import tts_service
import core.gamification as gamification
import core.database as db
from ui.theme_manager import get_theme

# Rejimlar
from ui.views.practice.typing_mode import TypingModeWidget
from ui.views.practice.flashcard_mode import FlashcardModeWidget
from ui.views.practice.choice_mode import ChoiceModeWidget
from ui.views.practice.scramble_mode import ScrambleModeWidget
from ui.views.practice.cloze_mode import ClozeModeWidget
from ui.views.practice.listening_mode import ListeningModeWidget

class PracticeWidget(QWidget):
    def __init__(self, direction="en_uz", on_finish_refresh=None):
        super().__init__()
        self.direction = direction
        self.on_finish_refresh = on_finish_refresh
        
        self.session = PracticeSessionService(direction)
        self.sounds = sound_effects
        self.tts = tts_service
        self._advance_timer = None
        self.is_waiting_for_enter = False
        self._mistake_timestamp = 0.0
        self._forced_mode = None
        
        self.setup_ui()
        self.apply_theme()
        
    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        # Header: Orqaga va Statistika
        header = QHBoxLayout()
        self.back_btn = QPushButton("⬅ Orqaga")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.close_practice)
        
        self.stats_lbl = QLabel("To'g'ri: 0 | Xato: 0")
        self.stats_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        header.addWidget(self.back_btn)
        header.addStretch()
        header.addWidget(self.stats_lbl)
        self.main_layout.addLayout(header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.main_layout.addWidget(self.progress_bar)

        # Mode selector buttons
        self.mode_buttons = {}
        modes_info = [
            ("typing", "✏️ Yozma"),
            ("choice", "🎯 4 ta variant"),
            ("flashcard", "🎴 Flashcard"),
            ("listening", "🎧 Eshitib yozish"),
            ("scramble", "🔤 Harf terish"),
            ("cloze", "🧩 Bo'sh joy"),
        ]
        self.modes_row = QHBoxLayout()
        self.modes_row.setSpacing(8)
        self.modes_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for mode_key, mode_title in modes_info:
            btn = QPushButton(mode_title)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, mk=mode_key: self.switch_mode(mk))
            self.modes_row.addWidget(btn)
            self.mode_buttons[mode_key] = btn
        self.main_layout.addLayout(self.modes_row)

        # Asosiy Word Card
        self.card_frame = QFrame()
        self.card_layout = QVBoxLayout(self.card_frame)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Word text
        self.word_label = QLabel("")
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.card_layout.addWidget(self.word_label)
        
        # Modes container
        self.mode_stack = QStackedWidget()
        
        self.typing_mode = TypingModeWidget(self.direction)
        self.flashcard_mode = FlashcardModeWidget()
        self.choice_mode = ChoiceModeWidget()
        self.listening_mode = ListeningModeWidget(self.direction)
        self.scramble_mode = ScrambleModeWidget()
        self.cloze_mode = ClozeModeWidget()
        
        self.mode_stack.addWidget(self.typing_mode)
        self.mode_stack.addWidget(self.flashcard_mode)
        self.mode_stack.addWidget(self.choice_mode)
        self.mode_stack.addWidget(self.listening_mode)
        self.mode_stack.addWidget(self.scramble_mode)
        self.mode_stack.addWidget(self.cloze_mode)
        
        self.modes = {
            "typing": self.typing_mode,
            "flashcard": self.flashcard_mode,
            "choice": self.choice_mode,
            "listening": self.listening_mode,
            "scramble": self.scramble_mode,
            "cloze": self.cloze_mode
        }
        
        self.typing_mode.answer_submitted.connect(lambda c: self.on_answer_submitted(c, "typing"))
        self.flashcard_mode.flashcard_rated.connect(self.on_flashcard_rated)
        self.choice_mode.answer_submitted.connect(lambda c: self.on_answer_submitted(c, "choice"))
        self.listening_mode.answer_submitted.connect(lambda c: self.on_answer_submitted(c, "listening"))
        self.scramble_mode.answer_submitted.connect(lambda c: self.on_answer_submitted(c, "scramble"))
        self.cloze_mode.answer_submitted.connect(lambda c: self.on_answer_submitted(c, "cloze"))
        
        self.card_layout.addWidget(self.mode_stack)
        
        self.main_layout.addWidget(self.card_frame)
        
        # Submit Button
        self.submit_btn = QPushButton("Tekshirish ↵")
        self.submit_btn.setFixedHeight(50)
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.clicked.connect(self.on_submit_clicked)
        self.main_layout.addWidget(self.submit_btn)
        
        self.main_layout.addStretch()

    @property
    def custom_word_ids(self):
        return self.session.custom_word_ids
        
    @custom_word_ids.setter
    def custom_word_ids(self, value):
        self.session.custom_word_ids = value

    @property
    def quiz_mode(self):
        current_widget = self.mode_stack.currentWidget()
        for k, v in self.modes.items():
            if v == current_widget:
                return k
        return "typing"

    @quiz_mode.setter
    def quiz_mode(self, value):
        self.switch_mode(value)
        
    def set_quiz_mode(self, mode_name: str):
        self.quiz_mode = mode_name
        
    def _update_mode_buttons(self):
        curr = self._forced_mode or "typing"
        theme_id = db.get_setting("theme", "midnight")
        t = get_theme(theme_id)
        for k, btn in getattr(self, "mode_buttons", {}).items():
            if k == curr:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
                    f"border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 700; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_muted}; border: 1px solid {t.border}; "
                    f"border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 500; }} "
                    f"QPushButton:hover {{ background-color: {t.primary_light}; color: white; }}"
                )

    def switch_mode(self, mode_name: str):
        if mode_name in self.modes:
            self._forced_mode = mode_name
            self.mode_stack.setCurrentWidget(self.modes[mode_name])
            self._update_mode_buttons()
            if self.session.current:
                if mode_name == "listening":
                    self.word_label.setText("🎧 Tinglang va yozing")
                else:
                    source_text = self.session.current["english"] if self.direction == "en_uz" else self.session.current["uzbek"]
                    self.word_label.setText(source_text)
                self.modes[mode_name].set_word(self.session.current, direction=self.direction)
                focus = self.modes[mode_name].get_focus_widget()
                if focus: focus.setFocus()
        
    def set_custom_words(self, word_ids: list[int]):
        self.custom_word_ids = word_ids
        self.load_batch(word_ids)

    def load_batch(self, word_ids=None):
        self.start_practice(mode="batch", custom_word_ids=word_ids)
        
    def resume_session(self):
        if not self.session.current:
            self.load_batch()
        else:
            self.show_next_word()

    def start_practice(self, mode="batch", custom_word_ids=None):
        if mode == "recent":
            self.session.load_latest_added()
        elif mode == "weak":
            self.session.load_weak_words()
        else:
            self.session.load_batch(custom_word_ids)
            
        if self.session.batch_total == 0:
            QMessageBox.information(self, "Ma'lumot", "Mashq qilish uchun so'zlar topilmadi!")
            return
            
        self.progress_bar.setMaximum(self.session.batch_total)
        self.show_next_word()

    def show_next_word(self):
        if not self.session.current:
            self.finish_practice()
            return
            
        self.is_waiting_for_enter = False
        self.submit_btn.setText("Tekshirish ↵")
        self.submit_btn.setStyleSheet("")
        
        c = self.session.current
        quiz_mode = self._forced_mode or "typing" 
        
        source_text = c["english"] if self.direction == "en_uz" else c["uzbek"]
        if quiz_mode == "listening":
            self.word_label.setText("🎧 Tinglang va yozing")
        else:
            self.word_label.setText(source_text)
        
        self._update_mode_buttons()

        if quiz_mode in self.modes:
            self.mode_stack.setCurrentWidget(self.modes[quiz_mode])
            self.modes[quiz_mode].set_word(c, direction=self.direction)
            focus = self.modes[quiz_mode].get_focus_widget()
            if focus: focus.setFocus()
        
        self.update_stats()
        
        # TTS autoplay
        if quiz_mode != "listening" and self.direction == "en_uz" and db.get_setting("tts_autoplay", "true") == "true":
            self.tts.speak(c["english"])

    def on_submit_clicked(self):
        import time
        if self.is_waiting_for_enter:
            if time.time() - self._mistake_timestamp < 0.3:
                return  # Debounce
            self.session.pop_next_word()
            self.show_next_word()
        else:
            current_mode = self.mode_stack.currentWidget()
            current_mode.check_answer()

    def on_answer_submitted(self, is_correct, mode_name):
        import time
        self.sounds.play_correct() if is_correct else self.sounds.play_wrong()
        self.session.record_answer(is_correct, mode_name)
        
        self.is_waiting_for_enter = True
        self._mistake_timestamp = time.time()
        self.submit_btn.setText("Davom etish ↵")
        
        if is_correct:
            self.submit_btn.setStyleSheet("background-color: #10B981; color: white;")
            if self._advance_timer:
                self._advance_timer.stop()
            self._advance_timer = QTimer(self)
            self._advance_timer.setSingleShot(True)
            self._advance_timer.timeout.connect(self.auto_advance)
            self._advance_timer.start(800)
        else:
            self.submit_btn.setStyleSheet("background-color: #EF4444; color: white;")
            
        if mode_name == "listening" and self.session.current:
            eng = self.session.current.get("english", "")
            self.word_label.setText(f"✅ {eng}" if is_correct else f"❌ {eng}")
            if not is_correct:
                self.tts.speak(eng)

        self.update_stats()

    def on_flashcard_rated(self, quality):
        self.sounds.play_correct() if quality in ["easy", "good"] else self.sounds.play_wrong()
        self.session.record_flashcard_answer(quality)
        self.session.pop_next_word()
        self.show_next_word()

    def auto_advance(self):
        if self.is_waiting_for_enter:
            self.session.pop_next_word()
            self.show_next_word()

    def update_stats(self):
        self.stats_lbl.setText(f"To'g'ri: {self.session.session_correct} | Xato: {self.session.session_wrong}")
        completed = self.session.batch_total - len(self.session.queue) - 1
        self.progress_bar.setValue(completed if completed >= 0 else 0)

    def finish_practice(self):
        if self.session.session_mistake_word_ids:
            retry = QMessageBox.question(self, "Mashq tugadi", "Xato qilingan so'zlarni qayta mashq qilasizmi?")
            if retry == QMessageBox.StandardButton.Yes:
                self.session.load_mistakes()
                self.show_next_word()
                return
                
        if self.on_finish_refresh:
            self.on_finish_refresh()
        self.close_practice()

    def close_practice(self):
        # Qayta ko'rinishga (Dashboard) o'tkazish logikasi (main_window orqali qilinadi)
        pass

    def apply_theme(self, t=None):
        if t is None:
            theme_id = db.get_setting("theme", "midnight")
            t = get_theme(theme_id)
        self.setStyleSheet(f"background-color: {t.bg_app}; color: {t.text_main};")
        self.card_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 15px; border: 1px solid {t.border};")
        self.submit_btn.setStyleSheet(f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; font-weight: bold; font-size: 16px; }}")
        
        self.typing_mode.apply_theme(t)
        self.flashcard_mode.apply_theme(t)
        self.choice_mode.apply_theme(t)
        self.listening_mode.apply_theme(t)
        self.scramble_mode.apply_theme(t)
        self.cloze_mode.apply_theme(t)
        self._update_mode_buttons()
