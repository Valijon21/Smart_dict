import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

import logger
from logger import get_logger
import database as db
from ui.main_window import MainWindow

app_log = get_logger("app")


def main():
    # 1. Professional log tizimini ishga tushirish (Rotating file + Console)
    logger.setup_logging()
    app_log.info("Vocab Master ilovasi ishga tushmoqda...")

    try:
        # High DPI ekranlar uchun tiniq shriftlar
        if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough"):
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        # 2. Qt ilovasi yaratish
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setApplicationName("VocabMasterPro")

        # Global standart shrift (Segoe UI 10pt - tiniq va o'qishga qulay)
        from PyQt6.QtGui import QFont
        default_font = QFont("Segoe UI", 10)
        default_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        app.setFont(default_font)

        # 3. Yagona instansiya (Single Instance Guard) tekshiruvi
        from PyQt6.QtCore import QSharedMemory
        shared_mem = QSharedMemory("VocabMasterPro_SingleInstance_Key")
        if not shared_mem.create(1):
            app_log.warning("Dastur allaqachon ishga tushirilgan. Yangi instansiya to'xtatildi.")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                None,
                "Vocab Master Pro",
                "Dastur allaqachon ishlamoqda!\n\nIltimos, ekranning pastki o'ng burchagidagi (Windows Tray) nishonchani tekshiring."
            )
            sys.exit(0)

        # 4. Ma'lumotlar bazasini initsializatsiya qilish va kunlik xavfsiz avto-zaxira
        db.init_db()
        app_log.info("Ma'lumotlar bazasi tayyorlandi.")
        try:
            bak_path = db.auto_backup_daily()
            if bak_path:
                app_log.info(f"Mahalliy kunlik xavfsiz zaxira tayyorlandi: {bak_path}")
        except Exception as bak_err:
            app_log.warning(f"Avto-zaxira olishda ogohlantirish: {bak_err}")

        # 5. Asosiy oyna
        window = MainWindow()
        window.show()
        app_log.info("Bosh oyna foydalanuvchiga ko'rsatildi.")

        # 6. Voqealar sikli
        exit_code = app.exec()
        shared_mem.detach()
        app_log.info(f"Vocab Master normal tartibda yakunlandi. Exit code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        app_log.critical("Ilova ishga tushishida kutilmagan xatolik yuz berdi:", exc_info=True)
        raise


if __name__ == "__main__":
    main()
