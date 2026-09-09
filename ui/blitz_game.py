"""
Vocab Master Pro — Blitz Marafon (60 soniyalik Ekstremal Test).
Vaqtga qarshi tezkor 4 variantli test, +2s vaqt bonusi va dinamik Combo ko'paytirgichlar.
"""
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QDialog, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

import database as db
import sound_effects
import gamification
import theme_manager
from logger import get_logger

logger = get_logger("blitz_game")


class BlitzSummaryDialog(QDialog):
    """O'yin yakunlanganda chiqadigan natijalar oynasi."""
    def __init__(self, parent, stats: dict, on_retry=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Blitz Marafon Yakunlandi!")
        self.setFixedSize(420, 480)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.stats = stats
        self.on_retry = on_retry
        self._build_ui()

    def _build_ui(self):
        t = theme_manager.get_active_theme()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border: 2px solid {t.primary}; border-radius: 20px; }}"
        )
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(28, 28, 28, 28)
        c_layout.setSpacing(14)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("⚡ MARAFON YAKUNI!")
        title.setStyleSheet(f"color: {t.primary_light}; font-size: 22px; font-weight: 800;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(title)

        if self.stats.get("is_new_best"):
            badge = QLabel("🏆 YANGI SHAXSIY REKORD!")
            badge.setStyleSheet(
                "background-color: #78350F; color: #FDE68A; border: 1px solid #F59E0B; "
                "border-radius: 8px; padding: 6px 14px; font-weight: 800; font-size: 13px;"
            )
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(badge)

        score_lbl = QLabel(f"{self.stats.get('score', 0)}")
        score_lbl.setStyleSheet("color: white; font-size: 54px; font-weight: 900;")
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(score_lbl)

        score_sub = QLabel("Umumiy to'plangan ball")
        score_sub.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
        score_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(score_sub)

        # Tafsilotlar paneli
        info_frame = QFrame()
        info_frame.setStyleSheet(f"background-color: {t.bg_card_secondary}; border-radius: 10px;")
        i_layout = QGridLayout(info_frame)
        i_layout.setContentsMargins(14, 12, 14, 12)

        def add_stat_row(row: int, title: str, val: str, val_color: str = "white"):
            l1 = QLabel(title)
            l1.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
            l2 = QLabel(val)
            l2.setStyleSheet(f"color: {val_color}; font-size: 13px; font-weight: 700;")
            l2.setAlignment(Qt.AlignmentFlag.AlignRight)
            i_layout.addWidget(l1, row, 0)
            i_layout.addWidget(l2, row, 1)

        add_stat_row(0, "To'g'ri javoblar:", f"✅ {self.stats.get('correct', 0)} ta", "#10B981")
        add_stat_row(1, "Xato javoblar:", f"❌ {self.stats.get('wrong', 0)} ta", "#EF4444")
        add_stat_row(2, "Maksimal Combo:", f"🔥 x{self.stats.get('max_combo', 1)}", "#F59E0B")
        add_stat_row(3, "Qo'lga kiritilgan XP:", f"⭐ +{self.stats.get('xp', 0)} XP", "#60A5FA")
        add_stat_row(4, "Eng yuqori rekord:", f"👑 {self.stats.get('best_score', 0)} ball", "#FBBF24")

        c_layout.addWidget(info_frame)
        c_layout.addSpacing(6)

        # Tugmalar
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        btn_retry = QPushButton("🔄 Qayta o'ynash")
        btn_retry.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_retry.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
            f"font-size: 13px; font-weight: 700; padding: 10px 18px; }}"
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        btn_retry.clicked.connect(self._on_retry)
        btn_box.addWidget(btn_retry)

        btn_close = QPushButton("Chiqish")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 8px; font-size: 13px; padding: 10px 18px; }}"
            f"QPushButton:hover {{ background-color: {t.border}; }}"
        )
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)

        c_layout.addLayout(btn_box)
        layout.addWidget(card)

    def _on_retry(self):
        self.accept()
        if self.on_retry:
            self.on_retry()


class BlitzGameWidget(QWidget):
    """Blitz Marafon — 60 soniyalik tezkor imtihon rejimi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words: list[dict] = []
        self.time_left: float = 60.0
        self.score: int = 0
        self.combo: int = 0
        self.max_combo: int = 1
        self.correct_count: int = 0
        self.wrong_count: int = 0
        self.is_running: bool = False
        self.current_question: dict = {}
        self.options: list[str] = []
        self.correct_option: str = ""

        # Taymer
        self.game_timer = QTimer(self)
        self.game_timer.setInterval(100)  # Har 100ms da yangilash
        self.game_timer.timeout.connect(self._on_timer_tick)

        self._build_ui()
        self._setup_shortcuts()
        self.apply_theme(theme_manager.get_active_theme())

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        # 1. Sarlavha va status paneli
        top_row = QHBoxLayout()
        self.title_lbl = QLabel("⚡ Blitz Marafon")
        self.title_lbl.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()

        self.record_lbl = QLabel("👑 Rekord: 0 ball")
        self.record_lbl.setStyleSheet(
            "background-color: #2D2006; color: #FBBF24; border: 1px solid #B45309; "
            "border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 700;"
        )
        top_row.addWidget(self.record_lbl)
        root.addLayout(top_row)

        self.sub_lbl = QLabel(
            "60 soniya ichida imkon qadar ko'proq to'g'ri javob toping! "
            "Har bir to'g'ri javob uchun +2 soniya vaqt va Combo ko'paytirgichlar beriladi."
        )
        self.sub_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        root.addWidget(self.sub_lbl)

        # 2. Hisoblagichlar paneli (Vaqt, Ball, Combo)
        stats_frame = QFrame()
        self.stats_frame = stats_frame
        s_layout = QHBoxLayout(stats_frame)
        s_layout.setContentsMargins(20, 14, 20, 14)
        s_layout.setSpacing(24)

        # Qolgan vaqt
        time_box = QVBoxLayout()
        time_sub = QLabel("⏱️ VAQT:")
        time_sub.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 700;")
        self.time_lbl = QLabel("01:00.0")
        self.time_lbl.setStyleSheet("color: #10B981; font-size: 32px; font-weight: 900; font-family: monospace;")
        time_box.addWidget(time_sub)
        time_box.addWidget(self.time_lbl)
        s_layout.addLayout(time_box)

        s_layout.addStretch()

        # Ball
        score_box = QVBoxLayout()
        score_sub = QLabel("🎯 BALL:")
        score_sub.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 700;")
        self.score_lbl = QLabel("0")
        self.score_lbl.setStyleSheet("color: white; font-size: 32px; font-weight: 900;")
        score_box.addWidget(score_sub)
        score_box.addWidget(self.score_lbl)
        s_layout.addLayout(score_box)

        s_layout.addStretch()

        # Combo
        combo_box = QVBoxLayout()
        combo_sub = QLabel("🔥 COMBO:")
        combo_sub.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 700;")
        self.combo_lbl = QLabel("x1")
        self.combo_lbl.setStyleSheet("color: #F59E0B; font-size: 32px; font-weight: 900;")
        combo_box.addWidget(combo_sub)
        combo_box.addWidget(self.combo_lbl)
        s_layout.addLayout(combo_box)

        root.addWidget(stats_frame)

        # 3. Asosiy Savol Kartasi
        self.question_card = QFrame()
        q_layout = QVBoxLayout(self.question_card)
        q_layout.setContentsMargins(28, 24, 28, 24)
        q_layout.setSpacing(12)
        q_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.word_display = QLabel("START TUGMASINI BOSING")
        self.word_display.setStyleSheet("color: white; font-size: 38px; font-weight: 900;")
        self.word_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q_layout.addWidget(self.word_display)

        ph_row = QHBoxLayout()
        ph_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ipa_display = QLabel("")
        self.ipa_display.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; border-radius: 6px; "
            "padding: 4px 10px; font-size: 14px;"
        )
        ph_row.addWidget(self.ipa_display)

        self.pos_display = QLabel("")
        self.pos_display.setStyleSheet(
            "background-color: #064E3B; color: #6EE7B7; border-radius: 6px; "
            "padding: 4px 10px; font-size: 12px; font-weight: 700;"
        )
        ph_row.addWidget(self.pos_display)
        q_layout.addLayout(ph_row)

        root.addWidget(self.question_card, 1)

        # 4. 4 ta Variant Tugmalari (2x2 Grid)
        self.options_grid = QGridLayout()
        self.options_grid.setSpacing(14)
        self.option_buttons: list[QPushButton] = []

        for i in range(4):
            btn = QPushButton(f"{i+1}. —")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(64)
            btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            btn.clicked.connect(lambda _, idx=i: self._on_option_clicked(idx))
            self.option_buttons.append(btn)
            self.options_grid.addWidget(btn, i // 2, i % 2)

        root.addLayout(self.options_grid)

        # 5. Start / Boshqaruv tugmasi
        self.btn_start = QPushButton("🚀 MARAFONNI BOSHLASH")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setMinimumHeight(48)
        self.btn_start.clicked.connect(self.start_game)
        root.addWidget(self.btn_start)

    def _setup_shortcuts(self):
        """Klaviatura 1, 2, 3, 4 tugmalari orqali chaqqon javob berish."""
        for i in range(4):
            sc = QShortcut(QKeySequence(str(i + 1)), self)
            sc.activated.connect(lambda idx=i: self._on_shortcut_pressed(idx))

    def _on_shortcut_pressed(self, idx: int):
        if self.is_running and 0 <= idx < len(self.option_buttons):
            self._on_option_clicked(idx)

    def load_best_score(self):
        best = db.get_setting("blitz_best_score", "0") or "0"
        self.record_lbl.setText(f"👑 Rekord: {best} ball")

    def start_game(self):
        self.words = [dict(w) for w in db.get_all_words()]
        if len(self.words) < 4:
            self.word_display.setText("Kamida 4 ta so'z kerak!")
            return

        self.time_left = 60.0
        self.score = 0
        self.combo = 0
        self.max_combo = 1
        self.correct_count = 0
        self.wrong_count = 0
        self.is_running = True

        self.btn_start.setEnabled(False)
        self.btn_start.setText("🔥 O'yin davom etmoqda...")
        self.load_best_score()
        self._update_stats_display()

        self._next_question()
        self.game_timer.start()

    def _on_timer_tick(self):
        if not self.is_running:
            return

        self.time_left = max(0.0, self.time_left - 0.1)
        self._update_timer_display()

        # Oxirgi 10 soniyada har soniyada chertish tovushi
        if self.time_left <= 10.0 and int(self.time_left * 10) % 10 == 0:
            sound_effects.play_tick()

        if self.time_left <= 0.0:
            self._finish_game()

    def _update_timer_display(self):
        secs = int(self.time_left)
        msecs = int((self.time_left - secs) * 10)
        m = secs // 60
        s = secs % 60
        self.time_lbl.setText(f"{m:02d}:{s:02d}.{msecs}")

        if self.time_left <= 10.0:
            self.time_lbl.setStyleSheet("color: #EF4444; font-size: 32px; font-weight: 900; font-family: monospace;")
        else:
            self.time_lbl.setStyleSheet("color: #10B981; font-size: 32px; font-weight: 900; font-family: monospace;")

    def _update_stats_display(self):
        self.score_lbl.setText(str(self.score))
        multiplier = 1
        if self.combo >= 10:
            multiplier = 5
        elif self.combo >= 6:
            multiplier = 3
        elif self.combo >= 3:
            multiplier = 2

        self.combo_lbl.setText(f"x{multiplier}")
        if multiplier >= 3:
            self.combo_lbl.setStyleSheet("color: #EC4899; font-size: 32px; font-weight: 900;")
        elif multiplier == 2:
            self.combo_lbl.setStyleSheet("color: #F59E0B; font-size: 32px; font-weight: 900;")
        else:
            self.combo_lbl.setStyleSheet("color: #9CA3AF; font-size: 32px; font-weight: 900;")

    def _next_question(self):
        if not self.is_running or not self.words:
            return

        self.current_question = random.choice(self.words)
        eng = self.current_question.get("english", "")
        self.correct_option = self.current_question.get("uzbek", "")
        pho = self.current_question.get("phonetic", "")
        pos = self.current_question.get("part_of_speech", "") or "word"

        self.word_display.setText(eng)
        self.ipa_display.setText(pho if pho else "/—/")
        self.pos_display.setText(f"[{pos}]")

        # 3 ta tasodifiy noto'g'ri variant tanlash
        distractors = [w.get("uzbek", "") for w in self.words if w.get("uzbek", "") != self.correct_option]
        wrong_samples = random.sample(distractors, min(3, len(distractors)))
        while len(wrong_samples) < 3:
            wrong_samples.append("—")

        self.options = wrong_samples + [self.correct_option]
        random.shuffle(self.options)

        t = theme_manager.get_active_theme()
        for i, btn in enumerate(self.option_buttons):
            text = self.options[i]
            btn.setText(f"{i+1}. {text}")
            btn.setEnabled(True)
            self._set_button_default_style(btn, t)

    def _on_option_clicked(self, idx: int):
        if not self.is_running or idx >= len(self.options):
            return

        chosen = self.options[idx]
        btn = self.option_buttons[idx]

        if chosen == self.correct_option:
            # TO'G'RI JAVOB
            self.correct_count += 1
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)

            # Vaqt bonusi +2 soniya
            self.time_left = min(120.0, self.time_left + 2.0)

            # Multiplier hisoblash
            mult = 1
            if self.combo >= 10:
                mult = 5
            elif self.combo >= 6:
                mult = 3
            elif self.combo >= 3:
                mult = 2

            self.score += 10 * mult
            self._update_stats_display()

            btn.setStyleSheet(
                "background-color: #065F46; color: white; border: 2px solid #10B981; "
                "border-radius: 10px; font-weight: 800; font-size: 13px;"
            )
            if self.combo in (3, 6, 10):
                sound_effects.play_combo(mult)
            else:
                sound_effects.play_correct()

            QTimer.singleShot(180, self._next_question)
        else:
            # XATO JAVOB
            self.wrong_count += 1
            self.combo = 0
            self._update_stats_display()

            btn.setStyleSheet(
                "background-color: #7F1D1D; color: white; border: 2px solid #EF4444; "
                "border-radius: 10px; font-weight: 800; font-size: 13px;"
            )
            # To'g'ri variantni yashil qilib ko'rsatish
            for i, b in enumerate(self.option_buttons):
                if self.options[i] == self.correct_option:
                    b.setStyleSheet(
                        "background-color: #065F46; color: white; border: 2px solid #10B981; "
                        "border-radius: 10px; font-weight: 800; font-size: 13px;"
                    )

            sound_effects.play_wrong()
            QTimer.singleShot(400, self._next_question)

    def _finish_game(self):
        self.is_running = False
        self.game_timer.stop()

        for btn in self.option_buttons:
            btn.setEnabled(False)

        self.btn_start.setEnabled(True)
        self.btn_start.setText("🚀 MARAFONNI QAYTA BOSHLASH")

        # Natijalarni bazaga yozish
        res = db.record_blitz_score(self.score, self.correct_count, self.wrong_count)

        # XP mukofoti
        awarded_xp = max(10, self.score // 5)
        gamification.award_xp(awarded_xp)
        sound_effects.play_victory()

        stats = {
            "score": self.score,
            "correct": self.correct_count,
            "wrong": self.wrong_count,
            "max_combo": self.max_combo,
            "xp": awarded_xp,
            "is_new_best": res.get("is_new_best", False),
            "best_score": res.get("best_score", self.score),
        }

        dlg = BlitzSummaryDialog(self, stats, on_retry=self.start_game)
        dlg.exec()
        self.load_best_score()

    def _set_button_default_style(self, btn: QPushButton, t: theme_manager.Theme):
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1.5px solid {t.border}; "
            f"border-radius: 10px; font-weight: 700; font-size: 13px; text-align: left; padding: 12px 18px; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; border-color: {t.primary}; }}"
        )

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        self.title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 22px; font-weight: 700;")
        self.sub_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")

        self.stats_frame.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border-radius: 14px; border: 1px solid {t.border}; }}"
        )
        self.question_card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border-radius: 16px; border: 2px solid {t.border}; }}"
        )

        for btn in self.option_buttons:
            self._set_button_default_style(btn, t)

        self.btn_start.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 10px; "
            f"font-size: 15px; font-weight: 800; padding: 12px; }}"
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            f"QPushButton:disabled {{ background-color: {t.bg_card_secondary}; color: {t.text_muted}; }}"
        )
        self.load_best_score()
