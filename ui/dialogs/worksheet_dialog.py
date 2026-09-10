"""
Vocab Master Pro — Chop Etish & PDF Ish Varaqlari Generatori.
A4 formatdagi ikki tomonlama qirqiladigan Flashcards va javob kalitli test varaqlarini yaratadi.
"""
import random
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextBrowser, QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

import database as db
import theme_manager
from logger import get_logger

logger = get_logger("worksheet_generator")


def _generate_flashcards_html(words: list[dict]) -> str:
    """A4 formatida 2x4 (8 ta kartochka) ikki tomonlama qirqiladigan kartochkalar HTML shabloni."""
    cards_html = ""
    for w in words:
        eng = w.get("english", "")
        uz = w.get("uzbek", "")
        pho = w.get("phonetic", "") or ""
        pos = w.get("part_of_speech", "") or "word"
        ex = w.get("example", "") or ""

        cards_html += f"""
        <div class="card">
            <div class="header-tag">[{pos}]</div>
            <div class="word-eng">{eng}</div>
            <div class="phonetic">{pho}</div>
            <div class="divider"></div>
            <div class="word-uz">{uz}</div>
            {f'<div class="example">“{ex}”</div>' if ex else ''}
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Vocab Master Pro — Printable Flashcards</title>
    <style>
        @page {{
            size: A4;
            margin: 10mm;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #ffffff;
            color: #111827;
            margin: 0;
            padding: 10px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        .card {{
            border: 1.5px dashed #9CA3AF;
            border-radius: 8px;
            padding: 16px;
            height: 140px;
            box-sizing: border-box;
            position: relative;
            background: #FAFAFA;
            display: flex;
            flex-direction: column;
            justify-content: center;
            page-break-inside: avoid;
        }}
        .header-tag {{
            position: absolute;
            top: 8px;
            right: 12px;
            font-size: 12px;
            font-weight: bold;
            color: #4F46E5;
            text-transform: uppercase;
        }}
        .word-eng {{
            font-size: 20px;
            font-weight: 800;
            color: #1E1B4B;
            margin-bottom: 2px;
        }}
        .phonetic {{
            font-size: 12px;
            color: #6366F1;
            margin-bottom: 6px;
        }}
        .divider {{
            height: 1px;
            background-color: #E5E7EB;
            margin: 4px 0 6px 0;
        }}
        .word-uz {{
            font-size: 15px;
            font-weight: 700;
            color: #059669;
        }}
        .example {{
            font-size: 11px;
            color: #4B5563;
            font-style: italic;
            margin-top: 4px;
        }}
    </style>
    </head>
    <body>
        <h2 style="text-align: center; color: #1E1B4B; margin-top: 0;">📚 Vocab Master Pro — Qirqiladigan Flashcards</h2>
        <div class="grid">
            {cards_html}
        </div>
    </body>
    </html>
    """


def _generate_matching_html(words: list[dict]) -> str:
    """Lug'atni sinash uchun Juftlash Testi (Matching Worksheet) va pastda javob kaliti."""
    n = min(16, len(words))
    selected = words[:n]

    # O'zbekcha variantlarni tasodifiy aralashtirish
    shuffled_uz = [w.get("uzbek", "") for w in selected]
    random.shuffle(shuffled_uz)

    letters = [chr(65 + i) for i in range(n)]  # A, B, C...
    key_mapping = {}

    rows_html = ""
    for i, w in enumerate(selected):
        eng = w.get("english", "")
        pho = w.get("phonetic", "")
        correct_uz = w.get("uzbek", "")
        letter_idx = shuffled_uz.index(correct_uz)
        ans_letter = letters[letter_idx]
        key_mapping[i + 1] = ans_letter

        uz_opt = shuffled_uz[i]
        curr_letter = letters[i]

        rows_html += f"""
        <tr>
            <td style="width: 8%; font-weight: bold; text-align: center;">{i + 1}.</td>
            <td style="width: 32%; font-weight: bold;">{eng} <span style="font-weight: normal; color: #666; font-size: 12px;">{pho}</span></td>
            <td style="width: 10%; text-align: center;">[ &nbsp;&nbsp;&nbsp;&nbsp; ]</td>
            <td style="width: 8%; font-weight: bold; text-align: center; color: #4F46E5;">{curr_letter})</td>
            <td style="width: 42%;">{uz_opt}</td>
        </tr>
        """

    answer_keys = ", ".join([f"<b>{num}</b>-{let}" for num, let in key_mapping.items()])

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Vocab Master Pro — Matching Quiz</title>
    <style>
        @page {{ size: A4; margin: 15mm; }}
        body {{ font-family: 'Segoe UI', sans-serif; color: #111; }}
        .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 16px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        td {{ padding: 8px 4px; border-bottom: 1px solid #E5E7EB; }}
        .key-box {{ margin-top: 36px; padding: 10px; border: 1px dashed #999; background: #F9FAFB; font-size: 11px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h2 style="margin: 0;">Vocab Master Pro — So'zlarni Juftlash Testi</h2>
                <span style="font-size: 12px; color: #666;">Inglizcha so'zlar qarshisiga to'g'ri keluvchi o'zbekcha harfni yozing.</span>
            </div>
            <div style="text-align: right; font-size: 13px;">
                Ism: _______________________<br>
                Sana: ______________________
            </div>
        </div>

        <table>
            {rows_html}
        </table>

        <div class="key-box">
            <b>🔑 Javoblar Kaliti (Answer Key):</b> {answer_keys}
        </div>
    </body>
    </html>
    """


class WorksheetGeneratorDialog(QDialog):
    """Chop etish va PDF ish varaqlarini eksport qilish oynasi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖨️ Chop Etish & Flashcards Generatori")
        self.resize(880, 680)
        self.current_html = ""
        self._build_ui()
        self.apply_theme(theme_manager.get_active_theme())
        self._generate_content()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # Boshqaruv paneli
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        top_bar.addWidget(QLabel("Format:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems([
            "🎴 Qirqiladigan Flashcards (2x4 A4)",
            "📝 Juftlash Test Varaqasi (Matching Quiz)"
        ])
        self.combo_format.currentIndexChanged.connect(self._generate_content)
        top_bar.addWidget(self.combo_format)

        top_bar.addWidget(QLabel("So'zlar:"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItems([
            "📚 Barcha so'zlar",
            "🧠 Bugungi takrorlash (SM-2)",
            "⚠️ Zaif so'zlar",
            "🎲 Tasodifiy 16 ta"
        ])
        self.combo_filter.currentIndexChanged.connect(self._generate_content)
        top_bar.addWidget(self.combo_filter)

        top_bar.addStretch()

        self.btn_print = QPushButton("🖨️ Chop etish")
        self.btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_print.clicked.connect(self._print_document)
        top_bar.addWidget(self.btn_print)

        self.btn_save = QPushButton("💾 HTML / PDF saqlash")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_file)
        top_bar.addWidget(self.btn_save)

        root.addLayout(top_bar)

        # HTML Ko'rish Paneli
        self.preview_browser = QTextBrowser()
        self.preview_browser.setStyleSheet(
            "background-color: white; color: #111827; border-radius: 10px; padding: 12px;"
        )
        root.addWidget(self.preview_browser, 1)

    def _get_filtered_words(self) -> list[dict]:
        idx = self.combo_filter.currentIndex()
        if idx == 0:
            words = db.get_all_words()
        elif idx == 1:
            words = db.get_due_words() or db.get_all_words()
        elif idx == 2:
            words = db.get_weakest_words(limit=24) or db.get_all_words()
        else:
            all_w = db.get_all_words()
            words = random.sample(all_w, min(16, len(all_w)))

        return [dict(w) for w in words]

    def _generate_content(self):
        words = self._get_filtered_words()
        if not words:
            self.preview_browser.setHtml("<h3 style='color:red;'>Bazada so'zlar topilmadi.</h3>")
            return

        fmt = self.combo_format.currentIndex()
        if fmt == 0:
            self.current_html = _generate_flashcards_html(words)
        else:
            self.current_html = _generate_matching_html(words)

        self.preview_browser.setHtml(self.current_html)

    def _print_document(self):
        doc = QTextDocument()
        doc.setHtml(self.current_html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            doc.print(printer)

    def _save_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Varaqni saqlash", "vocab_master_worksheet.html", "HTML Files (*.html)"
        )
        if path:
            try:
                Path(path).write_text(self.current_html, encoding="utf-8")
                QMessageBox.information(
                    self, "Muvaffaqiyat", f"Varaq muvaffaqiyatli saqlandi:\n{path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Xatolik", f"Faylni saqlab bo'lmadi: {e}")

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app}; color: {t.text_main};")
        btn_primary = (
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
            f"padding: 8px 16px; font-weight: 700; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        self.btn_print.setStyleSheet(btn_primary)
        self.btn_save.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 16px; font-weight: 600; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; }}"
        )
        combo_style = (
            f"QComboBox {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 6px 12px; font-size: 13px; }}"
        )
        self.combo_format.setStyleSheet(combo_style)
        self.combo_filter.setStyleSheet(combo_style)
