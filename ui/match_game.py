"""
Vocab Master Pro — Word Match (Quizlet uslubidagi so'z juftlash mini-o'yini).
Foydalanuvchi 6 ta inglizcha va ularning 6 ta o'zbekcha tarjimasini
eng qisqa vaqt ichida to'g'ri juftlab chiqishi kerak.
"""
import random
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QLabel, QFrame, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

import database as db
import theme_manager
import sound_effects
import gamification
from logger import get_logger

logger = get_logger("match_game")


class MatchTile(QPushButton):
    """Juftlash o'yini kartochkasi."""
    def __init__(self, item_id: int, text: str, lang: str, parent=None):
        super().__init__(text, parent)
        self.item_id = item_id
        self.text_val = text
        self.lang = lang
        self.is_matched = False
        self.is_selected = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(130, 80)
        self.setSizePolicy(
            QPushButton().sizePolicy().horizontalPolicy().Expanding,
            QPushButton().sizePolicy().verticalPolicy().Expanding
        )
        self.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))

    def set_state(self, state: str, t: theme_manager.Theme = None):
        """Kartochka holati: 'default', 'selected', 'wrong', 'matched'."""
        if t is None:
            t = theme_manager.get_active_theme()

        if state == "matched":
            self.is_matched = True
            self.is_selected = False
            self.setEnabled(False)
            self.setText(f"✓  {self.text_val}")
            self.setStyleSheet(
                "QPushButton {"
                "  background-color: #064E3B; color: #6EE7B7; border: 2px solid #10B981;"
                "  border-radius: 12px; font-size: 13px; font-weight: 700; opacity: 0.75;"
                "}"
            )
        elif state == "selected":
            self.is_selected = True
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {t.primary}; color: #FFFFFF; border: 2px solid {t.primary_light};"
                f"  border-radius: 12px; font-size: 13px; font-weight: 700;"
                f"}}"
            )
        elif state == "wrong":
            self.is_selected = False
            self.setStyleSheet(
                "QPushButton {"
                "  background-color: #7F1D1D; color: #FCA5A5; border: 2px solid #EF4444;"
                "  border-radius: 12px; font-size: 13px; font-weight: 700;"
                "}"
            )
        else:  # default
            self.is_matched = False
            self.is_selected = False
            self.setEnabled(True)
            self.setText(self.text_val)
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {t.bg_card}; color: {t.text_main}; border: 1.5px solid {t.border};"
                f"  border-radius: 12px; font-size: 13px; font-weight: 600; padding: 10px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {t.bg_card_secondary}; border-color: {t.primary}; color: {t.primary_light};"
                f"}}"
            )


class MatchGameWidget(QWidget):
    """Word Match mini-o'yini asosiy vidjeti."""
    finished = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tiles: list[MatchTile] = []
        self.first_selected: MatchTile | None = None
        self.matched_pairs = 0
        self.total_pairs = 6
        self.is_game_active = False

        self.start_timestamp = 0.0
        self.elapsed_seconds = 0.0

        # Vaqtni hisoblash taymeri (har 100ms)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._on_timer_tick)

        self._setup_ui()
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

    def _setup_ui(self):
        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(28, 24, 28, 24)
        self.layout_root.setSpacing(18)

        # 1. Header
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(4)

        self.title_label = QLabel("🎮 So'zlarni Juftlash (Word Match)")
        self.title_label.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        header_vbox.addWidget(self.title_label)

        self.subtitle_label = QLabel("Inglizcha so'zlarni ularning o'zbekcha tarjimalari bilan tezkor juftlang!")
        self.subtitle_label.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        header_vbox.addWidget(self.subtitle_label)
        header_row.addLayout(header_vbox)

        header_row.addStretch()

        self.btn_new_game = QPushButton("🔄 Yangi o'yin")
        self.btn_new_game.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_game.setStyleSheet(
            "QPushButton {"
            "  background-color: #4F46E5; color: white; border: none;"
            "  border-radius: 8px; padding: 8px 18px; font-size: 13px; font-weight: 600;"
            "}"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        self.btn_new_game.clicked.connect(self.start_new_game)
        header_row.addWidget(self.btn_new_game)

        self.layout_root.addLayout(header_row)

        # 2. Statistika paneli (Taymer, Juftliklar, Rekord)
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet("background-color: #1E1E2E; border-radius: 12px; border: 1px solid #2A2A3C;")
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(20, 12, 20, 12)
        stats_layout.setSpacing(24)

        # Taymer
        timer_box = QVBoxLayout()
        timer_box.setSpacing(2)
        timer_lbl = QLabel("⏱️ VAQT:")
        timer_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 600;")
        self.timer_display = QLabel("00:00.0")
        self.timer_display.setStyleSheet("color: #38BDF8; font-size: 22px; font-weight: 700; font-family: monospace;")
        timer_box.addWidget(timer_lbl)
        timer_box.addWidget(self.timer_display)
        stats_layout.addLayout(timer_box)

        # Juftliklar
        pairs_box = QVBoxLayout()
        pairs_box.setSpacing(2)
        pairs_lbl = QLabel("🎯 JUFTLANDI:")
        pairs_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 600;")
        self.pairs_display = QLabel("0 / 6")
        self.pairs_display.setStyleSheet("color: #34D399; font-size: 22px; font-weight: 700;")
        pairs_box.addWidget(pairs_lbl)
        pairs_box.addWidget(self.pairs_display)
        stats_layout.addLayout(pairs_box)

        # Eng yaxshi vaqt
        best_box = QVBoxLayout()
        best_box.setSpacing(2)
        best_lbl = QLabel("🏆 SHAXSIY REKORD:")
        best_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 600;")
        self.best_display = QLabel(self._get_best_time_str())
        self.best_display.setStyleSheet("color: #FBBF24; font-size: 22px; font-weight: 700; font-family: monospace;")
        best_box.addWidget(best_lbl)
        best_box.addWidget(self.best_display)
        stats_layout.addLayout(best_box)

        stats_layout.addStretch()
        self.layout_root.addWidget(self.stats_frame)

        # 3. O'yin maydoni (Grid 4x3)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 8, 0, 8)
        self.grid_layout.setSpacing(14)
        self.layout_root.addWidget(self.grid_container, 1)

    def _get_best_time_str(self) -> str:
        best = db.get_setting("match_best_time", "")
        if best:
            try:
                val = float(best)
                return f"{val:.1f} soniya"
            except ValueError:
                pass
        return "— (rekord yo'q)"

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {t.text_main}; font-size: 22px; font-weight: 700;")
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")
        if hasattr(self, "stats_frame"):
            self.stats_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        for tile in self.tiles:
            if not tile.is_matched and not tile.is_selected:
                tile.set_state("default", t)

    def start_new_game(self):
        """Yangi o'yin partiyasini boshlash."""
        self.timer.stop()
        self.first_selected = None
        self.matched_pairs = 0
        self.elapsed_seconds = 0.0
        self.timer_display.setText("00:00.0")
        self.pairs_display.setText("0 / 6")
        self.best_display.setText(self._get_best_time_str())

        # Eski tugmalarni tozalash
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.tiles = []

        # Bazadan 6 ta so'z olish (avvalo o'rganilayotgan va takrorlash kerak bo'lganlar)
        all_words = db.get_words_with_progress()
        if len(all_words) < 6:
            all_words = db.get_words(limit=50)

        if len(all_words) < 2:
            no_words_lbl = QLabel(
                "Lug'atda so'zlar yetarli emas!\n"
                "O'yin o'ynash uchun kamida 6 ta so'z kiriting yoki 'So'z import qilish' bo'limidan qo'shing."
            )
            no_words_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_words_lbl.setStyleSheet("color: #F87171; font-size: 16px; font-weight: 600; padding: 40px;")
            self.grid_layout.addWidget(no_words_lbl, 0, 0)
            return

        sample_size = min(6, len(all_words))
        self.total_pairs = sample_size
        self.pairs_display.setText(f"0 / {self.total_pairs}")

        selected_words = random.sample(all_words, sample_size)

        cards_data: list[tuple[int, str, str]] = []
        for w in selected_words:
            w_id = w["id"]
            eng = w["english"]
            uz = w["uzbek"].split(",")[0].strip()
            cards_data.append((w_id, eng, "en"))
            cards_data.append((w_id, uz, "uz"))

        random.shuffle(cards_data)

        # 4 ustun x 3 qator (yoki moslashuvchan)
        cols = 4 if len(cards_data) >= 8 else 3
        t = theme_manager.get_active_theme()

        for idx, (item_id, text, lang) in enumerate(cards_data):
            row = idx // cols
            col = idx % cols
            tile = MatchTile(item_id, text, lang, self)
            tile.set_state("default", t)
            tile.clicked.connect(lambda _, t_ref=tile: self._on_tile_clicked(t_ref))
            self.grid_layout.addWidget(tile, row, col)
            self.tiles.append(tile)

        self.start_timestamp = time.time()
        self.is_game_active = True
        self.timer.start()

    def _on_timer_tick(self):
        if not self.is_game_active:
            return
        self.elapsed_seconds = time.time() - self.start_timestamp
        mins = int(self.elapsed_seconds // 60)
        secs = int(self.elapsed_seconds % 60)
        tenths = int((self.elapsed_seconds * 10) % 10)
        self.timer_display.setText(f"{mins:02d}:{secs:02d}.{tenths}")

    def _on_tile_clicked(self, tile: MatchTile):
        if not self.is_game_active or tile.is_matched:
            return

        # 1-kartochkani bosish
        if self.first_selected is None:
            self.first_selected = tile
            tile.set_state("selected")
            return

        # Agar o'sha kartochkaning o'zini qayta bossa, tanlovni bekor qilish
        if self.first_selected == tile:
            self.first_selected.set_state("default")
            self.first_selected = None
            return

        # 2-kartochka bosildi: Juftlikni tekshirish
        first = self.first_selected
        self.first_selected = None

        # To'g'ri juftlik: bir xil ID va turli tillar
        if first.item_id == tile.item_id and first.lang != tile.lang:
            first.set_state("matched")
            tile.set_state("matched")
            sound_effects.play_correct()
            self.matched_pairs += 1
            self.pairs_display.setText(f"{self.matched_pairs} / {self.total_pairs}")

            # Leitner / SM-2 progressiga to'g'ri deb qayd etish
            db.record_answer(first.item_id, correct=True)

            if self.matched_pairs >= self.total_pairs:
                self._handle_victory()
        else:
            # Xato juftlik
            first.set_state("wrong")
            tile.set_state("wrong")
            sound_effects.play_wrong()

            # Kartochkalarni 450ms dan so'ng normal holatga qaytarish
            QTimer.singleShot(450, lambda: self._reset_wrong_tiles(first, tile))

    def _reset_wrong_tiles(self, t1: MatchTile, t2: MatchTile):
        try:
            t = theme_manager.get_active_theme()
            if not t1.is_matched:
                t1.set_state("default", t)
            if not t2.is_matched:
                t2.set_state("default", t)
        except RuntimeError:
            pass

    def _handle_victory(self):
        """Barcha juftliklar topilganda g'alaba va mukofot."""
        self.is_game_active = False
        self.timer.stop()

        final_time = round(self.elapsed_seconds, 1)
        sound_effects.play_milestone()

        # Gamifikatsiya: +30 XP berish
        new_xp, level_up, new_level = gamification.award_xp(30)

        # Rekordni tekshirish
        prev_best = db.get_setting("match_best_time", "")
        is_new_record = False
        if not prev_best or final_time < float(prev_best):
            db.set_setting("match_best_time", str(final_time))
            is_new_record = True
            self.best_display.setText(f"{final_time:.1f} soniya 👑")

        msg = f"🎉 Qoyilmaqom!\n\nBarcha {self.total_pairs} ta juftlikni {final_time} soniyada topdingiz!"
        if is_new_record:
            msg += "\n👑 YANGI SHAXSIY REKORD O'RNATILDI!"
        msg += "\n⭐ Sizga +30 XP mukofot berildi!"

        if level_up:
            msg += f"\n\n🎊 TABRIKLAYMIZ! Yangi darajaga ko'tarildingiz: {new_level}"

        box = QMessageBox(self)
        box.setWindowTitle("G'alaba! — Word Match")
        box.setText(msg)
        box.setIcon(QMessageBox.Icon.Information)
        btn_again = box.addButton("🔄 Yana o'ynash", QMessageBox.ButtonRole.AcceptRole)
        btn_close = box.addButton("Yopish", QMessageBox.ButtonRole.RejectRole)
        box.setStyleSheet(
            "QMessageBox { background-color: #1E1E2E; color: white; }"
            "QLabel { color: white; font-size: 14px; }"
            "QPushButton { background-color: #4F46E5; color: white; border-radius: 6px; padding: 6px 14px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        box.exec()

        if box.clickedButton() == btn_again:
            self.start_new_game()

    def showEvent(self, event):
        super().showEvent(event)
        # Sahifaga o'tilganda agar o'yin hali boshlanmagan bo'lsa, avtomatik boshlash
        if not self.is_game_active and self.matched_pairs == 0:
            self.start_new_game()
