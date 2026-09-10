"""
Vocab Master Pro — Tezkor So'z Qo'shish Oynasi (Quick Capture Dialog).
Foydalanuvchi boshqa dasturlarda (brauzer, kitob, video) ishlayotganda ham
ekranning ustida turib, so'zni tezda bazaga saqlash imkonini beradi.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QTimer
import database as db
import tts
import theme_manager
from logger import get_logger

logger = get_logger("quick_capture")


class QuickCaptureDialog(QDialog):
    def __init__(self, parent=None, on_word_added=None):
        super().__init__(parent)
        self.on_word_added = on_word_added
        t = theme_manager.get_active_theme()

        self.setWindowTitle("⚡ Tezkor so'z qo'shish (Quick Capture)")
        self.setFixedSize(440, 310)
        # Har doim boshqa oynalar ustida turish (Stay on Top)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {t.bg_app};
                color: {t.text_main};
                border-radius: 12px;
                border: 1px solid {t.border};
            }}
            QLineEdit {{
                background-color: {t.bg_card_secondary};
                color: {t.text_main};
                border: 1px solid {t.border};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {t.primary};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)

        # Sarlavha
        h_row = QHBoxLayout()
        header = QLabel("⚡ Tezkor so'z kiritish")
        header.setStyleSheet("color: white; font-size: 16px; font-weight: 700;")
        h_row.addWidget(header)
        h_row.addStretch()

        badge = QLabel("Har doim ustida")
        badge.setStyleSheet("background-color: #312E81; color: #A5B4FC; border-radius: 6px; padding: 3px 8px; font-size: 12px; font-weight: 600;")
        h_row.addWidget(badge)

        layout.addLayout(h_row)

        # 1. English Input + TTS Tugmasi
        layout.addWidget(self._field_label("Inglizcha so'z:"))
        eng_row = QHBoxLayout()
        self.eng_input = QLineEdit()
        self.eng_input.setPlaceholderText("Masalan: ubiquitous")
        self.eng_input.textChanged.connect(self._on_eng_text_changed)
        eng_row.addWidget(self.eng_input, 1)

        self.tts_btn = QPushButton("🔊")
        self.tts_btn.setFixedSize(38, 36)
        self.tts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tts_btn.setStyleSheet(
            "QPushButton { background-color: #1E1E2E; border: 1px solid #374151; border-radius: 8px; font-size: 16px; }"
            "QPushButton:hover { background-color: #4F46E5; border-color: #6366F1; }"
        )
        self.tts_btn.clicked.connect(self._speak_current)
        eng_row.addWidget(self.tts_btn)
        layout.addLayout(eng_row)

        # 2. Uzbek Input
        layout.addWidget(self._field_label("O'zbekcha tarjimasi:"))
        self.uz_input = QLineEdit()
        self.uz_input.setPlaceholderText("Masalan: hamma joyda uchraydigan")
        self.uz_input.returnPressed.connect(self.save_word)
        layout.addWidget(self.uz_input)

        # 3. Example Input (ixtiyoriy)
        layout.addWidget(self._field_label("Misol gap (ixtiyoriy):"))
        self.ex_input = QLineEdit()
        self.ex_input.setPlaceholderText("Masalan: Smartphones have become ubiquitous.")
        self.ex_input.returnPressed.connect(self.save_word)
        layout.addWidget(self.ex_input)

        # Xabar / Status
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 600; min-height: 16px;")
        layout.addWidget(self.status_lbl)

        # Tugmalar qatori
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("Yopish (Esc)")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "QPushButton { background-color: #2A2A3C; color: #9CA3AF; border-radius: 8px; padding: 7px 14px; }"
            "QPushButton:hover { background-color: #374151; color: white; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.save_btn = QPushButton("➕ Bazaga qo'shish (Enter)")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; font-weight: 600; border-radius: 8px; padding: 7px 16px; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        self.save_btn.clicked.connect(self.save_word)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

        # Boshlang'ich fokus
        QTimer.singleShot(100, self.eng_input.setFocus)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 600; margin-top: 2px;")
        return lbl

    def _on_eng_text_changed(self, text: str):
        self.tts_btn.setEnabled(bool(text.strip()))

    def _speak_current(self):
        txt = self.eng_input.text().strip()
        if txt:
            tts.speak_async(txt)

    def save_word(self):
        eng = self.eng_input.text().strip()
        uz = self.uz_input.text().strip()
        ex = self.ex_input.text().strip()

        if not eng:
            self.status_lbl.setStyleSheet("color: #EF4444;")
            self.status_lbl.setText("❌ Inglizcha so'zni kiriting!")
            self.eng_input.setFocus()
            return

        if not uz:
            self.status_lbl.setStyleSheet("color: #EF4444;")
            self.status_lbl.setText("❌ O'zbekcha tarjimani kiriting!")
            self.uz_input.setFocus()
            return

        word_id = db.add_word(eng, uz, source="quick_capture", example=ex)
        if word_id:
            self.status_lbl.setStyleSheet("color: #10B981;")
            self.status_lbl.setText(f"✅ '{eng}' bazaga qo'shildi!")
            self.eng_input.clear()
            self.uz_input.clear()
            self.ex_input.clear()
            self.eng_input.setFocus()

            if self.on_word_added:
                self.on_word_added(eng, uz)
        else:
            self.status_lbl.setStyleSheet("color: #F59E0B;")
            self.status_lbl.setText(f"ℹ️ '{eng}' allaqachon mavjud!")
