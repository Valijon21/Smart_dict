"""
Vocab Master Pro — Intellektual so'z import qilish va tahlil oynasi (Smart Importer).
Fayllar (.txt, .docx, .xlsx, .csv, .pdf) va nusxalangan matndan so'zlarni aqlli ajratadi,
interaktiv jadvalda ko'rsatadi, tahrirlash imkonini beradi va darhol mashqlarga yo'naltiradi.
"""
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QTextEdit, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QStackedLayout, QMessageBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor

try:
    from core import database as db
except ImportError:
    import database as db

try:
    from utils import importer
except ImportError:
    import importer

try:
    from ui import theme_manager
except ImportError:
    import theme_manager

try:
    from utils.logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger("import")


class DropZoneFrame(QFrame):
    """Faylni sudrab tashlash (Drag & Drop) zonasi."""
    def __init__(self, on_file_dropped, on_click_browse, parent=None):
        super().__init__(parent)
        self.on_file_dropped = on_file_dropped
        self.on_click_browse = on_click_browse
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._is_hovered = False

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._is_hovered = True
            self.update_style()

    def dragLeaveEvent(self, event):
        self._is_hovered = False
        self.update_style()

    def dropEvent(self, event: QDropEvent):
        self._is_hovered = False
        self.update_style()
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.on_file_dropped(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click_browse()

    def update_style(self, t=None):
        if not t:
            t = theme_manager.get_active_theme()
        border_color = t.primary if self._is_hovered else t.border
        bg_color = t.bg_card_secondary if self._is_hovered else t.bg_card
        self.setStyleSheet(
            f"DropZoneFrame {{ background-color: {bg_color}; border: 2px dashed {border_color}; "
            f"border-radius: 12px; padding: 20px; }}"
        )


class ImportWidget(QWidget):
    def __init__(self, on_words_changed=None, on_start_practice=None):
        super().__init__()
        self.on_words_changed = on_words_changed
        self.on_start_practice = on_start_practice
        self.last_added_ids: list[int] = []
        self._parsed_pairs: list[tuple] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(14)

        # 1. Sarlavha paneli
        header_row = QHBoxLayout()
        v_head = QVBoxLayout()
        self.title_lbl = QLabel("📥 So'zlarni import qilish va tahlil (Smart Importer)")
        self.title_lbl.setStyleSheet("color: white; font-size: 20px; font-weight: 700;")
        v_head.addWidget(self.title_lbl)

        self.desc_lbl = QLabel(
            "Fayldan (.txt, .docx, .xlsx, .csv, .pdf) yoki matn nusxasidan so'zlarni avtomatik ajratib oling, "
            "jadvalda tekshiring va darhol mashq qiling."
        )
        self.desc_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        self.desc_lbl.setWordWrap(True)
        v_head.addWidget(self.desc_lbl)
        header_row.addLayout(v_head, 1)

        # Word Packs tugmasi
        self.packs_btn = QPushButton("📚 Tayyor To'plamlar (Word Packs)")
        self.packs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.packs_btn.setStyleSheet(
            "QPushButton { background-color: #312E81; color: #C7D2FE; border: 1px solid #4338CA;"
            "border-radius: 8px; padding: 10px 16px; font-weight: 600; font-size: 13px; }"
            "QPushButton:hover { background-color: #4338CA; color: white; }"
        )
        self.packs_btn.clicked.connect(self.open_word_packs)
        header_row.addWidget(self.packs_btn)
        main_layout.addLayout(header_row)

        # 2. Rejim tanlash (Tabs / Segmented Bar)
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)

        self.tab_btn_file = QPushButton("📁 Fayl orqali (Drag & Drop)")
        self.tab_btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_btn_file.setCheckable(True)
        self.tab_btn_file.setChecked(True)
        self.tab_btn_file.clicked.connect(lambda: self.switch_mode("file"))
        tab_row.addWidget(self.tab_btn_file)

        self.tab_btn_paste = QPushButton("📋 Matn nusxasini qo'yish (Batch Paste)")
        self.tab_btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_btn_paste.setCheckable(True)
        self.tab_btn_paste.clicked.connect(lambda: self.switch_mode("paste"))
        tab_row.addWidget(self.tab_btn_paste)

        self.tab_btn_manual = QPushButton("✍️ Qo'lda bitta so'z qo'shish")
        self.tab_btn_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_btn_manual.setCheckable(True)
        self.tab_btn_manual.clicked.connect(lambda: self.switch_mode("manual"))
        tab_row.addWidget(self.tab_btn_manual)

        tab_row.addStretch()
        main_layout.addLayout(tab_row)

        # 3. Stacked Containers for modes
        self.mode_container = QFrame()
        self.mode_layout = QStackedLayout(self.mode_container)

        # Mode A: Fayl yuklash (Drag & Drop Zone)
        self.file_card = DropZoneFrame(self.on_file_selected, self.choose_file)
        file_card_layout = QVBoxLayout(self.file_card)
        file_card_layout.setContentsMargins(20, 16, 20, 16)
        file_card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_card_layout.setSpacing(8)

        self.drop_icon = QLabel("📁")
        self.drop_icon.setStyleSheet("font-size: 32px;")
        self.drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_card_layout.addWidget(self.drop_icon)

        self.drop_title = QLabel("Faylni shu yerga sudrab tashlang yoki kompyuterdan tanlang")
        self.drop_title.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
        self.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_card_layout.addWidget(self.drop_title)

        self.drop_formats = QLabel("Qo'llab-quvvatlanadi: .txt, .docx, .xlsx, .csv, .pdf (Jadvallar va matnlar)")
        self.drop_formats.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        self.drop_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_card_layout.addWidget(self.drop_formats)

        self.file_btn = QPushButton("📁 Fayl tanlash...")
        self.file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_btn.setStyleSheet(
            "background-color: #4F46E5; color: white; border-radius: 8px; padding: 8px 20px; "
            "font-weight: 600; font-size: 13px;"
        )
        self.file_btn.clicked.connect(self.choose_file)
        file_card_layout.addWidget(self.file_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.mode_layout.addWidget(self.file_card)

        # Mode B: Matn nusxasini qo'yish (Batch Paste)
        self.paste_card = QFrame()
        paste_layout = QVBoxLayout(self.paste_card)
        paste_layout.setContentsMargins(16, 12, 16, 12)
        paste_layout.setSpacing(8)

        paste_hint = QLabel("Nusxa olingan matnni (masalan Telegram, Word yoki saytdan) shu yerga joylashtiring:")
        paste_hint.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        paste_layout.addWidget(paste_hint)

        self.paste_edit = QTextEdit()
        self.paste_edit.setPlaceholderText(
            "Har qatorda so'z va tarjima (masalan):\n"
            "apple - olma\n"
            "check-in - ro'yxatdan o'tish\n"
            "abandon [ə'bændən] tark etmoq\n"
            "well-known : mashhur\n"
            "banana | banan\n"
            "1. book kitob"
        )
        self.paste_edit.setStyleSheet(
            "background-color: #151521; color: white; border: 1px solid #2A2A3C; "
            "border-radius: 8px; padding: 10px; font-size: 13px; font-family: monospace;"
        )
        self.paste_edit.setFixedHeight(120)
        paste_layout.addWidget(self.paste_edit)

        paste_btn_row = QHBoxLayout()
        self.paste_parse_btn = QPushButton("🔍 Tahlil qilish va Ajratish")
        self.paste_parse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_parse_btn.setStyleSheet(
            "background-color: #4F46E5; color: white; border-radius: 6px; padding: 8px 18px; font-weight: 600;"
        )
        self.paste_parse_btn.clicked.connect(self.parse_pasted_text)
        paste_btn_row.addWidget(self.paste_parse_btn)

        self.paste_clear_btn = QPushButton("🧹 Tozalash")
        self.paste_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_clear_btn.setStyleSheet(
            "background-color: #2A2A3C; color: #9CA3AF; border-radius: 6px; padding: 8px 14px;"
        )
        self.paste_clear_btn.clicked.connect(self.paste_edit.clear)
        paste_btn_row.addWidget(self.paste_clear_btn)
        paste_btn_row.addStretch()
        paste_layout.addLayout(paste_btn_row)

        self.mode_layout.addWidget(self.paste_card)

        # Mode C: Qo'lda bitta so'z qo'shish
        self.manual_frame = QFrame()
        manual_layout = QVBoxLayout(self.manual_frame)
        manual_layout.setContentsMargins(16, 12, 16, 12)
        manual_layout.setSpacing(8)

        manual_title = QLabel("Yangi so'z ma'lumotlarini kiriting:")
        manual_title.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
        manual_layout.addWidget(manual_title)

        input_row = QHBoxLayout()
        self.eng_input = QLineEdit()
        self.eng_input.setPlaceholderText("English so'z")
        self.uz_input = QLineEdit()
        self.uz_input.setPlaceholderText("O'zbekcha tarjima")
        self.ex_input = QLineEdit()
        self.ex_input.setPlaceholderText("Misol gap (ixtiyoriy)")
        self.eng_input.returnPressed.connect(self.add_manual)
        self.uz_input.returnPressed.connect(self.add_manual)
        self.ex_input.returnPressed.connect(self.add_manual)

        for w in (self.eng_input, self.uz_input, self.ex_input):
            w.setStyleSheet(
                "background-color: #151521; color: white; border: 1px solid #2A2A3C; "
                "border-radius: 6px; padding: 8px;"
            )

        self.manual_add_btn = QPushButton("Qo'shish")
        self.manual_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_add_btn.setStyleSheet(
            "background-color: #10B981; color: white; border-radius: 6px; padding: 8px 16px; font-weight: 600;"
        )
        self.manual_add_btn.clicked.connect(self.add_manual)

        input_row.addWidget(self.eng_input, 2)
        input_row.addWidget(self.uz_input, 2)
        input_row.addWidget(self.ex_input, 3)
        input_row.addWidget(self.manual_add_btn, 1)
        manual_layout.addLayout(input_row)

        self.mode_layout.addWidget(self.manual_frame)
        main_layout.addWidget(self.mode_container)

        # 4. Tahlil natijasi haqida xabar
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
        self.result_label.setWordWrap(True)
        main_layout.addWidget(self.result_label)

        # 5. Interaktiv Ko'rib Chiqish Jadvali (Preview Table Box)
        self.preview_box = QFrame()
        self.preview_box.setStyleSheet(
            "background-color: #151521; border: 1px solid #2A2A3C; border-radius: 12px;"
        )
        preview_layout = QVBoxLayout(self.preview_box)
        preview_layout.setContentsMargins(16, 12, 16, 12)
        preview_layout.setSpacing(10)

        prev_head_row = QHBoxLayout()
        self.prev_title = QLabel("🔍 Ajratilgan so'zlar jadvali:")
        self.prev_title.setStyleSheet("color: white; font-size: 14px; font-weight: 700;")
        prev_head_row.addWidget(self.prev_title)

        self.prev_stats = QLabel("")
        self.prev_stats.setStyleSheet("color: #60A5FA; font-size: 12px; font-weight: 600;")
        prev_head_row.addWidget(self.prev_stats)
        prev_head_row.addStretch()

        self.btn_del_row = QPushButton("🗑️ Qatorni o'chirish")
        self.btn_del_row.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_row.setStyleSheet(
            "background-color: #2A2A3C; color: #EF4444; border-radius: 6px; padding: 5px 10px; font-size: 11px;"
        )
        self.btn_del_row.clicked.connect(self.delete_selected_row)
        prev_head_row.addWidget(self.btn_del_row)

        self.btn_add_row = QPushButton("➕ Bo'sh qator")
        self.btn_add_row.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_row.setStyleSheet(
            "background-color: #2A2A3C; color: #10B981; border-radius: 6px; padding: 5px 10px; font-size: 11px;"
        )
        self.btn_add_row.clicked.connect(self.add_empty_row)
        prev_head_row.addWidget(self.btn_add_row)

        preview_layout.addLayout(prev_head_row)

        # Jadval
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["№", "Inglizcha so'z", "O'zbekcha tarjima", "Misol gap / Izoh", "Holati"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 220)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #1E1E2E; color: white; gridline-color: #2A2A3C; "
            "border: 1px solid #2A2A3C; border-radius: 8px; font-size: 13px; }"
            "QHeaderView::section { background-color: #151521; color: #9CA3AF; font-weight: 600; padding: 6px; border: none; }"
            "QTableWidget::item:selected { background-color: #4F46E5; color: white; }"
        )
        self.table.setFixedHeight(220)
        preview_layout.addWidget(self.table)

        # Tasdiqlash va saqlash tugmasi
        prev_action_row = QHBoxLayout()
        prev_action_row.addStretch()

        self.save_batch_btn = QPushButton("💾 Barcha so'zlarni lug'atga saqlash")
        self.save_batch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_batch_btn.setStyleSheet(
            "background-color: #10B981; color: white; border-radius: 8px; padding: 10px 24px; "
            "font-size: 13px; font-weight: 700;"
        )
        self.save_batch_btn.clicked.connect(self.save_preview_words)
        prev_action_row.addWidget(self.save_batch_btn)
        preview_layout.addLayout(prev_action_row)

        self.preview_box.setVisible(False)
        main_layout.addWidget(self.preview_box)

        # 6. Tezkor mashq qilish paneli (Quick Practice Box)
        self.quick_practice_box = QFrame()
        self.quick_practice_box.setStyleSheet(
            "background-color: #1E1E2E; border: 1.5px solid #4F46E5; border-radius: 12px;"
        )
        quick_layout = QVBoxLayout(self.quick_practice_box)
        quick_layout.setContentsMargins(18, 14, 18, 14)
        quick_layout.setSpacing(10)

        self.quick_title = QLabel("🎯 So'zlarni hoziroq mashq qilish va o'yinlarda mustahkamlash:")
        self.quick_title.setStyleSheet("color: white; font-size: 14px; font-weight: 700;")
        quick_layout.addWidget(self.quick_title)

        # 1-qator: Asosiy testlar
        quick_row1 = QHBoxLayout()
        quick_row1.setSpacing(8)

        self.quick_btn_en = QPushButton("🇬🇧→🇺🇿 EN → UZ")
        self.quick_btn_en.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_en.setStyleSheet("background-color: #4F46E5; color: white; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;")
        self.quick_btn_en.clicked.connect(lambda: self.launch_quick_practice("en_uz"))
        quick_row1.addWidget(self.quick_btn_en)

        self.quick_btn_uz = QPushButton("🇺🇿→🇬🇧 UZ → EN")
        self.quick_btn_uz.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_uz.setStyleSheet("background-color: #6366F1; color: white; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;")
        self.quick_btn_uz.clicked.connect(lambda: self.launch_quick_practice("uz_en"))
        quick_row1.addWidget(self.quick_btn_uz)

        self.quick_btn_flash = QPushButton("🎴 Flashcard (Anki)")
        self.quick_btn_flash.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_flash.setStyleSheet("background-color: #8B5CF6; color: white; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;")
        self.quick_btn_flash.clicked.connect(lambda: self.launch_quick_practice("flashcard"))
        quick_row1.addWidget(self.quick_btn_flash)

        self.quick_btn_speak = QPushButton("🎙️ Speaking Trenajyori")
        self.quick_btn_speak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_speak.setStyleSheet("background-color: #E11D48; color: white; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;")
        self.quick_btn_speak.clicked.connect(lambda: self.launch_quick_practice("speaking"))
        quick_row1.addWidget(self.quick_btn_speak)

        quick_row1.addStretch()
        quick_layout.addLayout(quick_row1)

        # 2-qator: O'yinlar va Lug'at
        quick_row2 = QHBoxLayout()
        quick_row2.setSpacing(8)

        self.quick_btn_match = QPushButton("🎮 So'z Juftlash (Match)")
        self.quick_btn_match.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_match.setStyleSheet("background-color: #059669; color: white; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;")
        self.quick_btn_match.clicked.connect(lambda: self.launch_quick_practice("match"))
        quick_row2.addWidget(self.quick_btn_match)

        self.quick_btn_blitz = QPushButton("⚡ Blitz Marafon")
        self.quick_btn_blitz.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_blitz.setStyleSheet("background-color: #D97706; color: white; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;")
        self.quick_btn_blitz.clicked.connect(lambda: self.launch_quick_practice("blitz"))
        quick_row2.addWidget(self.quick_btn_blitz)

        self.quick_btn_fall = QPushButton("🌧️ Word Fall")
        self.quick_btn_fall.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_fall.setStyleSheet("background-color: #2563EB; color: white; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;")
        self.quick_btn_fall.clicked.connect(lambda: self.launch_quick_practice("word_fall"))
        quick_row2.addWidget(self.quick_btn_fall)

        self.quick_btn_dict = QPushButton("📖 Lug'atda ko'rish (Ajratilgan)")
        self.quick_btn_dict.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_btn_dict.setStyleSheet(
            "background-color: #374151; color: #F3F4F6; border: 1px solid #6B7280; "
            "border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 600;"
        )
        self.quick_btn_dict.clicked.connect(lambda: self.launch_quick_practice("dictionary_import"))
        quick_row2.addWidget(self.quick_btn_dict)

        quick_row2.addStretch()
        quick_layout.addLayout(quick_row2)

        self.quick_practice_box.setVisible(False)
        main_layout.addWidget(self.quick_practice_box)

        main_layout.addStretch()

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

    def switch_mode(self, mode: str):
        """Rejimlar orasida almashish."""
        self.tab_btn_file.setChecked(mode == "file")
        self.tab_btn_paste.setChecked(mode == "paste")
        self.tab_btn_manual.setChecked(mode == "manual")

        if mode == "file":
            self.mode_layout.setCurrentWidget(self.file_card)
        elif mode == "paste":
            self.mode_layout.setCurrentWidget(self.paste_card)
            self.paste_edit.setFocus()
        elif mode == "manual":
            self.mode_layout.setCurrentWidget(self.manual_frame)
            self.eng_input.setFocus()

        self.update_tab_styles()

    def update_tab_styles(self):
        t = theme_manager.get_active_theme()
        active_style = (
            f"QPushButton {{ background-color: {t.primary}; color: white; font-weight: 700; "
            f"border-radius: 8px; padding: 8px 16px; border: 1px solid {t.primary}; }}"
        )
        inactive_style = (
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_muted}; font-weight: 500; "
            f"border-radius: 8px; padding: 8px 16px; border: 1px solid {t.border}; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; }}"
        )
        self.tab_btn_file.setStyleSheet(active_style if self.tab_btn_file.isChecked() else inactive_style)
        self.tab_btn_paste.setStyleSheet(active_style if self.tab_btn_paste.isChecked() else inactive_style)
        self.tab_btn_manual.setStyleSheet(active_style if self.tab_btn_manual.isChecked() else inactive_style)

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "title_lbl"):
            self.title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 20px; font-weight: 700;")
        if hasattr(self, "desc_lbl"):
            self.desc_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")

        if hasattr(self, "file_card"):
            self.file_card.update_style(t)
        if hasattr(self, "paste_card"):
            self.paste_card.setStyleSheet(f"background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 12px;")
        if hasattr(self, "manual_frame"):
            self.manual_frame.setStyleSheet(f"background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 12px;")
        if hasattr(self, "preview_box"):
            self.preview_box.setStyleSheet(f"background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 12px;")
        if hasattr(self, "quick_practice_box"):
            self.quick_practice_box.setStyleSheet(f"background-color: {t.bg_card}; border: 1.5px solid {t.primary}; border-radius: 12px;")

        self.update_tab_styles()

        # Inputs styling
        for w in (getattr(self, "eng_input", None), getattr(self, "uz_input", None), getattr(self, "ex_input", None)):
            if w:
                w.setStyleSheet(
                    f"background-color: {t.bg_card_secondary}; color: {t.text_main}; "
                    f"border: 1px solid {t.border}; border-radius: 6px; padding: 8px;"
                )
        if hasattr(self, "paste_edit"):
            self.paste_edit.setStyleSheet(
                f"background-color: {t.bg_card_secondary}; color: {t.text_main}; "
                f"border: 1px solid {t.border}; border-radius: 8px; padding: 10px; font-family: monospace;"
            )

        if hasattr(self, "table"):
            self.table.setStyleSheet(
                f"QTableWidget {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
                f"gridline-color: {t.border}; border: 1px solid {t.border}; border-radius: 8px; font-size: 13px; }}"
                f"QHeaderView::section {{ background-color: {t.bg_card}; color: {t.text_muted}; "
                f"font-weight: 600; padding: 6px; border: none; }}"
                f"QTableWidget::item:selected {{ background-color: {t.primary}; color: white; }}"
            )

    def launch_quick_practice(self, direction: str):
        target_ids = self.last_added_ids or db.get_last_import_word_ids()
        if self.on_start_practice and target_ids:
            logger.info(f"Import to'plami bo'yicha mashq boshlandi: {len(target_ids)} ta so'z (Rejim: {direction})")
            self.on_start_practice(target_ids, direction)

    def choose_file(self):
        """Fayl muloqot oynasini ochish."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "So'zlar faylini tanlang",
            "",
            "Barcha qo'llab-quvvatlanadigan fayllar (*.txt *.csv *.docx *.xlsx *.pdf);;"
            "Word fayllari (*.docx);;"
            "Excel jadvallari (*.xlsx *.xls);;"
            "Matn fayllari (*.txt);;"
            "CSV fayllari (*.csv);;"
            "PDF hujjatlari (*.pdf);;"
            "Barcha fayllar (*.*)"
        )
        if path:
            self.on_file_selected(path)

    def on_file_selected(self, path: str):
        """Fayl tanlanganda yoki drop qilinganda ishga tushadi."""
        logger.info(f"Import uchun fayl tanlandi: {path}")
        try:
            pairs = importer.parse_file(path)
        except Exception as e:
            logger.exception("Faylni tahlil qilishda xatolik:")
            self.result_label.setText(f"❌ Faylni o'qishda xatolik yuz berdi: {e}")
            self.result_label.setStyleSheet("color: #EF4444; font-weight: 600;")
            self.preview_box.setVisible(False)
            return

        if not pairs:
            self.result_label.setText(
                "⚠️ Fayldan so'zlar topilmadi. Iltimos, fayl ichida 'english - uzbek' yoki "
                "jadval formatida so'zlar borligini tekshiring."
            )
            self.result_label.setStyleSheet("color: #F59E0B; font-weight: 600;")
            self.preview_box.setVisible(False)
            return

        self.display_preview(pairs, source_desc=Path(path).name)

    def parse_pasted_text(self):
        """Nusxa olingan matnni tahlil qilish."""
        text = self.paste_edit.toPlainText().strip()
        if not text:
            self.result_label.setText("⚠️ Iltimos, avval matn maydoniga so'zlarni joylashtiring.")
            self.result_label.setStyleSheet("color: #F59E0B; font-weight: 600;")
            return

        pairs = importer.parse_text(text)
        if not pairs:
            self.result_label.setText("⚠️ Kiritilgan matndan tanish so'z juftliklari ajratilmadi.")
            self.result_label.setStyleSheet("color: #F59E0B; font-weight: 600;")
            self.preview_box.setVisible(False)
            return

        self.display_preview(pairs, source_desc="Matn nusxasi")

    def display_preview(self, pairs: list[tuple], source_desc: str = ""):
        """Ajratilgan so'zlarni jadvalda ko'rsatish."""
        self._parsed_pairs = pairs
        self.table.setRowCount(len(pairs))

        existing_count = 0
        new_count = 0

        for r, item in enumerate(pairs):
            eng = str(item[0]).strip()
            uz = str(item[1]).strip() if len(item) >= 2 else ""
            ex = str(item[2]).strip() if len(item) >= 3 else ""

            # Bazada mavjudligini tekshirish
            is_existing = bool(db.get_word_by_english(eng))
            if is_existing:
                existing_count += 1
                status_txt = "🔄 Bazada bor"
                status_color = QColor("#60A5FA")
            else:
                new_count += 1
                status_txt = "✅ Yangi so'z"
                status_color = QColor("#10B981")

            # №
            num_item = QTableWidgetItem(str(r + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, num_item)

            # English
            eng_item = QTableWidgetItem(eng)
            self.table.setItem(r, 1, eng_item)

            # Uzbek
            uz_item = QTableWidgetItem(uz)
            self.table.setItem(r, 2, uz_item)

            # Example
            ex_item = QTableWidgetItem(ex)
            self.table.setItem(r, 3, ex_item)

            # Status
            st_item = QTableWidgetItem(status_txt)
            st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            st_item.setForeground(status_color)
            st_item.setFlags(st_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 4, st_item)

        total = len(pairs)
        self.prev_title.setText(f"🔍 {source_desc} bo'yicha ajratilgan so'zlar:")
        self.prev_stats.setText(
            f"Jami: {total} ta so'z (🟢 {new_count} ta yangi | 🔄 {existing_count} ta bazada mavjud)"
        )
        self.save_batch_btn.setText(f"💾 Barcha {total} ta so'zni saqlash va mashq qilish")
        self.result_label.setText(
            f"🎉 Muvaffaqiyatli ajratildi: {total} ta so'z! Quyidagi jadvalda tekshirib, "
            f"kerak bo'lsa tahrirlashingiz yoki bevosita 'Saqlash' tugmasini bosishingiz mumkin."
        )
        self.result_label.setStyleSheet("color: #10B981; font-weight: 600;")

        self.preview_box.setVisible(True)

    def delete_selected_row(self):
        """Tanlangan qatorni jadvaldan o'chirish."""
        curr = self.table.currentRow()
        if curr >= 0:
            self.table.removeRow(curr)
            # Raqamlashni qayta sanash
            for r in range(self.table.rowCount()):
                it = self.table.item(r, 0)
                if it:
                    it.setText(str(r + 1))
            total = self.table.rowCount()
            self.save_batch_btn.setText(f"💾 Barcha {total} ta so'zni saqlash va mashq qilish")
            self.prev_stats.setText(f"Jami: {total} ta so'z")

    def add_empty_row(self):
        """Jadvalga yangi bo'sh qator qo'shish."""
        r = self.table.rowCount()
        self.table.insertRow(r)
        num_item = QTableWidgetItem(str(r + 1))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, num_item)
        self.table.setItem(r, 1, QTableWidgetItem(""))
        self.table.setItem(r, 2, QTableWidgetItem(""))
        self.table.setItem(r, 3, QTableWidgetItem(""))
        st_item = QTableWidgetItem("✍️ Qo'lda")
        st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        st_item.setFlags(st_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 4, st_item)
        self.table.setCurrentCell(r, 1)

    def save_preview_words(self):
        """Jadvaldagi so'zlarni bazaga to'liq saqlash va mashq panelini ochish."""
        pairs = []
        for r in range(self.table.rowCount()):
            eng_it = self.table.item(r, 1)
            uz_it = self.table.item(r, 2)
            ex_it = self.table.item(r, 3)
            eng = eng_it.text().strip() if eng_it else ""
            uz = uz_it.text().strip() if uz_it else ""
            ex = ex_it.text().strip() if ex_it else ""
            if eng and uz:
                pairs.append((eng, uz, ex) if ex else (eng, uz))

        if not pairs:
            QMessageBox.warning(self, "Diqqat", "Saqlash uchun jadvalda to'ldirilgan so'zlar topilmadi.")
            return

        summary = db.bulk_add_words(pairs, source="import")
        all_ids = summary.get("all_batch_ids", summary.get("word_ids", []))
        added_cnt = summary.get("added", 0)
        existing_cnt = len(summary.get("existing_ids", []))
        invalid_cnt = summary.get("invalid", 0)

        if all_ids:
            self.last_added_ids = all_ids
            self.quick_title.setText(
                f"🎯 Saqlangan {len(self.last_added_ids)} ta so'zni hoziroq mashq qilasizmi?"
            )
            self.quick_practice_box.setVisible(True)

        if added_cnt > 0 and existing_cnt > 0:
            msg = (
                f"✅ {added_cnt} ta yangi so'z qo'shildi | "
                f"🔄 {existing_cnt} ta mavjud so'z birlashtirildi (Jami: {len(all_ids)} ta so'z)!"
            )
            color = "#10B981"
        elif added_cnt > 0:
            msg = f"✅ Barcha {added_cnt} ta so'z muvaffaqiyatli saqlandi!"
            color = "#10B981"
        elif existing_cnt > 0:
            msg = (
                f"🔄 Barcha {existing_cnt} ta so'z allaqachon lug'atda bor edi — "
                f"mashq to'plamiga birlashtirildi!"
            )
            color = "#60A5FA"
        else:
            msg = f"⚠️ So'zlar qo'shilmadi (Yaroqsiz qatorlar: {invalid_cnt})"
            color = "#F59E0B"

        self.result_label.setText(msg)
        self.result_label.setStyleSheet(f"color: {color}; font-weight: 700;")
        self.preview_box.setVisible(False)

        if self.on_words_changed:
            self.on_words_changed()

    def add_manual(self):
        """Bitta so'zni qo'lda kiritish."""
        eng = self.eng_input.text().strip()
        uz = self.uz_input.text().strip()
        ex = self.ex_input.text().strip()
        if not eng or not uz:
            return
        added_id = db.add_word(eng, uz, source="manual", example=ex)
        if added_id:
            w_id = added_id
            msg = f"✅ '{eng} - {uz}' yangi so'z sifatida qo'shildi"
            color = "#10B981"
        else:
            existing = db.get_word_by_english(eng)
            w_id = existing["id"] if existing else None
            msg = f"🔄 '{eng}' allaqachon mavjud — mashq to'plamiga kiritildi!"
            color = "#60A5FA"

        if w_id:
            if w_id not in self.last_added_ids:
                self.last_added_ids.append(w_id)
            current_ids = db.get_last_import_word_ids()
            if w_id not in current_ids:
                current_ids.append(w_id)
                db.set_setting("last_import_word_ids", ",".join(str(i) for i in current_ids))
            self.quick_title.setText(
                f"🎯 Tanlangan {len(self.last_added_ids)} ta so'zni hoziroq mashq qilasizmi?"
            )
            self.quick_practice_box.setVisible(True)
            self.result_label.setText(msg)
            self.result_label.setStyleSheet(f"color: {color};")
            self.eng_input.clear()
            self.uz_input.clear()
            self.ex_input.clear()
            self.eng_input.setFocus()
            if self.on_words_changed:
                self.on_words_changed()

    def open_word_packs(self):
        """Tayyor so'z to'plamlari oynasini ochish."""
        from ui.word_packs_dialog import WordPacksDialog
        dlg = WordPacksDialog(self, on_words_imported=self.on_words_changed, on_start_practice=self.on_start_practice)
        dlg.exec()
        if self.on_words_changed:
            self.on_words_changed()
