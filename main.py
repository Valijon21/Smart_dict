import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

import logger
from logger import get_logger
import database as db
from ui.main_window import MainWindow

app_log = get_logger("app")


class SingleInstanceManager(QObject):
    """
    Windows va barcha platformalar uchun professional Yagona Instansiya (Single Instance) menejeri.
    QSharedMemory'dagi qulflanib qolish (stale lock/crash) muammosidan to'liq xoli bo'lib,
    QLocalServer / QLocalSocket IPC orqali ishlaydi:
    - Agar dastur allaqachon ishlab turgan bo'lsa, mavjud oynaga 'RESTORE' buyrug'ini yuboradi va uning oynasini ekranga chiqaradi.
    - Yangi instansiya esa shovqinsiz va xatosiz yopiladi.
    - Agar avvalgi jarayon to'satdan o'chgan bo'lsa, qadimgi socketni xavfsiz tozalab yangisini yoqadi.
    """
    restore_requested = pyqtSignal()

    def __init__(self, key: str = "VocabMasterPro_SingleInstance_IPC"):
        super().__init__()
        self.key = key
        self.server = None

    def is_another_instance_running(self) -> bool:
        """Boshqa faol instansiya ishlab turganini tekshirish."""
        socket = QLocalSocket()
        socket.connectToServer(self.key)
        if socket.waitForConnected(400):
            try:
                socket.write(b"RESTORE\n")
                socket.waitForBytesWritten(500)
            except Exception:
                pass
            socket.disconnectFromServer()
            return True
        return False

    def start_server(self) -> bool:
        """Yagona instansiya uchun mahalliy IPC serverni ishga tushirish."""
        QLocalServer.removeServer(self.key)
        self.server = QLocalServer()
        if self.server.listen(self.key):
            self.server.newConnection.connect(self._on_new_connection)
            return True
        return False

    def _on_new_connection(self):
        if not self.server:
            return
        client = self.server.nextPendingConnection()
        if not client:
            return
        client.readyRead.connect(lambda: self._read_client(client))

    def _read_client(self, client: QLocalSocket):
        try:
            msg = bytes(client.readAll()).decode("utf-8", errors="ignore")
            if "RESTORE" in msg:
                self.restore_requested.emit()
        except Exception:
            pass
        finally:
            try:
                client.disconnectFromServer()
            except Exception:
                pass

    def cleanup(self):
        if self.server:
            try:
                self.server.close()
                QLocalServer.removeServer(self.key)
            except Exception:
                pass
            self.server = None


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
        # System Tray rejimida oyna yopilganda dastur o'z-o'zidan to'xtab qolmasligi uchun
        app.setQuitOnLastWindowClosed(False)

        # Global standart shrift (Segoe UI 10pt - tiniq va o'qishga qulay)
        from PyQt6.QtGui import QFont
        default_font = QFont("Segoe UI", 10)
        default_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        app.setFont(default_font)

        # 3. Yagona instansiya (Single Instance Guard) tekshiruvi (IPC orqali)
        single_instance = SingleInstanceManager()
        if single_instance.is_another_instance_running():
            app_log.info("Dastur allaqachon orqa fonda ishlamoqda. Mavjud oynaga ochish buyrug'i yuborildi.")
            sys.exit(0)

        single_instance.start_server()

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
        single_instance.restore_requested.connect(window.restore_window)
        window.restore_window()
        app_log.info("Bosh oyna foydalanuvchiga ko'rsatildi.")

        # 6. Voqealar sikli
        exit_code = app.exec()
        single_instance.cleanup()
        app_log.info(f"Vocab Master normal tartibda yakunlandi. Exit code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        app_log.critical("Ilova ishga tushishida kutilmagan xatolik yuz berdi:", exc_info=True)
        raise


if __name__ == "__main__":
    main()
