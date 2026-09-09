"""
Vocab Master Pro — Word Fall (Tezkor So'z Yomg'iri Arkada O'yini).
Ekranning yuqorisidan tushayotgan so'zlarni vaqtida yozib yo'q qilish.
Gamifikatsiya qat'iy qoidasi: 0 ball bilan chiqilganda XP berilmaydi!
"""
import random
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush, QPen, QLinearGradient

import database as db
import gamification
import sound_effects
import theme_manager
from logger import get_logger

logger = get_logger("word_fall_game")


class FallingWord:
    """Tushayotgan so'z ob'ekti."""
    def __init__(self, word_data: dict, x: float, speed: float):
        wd = dict(word_data) if not isinstance(word_data, dict) else word_data
        self.word_data = wd
        self.english = wd.get("english", "").strip()
        self.uzbek = wd.get("uzbek", "").strip()
        self.clean_uzbek_options = [u.strip().lower() for u in self.uzbek.split(",")]
        self.x = x
        self.y = 10.0
        self.speed = speed
        self.width = max(110.0, len(self.english) * 11.0 + 24.0)
        self.height = 36.0
        self.is_destroyed = False
        self.opacity = 1.0


class WordFallCanvas(QWidget):
    """So'zlar tushadigan dinamik o'yin maydoni."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(380)
        self.words: list[FallingWord] = []

    def set_words(self, words: list[FallingWord]):
        self.words = words
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        t = theme_manager.get_active_theme()

        # Orqa fon gradienti
        w = self.width()
        h = self.height()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(t.bg_card))
        grad.setColorAt(1.0, QColor(t.bg_app))
        painter.fillRect(0, 0, w, h, grad)

        # Xavfli zona chizig'i (pastki qism)
        danger_y = h - 45
        pen_danger = QPen(QColor(239, 68, 68, 120), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen_danger)
        painter.drawLine(10, int(danger_y), w - 10, int(danger_y))

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(239, 68, 68, 180))
        painter.drawText(w - 110, int(danger_y - 6), "XAVFLI CHIZIQ")

        # So'z kartalarini chizish
        font_word = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_word)

        for fw in self.words:
            if fw.is_destroyed:
                continue

            rect = QRectF(fw.x, fw.y, fw.width, fw.height)

            # Yaqinlashganda qizilroq tus olish
            progress = fw.y / max(1.0, danger_y)
            if progress > 0.75:
                bg_col = QColor(185, 28, 28, int(220 * fw.opacity))
                border_col = QColor(248, 113, 113)
            else:
                bg_col = QColor(30, 27, 75, int(220 * fw.opacity))
                border_col = QColor(129, 140, 248)

            painter.setBrush(QBrush(bg_col))
            painter.setPen(QPen(border_col, 1.5))
            painter.drawRoundedRect(rect, 8.0, 8.0)

            # Matn
            painter.setPen(QColor(255, 255, 255, int(255 * fw.opacity)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, fw.english)


class WordFallGameWidget(QWidget):
    """Word Fall — Arkada so'z yomg'iri o'yini sahifasi."""
    game_finished = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.words_pool: list[dict] = []
        self.falling_words: list[FallingWord] = []
        self.score = 0
        self.lives = 3
        self.combo = 0
        self.max_combo = 0
        self.words_cleared = 0
        self.is_playing = False
        self.base_speed = 1.1

        # O'yin taymeri (30 fps)
        self.game_timer = QTimer(self)
        self.game_timer.setInterval(33)
        self.game_timer.timeout.connect(self._game_loop)

        # Yangi so'z tushish taymeri
        self.spawn_timer = QTimer(self)
        self.spawn_timer.setInterval(2400)
        self.spawn_timer.timeout.connect(self._spawn_word)

        self._build_ui()

    def _build_ui(self):
        t = theme_manager.get_active_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)

        # 1. Boshqaruv va holat qatori
        top_bar = QHBoxLayout()

        self.title_lbl = QLabel("🌧️ Word Fall — So'z Yomg'iri")
        self.title_lbl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.text_main};")
        top_bar.addWidget(self.title_lbl)
        top_bar.addStretch()

        self.lbl_lives = QLabel("❤️❤️❤️")
        self.lbl_lives.setStyleSheet("font-size: 18px;")
        top_bar.addWidget(self.lbl_lives)

        self.lbl_combo = QLabel("⚡ Combo: 0x")
        self.lbl_combo.setStyleSheet(
            "background-color: #312E81; color: #C7D2FE; font-size: 13px; font-weight: 700; "
            "border-radius: 8px; padding: 6px 14px;"
        )
        top_bar.addWidget(self.lbl_combo)

        self.lbl_score = QLabel("🏆 Ball: 0")
        self.lbl_score.setStyleSheet(
            f"background-color: #064E3B; color: #6EE7B7; font-size: 13px; font-weight: 700; "
            f"border-radius: 8px; padding: 6px 14px;"
        )
        top_bar.addWidget(self.lbl_score)

        root.addLayout(top_bar)

        desc = QLabel("Tepadan tushayotgan inglizcha so'zning o'zbekcha ma'nosini pastdagi qatorda yozing va Enter bosing.")
        desc.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")
        root.addWidget(desc)

        # 2. O'yin maydoni (Canvas)
        self.canvas = WordFallCanvas(self)
        root.addWidget(self.canvas, 1)

        # 3. Kiritish va Boshqaruv paneli
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.answer_input = QLineEdit()
        self.answer_input.setPlaceholderText("Tarjimasini yozing va Enter bosing...")
        self.answer_input.setEnabled(False)
        self.answer_input.setStyleSheet(
            f"QLineEdit {{ background-color: {t.bg_card}; color: {t.text_main}; border: 2px solid {t.border}; "
            f"border-radius: 10px; padding: 12px 16px; font-size: 15px; font-weight: 600; }} "
            f"QLineEdit:focus {{ border-color: {t.primary}; }}"
        )
        self.answer_input.returnPressed.connect(self._check_typed_answer)
        bottom_bar.addWidget(self.answer_input, 1)

        self.btn_start = QPushButton("▶️ O'yinni Boshlash")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 10px; "
            f"font-size: 14px; font-weight: 700; padding: 12px 24px; }} "
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        self.btn_start.clicked.connect(self.start_game)
        bottom_bar.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹️ Yakunlash")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: #EF4444; border: 1px solid #7F1D1D; "
            f"border-radius: 10px; font-size: 13px; font-weight: 600; padding: 12px 20px; }} "
            f"QPushButton:hover:enabled {{ background-color: #7F1D1D; color: white; }}"
        )
        self.btn_stop.clicked.connect(self.end_game)
        bottom_bar.addWidget(self.btn_stop)

        root.addLayout(bottom_bar)

    def start_game(self):
        """O'yinni yangidan boshlash."""
        words = db.get_all_words()
        if len(words) < 5:
            QMessageBox.warning(self, "So'zlar kam", "Word Fall o'ynash uchun bazada kamida 5 ta so'z bo'lishi kerak!")
            return

        self.words_pool = words
        random.shuffle(self.words_pool)
        self.falling_words = []
        self.score = 0
        self.lives = 3
        self.combo = 0
        self.max_combo = 0
        self.words_cleared = 0
        self.base_speed = 1.1
        self.is_playing = True

        self._update_hud()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.answer_input.setEnabled(True)
        self.answer_input.clear()
        self.answer_input.setFocus()

        self.canvas.set_words(self.falling_words)
        self.game_timer.start()
        self.spawn_timer.start()
        self._spawn_word()

    def _spawn_word(self):
        if not self.is_playing or not self.words_pool:
            return

        candidate = random.choice(self.words_pool)
        # Ekran kengligi bo'ylab tasodifiy X pozitsiya
        canvas_w = max(300, self.canvas.width() - 140)
        x_pos = random.uniform(20, canvas_w)
        speed = self.base_speed + random.uniform(0.1, 0.4)

        fw = FallingWord(candidate, x_pos, speed)
        self.falling_words.append(fw)

    def _game_loop(self):
        if not self.is_playing:
            return

        danger_y = self.canvas.height() - 45
        remaining_words = []

        for fw in self.falling_words:
            fw.y += fw.speed

            # So'z xavfli chiziqdan o'tib ketsa
            if fw.y >= danger_y:
                self.lives -= 1
                self.combo = 0
                sound_effects.play_wrong()
                self._update_hud()
                if self.lives <= 0:
                    self._on_game_over()
                    return
            else:
                remaining_words.append(fw)

        self.falling_words = remaining_words
        self.canvas.set_words(self.falling_words)

        # Har 5 ta tozalangan so'zda tezlikni biroz oshirish
        self.base_speed = 1.1 + (self.words_cleared // 5) * 0.15

    def _check_typed_answer(self):
        typed = self.answer_input.text().strip().lower()
        if not typed or not self.is_playing:
            return

        matched_fw = None
        # Eng pastdagi to'g'ri kelgan so'zni topish
        candidates = []
        for fw in self.falling_words:
            if not fw.is_destroyed:
                for opt in fw.clean_uzbek_options:
                    if typed == opt or (len(typed) >= 3 and typed in opt):
                        candidates.append(fw)
                        break

        if candidates:
            # Eng pastdagisi (y qiymati eng kattasi)
            candidates.sort(key=lambda w: w.y, reverse=True)
            matched_fw = candidates[0]

        if matched_fw:
            self.falling_words.remove(matched_fw)
            self.words_cleared += 1
            self.combo += 1
            if self.combo > self.max_combo:
                self.max_combo = self.combo

            bonus = self.combo * 5
            self.score += 10 + bonus
            sound_effects.play_correct()
            self._update_hud()
            self.answer_input.clear()
        else:
            sound_effects.play_wrong()
            self.combo = 0
            self._update_hud()

    def _update_hud(self):
        hearts = "❤️" * max(0, self.lives) + "🖤" * max(0, 3 - self.lives)
        self.lbl_lives.setText(hearts)
        self.lbl_combo.setText(f"⚡ Combo: {self.combo}x")
        self.lbl_score.setText(f"🏆 Ball: {self.score}")

    def _on_game_over(self):
        self.is_playing = False
        self.game_timer.stop()
        self.spawn_timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.answer_input.setEnabled(False)

        # GAMIFIKATSIYA QAT'IY QOIDASI: 0 ball bilan XP berilmaydi!
        if self.score > 0:
            earned_xp = max(1, self.score // 10)
            res = gamification.award_xp(earned_xp)
            sound_effects.play_victory()
            msg = (
                f"🌧️ <b>O'yin yakunlandi!</b><br><br>"
                f"🏆 To'plangan ball: <b>{self.score}</b><br>"
                f"✅ Yo'q qilingan so'zlar: <b>{self.words_cleared} ta</b><br>"
                f"⚡ Maksimal combo: <b>{self.max_combo}x</b><br>"
                f"⭐ Berilgan mukofot: <b>+{earned_xp} XP</b> (Jami: {res['total_xp']} XP)"
            )
        else:
            # 0 ball = 0 XP, ovozsiz
            msg = (
                f"🌧️ <b>O'yin yakunlandi!</b><br><br>"
                f"Ball: <b>0</b><br>"
                f"Siz hech qanday so'zni yo'q qila olmadingiz.<br>"
                f"<i>Qat'iy qoida: 0 ball bilan XP berilmaydi.</i>"
            )

        QMessageBox.information(self, "O'yin Yakuni", msg)
        self.canvas.set_words([])
        self.game_finished.emit(self.score)

    def end_game(self):
        """Foydalanuvchi o'yinni o'zi to'xtatganda."""
        if not self.is_playing:
            return
        self._on_game_over()
