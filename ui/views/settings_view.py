import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QCheckBox,
    QTimeEdit, QSlider, QPushButton, QFrame, QFileDialog, QMessageBox,
    QScrollArea, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt, QTime, QTimer

import database as db
import tts
import logger
import theme_manager
from logger import get_logger

log = get_logger("settings")


class SettingsWidget(QWidget):
    def __init__(self, on_settings_saved=None):
        super().__init__()
        self.on_settings_saved = on_settings_saved
        self._is_loading = False

        self.cards = []
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: #0F0F17; }")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: #0F0F17;")
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        # Header
        self.header_title = QLabel("⚙️ Dastur sozlamalari va Diagnostika")
        self.header_title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(self.header_title)

        # 1. Kunlik reja kartasi
        card_goal = self._create_card("🎯 Kunlik o'rganish maqsadi")
        goal_layout = QVBoxLayout(card_goal)
        goal_layout.setContentsMargins(20, 16, 20, 16)
        goal_layout.setSpacing(10)

        card_goal_desc = QLabel("Har kuni nechta yangi so'zni o'zlashtirishni reja qilganingizni belgilang:")
        card_goal_desc.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        goal_layout.addWidget(card_goal_desc)

        row_goal = QHBoxLayout()
        row_goal.setSpacing(10)
        self.lbl_goal = QLabel("Kuniga yangi so'zlar mashq qilish maqsadi:")
        self.lbl_goal.setStyleSheet("font-size: 13px; font-weight: 500;")
        row_goal.addWidget(self.lbl_goal)

        self.spin_goal = QSpinBox()
        self.spin_goal.setRange(1, 500)
        self.spin_goal.setFixedWidth(90)
        self.spin_goal.setStyleSheet(self._input_style())
        self.spin_goal.editingFinished.connect(self._on_goal_changed)
        self.spin_goal.valueChanged.connect(self._on_goal_changed)
        row_goal.addWidget(self.spin_goal)

        save_goal_btn = QPushButton("💾 Saqlash")
        save_goal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_goal_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border: none;"
            "border-radius: 6px; padding: 7px 16px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        save_goal_btn.clicked.connect(self._manual_save_goal)
        row_goal.addWidget(save_goal_btn)

        self.lbl_goal_saved = QLabel("")
        self.lbl_goal_saved.setStyleSheet("color: #10B981; font-size: 13px; font-weight: 600;")
        row_goal.addWidget(self.lbl_goal_saved)

        row_goal.addStretch()
        goal_layout.addLayout(row_goal)
        layout.addWidget(card_goal)

        # --- 2. Vizual Mavzular (Themes) kartasi ---
        card_theme = self._create_card("🎨 Interfeys Mavzulari (Visual Themes)")
        theme_layout = QVBoxLayout(card_theme)
        theme_layout.setContentsMargins(20, 16, 20, 16)
        theme_layout.setSpacing(12)

        theme_desc = QLabel("O'zingizga ma'qul ranglar palitrasini tanlang. Dastur bir lahzada yangi uslubga o'tadi:")
        theme_desc.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        theme_layout.addWidget(theme_desc)

        self.themes_grid = QGridLayout()
        self.themes_grid.setSpacing(10)
        self.theme_widgets = {}

        for idx, t in enumerate(theme_manager.get_all_themes()):
            row = idx // 3
            col = idx % 3
            card_w = self._build_theme_swatch_card(t)
            self.themes_grid.addWidget(card_w, row, col)

        theme_layout.addLayout(self.themes_grid)
        layout.addWidget(card_theme)

        # --- 3. Tipografiya va Matn O'lchami (Font Scale) kartasi ---
        t = theme_manager.get_active_theme()
        card_font = self._create_card("🔤 Matn va Shrift O'lchami (Typography & Scaling)")
        font_layout = QVBoxLayout(card_font)
        font_layout.setContentsMargins(20, 16, 20, 16)
        font_layout.setSpacing(12)

        font_desc = QLabel("Ko'zingizga qulay matn o'lchamini tanlang. O'lcham butun ilova bo'ylab zudlik bilan qo'llaniladi:")
        font_desc.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        font_layout.addWidget(font_desc)

        self.font_scale_btns = {}
        row_font = QHBoxLayout()
        row_font.setSpacing(12)

        current_scale = theme_manager.get_font_scale()

        for s_id, s_info in theme_manager.FONT_SCALE_OPTIONS.items():
            btn = QPushButton(f"{s_info['name']}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(42)
            btn.setCheckable(True)
            btn.setChecked(s_id == current_scale)
            btn.clicked.connect(lambda checked, sid=s_id: self._on_font_scale_selected(sid))
            row_font.addWidget(btn)
            self.font_scale_btns[s_id] = btn

        font_layout.addLayout(row_font)
        layout.addWidget(card_font)

        # 4. Eslatmalar va Tray kartasi
        card_reminder = self._create_card("🔔 Bildirishnomalar va Windows Tray")

        rem_layout = QVBoxLayout(card_reminder)
        rem_layout.setContentsMargins(20, 16, 20, 16)
        rem_layout.setSpacing(12)

        self.chk_reminder = QCheckBox("Kunlik reja bajarilmaganda Windows orqali eslatma ko'rsatilsin")
        self.chk_reminder.setStyleSheet("color: white; font-size: 13px;")
        self.chk_reminder.toggled.connect(self._auto_save_settings)
        rem_layout.addWidget(self.chk_reminder)

        row_time = QHBoxLayout()
        row_time.addWidget(QLabel("Eslatma chiqish vaqti:"))
        self.time_reminder = QTimeEdit()
        self.time_reminder.setDisplayFormat("HH:mm")
        self.time_reminder.setStyleSheet(self._input_style())
        self.time_reminder.timeChanged.connect(self._auto_save_settings)
        row_time.addWidget(self.time_reminder)
        row_time.addStretch()
        rem_layout.addLayout(row_time)

        self.chk_tray = QCheckBox("Dastur oynasi yopilganda (X) to'liq o'chmasdan, soat yoniga (Tray) yashirinsin")
        self.chk_tray.setStyleSheet("color: white; font-size: 13px;")
        self.chk_tray.toggled.connect(self._auto_save_settings)
        rem_layout.addWidget(self.chk_tray)

        self.chk_periodic_toast = QCheckBox("Kun so'zi eslatmalari (Desktop Smart Toast bildirishnomasi)")
        self.chk_periodic_toast.setStyleSheet("color: white; font-size: 13px;")
        self.chk_periodic_toast.toggled.connect(self._auto_save_settings)
        rem_layout.addWidget(self.chk_periodic_toast)

        self.chk_clipboard_lookup = QCheckBox("📋 Global Clipboard Avto-Qidiruv: Matn nusxalanganda (Ctrl+C) avtomatik tarjima popup ko'rsatilsin")
        self.chk_clipboard_lookup.setStyleSheet("color: white; font-size: 13px;")
        self.chk_clipboard_lookup.toggled.connect(self._auto_save_settings)
        rem_layout.addWidget(self.chk_clipboard_lookup)

        row_interval = QHBoxLayout()
        row_interval.addWidget(QLabel("Smart Toast chiqish oralig'i:"))
        self.combo_toast_interval = QComboBox()
        self.combo_toast_interval.addItems([
            "Har 30 daqiqada",
            "Har 1 soatda",
            "Har 2 soatda",
            "Har 3 soatda"
        ])
        self.combo_toast_interval.currentIndexChanged.connect(self._auto_save_settings)
        row_interval.addWidget(self.combo_toast_interval)
        row_interval.addStretch()
        rem_layout.addLayout(row_interval)

        layout.addWidget(card_reminder)

        # 3. Audio va Talaffuz kartasi
        card_audio = self._create_card("🔊 Oflayn Audio va Talaffuz (TTS)")
        audio_layout = QVBoxLayout(card_audio)
        audio_layout.setContentsMargins(20, 16, 20, 16)
        audio_layout.setSpacing(12)

        self.chk_autoplay = QCheckBox("Mashq boshlanganda inglizcha so'zni avtomatik talaffuz qilish")
        self.chk_autoplay.setStyleSheet("color: white; font-size: 13px;")
        self.chk_autoplay.toggled.connect(self._auto_save_settings)
        audio_layout.addWidget(self.chk_autoplay)

        self.chk_sound_fx = QCheckBox("Mashqlarda to'g'ri/xato javoblar uchun tovushli effektlar (Sound Feedback)")
        self.chk_sound_fx.setStyleSheet("color: white; font-size: 13px;")
        self.chk_sound_fx.toggled.connect(self._auto_save_settings)
        audio_layout.addWidget(self.chk_sound_fx)

        row_rate = QHBoxLayout()
        row_rate.addWidget(QLabel("Talaffuz tezligi:"))
        self.slider_rate = QSlider(Qt.Orientation.Horizontal)
        self.slider_rate.setRange(110, 210)
        self.slider_rate.setStyleSheet(
            """
            QSlider::groove:horizontal { height: 6px; background: #2A2A3C; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #4F46E5; border-radius: 3px; }
            QSlider::handle:horizontal { background: white; width: 16px; margin: -5px 0; border-radius: 8px; }
            """
        )
        self.slider_rate.valueChanged.connect(self._on_rate_change)
        row_rate.addWidget(self.slider_rate, 2)

        self.lbl_rate_val = QLabel("155")
        self.lbl_rate_val.setStyleSheet("color: #C4B5FD; font-weight: 600; min-width: 35px;")
        row_rate.addWidget(self.lbl_rate_val)

        test_tts_btn = QPushButton("🔊 Sinab ko'rish")
        test_tts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_tts_btn.setStyleSheet(
            "QPushButton { background-color: #3730A3; color: white; border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background-color: #4F46E5; }"
        )
        test_tts_btn.clicked.connect(self._test_speech)
        row_rate.addWidget(test_tts_btn)
        row_rate.addStretch()
        audio_layout.addLayout(row_rate)

        row_audio_int = QHBoxLayout()
        self.lbl_ai_title = QLabel("Audio pleyer oraliq kutish vaqti:")
        self.lbl_ai_title.setStyleSheet("font-size: 13px; color: white;")
        row_audio_int.addWidget(self.lbl_ai_title)

        self.slider_audio_interval = QSlider(Qt.Orientation.Horizontal)
        self.slider_audio_interval.setRange(10, 80)
        self.slider_audio_interval.setValue(40)
        self.slider_audio_interval.setStyleSheet(
            """
            QSlider::groove:horizontal { height: 6px; background: #2A2A3C; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #4F46E5; border-radius: 3px; }
            QSlider::handle:horizontal { background: white; width: 16px; margin: -5px 0; border-radius: 8px; }
            """
        )
        self.slider_audio_interval.valueChanged.connect(self._on_audio_interval_change)
        row_audio_int.addWidget(self.slider_audio_interval, 2)

        self.lbl_audio_interval_val = QLabel("4.0 soniya")
        self.lbl_audio_interval_val.setStyleSheet("color: #C4B5FD; font-weight: 600; min-width: 75px;")
        row_audio_int.addWidget(self.lbl_audio_interval_val)
        row_audio_int.addStretch()
        audio_layout.addLayout(row_audio_int)

        layout.addWidget(card_audio)

        # 4. Baza va Zaxira kartasi
        card_db = self._create_card("💾 Ma'lumotlar bazasi va Zaxira (Backup)")
        db_layout = QVBoxLayout(card_db)
        db_layout.setContentsMargins(20, 16, 20, 16)
        db_layout.setSpacing(10)

        self.lbl_db_path = QLabel(f"Baza joylashuvi: {db.DB_PATH}")
        self.lbl_db_path.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        db_layout.addWidget(self.lbl_db_path)

        row_backup = QHBoxLayout()
        row_backup.setSpacing(10)

        backup_btn = QPushButton("💾 Zaxira nusxa (Backup)")
        backup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        backup_btn.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; border-radius: 6px; padding: 8px 16px; font-weight: 600; font-size: 13px; }"
            "QPushButton:hover { background-color: #059669; }"
        )
        backup_btn.clicked.connect(self.backup_db)
        row_backup.addWidget(backup_btn)

        restore_btn = QPushButton("📥 Zaxiradan tiklash (Restore)")
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.setStyleSheet(
            "QPushButton { background-color: #3730A3; color: white; border-radius: 6px; padding: 8px 16px; font-weight: 600; font-size: 13px; }"
            "QPushButton:hover { background-color: #4F46E5; }"
        )
        restore_btn.clicked.connect(self.restore_db)
        row_backup.addWidget(restore_btn)

        open_db_dir_btn = QPushButton("📁 Papkani ochish")
        open_db_dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_db_dir_btn.setStyleSheet(
            "QPushButton { background-color: #1E1E2E; color: #9CA3AF; border: 1px solid #374151; border-radius: 6px; padding: 8px 14px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #2A2A3C; color: white; }"
        )
        open_db_dir_btn.clicked.connect(self.open_db_dir)
        row_backup.addWidget(open_db_dir_btn)

        row_backup.addStretch()
        db_layout.addLayout(row_backup)

        layout.addWidget(card_db)

        # 5. Tizim Diagnostikasi va Professional Loglar kartasi
        card_diag = self._create_card("📋 Tizim Diagnostikasi va Loglar")
        diag_layout = QVBoxLayout(card_diag)
        diag_layout.setContentsMargins(20, 16, 20, 16)
        diag_layout.setSpacing(12)

        self.lbl_log_path = QLabel(f"Log fayli: {logger.get_log_file_path()}")
        self.lbl_log_path.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        diag_layout.addWidget(self.lbl_log_path)

        self.lbl_log_size = QLabel(f"Hozirgi hajm: {logger.get_log_size_str()}")
        self.lbl_log_size.setStyleSheet("color: #C4B5FD; font-size: 12px; font-weight: 600;")
        diag_layout.addWidget(self.lbl_log_size)

        row_diag_btns = QHBoxLayout()
        row_diag_btns.setSpacing(10)

        open_log_btn = QPushButton("📂 Log fayli (Notepad)")
        open_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_log_btn.setStyleSheet(
            "QPushButton { background-color: #3730A3; color: white; border-radius: 6px; padding: 8px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4F46E5; }"
        )
        open_log_btn.clicked.connect(self.open_log_file)
        row_diag_btns.addWidget(open_log_btn)

        open_log_dir_btn = QPushButton("📁 Loglar papkasi")
        open_log_dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_log_dir_btn.setStyleSheet(
            "QPushButton { background-color: #1E1E2E; color: #9CA3AF; border: 1px solid #374151; border-radius: 6px; padding: 8px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #2A2A3C; color: white; }"
        )
        open_log_dir_btn.clicked.connect(self.open_log_dir)
        row_diag_btns.addWidget(open_log_dir_btn)

        clear_log_btn = QPushButton("🧹 Tozalash")
        clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_log_btn.setStyleSheet(
            "QPushButton { background-color: #4B5563; color: white; border-radius: 6px; padding: 8px 14px; font-size: 12px; }"
            "QPushButton:hover { background-color: #6B7280; }"
        )
        clear_log_btn.clicked.connect(self.clear_log_file)
        row_diag_btns.addWidget(clear_log_btn)

        diag_audio_btn = QPushButton("🔍 Ovoz diagnostikasi")
        diag_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diag_audio_btn.setStyleSheet(
            "QPushButton { background-color: #1E1E2E; color: #818CF8; border: 1px solid #6366F1;"
            "border-radius: 6px; padding: 8px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #312E81; color: white; }"
        )
        diag_audio_btn.clicked.connect(self.show_audio_diagnostics)
        row_diag_btns.addWidget(diag_audio_btn)

        row_diag_btns.addStretch()
        diag_layout.addLayout(row_diag_btns)

        layout.addWidget(card_diag)

        # Barcha sozlamalarni saqlash tugmasi
        save_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Barcha sozlamalarni saqlash")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border-radius: 8px; padding: 12px 28px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        self.save_btn.clicked.connect(self.save_settings)
        save_row.addWidget(self.save_btn)

        self.save_msg = QLabel("")
        self.save_msg.setStyleSheet("color: #10B981; font-size: 13px; font-weight: 600;")
        save_row.addWidget(self.save_msg)
        save_row.addStretch()

        layout.addLayout(save_row)
        layout.addStretch()

        self.scroll.setWidget(self.container)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.scroll)

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        self.load_settings()

    def _create_card(self, title: str) -> QFrame:
        t = theme_manager.get_active_theme()
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        if hasattr(self, "cards"):
            self.cards.append(frame)
        return frame

    def apply_theme(self, t: theme_manager.Theme):
        """Sozlamalar sahifasini faol mavzu ranglariga to'liq o'tkazish."""
        self.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "scroll"):
            self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.bg_app}; }}")
        if hasattr(self, "container"):
            self.container.setStyleSheet(f"background-color: {t.bg_app};")
        card_qss = f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};"
        for card in getattr(self, "cards", []):
            card.setStyleSheet(card_qss)
        if hasattr(self, "header_title"):
            self.header_title.setStyleSheet(f"color: {t.text_main}; font-size: 22px; font-weight: 700;")
        if hasattr(self, "lbl_goal"):
            self.lbl_goal.setStyleSheet(f"color: {t.text_main}; font-size: 13px; font-weight: 500;")
        if hasattr(self, "lbl_ai_title"):
            self.lbl_ai_title.setStyleSheet(f"color: {t.text_main}; font-size: 13px;")
        if hasattr(self, "save_btn"):
            self.save_btn.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 8px; padding: 12px 28px; font-size: 14px; font-weight: 700; }} "
                f"QPushButton:hover {{ background-color: {t.primary_hover}; }}"
            )
        for chk in [
            getattr(self, "chk_reminder", None),
            getattr(self, "chk_tray", None),
            getattr(self, "chk_periodic_toast", None),
            getattr(self, "chk_clipboard_lookup", None),
            getattr(self, "chk_autoplay", None),
            getattr(self, "chk_sound_fx", None),
        ]:
            if chk:
                chk.setStyleSheet(f"color: {t.text_main}; font-size: 13px;")
        for inp in [getattr(self, "spin_goal", None), getattr(self, "time_reminder", None)]:
            if inp:
                inp.setStyleSheet(self._input_style())
        if hasattr(self, "combo_toast_interval"):
            self.combo_toast_interval.setStyleSheet(
                f"QComboBox {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; "
                f"border-radius: 6px; padding: 4px 10px; font-size: 12px; }}"
            )
        self.refresh_theme_cards()

    def _build_theme_swatch_card(self, t: theme_manager.Theme) -> QFrame:
        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        # Sarlavha
        h_row = QHBoxLayout()
        name_lbl = QLabel(f"{t.icon} {t.name}")
        name_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 13px; font-weight: 700;")
        h_row.addWidget(name_lbl)
        h_row.addStretch()
        card_layout.addLayout(h_row)

        # Tavsif
        desc = QLabel(t.description)
        desc.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)


        # Rangli doirachalar (Swatches)
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(6)
        for col_hex in t.swatch_colors:
            dot = QLabel()
            dot.setFixedSize(16, 16)
            dot.setStyleSheet(f"background-color: {col_hex}; border-radius: 8px; border: 1px solid rgba(255,255,255,0.25);")
            swatch_row.addWidget(dot)
        swatch_row.addStretch()

        btn = QPushButton("Tanlash")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(26)
        btn.clicked.connect(lambda _, tid=t.id: self._select_theme(tid))
        swatch_row.addWidget(btn)
        card_layout.addLayout(swatch_row)

        self.theme_widgets[t.id] = {"card": card, "btn": btn, "theme": t}
        self._update_single_theme_card(t.id)
        return card

    def _select_theme(self, theme_id: str):
        theme_manager.set_active_theme(theme_id)
        self.refresh_theme_cards()

    def _update_single_theme_card(self, tid: str):
        if tid not in self.theme_widgets:
            return
        data = self.theme_widgets[tid]
        t = data["theme"]
        card = data["card"]
        btn = data["btn"]
        is_active = (theme_manager.get_active_theme().id == tid)

        if is_active:
            card.setStyleSheet(
                f"QFrame {{ background-color: {t.bg_card}; border: 2px solid {t.primary}; border-radius: 10px; }}"
            )
            btn.setText("✅ Faol")
            btn.setEnabled(False)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; font-size: 11px; font-weight: 700; "
                f"border-radius: 6px; padding: 2px 10px; border: none; }}"
            )
        else:
            card.setStyleSheet(
                f"QFrame {{ background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 10px; }}"
                f"QFrame:hover {{ border-color: {t.primary_light}; }}"
            )
            btn.setText("Tanlash")
            btn.setEnabled(True)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; font-size: 11px; font-weight: 600; "
                f"border-radius: 6px; padding: 2px 10px; border: 1px solid {t.border}; }}"
                f"QPushButton:hover {{ background-color: {t.primary}; color: white; border-color: {t.primary}; }}"
            )

    def refresh_theme_cards(self):
        for tid in self.theme_widgets:
            self._update_single_theme_card(tid)
        self._update_font_scale_buttons()

    def _on_font_scale_selected(self, scale_id: str):
        theme_manager.set_font_scale(scale_id)
        self._update_font_scale_buttons(scale_id)
        if self.on_settings_saved:
            self.on_settings_saved()

    def _update_font_scale_buttons(self, active_id: str = None):
        if not hasattr(self, "font_scale_btns"):
            return
        if active_id is None:
            active_id = theme_manager.get_font_scale()
        t = theme_manager.get_active_theme()
        for sid, btn in self.font_scale_btns.items():
            is_active = (sid == active_id)
            btn.setChecked(is_active)
            if is_active:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {t.primary}; color: white; border: 1.5px solid {t.primary_light}; "
                    f"border-radius: 8px; padding: 8px 16px; font-size: 14px; font-weight: 700; }} "
                    f"QPushButton:hover {{ background-color: {t.primary_hover}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; "
                    f"border-radius: 8px; padding: 8px 16px; font-size: 14px; font-weight: 500; }} "
                    f"QPushButton:hover {{ background-color: {t.border}; color: white; }}"
                )


    def _input_style(self) -> str:
        t = theme_manager.get_active_theme()
        return (
            f"background-color: {t.bg_sidebar}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 6px 10px; font-size: 13px;"
        )

    def _on_rate_change(self, val: int):
        self.lbl_rate_val.setText(str(val))
        tts.set_rate(val)
        if not self._is_loading:
            db.set_setting("tts_rate", str(val))

    def _on_audio_interval_change(self, val: int):
        sec = val / 10.0
        self.lbl_audio_interval_val.setText(f"{sec:.1f} soniya")
        if not self._is_loading:
            db.set_setting("audio_player_interval_sec", f"{sec:.1f}")
            if self.on_settings_saved:
                self.on_settings_saved()

    def _on_goal_changed(self):
        """Foydalanuvchi son yozganda yoki o'zgartirganda darhol avtomatik saqlash."""
        if self._is_loading:
            return
        val = self.spin_goal.value()
        current_db = db.get_daily_goal()
        if val != current_db:
            db.set_daily_goal(val)
            log.info(f"Kunlik o'rganish maqsadi avtomatik saqlandi: {val} ta so'z")
            self.lbl_goal_saved.setText(f"✅ Saqlandi ({val} ta so'z)")
            QTimer.singleShot(2500, lambda: self.lbl_goal_saved.setText(""))
            if self.on_settings_saved:
                self.on_settings_saved()

    def _manual_save_goal(self):
        val = self.spin_goal.value()
        db.set_daily_goal(val)
        log.info(f"Kunlik reja 'Saqlash' tugmasi orqali saqlandi: {val} ta so'z")
        self.lbl_goal_saved.setText(f"✅ Saqlandi ({val} ta so'z)")
        QTimer.singleShot(2500, lambda: self.lbl_goal_saved.setText(""))
        if self.on_settings_saved:
            self.on_settings_saved()

    def _auto_save_settings(self):
        if self._is_loading:
            return
        db.set_setting("reminder_enabled", "true" if self.chk_reminder.isChecked() else "false")
        db.set_setting("reminder_time", self.time_reminder.time().toString("HH:mm"))
        db.set_setting("minimize_to_tray", "true" if self.chk_tray.isChecked() else "false")
        db.set_setting("tts_autoplay", "true" if self.chk_autoplay.isChecked() else "false")
        db.set_setting("sound_effects_enabled", "true" if self.chk_sound_fx.isChecked() else "false")
        db.set_setting("periodic_reminder_enabled", "true" if self.chk_periodic_toast.isChecked() else "false")
        db.set_setting("clipboard_lookup_enabled", "true" if self.chk_clipboard_lookup.isChecked() else "false")
        intervals = ["30", "60", "120", "180"]
        c_idx = max(0, min(self.combo_toast_interval.currentIndex(), len(intervals) - 1))
        db.set_setting("periodic_reminder_interval_min", intervals[c_idx])
        if self.on_settings_saved:
            self.on_settings_saved()

    def _test_speech(self):
        log.info("Sozlamalar oynasida test audio talaffuz chaqirildi.")
        tts.speak("Vocab Master pronunciation is working perfectly!")

    def _open_system_path(self, target_path, is_dir: bool = False, description: str = ""):
        """Tizim darajasidagi papka yoki faylni xavfsiz ochish yordamchisi (DRY)."""
        try:
            p = Path(target_path)
            if is_dir:
                p.mkdir(parents=True, exist_ok=True)
            elif not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            os.startfile(str(p))
            log.info(f"Foydalanuvchi tizimda ochdi: {p} ({description})")
        except Exception as e:
            log.error(f"{description} ochishda xatolik: {e}")
            QMessageBox.warning(self, "Xatolik", f"{description} ochib bo'lmadi:\n{e}")

    def open_db_dir(self):
        """Ma'lumotlar bazasi joylashgan papkani ochish."""
        self._open_system_path(db.get_db_dir(), is_dir=True, description="Baza papkasi")

    def open_log_file(self):
        """Log faylini Windows standart dasturida (Notepad) ochish."""
        self._open_system_path(logger.get_log_file_path(), is_dir=False, description="Log fayli")

    def open_log_dir(self):
        """Loglar saqlanadigan papkani ochish."""
        self._open_system_path(logger.get_log_dir(), is_dir=True, description="Loglar papkasi")

    def clear_log_file(self):
        """Log faylini tozalash."""
        reply = QMessageBox.question(
            self,
            "Loglarni tozalash",
            "Haqiqatan ham barcha log yozuvlarini tozalamoqchimisiz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            logger.clear_logs()
            self.lbl_log_size.setText(f"Hozirgi hajm: {logger.get_log_size_str()}")
            QMessageBox.information(self, "Tozalandi", "Log fayli muvaffaqiyatli tozalandi.")

    def show_audio_diagnostics(self):
        """TTS drayveri va ovozlar holatini ko'rsatish."""
        diag = tts.get_diagnostics()
        voices_list = [f"  • {v}" for v in diag.get("available_voices", [])]
        voices_str = "\n".join(voices_list) if voices_list else "  (Ovozlar mavjud emas)"
        msg = (
            f"🔍 TTS Diagnostika Xulosasi:\n\n"
            f"• Holat: {diag.get('status')}\n"
            f"• Faol Dvigatel: {diag.get('engine')}\n"
            f"• Tanlangan Ovoz: {diag.get('active_voice')}\n"
            f"• Tezlik ko'rsatkichi: {diag.get('rate')}\n\n"
            f"Mavjud Windows ovozlari:\n{voices_str}\n\n"
            f"Sinov uchun 'Pronunciation test successful' talaffuz qilinmoqda."
        )
        tts.speak("Pronunciation test successful")
        QMessageBox.information(self, "Audio Diagnostika", msg)

    def load_settings(self):
        self._is_loading = True
        try:
            self.spin_goal.setValue(db.get_daily_goal())

            rem_en = (db.get_setting("reminder_enabled", "true") == "true")
            self.chk_reminder.setChecked(rem_en)

            rem_time_str = db.get_setting("reminder_time", "20:00")
            parts = rem_time_str.split(":")
            h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            self.time_reminder.setTime(QTime(h, m))

            tray_en = (db.get_setting("minimize_to_tray", "true") == "true")
            self.chk_tray.setChecked(tray_en)

            autoplay = (db.get_setting("tts_autoplay", "true") == "true")
            self.chk_autoplay.setChecked(autoplay)

            sound_fx = (db.get_setting("sound_effects_enabled", "true") == "true")
            self.chk_sound_fx.setChecked(sound_fx)

            rate = int(db.get_setting("tts_rate", "155"))
            self.slider_rate.setValue(rate)
            self.lbl_rate_val.setText(str(rate))
            tts.set_rate(rate)

            try:
                audio_sec = float(db.get_setting("audio_player_interval_sec", "4.0") or "4.0")
            except Exception:
                audio_sec = 4.0
            audio_sec = max(1.0, min(8.0, audio_sec))
            self.slider_audio_interval.setValue(int(audio_sec * 10))
            self.lbl_audio_interval_val.setText(f"{audio_sec:.1f} soniya")

            periodic_en = (db.get_setting("periodic_reminder_enabled", "true") == "true")
            self.chk_periodic_toast.setChecked(periodic_en)

            clip_en = (db.get_setting("clipboard_lookup_enabled", "true") == "true")
            self.chk_clipboard_lookup.setChecked(clip_en)

            cur_int = db.get_setting("periodic_reminder_interval_min", "60")
            int_map = {"30": 0, "60": 1, "120": 2, "180": 3}
            self.combo_toast_interval.setCurrentIndex(int_map.get(cur_int, 1))

            self.lbl_db_path.setText(f"Baza joylashuvi: {db.DB_PATH}")
            self.lbl_log_path.setText(f"Log fayli: {logger.get_log_file_path()}")
            self.lbl_log_size.setText(f"Hozirgi hajm: {logger.get_log_size_str()}")
            self.refresh_theme_cards()
        finally:
            self._is_loading = False

    def save_settings(self):
        val = self.spin_goal.value()
        db.set_daily_goal(val)
        db.set_setting("reminder_enabled", "true" if self.chk_reminder.isChecked() else "false")
        db.set_setting("reminder_time", self.time_reminder.time().toString("HH:mm"))
        db.set_setting("minimize_to_tray", "true" if self.chk_tray.isChecked() else "false")
        db.set_setting("tts_autoplay", "true" if self.chk_autoplay.isChecked() else "false")
        db.set_setting("sound_effects_enabled", "true" if self.chk_sound_fx.isChecked() else "false")
        db.set_setting("clipboard_lookup_enabled", "true" if self.chk_clipboard_lookup.isChecked() else "false")
        db.set_setting("tts_rate", str(self.slider_rate.value()))
        audio_sec = self.slider_audio_interval.value() / 10.0
        db.set_setting("audio_player_interval_sec", f"{audio_sec:.1f}")
        db.set_setting("periodic_reminder_enabled", "true" if self.chk_periodic_toast.isChecked() else "false")
        intervals = ["30", "60", "120", "180"]
        c_idx = max(0, min(self.combo_toast_interval.currentIndex(), len(intervals) - 1))
        db.set_setting("periodic_reminder_interval_min", intervals[c_idx])

        log.info(f"Barcha sozlamalar saqlandi. Kunlik reja: {val} ta so'z")

        self.save_msg.setText("✅ Barcha sozlamalar muvaffaqiyatli saqlandi!")
        self.lbl_goal_saved.setText(f"✅ Saqlandi ({val} ta so'z)")
        QTimer.singleShot(3000, lambda: self.save_msg.setText(""))
        QTimer.singleShot(3000, lambda: self.lbl_goal_saved.setText(""))

        if self.on_settings_saved:
            self.on_settings_saved()

    def backup_db(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Baza zaxira nusxasini saqlash", "vocab_backup.db", "SQLite Baza (*.db)"
        )
        if path:
            ok = db.backup_database(path)
            if ok:
                QMessageBox.information(self, "Muvaffaqiyatli", f"Baza zaxirasi saqlandi:\n{path}")
            else:
                QMessageBox.critical(self, "Xatolik", "Zaxira nusxa yaratishda xatolik yuz berdi.")

    def restore_db(self):
        reply = QMessageBox.question(
            self,
            "Tiklashni tasdiqlang",
            "Zaxira faylidan tiklash joriy bazadagi ma'lumotlarni yangilaydi. Davom ettirasizmi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Baza zaxira faylini tanlang", "", "SQLite Baza (*.db)"
        )
        if path:
            ok = db.restore_database(path)
            if ok:
                QMessageBox.information(self, "Muvaffaqiyatli", "Ma'lumotlar bazasi zaxiradan to'liq tiklandi!")
                self.load_settings()
                if self.on_settings_saved:
                    self.on_settings_saved()
            else:
                QMessageBox.critical(self, "Xatolik", "Zaxira faylini tiklashda xatolik yuz berdi.")
