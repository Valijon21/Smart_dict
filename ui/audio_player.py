"""
Vocab Master Pro — Hands-Free Audio Pleyer (Fon / Quloqchin Rejimi).
Ekranga qaramasdan, fon rejimida so'zlarni ketma-ket tinglab yodlash.
Interfeys qotmasligi uchun alohida QThread orqali ishlaydi.
"""
import time
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QSlider, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPainterPath

import database as db
import tts
import theme_manager
from logger import get_logger

logger = get_logger("audio_player")


class VisualizerWidget(QWidget):
    """Ovoz yangrayotganda ekvalayzer to'lqinlarini chizuvchi zamonaviy vidjet."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(48)
        self.setMaximumHeight(64)
        self.bars = 20
        self.heights = [4.0] * self.bars
        self.is_active = False
        self.bar_color = QColor("#4F46E5")
        self._phase = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(50)

    def set_active(self, active: bool):
        self.is_active = active

    def set_color(self, hex_color: str):
        self.bar_color = QColor(hex_color)
        self.update()

    def _animate(self):
        self._phase += 0.2
        if self.is_active:
            for i in range(self.bars):
                target = max(6.0, min(self.height() - 8.0, 10.0 + 35.0 * ((i * 7 + int(self._phase * 10)) % 11) / 10.0))
                self.heights[i] += (target - self.heights[i]) * 0.35
        else:
            for i in range(self.bars):
                self.heights[i] += (4.0 - self.heights[i]) * 0.25
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        gap = 4
        bar_w = max(3.0, (w - (self.bars - 1) * gap) / self.bars)

        painter.setBrush(QBrush(self.bar_color))
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(self.bars):
            bh = self.heights[i]
            bx = i * (bar_w + gap)
            by = (h - bh) / 2.0
            path = QPainterPath()
            path.addRoundedRect(QRectF(bx, by, bar_w, bh), 2.0, 2.0)
            painter.fillPath(path, QBrush(self.bar_color))


class AudioWorkerThread(QThread):
    """Fon rejimida so'zlarni ketma-ket o'quvchi xavfsiz ishchi oqim."""
    word_changed = pyqtSignal(dict, int, int)     # (word_dict, current_idx, total)
    state_changed = pyqtSignal(bool)             # is_playing
    audio_speaking = pyqtSignal(bool)            # tts is actively speaking

    def __init__(self):
        super().__init__()
        self.playlist: list[dict] = []
        self.current_index = 0
        self.is_running = False
        self.is_paused = False
        self.speed_rate = 150
        self.interval_sec = 2.0
        self.speak_uzbek = True
        self.speak_example = False
        self.loop_mode = True
        self.shuffle_mode = False
        self._skip_requested = False
        self._prev_requested = False

    def set_playlist(self, words: list[dict]):
        self.playlist = list(words)
        self.current_index = 0

    def pause_playback(self):
        self.is_paused = True
        self.audio_speaking.emit(False)
        self.state_changed.emit(False)
        tts.stop()

    def resume_playback(self):
        self.is_paused = False
        self.state_changed.emit(True)

    def stop_playback(self):
        self.is_running = False
        self.is_paused = False
        self.audio_speaking.emit(False)
        self.state_changed.emit(False)
        tts.stop()

    def next_track(self):
        self._skip_requested = True
        tts.stop()

    def prev_track(self):
        self._prev_requested = True
        tts.stop()

    def run(self):
        self.is_running = True
        self.is_paused = False
        self.state_changed.emit(True)

        while self.is_running:
            if not self.playlist:
                time.sleep(0.3)
                continue

            if self.is_paused:
                time.sleep(0.1)
                continue

            if self.current_index >= len(self.playlist):
                if self.loop_mode and len(self.playlist) > 0:
                    self.current_index = 0
                else:
                    break

            word = self.playlist[self.current_index]
            total = len(self.playlist)
            self.word_changed.emit(word, self.current_index + 1, total)

            # 1. Inglizcha so'zni talaffuz qilish
            if not self.is_running or self.is_paused:
                continue

            eng = word.get("english", "").strip()
            if eng:
                self.audio_speaking.emit(True)
                tts.speak_async(eng)
                self._wait_speaking(max_wait=3.5)
                self.audio_speaking.emit(False)

            # 2. Oraliq pauza (foydalanuvchi eslashi uchun)
            if not self._sleep_with_check(self.interval_sec):
                continue

            # 3. O'zbekcha tarjimani o'qish
            uz = word.get("uzbek", "").strip()
            if self.speak_uzbek and uz and self.is_running and not self.is_paused:
                self.audio_speaking.emit(True)
                tts.speak_async(uz)
                self._wait_speaking(max_wait=4.0)
                self.audio_speaking.emit(False)

            # 4. Namuna gapni o'qish
            ex = word.get("example", "").strip()
            if self.speak_example and ex and self.is_running and not self.is_paused:
                self._sleep_with_check(1.0)
                self.audio_speaking.emit(True)
                tts.speak_async(ex)
                self._wait_speaking(max_wait=6.0)
                self.audio_speaking.emit(False)

            # Keyingi so'zga o'tishdan oldingi oraliq pauza
            if not self._sleep_with_check(1.5):
                continue

            # Keyingi indeksga o'tish
            if self._prev_requested:
                self._prev_requested = False
                self.current_index = max(0, self.current_index - 1)
            elif self._skip_requested:
                self._skip_requested = False
                self.current_index = (self.current_index + 1) % max(1, len(self.playlist))
            elif self.shuffle_mode and len(self.playlist) > 1:
                next_idx = self.current_index
                while next_idx == self.current_index:
                    next_idx = random.randint(0, len(self.playlist) - 1)
                self.current_index = next_idx
            else:
                self.current_index += 1

        self.audio_speaking.emit(False)
        self.state_changed.emit(False)

    def _wait_speaking(self, max_wait: float = 4.0):
        start = time.time()
        while time.time() - start < max_wait and self.is_running:
            if self._skip_requested or self._prev_requested:
                break
            if not tts.is_speaking():
                break
            time.sleep(0.08)

    def _sleep_with_check(self, duration: float) -> bool:
        start = time.time()
        while time.time() - start < duration:
            if not self.is_running:
                return False
            if self._skip_requested or self._prev_requested:
                return False
            if self.is_paused:
                time.sleep(0.1)
                start = time.time()
                continue
            time.sleep(0.05)
        return True


class AudioPlayerWidget(QWidget):
    """Hands-Free Audio Pleyer — Asosiy oynaga qo'shiluvchi sahifa."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = AudioWorkerThread()
        self.worker.word_changed.connect(self._on_word_changed)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.audio_speaking.connect(self._on_audio_speaking)

        self._build_ui()
        self.apply_theme(theme_manager.get_active_theme())
        self.load_words()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        # 1. Sarlavha qatori
        header_row = QHBoxLayout()
        self.title_lbl = QLabel("🎧 Hands-Free Audio Pleyer")
        self.title_lbl.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "📚 Barcha so'zlar",
            "🧠 Bugun takrorlash kerak (SM-2)",
            "⚠️ Zaif / ko'p xato qilingan so'zlar",
            "🌱 O'rganilayotgan so'zlar"
        ])
        self.mode_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mode_combo.currentIndexChanged.connect(self.load_words)
        header_row.addWidget(self.mode_combo)
        root.addLayout(header_row)

        self.sub_lbl = QLabel(
            "Ekranga qaramasdan quloqchin orqali so'zlarni eshitib yodlang. "
            "Dastur so'zni aytadi, pauza beradi va tarjimasini o'qiydi."
        )
        self.sub_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        root.addWidget(self.sub_lbl)

        # 2. Markaziy Katta Pleyer Kartasi
        self.player_card = QFrame()
        card_layout = QVBoxLayout(self.player_card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.track_idx_lbl = QLabel("So'z: 0 / 0")
        self.track_idx_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px; font-weight: 600;")
        self.track_idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.track_idx_lbl)

        # Visualizer
        self.visualizer = VisualizerWidget()
        card_layout.addWidget(self.visualizer)

        self.word_lbl = QLabel("So'zlar yuklanmoqda...")
        self.word_lbl.setStyleSheet("color: white; font-size: 34px; font-weight: 800; padding: 4px;")
        self.word_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.word_lbl)

        phonetic_row = QHBoxLayout()
        phonetic_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phonetic_row.setSpacing(8)

        self.phonetic_badge = QLabel("/transcription/")
        self.phonetic_badge.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; border-radius: 6px; "
            "padding: 4px 10px; font-size: 14px; font-family: 'Segoe UI', sans-serif;"
        )
        phonetic_row.addWidget(self.phonetic_badge)

        self.pos_badge = QLabel("[noun]")
        self.pos_badge.setStyleSheet(
            "background-color: #064E3B; color: #6EE7B7; border-radius: 6px; "
            "padding: 4px 10px; font-size: 12px; font-weight: 700;"
        )
        phonetic_row.addWidget(self.pos_badge)
        card_layout.addLayout(phonetic_row)

        self.trans_lbl = QLabel("Tarjima")
        self.trans_lbl.setStyleSheet("color: #34D399; font-size: 22px; font-weight: 600; padding: 6px;")
        self.trans_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.trans_lbl)

        self.example_lbl = QLabel("")
        self.example_lbl.setStyleSheet("color: #9CA3AF; font-size: 14px; font-style: italic;")
        self.example_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_lbl.setWordWrap(True)
        card_layout.addWidget(self.example_lbl)

        root.addWidget(self.player_card, 1)

        # 3. Pleyer Boshqaruv Tugmalari Paneli
        controls_frame = QFrame()
        ctrl_layout = QHBoxLayout(controls_frame)
        ctrl_layout.setContentsMargins(18, 12, 18, 12)
        ctrl_layout.setSpacing(16)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_shuffle = QPushButton("🔀 Tasodifiy")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shuffle.clicked.connect(self._toggle_shuffle)
        ctrl_layout.addWidget(self.btn_shuffle)

        self.btn_prev = QPushButton("⏮️ Oldingi")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.clicked.connect(self.worker.prev_track)
        ctrl_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton("▶️ Tinglashni Boshlash")
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setMinimumHeight(44)
        self.btn_play.setMinimumWidth(180)
        self.btn_play.clicked.connect(self._toggle_play)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_next = QPushButton("Keyingi ⏭️")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(self.worker.next_track)
        ctrl_layout.addWidget(self.btn_next)

        self.btn_loop = QPushButton("🔁 Takrorlash")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_loop.clicked.connect(self._toggle_loop)
        ctrl_layout.addWidget(self.btn_loop)

        root.addWidget(controls_frame)

        # 4. Sozlamalar (Interval va Checkboxlar)
        settings_frame = QFrame()
        set_layout = QHBoxLayout(settings_frame)
        set_layout.setContentsMargins(16, 10, 16, 10)
        set_layout.setSpacing(20)

        set_layout.addWidget(QLabel("⏱️ Oraliq kutish:"))
        self.interval_lbl = QLabel("2.0s")
        self.interval_lbl.setStyleSheet("color: white; font-weight: 700;")
        self.slider_interval = QSlider(Qt.Orientation.Horizontal)
        self.slider_interval.setRange(10, 45)
        self.slider_interval.setValue(20)
        self.slider_interval.valueChanged.connect(self._on_interval_changed)
        set_layout.addWidget(self.slider_interval)
        set_layout.addWidget(self.interval_lbl)

        self.cb_uzbek = QCheckBox("O'zbekcha tarjimani o'qish")
        self.cb_uzbek.setChecked(True)
        self.cb_uzbek.stateChanged.connect(lambda s: setattr(self.worker, "speak_uzbek", bool(s)))
        set_layout.addWidget(self.cb_uzbek)

        self.cb_example = QCheckBox("Namuna gapni o'qish")
        self.cb_example.setChecked(False)
        self.cb_example.stateChanged.connect(lambda s: setattr(self.worker, "speak_example", bool(s)))
        set_layout.addWidget(self.cb_example)

        root.addWidget(settings_frame)

    def load_words(self):
        idx = self.mode_combo.currentIndex()
        if idx == 0:
            words = db.get_all_words()
        elif idx == 1:
            words = db.get_due_words()
            if not words:
                words = db.get_all_words()
        elif idx == 2:
            words = db.get_weakest_words(limit=30)
            if not words:
                words = db.get_all_words()
        else:
            words = db.get_words_by_status("learning")
            if not words:
                words = db.get_all_words()

        if not words:
            self.word_lbl.setText("Lug'atda so'zlar topilmadi")
            self.trans_lbl.setText("Avval so'z qo'shing")
            self.track_idx_lbl.setText("0 / 0")
            return

        words = [dict(w) for w in words]
        self.worker.set_playlist(words)
        self.track_idx_lbl.setText(f"So'z: 1 / {len(words)}")
        first = words[0]
        self._display_word(first)

    def _display_word(self, word: dict):
        eng = word.get("english", "")
        uz = word.get("uzbek", "")
        pho = word.get("phonetic", "") or ""
        pos = word.get("part_of_speech", "") or "word"
        ex = word.get("example", "") or ""

        self.word_lbl.setText(eng)
        self.trans_lbl.setText(uz)
        self.phonetic_badge.setText(pho if pho else "/—/")
        self.pos_badge.setText(f"[{pos}]")
        self.example_lbl.setText(f"“{ex}”" if ex else "")

    def _toggle_play(self):
        if not self.worker.is_running:
            self.worker.start()
        elif self.worker.is_paused:
            self.worker.resume_playback()
        else:
            self.worker.pause_playback()

    def _toggle_shuffle(self, checked: bool):
        self.worker.shuffle_mode = checked

    def _toggle_loop(self, checked: bool):
        self.worker.loop_mode = checked

    def _on_interval_changed(self, val: int):
        sec = val / 10.0
        self.interval_lbl.setText(f"{sec:.1f}s")
        self.worker.interval_sec = sec

    def _on_word_changed(self, word: dict, current_idx: int, total: int):
        self.track_idx_lbl.setText(f"So'z: {current_idx} / {total}")
        self._display_word(word)

    def _on_state_changed(self, is_playing: bool):
        t = theme_manager.get_active_theme()
        if is_playing:
            self.btn_play.setText("⏸️ Pauza")
            self.btn_play.setStyleSheet(
                f"QPushButton {{ background-color: #EF4444; color: white; border-radius: 8px; "
                f"font-size: 14px; font-weight: 700; padding: 10px 24px; }}"
                f"QPushButton:hover {{ background-color: #DC2626; }}"
            )
        else:
            self.btn_play.setText("▶️ Tinglashni Boshlash")
            self.btn_play.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
                f"font-size: 14px; font-weight: 700; padding: 10px 24px; }}"
                f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            )

    def _on_audio_speaking(self, is_speaking: bool):
        self.visualizer.set_active(is_speaking)

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        self.title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 22px; font-weight: 700;")
        self.sub_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")

        self.player_card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border-radius: 16px; border: 1.5px solid {t.border}; }}"
        )
        self.visualizer.set_color(t.primary)

        self.mode_combo.setStyleSheet(
            f"QComboBox {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 600; }}"
        )

        btn_style = (
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; border-color: {t.primary}; }}"
            f"QPushButton:checked {{ background-color: {t.primary}; color: white; border-color: {t.primary}; }}"
        )
        self.btn_shuffle.setStyleSheet(btn_style)
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_next.setStyleSheet(btn_style)
        self.btn_loop.setStyleSheet(btn_style)

        if not self.worker.is_running or self.worker.is_paused:
            self.btn_play.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
                f"font-size: 14px; font-weight: 700; padding: 10px 24px; }}"
                f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            )

    def closeEvent(self, event):
        self.worker.stop_playback()
        self.worker.wait(1000)
        super().closeEvent(event)
