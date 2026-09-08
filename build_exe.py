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
            size_mb = round(exe_path.stat().st_size / (1024 * 1024), 2)
            print("===========================================")
            print("🎉 MUVAFFAQIYATLI YAKUNLANDI!")
            print(f"📁 Tayyor fayl: {exe_path}")
            print(f"⚖️ Hajmi: {size_mb} MB")
            print("Bu faylni boshqa istalgan Windows kompyuterga nusxalab,")
            print("Python'siz to'g'ridan-to'g'ri ishga tushirish mumkin!")
            print("===========================================")
            return True

    print("❌ Xatolik yuz berdi!")
    return False


if __name__ == "__main__":
    build()
