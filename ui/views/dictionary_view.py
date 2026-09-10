from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QMessageBox,
    QFileDialog, QFrame, QScrollArea, QStyledItemDelegate, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QPointF, QEvent
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen, QBrush, QFont

import database as db
import tts
import theme_manager
import phonetics
import global_dict_service
from logger import get_logger

from ui.word_packs_dialog import WordPacksDialog
from ui.worksheet_generator import WorksheetGeneratorDialog

logger = get_logger("dictionary")


class EnglishCellDelegate(QStyledItemDelegate):
    """
    Inglizcha so'z, fonetika, so'z turkumi va audio tugmasini yuqori unumdorlikda chizuvchi delegat.
    Hech qanday og'ir QWidget yoki QLayout yaratmaydi (60 FPS silliq aylanish).
    """
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget

    def _get_audio_rect(self, cell_rect: QRect) -> QRect:
        return QRect(cell_rect.x() + 10, cell_rect.y() + (cell_rect.height() - 32) // 2, 34, 32)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        data = index.data(Qt.ItemDataRole.UserRole) or {}
        word = data.get("english", "")
        ph = data.get("phonetic", "")
        pos = data.get("pos", "")

        rect = option.rect
        t = theme_manager.get_active_theme()
        is_dark = t.is_dark

        # 1. Karnay tugmasi (Audio icon container)
        btn_rect = self._get_audio_rect(rect)
        if is_dark:
            painter.setPen(QPen(QColor("#3730A3"), 1))
            painter.setBrush(QBrush(QColor("#202038")))
            icon_color = QColor("#818CF8")
        else:
            painter.setPen(QPen(QColor("#C7D2FE"), 1))
            painter.setBrush(QBrush(QColor("#EEF2FF")))
            icon_color = QColor("#4338CA")
        painter.drawRoundedRect(btn_rect, 6, 6)

        f_icon = QFont(option.font)
        f_icon.setPointSize(12)
        painter.setFont(f_icon)
        painter.setPen(icon_color)
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, "🔊")

        # 2. Inglizcha so'z
        f_word = QFont(option.font)
        f_word.setPointSize(11)
        f_word.setBold(True)
        painter.setFont(f_word)
        painter.setPen(QColor(t.text_main))
        word_rect = QRect(rect.x() + 54, rect.y() + 6, max(10, rect.width() - 60), 20)
        painter.drawText(word_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, word)

        # 3. Fonetika va So'z turkumi
        f_sub = QFont(option.font)
        f_sub.setPointSize(9)
        f_sub.setBold(False)
        painter.setFont(f_sub)
        sub_x = rect.x() + 54
        sub_y = rect.y() + 27
        if ph:
            painter.setPen(QColor("#A5B4FC" if is_dark else "#4338CA"))
            painter.drawText(sub_x, sub_y + 14, ph)
            fm = painter.fontMetrics()
            sub_x += fm.horizontalAdvance(ph) + 8
        if pos:
            pos_text = f"[{pos}]"
            fm = painter.fontMetrics()
            pw = fm.horizontalAdvance(pos_text) + 8
            pill = QRect(sub_x, sub_y + 1, pw, 18)
            painter.setPen(Qt.PenStyle.NoPen)
            if is_dark:
                painter.setBrush(QBrush(QColor("#312E81")))
                painter.drawRoundedRect(pill, 4, 4)
                painter.setPen(QColor("#C7D2FE"))
            else:
                painter.setBrush(QBrush(QColor("#E0E7FF")))
                painter.drawRoundedRect(pill, 4, 4)
                painter.setPen(QColor("#3730A3"))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, pos_text)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            pos = event.position().toPoint()
            audio_rect = self._get_audio_rect(option.rect)
            data = index.data(Qt.ItemDataRole.UserRole) or {}
            word = data.get("english", "")
            if word and (audio_rect.contains(pos) or event.button() == Qt.MouseButton.LeftButton):
                self.parent_widget.play_word_audio(word)
                return True
        return super().editorEvent(event, model, option, index)


class UzbekCellDelegate(QStyledItemDelegate):
    """
    O'zbekcha tarjima va misol gapni chizuvchi yuqori unumdorlikdagi delegat.
    """
    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        data = index.data(Qt.ItemDataRole.UserRole) or {}
        uz_text = data.get("uzbek", "")
        ex_text = data.get("example", "")

        t = theme_manager.get_active_theme()
        is_dark = t.is_dark

        rect = option.rect.adjusted(12, 4, -12, -4)

        if ex_text:
            f1 = QFont(option.font)
            f1.setPointSize(10)
            f1.setBold(True)
            painter.setFont(f1)
            painter.setPen(QColor(t.text_main))
            top_rect = QRect(rect.x(), rect.y() + 2, rect.width(), 20)
            painter.drawText(top_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, uz_text)

            f2 = QFont(option.font)
            f2.setPointSize(9)
            f2.setItalic(True)
            painter.setFont(f2)
            painter.setPen(QColor("#818CF8" if is_dark else "#4338CA"))
            bot_rect = QRect(rect.x(), rect.y() + 24, rect.width(), 18)
            elided_ex = painter.fontMetrics().elidedText(f"💡 {ex_text}", Qt.TextElideMode.ElideRight, rect.width())
            painter.drawText(bot_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_ex)
        else:
            f = QFont(option.font)
            f.setPointSize(10)
            f.setBold(True)
            painter.setFont(f)
            painter.setPen(QColor(t.text_main))
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, uz_text)

        painter.restore()


class PillBadgeDelegate(QStyledItemDelegate):
    """
    Leitner Box va Status chiplarini zamonaviy yumaloq pill shaklida chizuvchi delegat.
    """
    def paint(self, painter: QPainter, option, index):
        data = index.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        text = data.get("text", "")
        bg = QColor(data.get("bg", "#1F2937"))
        fg = QColor(data.get("fg", "#9CA3AF"))
        border = QColor(data.get("border", "#374151"))

        rect = option.rect
        w = max(72, min(rect.width() - 16, len(text) * 8 + 24))
        h = 24
        x = rect.x() + (rect.width() - w) // 2
        y = rect.y() + (rect.height() - h) // 2
        pill_rect = QRect(x, y, w, h)

        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(pill_rect, 11, 11)

        f = QFont(option.font)
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(fg)
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()


class ActionsCellDelegate(QStyledItemDelegate):
    """
    Jadval amallari (💡 Smart Insights, ✏️ Tahrirlash, 🗑️ O'chirish) delegati.
    Hech qanday QWidget yaratmasdan, bir zumda silliq 60 FPS da ishlaydi.
    """
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget

    def _get_button_rects(self, cell_rect: QRect):
        btn_w, btn_h, spacing = 32, 30, 6
        total_w = 3 * btn_w + 2 * spacing
        sx = cell_rect.x() + (cell_rect.width() - total_w) // 2
        sy = cell_rect.y() + (cell_rect.height() - btn_h) // 2
        r1 = QRect(sx, sy, btn_w, btn_h)
        r2 = QRect(sx + btn_w + spacing, sy, btn_w, btn_h)
        r3 = QRect(sx + 2 * (btn_w + spacing), sy, btn_w, btn_h)
        return r1, r2, r3

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        r_info, r_edit, r_del = self._get_button_rects(option.rect)
        t = theme_manager.get_active_theme()
        is_dark = t.is_dark

        # 1. Info btn (💡)
        if is_dark:
            painter.setPen(QPen(QColor("#4D3D70"), 1))
            painter.setBrush(QBrush(QColor("#262040")))
        else:
            painter.setPen(QPen(QColor("#DDD6FE"), 1))
            painter.setBrush(QBrush(QColor("#F5F3FF")))
        painter.drawRoundedRect(r_info, 6, 6)

        # 2. Edit btn (✏️)
        if is_dark:
            painter.setPen(QPen(QColor("#3F377A"), 1))
            painter.setBrush(QBrush(QColor("#242044")))
        else:
            painter.setPen(QPen(QColor("#C7D2FE"), 1))
            painter.setBrush(QBrush(QColor("#EEF2FF")))
        painter.drawRoundedRect(r_edit, 6, 6)

        # 3. Del btn (🗑️)
        if is_dark:
            painter.setPen(QPen(QColor("#6B1D1D"), 1))
            painter.setBrush(QBrush(QColor("#381A1A")))
        else:
            painter.setPen(QPen(QColor("#FECACA"), 1))
            painter.setBrush(QBrush(QColor("#FEF2F2")))
        painter.drawRoundedRect(r_del, 6, 6)

        f = QFont(option.font)
        f.setPointSize(11)
        painter.setFont(f)

        painter.drawText(r_info, Qt.AlignmentFlag.AlignCenter, "💡")
        painter.drawText(r_edit, Qt.AlignmentFlag.AlignCenter, "✏️")
        painter.drawText(r_del, Qt.AlignmentFlag.AlignCenter, "🗑️")

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            pos = event.position().toPoint()
            r_info, r_edit, r_del = self._get_button_rects(option.rect)
            data = index.data(Qt.ItemDataRole.UserRole) or {}
            word_id = data.get("id")
            english = data.get("english", "")
            uzbek = data.get("uzbek", "")
            example = data.get("example", "")

            if r_info.contains(pos) and english:
                self.parent_widget.open_word_details(english)
                return True
            elif r_edit.contains(pos) and word_id is not None:
                self.parent_widget.edit_word(word_id, english, uzbek, example)
                return True
            elif r_del.contains(pos) and word_id is not None:
                self.parent_widget.delete_word(word_id, english)
                return True
        return super().editorEvent(event, model, option, index)


class WordDetailsDialog(QDialog):
    """
    64,000 so'zlik akademik bazadan so'zning barcha nozik qirralarini ko'rsatuvchi
    ensiklopedik oyna: Kollokatsiyalar, So'zlar farqi, Sinonimlar, Iboralar va Grammatika.
    """
    def __init__(self, parent, english: str, on_added=None):
        super().__init__(parent)
        self.english = english.strip()
        self.on_added = on_added
        self.setWindowTitle(f"💡 So'z tahlili & Smart Insights: {self.english}")
        self.setMinimumSize(660, 600)
        self.resize(720, 650)
        t = theme_manager.get_active_theme()

        self.setStyleSheet(
            f"QDialog {{ background-color: {t.bg_app}; color: {t.text_main}; }} "
            f"QLabel {{ color: {t.text_main}; }}"
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Ma'lumotlarni olish
        self.details = global_dict_service.get_word_full_details(english=self.english)
        local_word = db.get_word_by_english(self.english)

        # 2. Header Card (So'z nomi, fonetika, audio va qo'shish holati)
        header_card = QFrame()
        header_card.setStyleSheet(
            f"background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 12px; padding: 12px 16px;"
        )
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(14)

        # Audio button
        audio_btn = QPushButton("🔊")
        audio_btn.setToolTip("Talaffuzni eshitish")
        audio_btn.setFixedSize(46, 46)
        audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        audio_btn.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
            f"border-radius: 10px; font-size: 20px; }} "
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        audio_btn.clicked.connect(lambda: tts.speak(self.english))
        h_layout.addWidget(audio_btn)

        mic_btn = QPushButton("🎙️")
        mic_btn.setToolTip("O'z talaffuzingizni sinash va baholash")
        mic_btn.setFixedSize(46, 46)
        mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mic_btn.setStyleSheet(
            "QPushButton { background-color: #BE123C; color: white; border: none; "
            "border-radius: 10px; font-size: 18px; } "
            "QPushButton:hover { background-color: #E11D48; }"
        )
        mic_btn.clicked.connect(self._open_pronunciation_test)
        h_layout.addWidget(mic_btn)

        # So'z nomi va transkripsiya
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        lbl_word = QLabel(self.english)
        lbl_word.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {t.text_main};")
        name_row.addWidget(lbl_word)

        # Fonetika va Part of speech
        ph_info = phonetics.get_word_info(self.english)
        ph = ph_info["phonetic"]
        if ph:
            lbl_ph = QLabel(ph)
            lbl_ph.setStyleSheet("color: #A5B4FC; font-size: 13px; font-weight: 500;")
            name_row.addWidget(lbl_ph)

        pos = self.details.get("pos", "") if self.details else ph_info["part_of_speech"]
        if pos:
            lbl_pos = QLabel(f"[{pos}]")
            lbl_pos.setStyleSheet(
                "background-color: #312E81; color: #C7D2FE; font-size: 11px; font-weight: 700; "
                "border-radius: 4px; padding: 2px 6px;"
            )
            name_row.addWidget(lbl_pos)

        name_row.addStretch()
        title_box.addLayout(name_row)

        star = self.details.get("star", "0") if self.details else "0"
        if star and star != "0":
            lbl_star = QLabel(f"★ Oxford chastotasi: {star}/3")
            lbl_star.setStyleSheet("color: #F59E0B; font-size: 11px; font-weight: 600;")
            title_box.addWidget(lbl_star)

        h_layout.addLayout(title_box, 1)

        # Holat yoki Qo'shish tugmasi
        is_in_study = local_word is not None
        if is_in_study:
            box_lvl = local_word["box_level"] or 1
            lbl_study = QLabel(f"✅ O'rganish rejasida (Box {box_lvl})")
            lbl_study.setStyleSheet(
                "background-color: #064E3B; color: #6EE7B7; font-size: 12px; font-weight: 700; "
                "border-radius: 8px; padding: 6px 12px;"
            )
            h_layout.addWidget(lbl_study)
        else:
            self.btn_add_study = QPushButton("➕ Shaxsiy rejaga qo'shish")
            self.btn_add_study.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_add_study.setStyleSheet(
                "QPushButton { background-color: #10B981; color: white; border: none; "
                "border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: 700; } "
                "QPushButton:hover { background-color: #059669; }"
            )
            self.btn_add_study.clicked.connect(self._add_to_study_action)
            h_layout.addWidget(self.btn_add_study)

        main_layout.addWidget(header_card)

        # 3. Asosiy mazmun (ScrollArea)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: transparent; }} "
            f"QScrollBar:vertical {{ background: {t.bg_card}; width: 8px; border-radius: 4px; }} "
            f"QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 4px; }}"
        )
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 4, 0, 4)
        content_layout.setSpacing(14)

        if not self.details:
            # Agar 64k bazada bo'lmasa, faqat lokal ma'lumotlarni ko'rsatamiz
            no_info_card = self._create_card(
                "ℹ️ Lug'at ma'lumoti",
                [local_word["uzbek"]] if local_word else ["Ma'lumot topilmadi."],
                icon="📖"
            )
            content_layout.addWidget(no_info_card)
        else:
            # A) O'zbekcha tarjimalar
            uz_list = self.details.get("uzbek_translations", [])
            if uz_list:
                tr_chips = "  •  ".join(uz_list)
                content_layout.addWidget(self._create_card("🇺🇿 O'zbekcha tarjimalar", [tr_chips], icon="🌐"))
            elif local_word:
                content_layout.addWidget(self._create_card("🇺🇿 O'zbekcha tarjimalar", [local_word["uzbek"]], icon="🌐"))

            # B) Misol gaplar (Examples)
            examples = self.details.get("examples", [])
            if not examples and local_word and local_word.get("example"):
                examples = [local_word["example"]]
            if examples:
                content_layout.addWidget(self._create_card("💡 Misol gaplar (Real Context)", examples[:5], icon="💬"))

            # C) So'zlar farqi (Differences - Oxford/Longman tahlili)
            diffs = self.details.get("differences", [])
            if diffs:
                diff_texts = []
                for d in diffs:
                    title_d = d.get("title", "")
                    body_d = d.get("body", "")
                    diff_texts.append(f"<b>{title_d}</b><br>{body_d.replace(chr(10), '<br>')}")
                content_layout.addWidget(self._create_card("⚖️ So'zlar nozik farqi (Difference Insights)", diff_texts, icon="⚖️"))

            # D) Turg'un birikmalar (Collocations)
            collocations = self.details.get("collocations", [])
            if collocations:
                colloc_texts = [c.replace(chr(10), "<br>") for c in collocations[:3]]
                content_layout.addWidget(self._create_card("🔗 Turg'un birikmalar (Collocations)", colloc_texts, icon="🔗"))

            # E) Tezaurus va Sinonimlar (Thesaurus)
            thesaurus = self.details.get("thesaurus", [])
            if thesaurus:
                thes_texts = [th.replace(chr(10), "<br>") for th in thesaurus[:3]]
                content_layout.addWidget(self._create_card("📚 Sinonimlar tahlili (Thesaurus)", thes_texts, icon="📚"))

            # F) Iboralar (Phrases)
            phrases = self.details.get("phrases", [])
            if phrases:
                phrase_texts = []
                for p in phrases:
                    phr = p.get("phrase", "")
                    tr = p.get("translation", "")
                    if tr:
                        phrase_texts.append(f"<b>{phr}</b> — {tr}")
                    else:
                        phrase_texts.append(f"<b>{phr}</b>")
                content_layout.addWidget(self._create_card("🗣️ Mashhur iboralar (Phrases)", phrase_texts, icon="🗣️"))

            # G) Grammatika (Grammar)
            grammars = self.details.get("grammar_notes", [])
            if grammars:
                grammar_texts = [g.replace(chr(10), "<br>") for g in grammars[:2]]
                content_layout.addWidget(self._create_card("📝 Grammatika eslatmasi", grammar_texts, icon="📝"))

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, 1)

        # 4. Yopish tugmasi
        btn_close = QPushButton("Yopish")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.primary_light}; border: 1px solid {t.border}; "
            f"border-radius: 11px; padding: 4px 12px; font-size: 12px; font-weight: 700; }} "
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; border-color: {t.primary}; }}"
        )
        btn_close.clicked.connect(self.accept)

        b_row = QHBoxLayout()
        b_row.addStretch()
        b_row.addWidget(btn_close)
        main_layout.addLayout(b_row)

    def _create_card(self, title: str, items: list[str], icon: str = "") -> QFrame:
        t = theme_manager.get_active_theme()
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 12px; }} "
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        lbl_t = QLabel(f"{icon} {title}")
        lbl_t.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {t.primary_light};")
        lay.addWidget(lbl_t)

        for item in items:
            lbl_item = QLabel(item)
            lbl_item.setWordWrap(True)
            lbl_item.setStyleSheet(f"font-size: 13px; color: {t.text_main}; line-height: 1.5;")
            lay.addWidget(lbl_item)

        return card

    def _add_to_study_action(self):
        uz = self.details.get("uzbek_str", "") if self.details else ""
        ex = self.details["examples"][0] if (self.details and self.details.get("examples")) else ""
        success, msg, w_id = global_dict_service.add_to_study_list(self.english, uz, ex)
        if success:
            self.btn_add_study.setText("✅ Rejaga qo'shildi")
            self.btn_add_study.setStyleSheet(
                "QPushButton { background-color: #064E3B; color: #6EE7B7; border: none; "
                "border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: 700; }"
            )
            self.btn_add_study.setEnabled(False)
            if self.on_added:
                self.on_added()
        else:
            QMessageBox.information(self, "Ma'lumot", msg)

    def _open_pronunciation_test(self):
        """Ushbu so'z uchun talaffuzni sinash va baholash dialogini ochish."""
        try:
            import speech_recognizer
            ph_info = phonetics.get_word_info(self.english)
            uz_text = ""
            if self.details and self.details.get("uzbek_translations"):
                uz_text = ", ".join(self.details["uzbek_translations"])
            elif self.local_word:
                uz_text = self.local_word.get("uzbek", "")

            word_data = {
                "english": self.english,
                "uzbek": uz_text,
                "phonetic": ph_info.get("phonetic", ""),
            }
            speech_recognizer.open_pronunciation_dialog(word_data, parent=self)
        except Exception as e:
            logger.error(f"Talaffuz dialogini ochishda xatolik: {e}")


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
    """Jadval kataklari uchun fallback chip vidjeti."""
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
        self.header_title = QLabel("📖 Lug'at va so'zlar bazasi")
        self.header_title.setStyleSheet("font-size: 22px; font-weight: 700;")
        top_row.addWidget(self.header_title)
        top_row.addStretch()

        self.export_csv_btn = QPushButton("📥 CSV Eksport")
        self.export_csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_csv_btn.clicked.connect(self.export_csv)
        top_row.addWidget(self.export_csv_btn)

        self.export_json_btn = QPushButton("📥 JSON Eksport")
        self.export_json_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_json_btn.clicked.connect(self.export_json)
        top_row.addWidget(self.export_json_btn)

        self.packs_btn = QPushButton("📚 Tayyor to'plamlar (Word Packs)")
        self.packs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.packs_btn.clicked.connect(self.open_word_packs)
        top_row.addWidget(self.packs_btn)

        self.print_btn = QPushButton("🖨️ Chop etish / PDF")
        self.print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.print_btn.clicked.connect(self.open_worksheet_generator)
        top_row.addWidget(self.print_btn)

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

        # --- 2.1. 64,000 so'zlik Global Lug'at tavsiyalar banneri ---
        self.global_banner = QFrame()
        self.global_banner.setStyleSheet(
            "background-color: #1E1B4B; border: 1.5px solid #6366F1; border-radius: 12px; padding: 10px 14px;"
        )
        self.global_banner_layout = QHBoxLayout(self.global_banner)
        self.global_banner_layout.setContentsMargins(10, 6, 10, 6)
        self.global_banner_layout.setSpacing(10)
        self.global_banner.setVisible(False)
        layout.addWidget(self.global_banner)

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
        self.table.setColumnWidth(5, 145)  # Amallar (Smart Insights 💡, Tahrirlash ✏️, O'chirish 🗑️)

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
        self.table.verticalHeader().setDefaultSectionSize(54)

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
                font-size: 14px;
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
                font-size: 13px;
                font-weight: 700;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #2A2A3E;
            }
            """
        )
        self.table.setItemDelegateForColumn(1, EnglishCellDelegate(self))
        self.table.setItemDelegateForColumn(2, UzbekCellDelegate(self))
        self.table.setItemDelegateForColumn(3, PillBadgeDelegate(self))
        self.table.setItemDelegateForColumn(4, PillBadgeDelegate(self))
        self.table.setItemDelegateForColumn(5, ActionsCellDelegate(self))

        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        layout.addWidget(self.table)

        # --- 4. Footer ---
        footer = QHBoxLayout()
        self.count_label = QLabel("Jami so'zlar: 0")
        self.count_label.setStyleSheet("color: #9CA3AF; font-size: 13px; font-weight: 500;")
        footer.addWidget(self.count_label)
        footer.addStretch()

        self.hint_label = QLabel("💡 Maslahat: Har bir so'z oldidagi 🔊 karnay tugmasini bosib, darhol talaffuzini eshiting!")
        self.hint_label.setStyleSheet("color: #818CF8; font-size: 12px;")
        footer.addWidget(self.hint_label)

        layout.addLayout(footer)

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        # Tezkor boshlanish: so'zlar jadvalini navbat orqali chaqirish (UI muzlamaydi)
        QTimer.singleShot(0, self.load_words)

    def focus_search(self):
        """Ctrl + F: Qidiruv qatoriga fokus berish va mavjud matnni belgilash."""
        if hasattr(self, "search_input") and self.search_input:
            self.search_input.setFocus()
            self.search_input.selectAll()

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
        if hasattr(self, "header_title"):
            self.header_title.setStyleSheet(f"color: {t.text_main}; font-size: 22px; font-weight: 700;")
        if hasattr(self, "export_csv_btn"):
            if t.is_dark:
                self.export_csv_btn.setStyleSheet(
                    "QPushButton { background-color: #1E1E2E; color: #10B981; border: 1px solid #10B981;"
                    "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
                    "QPushButton:hover { background-color: #064E3B; color: white; }"
                )
            else:
                self.export_csv_btn.setStyleSheet(
                    "QPushButton { background-color: #ECFDF5; color: #059669; border: 1px solid #10B981;"
                    "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
                    "QPushButton:hover { background-color: #D1FAE5; }"
                )
        if hasattr(self, "export_json_btn"):
            if t.is_dark:
                self.export_json_btn.setStyleSheet(
                    "QPushButton { background-color: #1E1E2E; color: #818CF8; border: 1px solid #6366F1;"
                    "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
                    "QPushButton:hover { background-color: #312E81; color: white; }"
                )
            else:
                self.export_json_btn.setStyleSheet(
                    "QPushButton { background-color: #EEF2FF; color: #4F46E5; border: 1px solid #6366F1;"
                    "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
                    "QPushButton:hover { background-color: #E0E7FF; }"
                )
        if hasattr(self, "packs_btn"):
            self.packs_btn.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border: 1px solid {t.primary};"
                f"border-radius: 8px; padding: 7px 16px; font-size: 12px; font-weight: 700; }}"
                f"QPushButton:hover {{ background-color: {t.primary_hover}; }}"
            )
        if hasattr(self, "print_btn"):
            if t.is_dark:
                self.print_btn.setStyleSheet(
                    "QPushButton { background-color: #1E1E2E; color: #F59E0B; border: 1px solid #F59E0B;"
                    "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
                    "QPushButton:hover { background-color: #78350F; color: white; }"
                )
            else:
                self.print_btn.setStyleSheet(
                    "QPushButton { background-color: #FFFBEB; color: #D97706; border: 1px solid #F59E0B;"
                    "border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }"
                    "QPushButton:hover { background-color: #FEF3C7; }"
                )
        if hasattr(self, "global_banner"):
            if t.is_dark:
                self.global_banner.setStyleSheet(
                    "background-color: #1E1B4B; border: 1.5px solid #6366F1; border-radius: 12px; padding: 10px 14px;"
                )
            else:
                self.global_banner.setStyleSheet(
                    "background-color: #EEF2FF; border: 1.5px solid #818CF8; border-radius: 12px; padding: 10px 14px;"
                )
        if hasattr(self, "count_label"):
            self.count_label.setStyleSheet(f"color: {t.text_muted}; font-size: 13px; font-weight: 500;")
        if hasattr(self, "hint_label"):
            self.hint_label.setStyleSheet(f"color: {t.primary_light if not t.is_dark else '#818CF8'}; font-size: 12px;")
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
                    font-size: 14px;
                    selection-background-color: {t.primary};
                    selection-color: #FFFFFF;
                    outline: none;
                }}
                QTableWidget::item {{
                    padding-left: 8px;
                    padding-right: 8px;
                    border: none;
                }}
                QTableWidget::item:selected {{
                    background-color: {t.primary};
                    color: #FFFFFF;
                }}
                QHeaderView::section {{
                    background-color: {t.bg_card};
                    color: {t.text_muted};
                    font-size: 13px;
                    font-weight: 700;
                    padding: 10px 8px;
                    border: none;
                    border-bottom: 2px solid {t.border};
                }}
                """
            )
            self.table.viewport().update()
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

        # Agar shaxsiy bazada topilmasa va qidiruv kiritilgan bo'lsa, 64k bazadan tavsiya
        clean_q = query.strip()
        if len(rows) == 0 and clean_q:
            global_matches = global_dict_service.search_global_words(clean_q, limit=3)
            if global_matches:
                self._update_global_banner(global_matches)
                self.global_banner.setVisible(True)
            else:
                self.global_banner.setVisible(False)
        else:
            self.global_banner.setVisible(False)

        # Leitner Box va Status ranglari (Mavzuga mos zamonaviy chip palitrasi)
        t = theme_manager.get_active_theme()
        is_dark = t.is_dark

        if is_dark:
            box_badges = {
                0: ("Box 0", "#1F2937", "#9CA3AF", "#374151"),
                1: ("Box 1", "#1E2A4A", "#60A5FA", "#2563EB"),
                2: ("Box 2", "#281D4A", "#A78BFA", "#7C3AED"),
                3: ("Box 3", "#33220A", "#FBBF24", "#D97706"),
                4: ("Box 4", "#0D3322", "#34D399", "#059669"),
                5: ("Box 5", "#083328", "#2DD4BF", "#0D9488"),
            }
            status_badges = {
                "new": ("Yangi", "#1E293B", "#38BDF8", "#0284C7"),
                "learning": ("O'rganilmoqda", "#2E1A0F", "#FB923C", "#C2410C"),
                "mastered": ("O'zlashtirilgan", "#062E1F", "#34D399", "#059669"),
            }
            id_color = QColor("#6B7280")
        else:
            box_badges = {
                0: ("Box 0", "#F1F5F9", "#475569", "#CBD5E1"),
                1: ("Box 1", "#EFF6FF", "#1D4ED8", "#BFDBFE"),
                2: ("Box 2", "#F5F3FF", "#6D28D9", "#DDD6FE"),
                3: ("Box 3", "#FFFBEB", "#B45309", "#FDE68A"),
                4: ("Box 4", "#ECFDF5", "#047857", "#A7F3D0"),
                5: ("Box 5", "#F0FDFA", "#0F766E", "#99F6E4"),
            }
            status_badges = {
                "new": ("Yangi", "#F0F9FF", "#0369A1", "#BAE6FD"),
                "learning": ("O'rganilmoqda", "#FFF7ED", "#C2410C", "#FFEDD5"),
                "mastered": ("O'zlashtirilgan", "#F0FDF4", "#15803D", "#BBF7D0"),
            }
            id_color = QColor("#64748B")

        self.table.setUpdatesEnabled(False)
        for i, row in enumerate(rows):
            # 0: ID
            id_item = QTableWidgetItem(str(row["id"]))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setForeground(id_color)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, id_item)

            # 1: English (Karnay tugmasi, so'z, fonetika va part of speech)
            eng_word = row["english"]
            ph_val = row["phonetic"] if "phonetic" in row.keys() and row["phonetic"] else ""
            pos_val = row["part_of_speech"] if "part_of_speech" in row.keys() and row["part_of_speech"] else ""
            if not ph_val or not pos_val:
                ph_info = phonetics.get_word_info(eng_word)
                ph_val = ph_val or ph_info["phonetic"]
                pos_val = pos_val or ph_info["part_of_speech"]

            it1 = QTableWidgetItem()
            it1.setData(Qt.ItemDataRole.UserRole, {
                "english": eng_word,
                "phonetic": ph_val,
                "pos": pos_val
            })
            it1.setFlags(it1.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it1.setToolTip("Bosilsa talaffuz qilinadi, ikki marta bosilsa batafsil ma'lumot")
            self.table.setItem(i, 1, it1)

            # 2: Uzbek tarjimasi va misol gap
            ex = row["example"] if "example" in row.keys() and row["example"] else ""
            it2 = QTableWidgetItem()
            it2.setData(Qt.ItemDataRole.UserRole, {
                "uzbek": row["uzbek"],
                "example": ex
            })
            if ex:
                it2.setToolTip(f"Misol: {ex}")
            it2.setFlags(it2.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, it2)

            # 3: Leitner Box chipi
            box = row["box_level"] or 0
            b_text, b_bg, b_fg, b_border = box_badges.get(box, (f"Box {box}", "#1F2937", "#9CA3AF", "#374151"))
            it3 = QTableWidgetItem()
            it3.setData(Qt.ItemDataRole.UserRole, {
                "text": b_text,
                "bg": b_bg,
                "fg": b_fg,
                "border": b_border
            })
            it3.setFlags(it3.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 3, it3)

            # 4: Status chipi
            st = row["status"] or "new"
            s_text, s_bg, s_fg, s_border = status_badges.get(st, (st, "#1E293B", "#38BDF8", "#0284C7"))
            it4 = QTableWidgetItem()
            it4.setData(Qt.ItemDataRole.UserRole, {
                "text": s_text,
                "bg": s_bg,
                "fg": s_fg,
                "border": s_border
            })
            it4.setFlags(it4.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 4, it4)

            # 5: Amallar (Smart Insights 💡, Tahrirlash ✏️, O'chirish 🗑️)
            it5 = QTableWidgetItem()
            it5.setData(Qt.ItemDataRole.UserRole, {
                "id": row["id"],
                "english": eng_word,
                "uzbek": row["uzbek"],
                "example": ex
            })
            it5.setFlags(it5.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it5.setToolTip("💡 Smart Insights | ✏️ Tahrirlash | 🗑️ O'chirish")
            self.table.setItem(i, 5, it5)

        self.table.setUpdatesEnabled(True)

        self.count_label.setText(f"Ko'rsatilmoqda: {len(rows)} ta so'z")

    def _update_global_banner(self, matches: list[dict]):
        """64,000 so'zlik bazadan topilgan natijalarni chiroyli bannerda ko'rsatish."""
        while self.global_banner_layout.count():
            item = self.global_banner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl = QLabel("🌐 64,000 so'zlik lug'atdan tavsiya:")
        lbl.setStyleSheet("color: #C7D2FE; font-size: 12px; font-weight: 700;")
        self.global_banner_layout.addWidget(lbl)

        for m in matches:
            eng = m.get("english", "")
            uz = m.get("uzbek", "")
            btn = QPushButton(f"➕ {eng} ({uz[:25]}...)")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color: #312E81; color: #E0E7FF; border: 1px solid #4F46E5;"
                "border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background-color: #10B981; color: white; border-color: #10B981; }"
            )
            btn.clicked.connect(lambda checked, w=m: self._quick_add_from_banner(w))
            self.global_banner_layout.addWidget(btn)

        self.global_banner_layout.addStretch()

    def _quick_add_from_banner(self, word_data: dict):
        eng = word_data.get("english", "")
        uz = word_data.get("uzbek", "")
        ex = word_data.get("example", "")
        success, msg, w_id = global_dict_service.add_to_study_list(eng, uz, ex)
        if success:
            self.load_words()
            if self.on_words_changed:
                self.on_words_changed()
            QMessageBox.information(self, "Muvaffaqiyatli", f"'{eng}' so'zi o'rganish rejangizga qo'shildi!")

    def open_word_details(self, english: str):
        """So'zning to'liq ensiklopedik tahlil modalini ochish."""
        dlg = WordDetailsDialog(self, english, on_added=self._on_word_added_from_details)
        dlg.exec()

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
                self.open_word_details(word_row["english"])

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

    def open_worksheet_generator(self):
        """Chop etish va flashcardlar dialogini ochish."""
        dlg = WorksheetGeneratorDialog(self)
        dlg.exec()

