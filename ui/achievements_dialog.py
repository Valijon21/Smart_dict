"""
Vocab Master Pro — Yutuqlar va Nishonlar (Achievements Modal).
Foydalanuvchining nishonlari, XP ballari va darajasini zamonaviy ko'rinishda taqdim etadi.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QProgressBar
)
from PyQt6.QtCore import Qt
import database as db
import gamification
import theme_manager


class AchievementsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme_manager.get_active_theme()
        self.setWindowTitle("🏆 Yutuqlar va Nishonlar")
        self.setFixedSize(580, 620)
        self.setStyleSheet(f"background-color: {t.bg_app}; color: {t.text_main}; border-radius: 12px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Header: Daraja va XP xulosasi
        lvl_info = gamification.get_level_info()
        header_frame = QFrame()
        header_frame.setStyleSheet(
            f"background-color: {t.bg_card}; border: 1px solid {lvl_info['color']}; border-radius: 12px;"
        )
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(18, 14, 18, 14)
        h_layout.setSpacing(8)

        top_row = QHBoxLayout()
        lvl_label = QLabel(f"{lvl_info['badge']} {lvl_info['level']}-Daraja: {lvl_info['title']}")
        lvl_label.setStyleSheet(f"color: {lvl_info['color']}; font-size: 17px; font-weight: 700;")
        top_row.addWidget(lvl_label)

        top_row.addStretch()

        xp_label = QLabel(f"⭐ Jami: {lvl_info['total_xp']} XP")
        xp_label.setStyleSheet("color: #FBBF24; font-size: 15px; font-weight: 700;")
        top_row.addWidget(xp_label)
        h_layout.addLayout(top_row)

        # Progress bar
        pbar = QProgressBar()
        pbar.setValue(lvl_info["progress_percent"])
        pbar.setFormat(f"Keyingi darajagacha: {lvl_info['xp_in_level']} / {lvl_info['xp_in_level'] + lvl_info['xp_needed']} XP ({lvl_info['progress_percent']}%)")
        pbar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {t.bg_card_secondary};
                border-radius: 7px;
                height: 18px;
                text-align: center;
                color: {t.text_main};
                font-size: 11px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background: {lvl_info['color']};
                border-radius: 6px;
            }}
            """
        )
        h_layout.addWidget(pbar)
        layout.addWidget(header_frame)

        # 2. Sarlavha
        title_lbl = QLabel("Barcha nishonlar va vazifalar:")
        title_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px; font-weight: 600;")
        layout.addWidget(title_lbl)

        # 3. Scroll area bilan yutuqlar ro'yxati
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(10)

        # Bazadagi barcha yutuqlarni olish
        achievements = db.get_all_achievements()
        # Agar baza yangi bo'lsa
        if not achievements:
            gamification.init_gamification()
            achievements = db.get_all_achievements()

        unlocked_count = sum(1 for a in achievements if a.get("unlocked_at"))

        for a in achievements:
            card = self._create_achievement_card(a)
            c_layout.addWidget(card)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # 4. Pastki qator
        bottom_row = QHBoxLayout()
        summary_lbl = QLabel(f"Ochilgan nishonlar: {unlocked_count} / {len(achievements)}")
        summary_lbl.setStyleSheet("color: #34D399; font-size: 13px; font-weight: 600;")
        bottom_row.addWidget(summary_lbl)

        bottom_row.addStretch()

        close_btn = QPushButton("Yopish")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border-radius: 8px; "
            "padding: 8px 20px; font-weight: 600; } QPushButton:hover { background-color: #4338CA; }"
        )
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)

        layout.addLayout(bottom_row)

    def _create_achievement_card(self, ach: dict) -> QFrame:
        is_unlocked = bool(ach.get("unlocked_at"))
        card = QFrame()

        border_col = "#059669" if is_unlocked else "#2A2A3C"
        bg_col = "#162820" if is_unlocked else "#1A1A28"

        card.setStyleSheet(
            f"QFrame {{ background-color: {bg_col}; border: 1px solid {border_col}; "
            f"border-radius: 10px; }}"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(14)

        # Ikonka
        icon_lbl = QLabel(ach.get("icon", "🏆") if is_unlocked else "🔒")
        icon_lbl.setStyleSheet("font-size: 26px;")
        card_layout.addWidget(icon_lbl)

        # Matnlar
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title = QLabel(ach.get("title", ""))
        title_color = "#34D399" if is_unlocked else "white"
        title.setStyleSheet(f"color: {title_color}; font-size: 14px; font-weight: 700;")
        text_layout.addWidget(title)

        desc = QLabel(ach.get("description", ""))
        desc.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        desc.setWordWrap(True)
        text_layout.addWidget(desc)

        # Progress / Status
        if is_unlocked:
            status_lbl = QLabel(f"✅ Bajarildi: {ach.get('unlocked_at')}")
            status_lbl.setStyleSheet("color: #6EE7B7; font-size: 12px; font-weight: 600;")
            text_layout.addWidget(status_lbl)
        else:
            prog = ach.get("progress", 0)
            max_p = ach.get("max_progress", 1)
            if max_p > 1:
                p_text = f"Jarayon: {prog} / {max_p}"
            else:
                p_text = "Hali ochilmagan"
            status_lbl = QLabel(p_text)
            status_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px;")
            text_layout.addWidget(status_lbl)


        card_layout.addLayout(text_layout, 1)
        return card
