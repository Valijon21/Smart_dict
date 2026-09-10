"""
Vocab Master Pro — Word Match (Quizlet uslubidagi so'z juftlash mini-o'yini).
Foydalanuvchi inglizcha so'zlarni ularning o'zbekcha tarjimalari bilan
eng qisqa vaqt ichida to'g'ri juftlab chiqishi kerak.
Sanoq tanlash (4, 6, 8, 10 ta juftlik), "Boshlash" tugmasi, xato so'zlarni qayta berish
va o'yinni istalgan payt yakunlash imkoniyati bilan.
Gamifikatsiya qat'iy qoidasi: 0 juftlik bilan chiqilganda XP berilmaydi!
"""
import random
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QLabel, QFrame, QDialog, QApplication, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

import database as db
import theme_manager
import sound_effects
import gamification
from logger import get_logger
from ui.components.game_source_selector import GameSourceSelector
from services import game_word_provider as gwp

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
        self.setMinimumSize(140, 80)
        self.setSizePolicy(
            QPushButton().sizePolicy().horizontalPolicy().Expanding,
            QPushButton().sizePolicy().verticalPolicy().Expanding
        )
        self.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))

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
                "  border-radius: 12px; font-size: 14px; font-weight: 700;"
                "}"
            )
        elif state == "selected":
            self.is_selected = True
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {t.primary}; color: #FFFFFF; border: 2px solid {t.primary_light};"
                f"  border-radius: 12px; font-size: 14px; font-weight: 700;"
                f"}}"
            )
        elif state == "wrong":
            self.is_selected = False
            self.setStyleSheet(
                "QPushButton {"
                "  background-color: #7F1D1D; color: #FCA5A5; border: 2px solid #EF4444;"
                "  border-radius: 12px; font-size: 14px; font-weight: 700;"
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
                f"  border-radius: 12px; font-size: 14px; font-weight: 600; padding: 12px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {t.bg_card_secondary}; border-color: {t.primary}; color: {t.primary_light};"
                f"}}"
            )


class VictoryDialog(QDialog):
    """G'alaba qozonilganda yoki o'yin yakunlanganda ko'rsatiladigan zamonaviy modal oyna."""
    def __init__(self, parent, final_time: float, is_new_record: bool, xp_gained: int, total_xp: int, level_up: bool, new_level: str, custom_title: str = "Qoyilmaqom G'alaba!"):
        super().__init__(parent)
        self.setWindowTitle("Natija — Word Match")
        self.setFixedWidth(460)
        self.setModal(True)
        self.setObjectName("matchVictoryDialog")
        t = theme_manager.get_active_theme()

        self.setStyleSheet(
            f"#matchVictoryDialog {{ background-color: {t.bg_card}; border: 2px solid {t.primary}; border-radius: 20px; }}"
            f"#matchVictoryDialog QLabel {{ border: none; background: transparent; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        # 1. Katta nishoncha
        icon = "🏆" if xp_gained > 0 else "⏹️"
        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 50px;")
        layout.addWidget(icon_lbl)

        # 2. Sarlavha
        title = QLabel(custom_title)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {t.text_main}; font-size: 22px; font-weight: 800;")
        layout.addWidget(title)

        # 3. Natija vaqti
        time_lbl = QLabel(f"⏱️ Sarflangan vaqt: <b>{final_time:.1f} soniya</b>")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_lbl.setStyleSheet("color: #38BDF8; font-size: 16px; font-weight: 600;")
        layout.addWidget(time_lbl)

        # 4. Rekord
        if is_new_record and xp_gained > 0:
            rec_badge = QLabel("👑 YANGI SHAXSIY REKORD O'RNATILDI!")
            rec_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rec_badge.setStyleSheet(
                "background-color: #3D2908; color: #FBBF24; border: 1.5px solid #F59E0B; "
                "border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 800;"
            )
            layout.addWidget(rec_badge)

        # 5. XP mukofoti
        if xp_gained > 0:
            xp_badge = QLabel(f"⭐ +{xp_gained} XP berildi! (Jami: {total_xp} XP)")
            xp_badge.setStyleSheet("color: #A5B4FC; font-size: 14px; font-weight: 700;")
        else:
            xp_badge = QLabel("ℹ️ Hech qanday juftlik topilmadi (0 XP)")
            xp_badge.setStyleSheet("color: #9CA3AF; font-size: 14px; font-weight: 600;")
        xp_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(xp_badge)

        # 6. Yangi daraja
        if level_up and xp_gained > 0:
            lvl_lbl = QLabel(f"🎊 TABRIKLAYMIZ! Yangi daraja: {new_level}")
            lvl_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lvl_lbl.setStyleSheet("color: #34D399; font-size: 14px; font-weight: 700;")
            layout.addWidget(lvl_lbl)

        layout.addSpacing(6)

        # 7. Tugmalar
        btn_box = QHBoxLayout()
        btn_box.setSpacing(14)

        self.btn_again = QPushButton("🔄 Yana o'ynash (Enter)")
        self.btn_again.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_again.setDefault(True)
        self.btn_again.setMinimumHeight(44)
        self.btn_again.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
            f"border-radius: 8px; padding: 10px 22px; font-size: 14px; font-weight: 700; }} "
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        self.btn_again.clicked.connect(self.accept)
        btn_box.addWidget(self.btn_again)

        self.btn_close = QPushButton("Yopish")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setMinimumHeight(44)
        self.btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 10px 22px; font-size: 14px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: {t.bg_app}; color: white; }}"
        )
        self.btn_close.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_close)

        layout.addLayout(btn_box)


class MatchGameWidget(QWidget):
    """Word Match mini-o'yini asosiy vidjeti."""
    finished = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tiles: list[MatchTile] = []
        self.first_selected: MatchTile | None = None
        self.matched_pairs = 0
        self.target_pair_count = 6
        self.total_pairs = 6
        self.is_game_active = False

        # So'z takrorlanishini nazorat qilish
        self.used_word_ids: set[int] = set()
        self.failed_word_ids: set[int] = set()

        self.start_timestamp = 0.0
        self.elapsed_seconds = 0.0

        # Vaqtni hisoblash taymeri (har 100ms)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._on_timer_tick)

        self._setup_ui()
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        self.prepare_board()

    def _setup_ui(self):
        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(28, 24, 28, 24)
        self.layout_root.setSpacing(16)

        # 1. Header
        header_row = QHBoxLayout()
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(4)

        self.title_label = QLabel("🎮 So'zlarni Juftlash (Word Match)")
        self.title_label.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        header_vbox.addWidget(self.title_label)

        self.subtitle_label = QLabel("So'zlar sonini tanlang va 'Boshlash' tugmasini bosing yoki istalgan kartochkani tanlang.")
        self.subtitle_label.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        header_vbox.addWidget(self.subtitle_label)
        header_row.addLayout(header_vbox)

        header_row.addStretch()

        # Juftliklar sonini tanlash
        pair_ctrl_layout = QHBoxLayout()
        pair_ctrl_layout.setSpacing(8)
        self.lbl_pair_count = QLabel("🎯 Juftliklar:")
        self.lbl_pair_count.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: 600;")
        pair_ctrl_layout.addWidget(self.lbl_pair_count)

        self.combo_pair_count = QComboBox()
        self.combo_pair_count.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_pair_count.addItem("4 ta juftlik (8 kartochka — Tezkor)", 4)
        self.combo_pair_count.addItem("6 ta juftlik (12 kartochka — Standart)", 6)
        self.combo_pair_count.addItem("8 ta juftlik (16 kartochka — O'rta)", 8)
        self.combo_pair_count.addItem("10 ta juftlik (20 kartochka — Qiyin)", 10)
        self.combo_pair_count.setCurrentIndex(1)  # 6 juftlik standart
        self.combo_pair_count.currentIndexChanged.connect(self._on_pair_count_changed)
        pair_ctrl_layout.addWidget(self.combo_pair_count)

        header_row.addLayout(pair_ctrl_layout)

        # Boshlash / Qayta boshlash tugmasi
        self.btn_start_game = QPushButton("▶️ O'yinni Boshlash")
        self.btn_start_game.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_game.setMinimumHeight(40)
        self.btn_start_game.clicked.connect(self.start_game)
        header_row.addWidget(self.btn_start_game)

        # O'yinni yakunlash tugmasi
        self.btn_finish_game = QPushButton("🏁 Yakunlash")
        self.btn_finish_game.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finish_game.setMinimumHeight(40)
        self.btn_finish_game.setEnabled(False)
        self.btn_finish_game.clicked.connect(self._finish_game_manually)
        header_row.addWidget(self.btn_finish_game)

        self.layout_root.addLayout(header_row)

        # To'plam tanlash paneli (Mavzular, To'plamlar, CEFR, Shaxsiy)
        self.source_selector = GameSourceSelector("match", self)
        self.source_selector.source_changed.connect(self._on_source_changed)
        self.layout_root.addWidget(self.source_selector)

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

        # 3. G'alaba banneri
        self.victory_banner = QFrame()
        self.victory_banner.setStyleSheet(
            "QFrame { background-color: #064E3B; border: 1.5px solid #10B981; border-radius: 12px; }"
        )
        vb_layout = QHBoxLayout(self.victory_banner)
        vb_layout.setContentsMargins(18, 10, 18, 10)
        vb_layout.setSpacing(14)

        self.victory_banner_lbl = QLabel("🎉 Barcha juftliklar muvaffaqiyatli topildi!")
        self.victory_banner_lbl.setStyleSheet("color: #A7F3D0; font-size: 14px; font-weight: 700;")
        vb_layout.addWidget(self.victory_banner_lbl, 1)

        self.btn_banner_again = QPushButton("🔄 Yangi o'yinni boshlash")
        self.btn_banner_again.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_banner_again.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; border: none; "
            "border-radius: 8px; padding: 7px 18px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background-color: #059669; }"
        )
        self.btn_banner_again.clicked.connect(lambda: self.start_game(recreate_cards=True))
        vb_layout.addWidget(self.btn_banner_again)

        self.victory_banner.setVisible(False)
        self.layout_root.addWidget(self.victory_banner)

        # 4. O'yin maydoni
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 4, 0, 4)
        self.grid_layout.setSpacing(14)
        self.layout_root.addWidget(self.grid_container, 1)

    def _get_best_time_str(self) -> str:
        best = db.get_setting("match_best_time", "")
        if best:
            try:
                val = float(best)
                if val > 0:
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
        if hasattr(self, "lbl_pair_count"):
            self.lbl_pair_count.setStyleSheet(f"color: {t.text_muted}; font-size: 12px; font-weight: 600;")

        if hasattr(self, "combo_pair_count"):
            self.combo_pair_count.setStyleSheet(
                f"QComboBox {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1.5px solid {t.border}; "
                f"border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 600; min-width: 170px; }} "
                f"QComboBox::drop-down {{ border: none; }} "
                f"QComboBox QAbstractItemView {{ background-color: {t.bg_card}; color: {t.text_main}; selection-background-color: {t.primary}; }}"
            )

        if hasattr(self, "btn_start_game"):
            self.btn_start_game.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
                f"border-radius: 8px; padding: 8px 20px; font-size: 13px; font-weight: 700; }} "
                f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            )
        if hasattr(self, "btn_finish_game"):
            self.btn_finish_game.setStyleSheet(
                f"QPushButton {{ background-color: {t.bg_card}; color: #EF4444; border: 1.5px solid #7F1D1D; "
                f"border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 700; }} "
                f"QPushButton:hover:enabled {{ background-color: #7F1D1D; color: white; }}"
            )

        if hasattr(self, "source_selector"):
            self.source_selector.apply_theme(t)

        for tile in self.tiles:
            if not tile.is_matched and not tile.is_selected:
                tile.set_state("default", t)

    def _on_source_changed(self, cat: str, src: str):
        """Mavzu yoki to'plam o'zgarganda o'yin maydonini yangilash."""
        if not self.is_game_active:
            self.prepare_board()

    def _on_pair_count_changed(self, index: int):
        val = self.combo_pair_count.currentData()
        if val:
            self.target_pair_count = int(val)
            # Sanoq o'zgarganda taymer boshlanmaydi! Faqat maydon tayyorlanadi.
            self.prepare_board()

    def prepare_board(self):
        """O'yin maydonini tayyorlash — taymer boshlanmaydi."""
        self.timer.stop()
        self.is_game_active = False
        self.first_selected = None
        self.matched_pairs = 0
        self.elapsed_seconds = 0.0
        self.timer_display.setText("00:00.0")
        self.pairs_display.setText(f"0 / {self.target_pair_count}")
        self.best_display.setText(self._get_best_time_str())
        self.victory_banner.setVisible(False)

        self.btn_start_game.setText("▶️ O'yinni Boshlash")
        self.btn_start_game.setEnabled(True)
        self.combo_pair_count.setEnabled(True)
        if hasattr(self, "source_selector"):
            self.source_selector.set_enabled(True)
        self.btn_finish_game.setEnabled(False)

        self._render_cards()

    def start_game(self, recreate_cards: bool = True):
        """O'yinni vaqt hisobi bilan boshlash."""
        self.timer.stop()
        self.first_selected = None
        self.matched_pairs = 0
        self.elapsed_seconds = 0.0
        self.timer_display.setText("00:00.0")
        self.pairs_display.setText(f"0 / {self.target_pair_count}")
        self.victory_banner.setVisible(False)

        if hasattr(self, "source_selector"):
            self.source_selector.set_enabled(False)

        if recreate_cards or not self.tiles:
            self._render_cards()

        self.btn_start_game.setText("🔄 Qayta Boshlash")
        self.combo_pair_count.setEnabled(False)
        self.btn_finish_game.setEnabled(True)

        self.start_timestamp = time.time()
        self.is_game_active = True
        self.timer.start()

    def start_new_game(self):
        """Eski murojaatlar uchun moslik."""
        self.start_game(recreate_cards=True)

    def _render_cards(self):
        """Kartochkalarni bazadan olib maydonga joylashtirish."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.tiles = []

        all_words = []
        if hasattr(self, "source_selector"):
            all_words = self.source_selector.get_words(limit=100)

        if len(all_words) < self.target_pair_count:
            all_words = [dict(w) for w in db.get_words_with_progress()]

        if len(all_words) < self.target_pair_count:
            all_words = [dict(w) for w in db.get_words(limit=100)]

        if len(all_words) < self.target_pair_count:
            fallback = gwp.get_words_for_game(gwp.CAT_PACKS, "essential", limit=100)
            if fallback:
                all_words = fallback

        if len(all_words) < 2:
            no_words_lbl = QLabel(
                "Lug'atda so'zlar yetarli emas!\n"
                f"O'yin o'ynash uchun kamida {self.target_pair_count} ta so'z kiriting yoki 'So'z import qilish' bo'limidan qo'shing."
            )
            no_words_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_words_lbl.setStyleSheet("color: #F87171; font-size: 16px; font-weight: 600; padding: 40px;")
            self.grid_layout.addWidget(no_words_lbl, 0, 0)
            return

        target_count = min(self.target_pair_count, len(all_words))
        self.total_pairs = target_count
        self.pairs_display.setText(f"0 / {self.total_pairs}")

        # 1. Avvalo xato qilingan so'zlarni tanlash
        failed_pool = [w for w in all_words if w["id"] in self.failed_word_ids]
        # 2. Hali bu sessiyada chiqmagan yangi so'zlar
        unused_pool = [w for w in all_words if w["id"] not in self.used_word_ids and w["id"] not in self.failed_word_ids]

        if len(unused_pool) + len(failed_pool) < target_count:
            self.used_word_ids.clear()
            unused_pool = [w for w in all_words if w["id"] not in self.failed_word_ids]

        selected_words = []
        if failed_pool:
            selected_words.extend(failed_pool[:target_count])

        needed = target_count - len(selected_words)
        if needed > 0 and unused_pool:
            selected_words.extend(random.sample(unused_pool, min(needed, len(unused_pool))))

        if len(selected_words) < target_count:
            remaining = [w for w in all_words if w not in selected_words]
            fill_count = target_count - len(selected_words)
            if remaining:
                selected_words.extend(random.sample(remaining, min(fill_count, len(remaining))))

        for w in selected_words:
            self.used_word_ids.add(w["id"])

        cards_data: list[tuple[int, str, str]] = []
        for w in selected_words:
            w_id = w["id"]
            eng = w["english"]
            uz = w["uzbek"].split(",")[0].strip()
            cards_data.append((w_id, eng, "en"))
            cards_data.append((w_id, uz, "uz"))

        random.shuffle(cards_data)

        total_cards = len(cards_data)
        if total_cards >= 20:
            cols = 5
        else:
            cols = 4

        t = theme_manager.get_active_theme()

        for idx, (item_id, text, lang) in enumerate(cards_data):
            row = idx // cols
            col = idx % cols
            tile = MatchTile(item_id, text, lang, self)
            tile.set_state("default", t)
            tile.clicked.connect(lambda _, t_ref=tile: self._on_tile_clicked(t_ref))
            self.grid_layout.addWidget(tile, row, col)
            self.tiles.append(tile)

    def _on_timer_tick(self):
        if not self.is_game_active:
            return
        self.elapsed_seconds = time.time() - self.start_timestamp
        mins = int(self.elapsed_seconds // 60)
        secs = int(self.elapsed_seconds % 60)
        tenths = int((self.elapsed_seconds * 10) % 10)
        self.timer_display.setText(f"{mins:02d}:{secs:02d}.{tenths}")

    def _on_tile_clicked(self, tile: MatchTile):
        if tile.is_matched:
            return

        # Agar o'yin hali rasman boshlanmagan bo'lsa, birinchi kartochkani bosish o'yinni shu onda boshlaydi!
        if not self.is_game_active:
            self.start_game(recreate_cards=False)

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

            # Agar bu so'z avval xato ro'yxatida bo'lsa, endi u o'rganildi deb hisoblanadi
            if first.item_id in self.failed_word_ids:
                self.failed_word_ids.remove(first.item_id)

            # Leitner / SM-2 progressiga to'g'ri deb qayd etish
            db.record_answer(first.item_id, correct=True)

            if self.matched_pairs >= self.total_pairs:
                self.is_game_active = False
                self.timer.stop()
                QTimer.singleShot(250, self._handle_victory)
        else:
            # Xato juftlik
            first.set_state("wrong")
            tile.set_state("wrong")
            sound_effects.play_wrong()

            # Adashgan so'zlarni keyingi partiyada qayta berish uchun saqlab qolish
            self.failed_word_ids.add(first.item_id)
            self.failed_word_ids.add(tile.item_id)
            db.record_answer(first.item_id, correct=False)

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

    def _finish_game_manually(self):
        """Foydalanuvchi xohlagan paytda o'yinni yakunlashi uchun."""
        if not self.is_game_active and self.matched_pairs == 0:
            return

        self.is_game_active = False
        self.timer.stop()

        final_time = round(self.elapsed_seconds, 1)
        parent_window = self.window() if self.window() else self

        # GAMIFIKATSIYA QAT'IY QOIDASI: 0 ta juftlik topilsa 0 XP!
        if self.matched_pairs == 0:
            QMessageBox.information(
                parent_window,
                "O'yin Yakunlandi",
                f"⏹️ <b>O'yin yakunlandi</b><br><br>"
                f"Siz 0 ta juftlik topdingiz.<br>"
                f"<i>Qat'iy qoida: 0 ta juftlik bilan XP berilmaydi.</i>"
            )
            self.prepare_board()
            return

        xp_to_award = self.matched_pairs * 5
        new_xp, level_up, new_level = gamification.award_xp(xp_to_award)
        sound_effects.play_victory()
        try:
            import daily_quests_service
            daily_quests_service.record_quest_progress("game_score", xp_to_award)
            if self.matched_pairs >= 3:
                daily_quests_service.record_quest_progress("match_game", 1)
        except Exception:
            pass

        source_title = self.source_selector.get_current_source_title() if hasattr(self, "source_selector") else "Lug'at"

        self.victory_banner.setVisible(True)
        self.victory_banner_lbl.setText(
            f"🏁 O'yin yakunlandi [{source_title}]: {self.matched_pairs} / {self.total_pairs} juftlik topildi! Vaqt: {final_time:.1f}s  •  +{xp_to_award} XP"
        )

        dlg = VictoryDialog(
            parent_window,
            final_time=final_time,
            is_new_record=False,
            xp_gained=xp_to_award,
            total_xp=new_xp,
            level_up=level_up,
            new_level=new_level,
            custom_title=f"O'yin Yakunlandi — {source_title} ({self.matched_pairs}/{self.total_pairs})"
        )

        if dlg.exec():
            self.start_game(recreate_cards=True)
        else:
            self.prepare_board()

    def _handle_victory(self):
        """Barcha juftliklar topilganda g'alaba va mukofot."""
        try:
            self.is_game_active = False
            self.timer.stop()

            final_time = round(self.elapsed_seconds, 1)
            sound_effects.play_milestone()

            # Gamifikatsiya: har bir juftlik uchun 5 XP + 10 XP bonus
            earned_xp = self.total_pairs * 5 + 10
            new_xp, level_up, new_level = gamification.award_xp(earned_xp)
            try:
                import daily_quests_service
                daily_quests_service.record_quest_progress("game_score", earned_xp)
                daily_quests_service.record_quest_progress("match_game", 1)
            except Exception:
                pass

            # Rekordni tekshirish
            prev_best_str = db.get_setting("match_best_time", "")
            prev_best = None
            if prev_best_str:
                try:
                    val = float(prev_best_str)
                    if val > 0:
                        prev_best = val
                except ValueError:
                    pass

            is_new_record = False
            if prev_best is None or final_time < prev_best:
                db.set_setting("match_best_time", str(final_time))
                is_new_record = True
                self.best_display.setText(f"{final_time:.1f} soniya 👑")

            source_title = self.source_selector.get_current_source_title() if hasattr(self, "source_selector") else "Lug'at"

            # Vidjetdagi g'alaba bannerini yoqish
            self.victory_banner.setVisible(True)
            rec_txt = " (👑 Yangi shaxsiy rekord!)" if is_new_record else ""
            self.victory_banner_lbl.setText(
                f"🎉 Barcha {self.total_pairs} ta juftlik topildi! [{source_title}] • Vaqt: {final_time:.1f} soniya{rec_txt}  •  +{earned_xp} XP"
            )

            # Maxsus modal g'alaba oynasini ko'rsatish
            parent_window = self.window() if self.window() else self
            dlg = VictoryDialog(
                parent_window,
                final_time=final_time,
                is_new_record=is_new_record,
                xp_gained=earned_xp,
                total_xp=new_xp,
                level_up=level_up,
                new_level=new_level,
                custom_title=f"Qoyilmaqom G'alaba! — {source_title}"
            )
            if dlg.exec():
                self.start_game(recreate_cards=True)
            else:
                self.prepare_board()
        except Exception as e:
            logger.error(f"Word Match g'alaba amallarida xatolik: {e}", exc_info=True)
            self.prepare_board()

    def showEvent(self, event):
        super().showEvent(event)
        # Sahifaga o'tilganda taymer boshlanmaydi! Faqat maydon tayyorlanadi.
        if not self.is_game_active and self.matched_pairs == 0:
            self.prepare_board()

    def hideEvent(self, event):
        """Boshqa sahifaga o'tilganda Match o'yini taymerini to'xtatish."""
        if getattr(self, "is_game_active", False):
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
        super().hideEvent(event)
