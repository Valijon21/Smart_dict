"""
Vocab Master Pro — Spotlight / Raycast Fast Search.
Tezkor universal qidiruv paneli (Alt + Space).
Lug'atdagi so'zlar, tarjimalar, misollar va teglarni bir zumda topish,
talaffuzini eshitish va yangi so'zlarni 1-bosish bilan bazaga qo'shish.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QColor, QKeyEvent, QGuiApplication

import database as db
import tts
import theme_manager
import global_dict_service
try:
    from utils import text_search_utils
except ImportError:
    import text_search_utils
from logger import get_logger

logger = get_logger("spotlight_search")


class SpotlightResultItemWidget(QWidget):
    """Qidiruv natijalari ro'yxatidagi har bir so'zning zamonaviy kartasi."""
    def __init__(self, word_data: dict, on_quick_add=None, parent=None):
        super().__init__(parent)
        wd = dict(word_data) if not isinstance(word_data, dict) else word_data
        self.word_data = wd
        self.on_quick_add = on_quick_add
        t = theme_manager.get_active_theme()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Chap: Inglizcha so'z va transkripsiya
        left_col = QVBoxLayout()
        left_col.setSpacing(2)

        en_row = QHBoxLayout()
        en_row.setSpacing(8)
        self.lbl_en = QLabel(wd.get("english", ""))
        self.lbl_en.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {t.text_main};")
        en_row.addWidget(self.lbl_en)

        ph = wd.get("phonetic", "").strip()
        if ph:
            lbl_ph = QLabel(f"/{ph}/")
            lbl_ph.setStyleSheet("color: #A5B4FC; font-size: 12px; font-weight: 500;")
            en_row.addWidget(lbl_ph)

        pos = wd.get("part_of_speech", "") or wd.get("pos", "")
        pos = pos.strip()
        if pos:
            lbl_pos = QLabel(f"[{pos}]")
            lbl_pos.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 600;")
            en_row.addWidget(lbl_pos)

        en_row.addStretch()
        left_col.addLayout(en_row)

        self.lbl_uz = QLabel(wd.get("uzbek", ""))
        self.lbl_uz.setStyleSheet(f"font-size: 13px; color: {t.text_muted};")
        left_col.addWidget(self.lbl_uz)

        layout.addLayout(left_col, 1)

        # O'ng: Leitner Box yoki Global Lug'at holati
        is_global = wd.get("source") == "global" or wd.get("is_global", False)

        if not is_global:
            box = wd.get("box_level", wd.get("box", 1))
            lbl_box = QLabel(f"Box {box}")
            lbl_box.setStyleSheet(
                "background-color: #1E1B4B; color: #C7D2FE; font-size: 11px; font-weight: 700; "
                "border-radius: 6px; padding: 3px 8px;"
            )
            layout.addWidget(lbl_box)
        else:
            in_study = wd.get("is_in_study_list", False)
            if in_study:
                lbl_status = QLabel("✅ O'rganilmoqda")
                lbl_status.setStyleSheet(
                    "background-color: #064E3B; color: #6EE7B7; font-size: 11px; font-weight: 700; "
                    "border-radius: 6px; padding: 3px 8px;"
                )
                layout.addWidget(lbl_status)
            else:
                lbl_badge = QLabel("🌐 64k")
                lbl_badge.setStyleSheet(
                    "background-color: #1E293B; color: #94A3B8; font-size: 11px; font-weight: 600; "
                    "border-radius: 6px; padding: 3px 6px;"
                )
                layout.addWidget(lbl_badge)

                self.btn_add = QPushButton("➕ Qo'shish")
                self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
                self.btn_add.setStyleSheet(
                    "QPushButton { background-color: #10B981; color: white; border: none; "
                    "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; } "
                    "QPushButton:hover { background-color: #059669; }"
                )
                self.btn_add.clicked.connect(self._handle_add_click)
                layout.addWidget(self.btn_add)

    def _handle_add_click(self):
        if self.on_quick_add:
            success = self.on_quick_add(self.word_data)
            if success and hasattr(self, "btn_add"):
                self.btn_add.setText("✅ Qo'shildi")
                self.btn_add.setStyleSheet(
                    "QPushButton { background-color: #065F46; color: #A7F3D0; border: none; "
                    "border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; }"
                )
                self.btn_add.setEnabled(False)


class SpotlightSearchDialog(QDialog):
    """
    Spotlight / Raycast uslubidagi suzuvchi tezkor qidiruv modali.
    Alt + Space yoki Ctrl + Shift + F orqali ochiladi.
    """
    word_selected = pyqtSignal(dict)       # Lug'atda ochish uchun
    quick_add_requested = pyqtSignal(str)  # Yangi so'z qo'shish uchun

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(700, 520)
        self.setMinimumSize(620, 440)
        self.setMaximumSize(900, 720)

        self.current_results: list[dict] = []
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(120)  # 120ms debounce
        self.search_timer.timeout.connect(self._do_search)

        self._build_ui()
        self._center_on_screen()

    def _center_on_screen(self):
        """Ekranning yuqori qismida zamonaviy va xavfsiz markazlashtirish."""
        screen = None
        if self.parent() and hasattr(self.parent(), "screen") and self.parent().screen():
            screen = self.parent().screen()
        if not screen:
            screen = self.screen() or QGuiApplication.primaryScreen()

        if screen:
            avail = screen.availableGeometry()
            w = max(self.minimumWidth(), min(self.width(), avail.width() - 40))
            h = max(self.minimumHeight(), min(self.height(), avail.height() - 60))
            x = avail.x() + max(0, (avail.width() - w) // 2)
            y = avail.y() + max(30, (avail.height() - h) // 4)
            self.setGeometry(x, y, w, h)

    def _build_ui(self):
        t = theme_manager.get_active_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Tashqi konteyner (Shadow + Border + Glass effect)
        self.card = QFrame()
        self.card.setObjectName("SpotlightCard")
        self.card.setStyleSheet(
            f"QFrame#SpotlightCard {{ "
            f"background-color: {t.bg_app}; border: 1.5px solid {t.primary}; border-radius: 16px; "
            f"}}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        # 1. Qidiruv qatori
        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        icon_lbl = QLabel("🔍")
        icon_lbl.setStyleSheet("font-size: 18px;")
        search_row.addWidget(icon_lbl)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("So'z, tarjima, misol yoki tegni qidiring...")
        self.search_input.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {t.text_main}; border: none; "
            f"font-size: 16px; font-weight: 600; padding: 6px 0; }} "
            f"QLineEdit:focus {{ border: none; }}"
        )
        self.search_input.textChanged.connect(self._on_text_changed)
        search_row.addWidget(self.search_input, 1)

        badge_shortcut = QLabel("Alt + Space  |  Esc")
        badge_shortcut.setStyleSheet(
            f"background-color: {t.bg_card}; color: {t.text_muted}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 4px 8px; font-size: 11px; font-weight: 600;"
        )
        search_row.addWidget(badge_shortcut)
        card_layout.addLayout(search_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.border}; max-height: 1px;")
        card_layout.addWidget(sep)

        # 2. Natijalar ro'yxati
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; outline: none; }} "
            f"QListWidget::item {{ border-radius: 10px; margin-bottom: 3px; }} "
            f"QListWidget::item:selected {{ background-color: {t.bg_card_secondary}; border: 1px solid {t.primary}; }} "
            f"QListWidget::item:hover:!selected {{ background-color: {t.bg_card}; }}"
        )
        self.results_list.currentItemChanged.connect(self._on_item_selected)
        self.results_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        card_layout.addWidget(self.results_list, 1)

        # 3. Pastki Tafsilot va Amal paneli
        self.detail_frame = QFrame()
        self.detail_frame.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border-radius: 10px; padding: 8px 12px; }}"
        )
        detail_layout = QHBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(10, 6, 10, 6)
        detail_layout.setSpacing(10)

        self.lbl_action_hint = QLabel("💡 Tanlash: ↑/↓ | Talaffuz: Space | Lug'atda ochish: Enter")
        self.lbl_action_hint.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
        detail_layout.addWidget(self.lbl_action_hint)
        detail_layout.addStretch()

        self.btn_speak = QPushButton("🔊 Talaffuz")
        self.btn_speak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speak.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 6px; padding: 4px 10px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {t.primary}; color: {t.primary}; }}"
        )
        self.btn_speak.clicked.connect(self._speak_selected)
        detail_layout.addWidget(self.btn_speak)

        self.btn_open_dict = QPushButton("📖 Lug'atda ochish")
        self.btn_open_dict.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_dict.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; "
            f"border-radius: 6px; padding: 4px 12px; font-size: 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        self.btn_open_dict.clicked.connect(self._open_in_dict)
        detail_layout.addWidget(self.btn_open_dict)

        self.btn_add_new = QPushButton("➕ Lug'atga qo'shish")
        self.btn_add_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_new.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; border-radius: 6px; "
            "padding: 4px 12px; font-size: 12px; font-weight: 600; } "
            "QPushButton:hover { background-color: #059669; }"
        )
        self.btn_add_new.clicked.connect(self._request_quick_add)
        self.btn_add_new.setVisible(False)
        detail_layout.addWidget(self.btn_add_new)

        card_layout.addWidget(self.detail_frame)
        main_layout.addWidget(self.card)

    def show_spotlight(self, prefill_text: str = ""):
        """Spotlight panelini ochish va fokus berish."""
        self._center_on_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()
        if prefill_text:
            self.search_input.setText(prefill_text)
            self.search_input.selectAll()
        else:
            self.search_input.clear()
            self._do_search()

    def _on_text_changed(self, text: str):
        self.search_timer.start()

    def _do_search(self):
        query = self.search_input.text().strip()
        self.results_list.clear()
        self.current_results = []

        if not query:
            # Eng so'nggi qo'shilgan 15 ta so'zni ko'rsatish
            raw_rows = db.get_latest_added_words(limit=15)
            rows = [dict(r) for r in raw_rows]
            for r in rows:
                r["source"] = "personal"
            local_count = len(rows)
            global_count = 0
        else:
            raw_local = db.search_words(query, limit=20)
            local_rows = [dict(r) for r in raw_local]
            for r in local_rows:
                r["source"] = "personal"
            global_rows = global_dict_service.search_global_words(query, limit=25)

            # Shaxsiy va global bazani dublikatsiz birlashtirish
            local_engs = {r["english"].strip().lower() for r in local_rows}
            clean_global = [g for g in global_rows if g["english"].strip().lower() not in local_engs]

            rows = local_rows + clean_global

            # Aniq moslik (Rank 0) har doim eng yuqorida turishi uchun professional saralash
            def _spotlight_sort_key(item):
                if isinstance(item, dict):
                    eng = item.get("english", "")
                    uz = item.get("uzbek", "")
                    r_rank = item.get("match_rank")
                    is_personal = 0 if item.get("source") != "global" else 1
                    star_val = item.get("star", "0")
                else:
                    eng = item["english"]
                    uz = item["uzbek"]
                    r_rank = item["match_rank"] if "match_rank" in item.keys() else None
                    is_personal = 0
                    star_val = "0"

                if r_rank is None:
                    r_rank = text_search_utils.calculate_match_rank(query, eng, uz)
                star_num = int(star_val) if str(star_val).isdigit() else 0
                return (r_rank, is_personal, -star_num, len(eng))

            rows.sort(key=_spotlight_sort_key)
            local_count = len(local_rows)
            global_count = len(clean_global)

        self.current_results = rows

        if not rows:
            self.btn_speak.setVisible(False)
            self.btn_open_dict.setVisible(False)
            self.btn_add_new.setVisible(bool(query))
            if query:
                self.lbl_action_hint.setText(f"'{query}' so'zi topilmadi. Uni bazaga qo'shishingiz mumkin:")
            else:
                self.lbl_action_hint.setText("Qidirish uchun biron so'z yoki tarjima yozing.")
            return

        self.btn_speak.setVisible(True)
        self.btn_open_dict.setVisible(True)
        self.btn_add_new.setVisible(False)

        if not query:
            self.lbl_action_hint.setText(f"Shaxsiy lug'at: {local_count} ta so'z  |  ↑/↓: Navigatsiya")
        else:
            hint_parts = []
            if local_count > 0:
                hint_parts.append(f"{local_count} ta shaxsiy")
            if global_count > 0:
                hint_parts.append(f"{global_count} ta 64k lug'atdan")
            self.lbl_action_hint.setText(f"Topildi: {' + '.join(hint_parts)}  |  Enter: Tanlash / Ochish")

        for r in rows:
            item = QListWidgetItem(self.results_list)
            item.setData(Qt.ItemDataRole.UserRole, r)
            w = SpotlightResultItemWidget(r, on_quick_add=self._quick_add_global_word)
            item.setSizeHint(w.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, w)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def _quick_add_global_word(self, word_data: dict) -> bool:
        """Global lug'atdagi so'zni shaxsiy ro'yxatga tezkor qo'shish."""
        eng = word_data.get("english", "").strip()
        uz = word_data.get("uzbek", "")
        ex = word_data.get("example", "")
        success, msg, w_id = global_dict_service.add_to_study_list(eng, uz, ex)
        if success:
            word_data["is_in_study_list"] = True
            word_data["local_id"] = w_id
            self.lbl_action_hint.setText(f"🎉 {msg}")
            return True
        else:
            self.lbl_action_hint.setText(f"ℹ️ {msg}")
            return False

    def _on_item_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            return
        raw = current.data(Qt.ItemDataRole.UserRole)
        data = dict(raw) if raw and not isinstance(raw, dict) else raw
        if data:
            eng = data.get("english", "")
            uz = data.get("uzbek", "")
            ex = data.get("example", "")
            is_global = data.get("source") == "global" or data.get("is_global", False)

            if ex:
                self.lbl_action_hint.setText(f"💡 Misol: \"{ex[:60]}...\"" if len(ex) > 60 else f"💡 Misol: \"{ex}\"")
            elif is_global:
                self.lbl_action_hint.setText(f"🌐 64k Lug'at: {eng} — {uz}")
            else:
                self.lbl_action_hint.setText(f"📖 {eng} — {uz}")

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._open_in_dict()

    def _speak_selected(self):
        cur = self.results_list.currentItem()
        if not cur:
            return
        raw = cur.data(Qt.ItemDataRole.UserRole)
        data = dict(raw) if raw and not isinstance(raw, dict) else raw
        if data and data.get("english"):
            tts.speak(data["english"])

    def _open_in_dict(self):
        cur = self.results_list.currentItem()
        if not cur:
            return
        raw = cur.data(Qt.ItemDataRole.UserRole)
        data = dict(raw) if raw and not isinstance(raw, dict) else raw
        if not data:
            return

        is_global = data.get("source") == "global" or data.get("is_global", False)
        if is_global:
            # Agar so'z hali shaxsiy bazada bo'lmasa, uni avtomatik qo'shib keyin ochamiz
            if not data.get("is_in_study_list"):
                global_dict_service.add_to_study_list(
                    data.get("english", ""),
                    data.get("uzbek", ""),
                    data.get("example", "")
                )
            local_row = db.get_word_by_english(data.get("english", ""))
            if local_row:
                self.word_selected.emit(dict(local_row))
            else:
                self.word_selected.emit(data)
        else:
            self.word_selected.emit(data)

        self.close()

    def _request_quick_add(self):
        text = self.search_input.text().strip()
        self.quick_add_requested.emit(text)
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        elif key == Qt.Key.Key_Down:
            cur = self.results_list.currentRow()
            if cur < self.results_list.count() - 1:
                self.results_list.setCurrentRow(cur + 1)
            event.accept()
            return
        elif key == Qt.Key.Key_Up:
            cur = self.results_list.currentRow()
            if cur > 0:
                self.results_list.setCurrentRow(cur - 1)
            event.accept()
            return
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.btn_add_new.isVisible() and self.results_list.count() == 0:
                self._request_quick_add()
            else:
                self._open_in_dict()
            event.accept()
            return
        elif key == Qt.Key.Key_Space:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier or not self.search_input.hasFocus():
                self._speak_selected()
                event.accept()
                return

        super().keyPressEvent(event)
