"""
Vocab Master — Standalone Windows Executable Build Script.
Python o'rnatilmagan kompyuterlarda ham ishlaydigan yakka .exe fayl yaratadi.
NumPy C-extensions va Matplotlib kutubxonalari to'liq qamrab olinadi.
"""
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def build():
    print("===========================================")
    print("VOCAB MASTER PRO — STANDALONE EXE BUILDER")
    print("===========================================")

    root_dir = Path(__file__).resolve().parent
    spec_path = root_dir / "VocabMaster.spec"

    if not spec_path.exists():
        print(f"Xatolik: {spec_path} topilmadi!")
        return False

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_path)
    ]

    print("PyInstaller ishga tushirilmoqda:")
    print(" ".join(cmd))
    print("\nIltimos, kuting (1-2 daqiqa vaqt oladi)...")

    res = subprocess.run(cmd, cwd=str(root_dir))
    if res.returncode == 0:
        exe_path = root_dir / "dist" / "VocabMaster.exe"
        if exe_path.exists():
            import shutil
            global_db = root_dir / "db.sqlite3"
            dist_db = root_dir / "dist" / "db.sqlite3"
            if global_db.exists() and (not dist_db.exists() or dist_db.stat().st_size != global_db.stat().st_size):
                print("📦 64,000 global akademik lug'at bazasi (db.sqlite3) dist/ ga nusxalanmoqda...")
                shutil.copy2(global_db, dist_db)

            size_mb = round(exe_path.stat().st_size / (1024 * 1024), 2)
            print("===========================================")
            print("🎉 MUVAFFAQIYATLI YAKUNLANDI!")
            print(f"📁 Tayyor Standalone EXE: {exe_path}")
            print(f"⚖️ EXE Hajmi: {size_mb} MB")
            print(f"📚 Baza: {dist_db} ({round(dist_db.stat().st_size / (1024*1024), 1) if dist_db.exists() else 0} MB)")
            print("Bu 'dist' papkasini istalgan Windows kompyuterga ko'chirib,")
            print("Python yoki boshqa dasturlarsiz to'g'ridan-to'g'ri ishlatish mumkin!")
            print("===========================================")
            return True

    print("❌ Xatolik yuz berdi!")
    return False


if __name__ == "__main__":
    build()
