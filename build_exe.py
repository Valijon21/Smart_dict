"""
Vocab Master Pro — Senior Production Build & Packaging Script.
Standart Windows Executable (.exe), mustaqil Portable papka va
tarqatish uchun tayyor ZIP arxivini avtomatik ravishda hosil qiladi.
"""
import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

# UTF-8 chiqishini ta'minlash
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def print_banner(title: str):
    width = 65
    print("=" * width)
    print(f" {title.center(width - 2)} ")
    print("=" * width)


def get_python_executable(root_dir: Path) -> Path:
    """Tizimda yoki venv papkasidagi eng to'g'ri Python interpreterini aniqlaydi."""
    venv_py = root_dir / "venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return venv_py
    return Path(sys.executable)


def run_preflight_checks(root_dir: Path, py_exe: Path) -> bool:
    """Build oldidan barcha kerakli fayllar va resurslarni tekshirish."""
    print("🔍 1. Pre-flight tekshiruvlari o'tkazilmoqda...")

    required_files = [
        ("VocabMaster.spec", "PyInstaller spec fayli"),
        ("version_info.txt", "Windows PE Version ma'lumotlari"),
        ("app.manifest", "Windows DPI-Aware manifest"),
        ("app.ico", "Windows ilova ikonkasi"),
        ("db.sqlite3", "64,000 akademik lug'at bazasi"),
        ("sample_words.txt", "Namunaviy import fayli"),
    ]

    missing = []
    for rel_path, desc in required_files:
        full_path = root_dir / rel_path
        if not full_path.exists():
            missing.append(f"  ❌ {rel_path} ({desc}) topilmadi!")
        else:
            size_kb = round(full_path.stat().st_size / 1024, 1)
            print(f"  ✅ {rel_path} ({desc}) — {size_kb} KB")

    if missing:
        print("\nQuyidagi zarur fayllar yetishmayapti:")
        for m in missing:
            print(m)
        return False

    # PyInstaller mavjudligini tekshirish
    try:
        res = subprocess.run(
            [str(py_exe), "-m", "PyInstaller", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"  ✅ PyInstaller versiyasi: {res.stdout.strip()}")
    except Exception as e:
        print(f"  ❌ PyInstaller topilmadi yoki ishlamadi: {e}")
        return False

    print("  ✨ Barcha pre-flight tekshiruvlari muvaffaqiyatli o'tdi.\n")
    return True


def create_readme_txt(dest_dir: Path):
    """Tarqatish papkasi uchun tushunarli qo'llanma yaratish."""
    content = """===================================================================
VOCAB MASTER PRO — SMART ENGLISH DICTIONARY & SPACED REPETITION
===================================================================

Dastur haqida:
-------------
Vocab Master Pro — 100% oflayn ishlaydigan, 64,000 dan ortiq
akademik so'zlar bazasiga va SM-2 interval takrorlash algoritmlariga
ega professional Windows ilovasi.

Qanday ishga tushiriladi?
-------------------------
1. Ushbu papkadagi 'VocabMaster.exe' faylini ikki marta bosing.
2. Dastur to'liq mustaqil (Portable) ishlaydi — hech qanday Python,
   kutubxona yoki qo'shimcha dasturlar o'rnatish talab etilmaydi!

Papkadagi muhim fayllar:
-----------------------
- VocabMaster.exe  : Dasturning asosiy ishga tushiruvchi fayli.
- db.sqlite3       : 64,000 ta so'zdan iborat akademik global lug'at bazasi.
                     (Ushbu faylni o'chirib tashlamang!)
- vocab.db         : Sizning shaxsiy o'rgangan so'zlaringiz, natijalaringiz
                     va eslab qolish statistikangiz (avtomatik yaratiladi).
- sample_words.txt : Test uchun namunaviy so'zlar ro'yxati (Import uchun).
- app.ico          : Dastur ikonkasi.

Tizim talablari:
---------------
- Windows 10 yoki Windows 11 (64-bit)
- 4GB+ Operativ xotira (RAM)
- Minimum 300MB bo'sh disk maydoni

Texnik qo'llab-quvvatlash:
-------------------------
Mualliflik huquqi: (c) 2026 SmartDict. Barcha huquqlar himoyalangan.
===================================================================
"""
    readme_path = dest_dir / "README.txt"
    readme_path.write_text(content, encoding="utf-8")


def build():
    root_dir = Path(__file__).resolve().parent
    print_banner("VOCAB MASTER PRO — SENIOR PRODUCTION EXE BUILDER")

    py_exe = get_python_executable(root_dir)
    print(f"Tanlangan Python muhiti: {py_exe}\n")

    # 1. Pre-flight tekshiruvi
    if not run_preflight_checks(root_dir, py_exe):
        print("❌ Build jarayoni to'xtatildi.")
        return False

    spec_path = root_dir / "VocabMaster.spec"
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"

    # 2. PyInstaller ishga tushirish
    cmd = [
        str(py_exe), "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_path)
    ]

    print("🚀 2. PyInstaller kompilyatsiyasi boshlanmoqda...")
    print(f"Buyruq: {' '.join(cmd)}")
    print("Iltimos, kuting (bu jarayon 1-2 daqiqa vaqt olishi mumkin)...\n")

    res = subprocess.run(cmd, cwd=str(root_dir))
    if res.returncode != 0:
        print("\n❌ PyInstaller xatolik bilan tugadi!")
        return False

    raw_exe = dist_dir / "VocabMaster.exe"
    if not raw_exe.exists():
        print(f"\n❌ Xatolik: {raw_exe} hosil bo'lmadi!")
        return False

    # 3. Professional Distribution Staging (dist/VocabMaster/)
    print("\n📦 3. Professional Portable distributiv shakllantirilmoqda...")
    portable_dir = dist_dir / "VocabMaster"
    if portable_dir.exists():
        shutil.rmtree(portable_dir)
    portable_dir.mkdir(parents=True, exist_ok=True)

    # Standalone EXE ko'chiriladi
    target_exe = portable_dir / "VocabMaster.exe"
    shutil.move(str(raw_exe), str(target_exe))

    # db.sqlite3 ko'chiriladi (portable bazasi)
    global_db = root_dir / "db.sqlite3"
    target_db = portable_dir / "db.sqlite3"
    print("  -> 64,000 akademik lug'at bazasi nusxalanmoqda...")
    shutil.copy2(global_db, target_db)

    # Qo'shimcha yordamchi fayllar
    shutil.copy2(root_dir / "sample_words.txt", portable_dir / "sample_words.txt")
    shutil.copy2(root_dir / "app.ico", portable_dir / "app.ico")
    create_readme_txt(portable_dir)
    print("  -> README.txt va yordamchi fayllar tayyorlandi.")

    # 4. ZIP arxiv yaratish (Yagona faylda tarqatish uchun)
    print("\n🗜️ 4. Bir bosishda tarqatiladigan ZIP arxiv yaratilmoqda...")
    zip_path = dist_dir / "VocabMaster-Pro-v1.0.0-Windows.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in portable_dir.rglob("*"):
            rel = file.relative_to(dist_dir)
            zipf.write(file, arcname=str(rel))

    # 5. Hisobot va xulosa
    exe_size_mb = round(target_exe.stat().st_size / (1024 * 1024), 2)
    db_size_mb = round(target_db.stat().st_size / (1024 * 1024), 2)
    zip_size_mb = round(zip_path.stat().st_size / (1024 * 1024), 2)

    print_banner("🎉 MUVAFFAQIYATLI YAKUNLANDI!")
    print(f"📁 Tayyor Portable Papka: {portable_dir}")
    print(f"⚡ Asosiy Dastur:         {target_exe} ({exe_size_mb} MB)")
    print(f"📚 Oflayn Lug'at Bazasi:  {target_db} ({db_size_mb} MB)")
    print(f"🎁 Tarqatish uchun ZIP:   {zip_path} ({zip_size_mb} MB)")
    print("-" * 65)
    print("Bu papkani yoki ZIP faylni istalgan Windows kompyuterga yuborib,")
    print("to'g'ridan-to'g'ri hech narsa o'rnatmasdan ishlatish mumkin!")
    print("=" * 65)

    return True


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
