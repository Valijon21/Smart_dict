"""
Vocab Master Pro — Hands-Free Audio Pleyer (Fon / Quloqchin Rejimi).
Ekranga qaramasdan, fon rejimida so'zlarni ketma-ket tinglab yodlash.
Ekrandagi so'z bilan ovozli talaffuz 100% sinxron ishlashi kafolatlangan.
"""
import time
import random
import threading
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QSlider, QCheckBox, QDialog, QFileDialog,
    QProgressBar, QMessageBox, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPainterPath

import database as db
import tts
import theme_manager
from ui.components.game_source_selector import GameSourceSelector
import services.game_word_provider as gwp
from logger import get_logger

logger = get_logger("audio_player")


def format_uzbek_translation(uz: str) -> str:
    """
    Agar o'zbekcha tarjima uzun bo'lsa yoki bir nechta sinonimlardan iborat bo'lsa,
    uni ekranga qulay va chiroyli tarzda 2 qatorga (ikki qator) ajratadi.
    """
    if not uz:
        return ""
    uz = uz.strip()
    if len(uz) <= 35 or "\n" in uz:
        return uz

    if "," in uz:
        parts = [p.strip() for p in uz.split(",") if p.strip()]
        if len(parts) >= 2:
            total_len = len(uz)
            cur_len = 0
            best_idx = 1
            min_diff = float("inf")
            for i in range(len(parts) - 1):
                cur_len += len(parts[i]) + 2
                rem_len = total_len - cur_len
                diff = abs(cur_len - rem_len)
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i + 1

            line1 = ", ".join(parts[:best_idx])
            line2 = ", ".join(parts[best_idx:])
            return f"{line1},\n{line2}"

    words = uz.split()
    if len(words) >= 4:
        mid = len(words) // 2
        return " ".join(words[:mid]) + "\n" + " ".join(words[mid:])

    return uz


class VisualizerWidget(QWidget):
    """Ovoz yangrayotganda ekvalayzer to'lqinlarini chizuvchi nafis ixcham vidjet."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 28)
        self.bars = 24
        self.heights = [3.0] * self.bars
        self.is_active = False
        self.bar_color = QColor("#6366F1")
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
                norm_pos = abs(i - (self.bars / 2.0)) / (self.bars / 2.0)
                envelope = 1.0 - (norm_pos * 0.45)
                wave = ((i * 7 + int(self._phase * 10)) % 11) / 10.0
                target = max(3.0, min(self.height() - 4.0, (6.0 + 16.0 * wave) * envelope))
                self.heights[i] += (target - self.heights[i]) * 0.35
        else:
            for i in range(self.bars):
                self.heights[i] += (3.0 - self.heights[i]) * 0.25
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        gap = 3.5
        bar_w = max(2.5, (w - (self.bars - 1) * gap) / self.bars)

        painter.setBrush(QBrush(self.bar_color))
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(self.bars):
            bh = self.heights[i]
            bx = i * (bar_w + gap)
            by = (h - bh) / 2.0
            path = QPainterPath()
            path.addRoundedRect(QRectF(bx, by, bar_w, bh), 1.5, 1.5)
            painter.fillPath(path, QBrush(self.bar_color))



class AudioWorkerThread(QThread):
    """Fon rejimida so'zlarni ketma-ket o'quvchi xavfsiz va to'liq sinxron ishchi oqim."""
    word_changed = pyqtSignal(dict, int, int)     # (word_dict, current_idx, total)
    state_changed = pyqtSignal(bool)             # is_playing
    audio_speaking = pyqtSignal(bool)            # tts is actively speaking

    def __init__(self):
        super().__init__()
        self.playlist: list[dict] = []
        self.current_index = 0
        self.speed_rate = 150
        self._lock = threading.Lock()

        # Standart interval 4.0 soniya (bazadan o'qiladi)
        try:
            val_sec = float(db.get_setting("audio_player_interval_sec", "4.0") or "4.0")
        except Exception:
            val_sec = 4.0
        self.interval_sec = max(1.0, min(8.0, val_sec))

        self.speak_uzbek = False
        self.speak_example = False
        self.loop_mode = True
        self.shuffle_mode = False

        self._stop_event = threading.Event()
        self._skip_event = threading.Event()
        self._is_paused = False

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set() and self.isRunning()

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def set_playlist(self, words: list[dict]):
        with self._lock:
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

    def skip_current(self):
        """Hozirgi ijroni to'xtatib, belgilangan indeksdagi so'zga darhol o'tish."""
        self._skip_event.set()
        tts.stop()

    def next_track(self):
        with self._lock:
            if self.playlist:
                if self.shuffle_mode and len(self.playlist) > 1:
                    next_idx = self.current_index
                    while next_idx == self.current_index:
                        next_idx = random.randint(0, len(self.playlist) - 1)
                    self.current_index = next_idx
                else:
                    self.current_index = (self.current_index + 1) % len(self.playlist)
        self.skip_current()

    def prev_track(self):
        with self._lock:
            if self.playlist:
                self.current_index = max(0, self.current_index - 1)
        self.skip_current()

    def _should_cancel(self) -> bool:
        """Talaffuz yoki kutish jarayonini bekor qilish kerakligini tekshiradi."""
        return self._stop_event.is_set() or self._skip_event.is_set()

    def _sleep_interruptible(self, duration: float) -> bool:
        """Kutish vaqtini xavfsiz bo'lib o'tkazadi."""
        start = time.time()
        while time.time() - start < duration:
            if self._should_cancel():
                return False
            while self._is_paused and not self._stop_event.is_set():
                if self._skip_event.is_set():
                    break
                time.sleep(0.06)
            time.sleep(0.04)
        return True

    def run(self):
        self._stop_event.clear()
        self._skip_event.clear()
        self._is_paused = False
        self.state_changed.emit(True)

        while not self._stop_event.is_set():
            if not self.playlist:
                time.sleep(0.2)
                continue

            while self._is_paused and not self._stop_event.is_set():
                if self._skip_event.is_set():
                    break
                time.sleep(0.06)

            if self._stop_event.is_set():
                break

            with self._lock:
                # Indeks chegaralarini to'g'rilash
                if self.current_index >= len(self.playlist):
                    if self.loop_mode and len(self.playlist) > 0:
                        self.current_index = 0
                    else:
                        break
                elif self.current_index < 0:
                    self.current_index = 0

                word = self.playlist[self.current_index]
                idx = self.current_index
                total = len(self.playlist)

            # Ekrandagi so'zni talaffuzdan oldinroq DARHOL ko'rsatish
            self.word_changed.emit(word, idx + 1, total)

            # Yangi so'z ijrosini boshlashdan oldin skip bayrog'ini tozalash
            self._skip_event.clear()

            # 1. Inglizcha so'zni talaffuz qilish va u to'liq tugaguncha kutish (sinxron)
            eng = word.get("english", "").strip()
            if eng and not self._is_paused and not self._stop_event.is_set():
                self.audio_speaking.emit(True)
                tts.speak_and_wait(eng, max_wait=4.5, cancel_check=self._should_cancel)
                self.audio_speaking.emit(False)

            if self._should_cancel():
                self._skip_event.clear()
                continue

            # 2. Oraliq pauza (Foydalanuvchi so'zni eslashi uchun - standart 4.0 soniya)
            if not self._sleep_interruptible(self.interval_sec):
                self._skip_event.clear()
                continue

            # 3. O'zbekcha tarjimani o'qish (agar yoqilgan bo'lsa, faqat birinchi toza so'z)
            if self.speak_uzbek and not self._is_paused and not self._stop_event.is_set():
                raw_uz = word.get("uzbek", "").strip()
                uz = raw_uz.split(",")[0].split(";")[0].strip() if raw_uz else ""
                if uz:
                    self.audio_speaking.emit(True)
                    tts.speak_and_wait(uz, max_wait=3.5, cancel_check=self._should_cancel)
                    self.audio_speaking.emit(False)

            if self._should_cancel():
                self._skip_event.clear()
                continue

            # 4. Namuna gapni o'qish (agar yoqilgan bo'lsa)
            if self.speak_example and not self._is_paused and not self._stop_event.is_set():
                ex = word.get("example", "").strip()
                if ex:
                    self._sleep_interruptible(1.0)
                    self.audio_speaking.emit(True)
                    tts.speak_and_wait(ex, max_wait=6.0, cancel_check=self._should_cancel)
                    self.audio_speaking.emit(False)

            if self._should_cancel():
                self._skip_event.clear()
                continue

            # 5. Keyingi so'zga o'tish oldidan qisqa oraliq pauza (0.8 soniya)
            if not self._sleep_interruptible(0.8):
                self._skip_event.clear()
                continue

            # Normal avtomatik o'tish (foydalanuvchi tugma bosmagan holat)
            with self._lock:
                if not self._skip_event.is_set():
                    if self.shuffle_mode and len(self.playlist) > 1:
                        next_idx = self.current_index
                        while next_idx == self.current_index:
                            next_idx = random.randint(0, len(self.playlist) - 1)
                        self.current_index = next_idx
                    else:
                        self.current_index += 1

class AudioExportThread(QThread):
    """So'zlarni fonda .wav formatdagi audio podcastga eksport qiluvchi oqim."""
    progress = pyqtSignal(int, int)   # current, total
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, words: list[dict], filepath: str, interval_sec: float, include_uzbek: bool, include_example: bool):
        super().__init__()
        self.words = words
        self.filepath = filepath
        self.interval_sec = interval_sec
        self.include_uzbek = include_uzbek
        self.include_example = include_example
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        def _prog(cur, tot):
            self.progress.emit(cur, tot)

        def _chk_cancel():
            return self._cancelled

        try:
            ok = tts.export_words_to_audio(
                words=self.words,
                output_filepath=self.filepath,
                interval_sec=self.interval_sec,
                include_uzbek=self.include_uzbek,
                include_example=self.include_example,
                progress_cb=_prog,
                cancel_cb=_chk_cancel
            )
            if self._cancelled:
                self.finished.emit(False, "Eksport jarayoni bekor qilindi.")
            elif ok:
                self.finished.emit(True, f"Audio fayl muvaffaqiyatli saqlandi:\n{self.filepath}")
            else:
                self.finished.emit(False, "Audio eksport qilishda xatolik yuz berdi.")
        except Exception as e:
            self.finished.emit(False, f"Eksportda kutilmagan xatolik: {e}")


class AudioExportDialog(QDialog):
    """Lug'at so'zlarini oflayn audio podcast (.wav) sifatida yuklab olish oynasi."""
    def __init__(self, current_playlist: list[dict], parent=None, default_source_title: str = "Tanlangan to'plam"):
        super().__init__(parent)
        self.current_playlist = current_playlist
        self.default_source_title = default_source_title
        self.export_filepath = ""
        self.export_thread: AudioExportThread | None = None
        self.setWindowTitle(f"🎙️ Oflayn Audio Podcast Eksport — {default_source_title}")
        self.setFixedWidth(540)
        self._build_ui()

    def _build_ui(self):
        t = theme_manager.get_active_theme()
        self.setStyleSheet(f"QDialog {{ background-color: {t.bg_app}; color: {t.text_main}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(f"🎙️ Oflayn Audio Podcast Yaratish")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {t.text_main};")
        layout.addWidget(title)

        desc = QLabel(
            "So'zlarni audio (.wav) faylga yozib olib, telefon yoki pleyeringizda "
            "yo'lda, sportda va internetsiz quloqchin orqali tinglang."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 13px; color: {t.text_muted};")
        layout.addWidget(desc)

        # 1. So'zlar to'plami
        src_box = QHBoxLayout()
        src_lbl = QLabel("To'plam:")
        src_lbl.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        self.combo_source = QComboBox()
        self.combo_source.addItems([
            f"🎧 Hozirgi tanlangan to'plam [{self.default_source_title}] ({len(self.current_playlist)} ta)",
            "📚 Barcha shaxsiy so'zlar (To'liq lug'at)",
            "🧠 Bugun takrorlash kerak (SM-2)",
            "⚠️ Zaif / xato qilingan so'zlar",
        ])
        self.combo_source.setStyleSheet(
            f"QComboBox {{ background-color: {t.bg_card}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 8px; padding: 6px 12px; font-size: 13px; }}"
        )
        src_box.addWidget(src_lbl)
        src_box.addWidget(self.combo_source, 1)
        layout.addLayout(src_box)

        # 2. Oraliq pauza
        interval_box = QVBoxLayout()
        interval_lbl_row = QHBoxLayout()
        interval_title = QLabel("So'zlar orasidagi pauza:")
        interval_title.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        self.interval_val_lbl = QLabel("4.0 soniya")
        self.interval_val_lbl.setStyleSheet(f"font-weight: 700; color: {t.primary}; font-size: 13px;")
        interval_lbl_row.addWidget(interval_title)
        interval_lbl_row.addStretch()
        interval_lbl_row.addWidget(self.interval_val_lbl)
        interval_box.addLayout(interval_lbl_row)

        self.slider_interval = QSlider(Qt.Orientation.Horizontal)
        self.slider_interval.setRange(10, 80)
        self.slider_interval.setValue(40)
        self.slider_interval.valueChanged.connect(
            lambda v: self.interval_val_lbl.setText(f"{v / 10.0:.1f} soniya")
        )
        interval_box.addWidget(self.slider_interval)
        layout.addLayout(interval_box)

        # 3. Qo'shimcha parametrlar
        self.chk_uzbek = QCheckBox("O'zbekcha tarjimasini ham talaffuz qilish")
        self.chk_uzbek.setChecked(False)
        self.chk_uzbek.setStyleSheet(f"color: {t.text_main}; font-size: 13px;")
        layout.addWidget(self.chk_uzbek)

        self.chk_example = QCheckBox("Namuna gaplarni ham aytish (mavjud bo'lsa)")
        self.chk_example.setChecked(False)
        self.chk_example.setStyleSheet(f"color: {t.text_main}; font-size: 13px;")
        layout.addWidget(self.chk_example)

        # 4. Saqlash manzili
        path_box = QVBoxLayout()
        path_lbl = QLabel("Faylni saqlash manzili (.wav):")
        path_lbl.setStyleSheet(f"font-weight: 600; color: {t.text_main}; font-size: 13px;")
        path_box.addWidget(path_lbl)

        path_input_box = QHBoxLayout()
        self.line_path = QLineEdit()
        default_dir = Path.home() / "Music"
        if not default_dir.exists():
            default_dir = Path.cwd()
        default_file = default_dir / f"vocab_podcast_{int(time.time())}.wav"
        self.line_path.setText(str(default_file))
        self.line_path.setStyleSheet(
            f"background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 7px 10px; font-size: 12px;"
        )

        btn_browse = QPushButton("📁 Tanlash...")
        btn_browse.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 8px; padding: 7px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {t.primary}; }}"
        )
        btn_browse.clicked.connect(self._browse_file)
        path_input_box.addWidget(self.line_path, 1)
        path_input_box.addWidget(btn_browse)
        path_box.addLayout(path_input_box)
        layout.addLayout(path_box)

        # 5. Progress Bar & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid {t.border}; border-radius: 6px; text-align: center; "
            f"color: {t.text_main}; background: {t.bg_card}; font-size: 11px; }} "
            f"QProgressBar::chunk {{ background-color: {t.primary}; border-radius: 5px; }}"
        )
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)

        # 6. Tugmalar qatori
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Bekor qilish")
        self.btn_cancel.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_muted}; "
            f"border: 1px solid {t.border}; border-radius: 8px; padding: 8px 18px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; }}"
        )
        self.btn_cancel.clicked.connect(self._on_cancel)

        self.btn_start = QPushButton("🎙️ Eksportni Boshlash")
        self.btn_start.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; font-weight: 700; "
            f"border-radius: 8px; padding: 8px 22px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        self.btn_start.clicked.connect(self._start_export)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_start)
        layout.addLayout(btn_layout)

    def _browse_file(self):
        cur = self.line_path.text().strip()
        start_dir = str(Path(cur).parent) if cur and Path(cur).parent.exists() else str(Path.home())
        chosen, _ = QFileDialog.getSaveFileName(
            self,
            "Audio Podcast faylini saqlash",
            start_dir,
            "Audio Fayl (*.wav)"
        )
        if chosen:
            if not chosen.lower().endswith(".wav"):
                chosen += ".wav"
            self.line_path.setText(chosen)

    def _start_export(self):
        filepath = self.line_path.text().strip()
        if not filepath:
            QMessageBox.warning(self, "Xatolik", "Iltimos, faylni saqlash manzilini ko'rsating!")
            return

        idx = self.combo_source.currentIndex()
        if idx == 0:
            words = list(self.current_playlist)
        elif idx == 1:
            words = db.get_all_words()
        elif idx == 2:
            words = db.get_due_words(limit=500)
        else:
            words = db.get_weak_words(limit=100)

        if not words:
            QMessageBox.warning(self, "Bo'sh ro'yxat", "Tanlangan toifada audio eksport qilish uchun so'zlar topilmadi!")
            return

        self.export_filepath = filepath
        interval_sec = self.slider_interval.value() / 10.0
        include_uzbek = self.chk_uzbek.isChecked()
        include_example = self.chk_example.isChecked()

        self.btn_start.setEnabled(False)
        self.combo_source.setEnabled(False)
        self.slider_interval.setEnabled(False)
        self.chk_uzbek.setEnabled(False)
        self.chk_example.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_lbl.setText(f"Eksport boshlanmoqda (jami {len(words)} ta so'z)...")
        self.status_lbl.setVisible(True)

        self.export_thread = AudioExportThread(
            words=words,
            filepath=filepath,
            interval_sec=interval_sec,
            include_uzbek=include_uzbek,
            include_example=include_example
        )
        self.export_thread.progress.connect(self._on_progress)
        self.export_thread.finished.connect(self._on_finished)
        self.export_thread.start()

    def _on_progress(self, current: int, total: int):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.status_lbl.setText(f"Ovoz yozilmoqda: {current} / {total} ta so'z ({pct}%)")

    def _on_finished(self, success: bool, message: str):
        self.btn_start.setEnabled(True)
        self.combo_source.setEnabled(True)
        self.slider_interval.setEnabled(True)
        self.chk_uzbek.setEnabled(True)
        self.chk_example.setEnabled(True)
        self.status_lbl.setVisible(False)
        self.progress_bar.setVisible(False)

        if success:
            msg = QMessageBox(self)
            msg.setWindowTitle("🎙️ Eksport muvaffaqiyatli!")
            msg.setText(f"Audio podcast fayli muvaffaqiyatli saqlandi!\n\nManzil: {self.export_filepath}")
            btn_open = msg.addButton("📁 Jildni ochish", QMessageBox.ButtonRole.ActionRole)
            btn_ok = msg.addButton("Tushunarli", QMessageBox.ButtonRole.AcceptRole)
            msg.exec()
            if msg.clickedButton() == btn_open:
                try:
                    folder = str(Path(self.export_filepath).parent)
                    subprocess.run(["explorer", folder], check=False)
                except Exception:
                    pass
            self.accept()
        else:
            QMessageBox.critical(self, "Eksport xatosi", message)

    def _on_cancel(self):
        if self.export_thread and self.export_thread.isRunning():
            self.status_lbl.setText("Eksport to'xtatilmoqda...")
            self.export_thread.cancel()
            self.export_thread.wait(2000)
        self.reject()

    def closeEvent(self, event):
        self._on_cancel()
        super().closeEvent(event)


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
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)

        # 1. Sarlavha qatori
        header_row = QHBoxLayout()
        self.title_lbl = QLabel("🎧 Hands-Free Audio Pleyer")
        self.title_lbl.setStyleSheet("color: white; font-size: 20px; font-weight: 700;")
        header_row.addWidget(self.title_lbl)
        header_row.addStretch()

        self.btn_export = QPushButton("🎙️ Podcast (.wav) Eksport")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setToolTip("Pleyerdagi yoki tanlangan to'plamdagi so'zlarni oflayn audio podcast (.wav) qilib saqlash")
        self.btn_export.clicked.connect(self._open_export_dialog)
        header_row.addWidget(self.btn_export)

        root.addLayout(header_row)

        # 2. Mavzular va To'plamlar tanlash paneli (Universal Source Selector)
        self.source_selector = GameSourceSelector("audio_player", self)
        self.source_selector.source_changed.connect(self._on_source_changed)
        root.addWidget(self.source_selector)

        self.sub_lbl = QLabel(
            "Ekranga qaramasdan quloqchin orqali so'zlarni eshitib yodlang. "
            "Dastur ekrandagi so'zni aniq talaffuz qiladi, belgilangan pauza beradi va keyingi so'zga o'tadi."
        )
        self.sub_lbl.setStyleSheet("color: #9CA3AF; font-size: 12.5px;")
        root.addWidget(self.sub_lbl)

        # 2. Markaziy Pleyer Kartasi (Ixcham va professional dizayn)
        self.player_card = QFrame()
        self.player_card.setObjectName("PlayerCard")
        card_layout = QVBoxLayout(self.player_card)
        card_layout.setContentsMargins(24, 16, 24, 16)
        card_layout.setSpacing(8)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.track_idx_lbl = QLabel("So'z: 0 / 0")
        self.track_idx_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px; font-weight: 600;")
        self.track_idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.track_idx_lbl)

        # Visualizer (Ixcham, markazlashtirilgan ovoz to'lqini)
        self.visualizer = VisualizerWidget()
        card_layout.addWidget(self.visualizer, 0, Qt.AlignmentFlag.AlignCenter)

        self.word_lbl = QLabel("So'zlar yuklanmoqda...")
        self.word_lbl.setStyleSheet("color: white; font-size: 32px; font-weight: 800; padding: 2px;")
        self.word_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.word_lbl)

        phonetic_row = QHBoxLayout()
        phonetic_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phonetic_row.setSpacing(8)

        self.phonetic_badge = QLabel("/transcription/")
        self.phonetic_badge.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; border-radius: 6px; "
            "padding: 4px 10px; font-size: 13px; font-family: 'Segoe UI', sans-serif;"
        )
        phonetic_row.addWidget(self.phonetic_badge)

        self.pos_badge = QLabel("[word]")
        self.pos_badge.setStyleSheet(
            "background-color: #064E3B; color: #6EE7B7; border-radius: 6px; "
            "padding: 4px 10px; font-size: 12px; font-weight: 700;"
        )
        phonetic_row.addWidget(self.pos_badge)
        card_layout.addLayout(phonetic_row)

        # Tarjima (Uzun bo'lsa aniq 2 qatorga chiroyli sig'adigan qilib sozlangan)
        self.trans_lbl = QLabel("Tarjima")
        self.trans_lbl.setStyleSheet("color: #34D399; font-size: 18px; font-weight: 700; line-height: 1.35; padding: 2px 8px;")
        self.trans_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.trans_lbl.setWordWrap(True)
        self.trans_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        card_layout.addWidget(self.trans_lbl)

        self.example_lbl = QLabel("")
        self.example_lbl.setStyleSheet("color: #9CA3AF; font-size: 14.5px; font-style: italic; line-height: 1.45; padding: 4px 16px;")
        self.example_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_lbl.setWordWrap(True)
        self.example_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
        self.btn_prev.clicked.connect(self._on_prev_clicked)
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
        self.btn_next.clicked.connect(self._on_next_clicked)
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

        self.cb_uzbek = QCheckBox("Tarjimani ham o'qish")
        self.cb_uzbek.setChecked(False)
        self.cb_uzbek.setStyleSheet("font-size: 13px;")
        self.cb_uzbek.setToolTip("Yoqilsa, inglizcha so'zdan so'ng uning o'zbekcha tarjimasi ham o'qiladi.")
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

    def _on_source_changed(self, category_id: str, source_id: str):
        self.load_words()

    def load_words(self):
        # 1. Agar pleyer ishlab turgan bo'lsa, uni xavfsiz to'xtatamiz
        if hasattr(self, "worker") and (self.worker.isRunning() or self.worker.is_running):
            self.worker.stop_playback()
            self.worker.wait(400)

        # 2. UI holatini to'xtatilgan (kutish) holatiga keltiramiz
        if hasattr(self, "visualizer"):
            self.visualizer.set_active(False)
        if hasattr(self, "btn_play"):
            self._on_state_changed(False)

        # 3. Tanlangan to'plam yoki bazadan so'zlarni yuklaymiz
        if hasattr(self, "source_selector"):
            cat, src = self.source_selector.get_current_source()
            words = gwp.get_words_for_source(cat, src)
        else:
            words = db.get_all_words()

        if not words:
            self.word_lbl.setText("To'plamda so'zlar topilmadi")
            self.trans_lbl.setText("Boshqa mavzu yoki to'plamni tanlang")
            self.phonetic_badge.setText("/—/")
            self.pos_badge.setText("[—]")
            self.example_lbl.setText("")
            self.track_idx_lbl.setText("0 / 0")
            self.worker.set_playlist([])
            return

        words = [dict(w) for w in words]
        self.worker.set_playlist(words)
        self.track_idx_lbl.setText(f"So'z: 1 / {len(words)}")
        first = words[0]
        self._display_word(first)

        # QAT'IY QOIDA: Hech qachon avtomatik ravishda audio o'qish boshlanmasin!
        # Foydalanuvchi faqat '▶️ Tinglashni Boshlash' tugmasini bosgandagina ijro boshlanadi.

    def _display_word(self, word: dict):
        eng = word.get("english", "")
        uz = word.get("uzbek", "")
        pho = word.get("phonetic", "") or ""
        pos = word.get("part_of_speech", "") or "word"
        ex = word.get("example", "") or ""

        self.word_lbl.setText(eng)
        self.trans_lbl.setText(format_uzbek_translation(uz))
        self.phonetic_badge.setText(pho if pho else "/—/")
        if ex:
            clean_ex = ex.strip()
            while clean_ex and clean_ex[0] in ('"', "'", '•', '*', '-', '–', '—', ' ', '\t', '“', '”', '`'):
                clean_ex = clean_ex[1:].strip()
            while clean_ex and clean_ex[-1] in ('"', "'", ' ', '\t', '“', '”', '`'):
                clean_ex = clean_ex[:-1].strip()
            self.example_lbl.setText(f"“{clean_ex}”" if clean_ex else "")
        else:
            self.example_lbl.setText("")

    def _open_export_dialog(self):
        """Pleyerdagi so'zlar ro'yxatini oflayn audio (.wav) qilib yuklab olish oynasini ochadi."""
        playlist = list(self.worker.playlist) if self.worker and self.worker.playlist else []
        source_title = self.source_selector.get_current_source_title() if hasattr(self, "source_selector") else "Lug'at"
        dlg = AudioExportDialog(playlist, self, default_source_title=source_title)
        dlg.exec()

    def _toggle_play(self):
        if not self.worker.playlist:
            return

        if not self.worker.isRunning() or not self.worker.is_running:
            self.worker.start()
        elif self.worker.is_paused:
            self.worker.resume_playback()
        else:
            self.worker.pause_playback()

    def _on_stop_clicked(self):
        if self.worker.isRunning() or self.worker.is_running:
            self.worker.stop_playback()
            self.worker.wait(300)
        self.visualizer.set_active(False)
        self._on_state_changed(False)

    def _on_next_clicked(self):
        """Keyingi so'z tugmasi bosilganda ekranni va audioni yangilash."""
        if not self.worker.playlist:
            return

        if self.worker.shuffle_mode and len(self.worker.playlist) > 1:
            next_idx = self.worker.current_index
            while next_idx == self.worker.current_index:
                next_idx = random.randint(0, len(self.worker.playlist) - 1)
        else:
            next_idx = (self.worker.current_index + 1) % len(self.worker.playlist)

        self.worker.current_index = next_idx
        word = self.worker.playlist[next_idx]
        self.track_idx_lbl.setText(f"So'z: {next_idx + 1} / {len(self.worker.playlist)}")
        self._display_word(word)

        if self.worker.is_running and not self.worker.is_paused:
            self.worker.skip_current()

    def _on_prev_clicked(self):
        """Oldingi so'z tugmasi bosilganda ekranni va audioni yangilash."""
        if not self.worker.playlist:
            return

        prev_idx = max(0, self.worker.current_index - 1)
        self.worker.current_index = prev_idx
        word = self.worker.playlist[prev_idx]
        self.track_idx_lbl.setText(f"So'z: {prev_idx + 1} / {len(self.worker.playlist)}")
        self._display_word(word)

        if self.worker.is_running and not self.worker.is_paused:
            self.worker.skip_current()

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
        self.title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 20px; font-weight: 700;")
        self.sub_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12.5px;")

        self.player_card.setStyleSheet(
            f"QFrame#PlayerCard {{ background-color: {t.bg_card}; border-radius: 14px; border: 1px solid {t.border}; }} "
            f"QLabel {{ border: none; background: transparent; }}"
        )
        self.visualizer.set_color(t.primary)

        self.track_idx_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 13px; font-weight: 600;")
        self.word_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 32px; font-weight: 800; padding: 2px;")
        self.trans_lbl.setStyleSheet(f"color: {t.primary_light if t.primary_light else '#34D399'}; font-size: 19px; font-weight: 700; line-height: 1.35; padding: 2px 8px;")
        self.example_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 14.5px; font-style: italic; line-height: 1.45; padding: 4px 16px;")

        if hasattr(self, "source_selector"):
            self.source_selector.apply_theme(t)
        self.btn_export.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.primary_light if t.primary_light else t.primary}; "
            f"border: 1px solid {t.border}; border-radius: 7px; padding: 5px 12px; font-size: 12.5px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; border-color: {t.primary}; }}"
        )

        btn_style = (
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 7px; padding: 7px 14px; font-size: 12.5px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; border-color: {t.primary}; }}"
            f"QPushButton:checked {{ background-color: {t.primary}; color: white; border-color: {t.primary}; }}"
        )
        self.btn_shuffle.setStyleSheet(btn_style)
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_next.setStyleSheet(btn_style)
        self.btn_loop.setStyleSheet(btn_style)
        self.btn_stop.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: #EF4444; border: 1px solid #7F1D1D; "
            f"border-radius: 7px; padding: 7px 14px; font-size: 12.5px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: #7F1D1D; color: white; }}"
        )

        if not self.worker.isRunning() or not self.worker.is_running or self.worker.is_paused:
            self.btn_play.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 7px; "
                f"font-size: 13px; font-weight: 700; padding: 8px 20px; }}"
                f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            )

    def hideEvent(self, event):
        """Boshqa bo'limga o'tilganda audioni darhol to'xtatish va interfeysni tiklash."""
        if hasattr(self, "worker") and (self.worker.isRunning() or self.worker.is_running):
            self.worker.stop_playback()
            self.worker.wait(400)
        if hasattr(self, "visualizer"):
            self.visualizer.set_active(False)
        if hasattr(self, "btn_play"):
            self._on_state_changed(False)
        super().hideEvent(event)

    def closeEvent(self, event):
        self.worker.stop_playback()
        self.worker.wait(800)
        super().closeEvent(event)
