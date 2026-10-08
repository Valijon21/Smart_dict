from core.db.cache import _invalidate_cache
from core.db.connection import get_conn, _safe_order_by
"""
Vocab Master — ma'lumotlar bazasi qatlami.
SQLite orqali so'zlar, progress va statistika saqlanadi.
Dublikatlarni oldini olish: english UNIQUE COLLATE NOCASE.
"""
import sys
import sqlite3
import datetime
import csv
import json
import re
import shutil
from pathlib import Path
from contextlib import contextmanager
try:
    from core import phonetics
except ImportError:
    import phonetics

try:
    from core.fsrs import FSRSv5, FSRSCard, Rating, CardState
except ImportError:
    try:
        from fsrs import FSRSv5, FSRSCard, Rating, CardState
    except ImportError:
        FSRSv5 = None
        FSRSCard = None
        Rating = None
        CardState = None

try:
    from utils.logger import get_logger, get_app_dir
    from utils import text_search_utils
except ImportError:
    from logger import get_logger, get_app_dir
    import text_search_utils

logger = get_logger("database")

# SQL ORDER BY whitelist — f-string injection xavfini bartaraf etadi.
# Yangi sort qiymati kerak bo'lsa, shu ro'yxatga qo'shing.
_ALLOWED_ORDER_BY: frozenset[str] = frozenset({
    "created_at DESC",
    "created_at ASC",
    "english ASC",
    "english DESC",
    "uzbek ASC",
    "uzbek DESC",
    "id ASC",
    "id DESC",
    "w.id ASC",
    "w.id DESC",
    "w.created_at DESC",
    "w.created_at ASC",
    "w.english ASC",
    "w.english DESC",
    "box_level ASC",
    "box_level DESC",
    "correct_count DESC",
    "wrong_count DESC",
    "status ASC",
    "status DESC",
})



def export_to_csv(filepath: str | Path) -> int:
    """Barcha so'zlarni CSV faylga eksport qiladi (Excel uchun UTF-8 BOM bilan, 1 ta tezkor JOIN so'rovi)."""
    rows = get_words_with_progress(order_by="w.id ASC")
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "English", "Uzbek", "Example", "Status", "BoxLevel", "Correct", "Wrong", "CreatedAt"])
        for r in rows:
            writer.writerow([
                r["id"], r["english"], r["uzbek"], r["example"] or "",
                r["status"], r["box_level"], r["correct_count"], r["wrong_count"], r["created_at"]
            ])
    return len(rows)


def export_to_json(filepath: str | Path) -> int:
    """Barcha so'zlarni JSON formatida eksport qiladi (1 ta tezkor JOIN so'rovi)."""
    rows = get_words_with_progress(order_by="w.id ASC")
    data = [
        {
            "id": r["id"],
            "english": r["english"],
            "uzbek": r["uzbek"],
            "example": r["example"] or "",
            "status": r["status"],
            "box_level": r["box_level"],
            "correct_count": r["correct_count"],
            "wrong_count": r["wrong_count"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(data)


def backup_database(destination_path: str | Path) -> bool:
    """SQLite ma'lumotlar bazasini xavfsiz zaxira nusxasini yaratadi."""
    try:
        Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
        with get_conn() as src_conn:
            dest_conn = sqlite3.connect(str(destination_path))
            src_conn.backup(dest_conn)
            dest_conn.close()
        logger.info(f"Baza zaxira nusxasi yaratildi: {destination_path}")
        return True
    except Exception as e:
        logger.error(f"Zaxira nusxa yaratishda xatolik: {e}", exc_info=True)
        return False


def restore_database(source_path: str | Path) -> bool:
    """SQLite ma'lumotlar bazasini zaxira faylidan xavfsiz tiklaydi."""
    try:
        source_p = Path(source_path)
        if not source_p.exists():
            return False
        src_conn = sqlite3.connect(str(source_p))
        with get_conn() as dest_conn:
            src_conn.backup(dest_conn)
        src_conn.close()
        logger.info(f"Baza zaxiradan muvaffaqiyatli tiklandi: {source_path}")
        return True
    except Exception as e:
        logger.error(f"Bazani tiklashda xatolik: {e}", exc_info=True)
        return False


BACKUP_DIR = Path.home() / "VocabMaster" / "backups"


def get_backup_dir() -> Path:
    """Zaxiralar papkasini qaytaradi va mavjud bo'lmasa yaratadi."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def backup_database(target_path: str = None) -> bool:
    """
    Ma'lumotlar bazasini xavfsiz SQLite backup API orqali zaxiralaydi.
    WAL rejimini tozalab, bazaning yaxlit nusxasini yaratadi.
    """
    try:
        if target_path is None:
            today_str = datetime.date.today().isoformat()
            target_path = get_backup_dir() / f"vocab_backup_{today_str}.db"
        else:
            target_path = Path(target_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)

        with get_conn() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dest_conn = sqlite3.connect(str(target_path))
            try:
                conn.backup(dest_conn)
            finally:
                dest_conn.close()

        logger.info(f"Ma'lumotlar bazasi zaxirasi saqlandi: {target_path}")
        return True
    except Exception as e:
        logger.error(f"Baza zaxirasini olishda xatolik: {e}", exc_info=True)
        return False


def restore_database(source_path: str) -> bool:
    """
    Zaxira nusxasidan bazani xavfsiz qayta tiklaydi.
    """
    try:
        src = Path(source_path)
        if not src.exists() or src.stat().st_size == 0:
            logger.error(f"Tiklash uchun fayl topilmadi yoki bo'sh: {source_path}")
            return False

        # Fayl butunligini tekshirish
        test_conn = sqlite3.connect(str(src))
        try:
            cur = test_conn.cursor()
            cur.execute("PRAGMA integrity_check")
            res = cur.fetchone()
            if not res or res[0] != "ok":
                logger.error(f"Zaxira fayli shikastlangan (integrity check failed): {res}")
                return False
        finally:
            test_conn.close()

        # Favqulodda xavfsizlik nusxasi
        emergency_bak = get_backup_dir() / "pre_restore_snapshot.db"
        try:
            if DB_PATH.exists():
                shutil.copy2(DB_PATH, emergency_bak)
        except Exception:
            pass

        # Eskirgan WAL/SHM fayllarini tozalash
        for ext in (".db-wal", ".db-shm"):
            f = DB_PATH.with_suffix(ext)
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

        # Faylni nusxalash
        shutil.copy2(src, DB_PATH)
        logger.info(f"Baza zaxiradan to'liq tiklandi: {src} -> {DB_PATH}")
        return True
    except Exception as e:
        logger.error(f"Bazani zaxiradan tiklashda xatolik: {e}", exc_info=True)
        return False


def auto_backup_daily(keep_days: int = 14) -> str:
    """
    Dastur ishga tushganda avtomatik kunlik zaxira yaratadi.
    Eskirgan zaxiralarni avtomatik tozalab, disk hajmini tejaydi.
    """
    try:
        b_dir = get_backup_dir()
        today_str = datetime.date.today().isoformat()
        today_file = b_dir / f"vocab_backup_{today_str}.db"

        # Zaxira olish
        backup_database(str(today_file))

        # 14 kundan ortiq zaxiralarni tozalash
        all_backups = sorted(b_dir.glob("vocab_backup_*.db"), key=lambda p: p.stat().st_mtime)
        if len(all_backups) > keep_days:
            for old_f in all_backups[:-keep_days]:
                try:
                    old_f.unlink()
                    logger.info(f"Eski zaxira fayli o'chirildi: {old_f.name}")
                except Exception:
                    pass

        return str(today_file)
    except Exception as e:
        logger.warning(f"Avtomatik kunlik zaxira olishda xatolik: {e}")
        return ""


def list_local_backups() -> list[dict]:
    """Mavjud mahalliy zaxiralar ro'yxatini qaytaradi."""
    result = []
    try:
        b_dir = get_backup_dir()
        for f in sorted(b_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
            size_kb = round(f.stat().st_size / 1024, 1)
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            result.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size_kb": size_kb,
                "modified": mtime,
            })
    except Exception as e:
        logger.error(f"Zaxiralar ro'yxatini olishda xatolik: {e}")
    return result

