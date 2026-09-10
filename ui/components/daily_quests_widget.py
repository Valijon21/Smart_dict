"""
Vocab Master Pro — Kunlik Missiyalar (Daily Quests & Battle Pass) Vidjeti.
Har kuni yangilanadigan 3 ta dinamik vazifa, progress panellari va XP yig'ish tizimi.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QGridLayout, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

import theme_manager
import sound_effects
import daily_quests_service
from logger import get_logger

logger = get_logger("daily_quests_widget")


class QuestItemCard(QFrame):
    """Bitta kunlik vazifaning interaktiv kartochkasi."""
    reward_claimed = pyqtSignal(dict)

    def __init__(self, quest_data: dict, parent=None):
        super().__init__(parent)
        self.quest_data = quest_data
        self.setMinimumHeight(130)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        self.layout.setSpacing(10)

        # 1. Tepasi: Ikonka + Sarlavha + XP sovrini
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        icon_str = quest_data.get("icon", "🎯")
        self.lbl_icon = QLabel(icon_str)
        self.lbl_icon.setStyleSheet(
            "font-size: 20px; background-color: #24243A; border-radius: 18px; "
            "padding: 6px; border: 1px solid #3730A3;"
        )
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setFixedSize(36, 36)
        top_row.addWidget(self.lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        self.lbl_title = QLabel(quest_data.get("title", "Vazifa"))
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: white;")
        title_vbox.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(quest_data.get("description", ""))
        self.lbl_desc.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        self.lbl_desc.setWordWrap(True)
        title_vbox.addWidget(self.lbl_desc)

        top_row.addLayout(title_vbox, 1)

        self.lbl_xp_badge = QLabel(f"⭐ +{quest_data.get('reward_xp', 25)} XP")
        self.lbl_xp_badge.setStyleSheet(
            "background-color: #2D2006; color: #FBBF24; border: 1px solid #B45309; "
            "border-radius: 6px; padding: 4px 8px; font-size: 12px; font-weight: 700;"
        )
        top_row.addWidget(self.lbl_xp_badge)

        self.layout.addLayout(top_row)

        # 2. Progress Bar
        cur = quest_data.get("current", 0)
        target = max(1, quest_data.get("target", 1))
        pct = min(100, int((cur / target) * 100))

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, target)
        self.progress_bar.setValue(min(cur, target))
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat(f"%v / %m ({pct}%)")
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #12121C;
                border: 1px solid #28283E;
                border-radius: 6px;
                height: 18px;
                text-align: center;
                color: white;
                font-size: 11px;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F46E5, stop:1 #10B981);
                border-radius: 5px;
            }
            """
        )
        self.layout.addWidget(self.progress_bar)

        # 3. Pastki qator: Status yoki "Yig'ish" tugmasi
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.btn_action = QPushButton("")
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setFixedHeight(34)
        self.btn_action.clicked.connect(self._on_action_clicked)
        bottom_row.addWidget(self.btn_action)

        self.layout.addLayout(bottom_row)
        self.update_state(quest_data)

    def update_state(self, q: dict):
        self.quest_data = q
        cur = q.get("current", 0)
        target = max(1, q.get("target", 1))
        claimed = q.get("claimed", False)
        is_done = cur >= target
        pct = min(100, int((cur / target) * 100))

        self.progress_bar.setValue(min(cur, target))
        self.progress_bar.setFormat(f"{cur} / {target} ({pct}%)")

        if claimed:
            self.btn_action.setEnabled(False)
            self.btn_action.setText(f"✅ Mukofot Olingan (+{q.get('reward_xp', 20)} XP)")
            self.btn_action.setStyleSheet(
                "QPushButton { background-color: #064E3B; color: #6EE7B7; border: 1px solid #059669; "
                "border-radius: 8px; font-size: 12px; font-weight: 700; padding: 4px 14px; }"
            )
        elif is_done:
            self.btn_action.setEnabled(True)
            self.btn_action.setText(f"🎁 Mukofotni Olish (+{q.get('reward_xp', 20)} XP)")
            self.btn_action.setStyleSheet(
                "QPushButton { background-color: #059669; color: white; border: 1.5px solid #34D399; "
                "border-radius: 8px; font-size: 13px; font-weight: 800; padding: 4px 14px; } "
                "QPushButton:hover { background-color: #10B981; }"
            )
        else:
            self.btn_action.setEnabled(False)
            self.btn_action.setText(f"⏳ Bajarilmoqda ({cur} / {target})")
            self.btn_action.setStyleSheet(
                "QPushButton { background-color: #24243A; color: #9CA3AF; border: 1px solid #374151; "
                "border-radius: 8px; font-size: 12px; font-weight: 600; padding: 4px 14px; }"
            )

    def _on_action_clicked(self):
        q_id = self.quest_data.get("id")
        if not q_id:
            return
        res = daily_quests_service.claim_quest_reward(q_id)
        if res.get("success"):
            sound_effects.play_correct()
            self.reward_claimed.emit(res)

    def apply_theme(self, t: theme_manager.Theme):
        is_dark = getattr(t, "is_dark", True)
        bg = "#1A1A2A" if is_dark else "#F8FAFC"
        border = "#2E2A48" if is_dark else "#E2E8F0"
        self.setStyleSheet(
            f"QuestItemCard {{ background-color: {bg}; border: 1px solid {border}; border-radius: 12px; }}"
        )
        self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {t.text_main};")
        self.lbl_desc.setStyleSheet(f"font-size: 12px; color: {t.text_muted};")


class DailyQuestsWidget(QFrame):
    """
    Dashboard ichida joylashuvchi dinamik Kunlik Missiyalar (Daily Quests & Battle Pass) paneli.
    """
    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.quest_cards: list[QuestItemCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # 1. Header paneli
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        self.lbl_header = QLabel("🎯 Kunlik Missiyalar (Daily Quests & Battle Pass)")
        self.lbl_header.setStyleSheet("font-size: 18px; font-weight: 800; color: white;")
        title_vbox.addWidget(self.lbl_header)

        self.lbl_subtitle = QLabel("Har kuni 00:00 da yangilanadi. Vazifalarni bajaring va qo'shimcha XP yig'ing!")
        self.lbl_subtitle.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        title_vbox.addWidget(self.lbl_subtitle)
        header_row.addLayout(title_vbox, 1)

        # Status badge (masalan: 2 / 3 bajarildi)
        self.badge_status = QLabel("0 / 3")
        self.badge_status.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; border: 1px solid #4338CA; "
            "border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 700;"
        )
        header_row.addWidget(self.badge_status)
        layout.addLayout(header_row)

        # 2. 3 ta Vazifalar qatori (Grid)
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(12)
        layout.addLayout(self.cards_grid)

        # 3. Kunlik Battle Pass Super Bonus Banneri (+50 XP)
        self.bonus_frame = QFrame()
        self.bonus_frame.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2E1065, stop:1 #1E1B4B); "
            "border: 1.5px solid #7C3AED; border-radius: 12px;"
        )
        bonus_layout = QHBoxLayout(self.bonus_frame)
        bonus_layout.setContentsMargins(16, 12, 16, 12)
        bonus_layout.setSpacing(12)

        self.lbl_bonus_icon = QLabel("🎁")
        self.lbl_bonus_icon.setStyleSheet("font-size: 26px; border: none; background: transparent;")
        bonus_layout.addWidget(self.lbl_bonus_icon)

        bonus_text_vbox = QVBoxLayout()
        bonus_text_vbox.setSpacing(2)

        self.lbl_bonus_title = QLabel("Kunlik Super Bonus (Battle Pass Tier)")
        self.lbl_bonus_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #F5D0FE;")
        bonus_text_vbox.addWidget(self.lbl_bonus_title)

        self.lbl_bonus_desc = QLabel("3 ta vazifaning barchasini to'liq bajaring va +50 XP Super Bonusi oling!")
        self.lbl_bonus_desc.setStyleSheet("font-size: 12px; color: #DDD6FE;")
        bonus_text_vbox.addWidget(self.lbl_bonus_desc)

        bonus_layout.addLayout(bonus_text_vbox, 1)

        self.btn_bonus_claim = QPushButton("🎁 +50 XP Olish")
        self.btn_bonus_claim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bonus_claim.setFixedHeight(36)
        self.btn_bonus_claim.setStyleSheet(
            "QPushButton { background-color: #9333EA; color: white; border: 1.5px solid #C084FC; "
            "border-radius: 8px; font-size: 13px; font-weight: 800; padding: 4px 16px; } "
            "QPushButton:hover { background-color: #A855F7; }"
        )
        self.btn_bonus_claim.clicked.connect(self._on_claim_super_bonus)
        bonus_layout.addWidget(self.btn_bonus_claim)

        layout.addWidget(self.bonus_frame)

        t = theme_manager.get_active_theme()
        self.apply_theme(t)
        self.refresh()
        try:
            theme_manager.register_listener(self.apply_theme)
        except Exception:
            pass

    def refresh(self):
        """Kunlik vazifalar holatini qayta o'qish va ko'rinishni yangilash."""
        summary = daily_quests_service.get_daily_summary()
        quests = summary.get("quests", [])
        completed_count = summary.get("completed_count", 0)
        total_count = summary.get("total_count", 3)
        claimed_count = summary.get("claimed_count", 0)
        bonus_claimed = summary.get("bonus_claimed", False)
        bonus_reward_xp = summary.get("bonus_reward_xp", 50)

        self.badge_status.setText(f"🔥 {completed_count} / {total_count} bajarildi")

        # Kartalarni to'ldirish
        if not self.quest_cards:
            for idx, q in enumerate(quests):
                card = QuestItemCard(q, self)
                card.reward_claimed.connect(self._on_item_reward_claimed)
                t = theme_manager.get_active_theme()
                card.apply_theme(t)
                self.quest_cards.append(card)
                self.cards_grid.addWidget(card, 0, idx)
        else:
            for idx, q in enumerate(quests):
                if idx < len(self.quest_cards):
                    self.quest_cards[idx].update_state(q)

        # Super bonus bannerini sozlash
        all_claimed = summary.get("all_claimed", False)

        if bonus_claimed:
            self.lbl_bonus_title.setText("👑 Kunlik Battle Pass yakunlandi!")
            self.lbl_bonus_desc.setText("Bugungi barcha vazifalar va Super Bonus to'liq olingan. Ertaga yangi missiyalar ochiladi!")
            self.btn_bonus_claim.setEnabled(False)
            self.btn_bonus_claim.setText("✅ Olingan (+50 XP)")
            self.btn_bonus_claim.setStyleSheet(
                "QPushButton { background-color: #064E3B; color: #6EE7B7; border: 1px solid #059669; "
                "border-radius: 8px; font-size: 12px; font-weight: 700; padding: 4px 14px; }"
            )
        elif all_claimed:
            self.lbl_bonus_title.setText("🌟 Tabriklaymiz! Barcha vazifalar bajarildi!")
            self.lbl_bonus_desc.setText(f"Kunlik Battle Pass super sovrini sizni kutmoqda! +{bonus_reward_xp} XP yig'ing.")
            self.btn_bonus_claim.setEnabled(True)
            self.btn_bonus_claim.setText(f"🎁 +{bonus_reward_xp} XP Olish")
            self.btn_bonus_claim.setStyleSheet(
                "QPushButton { background-color: #D97706; color: white; border: 1.5px solid #FCD34D; "
                "border-radius: 8px; font-size: 13px; font-weight: 800; padding: 4px 18px; } "
                "QPushButton:hover { background-color: #F59E0B; }"
            )
        else:
            self.lbl_bonus_title.setText("Kunlik Super Bonus (Battle Pass Tier)")
            self.lbl_bonus_desc.setText(f"3 ta vazifaning barchasini to'liq bajaring va +{bonus_reward_xp} XP Super Bonusi oling! ({claimed_count}/{total_count})")
            self.btn_bonus_claim.setEnabled(False)
            self.btn_bonus_claim.setText(f"🔒 Qulfda (+{bonus_reward_xp} XP)")
            self.btn_bonus_claim.setStyleSheet(
                "QPushButton { background-color: #24243A; color: #9CA3AF; border: 1px solid #374151; "
                "border-radius: 8px; font-size: 12px; font-weight: 600; padding: 4px 14px; }"
            )

    def _on_item_reward_claimed(self, res: dict):
        self.refresh()
        self.data_changed.emit()

    def _on_claim_super_bonus(self):
        res = daily_quests_service.claim_daily_bonus()
        if res.get("success"):
            sound_effects.play_milestone()
            self.refresh()
            self.data_changed.emit()

    def apply_theme(self, t: theme_manager.Theme):
        is_dark = getattr(t, "is_dark", True)
        bg = t.bg_card
        border = t.border
        self.setStyleSheet(
            f"DailyQuestsWidget {{ background-color: {bg}; border: 1.5px solid {border}; border-radius: 14px; }}"
        )
        self.lbl_header.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {t.text_main};")
        self.lbl_subtitle.setStyleSheet(f"font-size: 12px; color: {t.text_muted};")

        b_bg = "#1E1B4B" if is_dark else "#EEF2FF"
        b_fg = "#A5B4FC" if is_dark else "#4338CA"
        b_bd = "#4338CA" if is_dark else "#C7D2FE"
        self.badge_status.setStyleSheet(
            f"background-color: {b_bg}; color: {b_fg}; border: 1px solid {b_bd}; "
            f"border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 700;"
        )

        for card in self.quest_cards:
            card.apply_theme(t)
