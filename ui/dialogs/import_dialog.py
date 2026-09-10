from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QTextEdit, QLineEdit, QFrame
)
from PyQt6.QtCore import Qt

import database as db
import importer
import theme_manager
from logger import get_logger

logger = get_logger("import")


class ImportWidget(QWidget):
    def __init__(self, on_words_changed=None, on_start_practice=None):
        super().__init__()
        self.on_words_changed = on_words_changed
        self.on_start_practice = on_start_practice
        self.last_added_ids: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = QLabel("So'zlarni import qilish")
        header.setStyleSheet("color: white; font-size: 20px; font-weight: 700;")
        layout.addWidget(header)

        desc = QLabel(
            ".txt yoki .docx fayl tanlang. Har qatorda: english - o'zbekcha "
            "(yoki :, =, tab bilan ajratilgan). Dublikatlar avtomatik o'tkazib yuboriladi."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        layout.addWidget(desc)

        file_row = QHBoxLayout()
        self.file_btn = QPushButton("📁 Fayl tanlash (.txt / .docx)")
        self.file_btn.setStyleSheet(
            "background-color: #4F46E5; color: white; border-radius: 8px; padding: 10px 16px; font-weight: 600;"
        )
        self.file_btn.clicked.connect(self.choose_file)
        file_row.addWidget(self.file_btn)

        packs_btn = QPushButton("📚 Tayyor To'plamlar (Word Packs)")
        packs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        packs_btn.setStyleSheet(
            "QPushButton { background-color: #312E81; color: #C7D2FE; border: 1px solid #4338CA;"
            "border-radius: 8px; padding: 10px 16px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4338CA; color: white; }"
        )
        packs_btn.clicked.connect(self.open_word_packs)
        file_row.addWidget(packs_btn)

        file_row.addStretch()
        layout.addLayout(file_row)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: white; font-size: 13px;")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        # Yangi qo'shilgan so'zlarni darhol mashq qilish paneli
        self.quick_practice_box = QFrame()
        self.quick_practice_box.setStyleSheet(
            "background-color: #1E1E2E; border: 1px solid #4F46E5; border-radius: 12px;"
        )
        quick_layout = QVBoxLayout(self.quick_practice_box)
        quick_layout.setContentsMargins(18, 14, 18, 14)
        quick_layout.setSpacing(10)

        self.quick_title = QLabel("🎯 Yangi qo'shilgan so'zlarni hoziroq mashq qilasizmi?")
        self.quick_title.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
        quick_layout.addWidget(self.quick_title)

        quick_btns_row = QHBoxLayout()
        self.quick_btn_en = QPushButton("🇬🇧→🇺🇿 EN → UZ mashq qilish")
        self.quick_btn_en.setStyleSheet(
            "background-color: #4F46E5; color: white; border-radius: 6px; padding: 8px 14px; font-size: 13px;"
        )
        self.quick_btn_en.clicked.connect(lambda: self.launch_quick_practice("en_uz"))

        self.quick_btn_uz = QPushButton("🇺🇿→🇬🇧 UZ → EN mashq qilish")
        self.quick_btn_uz.setStyleSheet(
            "background-color: #6366F1; color: white; border-radius: 6px; padding: 8px 14px; font-size: 13px;"
        )
        self.quick_btn_uz.clicked.connect(lambda: self.launch_quick_practice("uz_en"))

        quick_btns_row.addWidget(self.quick_btn_en)
        quick_btns_row.addWidget(self.quick_btn_uz)
        quick_btns_row.addStretch()
        quick_layout.addLayout(quick_btns_row)

        self.quick_practice_box.setVisible(False)
        layout.addWidget(self.quick_practice_box)

        # Qo'lda bitta so'z qo'shish
        self.manual_frame = QFrame()
        self.manual_frame.setStyleSheet("background-color: #1E1E2E; border-radius: 12px;")
        manual_layout = QVBoxLayout(self.manual_frame)
        manual_layout.setContentsMargins(20, 16, 20, 16)

        manual_title = QLabel("Yoki qo'lda so'z qo'shing")
        manual_title.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
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
                "background-color: #151521; color: white; border: 1px solid #2A2A3C;"
                "border-radius: 6px; padding: 8px;"
            )
        add_btn = QPushButton("Qo'shish")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            "background-color: #10B981; color: white; border-radius: 6px; padding: 8px 14px; font-weight: 600;"
        )
        add_btn.clicked.connect(self.add_manual)
        input_row.addWidget(self.eng_input, 2)
        input_row.addWidget(self.uz_input, 2)
        input_row.addWidget(self.ex_input, 3)
        input_row.addWidget(add_btn, 1)
        manual_layout.addLayout(input_row)

        layout.addWidget(self.manual_frame)
        layout.addStretch()

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "quick_practice_box"):
            self.quick_practice_box.setStyleSheet(f"background-color: {t.bg_card}; border: 1px solid {t.primary}; border-radius: 12px;")
        if hasattr(self, "manual_frame"):
            self.manual_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        for w in (getattr(self, "eng_input", None), getattr(self, "uz_input", None), getattr(self, "ex_input", None)):
            if w:
                w.setStyleSheet(
                    f"background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; "
                    f"border-radius: 6px; padding: 8px;"
                )

    def launch_quick_practice(self, direction: str):
        if self.on_start_practice and self.last_added_ids:
            logger.info(f"Yangi qo'shilgan so'zlar bo'yicha tezkor mashq boshlandi: {len(self.last_added_ids)} ta so'z ({direction})")
            self.on_start_practice(self.last_added_ids, direction)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "So'zlar faylini tanlang",
            "",
            "Lug'at fayllari (*.txt *.csv *.docx);;Matn fayllari (*.txt);;CSV fayllari (*.csv);;Word fayllari (*.docx);;Barcha fayllar (*.*)"
        )
        if not path:
            return
        logger.info(f"Import uchun fayl tanlandi: {path}")
        try:
            pairs = importer.parse_file(path)
        except Exception as e:
            self.result_label.setText(f"❌ Xatolik: {e}")
            self.result_label.setStyleSheet("color: #EF4444;")
            return

        if not pairs:
            self.result_label.setText("⚠️ Faylda tanish formatdagi so'z topilmadi.")
            self.result_label.setStyleSheet("color: #F59E0B;")
            return

        summary = db.bulk_add_words(pairs, source="import")
        new_ids = summary.get("word_ids", [])
        if new_ids:
            self.last_added_ids = new_ids
            self.quick_title.setText(
                f"🎯 Yangi qo'shilgan {len(self.last_added_ids)} ta so'zni hoziroq mashq qilasizmi?"
            )
            self.quick_practice_box.setVisible(True)

        self.result_label.setText(
            f"✅ {summary['added']} ta yangi so'z qo'shildi | "
            f"⏭ {summary['duplicates']} dublikat o'tkazildi | "
            f"⚠️ {summary['invalid']} noto'g'ri qator"
        )
        self.result_label.setStyleSheet("color: #10B981;")
        if self.on_words_changed:
            self.on_words_changed()

    def add_manual(self):
        eng = self.eng_input.text().strip()
        uz = self.uz_input.text().strip()
        ex = self.ex_input.text().strip()
        if not eng or not uz:
            return
        added_id = db.add_word(eng, uz, source="manual", example=ex)
        if added_id:
            self.last_added_ids.append(added_id)
            self.quick_title.setText(
                f"🎯 Yangi kiritilgan {len(self.last_added_ids)} ta so'zni hoziroq mashq qilasizmi?"
            )
            self.quick_practice_box.setVisible(True)
            self.result_label.setText(f"✅ '{eng} - {uz}' qo'shildi")
            self.result_label.setStyleSheet("color: #10B981;")
            self.eng_input.clear()
            self.uz_input.clear()
            self.ex_input.clear()
            self.eng_input.setFocus()
            if self.on_words_changed:
                self.on_words_changed()
        else:
            self.result_label.setText(f"⏭ '{eng}' allaqachon bazada mavjud")
            self.result_label.setStyleSheet("color: #F59E0B;")

    def open_word_packs(self):
        """Tayyor so'z to'plamlari oynasini ochish."""
        from ui.word_packs_dialog import WordPacksDialog
        dlg = WordPacksDialog(self, on_words_imported=self.on_words_changed, on_start_practice=self.on_start_practice)
        dlg.exec()
        if self.on_words_changed:
            self.on_words_changed()
