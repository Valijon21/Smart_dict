import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QSystemTrayIcon, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QTime, QDate, pyqtSlot
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QShortcut

from ui.dashboard import DashboardWidget
from ui.dictionary import DictionaryWidget
from ui.practice import PracticeWidget
from ui.import_dialog import ImportWidget
from ui.settings_page import SettingsWidget
from ui.reader import ReaderWidget
from ui.quick_capture import QuickCaptureDialog
from ui.match_game import MatchGameWidget
from ui.mini_widget import MiniWidget
import database as db
import theme_manager
from logger import get_logger

logger = get_logger("main_window")


NAV_ITEMS = [
    ("📊  Dashboard", "dashboard"),
    ("📖  Lug'at", "dictionary"),
    ("📚  Aqlli o'qish", "reader"),
    ("🎮  So'z juftlash", "match"),
    ("🇬🇧→🇺🇿  EN → UZ mashq", "en_uz"),
    ("🇺🇿→🇬🇧  UZ → EN mashq", "uz_en"),
    ("📥  So'z import qilish", "import"),
    ("⚙️  Sozlamalar", "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vocab Master Pro — Lug'at va Intellektual Trenajyor")
        self.resize(1180, 740)
        self.setStyleSheet("background-color: #0F0F17;")

        self.last_reminder_date = None
        self._tray_notified = False

        # Ilova ikonkasini o'rnatish
        icon_path = Path(__file__).resolve().parent.parent / "app_icon.png"
        if icon_path.exists():
            self.app_icon = QIcon(str(icon_path))
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Sidebar ---
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(240)
        self.side_layout = QVBoxLayout(self.sidebar)
        self.side_layout.setContentsMargins(16, 24, 16, 24)
        self.side_layout.setSpacing(8)

        self.logo = QLabel("📚 Vocab Master Pro")
        self.side_layout.addWidget(self.logo)

        self.nav_buttons = {}
        for label, key in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self.switch_page(k))
            self.side_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        self.side_layout.addStretch()

        # Tezkor mavzu tanlash tugmasi
        self.theme_btn = QPushButton("🎨 Mavzular")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("Vizual rang mavzusini tanlash")

        self.theme_menu = QMenu(self)
        for th in theme_manager.get_all_themes():
            act = QAction(f"{th.icon}  {th.name}", self)
            act.triggered.connect(lambda _, tid=th.id: theme_manager.set_active_theme(tid))
            self.theme_menu.addAction(act)
        self.theme_btn.setMenu(self.theme_menu)
        self.side_layout.addWidget(self.theme_btn)

        root.addWidget(self.sidebar)

        # --- Content stack ---
        self.stack = QStackedWidget()
        self.dashboard = DashboardWidget(
            on_navigate=self.switch_page,
            on_goal_changed=self._on_settings_saved,
            on_start_practice=self.start_custom_practice,
        )
        self.dictionary = DictionaryWidget(on_words_changed=self._on_words_changed)
        self.reader_widget = ReaderWidget(
            on_words_changed=self._on_words_changed,
            on_start_practice=self.start_custom_practice,
        )
        self.practice_en_uz = PracticeWidget("en_uz", on_finish_refresh=self.dashboard.refresh)
        self.practice_uz_en = PracticeWidget("uz_en", on_finish_refresh=self.dashboard.refresh)
        self.import_widget = ImportWidget(
            on_words_changed=self._on_words_changed,
            on_start_practice=self.start_custom_practice,
        )
        self.match_game = MatchGameWidget(self)
        self.settings_page = SettingsWidget(on_settings_saved=self._on_settings_saved)

        self.pages = {
            "dashboard": self.dashboard,
            "dictionary": self.dictionary,
            "reader": self.reader_widget,
            "match": self.match_game,
            "en_uz": self.practice_en_uz,
            "uz_en": self.practice_uz_en,
            "import": self.import_widget,
            "settings": self.settings_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.current_page_key = "dashboard"
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        self.switch_page("dashboard")

        # Mini suzib yuruvchi vidjet (Ctrl+Shift+W)
        self.mini_widget = None
        self.sc_mini_widget = QShortcut(QKeySequence("Ctrl+Shift+W"), self)
        self.sc_mini_widget.activated.connect(self.toggle_mini_widget)

        # Tezkor so'z qo'shish qisqa tugmalari (Ctrl+Shift+A va Ctrl+Shift+V)
        self.sc_capture_a = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        self.sc_capture_a.activated.connect(self.open_quick_capture)
        self.sc_capture_v = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
        self.sc_capture_v.activated.connect(self.open_quick_capture)

        # System Tray va Kunlik Eslatma taymeri
        self.setup_tray()
        self.setup_reminder_timer()

    def setup_tray(self):
        """Windows soat yonidagi System Tray ikonkasini sozlash."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self.app_icon, self)
        self.update_tray_tooltip()

        tray_menu = QMenu()
        tray_menu.setStyleSheet(
            "QMenu { background-color: #1E1E2E; color: white; border: 1px solid #2A2A3C; padding: 4px; }"
            "QMenu::item:selected { background-color: #4F46E5; }"
        )

        title_act = QAction("📚 Vocab Master Pro", self)
        title_act.setEnabled(False)
        tray_menu.addAction(title_act)
        tray_menu.addSeparator()

        open_act = QAction("🖥️ Oynani ochish", self)
        open_act.triggered.connect(self.restore_window)
        tray_menu.addAction(open_act)

        quick_act = QAction("⚡ Tezkor so'z qo'shish (Quick Add)", self)
        quick_act.triggered.connect(self.open_quick_capture)
        tray_menu.addAction(quick_act)

        mini_act = QAction("🪟 Mini vidjet (Ctrl+Shift+W)", self)
        mini_act.triggered.connect(self.toggle_mini_widget)
        tray_menu.addAction(mini_act)

        match_act = QAction("🎮 So'zlarni juftlash", self)
        match_act.triggered.connect(lambda: self._tray_navigate("match"))
        tray_menu.addAction(match_act)

        practice_act = QAction("⚡ EN → UZ Mashq", self)
        practice_act.triggered.connect(lambda: self._tray_practice("en_uz"))
        tray_menu.addAction(practice_act)

        practice_uz_act = QAction("⚡ UZ → EN Mashq", self)
        practice_uz_act.triggered.connect(lambda: self._tray_practice("uz_en"))
        tray_menu.addAction(practice_uz_act)

        settings_act = QAction("⚙️ Sozlamalar", self)
        settings_act.triggered.connect(lambda: self._tray_navigate("settings"))
        tray_menu.addAction(settings_act)

        tray_menu.addSeparator()
        quit_act = QAction("❌ Chiqish", self)
        quit_act.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_act)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    @pyqtSlot()
    def _on_tray_activated(self):
        """Tray ikonka bosilganda oynani tiklash (PyQt6 type-safe)."""
        self.restore_window()

    def restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def toggle_mini_widget(self):
        """Mini suzib yuruvchi vidjetni ochish yoki yashirish."""
        if self.mini_widget is None:
            self.mini_widget = MiniWidget()
        if self.mini_widget.isVisible():
            self.mini_widget.hide()
        else:
            self.mini_widget.load_words()
            self.mini_widget.show()
            self.mini_widget.raise_()
            self.mini_widget.activateWindow()

    def _tray_practice(self, direction: str):
        self.restore_window()
        self.switch_page(direction)

    def _tray_navigate(self, page_key: str):
        self.restore_window()
        self.switch_page(page_key)

    def quit_app(self):
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        if self.mini_widget:
            self.mini_widget.close()
        QApplication.quit()

    def closeEvent(self, event):
        """X bosilganda Tray'ga yashirish yoki butunlay yopish."""
        min_to_tray = (db.get_setting("minimize_to_tray", "true") == "true")
        if min_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            if not self._tray_notified:
                self._tray_notified = True
                self.tray_icon.showMessage(
                    "Vocab Master Pro",
                    "Dastur orqa fonda (Tray) ishlamoqda. Bildirishnomalar vaqtida ko'rsatiladi.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )
        else:
            self.quit_app()

    def setup_reminder_timer(self):
        """Har daqiqada kunlik eslatma vaqti kelganligini tekshiruvchi taymer."""
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_daily_reminder)
        self.reminder_timer.start(60000)  # Har 60 sekundda

    def check_daily_reminder(self):
        enabled = (db.get_setting("reminder_enabled", "true") == "true")
        if not enabled or not hasattr(self, "tray_icon"):
            return

        target_time = db.get_setting("reminder_time", "20:00")
        current_time = QTime.currentTime().toString("HH:mm")

        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        if current_time == target_time and self.last_reminder_date != today_str:
            prog = db.get_today_progress()
            if not prog["done"]:
                self.last_reminder_date = today_str
                remaining = prog["goal"] - prog["practiced"]
                self.tray_icon.showMessage(
                    "Vocab Master 🔥 Eslatma",
                    f"Bugungi rejangiz hali to'lmadi! Yana {remaining} ta so'z qoldi. Streak'ni saqlab qoling!",
                    QSystemTrayIcon.MessageIcon.Information,
                    6000
                )

    def start_custom_practice(self, word_ids: list[int], direction: str = "en_uz"):
        page_key = "en_uz" if direction == "en_uz" else "uz_en"
        self.pages[page_key].set_custom_words(word_ids)
        self.switch_page(page_key)

    def _nav_style(self, active: bool) -> str:
        t = theme_manager.get_active_theme()
        if active:
            return (
                f"QPushButton {{ background-color: {t.primary}; color: white; border: none;"
                f"border-radius: 8px; padding: 10px 14px; text-align: left; font-size: 13px; font-weight: 600; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {t.text_muted}; border: none;"
            f"border-radius: 8px; padding: 10px 14px; text-align: left; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {t.bg_card}; color: {t.text_main}; }}"
        )

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        self.sidebar.setStyleSheet(f"background-color: {t.bg_sidebar}; border-right: 1px solid {t.border};")
        self.logo.setStyleSheet(f"color: {t.text_main}; font-size: 18px; font-weight: 700; padding-bottom: 16px;")
        self.theme_btn.setText(f"🎨 {t.name}")
        self.theme_btn.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.primary_light}; border: 1px solid {t.border};"
            f"border-radius: 8px; padding: 8px 12px; font-size: 12px; font-weight: 600; text-align: left; }}"
            f"QPushButton:hover {{ background-color: {t.primary}; color: white; border-color: {t.primary}; }}"
        )
        if hasattr(self, "theme_menu"):
            self.theme_menu.setStyleSheet(
                f"QMenu {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; padding: 6px; }} "
                f"QMenu::item {{ padding: 6px 14px; border-radius: 6px; font-size: 12px; color: {t.text_main}; }} "
                f"QMenu::item:selected {{ background-color: {t.primary}; color: white; }}"
            )
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme_manager.get_global_stylesheet(t))
        curr = getattr(self, "current_page_key", "dashboard")
        for k, btn in self.nav_buttons.items():
            btn.setStyleSheet(self._nav_style(k == curr))
        for page in getattr(self, "pages", {}).values():
            if hasattr(page, "apply_theme") and callable(page.apply_theme):
                page.apply_theme(t)

    def update_tray_tooltip(self):
        if not hasattr(self, "tray_icon") or not self.tray_icon:
            return
        streak = db.get_current_streak()
        prog = db.get_today_progress()
        xp = db.get_xp()
        self.tray_icon.setToolTip(
            f"Vocab Master Pro\n🎯 Reja: {prog['practiced']}/{prog['goal']} ta\n🔥 Streak: {streak} kun | ⭐ {xp} XP"
        )

    def open_quick_capture(self):
        dlg = QuickCaptureDialog(self, on_word_added=self._on_quick_word_added)
        dlg.exec()

    def _on_quick_word_added(self, eng: str, uz: str):
        self._on_words_changed()
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "Vocab Master Pro",
                f"✅ '{eng}' -> '{uz}' bazaga qo'shildi!",
                QSystemTrayIcon.MessageIcon.Information,
                2500
            )

    def switch_page(self, key: str):
        logger.debug(f"Sahifa almashtirildi: '{key}'")
        self.current_page_key = key
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
            btn.setStyleSheet(self._nav_style(k == key))
        if key == "dashboard":
            self.dashboard.refresh()
        elif key == "dictionary":
            self.dictionary.load_words()
        elif key == "reader":
            self.reader_widget.refresh_reader()
        elif key == "settings":
            self.settings_page.load_settings()
        elif key in ("en_uz", "uz_en"):
            if not getattr(self.pages[key], "custom_word_ids", None):
                self.pages[key].load_batch()
        self.stack.setCurrentWidget(self.pages[key])
        self.update_tray_tooltip()

    def _on_words_changed(self):
        self.dashboard.refresh()
        self.dictionary.load_words()
        if hasattr(self, "reader_widget"):
            self.reader_widget.refresh_reader()
        self.update_tray_tooltip()

    def _on_settings_saved(self):
        self.dashboard.refresh()
        self.update_tray_tooltip()
