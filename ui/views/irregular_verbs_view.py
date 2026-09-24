"""
ui/views/irregular_verbs_view.py
Noto'g'ri fe'llar (Irregular Verbs) uchun professional asosiy vidjet:
- 115 ta fe'ldan iborat to'liq interaktiv jadval (Qidiruv, Filtrlash, Audio, CRUD)
- 3-shakl viktorinasi (Quiz)
- Yozma sinov (Typing/Spelling)
- Flashcardlar (Aylanuvchi kartochkalar)
- So'z juftlash o'yini (Match Game)
- Harflardan yig'ish o'yini (Letter Scramble)
"""
import time
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget, QFrame,
    QMessageBox, QDialog, QFormLayout, QGridLayout, QScrollArea, QButtonGroup,
    QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QCursor

import ui.theme_manager as theme_manager
from services.irregular_verbs_service import (
    IrregularVerbsService, speak_verb_form, speak_all_forms
)
from utils.logger import get_logger

logger = get_logger("irregular_verbs_view")


# =====================================================================
# MODAL DIALOG: FE'L QO'SHISH VA TAHRIRLASH
# =====================================================================

class VerbEditDialog(QDialog):
    """Noto'g'ri fe'lni qo'shish yoki tahrirlash dialogi."""

    def __init__(self, parent=None, verb: Optional[Dict] = None):
        super().__init__(parent)
        self.verb = verb
        self.setWindowTitle("Yangi Noto'g'ri Fe'l Qo'shish" if not verb else "Fe'lni Tahrirlash")
        self.setMinimumWidth(420)
        self.setStyleSheet(self._dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_lbl = QLabel(self.windowTitle())
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        self.v1_input = QLineEdit(verb.get("v1", "") if verb else "")
        self.v1_input.setPlaceholderText("Masalan: take")

        self.v2_input = QLineEdit(verb.get("v2", "") if verb else "")
        self.v2_input.setPlaceholderText("Masalan: took")

        self.v3_input = QLineEdit(verb.get("v3", "") if verb else "")
        self.v3_input.setPlaceholderText("Masalan: taken")

        self.trans_input = QLineEdit(verb.get("translation", "") if verb else "")
        self.trans_input.setPlaceholderText("Masalan: olmoq")

        form.addRow("V1 (Infinitive):", self.v1_input)
        form.addRow("V2 (Past Simple):", self.v2_input)
        form.addRow("V3 (Past Participle):", self.v3_input)
        form.addRow("O'zbekcha Tarjima:", self.trans_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Bekor qilish")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Saqlash")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet("background-color: #4F46E5; color: white; font-weight: bold; padding: 6px 16px;")
        self.save_btn.clicked.connect(self._validate_and_save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _validate_and_save(self):
        v1 = self.v1_input.text().strip()
        v2 = self.v2_input.text().strip()
        v3 = self.v3_input.text().strip()
        tr = self.trans_input.text().strip()

        if not v1 or not v2 or not v3 or not tr:
            QMessageBox.warning(self, "Xatolik", "Iltimos, barcha 4 ta maydonni to'ldiring!")
            return

        self.accept()

    def get_data(self) -> Dict[str, str]:
        return {
            "v1": self.v1_input.text().strip(),
            "v2": self.v2_input.text().strip(),
            "v3": self.v3_input.text().strip(),
            "translation": self.trans_input.text().strip(),
        }

    def _dialog_style(self) -> str:
        return """
            QDialog {
                background-color: #1E1E2E;
                border-radius: 12px;
            }
            QLabel {
                color: #D1D5DB;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #171724;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #6366F1;
            }
            QPushButton {
                background-color: #2D3748;
                color: #E2E8F0;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #374151;
            }
        """


# =====================================================================
# ASOSIY VIDJET: IRREGULAR VERBS WIDGET
# =====================================================================

class IrregularVerbsWidget(QWidget):
    """
    Noto'g'ri fe'llar bo'limi:
    Sidebar dan 'Lug'at' ning tagida ochiladi.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.service = IrregularVerbsService()
        self.current_filter = "all"
        self._quiz_state = None
        self._typing_state = None
        self._flashcard_list = []
        self._fc_index = 0
        self._fc_is_flipped = False
        self._match_cards = []
        self._match_first_selected = None
        self._match_timer = None
        self._match_start_time = 0
        self._scramble_state = None
        self._scramble_current_assembled = []

        self.init_ui()
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        self.refresh_table()
        self.refresh_stats()

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # 1. Sarlavha va Statistika Kartochkalari
        header_layout = QHBoxLayout()

        title_col = QVBoxLayout()
        self.title_lbl = QLabel("⚡ Noto'g'ri Fe'llar (Irregular Verbs)")
        self.title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #FFFFFF;")
        self.sub_lbl = QLabel("115 ta asosiy fe'l, barcha shakllar, audio talaffuz va interaktiv trenajyorlar")
        self.sub_lbl.setStyleSheet("font-size: 13px; color: #9CA3AF;")
        title_col.addWidget(self.title_lbl)
        title_col.addWidget(self.sub_lbl)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        # Mini stats kartochkalari
        self.stats_box = QHBoxLayout()
        self.stats_box.setSpacing(10)
        self.stat_total = self._create_stat_badge("📚 Jami", "115")
        self.stat_learned = self._create_stat_badge("✅ Yodlandi", "0")
        self.stat_favs = self._create_stat_badge("⭐ Sevimlilar", "0")
        self.stat_accuracy = self._create_stat_badge("🎯 Aniqlik", "0%")
        self.stats_box.addWidget(self.stat_total)
        self.stats_box.addWidget(self.stat_learned)
        self.stats_box.addWidget(self.stat_favs)
        self.stats_box.addWidget(self.stat_accuracy)
        header_layout.addLayout(self.stats_box)

        root.addLayout(header_layout)

        # 2. Sub-tab Navigatsiya Menyusi (Pill buttons)
        self.nav_bar = QHBoxLayout()
        self.nav_bar.setSpacing(8)

        self.nav_btn_table = QPushButton("📋 Fe'llar Jadvali")
        self.nav_btn_quiz = QPushButton("🎯 3-Shakl Testi (Quiz)")
        self.nav_btn_typing = QPushButton("⌨️ Yozma Sinov (Typing)")
        self.nav_btn_flashcard = QPushButton("🗂️ Flashcardlar")
        self.nav_btn_match = QPushButton("🧩 So'z Juftlash (Match)")
        self.nav_btn_scramble = QPushButton("🔤 Harflardan Yig'ish")

        self.tab_buttons = [
            (self.nav_btn_table, 0),
            (self.nav_btn_quiz, 1),
            (self.nav_btn_typing, 2),
            (self.nav_btn_flashcard, 3),
            (self.nav_btn_match, 4),
            (self.nav_btn_scramble, 5),
        ]

        for btn, idx in self.tab_buttons:
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self.switch_tab(i))
            self.nav_bar.addWidget(btn)

        self.nav_bar.addStretch()
        root.addLayout(self.nav_bar)

        # 3. Stacked Widget (Asosiy sahifalar)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_table_page())       # Index 0
        self.stack.addWidget(self._build_quiz_page())        # Index 1
        self.stack.addWidget(self._build_typing_page())      # Index 2
        self.stack.addWidget(self._build_flashcard_page())   # Index 3
        self.stack.addWidget(self._build_match_page())       # Index 4
        self.stack.addWidget(self._build_scramble_page())    # Index 5

        root.addWidget(self.stack, 1)

        # Boshlang'ich holat: Jadval tanlangan
        self.switch_tab(0)

    def _create_stat_badge(self, title: str, val: str) -> QFrame:
        badge = QFrame()
        badge.setStyleSheet("""
            QFrame {
                background-color: #1E1E2E;
                border: 1px solid #2A2A3C;
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        lay = QVBoxLayout(badge)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 11px; color: #9CA3AF;")
        v_lbl = QLabel(val)
        v_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #818CF8;")
        lay.addWidget(t_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(v_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        badge.val_lbl = v_lbl
        return badge

    def switch_tab(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for btn, i in self.tab_buttons:
            btn.setChecked(i == idx)

        # Sahifa ochilganda tegishli generatorni chaqirish
        if idx == 0:
            self.refresh_table()
        elif idx == 1:
            self.load_next_quiz()
        elif idx == 2:
            self.load_next_typing()
        elif idx == 3:
            self.init_flashcards()
        elif idx == 4:
            self.start_match_game()
        elif idx == 5:
            self.load_next_scramble()

    # =================================================================
    # 1. TAB: FE'LLAR JADVALI (TABLE & SEARCH)
    # =================================================================

    def _build_table_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # Qidiruv va Filtr paneli
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Fe'lni qidirish (V1, V2, V3 yoki o'zbekcha tarjima)...")
        self.search_input.textChanged.connect(self._on_search_changed)
        self.search_input.setFixedHeight(38)
        top_bar.addWidget(self.search_input, 2)

        # Filtr chiplari
        self.filter_group = QButtonGroup(self)
        self.chip_all = QPushButton("Hammasi")
        self.chip_unlearned = QPushButton("O'rganilmagan")
        self.chip_learned = QPushButton("Yodlangan")
        self.chip_favs = QPushButton("⭐ Sevimlilar")

        chips = [
            (self.chip_all, "all"),
            (self.chip_unlearned, "unlearned"),
            (self.chip_learned, "learned"),
            (self.chip_favs, "favorites"),
        ]

        for chip, mode in chips:
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda checked, m=mode: self._set_filter(m))
            self.filter_group.addButton(chip)
            top_bar.addWidget(chip)

        self.chip_all.setChecked(True)

        top_bar.addSpacing(10)

        # Yangi fe'l qo'shish tugmasi
        self.add_btn = QPushButton("➕ Yangi fe'l")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFixedHeight(38)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 8px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
        """)
        self.add_btn.clicked.connect(self._on_add_verb_clicked)
        top_bar.addWidget(self.add_btn)

        lay.addLayout(top_bar)

        # Jadval
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "⭐", "V1 (Infinitive)", "V2 (Past Simple)", "V3 (Past Participle)",
            "O'zbekcha Tarjima", "🔊 Barchasi", "Holat", "Amallar"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Ustun kengliklari
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 45)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 160)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 160)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 160)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 100)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 110)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, 100)

        lay.addWidget(self.table)

        # Jadval quyi hisoblagich paneli
        bot_bar = QHBoxLayout()
        self.table_counter_lbl = QLabel("")
        self.table_counter_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: 500;")
        bot_bar.addWidget(self.table_counter_lbl)
        bot_bar.addStretch()
        lay.addLayout(bot_bar)

        return page

    def _set_filter(self, mode: str):
        self.current_filter = mode
        self.refresh_table()

    def _on_search_changed(self, text: str):
        self.refresh_table()

    def refresh_stats(self):
        st = self.service.get_stats()
        self.stat_total.val_lbl.setText(str(st["total"]))
        self.stat_learned.val_lbl.setText(f"{st['learned']} / {st['total']}")
        self.stat_favs.val_lbl.setText(str(st["favorites"]))
        self.stat_accuracy.val_lbl.setText(f"{st['accuracy']}%")

    def refresh_table(self):
        query = self.search_input.text().strip()
        verbs = self.service.get_verbs(search=query, filter_mode=self.current_filter)

        self.table.setRowCount(len(verbs))
        total_count = len(verbs)
        if hasattr(self, "table_counter_lbl"):
            if query:
                self.table_counter_lbl.setText(f"🔍 Qidiruv bo'yicha: {total_count} ta fe'l topildi")
            else:
                self.table_counter_lbl.setText(f"📋 Jami ko'rsatilmoqda: {total_count} ta fe'l")

        self.refresh_stats()

        for row_idx, v in enumerate(verbs):
            self.table.setRowHeight(row_idx, 46)

            # 0. Yulduzcha (Favorite)
            fav_btn = QPushButton("★" if v["favorite"] else "☆")
            fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            fav_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    font-size: 18px;
                    color: {"#F59E0B" if v["favorite"] else "#6B7280"};
                }}
                QPushButton:hover {{
                    color: #FBBF24;
                }}
            """)
            fav_btn.clicked.connect(lambda ch, vid=v["id"]: self._toggle_fav(vid))
            self.table.setCellWidget(row_idx, 0, fav_btn)

            # 1. V1 + 🔊
            v1_widget = self._create_audio_cell(v["v1"], v["v1"])
            self.table.setCellWidget(row_idx, 1, v1_widget)

            # 2. V2 + 🔊
            v2_widget = self._create_audio_cell(v["v2"], v["v2"])
            self.table.setCellWidget(row_idx, 2, v2_widget)

            # 3. V3 + 🔊
            v3_widget = self._create_audio_cell(v["v3"], v["v3"])
            self.table.setCellWidget(row_idx, 3, v3_widget)

            # 4. Tarjima
            tr_item = QTableWidgetItem(f" {v['translation']}")
            tr_item.setFont(QFont("Segoe UI", 10))
            self.table.setItem(row_idx, 4, tr_item)

            # 5. 🔊 Barchasini talaffuz qilish
            all_audio_btn = QPushButton("🔊 1-2-3")
            all_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            all_audio_btn.setStyleSheet("""
                QPushButton {
                    background-color: #312E81;
                    color: #C7D2FE;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3730A3;
                    color: #FFFFFF;
                }
            """)
            all_audio_btn.clicked.connect(lambda ch, item=v: speak_all_forms(item["v1"], item["v2"], item["v3"]))
            self.table.setCellWidget(row_idx, 5, all_audio_btn)

            # 6. Holat (Learned toggle badge)
            is_learned = bool(v["learned"])
            status_btn = QPushButton("✅ Yodlangan" if is_learned else "⏳ O'rganish")
            status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            status_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {"#065F46" if is_learned else "#1F2937"};
                    color: {"#6EE7B7" if is_learned else "#9CA3AF"};
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 6px;
                }}
                QPushButton:hover {{
                    background-color: {"#047857" if is_learned else "#374151"};
                }}
            """)
            status_btn.clicked.connect(lambda ch, vid=v["id"]: self._toggle_learned(vid))
            self.table.setCellWidget(row_idx, 6, status_btn)

            # 7. Amallar: Tahrirlash va O'chirish
            actions_w = QWidget()
            a_lay = QHBoxLayout(actions_w)
            a_lay.setContentsMargins(4, 2, 4, 2)
            a_lay.setSpacing(6)

            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Tahrirlash")
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setStyleSheet("background: transparent; border: none; font-size: 13px;")
            edit_btn.clicked.connect(lambda ch, verb=v: self._on_edit_verb_clicked(verb))
            a_lay.addWidget(edit_btn)

            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("O'chirish")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet("background: transparent; border: none; font-size: 13px; color: #EF4444;")
            del_btn.clicked.connect(lambda ch, vid=v["id"]: self._on_delete_verb_clicked(vid))
            a_lay.addWidget(del_btn)

            self.table.setCellWidget(row_idx, 7, actions_w)

    def _create_audio_cell(self, text: str, speak_val: str) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)

        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        lbl.setStyleSheet("color: #FFFFFF;")
        lay.addWidget(lbl, 1)

        spk_btn = QPushButton("🔊")
        spk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        spk_btn.setToolTip(f"Talaffuz: {text}")
        spk_btn.setFixedSize(24, 24)
        spk_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 12px;
                color: #A5B4FC;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        spk_btn.clicked.connect(lambda ch, s=speak_val: speak_verb_form(s))
        lay.addWidget(spk_btn)

        return w

    def _toggle_fav(self, verb_id: int):
        self.service.toggle_favorite(verb_id)
        self.refresh_table()
        self.refresh_stats()

    def _toggle_learned(self, verb_id: int):
        self.service.toggle_learned(verb_id)
        self.refresh_table()
        self.refresh_stats()

    def _on_add_verb_clicked(self):
        dlg = VerbEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.service.add_verb(data["v1"], data["v2"], data["v3"], data["translation"])
            self.refresh_table()
            self.refresh_stats()

    def _on_edit_verb_clicked(self, verb: Dict):
        dlg = VerbEditDialog(self, verb=verb)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.service.update_verb(verb["id"], data["v1"], data["v2"], data["v3"], data["translation"])
            self.refresh_table()

    def _on_delete_verb_clicked(self, verb_id: int):
        ret = QMessageBox.question(
            self,
            "O'chirishni tasdiqlash",
            "Haqiqatan ham ushbu fe'lni o'chirmoqchimisiz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.service.delete_verb(verb_id)
            self.refresh_table()
            self.refresh_stats()

    # =================================================================
    # 2. TAB: 3-SHAKL TESTI (QUIZ)
    # =================================================================

    def _build_quiz_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(20)

        # Savol kartochkasi
        self.quiz_card = QFrame()
        self.quiz_card.setStyleSheet("""
            QFrame {
                background-color: #1E1E2E;
                border: 1px solid #312E81;
                border-radius: 16px;
                padding: 24px;
            }
        """)
        q_lay = QVBoxLayout(self.quiz_card)
        q_lay.setSpacing(12)
        q_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        prompt_lbl = QLabel("Ushbu fe'lning to'g'ri V2 (Past Simple) va V3 (Past Participle) shakllarini tanlang:")
        prompt_lbl.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        q_lay.addWidget(prompt_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        h_box = QHBoxLayout()
        h_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quiz_word_lbl = QLabel("break")
        self.quiz_word_lbl.setStyleSheet("font-size: 32px; font-weight: 800; color: #818CF8;")
        h_box.addWidget(self.quiz_word_lbl)

        self.quiz_audio_btn = QPushButton("🔊")
        self.quiz_audio_btn.setFixedSize(36, 36)
        self.quiz_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quiz_audio_btn.setStyleSheet("font-size: 18px; background: transparent; border: none;")
        self.quiz_audio_btn.clicked.connect(self._play_quiz_audio)
        h_box.addWidget(self.quiz_audio_btn)

        q_lay.addLayout(h_box)

        self.quiz_trans_lbl = QLabel("sindirmoq")
        self.quiz_trans_lbl.setStyleSheet("font-size: 16px; font-style: italic; color: #D1D5DB;")
        q_lay.addWidget(self.quiz_trans_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self.quiz_card)

        # Variantlar to'ri (2x2)
        self.quiz_grid = QGridLayout()
        self.quiz_grid.setSpacing(16)
        self.quiz_option_btns = []

        for i in range(4):
            btn = QPushButton(f"Option {i}")
            btn.setMinimumHeight(60)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._option_btn_style("default"))
            btn.clicked.connect(lambda ch, idx=i: self._on_quiz_option_selected(idx))
            self.quiz_grid.addWidget(btn, i // 2, i % 2)
            self.quiz_option_btns.append(btn)

        lay.addLayout(self.quiz_grid)

        # Natija va Keyingi tugma
        bottom_box = QHBoxLayout()
        self.quiz_feedback_lbl = QLabel("")
        self.quiz_feedback_lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        bottom_box.addWidget(self.quiz_feedback_lbl)

        bottom_box.addStretch()

        self.quiz_next_btn = QPushButton("Keyingi Savol ➔")
        self.quiz_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quiz_next_btn.setFixedHeight(44)
        self.quiz_next_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 0 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
        """)
        self.quiz_next_btn.clicked.connect(self.load_next_quiz)
        bottom_box.addWidget(self.quiz_next_btn)

        lay.addLayout(bottom_box)
        lay.addStretch()
        return page

    def load_next_quiz(self):
        q = self.service.generate_quiz_question(filter_mode=self.current_filter)
        if not q:
            return

        self._quiz_state = q
        self.quiz_word_lbl.setText(q["question_v1"])
        self.quiz_trans_lbl.setText(f"({q['translation']})")
        self.quiz_feedback_lbl.setText("")
        self.quiz_next_btn.setEnabled(True)

        for i, opt_text in enumerate(q["options"]):
            btn = self.quiz_option_btns[i]
            btn.setText(opt_text)
            btn.setEnabled(True)
            btn.setStyleSheet(self._option_btn_style("default"))

    def _play_quiz_audio(self):
        if self._quiz_state:
            speak_verb_form(self._quiz_state["question_v1"])

    def _on_quiz_option_selected(self, chosen_idx: int):
        if not self._quiz_state:
            return

        chosen_text = self._quiz_state["options"][chosen_idx]
        is_correct = (chosen_text == self._quiz_state["correct_answer"])

        self.service.record_practice(self._quiz_state["target"]["id"], is_correct)
        self.refresh_stats()

        # Variantlarni belgilash
        for i, opt_text in enumerate(self._quiz_state["options"]):
            btn = self.quiz_option_btns[i]
            btn.setEnabled(False)
            if opt_text == self._quiz_state["correct_answer"]:
                btn.setStyleSheet(self._option_btn_style("correct"))
            elif i == chosen_idx and not is_correct:
                btn.setStyleSheet(self._option_btn_style("wrong"))

        if is_correct:
            self.quiz_feedback_lbl.setText("🎉 Barakalla! To'g'ri topdingiz!")
            self.quiz_feedback_lbl.setStyleSheet("color: #10B981; font-size: 16px; font-weight: bold;")
            # Barcha 3 ta shaklni ovozli eshittirish
            t = self._quiz_state["target"]
            speak_all_forms(t["v1"], t["v2"], t["v3"])
        else:
            self.quiz_feedback_lbl.setText(f"❌ Xato! To'g'ri javob: {self._quiz_state['correct_answer']}")
            self.quiz_feedback_lbl.setStyleSheet("color: #EF4444; font-size: 16px; font-weight: bold;")

    def _option_btn_style(self, state: str) -> str:
        if state == "correct":
            return """
                QPushButton {
                    background-color: #065F46;
                    border: 2px solid #10B981;
                    border-radius: 12px;
                    color: #FFFFFF;
                    font-size: 16px;
                    font-weight: bold;
                }
            """
        elif state == "wrong":
            return """
                QPushButton {
                    background-color: #7F1D1D;
                    border: 2px solid #EF4444;
                    border-radius: 12px;
                    color: #FFFFFF;
                    font-size: 16px;
                    font-weight: bold;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #1E1E2E;
                    border: 1px solid #374151;
                    border-radius: 12px;
                    color: #E2E8F0;
                    font-size: 16px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2D3748;
                    border-color: #6366F1;
                }
            """

    # =================================================================
    # 3. TAB: YOZMA SINOV (TYPING / SPELLING)
    # =================================================================

    def _build_typing_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(60, 20, 60, 20)
        lay.setSpacing(20)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1E1E2E;
                border: 1px solid #312E81;
                border-radius: 16px;
                padding: 24px;
            }
        """)
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(16)
        c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        prompt = QLabel("Klaviaturada V2 va V3 shakllarini yozing va Enter tugmasini bosing:")
        prompt.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        c_lay.addWidget(prompt, 0, Qt.AlignmentFlag.AlignCenter)

        self.typing_v1_lbl = QLabel("speak")
        self.typing_v1_lbl.setStyleSheet("font-size: 34px; font-weight: 800; color: #818CF8;")
        c_lay.addWidget(self.typing_v1_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        self.typing_trans_lbl = QLabel("gapirmoq")
        self.typing_trans_lbl.setStyleSheet("font-size: 16px; font-style: italic; color: #D1D5DB;")
        c_lay.addWidget(self.typing_trans_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Kirish maydonlari
        inputs_box = QHBoxLayout()
        inputs_box.setSpacing(24)

        # V2 box
        v2_box = QVBoxLayout()
        v2_lbl = QLabel("V2 (Past Simple):")
        v2_lbl.setStyleSheet("color: #A5B4FC; font-weight: bold; font-size: 13px;")
        self.input_v2 = QLineEdit()
        self.input_v2.setFixedHeight(46)
        self.input_v2.setPlaceholderText("V2 shaklini yozing...")
        self.input_v2.setStyleSheet(self._input_field_style())
        self.input_v2.returnPressed.connect(self._check_typing_answer)
        v2_box.addWidget(v2_lbl)
        v2_box.addWidget(self.input_v2)
        inputs_box.addLayout(v2_box)

        # V3 box
        v3_box = QVBoxLayout()
        v3_lbl = QLabel("V3 (Past Participle):")
        v3_lbl.setStyleSheet("color: #A5B4FC; font-weight: bold; font-size: 13px;")
        self.input_v3 = QLineEdit()
        self.input_v3.setFixedHeight(46)
        self.input_v3.setPlaceholderText("V3 shaklini yozing...")
        self.input_v3.setStyleSheet(self._input_field_style())
        self.input_v3.returnPressed.connect(self._check_typing_answer)
        v3_box.addWidget(v3_lbl)
        v3_box.addWidget(self.input_v3)
        inputs_box.addLayout(v3_box)

        c_lay.addLayout(inputs_box)

        # Tekshirish tugmasi
        self.check_typing_btn = QPushButton("Tekshirish (Enter)")
        self.check_typing_btn.setFixedHeight(44)
        self.check_typing_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_typing_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 0 30px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
        """)
        self.check_typing_btn.clicked.connect(self._check_typing_answer)
        c_lay.addWidget(self.check_typing_btn, 0, Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(card)

        # Natija va Keyingi
        res_box = QHBoxLayout()
        self.typing_feedback_lbl = QLabel("")
        self.typing_feedback_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        res_box.addWidget(self.typing_feedback_lbl)

        res_box.addStretch()

        self.typing_next_btn = QPushButton("Keyingi Fe'l ➔")
        self.typing_next_btn.setFixedHeight(42)
        self.typing_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.typing_next_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D3748;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #374151;
            }
        """)
        self.typing_next_btn.clicked.connect(self.load_next_typing)
        res_box.addWidget(self.typing_next_btn)

        lay.addLayout(res_box)
        lay.addStretch()
        return page

    def _input_field_style(self) -> str:
        return """
            QLineEdit {
                background-color: #171724;
                border: 2px solid #374151;
                border-radius: 8px;
                padding: 8px 14px;
                color: #FFFFFF;
                font-size: 16px;
            }
            QLineEdit:focus {
                border-color: #6366F1;
            }
        """

    def load_next_typing(self):
        t = self.service.generate_typing_question(filter_mode=self.current_filter)
        if not t:
            return

        self._typing_state = t
        self.typing_v1_lbl.setText(t["v1"])
        self.typing_trans_lbl.setText(f"({t['translation']})")
        self.input_v2.clear()
        self.input_v3.clear()
        self.input_v2.setStyleSheet(self._input_field_style())
        self.input_v3.setStyleSheet(self._input_field_style())
        self.typing_feedback_lbl.setText("")
        self.input_v2.setFocus()

    def _check_typing_answer(self):
        if not self._typing_state:
            return

        user_v2 = self.input_v2.text().strip()
        user_v3 = self.input_v3.text().strip()
        corr_v2 = self._typing_state["v2"]
        corr_v3 = self._typing_state["v3"]

        v2_ok, v3_ok = self.service.check_typing_answer(user_v2, user_v3, corr_v2, corr_v3)
        is_all_correct = v2_ok and v3_ok

        self.service.record_practice(self._typing_state["target"]["id"], is_all_correct)
        self.refresh_stats()

        # V2 stilini belgilash
        if v2_ok:
            self.input_v2.setStyleSheet("background-color: #064E3B; border: 2px solid #10B981; border-radius: 8px; color: white; font-size: 16px; padding: 8px 14px;")
        else:
            self.input_v2.setStyleSheet("background-color: #7F1D1D; border: 2px solid #EF4444; border-radius: 8px; color: white; font-size: 16px; padding: 8px 14px;")

        # V3 stilini belgilash
        if v3_ok:
            self.input_v3.setStyleSheet("background-color: #064E3B; border: 2px solid #10B981; border-radius: 8px; color: white; font-size: 16px; padding: 8px 14px;")
        else:
            self.input_v3.setStyleSheet("background-color: #7F1D1D; border: 2px solid #EF4444; border-radius: 8px; color: white; font-size: 16px; padding: 8px 14px;")

        if is_all_correct:
            self.typing_feedback_lbl.setText(f"🎉 A'lo darajada! To'g'ri: {corr_v2} / {corr_v3}")
            self.typing_feedback_lbl.setStyleSheet("color: #10B981; font-size: 16px; font-weight: bold;")
            speak_all_forms(self._typing_state["v1"], corr_v2, corr_v3)
        else:
            self.typing_feedback_lbl.setText(f"To'g'ri javob: {corr_v2}  /  {corr_v3}")
            self.typing_feedback_lbl.setStyleSheet("color: #F87171; font-size: 16px; font-weight: bold;")

    # =================================================================
    # 4. TAB: FLASHCARDLAR (INTERAKTIV FLIP KARTALAR)
    # =================================================================

    def _build_flashcard_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(60, 16, 60, 16)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Yuqori ma'lumot va qisqa tugmalar eslatmasi
        top_meta = QHBoxLayout()
        self.fc_progress_lbl = QLabel("🔖 Karta: 1 / 115")
        self.fc_progress_lbl.setStyleSheet("color: #818CF8; font-weight: bold; font-size: 14px;")
        top_meta.addWidget(self.fc_progress_lbl)

        top_meta.addStretch()

        shortcut_hint = QLabel("💡 Tugmalar: [Space] Aylantirish | [←] Bilmayman | [→] Yodladim | [A] Audio")
        shortcut_hint.setStyleSheet("color: #6B7280; font-size: 12px; font-style: italic;")
        top_meta.addWidget(shortcut_hint)
        lay.addLayout(top_meta)

        # 2. Sleek Kartochka Progress Bari
        self.fc_progress_bar = QProgressBar()
        self.fc_progress_bar.setFixedHeight(5)
        self.fc_progress_bar.setTextVisible(False)
        self.fc_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E1E2E;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #10B981);
                border-radius: 2px;
            }
        """)
        lay.addWidget(self.fc_progress_bar)

        # 3. Asosiy Flashcard (Zamonaviy Neon-Glass dizayn)
        self.fc_card = QFrame()
        self.fc_card.setObjectName("flashcard_container")
        self.fc_card.setFixedSize(620, 310)
        self.fc_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fc_card.mousePressEvent = lambda e: self._flip_flashcard()

        # Faqat konteynerga ta'sir qiluvchi CSS (bolalar label'lariga border o'tib ketmaydi!)
        self.fc_card.setStyleSheet("""
            QFrame#flashcard_container {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E1E2E, stop:1 #161625);
                border: 2px solid #4F46E5;
                border-radius: 24px;
            }
            QFrame#flashcard_container:hover {
                border: 2px solid #6366F1;
            }
            QFrame#flashcard_container QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)

        card_layout = QVBoxLayout(self.fc_card)
        card_layout.setContentsMargins(28, 20, 28, 20)
        card_layout.setSpacing(10)

        # Kartochka ichki bosh qismi (Status va Yulduzcha)
        card_top = QHBoxLayout()
        self.fc_side_tag = QLabel("✨ OLD TOMON (Infinitive)")
        self.fc_side_tag.setStyleSheet("""
            color: #A5B4FC;
            background-color: #312E81;
            padding: 4px 14px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        """)
        card_top.addWidget(self.fc_side_tag)

        card_top.addStretch()

        self.fc_star_btn = QPushButton("☆")
        self.fc_star_btn.setFixedSize(32, 32)
        self.fc_star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fc_star_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 22px;
                color: #F59E0B;
            }
            QPushButton:hover {
                color: #FBBF24;
            }
        """)
        self.fc_star_btn.clicked.connect(self._fc_toggle_star)
        card_top.addWidget(self.fc_star_btn)

        card_layout.addLayout(card_top)

        # Kartaning ichki almashtiriluvchi qatlami (Front va Back)
        self.fc_card_stack = QStackedWidget()
        self.fc_card_stack.setStyleSheet("background: transparent; border: none;")

        # --- OLD TOMON (FRONT) ---
        self.fc_front_widget = QWidget()
        self.fc_front_widget.setStyleSheet("background: transparent; border: none;")
        front_lay = QVBoxLayout(self.fc_front_widget)
        front_lay.setContentsMargins(0, 10, 0, 0)
        front_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        front_lay.setSpacing(10)

        self.fc_v1_lbl = QLabel("become")
        self.fc_v1_lbl.setStyleSheet("font-size: 42px; font-weight: 800; color: #FFFFFF;")
        front_lay.addWidget(self.fc_v1_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        self.fc_trans_lbl = QLabel("bo'lmoq")
        self.fc_trans_lbl.setStyleSheet("font-size: 19px; color: #9CA3AF; font-style: italic;")
        front_lay.addWidget(self.fc_trans_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        front_hint = QLabel("💡 Aylanitirish uchun kartochkani bosing")
        front_hint.setStyleSheet("font-size: 12px; color: #6366F1; padding-top: 14px;")
        front_lay.addWidget(front_hint, 0, Qt.AlignmentFlag.AlignCenter)

        self.fc_card_stack.addWidget(self.fc_front_widget)

        # --- ORQA TOMON (BACK) ---
        self.fc_back_widget = QWidget()
        self.fc_back_widget.setStyleSheet("background: transparent; border: none;")
        back_lay = QVBoxLayout(self.fc_back_widget)
        back_lay.setContentsMargins(0, 10, 0, 0)
        back_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back_lay.setSpacing(12)

        # V2 va V3 yonma-yon bloklari
        forms_box = QHBoxLayout()
        forms_box.setSpacing(16)

        # V2 Bloki
        self.fc_v2_card = QFrame()
        self.fc_v2_card.setStyleSheet("""
            QFrame {
                background-color: #171724;
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        v2_lay = QVBoxLayout(self.fc_v2_card)
        v2_lay.setContentsMargins(12, 8, 12, 8)
        v2_lay.setSpacing(4)
        v2_tag = QLabel("V2 (Past Simple)")
        v2_tag.setStyleSheet("color: #A5B4FC; font-size: 11px; font-weight: bold;")
        self.fc_v2_lbl = QLabel("became")
        self.fc_v2_lbl.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: 800;")
        v2_lay.addWidget(v2_tag, 0, Qt.AlignmentFlag.AlignCenter)
        v2_lay.addWidget(self.fc_v2_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        forms_box.addWidget(self.fc_v2_card)

        # V3 Bloki
        self.fc_v3_card = QFrame()
        self.fc_v3_card.setStyleSheet("""
            QFrame {
                background-color: #171724;
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        v3_lay = QVBoxLayout(self.fc_v3_card)
        v3_lay.setContentsMargins(12, 8, 12, 8)
        v3_lay.setSpacing(4)
        v3_tag = QLabel("V3 (Past Participle)")
        v3_tag.setStyleSheet("color: #A5B4FC; font-size: 11px; font-weight: bold;")
        self.fc_v3_lbl = QLabel("become")
        self.fc_v3_lbl.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: 800;")
        v3_lay.addWidget(v3_tag, 0, Qt.AlignmentFlag.AlignCenter)
        v3_lay.addWidget(self.fc_v3_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        forms_box.addWidget(self.fc_v3_card)

        back_lay.addLayout(forms_box)

        self.fc_back_trans_lbl = QLabel("💡 V1: become — bo'lmoq")
        self.fc_back_trans_lbl.setStyleSheet("color: #E2E8F0; font-size: 15px; font-style: italic;")
        back_lay.addWidget(self.fc_back_trans_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        self.fc_card_stack.addWidget(self.fc_back_widget)
        card_layout.addWidget(self.fc_card_stack, 1)

        lay.addWidget(self.fc_card, 0, Qt.AlignmentFlag.AlignCenter)

        # 4. Pastki Boshqaruv Tugmalari
        ctl_box = QHBoxLayout()
        ctl_box.setSpacing(14)

        self.fc_unlearned_btn = QPushButton("❌ Hali bilmayman  [←]")
        self.fc_unlearned_btn.setFixedHeight(46)
        self.fc_unlearned_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fc_unlearned_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2430;
                color: #F87171;
                border: 1px solid #7F1D1D;
                font-weight: bold;
                border-radius: 10px;
                padding: 0 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7F1D1D;
                color: #FFFFFF;
            }
        """)
        self.fc_unlearned_btn.clicked.connect(self._fc_mark_unlearned)
        ctl_box.addWidget(self.fc_unlearned_btn)

        self.fc_flip_btn = QPushButton("🔄 Aylantirish  [Space]")
        self.fc_flip_btn.setFixedHeight(46)
        self.fc_flip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fc_flip_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                border-radius: 10px;
                padding: 0 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
        """)
        self.fc_flip_btn.clicked.connect(self._flip_flashcard)
        ctl_box.addWidget(self.fc_flip_btn)

        self.fc_audio_btn = QPushButton("🔊 Audio  [A]")
        self.fc_audio_btn.setFixedHeight(46)
        self.fc_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fc_audio_btn.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                color: #A5B4FC;
                border: 1px solid #374151;
                font-weight: bold;
                border-radius: 10px;
                padding: 0 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #374151;
                color: #FFFFFF;
            }
        """)
        self.fc_audio_btn.clicked.connect(self._fc_play_audio)
        ctl_box.addWidget(self.fc_audio_btn)

        self.fc_learned_btn = QPushButton("✅ Yodladim  [→]")
        self.fc_learned_btn.setFixedHeight(46)
        self.fc_learned_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fc_learned_btn.setStyleSheet("""
            QPushButton {
                background-color: #064E3B;
                color: #6EE7B7;
                border: 1px solid #059669;
                font-weight: bold;
                border-radius: 10px;
                padding: 0 22px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
                color: #FFFFFF;
            }
        """)
        self.fc_learned_btn.clicked.connect(self._fc_mark_learned)
        ctl_box.addWidget(self.fc_learned_btn)

        lay.addLayout(ctl_box)
        return page

    def init_flashcards(self):
        self._flashcard_list = self.service.get_verbs(filter_mode=self.current_filter)
        if not self._flashcard_list:
            self._flashcard_list = self.service.get_verbs(filter_mode="all")
        self._fc_index = 0
        self._fc_is_flipped = False
        self._render_current_flashcard()

    def _render_current_flashcard(self):
        if not self._flashcard_list or self._fc_index >= len(self._flashcard_list):
            self.fc_progress_lbl.setText("Barcha kartochkalar tugadi!")
            self.fc_v1_lbl.setText("🎉 Tabriklaymiz!")
            self.fc_trans_lbl.setText("Barcha kartochkalar ko'rib chiqildi")
            self.fc_side_tag.setText("YAKUNLANDI")
            self.fc_card_stack.setCurrentIndex(0)
            return

        item = self._flashcard_list[self._fc_index]
        total = len(self._flashcard_list)
        cur = self._fc_index + 1

        self.fc_progress_lbl.setText(f"🔖 Karta: {cur} / {total}")
        self.fc_progress_bar.setMaximum(total)
        self.fc_progress_bar.setValue(cur)

        # Yulduzcha holati
        self.fc_star_btn.setText("★" if item.get("favorite") else "☆")

        if not self._fc_is_flipped:
            self.fc_side_tag.setText("✨ OLD TOMON (Infinitive)")
            self.fc_side_tag.setStyleSheet("""
                color: #A5B4FC;
                background-color: #312E81;
                padding: 4px 14px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            """)
            self.fc_v1_lbl.setText(item["v1"])
            self.fc_trans_lbl.setText(f"({item['translation']})")
            self.fc_card_stack.setCurrentIndex(0)
        else:
            self.fc_side_tag.setText("🔄 ORQA TOMON (O'tgan shakllar)")
            self.fc_side_tag.setStyleSheet("""
                color: #6EE7B7;
                background-color: #064E3B;
                padding: 4px 14px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            """)
            self.fc_v2_lbl.setText(item["v2"])
            self.fc_v3_lbl.setText(item["v3"])
            self.fc_back_trans_lbl.setText(f"💡 V1: {item['v1']} — {item['translation']}")
            self.fc_card_stack.setCurrentIndex(1)

    def _flip_flashcard(self):
        self._fc_is_flipped = not self._fc_is_flipped
        self._render_current_flashcard()
        if self._fc_is_flipped and self._flashcard_list and self._fc_index < len(self._flashcard_list):
            item = self._flashcard_list[self._fc_index]
            speak_all_forms(item["v1"], item["v2"], item["v3"])

    def _fc_play_audio(self):
        if self._flashcard_list and self._fc_index < len(self._flashcard_list):
            item = self._flashcard_list[self._fc_index]
            if self._fc_is_flipped:
                speak_all_forms(item["v1"], item["v2"], item["v3"])
            else:
                speak_verb_form(item["v1"])

    def _fc_toggle_star(self):
        if self._flashcard_list and self._fc_index < len(self._flashcard_list):
            item = self._flashcard_list[self._fc_index]
            new_fav = self.service.toggle_favorite(item["id"])
            item["favorite"] = int(new_fav)
            self.fc_star_btn.setText("★" if new_fav else "☆")
            self.refresh_stats()

    def _fc_mark_learned(self):
        if self._flashcard_list and self._fc_index < len(self._flashcard_list):
            item = self._flashcard_list[self._fc_index]
            self.service.toggle_learned(item["id"])
            self.service.record_practice(item["id"], is_correct=True)
            self.refresh_stats()

        self._fc_index += 1
        self._fc_is_flipped = False
        self._render_current_flashcard()

    def _fc_mark_unlearned(self):
        if self._flashcard_list and self._fc_index < len(self._flashcard_list):
            item = self._flashcard_list[self._fc_index]
            self.service.record_practice(item["id"], is_correct=False)
            self.refresh_stats()

        self._fc_index += 1
        self._fc_is_flipped = False
        self._render_current_flashcard()

    # =================================================================
    # 5. TAB: SO'Z JUFTLASH (MATCH GAME)
    # =================================================================

    def _build_match_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(40, 20, 40, 20)
        lay.setSpacing(16)

        # Header
        top_box = QHBoxLayout()
        self.match_info_lbl = QLabel("Mos juftliklarni toping (V1 <---> V2/V3):")
        self.match_info_lbl.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        top_box.addWidget(self.match_info_lbl)

        top_box.addStretch()

        self.match_timer_lbl = QLabel("⏱️ Vaqt: 0s")
        self.match_timer_lbl.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 15px;")
        top_box.addWidget(self.match_timer_lbl)

        restart_btn = QPushButton("🔄 Yangi O'yin")
        restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        restart_btn.clicked.connect(self.start_match_game)
        top_box.addWidget(restart_btn)

        lay.addLayout(top_box)

        # Grid (3x4 = 12 cards)
        self.match_grid = QGridLayout()
        self.match_grid.setSpacing(12)
        lay.addLayout(self.match_grid)

        # Feedback
        self.match_feedback_lbl = QLabel("")
        self.match_feedback_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        lay.addWidget(self.match_feedback_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        lay.addStretch()
        return page

    def start_match_game(self):
        # Tozalash
        while self.match_grid.count():
            item = self.match_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._match_cards = self.service.generate_match_game(pair_count=6)
        self._match_first_selected = None
        self._match_start_time = time.time()
        self.match_feedback_lbl.setText("")

        if self._match_timer:
            self._match_timer.stop()
        self._match_timer = QTimer(self)
        self._match_timer.timeout.connect(self._update_match_timer)
        self._match_timer.start(1000)

        for i, card_data in enumerate(self._match_cards):
            btn = QPushButton()
            btn.setFixedSize(220, 75)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            card_lay = QVBoxLayout(btn)
            card_lay.setContentsMargins(8, 6, 8, 6)
            card_lay.setSpacing(2)

            t_lbl = QLabel(card_data["text"])
            t_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
            s_lbl = QLabel(card_data["subtext"])
            s_lbl.setStyleSheet("font-size: 11px; color: #9CA3AF;")

            card_lay.addWidget(t_lbl, 0, Qt.AlignmentFlag.AlignCenter)
            card_lay.addWidget(s_lbl, 0, Qt.AlignmentFlag.AlignCenter)

            btn.setStyleSheet(self._match_card_style("normal"))
            btn.clicked.connect(lambda ch, idx=i, b=btn: self._on_match_card_clicked(idx, b))

            card_data["button"] = btn
            card_data["is_matched"] = False

            row = i // 4
            col = i % 4
            self.match_grid.addWidget(btn, row, col)

    def _update_match_timer(self):
        elapsed = int(time.time() - self._match_start_time)
        self.match_timer_lbl.setText(f"⏱️ Vaqt: {elapsed}s")

    def _on_match_card_clicked(self, idx: int, btn: QPushButton):
        card = self._match_cards[idx]
        if card["is_matched"]:
            return

        if self._match_first_selected is None:
            self._match_first_selected = (idx, card, btn)
            btn.setStyleSheet(self._match_card_style("selected"))
            speak_verb_form(card["raw_verb"]["v1"])
        else:
            first_idx, first_card, first_btn = self._match_first_selected
            if first_idx == idx:
                return

            if first_card["pair_id"] == card["pair_id"]:
                # To'g'ri juftlik (Match!)
                first_btn.setStyleSheet(self._match_card_style("matched"))
                btn.setStyleSheet(self._match_card_style("matched"))
                first_card["is_matched"] = True
                card["is_matched"] = True
                first_btn.setEnabled(False)
                btn.setEnabled(False)
                self._match_first_selected = None

                self.service.record_practice(card["pair_id"], is_correct=True)
                self.refresh_stats()

                # Barcha kartochkalar tugaganligini tekshirish
                if all(c["is_matched"] for c in self._match_cards):
                    if self._match_timer:
                        self._match_timer.stop()
                    elapsed = int(time.time() - self._match_start_time)
                    self.match_feedback_lbl.setText(f"🏆 G'alaba! Barcha juftliklarni {elapsed} soniyada topdingiz!")
                    self.match_feedback_lbl.setStyleSheet("color: #10B981; font-size: 18px; font-weight: bold;")
            else:
                # Noto'g'ri juftlik
                btn.setStyleSheet(self._match_card_style("wrong"))
                first_btn.setStyleSheet(self._match_card_style("wrong"))
                self._match_first_selected = None
                QTimer.singleShot(600, lambda: self._reset_unmatched_styles(first_btn, btn))

    def _reset_unmatched_styles(self, btn1: QPushButton, btn2: QPushButton):
        btn1.setStyleSheet(self._match_card_style("normal"))
        btn2.setStyleSheet(self._match_card_style("normal"))

    def _match_card_style(self, state: str) -> str:
        if state == "selected":
            return """
                QPushButton {
                    background-color: #312E81;
                    border: 2px solid #6366F1;
                    border-radius: 10px;
                }
            """
        elif state == "matched":
            return """
                QPushButton {
                    background-color: #064E3B;
                    border: 2px solid #10B981;
                    border-radius: 10px;
                    opacity: 0.6;
                }
            """
        elif state == "wrong":
            return """
                QPushButton {
                    background-color: #7F1D1D;
                    border: 2px solid #EF4444;
                    border-radius: 10px;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #1E1E2E;
                    border: 1px solid #374151;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #28283D;
                    border-color: #4F46E5;
                }
            """

    # =================================================================
    # 6. TAB: HARFLARDAN YIG'ISH (LETTER SCRAMBLE)
    # =================================================================

    def _build_scramble_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(60, 20, 60, 20)
        lay.setSpacing(20)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1E1E2E;
                border: 1px solid #312E81;
                border-radius: 16px;
                padding: 24px;
            }
        """)
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(16)
        c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scramble_task_lbl = QLabel("V2 (Past Simple) shaklini harflardan yig'ing:")
        self.scramble_task_lbl.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        c_lay.addWidget(self.scramble_task_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        self.scramble_v1_lbl = QLabel("begin")
        self.scramble_v1_lbl.setStyleSheet("font-size: 32px; font-weight: 800; color: #818CF8;")
        c_lay.addWidget(self.scramble_v1_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        self.scramble_trans_lbl = QLabel("boshlamoq")
        self.scramble_trans_lbl.setStyleSheet("font-size: 16px; font-style: italic; color: #D1D5DB;")
        c_lay.addWidget(self.scramble_trans_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Foydalanuvchi yig'ayotgan so'z qatori
        self.scramble_display_lbl = QLabel("_____")
        self.scramble_display_lbl.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 800;
                letter-spacing: 6px;
                color: #F59E0B;
                background-color: #171724;
                border: 2px dashed #4F46E5;
                border-radius: 10px;
                padding: 10px 24px;
            }
        """)
        c_lay.addWidget(self.scramble_display_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Harf tugmalari konteyneri
        self.scramble_buttons_layout = QHBoxLayout()
        self.scramble_buttons_layout.setSpacing(10)
        self.scramble_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.addLayout(self.scramble_buttons_layout)

        # Boshqaruv: Orqaga / Tozalash
        ctrl_box = QHBoxLayout()
        ctrl_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_box.setSpacing(12)

        back_btn = QPushButton("⌫ O'chirish")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        back_btn.clicked.connect(self._scramble_backspace)
        ctrl_box.addWidget(back_btn)

        clear_btn = QPushButton("🔄 Tozalash")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                color: #9CA3AF;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #374151;
            }
        """)
        clear_btn.clicked.connect(self._scramble_clear)
        ctrl_box.addWidget(clear_btn)

        c_lay.addLayout(ctrl_box)
        lay.addWidget(card)

        # Natija va Keyingi
        res_box = QHBoxLayout()
        self.scramble_feedback_lbl = QLabel("")
        self.scramble_feedback_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        res_box.addWidget(self.scramble_feedback_lbl)

        res_box.addStretch()

        self.scramble_next_btn = QPushButton("Keyingi So'z ➔")
        self.scramble_next_btn.setFixedHeight(42)
        self.scramble_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scramble_next_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
        """)
        self.scramble_next_btn.clicked.connect(self.load_next_scramble)
        res_box.addWidget(self.scramble_next_btn)

        lay.addLayout(res_box)
        lay.addStretch()
        return page

    def load_next_scramble(self):
        s = self.service.generate_scramble_game()
        if not s:
            return

        self._scramble_state = s
        self._scramble_current_assembled = []
        self.scramble_task_lbl.setText(f"Ushbu fe'lning {s['form_label']} shaklini yig'ing:")
        self.scramble_v1_lbl.setText(s["v1"])
        self.scramble_trans_lbl.setText(f"({s['translation']})")
        self.scramble_feedback_lbl.setText("")
        self._update_scramble_display()

        # Harf tugmalarini joylashtirish
        while self.scramble_buttons_layout.count():
            item = self.scramble_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, char in enumerate(s["letters"]):
            btn = QPushButton(char.upper())
            btn.setFixedSize(50, 50)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2D3748;
                    color: #FFFFFF;
                    font-size: 20px;
                    font-weight: 800;
                    border: 2px solid #4F46E5;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #4F46E5;
                }
                QPushButton:disabled {
                    background-color: #171724;
                    color: #4B5563;
                    border-color: #2A2A3C;
                }
            """)
            btn.clicked.connect(lambda ch, b=btn, c=char: self._on_scramble_letter_clicked(b, c))
            self.scramble_buttons_layout.addWidget(btn)

    def _on_scramble_letter_clicked(self, btn: QPushButton, char: str):
        btn.setEnabled(False)
        self._scramble_current_assembled.append((char, btn))
        self._update_scramble_display()

        target = self._scramble_state["target_word"].lower()
        assembled = "".join(c for c, _ in self._scramble_current_assembled).lower()

        if len(assembled) == len(target):
            if assembled == target:
                self.scramble_feedback_lbl.setText(f"🎉 To'g'ri! {target.upper()}")
                self.scramble_feedback_lbl.setStyleSheet("color: #10B981; font-size: 18px; font-weight: bold;")
                self.service.record_practice(self._scramble_state["verb"]["id"], is_correct=True)
                self.refresh_stats()
                speak_verb_form(target)
            else:
                self.scramble_feedback_lbl.setText(f"❌ Xato! To'g'ri so'z: {target.upper()}")
                self.scramble_feedback_lbl.setStyleSheet("color: #EF4444; font-size: 16px; font-weight: bold;")
                self.service.record_practice(self._scramble_state["verb"]["id"], is_correct=False)
                self.refresh_stats()

    def _scramble_backspace(self):
        if self._scramble_current_assembled:
            char, btn = self._scramble_current_assembled.pop()
            btn.setEnabled(True)
            self._update_scramble_display()

    def _scramble_clear(self):
        while self._scramble_current_assembled:
            char, btn = self._scramble_current_assembled.pop()
            btn.setEnabled(True)
        self._update_scramble_display()
        self.scramble_feedback_lbl.setText("")

    def _update_scramble_display(self):
        text = "".join(c for c, _ in self._scramble_current_assembled).upper()
        if not text:
            text = "_____"
        self.scramble_display_lbl.setText(text)

    # =================================================================
    # VIZUAL MAVZU (THEMING)
    # =================================================================

    def apply_theme(self, theme):
        """Mavzu o'zgarganda barcha elementlarni moslashtirish."""
        is_dark = theme.is_dark

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme.bg_app};
                color: {theme.text_main};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QTableWidget {{
                background-color: {theme.bg_card};
                alternate-background-color: {theme.bg_card_secondary};
                border: 1px solid {theme.border};
                border-radius: 12px;
                gridline-color: transparent;
                selection-background-color: {theme.primary}44;
            }}
            QHeaderView::section {{
                background-color: {theme.bg_sidebar};
                color: {theme.text_muted};
                font-weight: bold;
                font-size: 12px;
                padding: 10px;
                border: none;
                border-bottom: 2px solid {theme.border};
            }}
            QLineEdit {{
                background-color: {theme.bg_card_secondary};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 6px 12px;
                color: {theme.text_main};
            }}
            QLineEdit:focus {{
                border-color: {theme.primary};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.border};
                min-height: 28px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {theme.primary};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 0px 2px 0px 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {theme.border};
                min-width: 28px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {theme.primary};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)

        # Nav bar pill button style
        for btn, _ in self.tab_buttons:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.bg_card};
                    border: 1px solid {theme.border};
                    border-radius: 18px;
                    padding: 8px 16px;
                    color: {theme.text_muted};
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {theme.bg_card_secondary};
                    color: {theme.text_main};
                }}
                QPushButton:checked {{
                    background-color: {theme.primary};
                    border-color: {theme.primary};
                    color: #FFFFFF;
                }}
            """)

    def keyPressEvent(self, event):
        """Flashcard sahifasida (index == 3) tezkor klaviatura qisqa tugmalari."""
        if self.stack.currentIndex() == 3:
            key = event.key()
            if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._flip_flashcard()
                return
            elif key == Qt.Key.Key_Left:
                self._fc_mark_unlearned()
                return
            elif key == Qt.Key.Key_Right:
                self._fc_mark_learned()
                return
            elif key in (Qt.Key.Key_A, Qt.Key.Key_Up):
                self._fc_play_audio()
                return
        super().keyPressEvent(event)
