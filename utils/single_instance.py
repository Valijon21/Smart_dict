"""
Vocab Master Pro — Professional Single Instance Manager (IPC).
QSharedMemory muammolarisiz, QLocalServer / QLocalSocket orqali
faqat 1 ta oyna ochilishini kafolatlaydi.
"""
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


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
