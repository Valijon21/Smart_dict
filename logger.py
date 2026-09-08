"""
Vocab Master — Professional Logging & Debugging Module.
Har bir qadam, xatolik va hodisalarni 'logs/vocab_master.log' fayliga va konsolga yozadi.
Kutilmagan xatoliklar (uncaught exceptions) va Qt xabarlarini avtomatik ushlaydi.
"""
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_app_dir() -> Path:
    """Ilovaning asosiy ishchi papkasini (.exe yoki .py joylashgan papka) aniqlaydi."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _determine_log_dir() -> Path:
    """Loglar papkasini dastur yonida yoki fallback sifatida User profilida aniqlaydi."""
    try:
        log_dir = get_app_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        test_file = log_dir / ".perm_check"
        test_file.touch()
        test_file.unlink()
        return log_dir
    except (PermissionError, OSError):
        fallback = Path.home() / "VocabMaster" / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


LOG_DIR = _determine_log_dir()
LOG_FILE = LOG_DIR / "vocab_master.log"


def get_log_dir() -> Path:
    """Loglar saqlanadigan papka yo'li."""
    return LOG_DIR


def setup_logging(level=logging.INFO):
    """Log tizimini ishga tushirish (aylanuvchi fayl va konsol oqimi)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Agar handlerlar allaqachon qo'shilgan bo'lsa, qayta qo'shmaymiz
    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Windows cp1251 yoki boshqa non-utf8 terminallarda crash bo'lmasligi uchun
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass

    # 1. Aylanuvchi fayl handler (maksimal 5MB, 3 ta zaxira fayl)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Log faylini ochishda xatolik: {e}")

    # 2. Konsol handler (stdout)
    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    except Exception:
        pass

    # Kutilmagan barcha xatoliklarni ushlab logga yozish
    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical(
            "Kutilmagan kritik xatolik yuz berdi (Uncaught Exception):",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_uncaught_exception

    root_logger.info("=" * 60)
    root_logger.info("Vocab Master Pro — Logging tizimi muvaffaqiyatli ishga tushdi")
    root_logger.info(f"Log fayli: {LOG_FILE}")
    root_logger.info(f"Python: {sys.version.split()[0]} | Platform: {sys.platform}")
    root_logger.info("=" * 60)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Modullar uchun nomlangan logger qaytaradi."""
    return logging.getLogger(name)


def get_log_file_path() -> Path:
    """Log faylining to'liq yo'lini qaytaradi."""
    return LOG_FILE


def get_log_size_str() -> str:
    """Log faylining hajmini qulay ko'rinishda (KB/MB) qaytaradi."""
    if not LOG_FILE.exists():
        return "0 KB (fayl hali yaratilmagan)"
    size_bytes = LOG_FILE.stat().st_size
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def clear_logs() -> bool:
    """Log faylini xavfsiz tozalaydi."""
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.truncate(0)
        logger = get_logger("system")
        logger.info("Log fayli foydalanuvchi tomonidan tozalandi.")
        return True
    except Exception as e:
        print(f"Loglarni tozalashda xatolik: {e}")
        return False
