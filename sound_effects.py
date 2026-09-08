"""
Vocab Master Pro — Tovushli Effektlar (Sound Effects Engine).
Python standart kutubxonalari (wave, struct, math, winsound) yordamida
100% oflayn va tashqi fayllarsiz yuqori sifatli audio bildirishnomalarni ijro etadi.
"""
import io
import math
import struct
import threading
import wave
from logger import get_logger
import database as db

logger = get_logger("sound_effects")

_CORRECT_WAV: bytes = b""
_WRONG_WAV: bytes = b""
_MILESTONE_WAV: bytes = b""
_INITIALIZED: bool = False


def _generate_tone_wav(notes: list[tuple[float, float, float]]) -> bytes:
    """
    notes: list of (frequency_hz, duration_sec, volume_0_to_1)
    Yumshoq fade-in va fade-out bilan toza sinus to'lqinli WAV baytlarini yaratadi.
    """
    sample_rate = 44100
    all_samples = []

    for freq, duration, volume in notes:
        total_samples = int(sample_rate * duration)
        fade_len = int(sample_rate * 0.015)  # 15ms fade chertishni yo'qotish uchun
        for i in range(total_samples):
            # Envelop (fade in / fade out)
            env = 1.0
            if i < fade_len:
                env = i / fade_len
            elif i > total_samples - fade_len:
                env = (total_samples - i) / fade_len

            # Sinus to'lqin
            val = math.sin(2.0 * math.pi * freq * (i / sample_rate))
            sample_val = int(val * env * volume * 32767.0)
            sample_val = max(-32768, min(32767, sample_val))
            all_samples.append(sample_val)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        # Pack into signed short bytes
        raw_data = struct.pack(f"<{len(all_samples)}h", *all_samples)
        wf.writeframes(raw_data)

    return buf.getvalue()


def _ensure_sounds():
    global _CORRECT_WAV, _WRONG_WAV, _MILESTONE_WAV, _INITIALIZED
    if _INITIALIZED:
        return
    try:
        # G'alaba akkordi: C5 (523 Hz) -> G5 (784 Hz)
        _CORRECT_WAV = _generate_tone_wav([
            (523.25, 0.07, 0.35),
            (783.99, 0.16, 0.45)
        ])
        # Xato tovushi: Yumshoq past ton (240 Hz -> 190 Hz)
        _WRONG_WAV = _generate_tone_wav([
            (240.0, 0.09, 0.30),
            (190.0, 0.14, 0.25)
        ])
        # Katta g'alaba/yutuq fanfari: C5 -> E5 -> G5 -> C6
        _MILESTONE_WAV = _generate_tone_wav([
            (523.25, 0.08, 0.30),
            (659.25, 0.08, 0.35),
            (783.99, 0.10, 0.40),
            (1046.50, 0.28, 0.45)
        ])
        _INITIALIZED = True
    except Exception as e:
        logger.warning(f"Audio generatsiyasida xatolik: {e}")


def _play_wav_async(wav_bytes: bytes):
    try:
        import winsound
        # SND_MEMORY + SND_ASYNC (interfeysni qotirmasdan ijro etish)
        winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_ASYNC)
    except Exception as e:
        logger.debug(f"Ovoz chiqarishda xatolik (tizimda audio qurilma bo'lmasligi mumkin): {e}")


def play_correct():
    """To'g'ri javob berilganda mayin g'alaba tovushini chiqaradi."""
    if db.get_setting("sound_effects_enabled", "true") != "true":
        return
    _ensure_sounds()
    if _CORRECT_WAV:
        threading.Thread(target=_play_wav_async, args=(_CORRECT_WAV,), daemon=True).start()


def play_wrong():
    """Xato javob berilganda yumshoq ogohlantiruvchi tovush chiqaradi."""
    if db.get_setting("sound_effects_enabled", "true") != "true":
        return
    _ensure_sounds()
    if _WRONG_WAV:
        threading.Thread(target=_play_wav_async, args=(_WRONG_WAV,), daemon=True).start()


def play_milestone():
    """O'yin yakuni, katta rekord yoki yutuq ochilganda bayramona akkord."""
    if db.get_setting("sound_effects_enabled", "true") != "true":
        return
    _ensure_sounds()
    if _MILESTONE_WAV:
        threading.Thread(target=_play_wav_async, args=(_MILESTONE_WAV,), daemon=True).start()


play_victory = play_milestone
