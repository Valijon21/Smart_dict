from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QMessageBox,
    QFileDialog, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QCursor

import database as db
import tts
import theme_manager
import phonetics
from logger import get_logger

from ui.word_packs_dialog import WordPacksDialog

logger = get_logger("dictionary")


class EditWordDialog(QDialog):
    """So'zni tahrirlash uchun zamonaviy modal oyna."""
    def __init__(self, parent, word_id: int, english: str, uzbek: str, example: str = ""):
        super().__init__(parent)
        self.word_id = word_id
        self.setWindowTitle("So'zni tahrirlash")
        self.setFixedWidth(460)
        self.setStyleSheet("background-color: #1E1E2E; color: white; border-radius: 12px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("✏️ So'zni tahrirlash")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: white;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Inglizcha so'z:"))
        self.eng_input = QLineEdit(english)
        self.eng_input.setStyleSheet(
            "background-color: #151521; color: white; border: 1px solid #2A2A3C;"
            "border-radius: 8px; padding: 10px 12px; font-size: 14px;"
        )
        layout.addWidget(self.eng_input)

        layout.addWidget(QLabel("O'zbekcha tarjima:"))
        self.uz_input = QLineEdit(uzbek)
        self.uz_input.setStyleSheet(
            "background-color: #151521; color: white; border: 1px solid #2A2A3C;"
            "border-radius: 8px; padding: 10px 12px; font-size: 14px;"
        )
        layout.addWidget(self.uz_input)

        layout.addWidget(QLabel("Misol gap (ixtiyoriy):"))
        self.ex_input = QLineEdit(example or "")
        self.ex_input.setPlaceholderText("Masalan: She achieved great results.")
        self.ex_input.setStyleSheet(
            "background-color: #151521; color: white; border: 1px solid #2A2A3C;"
            "border-radius: 8px; padding: 10px 12px; font-size: 13px;"
        )
        layout.addWidget(self.ex_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Bekor qilish")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "QPushButton { background-color: #2E2E3E; color: #9CA3AF; border: 1px solid #374151;"
            "border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background-color: #374151; color: white; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Saqlash")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border: none;"
            "border-radius: 8px; padding: 9px 22px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        save_btn.clicked.connect(self.save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def save(self):
        eng = self.eng_input.text().strip()
        uz = self.uz_input.text().strip()
        ex = self.ex_input.text().strip()
        if not eng or not uz:
            QMessageBox.warning(self, "Xatolik", "Iltimos, har ikkala maydonni to'ldiring.")
            return
        success = db.update_word(self.word_id, eng, uz, ex)
        if success:
            logger.info(f"Modal orqali so'z saqlandi: ID={self.word_id}, '{eng}' -> '{uz}'")
            self.accept()
        else:
            QMessageBox.warning(self, "Xatolik", "Ushbu inglizcha so'z allaqachon bazada mavjud.")


def _make_badge(text: str, bg_color: str, text_color: str, border_color: str = None) -> QWidget:
    """Jadval kataklari uchun professional yumaloq chip (badge) vidjeti."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lbl = QLabel(text)
    border_css = f"border: 1px solid {border_color};" if border_color else "border: none;"
    lbl.setStyleSheet(
        f"background-color: {bg_color}; color: {text_color}; {border_css}"
        f"border-radius: 11px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
    )
    lay.addWidget(lbl)
    return w


class DictionaryWidget(QWidget):
    def __init__(self, on_words_changed=None):
        super().__init__()
        self.on_words_changed = on_words_changed
        self.current_filter = "all"
        self.hard_only = False
        self._current_rows_data = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        # --- 1. Header va Eksport tugmalari ---
        top_row = QHBoxLayout()
        header = QLabel("📖 Lug'at va so'zlar bazasi")
        header.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        top_row.addWidget(header)
        top_row.addStretch()

        export_csv_btn = QPushButton("📥 CSV Eksport")
        export_csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_csv_btn.setStyleSheet(
            "QPushButton { background-color: #1E1E2E; color: #10B981; border: 1px solid #10B981;"
            "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #064E3B; color: white; }"
        )
        export_csv_btn.clicked.connect(self.export_csv)
        top_row.addWidget(export_csv_btn)

        export_json_btn = QPushButton("📥 JSON Eksport")
        export_json_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_json_btn.setStyleSheet(
            "QPushButton { background-color: #1E1E2E; color: #818CF8; border: 1px solid #6366F1;"
            "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #312E81; color: white; }"
        )
        export_json_btn.clicked.connect(self.export_json)
        top_row.addWidget(export_json_btn)

        packs_btn = QPushButton("📚 Tayyor to'plamlar (Word Packs)")
        packs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        packs_btn.setStyleSheet(
            "QPushButton { background-color: #4338CA; color: white; border: 1px solid #6366F1;"
            "border-radius: 8px; padding: 7px 16px; font-size: 12px; font-weight: 700; }"
            "QPushButton:hover { background-color: #4F46E5; border-color: #A5B4FC; }"
        )
        packs_btn.clicked.connect(self.open_word_packs)
        top_row.addWidget(packs_btn)

        layout.addLayout(top_row)

        # --- 2. Qidiruv va Filtrlar paneli ---
        self.filter_frame = QFrame()
        self.filter_frame.setStyleSheet("background-color: #1E1E2E; border-radius: 12px; border: 1px solid #2A2A3C;")
        filter_layout = QHBoxLayout(self.filter_frame)
        filter_layout.setContentsMargins(14, 10, 14, 10)
        filter_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Inglizcha yoki o'zbekcha so'zni qidiring...")
        self.search_input.setStyleSheet(
            "background-color: #151521; color: white; border: 1px solid #2A2A3C;"
            "border-radius: 8px; padding: 9px 14px; font-size: 13px;"
        )
        # Ravon qidiruv uchun 160ms debounce taymeri
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(160)
        self._search_timer.timeout.connect(self.load_words)
        self.search_input.textChanged.connect(lambda: self._search_timer.start())
        filter_layout.addWidget(self.search_input, 2)

        # Filtr tugmalari
        self.filter_buttons = {}
        filters = [
            ("Barchasi", "all"),
            ("Yangi", "new"),
            ("O'rganilmoqda", "learning"),
            ("O'zlashtirilgan", "mastered"),
            ("🔥 Qiyin so'zlar", "hard"),
        ]

        btn_group = QHBoxLayout()
        btn_group.setSpacing(8)
        for label, f_key in filters:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._filter_btn_style(f_key == "all"))
            btn.clicked.connect(lambda checked, k=f_key: self.set_filter(k))
            btn_group.addWidget(btn)
            self.filter_buttons[f_key] = btn

        filter_layout.addLayout(btn_group)
        layout.addWidget(self.filter_frame)

        # --- 3. Jadval (QTableWidget) ---
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Inglizcha (Talaffuz)", "O'zbekcha tarjima", "Daraja (Box)", "Holat", "Amallar"
        ])

        # Ustunlar kengligini professional nisbatda taqsimlash
        self.table.setColumnWidth(0, 55)   # ID
        self.table.setColumnWidth(3, 115)  # Box
        self.table.setColumnWidth(4, 135)  # Status
        self.table.setColumnWidth(5, 110)  # Amallar (Amallar tor, ortiqcha cho'zilmaydi)

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Inglizcha kengayadi
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # O'zbekcha kengayadi
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header_view.setStretchLastSection(False)  # Oxirgi ustun cho'zilib ketmasligi uchun

        # Qator balandligi (Keng va qulay 48px)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)

        # Qator tanlash va ranglar
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)

        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #151521;
                alternate-background-color: #181829;
                color: #E5E7EB;
                gridline-color: #232338;
                border: 1px solid #232338;
                border-radius: 12px;
                font-size: 13px;
                selection-background-color: #262642;
                selection-color: #FFFFFF;
                outline: none;
            }
            QTableWidget::item {
                padding-left: 8px;
                padding-right: 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #262642;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #1B1B2A;
                color: #9CA3AF;
                font-size: 12px;
                font-weight: 700;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #2A2A3E;
            }
            """
        )
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        layout.addWidget(self.table)

        # --- 4. Footer ---
        footer = QHBoxLayout()
        self.count_label = QLabel("Jami so'zlar: 0")
        self.count_label.setStyleSheet("color: #9CA3AF; font-size: 13px; font-weight: 500;")
        footer.addWidget(self.count_label)
        footer.addStretch()

        hint_label = QLabel("💡 Maslahat: Har bir so'z oldidagi 🔊 karnay tugmasini bosib, darhol talaffuzini eshiting!")
        hint_label.setStyleSheet("color: #818CF8; font-size: 12px;")
        footer.addWidget(hint_label)

        layout.addLayout(footer)

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        self.load_words()

    def _filter_btn_style(self, active: bool) -> str:
        t = theme_manager.get_active_theme()
        if active:
            return (
                f"QPushButton {{ background-color: {t.primary}; color: white; border: none;"
                f"border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }}"
            )
        return (
            f"QPushButton {{ background-color: {t.bg_sidebar}; color: {t.text_muted}; border: 1px solid {t.border};"
            f"border-radius: 8px; padding: 7px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card}; color: {t.text_main}; border-color: {t.primary}; }}"
        )

    def apply_theme(self, t: theme_manager.Theme):
        if hasattr(self, "filter_frame"):
            self.filter_frame.setStyleSheet(
                f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};"
            )
        if hasattr(self, "search_input"):
            self.search_input.setStyleSheet(
                f"background-color: {t.bg_sidebar}; color: {t.text_main}; border: 1px solid {t.border};"
                f"border-radius: 8px; padding: 9px 14px; font-size: 13px;"
            )
        if hasattr(self, "table"):
            self.table.setStyleSheet(
                f"""
                QTableWidget {{
                    background-color: {t.bg_sidebar};
                    alternate-background-color: {t.bg_card_secondary};
                    color: {t.text_main};
                    gridline-color: {t.border};
                    border: 1px solid {t.border};
                    border-radius: 12px;
                    font-size: 13px;
                    selection-background-color: {t.bg_card};
                    selection-color: #FFFFFF;
                    outline: none;
                }}
                QTableWidget::item {{
                    padding-left: 8px;
                    padding-right: 8px;
                    border: none;
                }}
                QTableWidget::item:selected {{
                    background-color: {t.bg_card};
                    color: #FFFFFF;
                }}
                QHeaderView::section {{
                    background-color: {t.bg_card};
                    color: {t.text_muted};
                    font-size: 12px;
                    font-weight: 700;
                    padding: 10px 8px;
                    border: none;
                    border-bottom: 2px solid {t.border};
                }}
                """
            )
        for k, btn in getattr(self, "filter_buttons", {}).items():
            btn.setStyleSheet(self._filter_btn_style(k == getattr(self, "current_filter", "all")))

    def set_filter(self, filter_key: str):
        self.current_filter = filter_key
        logger.debug(f"Lug'at filtri tanlandi: {filter_key}")
        for k, btn in self.filter_buttons.items():
            btn.setChecked(k == filter_key)
            btn.setStyleSheet(self._filter_btn_style(k == filter_key))
        self.load_words()

    def load_words(self):
        query = self.search_input.text()
        status = None if self.current_filter in ("all", "hard") else self.current_filter
        hard_only = (self.current_filter == "hard")

        rows = db.search_words(query=query, status_filter=status, hard_only=hard_only)
        self._current_rows_data = rows
        self.table.setRowCount(len(rows))

        # Leitner Box ranglari (zamonaviy chip palitrasi)
        box_badges = {
            0: ("Box 0", "#1F2937", "#9CA3AF", "#374151"),
            1: ("Box 1", "#1E2A4A", "#60A5FA", "#2563EB"),
            2: ("Box 2", "#281D4A", "#A78BFA", "#7C3AED"),
            3: ("Box 3", "#33220A", "#FBBF24", "#D97706"),
            4: ("Box 4", "#0D3322", "#34D399", "#059669"),
            5: ("Box 5", "#083328", "#2DD4BF", "#0D9488"),
        }

        # Status chiplari
        status_badges = {
            "new": ("Yangi", "#1E293B", "#38BDF8", "#0284C7"),
            "learning": ("O'rganilmoqda", "#2E1A0F", "#FB923C", "#C2410C"),
            "mastered": ("O'zlashtirilgan", "#062E1F", "#34D399", "#059669"),
        }

        for i, row in enumerate(rows):
            # 0: ID
            id_item = QTableWidgetItem(str(row["id"]))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setForeground(QColor("#6B7280"))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, id_item)

            # 1: English (Karnay tugmasi va so'z)
            eng_cell = QWidget()
            eng_lay = QHBoxLayout(eng_cell)
            eng_lay.setContentsMargins(10, 4, 10, 4)
            eng_lay.setSpacing(10)

            audio_btn = QPushButton("🔊")
            audio_btn.setToolTip("Talaffuzni eshitish (Inglizcha)")
            audio_btn.setFixedSize(34, 32)
            audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            audio_btn.setStyleSheet(
                "QPushButton { background-color: #202038; color: #818CF8; border: 1px solid #3730A3;"
                "border-radius: 6px; font-size: 14px; }"
                "QPushButton:hover { background-color: #4F46E5; color: white; border-color: #818CF8; }"
            )
            eng_word = row["english"]
            audio_btn.clicked.connect(lambda checked, w=eng_word, b=audio_btn: self.play_word_audio(w, b))
            eng_lay.addWidget(audio_btn)

            eng_box = QVBoxLayout()
            eng_box.setSpacing(1)
            eng_box.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            eng_label = QLabel(eng_word)
            eng_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")
            eng_box.addWidget(eng_label)

            ph_info = phonetics.get_word_info(eng_word)
            ph_val = row["phonetic"] if "phonetic" in row.keys() and row["phonetic"] else ph_info["phonetic"]
            pos_val = row["part_of_speech"] if "part_of_speech" in row.keys() and row["part_of_speech"] else ph_info["part_of_speech"]

            sub_lbl = QLabel(
                f"<span style='color: #A5B4FC; font-size: 11px;'>{ph_val}</span>  "
                f"<span style='background-color: #312E81; color: #C7D2FE; font-size: 10px; font-weight: 700; border-radius: 3px; padding: 1px 4px;'>[{pos_val}]</span>"
            )
            eng_box.addWidget(sub_lbl)
            eng_lay.addLayout(eng_box)
            eng_lay.addStretch()

            self.table.setCellWidget(i, 1, eng_cell)

            # 2: Uzbek tarjimasi va misol gap
            uz_cell = QWidget()
            uz_lay = QVBoxLayout(uz_cell)
            uz_lay.setContentsMargins(10, 4, 10, 4)
            uz_lay.setSpacing(2)
            uz_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            uz_label = QLabel(row["uzbek"])
            uz_label.setStyleSheet("color: #E5E7EB; font-size: 13px; font-weight: 500;")
            uz_lay.addWidget(uz_label)

            ex = row["example"] if "example" in row.keys() and row["example"] else ""
            if ex:
                ex_label = QLabel(f"💡 {ex}")
                ex_label.setStyleSheet("color: #818CF8; font-size: 11px; font-style: italic;")
                uz_lay.addWidget(ex_label)
                uz_cell.setToolTip(f"Misol: {ex}")

            self.table.setCellWidget(i, 2, uz_cell)

            # 3: Leitner Box chipi
            box = row["box_level"] or 0
            b_text, b_bg, b_fg, b_border = box_badges.get(box, (f"Box {box}", "#1F2937", "#9CA3AF", "#374151"))
            self.table.setCellWidget(i, 3, _make_badge(b_text, b_bg, b_fg, b_border))

            # 4: Status chipi
            st = row["status"] or "new"
            s_text, s_bg, s_fg, s_border = status_badges.get(st, (st, "#1E293B", "#38BDF8", "#0284C7"))
            self.table.setCellWidget(i, 4, _make_badge(s_text, s_bg, s_fg, s_border))

            # 5: Amallar (Tahrirlash va O'chirish tugmalari markazda)
            act_cell = QWidget()
            act_lay = QHBoxLayout(act_cell)
            act_lay.setContentsMargins(4, 4, 4, 4)
            act_lay.setSpacing(8)
            act_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("So'zni tahrirlash")
            edit_btn.setFixedSize(32, 32)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setStyleSheet(
                "QPushButton { background-color: #242044; color: #A5B4FC; border: 1px solid #3F377A;"
                "border-radius: 6px; font-size: 14px; }"
                "QPushButton:hover { background-color: #4F46E5; color: white; border-color: #818CF8; }"
            )
            ex_val = row["example"] if "example" in row.keys() and row["example"] else ""
            edit_btn.clicked.connect(
                lambda checked, w_id=row["id"], e=row["english"], u=row["uzbek"], ex=ex_val: self.edit_word(w_id, e, u, ex)
            )

            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("So'zni o'chirish")
            del_btn.setFixedSize(32, 32)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(
                "QPushButton { background-color: #381A1A; color: #F87171; border: 1px solid #6B1D1D;"
                "border-radius: 6px; font-size: 14px; }"
                "QPushButton:hover { background-color: #DC2626; color: white; border-color: #EF4444; }"
            )
            del_btn.clicked.connect(
                lambda checked, w_id=row["id"], e=row["english"]: self.delete_word(w_id, e)
            )

            act_lay.addWidget(edit_btn)
            act_lay.addWidget(del_btn)

            self.table.setCellWidget(i, 5, act_cell)

        self.count_label.setText(f"Ko'rsatilmoqda: {len(rows)} ta so'z")

    def play_word_audio(self, text: str, button: QPushButton = None):
        """Karnay bosilganda ovoz chiqarish va chiroyli animatsiya berish."""
        if not text:
            return

        logger.info(f"Lug'at jadvalida karnay bosildi: '{text}'")

        if button:
            original_style = button.styleSheet()
            button.setText("🔈")
            button.setStyleSheet(
                "QPushButton { background-color: #4F46E5; color: white; border: 1px solid #818CF8;"
                "border-radius: 6px; font-size: 14px; }"
            )
            QTimer.singleShot(350, lambda: self._revert_audio_btn(button, original_style))

        tts.speak(text)

    def _revert_audio_btn(self, button: QPushButton, original_style: str):
        try:
            button.setText("🔊")
            button.setStyleSheet(original_style)
        except RuntimeError:
            pass

    def on_cell_clicked(self, row: int, column: int):
        """Katakka 1 marta bosilganda audio ishlashi."""
        if column == 1 and row < len(self._current_rows_data):
            word_row = self._current_rows_data[row]
            self.play_word_audio(word_row["english"])

    def on_cell_double_clicked(self, row: int, column: int):
        if 0 <= row < len(self._current_rows_data):
            word_row = self._current_rows_data[row]
            if column == 1:
                self.play_word_audio(word_row["english"])
            else:
                ex = word_row["example"] if "example" in word_row.keys() and word_row["example"] else ""
                self.edit_word(word_row["id"], word_row["english"], word_row["uzbek"], ex)

    def edit_word(self, word_id: int, english: str, uzbek: str, example: str = ""):
        logger.info(f"So'zni tahrirlash oynasi ochildi: ID={word_id} ('{english}')")
        dlg = EditWordDialog(self, word_id, english, uzbek, example)
        if dlg.exec():
            self.load_words()
            if self.on_words_changed:
                self.on_words_changed()

    def open_word_packs(self):
        """Tayyor so'z to'plamlari modalini ochish."""
        logger.info("Tayyor so'z to'plamlari oynasi ochildi.")
        parent_main = self.window()
        practice_cb = getattr(parent_main, "start_custom_practice", None)
        dlg = WordPacksDialog(self, on_words_imported=self.load_words, on_start_practice=practice_cb)
        dlg.exec()
        self.load_words()
        if self.on_words_changed:
            self.on_words_changed()

    def delete_word(self, word_id: int, english: str):
        reply = QMessageBox.question(
            self,
            "O'chirishni tasdiqlang",
            f"Haqiqatan ham '{english}' so'zini bazadan butunlay o'chirmoqchimisiz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"Foydalanuvchi so'zni o'chirishni tasdiqladi: ID={word_id}, '{english}'")
            db.delete_word(word_id)
            self.load_words()
            if self.on_words_changed:
                self.on_words_changed()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Lug'atni CSV formatida saqlash", "vocab_export.csv", "CSV fayllar (*.csv)"
        )
        if path:
            count = db.export_to_csv(path)
            logger.info(f"Lug'at CSV faylga saqlandi ({count} ta so'z): {path}")
            QMessageBox.information(self, "Muvaffaqiyatli", f"{count} ta so'z muvaffaqiyatli CSV faylga saqlandi!")

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Lug'atni JSON formatida saqlash", "vocab_export.json", "JSON fayllar (*.json)"
        )
        if path:
            count = db.export_to_json(path)
            logger.info(f"Lug'at JSON faylga saqlandi ({count} ta so'z): {path}")
            QMessageBox.information(self, "Muvaffaqiyatli", f"{count} ta so'z muvaffaqiyatli JSON faylga saqlandi!")
