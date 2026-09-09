"""
Vocab Master Pro — Global Clipboard Auto-Lookup Monitor & Toast Popup.
Foydalanuvchi Windows tizimidagi har qanday dasturda (Chrome, Word, Telegram, PDF Reader)
inglizcha so'z ustida 'Ctrl+C' bosganda, ushbu modul avtomatik ravishda 64k Oxford
lug'atidan so'z ma'nosini topadi va ekranning pastki o'ng burchagida ixcham, zamonaviy,
foydalanuvchi ishini to'xtatmaydigan (non-intrusive floating toast) popup taqdim etadi.
"""
import re
import time
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QWidget
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor, QFont

import database as db
import global_dict_service
import phonetics
import tts
import theme_manager
from logger import get_logger

logger = get_logger("clipboard_monitor")


class ClipboardPopupDialog(QDialog):
    """
    Ekranning pastki o'ng burchagida chiquvchi zamonaviy suzuvchi tarjima oynasi.
    Aktiv oynaning fokusini olib qo'ymaydi (WA_ShowWithoutActivating).
    """
    word_added = pyqtSignal()

    def __init__(self, word_data: dict, parent=None):
        super().__init__(parent)
        self.word_data = word_data
        self.english = word_data.get("english", "").strip()
        self.uzbek = word_data.get("uzbek", "").strip()
        self.phonetic = word_data.get("phonetic", "").strip()
        self.example = word_data.get("example", "").strip()
        self.star = word_data.get("star", "0")
        self.is_pinned = False

        # Oyna xususiyatlari: Frameless, Top-most, ToolTip/Splash
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setFixedWidth(380)
        self._build_ui()
        self._position_on_screen()

        # Avtomatik yopilish taymeri (8 soniya)
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setInterval(8000)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self._auto_close)
        self.auto_close_timer.start()

    def _build_ui(self):
        t = theme_manager.get_active_theme()
        self.setStyleSheet(
            f"QDialog {{ background-color: {t.bg_card}; color: {t.text_main}; "
            f"border: 1.5px solid {t.primary}; border-radius: 14px; }}"
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 14)
        main_layout.setSpacing(10)

        # 1. Header: Kichik nishon + Pin + Close
        head_row = QHBoxLayout()
        head_row.setSpacing(8)

        lbl_badge = QLabel("📋 TEZKOR TARJIMA")
        lbl_badge.setStyleSheet(
            f"background-color: {t.primary}22; color: {t.primary}; font-size: 11px; font-weight: 800; "
            f"border: 1px solid {t.primary}55; border-radius: 5px; padding: 2px 7px;"
        )
        head_row.addWidget(lbl_badge)

        if self.star and self.star != "0":
            lbl_star = QLabel(f"★ {self.star}/3")
            lbl_star.setStyleSheet("color: #F59E0B; font-size: 11px; font-weight: 700;")
            head_row.addWidget(lbl_star)

        head_row.addStretch()

        # Pin tugmasi (avtomatik yopilishni to'xtatish)
        self.btn_pin = QPushButton("📌")
        self.btn_pin.setToolTip("Oynani qadash (avto-yopilishni to'xtatish)")
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pin.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 12px; } "
            "QPushButton:hover { background: #374151; border-radius: 12px; }"
        )
        self.btn_pin.clicked.connect(self._toggle_pin)
        head_row.addWidget(self.btn_pin)

        # Close tugmasi
        btn_close = QPushButton("✕")
        btn_close.setToolTip("Yopish")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #9CA3AF; font-size: 13px; font-weight: 700; } "
            "QPushButton:hover { background: #EF4444; color: white; border-radius: 12px; }"
        )
        btn_close.clicked.connect(self.close)
        head_row.addWidget(btn_close)

        main_layout.addLayout(head_row)

        # 2. Asosiy so'z qatori: English + Pronounce + Mic
        word_row = QHBoxLayout()
        word_row.setSpacing(8)

        lbl_eng = QLabel(self.english)
        lbl_eng.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {t.text_main};")
        word_row.addWidget(lbl_eng)

        if self.phonetic:
            lbl_ph = QLabel(f"/{self.phonetic}/")
            lbl_ph.setStyleSheet("color: #A5B4FC; font-size: 13px; font-weight: 600;")
            word_row.addWidget(lbl_ph)

        word_row.addStretch()

        # Ovozli talaffuz (TTS)
        btn_tts = QPushButton("🔊")
        btn_tts.setToolTip("Talaffuzni tinglash")
        btn_tts.setFixedSize(30, 30)
        btn_tts.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tts.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.primary}; "
            f"border: 1px solid {t.border}; border-radius: 8px; font-size: 14px; }} "
            f"QPushButton:hover {{ background-color: {t.primary}; color: white; }}"
        )
        btn_tts.clicked.connect(lambda: tts.speak(self.english))
        word_row.addWidget(btn_tts)

        # Talaffuzni sinash (Speech Recognizer)
        btn_speech = QPushButton("🎙️")
        btn_speech.setToolTip("Talaffuzingizni sinash va baholash")
        btn_speech.setFixedSize(30, 30)
        btn_speech.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_speech.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: #F43F5E; "
            f"border: 1px solid {t.border}; border-radius: 8px; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: #E11D48; color: white; }}"
        )
        btn_speech.clicked.connect(self._open_speech_dialog)
        word_row.addWidget(btn_speech)

        main_layout.addLayout(word_row)

        # 3. O'zbekcha tarjima
        lbl_uz = QLabel(self.uzbek or "Tarjima yuklanmoqda...")
        lbl_uz.setWordWrap(True)
        lbl_uz.setStyleSheet(f"font-size: 14px; font-weight: 600; color: #34D399; line-height: 1.3;")
        main_layout.addWidget(lbl_uz)

        # 4. Misol gap (agar mavjud bo'lsa)
        if self.example:
            lbl_ex = QLabel(f"💡 <i>\"{self.example}\"</i>")
            lbl_ex.setWordWrap(True)
            lbl_ex.setStyleSheet(f"font-size: 12px; color: {t.text_muted};")
            main_layout.addWidget(lbl_ex)

        # 5. Pastki amallar qatori: "➕ Qo'shish" va "📖 Batafsil"
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        local_word = db.get_word_by_english(self.english)
        self.btn_add = QPushButton()
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)

        if local_word:
            self.btn_add.setText("✅ Lug'atda mavjud")
            self.btn_add.setEnabled(False)
            self.btn_add.setStyleSheet(
                "QPushButton { background-color: #064E3B; color: #6EE7B7; border: none; "
                "border-radius: 8px; padding: 6px 14px; font-size: 12px; font-weight: 700; }"
            )
        else:
            self.btn_add.setText("➕ Lug'atga qo'shish")
            self.btn_add.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
                f"border-radius: 8px; padding: 6px 14px; font-size: 12px; font-weight: 700; }} "
                f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            )
            self.btn_add.clicked.connect(self._add_to_study)

        action_row.addWidget(self.btn_add, 1)

        btn_more = QPushButton("📖 Batafsil")
        btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_more.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 600; }} "
            f"QPushButton:hover {{ border-color: {t.primary}; color: {t.primary}; }}"
        )
        btn_more.clicked.connect(self._open_full_details)
        action_row.addWidget(btn_more)

        main_layout.addLayout(action_row)

    def _position_on_screen(self):
        """Ekranning pastki o'ng burchagiga (taskbar ustiga) joylashtirish."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + geo.width() - self.width() - 24
        y = geo.y() + geo.height() - self.height() - 24
        self.move(x, y)

    def _toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.btn_pin.setStyleSheet(
                "QPushButton { background: #4F46E5; color: white; border-radius: 12px; font-size: 12px; }"
            )
            self.auto_close_timer.stop()
        else:
            self.btn_pin.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 12px; }")
            self.auto_close_timer.start(5000)

    def enterEvent(self, event):
        """Sichqoncha oyna ustiga kelganda avto-yopilishni to'xtatib turish."""
        if not self.is_pinned:
            self.auto_close_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Sichqoncha oynadan ketganda 4 soniyadan keyin yopish."""
        if not self.is_pinned:
            self.auto_close_timer.start(4000)
        super().leaveEvent(event)

    def _auto_close(self):
        if not self.is_pinned:
            self.close()

    def _add_to_study(self):
        success, msg, w_id = global_dict_service.add_to_study_list(
            english=self.english,
            uzbek=self.uzbek,
            example=self.example
        )
        if success:
            self.btn_add.setText("✅ Qo'shildi")
            self.btn_add.setEnabled(False)
            self.btn_add.setStyleSheet(
                "QPushButton { background-color: #064E3B; color: #6EE7B7; border: none; "
                "border-radius: 8px; padding: 6px 14px; font-size: 12px; font-weight: 700; }"
            )
            self.word_added.emit()

    def _open_speech_dialog(self):
        self.auto_close_timer.stop()
        import speech_recognizer
        speech_recognizer.open_pronunciation_dialog(self.word_data, parent=self)

    def _open_full_details(self):
        self.auto_close_timer.stop()
        from ui.dictionary import WordDetailsDialog
        dlg = WordDetailsDialog(self.english, parent=None, on_added=self.word_added.emit)
        dlg.exec()
        self.close()


class ClipboardMonitor(QObject):
    """
    Windows almashish buferi (Clipboard) o'zgarishlarini kuzatuvchi servis.
    Foydalanuvchi biror so'zni nusxalaganda avtomatik qidiradi va bildirishnoma chiqaradi.
    """
    def __init__(self, parent=None, on_words_changed=None):
        super().__init__(parent)
        self.on_words_changed = on_words_changed
        self.last_text = ""
        self.last_lookup_time = 0.0
        self.active_dialog: ClipboardPopupDialog | None = None
        self.enabled = db.get_setting("clipboard_lookup_enabled", "true") == "true"

        # Debounce taymeri (ketma-ket nusxalanganda so'nggisini olish uchun)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(300)
        self.debounce_timer.timeout.connect(self._process_clipboard)

        # QApplication clipboard signaliga ulanish
        app = QApplication.instance()
        if app:
            cb = app.clipboard()
            cb.dataChanged.connect(self._on_clipboard_changed)
            logger.info("Global Clipboard Monitor muvaffaqiyatli ishga tushirildi.")

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        db.set_setting("clipboard_lookup_enabled", "true" if enabled else "false")
        logger.info(f"Clipboard avto-qidiruv holati: {enabled}")

    def reload_settings(self):
        self.enabled = db.get_setting("clipboard_lookup_enabled", "true") == "true"

    def _on_clipboard_changed(self):
        if not self.enabled:
            return
        # Debounce taymerini qayta yoqish
        self.debounce_timer.start()

    def _process_clipboard(self):
        if not self.enabled:
            return

        app = QApplication.instance()
        if not app:
            return

        try:
            raw_text = app.clipboard().text()
        except Exception:
            return

        if not raw_text:
            return

        text = raw_text.strip()

        # Filtrlar:
        # 1. 2 tadan kam yoki 40 tadan ko'p belgili bo'lsa qaramaymiz
        if len(text) < 2 or len(text) > 40:
            return

        # 2. 3 tadan ko'p so'z bo'lsa (butun gap yoki abzas) e'tiborsiz qoldiramiz
        words_count = len(text.split())
        if words_count > 3:
            return

        # 3. URL, email, sonlar, kod sintaksisi bo'lsa rad etamiz
        if any(x in text for x in ("http://", "https://", "www.", "@", "{", "}", ";", "=", "def ", "class ")):
            return

        # Raqamlardan iborat bo'lsa rad etamiz
        if re.match(r"^[\d\s\.,:\-]+$", text):
            return

        # 4. Oldingi qidirilgan so'z bilan bir xil bo'lsa va 8 soniya o'tmagan bo'lsa, takrorlamaymiz
        now = time.time()
        if text.lower() == self.last_text.lower() and (now - self.last_lookup_time) < 8.0:
            return

        self.last_text = text
        self.last_lookup_time = now

        # Qidiruv: 64k Oxford bazasidan
        details = global_dict_service.get_word_full_details(english=text)
        if details:
            self._show_popup({
                "english": details["english"],
                "uzbek": ", ".join(details.get("uzbek_translations", [])) or details.get("uzbek_str", ""),
                "phonetic": details.get("phonetic", ""),
                "example": details.get("examples", [""])[0] if details.get("examples") else "",
                "star": details.get("star", "0"),
            })
            return

        # Agar to'g'ridan-to'g'ri topilmasa, prefix/universal qidiruv
        results = global_dict_service.search_global_words(text, limit=1)
        if results:
            first = results[0]
            # Agar kiritilgan so'z bilan topilgan so'z mos bo'lsa
            if first["english"].lower() == text.lower() or text.lower() in first["uzbek"].lower():
                ph_info = phonetics.get_word_info(first["english"])
                self._show_popup({
                    "english": first["english"],
                    "uzbek": first["uzbek"],
                    "phonetic": ph_info.get("phonetic", ""),
                    "example": first.get("example", ""),
                    "star": first.get("star", "0"),
                })

    def _show_popup(self, word_data: dict):
        # Eski popup ochiq bo'lsa, uni yopamiz
        if self.active_dialog:
            try:
                self.active_dialog.close()
            except Exception:
                pass
            self.active_dialog = None

        self.active_dialog = ClipboardPopupDialog(word_data)
        if self.on_words_changed:
            self.active_dialog.word_added.connect(self.on_words_changed)
        self.active_dialog.show()
