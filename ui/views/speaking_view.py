"""
ui/views/speaking_view.py
Vocab Master Pro — Professional Speaking & Talaffuz Trenajyori (Pronunciation Trainer).

Foydalanuvchiga inglizcha so'zlarning to'g'ri talaffuzini eshitish, mikrofonga aytish,
Windows Speech Recognition dvigateli va oflayn akustik tahlil orqali talaffuz aniqligini
(0-100% shkalada) baholash hamda o'z ovozini darhol qayta tinglash imkoniyatini beradi.
"""
import os
import time
import tempfile
import wave
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QComboBox, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QByteArray, QBuffer, QIODevice
from PyQt6.QtMultimedia import (
    QAudioSource, QAudioFormat, QMediaDevices, QMediaPlayer, QAudioOutput
)

import core.database as db
import ui.theme_manager as theme_manager
import services.tts_service as tts
from services.speech_service import (
    check_windows_speech_recognizers,
    WindowsSpeechWorker,
    analyze_recorded_wav
)
from utils.logger import get_logger

logger = get_logger("speaking_view")


class SpeakingWidget(QWidget):
    """
    Asosiy chap menyuga joylashtiriladigan to'liq interaktiv Speaking Trenajyori vidjeti.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.words_list: List[Dict[str, Any]] = []
        self.current_idx: int = 0
        self.current_word: Optional[Dict[str, Any]] = None

        # Yozish holati va audio
        self.is_recording = False
        self.recorded_file = ""
        self.record_time_ms = 0
        self.worker: Optional[WindowsSpeechWorker] = None

        # Statistika
        self.session_practiced = 0
        self.session_scores: List[int] = []

        # 16kHz 16-bit Mono PCM audio format
        self.audio_format = QAudioFormat()
        self.audio_format.setSampleRate(16000)
        self.audio_format.setChannelCount(1)
        self.audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self.audio_source: Optional[QAudioSource] = None
        self.audio_byte_array = QByteArray()
        self.audio_buffer: Optional[QBuffer] = None

        # Qayta eshitish pleyeri
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        # Ovoz yozish taymeri (100ms intervalli, jami 4000ms = 4 sek)
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(100)
        self.record_timer.timeout.connect(self._on_record_tick)

        # Windows speech dvigateli holatini tekshirish
        self.has_speech_engine, self.engine_msg, self.engine_langs = check_windows_speech_recognizers()

        self._build_ui()
        self.load_words()

    # =========================================================================
    # UI QURILISHI
    # =========================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 24)
        root.setSpacing(16)

        # --- 1. Sarlavha va Dvigatel holati ---
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        self.lbl_title = QLabel("🎙️ Speaking & Talaffuz Trenajyori")
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: 800;")
        title_box.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel(
            "So'zni to'g'ri talaffuzini eshiting, mikrofonga ayting va sun'iy intellekt orqali ball oling"
        )
        self.lbl_subtitle.setStyleSheet("font-size: 13px; color: #9CA3AF;")
        title_box.addWidget(self.lbl_subtitle)
        header_row.addLayout(title_box)
        header_row.addStretch()

        # Dvigatel status nishoni
        self.badge_engine = QLabel()
        if self.has_speech_engine:
            self.badge_engine.setText("🟢 Windows Speech Dvigateli: Faol")
            self.badge_engine.setStyleSheet(
                "background-color: #064E3B; color: #6EE7B7; border: 1px solid #059669; "
                "border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 600;"
            )
        else:
            self.badge_engine.setText("🟡 Oflayn Akustik Tahlil: Faol")
            self.badge_engine.setStyleSheet(
                "background-color: #78350F; color: #FCD34D; border: 1px solid #D97706; "
                "border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 600;"
            )
        header_row.addWidget(self.badge_engine)
        root.addLayout(header_row)

        # --- 2. Filtrlar va Mini Statistika Paneli ---
        ctrl_bar = QFrame()
        ctrl_bar.setObjectName("ctrl_bar")
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(14, 10, 14, 10)
        ctrl_layout.setSpacing(12)

        lbl_cat = QLabel("Kategoriya:")
        lbl_cat.setStyleSheet("font-weight: 600; font-size: 13px;")
        ctrl_layout.addWidget(lbl_cat)

        self.combo_filter = QComboBox()
        self.combo_filter.setFixedWidth(220)
        self.combo_filter.addItems([
            "📖 Barcha so'zlar (Lug'at)",
            "⚠️ Qiyin so'zlar (Xatolar ko'p)",
            "⚡ Noto'g'ri fe'llar (V1 / V2 / V3)",
            "🆕 Yangi so'zlar",
        ])
        self.combo_filter.currentIndexChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self.combo_filter)

        ctrl_layout.addStretch()

        # Mini statistik chiplar
        self.lbl_stat_avg = QLabel("🎯 O'rtacha: 0%")
        self.lbl_stat_avg.setStyleSheet(
            "background-color: rgba(99, 102, 241, 0.15); color: #A5B4FC; "
            "padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 600;"
        )
        ctrl_layout.addWidget(self.lbl_stat_avg)

        self.lbl_stat_count = QLabel("🗣️ Mashq: 0 ta")
        self.lbl_stat_count.setStyleSheet(
            "background-color: rgba(16, 185, 129, 0.15); color: #6EE7B7; "
            "padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 600;"
        )
        ctrl_layout.addWidget(self.lbl_stat_count)

        self.lbl_stat_great = QLabel("🌟 A'lo (90%+): 0")
        self.lbl_stat_great.setStyleSheet(
            "background-color: rgba(245, 158, 11, 0.15); color: #FCD34D; "
            "padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 600;"
        )
        ctrl_layout.addWidget(self.lbl_stat_great)

        root.addWidget(ctrl_bar)

        # --- 3. Asosiy So'z Kartasi (Hero Card) ---
        self.card_main = QFrame()
        self.card_main.setObjectName("speaking_hero_card")
        card_layout = QVBoxLayout(self.card_main)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Yuqori ko'rsatkich (Index chip)
        self.lbl_counter = QLabel("So'z: 0 / 0")
        self.lbl_counter.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #9CA3AF; "
            "background-color: rgba(255,255,255,0.06); padding: 3px 10px; border-radius: 12px;"
        )
        self.lbl_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_counter)

        # Asosiy inglizcha so'z
        self.lbl_word = QLabel("Yuklanmoqda...")
        self.lbl_word.setObjectName("lbl_speaking_word")
        self.lbl_word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_word)

        # Fonetik transkripsiya va so'z turkumi
        ph_row = QHBoxLayout()
        ph_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_row.setSpacing(8)

        self.lbl_phonetic = QLabel("")
        self.lbl_phonetic.setObjectName("lbl_speaking_phonetic")
        self.lbl_phonetic.setVisible(False)
        ph_row.addWidget(self.lbl_phonetic)

        self.lbl_pos = QLabel("")
        self.lbl_pos.setObjectName("lbl_speaking_pos")
        self.lbl_pos.setVisible(False)
        ph_row.addWidget(self.lbl_pos)
        card_layout.addLayout(ph_row)

        # O'zbekcha tarjima
        self.lbl_uzbek = QLabel("")
        self.lbl_uzbek.setObjectName("lbl_speaking_uzbek")
        self.lbl_uzbek.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_uzbek.setWordWrap(True)
        card_layout.addWidget(self.lbl_uzbek)

        # Misol jumla
        self.lbl_example = QLabel("")
        self.lbl_example.setObjectName("lbl_speaking_example")
        self.lbl_example.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_example.setWordWrap(True)
        self.lbl_example.setVisible(False)
        card_layout.addWidget(self.lbl_example)

        # TTS namunaviy tinglash tugmalari
        tts_row = QHBoxLayout()
        tts_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tts_row.setSpacing(12)

        self.btn_listen_normal = QPushButton("🔊 Namunani tinglash [R]")
        self.btn_listen_normal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_listen_normal.clicked.connect(self._speak_normal)
        tts_row.addWidget(self.btn_listen_normal)

        self.btn_listen_slow = QPushButton("🐢 Sekinlashtirilgan 0.75x [S]")
        self.btn_listen_slow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_listen_slow.clicked.connect(self._speak_slow)
        tts_row.addWidget(self.btn_listen_slow)

        card_layout.addLayout(tts_row)
        root.addWidget(self.card_main)

        # --- 4. Ovoz Yozish va Real-vaqt Tekshiruv Bloki ---
        self.card_action = QFrame()
        self.card_action.setObjectName("speaking_action_card")
        action_layout = QVBoxLayout(self.card_action)
        action_layout.setContentsMargins(24, 18, 24, 18)
        action_layout.setSpacing(12)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_rec_status = QLabel("Quyidagi qizil tugmani bosing va so'zni aniq talaffuz qiling:")
        self.lbl_rec_status.setStyleSheet("font-size: 13px; color: #9CA3AF;")
        self.lbl_rec_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_layout.addWidget(self.lbl_rec_status)

        # 4 soniyalik vizual progress bar
        self.rec_progress = QProgressBar()
        self.rec_progress.setRange(0, 40)
        self.rec_progress.setValue(0)
        self.rec_progress.setTextVisible(False)
        self.rec_progress.setFixedHeight(8)
        self.rec_progress.setVisible(False)
        action_layout.addWidget(self.rec_progress)

        # Ovoz yozish va O'z ovozini tinglash tugmalari
        rec_btn_row = QHBoxLayout()
        rec_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_btn_row.setSpacing(16)

        self.btn_record = QPushButton("🎙️ Ovozni Yozish (4 sek) [Space]")
        self.btn_record.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_record.setFixedHeight(48)
        self.btn_record.clicked.connect(self._toggle_record)
        rec_btn_row.addWidget(self.btn_record)

        self.btn_replay = QPushButton("▶️ O'z talaffuzingizni tinglash [P]")
        self.btn_replay.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_replay.setFixedHeight(48)
        self.btn_replay.setEnabled(False)
        self.btn_replay.clicked.connect(self._play_user_recording)
        rec_btn_row.addWidget(self.btn_replay)

        action_layout.addLayout(rec_btn_row)
        root.addWidget(self.card_action)

        # --- 5. Natija va Tahlil Bloki ---
        self.card_result = QFrame()
        self.card_result.setObjectName("speaking_result_card")
        result_layout = QVBoxLayout(self.card_result)
        result_layout.setContentsMargins(20, 14, 20, 14)
        result_layout.setSpacing(6)
        result_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_score_badge = QLabel("📊 Natija: Kutilmoqda")
        self.lbl_score_badge.setStyleSheet("font-size: 16px; font-weight: 700; color: #9CA3AF;")
        self.lbl_score_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_layout.addWidget(self.lbl_score_badge)

        self.lbl_feedback = QLabel(
            "So'zni aytganingizdan so'ng nutq dvigateli ovozingizni tahlil qilib, 0-100% ball beradi."
        )
        self.lbl_feedback.setStyleSheet("font-size: 12px; color: #6B7280;")
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_layout.addWidget(self.lbl_feedback)

        root.addWidget(self.card_result)

        # --- 6. Navigatsiya paneli ---
        nav_row = QHBoxLayout()
        nav_row.setSpacing(12)

        self.btn_prev = QPushButton("⬅️ Oldingi [←]")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.clicked.connect(self._prev_word)
        nav_row.addWidget(self.btn_prev)

        self.btn_random = QPushButton("🎲 Tasodifiy")
        self.btn_random.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_random.clicked.connect(self._random_word)
        nav_row.addWidget(self.btn_random)

        self.btn_next = QPushButton("Keyingi [→] ➡️")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(self._next_word)
        nav_row.addWidget(self.btn_next)

        root.addLayout(nav_row)

        # Mavzuni qo'llash
        self.apply_theme(theme_manager.get_active_theme())

    # =========================================================================
    # MAVZU VA USLUBLAR
    # =========================================================================

    def apply_theme(self, t: theme_manager.Theme):
        """Vizual rang mavzusini to'liq sinxronlashtirish."""
        self.setStyleSheet(f"""
            QWidget {{
                color: {t.text_main};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            #ctrl_bar {{
                background-color: {t.bg_card};
                border: 1px solid {t.border};
                border-radius: 10px;
            }}
            #speaking_hero_card {{
                background-color: {t.bg_card};
                border: 1.5px solid {t.border};
                border-radius: 16px;
            }}
            #speaking_action_card {{
                background-color: {t.bg_card_secondary};
                border: 1px solid {t.border};
                border-radius: 14px;
            }}
            #speaking_result_card {{
                background-color: {t.bg_card};
                border: 1px solid {t.border};
                border-radius: 12px;
            }}
            #lbl_speaking_word {{
                font-size: 36px;
                font-weight: 800;
                color: {t.primary_light};
                letter-spacing: 0.5px;
            }}
            #lbl_speaking_phonetic {{
                background-color: rgba(99, 102, 241, 0.2);
                color: #A5B4FC;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 15px;
                font-weight: 600;
            }}
            #lbl_speaking_pos {{
                background-color: rgba(255, 255, 255, 0.08);
                color: {t.text_muted};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-style: italic;
            }}
            #lbl_speaking_uzbek {{
                font-size: 16px;
                color: {t.text_main};
                font-weight: 600;
            }}
            #lbl_speaking_example {{
                font-size: 13px;
                color: {t.text_muted};
                font-style: italic;
                padding: 4px 16px;
            }}
            QComboBox {{
                background-color: {t.bg_card_secondary};
                color: {t.text_main};
                border: 1px solid {t.border};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QProgressBar {{
                background: {t.bg_card};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: #EF4444;
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {t.bg_card_secondary};
                color: {t.text_main};
                border: 1px solid {t.border};
                border-radius: 10px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {t.primary};
                color: {t.primary_light};
                background-color: {t.bg_card};
            }}
        """)

        # Maxsus tugma uslublari
        self._update_record_button_style()
        self.btn_replay.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.bg_card};
                color: {t.text_muted};
                border: 1px solid {t.border};
                border-radius: 10px;
                padding: 10px 22px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:enabled {{
                color: {t.text_main};
                border-color: {t.primary};
            }}
            QPushButton:hover:enabled {{
                background-color: {t.bg_card_secondary};
                color: {t.primary_light};
            }}
        """)

    def _update_record_button_style(self):
        if self.is_recording:
            self.btn_record.setText("⏹️ Yozishni To'xtatish [Space]")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #B91C1C;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 10px;
                    padding: 10px 24px;
                    font-size: 14px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #991B1B;
                }
            """)
        else:
            self.btn_record.setText("🎙️ Ovozni Yozish (4 sek) [Space]")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #EF4444;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 10px;
                    padding: 10px 24px;
                    font-size: 14px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #DC2626;
                }
            """)

    # =========================================================================
    # SO'ZLARNI YUKLASH VA FILTRLASH
    # =========================================================================

    def load_words(self):
        """Tanlangan filtr bo'yicha so'zlar ro'yxatini yuklash."""
        mode_idx = self.combo_filter.currentIndex()
        words = []

        if mode_idx == 0:
            # Barcha so'zlar
            rows = db.get_all_words(order_by="created_at DESC")
            for r in rows:
                words.append({
                    "id": r["id"],
                    "english": r["english"],
                    "uzbek": r["uzbek"],
                    "phonetic": r["phonetic"] if "phonetic" in r.keys() else "",
                    "part_of_speech": r["part_of_speech"] if "part_of_speech" in r.keys() else "",
                    "example": r["example"] if "example" in r.keys() else "",
                })
        elif mode_idx == 1:
            # Qiyin so'zlar
            rows = db.search_words(hard_only=True, limit=100)
            for r in rows:
                words.append({
                    "id": r["id"],
                    "english": r["english"],
                    "uzbek": r["uzbek"],
                    "phonetic": r["phonetic"] if "phonetic" in r.keys() else "",
                    "part_of_speech": r["part_of_speech"] if "part_of_speech" in r.keys() else "",
                    "example": r["example"] if "example" in r.keys() else "",
                })
        elif mode_idx == 2:
            # Noto'g'ri fe'llar
            verbs = db.get_irregular_verbs(limit=150)
            for v in verbs:
                words.append({
                    "id": v["id"],
                    "english": f"{v['v1']} — {v['v2']} — {v['v3']}",
                    "clean_tts": v["v1"],
                    "uzbek": v["translation"],
                    "phonetic": "",
                    "part_of_speech": "verb",
                    "example": f"V1: {v['v1']} | V2: {v['v2']} | V3: {v['v3']}",
                })
        else:
            # Yangi so'zlar
            rows = db.get_words_by_status("new")
            for r in rows:
                words.append({
                    "id": r["id"],
                    "english": r["english"],
                    "uzbek": r["uzbek"],
                    "phonetic": r["phonetic"] if "phonetic" in r.keys() else "",
                    "part_of_speech": r["part_of_speech"] if "part_of_speech" in r.keys() else "",
                    "example": r["example"] if "example" in r.keys() else "",
                })

        self.words_list = words
        self.current_idx = 0
        self._display_current_word()

    def _on_filter_changed(self):
        self._stop_recording()
        self.load_words()

    def _display_current_word(self):
        """Hozirgi so'zni kartada ko'rsatish."""
        if not self.words_list:
            self.current_word = None
            self.lbl_counter.setText("So'z: 0 / 0")
            self.lbl_word.setText("Lug'atda so'zlar mavjud emas")
            self.lbl_phonetic.setVisible(False)
            self.lbl_pos.setVisible(False)
            self.lbl_uzbek.setText("Iltimos, avval yangi so'zlar qo'shing yoki boshqa filtrni tanlang.")
            self.lbl_example.setVisible(False)
            self.btn_listen_normal.setEnabled(False)
            self.btn_listen_slow.setEnabled(False)
            self.btn_record.setEnabled(False)
            self.btn_replay.setEnabled(False)
            return

        self.btn_listen_normal.setEnabled(True)
        self.btn_listen_slow.setEnabled(True)
        self.btn_record.setEnabled(True)

        w = self.words_list[self.current_idx]
        self.current_word = w

        self.lbl_counter.setText(f"So'z: {self.current_idx + 1} / {len(self.words_list)}")
        self.lbl_word.setText(w.get("english", ""))

        # Fonetika
        ph = str(w.get("phonetic", "") or "").strip()
        if ph:
            self.lbl_phonetic.setText(f"/{ph}/")
            self.lbl_phonetic.setVisible(True)
        else:
            self.lbl_phonetic.setVisible(False)

        # So'z turkumi
        pos = str(w.get("part_of_speech", "") or "").strip()
        if pos:
            self.lbl_pos.setText(f"[{pos}]")
            self.lbl_pos.setVisible(True)
        else:
            self.lbl_pos.setVisible(False)

        self.lbl_uzbek.setText(w.get("uzbek", ""))

        # Misol jumla
        ex = str(w.get("example", "") or "").strip()
        if ex:
            self.lbl_example.setText(f"“ {ex} ”")
            self.lbl_example.setVisible(True)
        else:
            self.lbl_example.setVisible(False)

        # Natija panelini reset qilish
        self.lbl_score_badge.setText("📊 Natija: Kutilmoqda")
        self.lbl_score_badge.setStyleSheet("font-size: 16px; font-weight: 700; color: #9CA3AF;")
        self.lbl_feedback.setText(
            "Pastdagi qizil tugmani bosing va so'zni aniq talaffuz qiling."
        )
        self.lbl_rec_status.setText("Mikrofon tayyor. 'Ovozni Yozish' tugmasini bosing:")
        self.lbl_rec_status.setStyleSheet("font-size: 13px; color: #9CA3AF;")
        self.btn_replay.setEnabled(False)
        self.rec_progress.setVisible(False)

    # =========================================================================
    # AUDIO VA NUTQNI TINGLASH (TTS)
    # =========================================================================

    def _get_target_text(self) -> str:
        if not self.current_word:
            return ""
        return self.current_word.get("clean_tts") or self.current_word.get("english", "")

    def _speak_normal(self):
        text = self._get_target_text()
        if text:
            tts.speak(text, slow=False)

    def _speak_slow(self):
        text = self._get_target_text()
        if text:
            tts.speak(text, slow=True)

    # =========================================================================
    # MIKROFON VA TALAFUZNI YOZISH / BAHOLASH
    # =========================================================================

    def _toggle_record(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not self.current_word:
            return
        self.is_recording = True
        self._update_record_button_style()

        self.lbl_rec_status.setText("🔴 Yozilmoqda... So'zni aniq talaffuz qiling!")
        self.lbl_rec_status.setStyleSheet("font-size: 13px; color: #EF4444; font-weight: 700;")
        self.rec_progress.setValue(0)
        self.rec_progress.setVisible(True)
        self.btn_replay.setEnabled(False)

        # Vaqtinchalik faylga yozish
        temp_dir = Path(tempfile.gettempdir())
        self.recorded_file = str(temp_dir / f"speaking_trainer_{int(time.time() * 1000)}.wav")

        try:
            device = QMediaDevices.defaultAudioInput()
            self.audio_source = QAudioSource(device, self.audio_format, self)
            self.audio_byte_array = QByteArray()
            self.audio_buffer = QBuffer(self.audio_byte_array)
            self.audio_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self.audio_source.start(self.audio_buffer)
        except Exception as e:
            logger.error(f"Speaking trainer audio yozishda xatolik: {e}")

        self.record_time_ms = 0
        self.record_timer.start()

        # Windows speech dvigateli asinxron ishga tushadi
        target_text = self._get_target_text()
        self.worker = WindowsSpeechWorker(target_text, timeout_sec=4)
        self.worker.finished.connect(self._on_speech_finished)
        self.worker.start()

    def _on_record_tick(self):
        self.record_time_ms += 100
        step = int(self.record_time_ms / 100)
        self.rec_progress.setValue(min(40, step))
        if self.record_time_ms >= 4000:
            self._stop_recording()

    def _stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.record_timer.stop()
        self.rec_progress.setVisible(False)
        self._update_record_button_style()

        self.lbl_rec_status.setText("Tahlil qilinmoqda...")
        self.lbl_rec_status.setStyleSheet("font-size: 13px; color: #9CA3AF;")

        try:
            if self.audio_source:
                self.audio_source.stop()
                self.audio_source = None
            if self.audio_buffer:
                self.audio_buffer.close()
                self.audio_buffer = None

            raw_bytes = bytes(self.audio_byte_array.data())
            if raw_bytes:
                with wave.open(self.recorded_file, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(raw_bytes)
        except Exception as e:
            logger.error(f"WAV faylga saqlashda xatolik: {e}")

        if os.path.exists(self.recorded_file) and os.path.getsize(self.recorded_file) > 100:
            self.btn_replay.setEnabled(True)

    def _play_user_recording(self):
        """Foydalanuvchining o'zi yozgan ovozini qayta tinglash."""
        if self.recorded_file and os.path.exists(self.recorded_file):
            self.player.setSource(QUrl.fromLocalFile(self.recorded_file))
            self.player.play()
            self.lbl_rec_status.setText("🔊 O'z ovozingiz eshittirilmoqda...")

    def _on_speech_finished(self, res: dict):
        """Windows Speech yoki WAV tahlili natijalarini ko'rsatish."""
        if not self.current_word:
            return

        status = res.get("status", "")
        score = res.get("score", 0)
        target = self._get_target_text()

        # Agar Windows Speech tanimasa, oflayn WAV akustik tahliliga murojaat qilamiz
        if status != "ok" and self.recorded_file and os.path.exists(self.recorded_file) and os.path.getsize(self.recorded_file) > 200:
            wav_res = analyze_recorded_wav(self.recorded_file, target)
            if wav_res.get("status") == "ok":
                status = "ok"
                score = wav_res.get("score", 76)

        if status == "ok":
            self.lbl_score_badge.setText(f"🎯 Aniqlik: {score}%")
            if score >= 88:
                self.lbl_score_badge.setStyleSheet("font-size: 20px; font-weight: 800; color: #10B981;")
                self.lbl_feedback.setText(
                    "🌟 Ajoyib talaffuz! So'z aniq va sof yangradi. Keyingi so'zga o'tishingiz mumkin."
                )
            elif score >= 68:
                self.lbl_score_badge.setStyleSheet("font-size: 20px; font-weight: 800; color: #F59E0B;")
                self.lbl_feedback.setText(
                    "👍 Yaxshi talaffuz! Namunani yana bir marta tinglab, intonatsiyani taqqoslang."
                )
            else:
                self.lbl_score_badge.setStyleSheet("font-size: 20px; font-weight: 800; color: #EF4444;")
                self.lbl_feedback.setText(
                    "⚠️ So'zni namunadagidek aniqroq aytishga harakat qiling va qaytadan sinab ko'ring."
                )

            # Statistikani yangilash
            self.session_practiced += 1
            self.session_scores.append(score)
            self._update_stats_ui()

            # Kunlik topshiriqlar (Daily Quests)
            try:
                import services.daily_quests_service as dqs
                dqs.record_quest_progress("pronunciation", 1)
            except Exception:
                pass

        elif status == "no_speech":
            self.lbl_score_badge.setText("🔇 Ovoz aniqlanmadi")
            self.lbl_score_badge.setStyleSheet("font-size: 16px; font-weight: 700; color: #F59E0B;")
            self.lbl_feedback.setText(
                "Mikrofondan yetarli tovush eshitilmadi. Mikrofonni yaqinroq tutib, balandroq gapiring."
            )
        else:
            self.lbl_score_badge.setText("ℹ️ Ovoz yozildi")
            self.lbl_score_badge.setStyleSheet("font-size: 15px; font-weight: 700; color: #6366F1;")
            self.lbl_feedback.setText(
                "Ovozingiz muvaffaqiyatli yozildi. 'O'z talaffuzingizni tinglash' orqali namunaga solishtiring."
            )

        self.lbl_rec_status.setText("Tahlil yakunlandi.")

    def _update_stats_ui(self):
        """Mini statistikani yangilash."""
        if not self.session_scores:
            return
        avg = int(sum(self.session_scores) / len(self.session_scores))
        great = sum(1 for s in self.session_scores if s >= 90)
        self.lbl_stat_avg.setText(f"🎯 O'rtacha: {avg}%")
        self.lbl_stat_count.setText(f"🗣️ Mashq: {self.session_practiced} ta")
        self.lbl_stat_great.setText(f"🌟 A'lo (90%+): {great}")

    # =========================================================================
    # NAVIGATSIYA
    # =========================================================================

    def _prev_word(self):
        if not self.words_list:
            return
        self._stop_recording()
        self.current_idx = (self.current_idx - 1) % len(self.words_list)
        self._display_current_word()

    def _next_word(self):
        if not self.words_list:
            return
        self._stop_recording()
        self.current_idx = (self.current_idx + 1) % len(self.words_list)
        self._display_current_word()

    def _random_word(self):
        if not self.words_list or len(self.words_list) <= 1:
            return
        import random
        self._stop_recording()
        new_idx = random.randint(0, len(self.words_list) - 1)
        if new_idx == self.current_idx:
            new_idx = (new_idx + 1) % len(self.words_list)
        self.current_idx = new_idx
        self._display_current_word()

    # =========================================================================
    # KLAVIATURA TUGMALARI (SHORTCUTS)
    # =========================================================================

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self._toggle_record()
            event.accept()
        elif key == Qt.Key.Key_R:
            self._speak_normal()
            event.accept()
        elif key == Qt.Key.Key_S:
            self._speak_slow()
            event.accept()
        elif key == Qt.Key.Key_P:
            if self.btn_replay.isEnabled():
                self._play_user_recording()
            event.accept()
        elif key == Qt.Key.Key_Left:
            self._prev_word()
            event.accept()
        elif key == Qt.Key.Key_Right:
            self._next_word()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._stop_recording()
        try:
            self.player.stop()
        except Exception:
            pass
        super().closeEvent(event)
