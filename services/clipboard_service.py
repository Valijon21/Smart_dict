"""
Vocab Master Pro — Global Clipboard Auto-Lookup Monitor & Toast Popup.
Foydalanuvchi Windows tizimidagi har qanday dasturda (Chrome, Word, Telegram, PDF Reader)
inglizcha so'z ustida 'Ctrl+C' bosganda, ushbu modul avtomatik ravishda 64k Oxford
lug'atidan so'z ma'nosini topadi va ekranning pastki o'ng burchagida ixcham, zamonaviy,
foydalanuvchi ishini to'xtatmaydigan (non-intrusive floating toast) popup taqdim etadi.
"""
import re
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QObject, pyqtSignal

import core.database as db
import services.global_dict_service as global_dict_service
import core.phonetics as phonetics
from ui.dialogs.clipboard_popup_dialog import ClipboardPopupDialog
from utils.logger import get_logger

logger = get_logger("clipboard_monitor")


class ClipboardMonitor(QObject):
    """
    Windows almashish buferi (Clipboard) o'zgarishlarini kuzatuvchi servis.
    Foydalanuvchi biror so'zni nusxalaganda avtomatik qidiradi va bildirishnoma chiqaradi.
    """
    def __init__(self, parent=None, on_words_changed=None):
        super().__init__(parent)
        self.on_words_changed = on_words_changed
        self.last_text = ""
        self.last_lookup_time = 0.0
        self.active_dialog: ClipboardPopupDialog | None = None
        self.enabled = db.get_setting("clipboard_lookup_enabled", "true") == "true"

        # Debounce taymeri (ketma-ket nusxalanganda so'nggisini olish uchun)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(300)
        self.debounce_timer.timeout.connect(self._process_clipboard)

        # QApplication clipboard signaliga ulanish
        app = QApplication.instance()
        if app:
            cb = app.clipboard()
            cb.dataChanged.connect(self._on_clipboard_changed)
            logger.info("Global Clipboard Monitor muvaffaqiyatli ishga tushirildi.")

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        db.set_setting("clipboard_lookup_enabled", "true" if enabled else "false")
        logger.info(f"Clipboard avto-qidiruv holati: {enabled}")

    def reload_settings(self):
        self.enabled = db.get_setting("clipboard_lookup_enabled", "true") == "true"

    def _on_clipboard_changed(self):
        if not self.enabled:
            return
        # Debounce taymerini qayta yoqish
        self.debounce_timer.start()

    def _process_clipboard(self):
        if not self.enabled:
            return

        app = QApplication.instance()
        if not app:
            return

        try:
            raw_text = app.clipboard().text()
        except Exception:
            return

        if not raw_text:
            return

        text = raw_text.strip()

        # Filtrlar:
        # 1. 2 tadan kam yoki 40 tadan ko'p belgili bo'lsa qaramaymiz
        if len(text) < 2 or len(text) > 40:
            return

        # 2. 3 tadan ko'p so'z bo'lsa (butun gap yoki abzas) e'tiborsiz qoldiramiz
        words_count = len(text.split())
        if words_count > 3:
            return

        # 3. Maxfiylik va xavfsizlik (Privacy & Security Guard):
        # URL, email, kod sintaksisi, parollar, tokenlar va bank kartalarini rad etamiz
        if any(x in text for x in ("http://", "https://", "www.", "@", "{", "}", ";", "=", "def ", "class ", "Bearer ")):
            return

        # Raqamlardan yoki telefon/kodlardan iborat bo'lsa rad etamiz
        if re.match(r"^[\d\s\.,:\-]+$", text) or re.match(r"^\+?\d{7,15}$", text):
            return

        # Parol yoki maxfiy token belgilari (aralash maxsus belgilar)
        if any(c in text for c in ("$", "%", "^", "*", "~", "\\", "|", "`", "<", ">")):
            return

        # API tokenlar va maxfiy kalitlar (sk-..., ghp_..., eyJ...)
        if re.search(r"\b(sk-[a-zA-Z0-9]+|ghp_[a-zA-Z0-9]+|ey[a-zA-Z0-9_\-\.]+)\b", text):
            return

        # Karta raqamlari (13-19 ta ketma-ket yoki bo'shliqli raqamlar)
        if re.search(r"\b(?:\d[ -]*?){13,19}\b", text):
            return

        # 4. Oldingi qidirilgan so'z bilan bir xil bo'lsa va 8 soniya o'tmagan bo'lsa, takrorlamaymiz
        now = time.time()
        if text.lower() == self.last_text.lower() and (now - self.last_lookup_time) < 8.0:
            return

        self.last_text = text
        self.last_lookup_time = now

        # Qidiruv: 64k Oxford bazasidan
        details = global_dict_service.get_word_full_details(english=text)
        if details:
            self._show_popup({
                "english": details["english"],
                "uzbek": ", ".join(details.get("uzbek_translations", [])) or details.get("uzbek_str", ""),
                "phonetic": details.get("phonetic", ""),
                "example": details.get("examples", [""])[0] if details.get("examples") else "",
                "star": details.get("star", "0"),
            })
            return

        # Agar to'g'ridan-to'g'ri topilmasa, prefix/universal qidiruv
        results = global_dict_service.search_global_words(text, limit=1)
        if results:
            first = results[0]
            # Agar kiritilgan so'z bilan topilgan so'z mos bo'lsa
            if first["english"].lower() == text.lower() or text.lower() in first["uzbek"].lower():
                ph_info = phonetics.get_word_info(first["english"])
                self._show_popup({
                    "english": first["english"],
                    "uzbek": first["uzbek"],
                    "phonetic": ph_info.get("phonetic", ""),
                    "example": first.get("example", ""),
                    "star": first.get("star", "0"),
                })

    def _show_popup(self, word_data: dict):
        # Eski popup ochiq bo'lsa, uni yopamiz
        if self.active_dialog:
            try:
                self.active_dialog.close()
            except Exception:
                pass
            self.active_dialog = None

        self.active_dialog = ClipboardPopupDialog(word_data)
        if self.on_words_changed:
            self.active_dialog.word_added.connect(self.on_words_changed)
        self.active_dialog.show()
