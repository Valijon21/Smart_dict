"""
Vocab Master Pro — Floating Clipboard Lookup Popup Dialog.
Ekranning pastki o'ng burchagida chiquvchi zamonaviy suzuvchi tarjima oynasi (Toast).
Aktiv oynaning fokusini olib qo'ymaydi (WA_ShowWithoutActivating).
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

import core.database as db
import services.global_dict_service as global_dict_service
import services.tts_service as tts
import ui.theme_manager as theme_manager
from utils.logger import get_logger

logger = get_logger("clipboard_popup")


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
        lbl_uz.setStyleSheet("font-size: 14px; font-weight: 600; color: #34D399; line-height: 1.3;")
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
        try:
            import services.speech_service as speech_service
            speech_service.open_pronunciation_dialog(self.word_data, parent=self)
        except Exception as e:
            logger.error(f"Talaffuz dialogini ochishda xatolik: {e}")

    def _open_full_details(self):
        self.auto_close_timer.stop()
        try:
            from ui.views.dictionary_view import WordDetailsDialog
            dlg = WordDetailsDialog(self.english, parent=None, on_added=self.word_added.emit)
            dlg.exec()
            self.close()
        except Exception as e:
            logger.error(f"Batafsil ma'lumot dialogini ochishda xatolik: {e}")
