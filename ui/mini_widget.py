"""
Vocab Master Pro — Mini Floating Desktop Widget.
Ish stoli ustida suzib yuruvchi, doimo boshqa dasturlar ustida turadigan (stay-on-top),
shaffof (translucent) va siljitish mumkin bo'lgan mini so'z trenajyori.
"""
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QColor, QFont, QMouseEvent

import database as db
import phonetics
import theme_manager
import tts
from logger import get_logger

logger = get_logger("mini_widget")


class MiniWidget(QWidget):
    """Barcha oynalar ustida suzib yuruvchi mini vidjet."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Boshqa oynalar ustida turish, sarlavhasiz (frameless) va tool oyna
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(320, 190)

        # Oynani sudrab siljitish (Drag & Drop)
        self._drag_position = QPoint()
        self._is_dragging = False

        # So'zlar navbati
        self.words_pool = []
        self.current_index = 0
        self.current_word = None
        self.is_translation_hidden = False
        self.is_pinned = True

        # Avtomatik so'z almashish taymeri (default 15 soniya)
        self.cycle_interval_sec = int(db.get_setting("floating_widget_interval", "15"))
        self.cycle_timer = QTimer(self)
        self.cycle_timer.timeout.connect(self.next_word)

        self._setup_ui()
        self.load_words()

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

        # Taymerni ishga tushirish
        if self.cycle_interval_sec > 0:
            self.cycle_timer.start(self.cycle_interval_sec * 1000)

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        # Asosiy karta (Glassmorphism & Border)
        self.card_frame = QFrame(self)
        self.card_frame.setObjectName("miniCard")
        self.card_frame.setStyleSheet(
            "QFrame#miniCard {"
            "  background-color: rgba(26, 26, 38, 0.95);"
            "  border: 1.5px solid #3730A3;"
            "  border-radius: 16px;"
            "}"
        )

        # Yumshoq soyalar (Drop Shadow)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 6)
        self.card_frame.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(6)

        # 1. Sarlavha paneli (Drag bar, timer ko'rsatkichi, tts, pin, close)
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.drag_handle = QLabel("⋮⋮ Vocab Mini")
        self.drag_handle.setStyleSheet("color: #818CF8; font-size: 11px; font-weight: 700; cursor: move;")
        header_row.addWidget(self.drag_handle)

        self.timer_badge = QLabel(f"⏱️ {self.cycle_interval_sec}s")
        self.timer_badge.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; font-size: 10px; font-weight: 600; "
            "border-radius: 4px; padding: 1px 5px;"
        )
        header_row.addWidget(self.timer_badge)

        header_row.addStretch()

        # Ovozli talaffuz tugmasi
        self.btn_speak = QPushButton("🔊")
        self.btn_speak.setFixedSize(24, 24)
        self.btn_speak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speak.setStyleSheet(
            "QPushButton { background: transparent; color: #38BDF8; border: none; font-size: 13px; }"
            "QPushButton:hover { background-color: #2E2850; border-radius: 4px; }"
        )
        self.btn_speak.clicked.connect(self._speak_current)
        header_row.addWidget(self.btn_speak)

        # Pin (Stay on top) tugmasi
        self.btn_pin = QPushButton("📌")
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pin.setStyleSheet(
            "QPushButton { background: transparent; color: #F59E0B; border: none; font-size: 12px; }"
            "QPushButton:hover { background-color: #2E2850; border-radius: 4px; }"
        )
        self.btn_pin.clicked.connect(self._toggle_pin)
        header_row.addWidget(self.btn_pin)

        # Yopish (yashirish) tugmasi
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(
            "QPushButton { background: transparent; color: #9CA3AF; border: none; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { color: #EF4444; background-color: #381A1A; border-radius: 4px; }"
        )
        self.btn_close.clicked.connect(self.hide)
        header_row.addWidget(self.btn_close)

        card_layout.addLayout(header_row)

        # 2. Inglizcha so'z va fonetik ma'lumot
        word_box = QVBoxLayout()
        word_box.setSpacing(2)

        self.lbl_english = QLabel("Loading...")
        self.lbl_english.setStyleSheet("color: #FFFFFF; font-size: 19px; font-weight: 800;")
        word_box.addWidget(self.lbl_english)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)

        self.lbl_phonetic = QLabel("")
        self.lbl_phonetic.setStyleSheet("color: #A5B4FC; font-size: 11px; font-weight: 500;")
        sub_row.addWidget(self.lbl_phonetic)

        self.lbl_pos = QLabel("")
        self.lbl_pos.setStyleSheet(
            "background-color: #312E81; color: #C7D2FE; font-size: 10px; font-weight: 700; "
            "border-radius: 3px; padding: 1px 5px;"
        )
        sub_row.addWidget(self.lbl_pos)
        sub_row.addStretch()

        word_box.addLayout(sub_row)
        card_layout.addLayout(word_box)

        # 3. O'zbekcha tarjima (bosganda ko'rsatish/yashirish imkoniyati bilan)
        self.lbl_uzbek = QLabel("")
        self.lbl_uzbek.setWordWrap(True)
        self.lbl_uzbek.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_uzbek.setStyleSheet(
            "color: #34D399; font-size: 14px; font-weight: 700; "
            "background-color: rgba(6, 78, 59, 0.4); border-radius: 6px; padding: 4px 8px;"
        )
        self.lbl_uzbek.mousePressEvent = lambda e: self._toggle_translation_reveal()
        card_layout.addWidget(self.lbl_uzbek)

        # 4. Pastki navigatsiya (Avvalgi, Keyingi, O'rgandim)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(28, 26)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet(
            "QPushButton { background-color: #242438; color: white; border: 1px solid #3730A3; border-radius: 6px; font-size: 11px; }"
            "QPushButton:hover { background-color: #4F46E5; }"
        )
        self.btn_prev.clicked.connect(self.prev_word)
        nav_row.addWidget(self.btn_prev)

        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(28, 26)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet(
            "QPushButton { background-color: #242438; color: white; border: 1px solid #3730A3; border-radius: 6px; font-size: 11px; }"
            "QPushButton:hover { background-color: #4F46E5; }"
        )
        self.btn_next.clicked.connect(self.next_word)
        nav_row.addWidget(self.btn_next)

        nav_row.addStretch()

        self.btn_master = QPushButton("✓ Yodladim")
        self.btn_master.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_master.setStyleSheet(
            "QPushButton { background-color: #065F46; color: #A7F3D0; border: 1px solid #10B981; "
            "border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background-color: #047857; color: white; }"
        )
        self.btn_master.clicked.connect(self._mark_current_mastered)
        nav_row.addWidget(self.btn_master)

        card_layout.addLayout(nav_row)

        root_layout.addWidget(self.card_frame)

    def apply_theme(self, t: theme_manager.Theme):
        if hasattr(self, "card_frame"):
            self.card_frame.setStyleSheet(
                f"QFrame#miniCard {{"
                f"  background-color: {t.bg_card};"
                f"  border: 1.5px solid {t.border};"
                f"  border-radius: 16px;"
                f"}}"
            )
        if hasattr(self, "lbl_english"):
            self.lbl_english.setStyleSheet(f"color: {t.text_main}; font-size: 19px; font-weight: 800;")
        if hasattr(self, "drag_handle"):
            self.drag_handle.setStyleSheet(f"color: {t.primary_light}; font-size: 11px; font-weight: 700; cursor: move;")

    def load_words(self):
        """O'rganish uchun so'zlar bazasini yuklash."""
        # 1. Bugun takrorlash kerak bo'lganlar yoki Leitner Box 0-3 so'zlari
        due = db.get_due_words(limit=30)
        if due:
            self.words_pool = list(due)
        else:
            self.words_pool = list(db.get_words(limit=60))

        if not self.words_pool:
            self.lbl_english.setText("Lug'at bo'sh")
            self.lbl_uzbek.setText("So'z qo'shing")
            self.lbl_phonetic.setText("")
            self.lbl_pos.setText("")
            return

        random.shuffle(self.words_pool)
        self.current_index = 0
        self._display_word(self.words_pool[0])

    def _display_word(self, word_data):
        self.current_word = word_data
        eng = word_data["english"]
        uz = word_data["uzbek"]

        # Fonetik va so'z turkumi ma'lumotlarini olish
        ph_info = phonetics.get_word_info(eng)
        phonetic_text = word_data["phonetic"] if "phonetic" in word_data.keys() and word_data["phonetic"] else ph_info["phonetic"]
        pos_tag = word_data["part_of_speech"] if "part_of_speech" in word_data.keys() and word_data["part_of_speech"] else ph_info["part_of_speech"]

        self.lbl_english.setText(eng)
        self.lbl_phonetic.setText(phonetic_text)
        self.lbl_pos.setText(f"[{pos_tag}]")
        self.lbl_uzbek.setText(uz)
        self.is_translation_hidden = False

    def next_word(self):
        if not self.words_pool:
            return
        self.current_index = (self.current_index + 1) % len(self.words_pool)
        self._display_word(self.words_pool[self.current_index])
        # Taymerni nollash
        if self.cycle_interval_sec > 0:
            self.cycle_timer.start(self.cycle_interval_sec * 1000)

    def prev_word(self):
        if not self.words_pool:
            return
        self.current_index = (self.current_index - 1) % len(self.words_pool)
        self._display_word(self.words_pool[self.current_index])
        if self.cycle_interval_sec > 0:
            self.cycle_timer.start(self.cycle_interval_sec * 1000)

    def _speak_current(self):
        if self.current_word:
            tts.speak(self.current_word["english"])

    def _toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.btn_pin.setStyleSheet("color: #F59E0B; background: transparent; font-size: 12px; border: none;")
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            self.btn_pin.setStyleSheet("color: #6B7280; background: transparent; font-size: 12px; border: none;")
        self.show()

    def _toggle_translation_reveal(self):
        if not self.current_word:
            return
        self.is_translation_hidden = not self.is_translation_hidden
        if self.is_translation_hidden:
            self.lbl_uzbek.setText("👁️ Tarjimani ko'rish uchun bosing...")
            self.lbl_uzbek.setStyleSheet(
                "color: #9CA3AF; font-size: 12px; font-style: italic; "
                "background-color: rgba(30, 30, 46, 0.4); border-radius: 6px; padding: 4px 8px;"
            )
        else:
            self.lbl_uzbek.setText(self.current_word["uzbek"])
            self.lbl_uzbek.setStyleSheet(
                "color: #34D399; font-size: 14px; font-weight: 700; "
                "background-color: rgba(6, 78, 59, 0.4); border-radius: 6px; padding: 4px 8px;"
            )

    def _mark_current_mastered(self):
        if not self.current_word:
            return
        w_id = self.current_word["id"]
        # SM-2 bo'yicha eng yuqori baho (5 - Easy/Mastered)
        db.record_sm2_review(w_id, quality=5)
        self.next_word()

    # --- Drag & Drop (Oynani ekranda ko'chirish) ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_dragging = False
        event.accept()
