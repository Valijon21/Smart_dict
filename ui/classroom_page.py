"""
Vocab Master Pro — Teacher & Classroom Mode (O'qituvchi va Sinf Rejimi).
1. .smartpack Darslik paketlarini eksport va import qilish.
2. O'quvchi o'zlashtirish hisoboti va sertifikati (A4 HTML/PDF).
"""
import os
import json
import time
import webbrowser
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QTextBrowser, QFrame,
    QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor

import database as db
import theme_manager
from logger import get_logger

logger = get_logger("classroom_page")


class ClassroomPageWidget(QWidget):
    """O'qituvchi va Sinf Rejimi sahifasi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        t = theme_manager.get_active_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(16)

        # 1. Sarlavha qatori
        title_row = QHBoxLayout()
        self.title_lbl = QLabel("👨‍🏫 O'qituvchi va Sinf Rejimi (Teacher Mode)")
        self.title_lbl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.text_main};")
        title_row.addWidget(self.title_lbl)
        title_row.addStretch()
        root.addLayout(title_row)

        desc = QLabel(
            "O'quvchilaringiz uchun maxsus mavzulashtirilgan '.smartpack' darslik paketlarini yarating "
            "va ularning o'zlashtirish ko'rsatkichlari bo'yicha A4 formatdagi rasmiy hisobot/sertifikat shakllantiring."
        )
        desc.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # 2. Asosiy Tablar
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {t.border}; border-radius: 10px; background-color: {t.bg_card}; }} "
            f"QTabBar::tab {{ background: {t.bg_app}; color: {t.text_muted}; padding: 10px 22px; "
            f"font-weight: 600; font-size: 13px; border-top-left-radius: 8px; border-top-right-radius: 8px; }} "
            f"QTabBar::tab:selected {{ background: {t.bg_card}; color: {t.primary}; border: 1px solid {t.border}; border-bottom: none; }}"
        )

        # Tab 1: Paket yaratish va eksport
        self.tab_export = QWidget()
        self._build_export_tab()
        self.tabs.addTab(self.tab_export, "📦 Yangi .smartpack Yaratish")

        # Tab 2: Paket import qilish
        self.tab_import = QWidget()
        self._build_import_tab()
        self.tabs.addTab(self.tab_import, "📥 .smartpack Import Qilish")

        # Tab 3: O'quvchi hisoboti va sertifikat
        self.tab_report = QWidget()
        self._build_report_tab()
        self.tabs.addTab(self.tab_report, "🎓 O'quvchi Hisoboti & Sertifikat")

        root.addWidget(self.tabs, 1)

    def _build_export_tab(self):
        t = theme_manager.get_active_theme()
        layout = QVBoxLayout(self.tab_export)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Meta ma'lumotlar
        meta_grid = QHBoxLayout()
        meta_grid.setSpacing(14)

        col1 = QVBoxLayout()
        lbl_pname = QLabel("Paket Nomi (Darslik mavzusi):")
        lbl_pname.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        self.input_pack_name = QLineEdit()
        self.input_pack_name.setPlaceholderText("Masalan: Unit 5 - Environmental Science")
        self.input_pack_name.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 12px; font-size: 13px;"
        )
        col1.addWidget(lbl_pname)
        col1.addWidget(self.input_pack_name)
        meta_grid.addLayout(col1, 2)

        col2 = QVBoxLayout()
        lbl_pauthor = QLabel("O'qituvchi / Muallif:")
        lbl_pauthor.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        self.input_pack_author = QLineEdit()
        self.input_pack_author.setPlaceholderText("Ism-familiyangiz")
        self.input_pack_author.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 12px; font-size: 13px;"
        )
        col2.addWidget(lbl_pauthor)
        col2.addWidget(self.input_pack_author)
        meta_grid.addLayout(col2, 1)

        col3 = QVBoxLayout()
        lbl_plevel = QLabel("Daraja (CEFR):")
        lbl_plevel.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        self.combo_pack_level = QComboBox()
        self.combo_pack_level.addItems(["A1 - Beginner", "A2 - Elementary", "B1 - Intermediate", "B2 - Upper-Intermediate", "C1 - Advanced"])
        self.combo_pack_level.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 7px 12px; font-size: 13px;"
        )
        col3.addWidget(lbl_plevel)
        col3.addWidget(self.combo_pack_level)
        meta_grid.addLayout(col3, 1)

        layout.addLayout(meta_grid)

        # So'zlar jadvali
        lbl_tbl = QLabel("Paketga qo'shiladigan so'zlarni tanlang:")
        lbl_tbl.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        layout.addWidget(lbl_tbl)

        tbl_actions = QHBoxLayout()
        self.chk_select_all = QCheckBox("Barchasini tanlash")
        self.chk_select_all.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
        self.chk_select_all.stateChanged.connect(self._toggle_select_all)
        tbl_actions.addWidget(self.chk_select_all)
        tbl_actions.addStretch()

        self.btn_refresh_words = QPushButton("🔄 Ro'yxatni yangilash")
        self.btn_refresh_words.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 4px 12px; font-size: 12px;"
        )
        self.btn_refresh_words.clicked.connect(self._load_words_for_export)
        tbl_actions.addWidget(self.btn_refresh_words)
        layout.addLayout(tbl_actions)

        self.export_table = QTableWidget()
        self.export_table.setColumnCount(4)
        self.export_table.setHorizontalHeaderLabels(["Tanlash", "Inglizcha", "O'zbekcha", "Misol"])
        self.export_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.export_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.export_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.export_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.export_table.setStyleSheet(
            f"QTableWidget {{ background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; border-radius: 8px; }} "
            f"QHeaderView::section {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; padding: 6px; }}"
        )
        layout.addWidget(self.export_table, 1)

        # Eksport tugmasi
        btn_exp_row = QHBoxLayout()
        btn_exp_row.addStretch()

        self.btn_save_pack = QPushButton("📦 .smartpack Fayliga Eksport Qilish")
        self.btn_save_pack.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_pack.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
            f"font-size: 14px; font-weight: 700; padding: 10px 24px; }} "
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        self.btn_save_pack.clicked.connect(self._export_smartpack)
        btn_exp_row.addWidget(self.btn_save_pack)
        layout.addLayout(btn_exp_row)

        self._load_words_for_export()

    def _load_words_for_export(self):
        words = db.get_all_words()
        self.export_table.setRowCount(len(words))
        for r, w in enumerate(words):
            wd = dict(w) if not isinstance(w, dict) else w
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.addWidget(chk)
            chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            self.export_table.setCellWidget(r, 0, chk_widget)

            # Data
            item_en = QTableWidgetItem(wd.get("english", ""))
            item_en.setData(Qt.ItemDataRole.UserRole, wd)
            item_uz = QTableWidgetItem(wd.get("uzbek", ""))
            item_ex = QTableWidgetItem(wd.get("example", ""))

            self.export_table.setItem(r, 1, item_en)
            self.export_table.setItem(r, 2, item_uz)
            self.export_table.setItem(r, 3, item_ex)

    def _toggle_select_all(self, state):
        checked = bool(state)
        for r in range(self.export_table.rowCount()):
            w = self.export_table.cellWidget(r, 0)
            if w:
                chk = w.findChild(QCheckBox)
                if chk:
                    chk.setChecked(checked)

    def _export_smartpack(self):
        title = self.input_pack_name.text().strip()
        if not title:
            QMessageBox.warning(self, "Xatolik", "Iltimos, paket nomini kiriting!")
            return

        selected_words = []
        for r in range(self.export_table.rowCount()):
            chk_widget = self.export_table.cellWidget(r, 0)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    item = self.export_table.item(r, 1)
                    if item:
                        wdata = item.data(Qt.ItemDataRole.UserRole)
                        if wdata:
                            selected_words.append({
                                "english": wdata.get("english", ""),
                                "uzbek": wdata.get("uzbek", ""),
                                "part_of_speech": wdata.get("part_of_speech", ""),
                                "phonetic": wdata.get("phonetic", ""),
                                "example": wdata.get("example", ""),
                                "tags": wdata.get("tags", "")
                            })

        if not selected_words:
            QMessageBox.warning(self, "Bo'sh paket", "Paketga kamida bitta so'z tanlanishi kerak!")
            return

        clean_slug = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        default_filename = f"{clean_slug}.smartpack"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Smartpack Faylini Saqlash",
            str(Path.home() / default_filename),
            "Smartpack Lesson (*.smartpack)"
        )
        if not save_path:
            return

        pack_obj = {
            "version": "1.0",
            "format": "smartpack",
            "created_at": QDate.currentDate().toString(Qt.DateFormat.ISODate),
            "title": title,
            "author": self.input_pack_author.text().strip() or "O'qituvchi",
            "level": self.combo_pack_level.currentText(),
            "word_count": len(selected_words),
            "words": selected_words
        }

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(pack_obj, f, ensure_ascii=False, indent=2)

            QMessageBox.information(
                self,
                "Muvaffaqiyatli!",
                f"'{title}' darslik to'plami muvaffaqiyatli saqlandi!\n\n"
                f"So'zlar soni: {len(selected_words)} ta\nFayl: {save_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Saqlashda xatolik", f"Xatolik: {e}")

    def _build_import_tab(self):
        t = theme_manager.get_active_theme()
        layout = QVBoxLayout(self.tab_import)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        info_lbl = QLabel(
            "O'qituvchi yoki boshqa foydalanuvchilar tomonidan yuborilgan "
            "'.smartpack' darslik faylini tanlang va 1-bosish bilan bazaga qo'shing:"
        )
        info_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 13px;")
        layout.addWidget(info_lbl)

        # Fayl tanlash paneli
        file_box = QHBoxLayout()
        self.input_import_path = QLineEdit()
        self.input_import_path.setPlaceholderText(".smartpack fayli yo'li...")
        self.input_import_path.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 12px; font-size: 13px;"
        )
        file_box.addWidget(self.input_import_path, 1)

        btn_browse_pack = QPushButton("📁 Faylni tanlash...")
        btn_browse_pack.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 8px; padding: 8px 16px; font-size: 13px; }} "
            f"QPushButton:hover {{ border-color: {t.primary}; }}"
        )
        btn_browse_pack.clicked.connect(self._browse_smartpack)
        file_box.addWidget(btn_browse_pack)
        layout.addLayout(file_box)

        # Paket ko'rinishi (Preview)
        self.import_preview_lbl = QLabel("Paket haqida ma'lumotlar bu yerda ko'rinadi.")
        self.import_preview_lbl.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_muted}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 14px; font-size: 13px;"
        )
        layout.addWidget(self.import_preview_lbl)

        self.import_table = QTableWidget()
        self.import_table.setColumnCount(3)
        self.import_table.setHorizontalHeaderLabels(["Inglizcha", "O'zbekcha", "Misol"])
        self.import_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.import_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.import_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.import_table.setStyleSheet(
            f"QTableWidget {{ background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; border-radius: 8px; }} "
            f"QHeaderView::section {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; padding: 6px; }}"
        )
        layout.addWidget(self.import_table, 1)

        # Import tugmasi
        btn_import_row = QHBoxLayout()
        btn_import_row.addStretch()

        self.btn_execute_import = QPushButton("📥 Lug'atga Qo'shish (Import)")
        self.btn_execute_import.setEnabled(False)
        self.btn_execute_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_execute_import.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; border-radius: 8px; "
            "font-size: 14px; font-weight: 700; padding: 10px 24px; } "
            "QPushButton:hover { background-color: #059669; }"
        )
        self.btn_execute_import.clicked.connect(self._execute_smartpack_import)
        btn_import_row.addWidget(self.btn_execute_import)
        layout.addLayout(btn_import_row)

        self.loaded_pack_data = None

    def _browse_smartpack(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Smartpack darslik paketini ochish",
            str(Path.home()),
            "Smartpack Lesson (*.smartpack *.json)"
        )
        if not filepath:
            return

        self.input_import_path.setText(filepath)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                pack = json.load(f)

            self.loaded_pack_data = pack
            title = pack.get("title", "Nomsiz to'plam")
            author = pack.get("author", "Noma'lum")
            level = pack.get("level", "-")
            words = pack.get("words", [])

            self.import_preview_lbl.setText(
                f"📦 <b>Darslik:</b> {title}  |  👨‍🏫 <b>Muallif:</b> {author}  |  "
                f"🎯 <b>Daraja:</b> {level}  |  📚 <b>So'zlar:</b> {len(words)} ta"
            )

            self.import_table.setRowCount(len(words))
            for r, w in enumerate(words):
                self.import_table.setItem(r, 0, QTableWidgetItem(w.get("english", "")))
                self.import_table.setItem(r, 1, QTableWidgetItem(w.get("uzbek", "")))
                self.import_table.setItem(r, 2, QTableWidgetItem(w.get("example", "")))

            self.btn_execute_import.setEnabled(len(words) > 0)
        except Exception as e:
            QMessageBox.critical(self, "O'qishda xatolik", f"Smartpack faylini ochib bo'lmadi: {e}")

    def _execute_smartpack_import(self):
        if not self.loaded_pack_data:
            return

        words = self.loaded_pack_data.get("words", [])
        title = self.loaded_pack_data.get("title", "Darslik")
        tag_name = f"pack_{title.lower().replace(' ', '_')}"

        added = 0
        skipped = 0
        for w in words:
            eng = w.get("english", "").strip()
            uz = w.get("uzbek", "").strip()
            if eng and uz:
                try:
                    ok = db.add_word(
                        english=eng,
                        uzbek=uz,
                        part_of_speech=w.get("part_of_speech", ""),
                        phonetic=w.get("phonetic", ""),
                        example=w.get("example", ""),
                        tags=f"{tag_name},{w.get('tags', '')}".strip(",")
                    )
                    if ok:
                        added += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

        QMessageBox.information(
            self,
            "Import Yakunlandi",
            f"'{title}' paketi muvaffaqiyatli import qilindi!\n\n"
            f"✅ Yangi qo'shildi: {added} ta so'z\n"
            f"⚠️ Mavjud bo'lgani uchun o'tkazildi: {skipped} ta"
        )
        self.btn_execute_import.setEnabled(False)

    def _build_report_tab(self):
        t = theme_manager.get_active_theme()
        layout = QVBoxLayout(self.tab_report)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # O'quvchi ma'lumotlari
        inp_row = QHBoxLayout()
        inp_row.setSpacing(14)

        lbl_sname = QLabel("O'quvchi Ismi-Familiyasi:")
        lbl_sname.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        self.input_student_name = QLineEdit()
        self.input_student_name.setPlaceholderText("Masalan: Alisher Navoiy")
        self.input_student_name.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 12px; font-size: 13px;"
        )
        inp_row.addWidget(lbl_sname)
        inp_row.addWidget(self.input_student_name, 1)

        btn_gen = QPushButton("📄 Hisobotni Shakllantirish")
        btn_gen.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_gen.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
            f"font-size: 13px; font-weight: 700; padding: 8px 20px; }} "
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        btn_gen.clicked.connect(self._generate_student_report)
        inp_row.addWidget(btn_gen)

        layout.addLayout(inp_row)

        # HTML hisobot brauzeri
        self.report_browser = QTextBrowser()
        self.report_browser.setStyleSheet(
            "QTextBrowser { background-color: #FFFFFF; color: #111827; border-radius: 10px; padding: 16px; }"
        )
        layout.addWidget(self.report_browser, 1)

        # Pastki amallar
        act_row = QHBoxLayout()
        act_row.addStretch()

        self.btn_open_browser = QPushButton("🌐 Brauzerda Ochish & Chop Etish (Print)")
        self.btn_open_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_browser.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; border-radius: 8px; "
            "padding: 9px 20px; font-size: 13px; font-weight: 700; } "
            "QPushButton:hover { background-color: #1D4ED8; }"
        )
        self.btn_open_browser.clicked.connect(self._open_report_in_browser)
        act_row.addWidget(self.btn_open_browser)

        layout.addLayout(act_row)
        self.last_generated_html = ""

    def _generate_student_report(self):
        student_name = self.input_student_name.text().strip() or "Foydalanuvchi"
        today_str = QDate.currentDate().toString("dd.MM.yyyy")

        # Bazadan statistik ma'lumotlarni yig'ish
        counts = db.word_count()
        total_words = counts.get("total", 0)
        mastered_words = counts.get("mastered", 0)
        learning_words = counts.get("learning", 0)
        weak_words = counts.get("weak", 0)

        # XP va Gamifikatsiya
        cur_xp = int(db.get_setting("user_xp", "0") or "0")
        streak = int(db.get_setting("streak_days", "1") or "1")

        # CEFR darajasini aniqlash
        if total_words >= 3000:
            level = "C1 — Advanced"
        elif total_words >= 1800:
            level = "B2 — Upper-Intermediate"
        elif total_words >= 900:
            level = "B1 — Intermediate"
        elif total_words >= 400:
            level = "A2 — Elementary"
        else:
            level = "A1 — Beginner"

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Vocab Master Pro — O'quvchi Hisoboti</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #F9FAFB; color: #111827; margin: 0; padding: 24px; }}
  .cert-container {{ max-width: 780px; margin: 0 auto; background: white; border: 2px solid #E5E7EB; border-radius: 16px; padding: 40px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
  .header {{ text-align: center; border-bottom: 2px solid #4F46E5; padding-bottom: 24px; margin-bottom: 28px; }}
  .title {{ font-size: 26px; font-weight: 800; color: #1E1B4B; margin: 0; }}
  .subtitle {{ font-size: 14px; color: #6B7280; margin-top: 6px; }}
  .student-card {{ background: #EEF2FF; border-radius: 12px; padding: 18px 24px; text-align: center; margin-bottom: 28px; border: 1px solid #C7D2FE; }}
  .student-name {{ font-size: 24px; font-weight: 700; color: #4338CA; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 28px; }}
  .card {{ flex: 1; min-width: 150px; background: #F3F4F6; border-radius: 10px; padding: 16px; text-align: center; border: 1px solid #E5E7EB; }}
  .card-val {{ font-size: 22px; font-weight: 800; color: #111827; }}
  .card-lbl {{ font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase; margin-top: 4px; }}
  .badge-master {{ color: #059669; }}
  .badge-level {{ color: #4F46E5; }}
  .footer {{ display: flex; justify-content: space-between; border-top: 1px solid #E5E7EB; padding-top: 20px; font-size: 12px; color: #9CA3AF; margin-top: 30px; }}
  @media print {{
    body {{ background: white; padding: 0; }}
    .cert-container {{ border: none; box-shadow: none; padding: 10px; }}
  }}
</style>
</head>
<body>
<div class="cert-container">
  <div class="header">
    <div style="font-size: 36px; margin-bottom: 8px;">🎓</div>
    <h1 class="title">VOCAB MASTER PRO — O'QUVCHILAR NATIJASI</h1>
    <div class="subtitle">Ingliz tili so'z boyligi va o'zlashtirish rasmiy sertifikat-hisoboti</div>
  </div>

  <div class="student-card">
    <div style="font-size: 13px; color: #6366F1; font-weight: 600; text-transform: uppercase;">O'quvchi</div>
    <div class="student-name">{student_name}</div>
    <div style="font-size: 13px; color: #4B5563; margin-top: 4px;">Taqdim etilgan sana: {today_str}</div>
  </div>

  <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
    <tr>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0; width: 50%;"><b>📚 Jami so'z boyligi:</b></td>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0; text-align: right; font-weight: 700; color: #1E293B;">{total_words} ta so'z</td>
    </tr>
    <tr>
      <td style="padding: 10px; background: white; border: 1px solid #E2E8F0;"><b>🎯 Taxminiy CEFR darajasi:</b></td>
      <td style="padding: 10px; background: white; border: 1px solid #E2E8F0; text-align: right; font-weight: 700; color: #4F46E5;">{level}</td>
    </tr>
    <tr>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0;"><b>✅ Mustahkam o'zlashtirilgan:</b></td>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0; text-align: right; font-weight: 700; color: #059669;">{mastered_words} ta so'z</td>
    </tr>
    <tr>
      <td style="padding: 10px; background: white; border: 1px solid #E2E8F0;"><b>🌱 O'rganilayotgan (Leitner jarayoni):</b></td>
      <td style="padding: 10px; background: white; border: 1px solid #E2E8F0; text-align: right; font-weight: 700; color: #2563EB;">{learning_words} ta so'z</td>
    </tr>
    <tr>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0;"><b>⚠️ Ko'p xato qilingan (zaif) so'zlar:</b></td>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0; text-align: right; font-weight: 700; color: #DC2626;">{weak_words} ta so'z</td>
    </tr>
    <tr>
      <td style="padding: 10px; background: white; border: 1px solid #E2E8F0;"><b>⭐ Tajriba ballari (Gamification XP):</b></td>
      <td style="padding: 10px; background: white; border: 1px solid #E2E8F0; text-align: right; font-weight: 700; color: #D97706;">{cur_xp} XP</td>
    </tr>
    <tr>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0;"><b>🔥 Uzluksiz o'qish zanjiri (Streak):</b></td>
      <td style="padding: 10px; background: #F8FAFC; border: 1px solid #E2E8F0; text-align: right; font-weight: 700; color: #EA580C;">{streak} kun</td>
    </tr>
  </table>

  <div style="background-color: #F9FAFB; border-radius: 10px; padding: 14px; font-size: 13px; color: #4B5563; border-left: 4px solid #4F46E5;">
    <b>O'qituvchi xulosasi:</b> O'quvchi so'zlarni muntazam mashq qilib bormoqda. Leitner qutilari bo'yicha oraliq takrorlash (Spaced Repetition) natijasida so'zlar uzoq muddatli xotiraga muvaffaqiyatli o'tkazilmoqda.
  </div>

  <div class="footer">
    <div>Vocab Master Pro Dasturi orqali avtomatik tasdiqlangan</div>
    <div>Tekshiruv kodi: VMP-{int(time.time()) % 1000000:06d}</div>
  </div>
</div>
</body>
</html>
"""
        self.last_generated_html = html
        self.report_browser.setHtml(html)

    def _open_report_in_browser(self):
        if not self.last_generated_html:
            self._generate_student_report()

        temp_path = Path.home() / "vocab_master_student_report.html"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(self.last_generated_html)
            webbrowser.open(f"file:///{temp_path}")
        except Exception as e:
            QMessageBox.critical(self, "Xatolik", f"Brauzerda ochishda xatolik: {e}")
