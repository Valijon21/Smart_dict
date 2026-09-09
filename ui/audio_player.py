"""
Vocab Master Pro — Hands-Free Audio Pleyer (Fon / Quloqchin Rejimi).
Ekranga qaramasdan, fon rejimida so'zlarni ketma-ket tinglab yodlash.
Interfeys qotmasligi uchun alohida QThread va threading.Event orqali xavfsiz ishlaydi.
"""
import time
import random
import threading
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
        self.bars = 22
        self.heights = [4.0] * self.bars
        self.is_active = False
        self.bar_color = QColor("#4F46E5")
        self._phase = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(45)

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
    """Fon rejimida so'zlarni ketma-ket o'quvchi xavfsiz va barqaror ishchi oqim."""
    word_changed = pyqtSignal(dict, int, int)     # (word_dict, current_idx, total)
    state_changed = pyqtSignal(bool)             # is_playing
    audio_speaking = pyqtSignal(bool)            # tts is actively speaking

    def __init__(self):
        super().__init__()
        self.playlist: list[dict] = []
        self.current_index = 0
        self.speed_rate = 150

        # Standart interval 4.0 soniya (bazadan o'qiladi)
        try:
            val_sec = float(db.get_setting("audio_player_interval_sec", "4.0") or "4.0")
        except Exception:
            val_sec = 4.0
        self.interval_sec = max(1.0, min(8.0, val_sec))

        self.speak_uzbek = True
        self.speak_example = False
        self.loop_mode = True
        self.shuffle_mode = False

        self._stop_event = threading.Event()
        self._skip_event = threading.Event()
        self._prev_event = threading.Event()
        self._is_paused = False

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set() and self.isRunning()

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def set_playlist(self, words: list[dict]):
        self.playlist = list(words)
        self.current_index = 0

    def pause_playback(self):
        self._is_paused = True
        self.audio_speaking.emit(False)
        self.state_changed.emit(False)
        tts.stop()

    def resume_playback(self):
        self._is_paused = False
        self.state_changed.emit(True)

    def stop_playback(self):
        self._stop_event.set()
        self._skip_event.set()
        self._is_paused = False
        self.audio_speaking.emit(False)
        self.state_changed.emit(False)
        tts.stop()

    def next_track(self):
        self._skip_event.set()
        tts.stop()

    def prev_track(self):
        self._prev_event.set()
        tts.stop()

    def _sleep_interruptible(self, duration: float) -> bool:
        """
        Kutish vaqtini xavfsiz bo'lib o'tkazadi.
        Agar to'xtatish yoki skip buyrug'i kelsa darhol False qaytaradi.
        """
        start = time.time()
        while time.time() - start < duration:
            if self._stop_event.is_set():
                return False
            if self._skip_event.is_set() or self._prev_event.is_set():
                return False
            while self._is_paused and not self._stop_event.is_set():
                if self._skip_event.is_set() or self._prev_event.is_set():
                    break
                time.sleep(0.08)
            time.sleep(0.05)
        return True

    def _wait_speaking(self, max_wait: float = 4.0):
        start = time.time()
        while time.time() - start < max_wait:
            if self._stop_event.is_set() or self._skip_event.is_set() or self._prev_event.is_set():
                break
            if not tts.is_speaking():
                break
            time.sleep(0.06)

    def run(self):
        self._stop_event.clear()
        self._skip_event.clear()
        self._prev_event.clear()
        self._is_paused = False
        self.state_changed.emit(True)

        while not self._stop_event.is_set():
            if not self.playlist:
                time.sleep(0.2)
                continue

            while self._is_paused and not self._stop_event.is_set():
                if self._skip_event.is_set() or self._prev_event.is_set():
                    break
                time.sleep(0.08)

            if self._stop_event.is_set():
                break

            # Indeks chegaralarini to'g'rilash
            if self.current_index >= len(self.playlist):
                if self.loop_mode and len(self.playlist) > 0:
                    self.current_index = 0
                else:
                    break
            elif self.current_index < 0:
                self.current_index = 0

            word = self.playlist[self.current_index]
            total = len(self.playlist)
            self.word_changed.emit(word, self.current_index + 1, total)

            # Yangi so'z boshlanganda o'tish hodisalarini tozalash
            self._skip_event.clear()
            self._prev_event.clear()

            # 1. Inglizcha so'zni talaffuz qilish
            eng = word.get("english", "").strip()
            if eng and not self._is_paused and not self._stop_event.is_set():
                self.audio_speaking.emit(True)
                tts.speak_async(eng)
                self._wait_speaking(max_wait=3.5)
                self.audio_speaking.emit(False)

            # 2. Oraliq pauza (Foydalanuvchi so'zni eslashi uchun - standart 4.0 soniya)
            interrupted = not self._sleep_interruptible(self.interval_sec)

            # 3. O'zbekcha tarjimani o'qish
            if not interrupted and self.speak_uzbek and not self._is_paused and not self._stop_event.is_set():
                uz = word.get("uzbek", "").strip()
                if uz:
                    self.audio_speaking.emit(True)
                    tts.speak_async(uz)
                    self._wait_speaking(max_wait=4.0)
                    self.audio_speaking.emit(False)

            # 4. Namuna gapni o'qish (agar belgilangan bo'lsa)
            if not interrupted and self.speak_example and not self._is_paused and not self._stop_event.is_set():
                ex = word.get("example", "").strip()
                if ex:
                    self._sleep_interruptible(1.0)
                    self.audio_speaking.emit(True)
                    tts.speak_async(ex)
                    self._wait_speaking(max_wait=6.0)
                    self.audio_speaking.emit(False)

            # 5. Keyingi so'zga o'tish oldidan qisqa oraliq pauza (1.0 soniya)
            if not interrupted and not self._is_paused and not self._stop_event.is_set():
                self._sleep_interruptible(1.0)

            # Indeksni yangilash
            if self._prev_event.is_set():
                self._prev_event.clear()
                self.current_index = max(0, self.current_index - 1)
            elif self._skip_event.is_set():
                self._skip_event.clear()
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


class AudioPlayerWidget(QWidget):
    """Hands-Free Audio Pleyer — Asosiy oynaga qo'shiluvchi zamonaviy sahifa."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = AudioWorkerThread()
        self.worker.word_changed.connect(self._on_word_changed)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.audio_speaking.connect(self._on_audio_speaking)

        self._build_ui()
        self.load_interval_from_settings()
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
            "Dastur so'zni aytadi, belgilangan pauza beradi va tarjimasini o'qiydi."
        )
        self.sub_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        root.addWidget(self.sub_lbl)

        # 2. Markaziy Katta Pleyer Kartasi
        self.player_card = QFrame()
        card_layout = QVBoxLayout(self.player_card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(16)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.track_idx_lbl = QLabel("So'z: 0 / 0")
        self.track_idx_lbl.setStyleSheet("color: #9CA3AF; font-size: 14px; font-weight: 600;")
        self.track_idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.track_idx_lbl)

        # Visualizer
        self.visualizer = VisualizerWidget()
        card_layout.addWidget(self.visualizer)

        self.word_lbl = QLabel("So'zlar yuklanmoqda...")
        self.word_lbl.setStyleSheet("color: white; font-size: 38px; font-weight: 800; padding: 4px;")
        self.word_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.word_lbl)

        phonetic_row = QHBoxLayout()
        phonetic_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phonetic_row.setSpacing(10)

        self.phonetic_badge = QLabel("/transcription/")
        self.phonetic_badge.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; border-radius: 8px; "
            "padding: 6px 14px; font-size: 15px; font-family: 'Segoe UI', sans-serif;"
        )
        phonetic_row.addWidget(self.phonetic_badge)

        self.pos_badge = QLabel("[word]")
        self.pos_badge.setStyleSheet(
            "background-color: #064E3B; color: #6EE7B7; border-radius: 8px; "
            "padding: 6px 12px; font-size: 13px; font-weight: 700;"
        )
        phonetic_row.addWidget(self.pos_badge)
        card_layout.addLayout(phonetic_row)

        self.trans_lbl = QLabel("Tarjima")
        self.trans_lbl.setStyleSheet("color: #34D399; font-size: 24px; font-weight: 700; padding: 6px;")
        self.trans_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.trans_lbl)

        self.example_lbl = QLabel("")
        self.example_lbl.setStyleSheet("color: #9CA3AF; font-size: 15px; font-style: italic;")
        self.example_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_lbl.setWordWrap(True)
        card_layout.addWidget(self.example_lbl)

        root.addWidget(self.player_card, 1)

        # 3. Pleyer Boshqaruv Tugmalari Paneli
        controls_frame = QFrame()
        ctrl_layout = QHBoxLayout(controls_frame)
        ctrl_layout.setContentsMargins(18, 12, 18, 12)
        ctrl_layout.setSpacing(14)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_shuffle = QPushButton("🔀 Tasodifiy")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shuffle.setMinimumHeight(44)
        self.btn_shuffle.clicked.connect(self._toggle_shuffle)
        ctrl_layout.addWidget(self.btn_shuffle)

        self.btn_prev = QPushButton("⏮️ Oldingi")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setMinimumHeight(44)
        self.btn_prev.clicked.connect(self.worker.prev_track)
        ctrl_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton("▶️ Tinglashni Boshlash")
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setMinimumHeight(46)
        self.btn_play.setMinimumWidth(180)
        self.btn_play.clicked.connect(self._toggle_play)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹️ To'xtatish")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setMinimumHeight(44)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        ctrl_layout.addWidget(self.btn_stop)

        self.btn_next = QPushButton("Keyingi ⏭️")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setMinimumHeight(44)
        self.btn_next.clicked.connect(self.worker.next_track)
        ctrl_layout.addWidget(self.btn_next)

        self.btn_loop = QPushButton("🔁 Takrorlash")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_loop.setMinimumHeight(44)
        self.btn_loop.clicked.connect(self._toggle_loop)
        ctrl_layout.addWidget(self.btn_loop)

        root.addWidget(controls_frame)

        # 4. Sozlamalar (Interval va Checkboxlar)
        settings_frame = QFrame()
        set_layout = QHBoxLayout(settings_frame)
        set_layout.setContentsMargins(18, 12, 18, 12)
        set_layout.setSpacing(20)

        set_layout.addWidget(QLabel("⏱️ Oraliq kutish vaqti:"))
        self.interval_lbl = QLabel("4.0s")
        self.interval_lbl.setStyleSheet("color: white; font-weight: 700; font-size: 14px; min-width: 45px;")
        self.slider_interval = QSlider(Qt.Orientation.Horizontal)
        self.slider_interval.setRange(10, 80)
        self.slider_interval.setValue(40)
        self.slider_interval.valueChanged.connect(self._on_interval_changed)
        set_layout.addWidget(self.slider_interval, 1)
        set_layout.addWidget(self.interval_lbl)

        self.cb_uzbek = QCheckBox("O'zbekcha tarjimani o'qish")
        self.cb_uzbek.setChecked(True)
        self.cb_uzbek.setStyleSheet("font-size: 13px;")
        self.cb_uzbek.stateChanged.connect(lambda s: setattr(self.worker, "speak_uzbek", bool(s)))
        set_layout.addWidget(self.cb_uzbek)

        self.cb_example = QCheckBox("Namuna gapni o'qish")
        self.cb_example.setChecked(False)
        self.cb_example.setStyleSheet("font-size: 13px;")
        self.cb_example.stateChanged.connect(lambda s: setattr(self.worker, "speak_example", bool(s)))
        set_layout.addWidget(self.cb_example)

        root.addWidget(settings_frame)

    def load_interval_from_settings(self):
        """Baza yoki sozlamalardagi audio interval qiymatini yuklaydi."""
        try:
            val_sec = float(db.get_setting("audio_player_interval_sec", "4.0") or "4.0")
        except Exception:
            val_sec = 4.0
        val_sec = max(1.0, min(8.0, val_sec))
        self.worker.interval_sec = val_sec
        self.slider_interval.blockSignals(True)
        self.slider_interval.setValue(int(val_sec * 10))
        self.slider_interval.blockSignals(False)
        self.interval_lbl.setText(f"{val_sec:.1f}s")

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
        if not self.worker.isRunning() or not self.worker.is_running:
            self.worker.start()
        elif self.worker.is_paused:
            self.worker.resume_playback()
        else:
            self.worker.pause_playback()

    def _on_stop_clicked(self):
        self.worker.stop_playback()
        self.btn_play.setText("▶️ Tinglashni Boshlash")
        t = theme_manager.get_active_theme()
        self.btn_play.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
            f"font-size: 14px; font-weight: 700; padding: 10px 24px; }}"
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )

    def _toggle_shuffle(self, checked: bool):
        self.worker.shuffle_mode = checked

    def _toggle_loop(self, checked: bool):
        self.worker.loop_mode = checked

    def _on_interval_changed(self, val: int):
        sec = val / 10.0
        self.interval_lbl.setText(f"{sec:.1f}s")
        self.worker.interval_sec = sec
        db.set_setting("audio_player_interval_sec", f"{sec:.1f}")

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
        self.btn_stop.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: #EF4444; border: 1px solid #7F1D1D; "
            f"border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: #7F1D1D; color: white; }}"
        )

        if not self.worker.isRunning() or not self.worker.is_running or self.worker.is_paused:
            self.btn_play.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; "
                f"font-size: 14px; font-weight: 700; padding: 10px 24px; }}"
                f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            )

    def closeEvent(self, event):
        self.worker.stop_playback()
        self.worker.wait(800)
        super().closeEvent(event)
