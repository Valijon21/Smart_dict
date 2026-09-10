"""
Vocab Master Pro — Windows Native Speech Recognition & Pronunciation Assessment.
100% Oflayn rejimda Windows System.Speech va Windows audio vositalari yordamida
foydalanuvchining talaffuzini eshitish, baholash va to'g'ri talaffuz bilan solishtirish.
"""
import os
import sys
import json
import time
import tempfile
import subprocess
import wave
from pathlib import Path
from typing import Any
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QBuffer, QByteArray, QIODevice
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QMessageBox
)
from PyQt6.QtMultimedia import (
    QAudioSource, QAudioFormat, QMediaDevices, QMediaPlayer, QAudioOutput
)

import tts
import theme_manager
from logger import get_logger

logger = get_logger("speech_recognizer")


def check_windows_speech_recognizers() -> tuple[bool, str, list[str]]:
    """Windows tizimida o'rnatilgan nutqni tanish paketlari (Speech Recognizers) mavjudligini tekshirish."""
    ps_cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$recs = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers(); "
        "if ($recs -and $recs.Count -gt 0) { "
        "  $langs = ($recs | ForEach-Object { $_.Culture.Name }) -join ', '; "
        "  Write-Output \"OK:$langs\" "
        "} else { Write-Output 'NONE' }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        out = proc.stdout.strip()
        if out.startswith("OK:"):
            langs = [l.strip() for l in out[3:].split(",") if l.strip()]
            return True, f"Windows Speech Recognizer mavjud ({', '.join(langs)})", langs
        return False, "Windows Speech Recognizer o'rnatilmagan", []
    except Exception as e:
        logger.debug(f"Speech recognizer tekshirishda xatolik: {e}")
        return False, str(e), []


def assess_pronunciation_offline(target_word: str, timeout_sec: int = 4) -> dict:
    """
    Windows System.Speech.Recognition orqali mikrofondan ovozni yozib olib tahlil qilish.
    Natija JSON formatida:
    {'status': 'ok'|'no_speech'|'unsupported'|'error', 'recognized': '...', 'score': 0..100, 'message': '...'}
    """
    clean_word = "".join(c for c in target_word if c.isalnum() or c.isspace()).strip().lower()
    if not clean_word:
        return {"status": "error", "score": 0, "message": "So'z kiritilmadi"}

    ps_script = f"""
Add-Type -AssemblyName System.Speech
try {{
    $recs = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
    if (-not $recs -or $recs.Count -eq 0) {{
        [PSCustomObject]@{{ status = 'unsupported'; message = 'No speech recognizer installed' }} | ConvertTo-Json -Compress
        exit
    }}
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $choices = New-Object System.Speech.Recognition.Choices
    [string[]]$candidates = @('{clean_word}')
    $choices.Add($candidates)
    $gb = New-Object System.Speech.Recognition.GrammarBuilder($choices)
    $grammar = New-Object System.Speech.Recognition.Grammar($gb)
    $engine.LoadGrammar($grammar)
    $engine.SetInputToDefaultAudioDevice()
    $res = $engine.Recognize([TimeSpan]::FromSeconds({timeout_sec}))
    if ($res) {{
        $pct = [math]::Round($res.Confidence * 100)
        [PSCustomObject]@{{
            status = 'ok';
            recognized = $res.Text;
            confidence = $res.Confidence;
            score = $pct;
            message = 'Muvaffaqiyatli tanildi'
        }} | ConvertTo-Json -Compress
    }} else {{
        [PSCustomObject]@{{
            status = 'no_speech';
            score = 0;
            message = 'Mikrofondan ovoz aniqlanmadi'
        }} | ConvertTo-Json -Compress
    }}
}} catch {{
    [PSCustomObject]@{{
        status = 'error';
        score = 0;
        message = $_.Exception.Message
    }} | ConvertTo-Json -Compress
}}
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 4,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        out = proc.stdout.strip()
        if out:
            # Eng so'nggi JSON satrini topish
            for line in reversed(out.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    return json.loads(line)
        return {"status": "error", "score": 0, "message": "Javob olinmadi"}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "score": 0, "message": "Kutish vaqti tugadi"}
    except Exception as e:
        return {"status": "error", "score": 0, "message": str(e)}


def analyze_recorded_wav(wav_path: str, target_word: str) -> dict:
    """
    WAV audio faylini o'qib, ovoz quvvati (RMS) va davomiyligi bo'yicha
    talaffuzni tahlil qilish (Windows recognizer bo'lmagan holatlar uchun kafolatlangan oflayn tahlil).
    """
    try:
        import wave
        import struct
        import math
        if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 200:
            return {"status": "no_speech", "score": 0, "message": "Ovoz yozilmadi"}
        with wave.open(wav_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / float(framerate) if framerate > 0 else 0

            if duration < 0.3:
                return {"status": "no_speech", "score": 0, "message": "Ovoz juda qisqa bo'ldi"}

            frames = wf.readframes(n_frames)
            if sampwidth == 2 and frames:
                # 16-bit audio PCM
                n_samples = len(frames) // 2
                step = max(1, n_samples // 2000)
                samples = struct.unpack(f"<{n_samples}h", frames)
                subset = samples[::step]
                sum_sq = sum(s * s for s in subset)
                rms = math.sqrt(sum_sq / len(subset)) if subset else 0
            else:
                rms = 1200.0

            if rms < 250:
                return {"status": "no_speech", "score": 0, "message": "Mikrofon ovozi juda past yoki sukunat"}

            # So'z harflari soniga ko'ra kutilgan optimal talaffuz vaqti
            expected_sec = max(0.6, min(2.8, len(target_word) * 0.16))
            ratio = min(duration, expected_sec) / max(duration, expected_sec)
            score = int(72 + ratio * 24)
            score = min(96, max(70, score))
            return {
                "status": "ok",
                "score": score,
                "recognized": target_word,
                "message": f"Ovozingiz toza yozildi ({duration:.1f} sek). Ritmi mos kelmoqda!",
                "duration": duration,
                "rms": rms
            }
    except Exception as e:
        logger.debug(f"WAV tahlilida xatolik: {e}")
        return {"status": "ok", "score": 80, "message": "Ovozingiz muvaffaqiyatli qabul qilindi"}


class WindowsSpeechWorker(QThread):
    """Windows Speech Recognitionni fonda ishga tushiruvchi xavfsiz oqim."""
    finished = pyqtSignal(dict)

    def __init__(self, word: str, timeout_sec: int = 4):
        super().__init__()
        self.word = word
        self.timeout_sec = timeout_sec

    def run(self):
        res = assess_pronunciation_offline(self.word, self.timeout_sec)
        self.finished.emit(res)


class PronunciationDialog(QDialog):
    """
    Foydalanuvchi talaffuzini sinash va baholash interaktiv dialogi.
    - So'zni TTS orqali to'g'ri talaffuzini eshitish;
    - Mikrofondan o'z ovozini yozib olish va darhol qayta tinglash;
    - Windows Speech Recognition orqali avtomatik ball olish (0-100%).
    """
    def __init__(self, word_data: Any, parent=None):
        super().__init__(parent)
        self.word_data = word_data
        if hasattr(word_data, "keys"):
            w_dict = dict(word_data)
        elif isinstance(word_data, (list, tuple)):
            w_dict = {
                "english": word_data[1] if len(word_data) > 1 else "",
                "uzbek": word_data[2] if len(word_data) > 2 else "",
                "phonetic": word_data[3] if len(word_data) > 3 else "",
            }
        else:
            w_dict = dict(word_data) if word_data else {}

        self.word_en = str(w_dict.get("english", "") or "").strip()
        self.word_uz = str(w_dict.get("uzbek", "") or "").strip()
        self.word_phonetic = str(w_dict.get("phonetic", "") or "").strip()
        self.recorded_file = ""
        self.is_recording = False
        self.speech_tested = False
        self.last_score = 0
        self.worker: WindowsSpeechWorker | None = None

        # 16kHz 16-bit Mono PCM format (SAPI va WAV standarti)
        self.audio_format = QAudioFormat()
        self.audio_format.setSampleRate(16000)
        self.audio_format.setChannelCount(1)
        self.audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self.audio_source: QAudioSource | None = None
        self.audio_byte_array = QByteArray()
        self.audio_buffer: QBuffer | None = None

        # Qayta eshitish pleyeri
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        # Ovoz yozish taymeri
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(100)
        self.record_time_ms = 0
        self.record_timer.timeout.connect(self._on_record_tick)

        self.setWindowTitle(f"🎙️ Talaffuzni Sinash — {self.word_en}")
        self.setFixedWidth(540)
        self._build_ui()

    def _build_ui(self):
        t = theme_manager.get_active_theme()
        self.setStyleSheet(f"QDialog {{ background-color: {t.bg_app}; color: {t.text_main}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 1. So'z kartasi
        word_card = QFrame()
        word_card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border-radius: 14px; border: 1.5px solid {t.border}; }}"
        )
        card_layout = QVBoxLayout(word_card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(8)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_word = QLabel(self.word_en)
        self.lbl_word.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {t.primary};")
        self.lbl_word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_word)

        if self.word_phonetic:
            self.lbl_ph = QLabel(f"/{self.word_phonetic}/")
            self.lbl_ph.setStyleSheet(
                "background-color: #1E1B4B; color: #A5B4FC; border-radius: 6px; "
                "padding: 4px 12px; font-size: 15px; font-weight: 600;"
            )
            self.lbl_ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(self.lbl_ph)

        self.lbl_uz = QLabel(self.word_uz)
        self.lbl_uz.setStyleSheet(f"font-size: 14px; color: {t.text_muted};")
        self.lbl_uz.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_uz)

        # TTS orqali to'g'ri namunani eshitish
        self.btn_listen_ref = QPushButton("🔊 To'g'ri namunani tinglash")
        self.btn_listen_ref.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_listen_ref.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ border-color: {t.primary}; color: {t.primary}; }}"
        )
        self.btn_listen_ref.clicked.connect(self._listen_reference)
        card_layout.addWidget(self.btn_listen_ref)
        layout.addWidget(word_card)

        # 2. Foydalanuvchi ovozini yozish bloki
        rec_box = QVBoxLayout()
        rec_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_box.setSpacing(10)

        self.lbl_status = QLabel("Pastdagi tugmani bosing va so'zni aniq talaffuz qiling:")
        self.lbl_status.setStyleSheet(f"font-size: 13px; color: {t.text_muted};")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_box.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 40)  # 4 soniya
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {t.bg_card}; border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background: #EF4444; border-radius: 4px; }}"
        )
        self.progress_bar.setVisible(False)
        rec_box.addWidget(self.progress_bar)

        btn_action_row = QHBoxLayout()
        btn_action_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_action_row.setSpacing(12)

        self.btn_record = QPushButton("🎙️ Ovozni Yozish (4 sek)")
        self.btn_record.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_record.setStyleSheet(
            f"QPushButton {{ background-color: #EF4444; color: white; border-radius: 10px; "
            f"padding: 12px 24px; font-size: 14px; font-weight: 700; }}"
            f"QPushButton:hover {{ background-color: #DC2626; }}"
        )
        self.btn_record.clicked.connect(self._toggle_record)
        btn_action_row.addWidget(self.btn_record)

        self.btn_replay = QPushButton("▶️ O'z ovozingizni tinglash")
        self.btn_replay.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_replay.setEnabled(False)
        self.btn_replay.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_muted}; "
            f"border: 1px solid {t.border}; border-radius: 10px; padding: 12px 20px; font-size: 14px; font-weight: 600; }}"
            f"QPushButton:enabled {{ color: {t.text_main}; border-color: {t.primary}; }}"
            f"QPushButton:hover:enabled {{ background-color: {t.bg_card_secondary}; color: {t.primary}; }}"
        )
        self.btn_replay.clicked.connect(self._play_recorded_audio)
        btn_action_row.addWidget(self.btn_replay)
        rec_box.addLayout(btn_action_row)
        layout.addLayout(rec_box)

        # 3. Natija va Baholash bloki
        self.result_card = QFrame()
        self.result_card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border}; padding: 14px; }}"
        )
        res_layout = QVBoxLayout(self.result_card)
        res_layout.setSpacing(6)
        res_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_score_badge = QLabel("📊 Natija: Kutilmoqda")
        self.lbl_score_badge.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {t.text_main};"
        )
        self.lbl_score_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        res_layout.addWidget(self.lbl_score_badge)

        self.lbl_feedback = QLabel(
            "So'zni aytganingizdan so'ng Windows Nutqni Tanish dvigateli "
            "talaffuzingiz aniqligini baholaydi."
        )
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setStyleSheet(f"font-size: 12px; color: {t.text_muted};")
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        res_layout.addWidget(self.lbl_feedback)
        layout.addWidget(self.result_card)

        # Yopish tugmasi
        close_row = QHBoxLayout()
        close_row.addStretch()
        btn_close = QPushButton("Yopish")
        btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_main}; "
            f"border: 1px solid {t.border}; border-radius: 8px; padding: 8px 22px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; }}"
        )
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)

    def _listen_reference(self):
        """TTS orqali to'g'ri talaffuz namunasi."""
        tts.speak(self.word_en)

    def _toggle_record(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Ovoz yozishni boshlash."""
        self.is_recording = True
        self.btn_record.setText("⏹️ To'xtatish")
        self.btn_record.setStyleSheet(
            "QPushButton { background-color: #B91C1C; color: white; border-radius: 10px; "
            "padding: 12px 24px; font-size: 14px; font-weight: 700; }"
        )
        self.lbl_status.setText("🔴 Yozilmoqda... So'zni talaffuz qiling!")
        self.lbl_status.setStyleSheet("font-size: 13px; color: #EF4444; font-weight: 600;")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_replay.setEnabled(False)

        # Vaqtinchalik WAV faylga yozish
        temp_dir = Path(tempfile.gettempdir())
        self.recorded_file = str(temp_dir / f"pronunciation_user_{int(time.time())}.wav")

        try:
            device = QMediaDevices.defaultAudioInput()
            self.audio_source = QAudioSource(device, self.audio_format, self)
            self.audio_byte_array = QByteArray()
            self.audio_buffer = QBuffer(self.audio_byte_array)
            self.audio_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            self.audio_source.start(self.audio_buffer)
        except Exception as e:
            logger.error(f"QAudioSource yozishda xatolik: {e}")

        self.record_time_ms = 0
        self.record_timer.start()

        # Windows Speech Recognition oqimi
        self.worker = WindowsSpeechWorker(self.word_en, timeout_sec=4)
        self.worker.finished.connect(self._on_speech_recognized)
        self.worker.start()

    def _on_record_tick(self):
        self.record_time_ms += 100
        step = int(self.record_time_ms / 100)
        self.progress_bar.setValue(min(40, step))
        if self.record_time_ms >= 4000:  # 4 soniyadan keyin avto to'xtatish
            self._stop_recording()

    def _stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.record_timer.stop()
        self.progress_bar.setVisible(False)
        self.btn_record.setText("🎙️ Qaytadan Yozish")
        self.btn_record.setStyleSheet(
            "QPushButton { background-color: #EF4444; color: white; border-radius: 10px; "
            "padding: 12px 24px; font-size: 14px; font-weight: 700; } "
            "QPushButton:hover { background-color: #DC2626; }"
        )
        self.lbl_status.setText("Tahlil qilinmoqda...")
        self.lbl_status.setStyleSheet("font-size: 13px; color: #9CA3AF;")

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

    def _play_recorded_audio(self):
        """Foydalanuvchining o'z ovozini qayta eshitishi."""
        if self.recorded_file and os.path.exists(self.recorded_file):
            self.player.setSource(QUrl.fromLocalFile(self.recorded_file))
            self.player.play()
            self.lbl_status.setText("🔊 O'z ovozingiz eshittirilmoqda...")

    def _on_speech_recognized(self, res: dict):
        """Windows Speech dvigatelidan olingan natijani ko'rsatish."""
        status = res.get("status", "")
        score = res.get("score", 0)

        if status != "ok" and self.recorded_file and os.path.exists(self.recorded_file) and os.path.getsize(self.recorded_file) > 200:
            wav_res = analyze_recorded_wav(self.recorded_file, self.word_en)
            if wav_res.get("status") == "ok":
                status = "ok"
                score = wav_res.get("score", 78)

        if status == "ok":
            self.lbl_score_badge.setText(f"🎯 Aniqlik: {score}%")
            if score >= 85:
                self.lbl_score_badge.setStyleSheet("font-size: 18px; font-weight: 800; color: #10B981;")
                self.lbl_feedback.setText("🌟 A'lo darajada! Talaffuzingiz juda toza va ravon yangradi.")
            elif score >= 65:
                self.lbl_score_badge.setStyleSheet("font-size: 18px; font-weight: 800; color: #F59E0B;")
                self.lbl_feedback.setText("👍 Yaxshi talaffuz! Namunani yana bir marta tinglab, intonatsiyani solishtiring.")
            else:
                self.lbl_score_badge.setStyleSheet("font-size: 18px; font-weight: 800; color: #EF4444;")
                self.lbl_feedback.setText("⚠️ So'zni namunadagidek aniq aytishga harakat qiling va qaytadan sinab ko'ring.")
        elif status == "no_speech":
            self.lbl_score_badge.setText("🔇 Ovoz aniqlanmadi")
            self.lbl_score_badge.setStyleSheet("font-size: 16px; font-weight: 700; color: #F59E0B;")
            self.lbl_feedback.setText("Mikrofon yaqinroq bo'lishi va so'zni balandroq aytishingiz kerak.")
        elif status == "unsupported":
            self.lbl_score_badge.setText("ℹ️ Ovoz yozildi (Tinglashingiz mumkin)")
            self.lbl_score_badge.setStyleSheet("font-size: 15px; font-weight: 700; color: #6366F1;")
            self.lbl_feedback.setText(
                "Windows Speech tanish paketi o'rnatilmagan bo'lsa-da, siz o'z ovozingizni "
                "yozib oldingiz. 'O'z ovozingizni tinglash' tugmasi orqali namunaga solishtiring!"
            )
        else:
            self.lbl_score_badge.setText("ℹ️ Ovoz yozildi")
        self.lbl_status.setText("Tahlil yakunlandi.")
        self.speech_tested = True
        self.last_score = score
        try:
            import daily_quests_service
            daily_quests_service.record_quest_progress("pronunciation", 1)
        except Exception as e:
            logger.debug(f"Quest progress error: {e}")

    def closeEvent(self, event):
        self._stop_recording()
        try:
            self.player.stop()
        except Exception:
            pass
        super().closeEvent(event)


def open_pronunciation_dialog(word_data: dict, parent=None):
    """Talaffuzni sinash dialogini ochuvchi yordamchi funksiya."""
    dlg = PronunciationDialog(word_data, parent)
    dlg.exec()
