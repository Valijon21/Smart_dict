"""
Vocab Master — Professional Oflayn Audio Talaffuz (TTS) moduli.
Ko'p qatlamli arxitektura:
  1. Asosiy: Windows SAPI5 (win32com.client) — 100% oflayn, asinxron (non-blocking), yashin tezligida.
  2. Zaxira 1: pyttsx3 drayveri (agar win32com mavjud bo'lmasa).
  3. Zaxira 2: Windows PowerShell System.Speech (avtonom zaxira).
Barcha chaqiriqlar va xatoliklar 'logger' orqali log faylga yoziladi.
"""
import re
import sys
import subprocess
import threading
import queue
from logger import get_logger

logger = get_logger("tts")

# SAPI Flaglari
SVSFlagsAsync = 1
SVSFPurgeBeforeSpeak = 2


def clean_english_for_tts(text: str) -> str:
    """
    TTS uchun inglizcha matn yoki so'zni tozalash:
    - HTML teglarini tozalaydi: "<p>Hello</p>" -> "Hello"
    - Lug'atdagi grammatik izohlarni olib tashlaydi: "abandon (verb)" -> "abandon", "data [noun]" -> "data"
    - Agar bu bitta qisqa lug'at so'zi bo'lib (<= 3 so'z), unda sinonimlar '/' yoki ',' bilan ajratilgan bo'lsa,
      birinchi sinonimni oladi: "quick / fast" -> "quick", "autumn, fall" -> "autumn"
    - Agar bu gap, paragraf yoki butun hikoya bo'lsa (yoki yangi qator, nuqta, 4 tadan ko'p so'z bo'lsa),
      matnning yaxlitligini, barcha vergullar, nuqtalar va jumlalarni 100% to'liq saqlab qoladi!
    """
    if not text:
        return ""

    raw = str(text).strip()

    # 1. HTML teglarni tozalash (agar matn ichida bo'lsa)
    cleaned = re.sub(r"<[^>]+>", " ", raw)

    # 2. Qavslar ichidagi grammatik qisqartmalarni tozalash: (verb), [noun], (adj) va hk.
    cleaned = re.sub(r"\((?:verb|noun|adj|adv|v\.|n\.|prep|pron|phr)[^)]*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[(?:verb|noun|adj|adv|v\.|n\.|prep|pron|phr)[^\]]*\]", "", cleaned, flags=re.IGNORECASE)

    # Matn hikoya, paragraf yoki to'liq gapmi?
    has_newlines = "\n" in cleaned
    has_sentence_end = bool(re.search(r"[.!?]", cleaned))
    word_count = len(cleaned.split())
    is_continuous_text = has_newlines or has_sentence_end or word_count > 4

    if not is_continuous_text:
        # Faqat qisqa lug'at so'zi bo'lsa (masalan: "autumn / fall" yoki "couch, sofa")
        if "/" in cleaned:
            parts = cleaned.split("/")
            if len(parts) == 2 and len(parts[0].split()) <= 2:
                cleaned = parts[0]
        if "," in cleaned:
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[0].split()) <= 2 and len(parts[1].split()) <= 2:
                cleaned = parts[0]
        cleaned = re.sub(r"\(.*?\)", "", cleaned)
        cleaned = re.sub(r"\[.*?\]", "", cleaned)
        cleaned = re.sub(r"\{.*?\}", "", cleaned)

    # Ortiqcha bo'shliqlarni tartibga solish, lekin satrlarni saqlash
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.split("\n")]
    cleaned = "\n".join([line for line in lines if line])

    return cleaned if cleaned else raw


class TTSEngine:
    """Oflayn TTS dvigateli (Windows SAPI5 + pyttsx3 + PowerShell fallback)."""

    def __init__(self):
        self._sapi_speaker = None
        self._pyttsx3_engine = None
        self._pyttsx3_queue = None
        self._active_voice_name = "Noma'lum"
        self._engine_type = "none"
        self._current_ui_rate = 155
        self._is_paused = False
        self._lock = threading.Lock()

        self._init_engine()

    def _init_engine(self):
        """Asosiy dvigatelni tanlash va sozlash."""
        # 1-urinish: Windows SAPI5
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            voices = speaker.GetVoices()

            selected_voice = None
            for i in range(voices.Count):
                v = voices.Item(i)
                desc = v.GetDescription()
                # Inglizcha ovozni qidirish
                if any(k in desc.lower() for k in ("english", "zira", "david", "en-us", "en-gb")):
                    selected_voice = v
                    self._active_voice_name = desc
                    break

            if selected_voice:
                speaker.Voice = selected_voice
            elif voices.Count > 0:
                self._active_voice_name = voices.Item(0).GetDescription()

            self._sapi_speaker = speaker
            self._engine_type = "SAPI5"
            self.set_rate(self._current_ui_rate)
            logger.info(f"Oflayn TTS dvigateli muvaffaqiyatli ishga tushdi: SAPI5 (Ovoz: '{self._active_voice_name}')")
            return
        except Exception as e:
            logger.warning(f"Windows SAPI5 ishga tushirishda xatolik: {e}. Zaxira pyttsx3 sinab ko'rilmoqda...")

        # 2-urinish: pyttsx3
        try:
            import pyttsx3
            self._pyttsx3_engine = pyttsx3.init()
            self._pyttsx3_engine.setProperty("rate", 155)
            self._pyttsx3_engine.setProperty("volume", 1.0)
            voices = self._pyttsx3_engine.getProperty("voices")
            if voices:
                for v in voices:
                    if "en" in v.id.lower() or "english" in v.name.lower():
                        self._pyttsx3_engine.setProperty("voice", v.id)
                        self._active_voice_name = v.name
                        break
                else:
                    self._active_voice_name = voices[0].name

            self._pyttsx3_queue = queue.Queue()
            t = threading.Thread(target=self._pyttsx3_worker, daemon=True)
            t.start()
            self._engine_type = "pyttsx3"
            logger.info(f"Oflayn TTS pyttsx3 orqali ishga tushdi (Ovoz: '{self._active_voice_name}')")
            return
        except Exception as e:
            logger.warning(f"pyttsx3 ishga tushirishda xatolik: {e}. PowerShell zaxirasi ishlatiladi.")

        # 3-urinish: PowerShell System.Speech
        self._engine_type = "PowerShell"
        self._active_voice_name = "Windows System.Speech"
        logger.info("Oflayn TTS PowerShell System.Speech orqali ishlatiladi.")

    def _pyttsx3_worker(self):
        """pyttsx3 alohida oqimida navbatdagi so'zlarni aytish."""
        while True:
            text = self._pyttsx3_queue.get()
            if text is None:
                break
            try:
                self._pyttsx3_engine.say(text)
                self._pyttsx3_engine.runAndWait()
            except Exception as e:
                logger.error(f"pyttsx3 talaffuz qilishda xatolik: {e}")
            self._pyttsx3_queue.task_done()

    def speak(self, text: str):
        """So'zni oflayn talaffuz qilish (asinxron, GUI qotmaydi)."""
        if not text or not str(text).strip():
            return

        raw_text = str(text).strip()
        clean_text = clean_english_for_tts(raw_text)
        if not clean_text:
            clean_text = raw_text

        preview = (clean_text[:75] + "...") if len(clean_text) > 75 else clean_text
        logger.info(f"[AUDIO] Talaffuz so'rovi ({len(clean_text)} belgi): '{preview}' (dvigatel: {self._engine_type})")

        # Agar avval pauzada bo'lsa, tozalaymiz
        if self._is_paused and self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                self._sapi_speaker.Resume()
            except Exception:
                pass
        self._is_paused = False

        # 1. SAPI5 (Eng tez va barqaror)
        if self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                # Flag 1 = Async, Flag 2 = PurgeBeforeSpeak (oldingi ovozni to'xtatib yangisini darhol gapirish)
                self._sapi_speaker.Speak(clean_text, SVSFlagsAsync | SVSFPurgeBeforeSpeak)
                return
            except Exception as e:
                logger.error(f"SAPI5 ovoz chiqarishda xatolik: {e}. Qayta tiklanmoqda...")
                # Qayta tiklashga urinish
                try:
                    self._init_engine()
                    if self._sapi_speaker:
                        self._sapi_speaker.Speak(clean_text, SVSFlagsAsync | SVSFPurgeBeforeSpeak)
                        return
                except Exception:
                    pass

        # 2. pyttsx3
        if self._engine_type == "pyttsx3" and self._pyttsx3_queue:
            try:
                # Navbatni tozalash (faqat oxirgi bosilgan so'zni aytish uchun)
                while not self._pyttsx3_queue.empty():
                    try:
                        self._pyttsx3_queue.get_nowait()
                        self._pyttsx3_queue.task_done()
                    except queue.Empty:
                        break
                self._pyttsx3_queue.put(clean_text)
                return
            except Exception as e:
                logger.error(f"pyttsx3 navbatga qo'yishda xatolik: {e}")

        # 3. PowerShell Fallback (Har qanday Windows tizimida ishlaydi)
        try:
            safe_text = clean_text.replace('"', '').replace("'", "").replace("\n", " ")
            cmd = [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.SpeakAsync('{safe_text}')"
            ]
            # Qora konsol oynasi miltillab ketmasligi uchun CREATE_NO_WINDOW
            create_flags = 0
            if sys.platform == "win32":
                create_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=create_flags)
            logger.info(f"PowerShell orqali talaffuz qilindi: '{safe_text}'")
        except Exception as e:
            logger.critical(f"Barcha TTS vositalari xatolik berdi: {e}")

    def pause(self) -> bool:
        """Talaffuzni vaqtincha to'xtatish (Pause)."""
        if self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                self._sapi_speaker.Pause()
                self._is_paused = True
                logger.info("TTS talaffuzi pauza qilindi.")
                return True
            except Exception as e:
                logger.error(f"TTS pause xatolik: {e}")
        return False

    def resume(self) -> bool:
        """Pauza qilingan joyidan xatosiz davom ettirish (Resume)."""
        if self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                self._sapi_speaker.Resume()
                self._is_paused = False
                logger.info("TTS talaffuzi qolgan joyidan davom ettirildi.")
                return True
            except Exception as e:
                logger.error(f"TTS resume xatolik: {e}")
        return False

    def is_paused(self) -> bool:
        """Hozirgi vaqtda audio pauzada turganini aniqlash."""
        return self._is_paused

    def is_speaking(self) -> bool:
        """Hozirgi vaqtda audio faol ijro etilayotganini tekshirish."""
        if self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                # 2 = SRSEIsSpeaking
                return self._sapi_speaker.Status.RunningState == 2
            except Exception:
                pass
        return False

    def stop(self):
        """Ovozni darhol to'xtatish."""
        if self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                if self._is_paused:
                    try:
                        self._sapi_speaker.Resume()
                    except Exception:
                        pass
                self._sapi_speaker.Speak("", SVSFPurgeBeforeSpeak)
                self._is_paused = False
                logger.info("TTS talaffuzi to'liq to'xtatildi.")
            except Exception as e:
                logger.debug(f"SAPI5 stop xatolik: {e}")
        elif self._engine_type == "pyttsx3" and self._pyttsx3_queue:
            try:
                while not self._pyttsx3_queue.empty():
                    self._pyttsx3_queue.get_nowait()
                    self._pyttsx3_queue.task_done()
                if self._pyttsx3_engine:
                    self._pyttsx3_engine.stop()
                self._is_paused = False
            except Exception as e:
                logger.debug(f"pyttsx3 stop xatolik: {e}")

    def set_rate(self, rate: int):
        """Tezlikni sozlash (UI: 110 dan 210 gacha, odatiy: 155)."""
        self._current_ui_rate = rate
        if self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                # SAPI rate: -10 dan +10 gacha (0 — standart)
                sapi_rate = int((rate - 155) / 10)
                sapi_rate = max(-10, min(10, sapi_rate))
                self._sapi_speaker.Rate = sapi_rate
            except Exception as e:
                logger.warning(f"SAPI tezligini o'zgartirishda xatolik: {e}")
        elif self._engine_type == "pyttsx3" and self._pyttsx3_engine:
            try:
                self._pyttsx3_engine.setProperty("rate", rate)
            except Exception:
                pass

    def get_diagnostics(self) -> dict:
        """Tizim diagnostikasi uchun TTS holati ma'lumotlari."""
        voices_list = []
        if self._engine_type == "SAPI5" and self._sapi_speaker:
            try:
                voices = self._sapi_speaker.GetVoices()
                for i in range(voices.Count):
                    voices_list.append(voices.Item(i).GetDescription())
            except Exception:
                pass

        return {
            "engine": self._engine_type,
            "active_voice": self._active_voice_name,
            "rate": self._current_ui_rate,
            "available_voices": voices_list,
            "status": "OK" if self._engine_type != "none" else "ERROR"
        }


# Global yagona instansiya
_engine_instance = None
_instance_lock = threading.Lock()


def _get_engine() -> TTSEngine:
    global _engine_instance
    with _instance_lock:
        if _engine_instance is None:
            _engine_instance = TTSEngine()
        return _engine_instance


def speak(text: str):
    """Inglizcha so'zni oflayn talaffuz qilish."""
    engine = _get_engine()
    engine.speak(text)


def speak_async(text: str):
    """Asinxron oflayn talaffuz qilish (speak bilan bir xil)."""
    speak(text)


def stop():
    """Hozirgi talaffuzni darhol to'xtatish."""
    engine = _get_engine()
    engine.stop()


def pause() -> bool:
    """Talaffuzni vaqtincha to'xtatish (Pause)."""
    return _get_engine().pause()


def resume() -> bool:
    """Pauza qilingan joyidan xatosiz davom ettirish (Resume)."""
    return _get_engine().resume()


def is_paused() -> bool:
    """Audio pauzada turganini tekshirish."""
    return _get_engine().is_paused()


def is_speaking() -> bool:
    """Audio faol ijro etilayotganini tekshirish."""
    return _get_engine().is_speaking()


def set_rate(rate: int):
    """Talaffuz tezligini sozlash."""
    engine = _get_engine()
    engine.set_rate(rate)


def get_diagnostics() -> dict:
    """TTS diagnostika ma'lumotlarini olish."""
    engine = _get_engine()
    return engine.get_diagnostics()
