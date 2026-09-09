"""
Vocab Master Pro — Tayyor So'z Paketlari (Word Packs) & CEFR / IELTS Modali.
Foydalanuvchiga saralangan so'z to'plamlarini va xalqaro CEFR (A1-C2) hamda
IELTS Academic (AWL) darajalaridagi 64,000 so'zlik bazadan 1-bosish bilan
shaxsiy lug'atga import qilish va mashq qilish imkonini beradi.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QMessageBox, QStackedWidget
)
from PyQt6.QtCore import Qt

import database as db
import word_packs
import cefr_service
import theme_manager
from logger import get_logger

logger = get_logger("word_packs_ui")


class WordPacksDialog(QDialog):
    def __init__(self, parent=None, on_words_imported=None, on_start_practice=None):
        super().__init__(parent)
        self.on_words_imported = on_words_imported
        self.on_start_practice = on_start_practice
        self.imported_counts = db.get_imported_pack_counts()
        self.newly_imported_ids = []
        t = theme_manager.get_active_theme()

        self.setWindowTitle("Tayyor Lug'at To'plamlari & CEFR / IELTS Darajalari")
        self.resize(800, 650)
        self.setStyleSheet(f"background-color: {t.bg_app}; color: {t.text_main};")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(14)

        # Header
        head_layout = QVBoxLayout()
        title = QLabel("📚 Tayyor Lug'at To'plamlari & CEFR / IELTS")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #FFFFFF;")
        head_layout.addWidget(title)

        subtitle = QLabel(
            "O'zingizga kerakli sohada eng ko'p ishlatiladigan so'zlarni yoki xalqaro CEFR (A1-C2) "
            "va IELTS Academic darajalarini bitta tugma bilan lug'atingizga qo'shing."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #9CA3AF; line-height: 1.4;")
        head_layout.addWidget(subtitle)
        root_layout.addLayout(head_layout)

        # Segmented Tabs Header: [🌟 Mavzuli to'plamlar] [🎯 CEFR & IELTS Darajalari]
        tabs_bar = QHBoxLayout()
        tabs_bar.setSpacing(10)

        self.btn_tab_general = QPushButton("🌟 Mavzuli To'plamlar (General & IT)")
        self.btn_tab_general.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tab_general.setStyleSheet(self._tab_btn_style(True))
        self.btn_tab_general.clicked.connect(lambda: self._switch_tab(0))
        tabs_bar.addWidget(self.btn_tab_general)

        self.btn_tab_cefr = QPushButton("🎯 CEFR (A1–C2) & IELTS Academic (64k Baza)")
        self.btn_tab_cefr.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tab_cefr.setStyleSheet(self._tab_btn_style(False))
        self.btn_tab_cefr.clicked.connect(lambda: self._switch_tab(1))
        tabs_bar.addWidget(self.btn_tab_cefr)

        tabs_bar.addStretch()
        root_layout.addLayout(tabs_bar)

        # Stacked Pages
        self.stack = QStackedWidget()

        # TAB 1: General Pre-made Packs
        scroll_general = QScrollArea()
        scroll_general.setWidgetResizable(True)
        scroll_general.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container_general = QWidget()
        self.cards_layout = QVBoxLayout(container_general)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setSpacing(14)

        self.pack_cards = {}
        for pack in word_packs.get_all_packs():
            card = self._create_pack_card(pack)
            self.cards_layout.addWidget(card)
            self.pack_cards[pack["id"]] = card

        self.cards_layout.addStretch()
        scroll_general.setWidget(container_general)
        self.stack.addWidget(scroll_general)

        # TAB 2: CEFR & IELTS Packs
        scroll_cefr = QScrollArea()
        scroll_cefr.setWidgetResizable(True)
        scroll_cefr.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container_cefr = QWidget()
        self.cefr_cards_layout = QVBoxLayout(container_cefr)
        self.cefr_cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cefr_cards_layout.setSpacing(14)

        self._build_cefr_cards()
        self.cefr_cards_layout.addStretch()
        scroll_cefr.setWidget(container_cefr)
        self.stack.addWidget(scroll_cefr)

        root_layout.addWidget(self.stack, 1)

        # Bottom row
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        close_btn = QPushButton("Yopish")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background-color: #262638; color: #E5E7EB; border: 1px solid #374151;"
            "border-radius: 8px; padding: 10px 24px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #374151; color: white; }"
        )
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        root_layout.addLayout(bottom_row)

    def _tab_btn_style(self, active: bool) -> str:
        t = theme_manager.get_active_theme()
        if active:
            return (
                f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
                f"border-radius: 8px; padding: 8px 18px; font-size: 13px; font-weight: 700; }}"
            )
        return (
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_muted}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 18px; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; }}"
        )

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        self.btn_tab_general.setStyleSheet(self._tab_btn_style(index == 0))
        self.btn_tab_cefr.setStyleSheet(self._tab_btn_style(index == 1))

    def _create_pack_card(self, pack: dict) -> QFrame:
        pack_id = pack["id"]
        total_words = len(pack["words"])
        already_count = self.imported_counts.get(pack_id, 0)

        card = QFrame()
        t = theme_manager.get_active_theme()
        card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border-radius: 14px; border: 1px solid {t.border}; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        top_row = QHBoxLayout()
        title_lbl = QLabel(pack["title"])
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF;")
        top_row.addWidget(title_lbl)

        level_badge = QLabel(f" {pack['level']} ")
        badge_bg = pack.get("badge_color", "#4F46E5")
        level_badge.setStyleSheet(
            f"background-color: {badge_bg}22; color: {badge_bg}; border: 1px solid {badge_bg}88;"
            f"border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
        )
        top_row.addWidget(level_badge)
        top_row.addStretch()

        count_lbl = QLabel(f"📊 {total_words} ta so'z")
        count_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: 600;")
        top_row.addWidget(count_lbl)
        card_layout.addLayout(top_row)

        desc_lbl = QLabel(pack["description"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 13px; color: #C4C8D4;")
        card_layout.addWidget(desc_lbl)

        samples = [f"<b>{w['english']}</b> ({w['uzbek']})" for w in pack["words"][:4]]
        prev_lbl = QLabel("💡 <i>Namunalar:</i> " + ", ".join(samples) + "...")
        prev_lbl.setWordWrap(True)
        prev_lbl.setStyleSheet("font-size: 12px; color: #818CF8;")
        card_layout.addWidget(prev_lbl)

        act_row = QHBoxLayout()
        status_lbl = QLabel()
        if already_count >= total_words:
            status_lbl.setText(f"✅ Barchasi lug'atda mavjud ({already_count} ta)")
            status_lbl.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 600;")
        elif already_count > 0:
            status_lbl.setText(f"⏳ {already_count} / {total_words} ta yuklangan")
            status_lbl.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: 600;")
        else:
            status_lbl.setText("Hali yuklanmagan")
            status_lbl.setStyleSheet("color: #6B7280; font-size: 12px;")
        act_row.addWidget(status_lbl)
        act_row.addStretch()

        import_btn = QPushButton("📥 Lug'atga yuklash")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border-radius: 8px;"
            "padding: 8px 18px; font-size: 13px; font-weight: 600; border: none; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        import_btn.clicked.connect(lambda _, p=pack, s=status_lbl, b=import_btn: self._import_pack(p, s, b))
        act_row.addWidget(import_btn)

        card_layout.addLayout(act_row)
        return card

    def _build_cefr_cards(self):
        """CEFR (A1-C2) va IELTS kartalarini yaratish."""
        summaries = cefr_service.get_cefr_levels_summary()
        t = theme_manager.get_active_theme()

        for s in summaries:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {t.bg_card}; border-radius: 14px; border: 1px solid {t.border}; }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 16, 20, 16)
            card_layout.setSpacing(12)

            top_row = QHBoxLayout()
            title_lbl = QLabel(s["title"])
            title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF;")
            top_row.addWidget(title_lbl)

            color = s.get("badge_color", "#10B981")
            level_badge = QLabel(f" {s['level']} ")
            level_badge.setStyleSheet(
                f"background-color: {color}22; color: {color}; border: 1px solid {color}88;"
                f"border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
            )
            top_row.addWidget(level_badge)
            top_row.addStretch()

            count_lbl = QLabel(f"📊 {s['total_words']:,} ta so'z")
            count_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: 600;")
            top_row.addWidget(count_lbl)
            card_layout.addLayout(top_row)

            desc_lbl = QLabel(s["description"])
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("font-size: 13px; color: #C4C8D4;")
            card_layout.addWidget(desc_lbl)

            # Namunalar
            sample_strs = [f"<b>{item['english']}</b> ({item['uzbek']})" for item in s.get("samples", [])]
            prev_lbl = QLabel("💡 <i>Namunalar:</i> " + ", ".join(sample_strs) + "...")
            prev_lbl.setWordWrap(True)
            prev_lbl.setStyleSheet("font-size: 12px; color: #A5B4FC;")
            card_layout.addWidget(prev_lbl)

            # Amallar qatori
            act_row = QHBoxLayout()
            status_lbl = QLabel(f"⏳ {s['already_imported']} / {s['total_words']} ta lug'atingizda bor")
            status_lbl.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: 600;")
            act_row.addWidget(status_lbl)
            act_row.addStretch()

            btn_25 = QPushButton("📥 25 ta")
            btn_25.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_25.setStyleSheet(self._cefr_btn_style(color))
            btn_25.clicked.connect(lambda _, lid=s["id"], title=s["title"], sl=status_lbl: self._import_cefr_action(lid, 25, title, sl))
            act_row.addWidget(btn_25)

            btn_50 = QPushButton("📥 50 ta")
            btn_50.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_50.setStyleSheet(self._cefr_btn_style(color))
            btn_50.clicked.connect(lambda _, lid=s["id"], title=s["title"], sl=status_lbl: self._import_cefr_action(lid, 50, title, sl))
            act_row.addWidget(btn_50)

            btn_100 = QPushButton("📥 100 ta")
            btn_100.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_100.setStyleSheet(self._cefr_btn_style(color))
            btn_100.clicked.connect(lambda _, lid=s["id"], title=s["title"], sl=status_lbl: self._import_cefr_action(lid, 100, title, sl))
            act_row.addWidget(btn_100)

            card_layout.addLayout(act_row)
            self.cefr_cards_layout.addWidget(card)

    def _cefr_btn_style(self, color: str) -> str:
        return (
            f"QPushButton {{ background-color: {color}22; color: {color}; border: 1px solid {color}88; "
            f"border-radius: 8px; padding: 6px 14px; font-size: 12px; font-weight: 700; }} "
            f"QPushButton:hover {{ background-color: {color}; color: white; }}"
        )

    def _import_cefr_action(self, level_id: str, count: int, title: str, status_lbl: QLabel):
        added, total = cefr_service.import_cefr_words_to_study(level_id, count=count)
        now_count = cefr_service.get_imported_count_for_level(level_id)
        status_lbl.setText(f"✅ {now_count} / {total} ta lug'atingizda bor")

        if self.on_words_imported:
            self.on_words_imported()

        QMessageBox.information(
            self,
            "Yuklandi",
            f"🎉 <b>{title}</b> to'plamidan <b>{added} ta</b> yangi so'z "
            f"shaxsiy lug'atingizga muvaffaqiyatli qo'shildi!"
        )

    def _import_pack(self, pack: dict, status_lbl: QLabel, import_btn: QPushButton):
        pack_id = pack["id"]
        words = pack["words"]

        summary = db.bulk_import_pack(pack_id, words)
        added = summary.get("added", 0)
        duplicates = summary.get("duplicates", 0)
        new_ids = summary.get("word_ids", [])
        self.newly_imported_ids.extend(new_ids)

        self.imported_counts = db.get_imported_pack_counts()
        total_now = self.imported_counts.get(pack_id, len(words))

        status_lbl.setText(f"✅ Muvaffaqiyatli yuklandi ({total_now} ta)")
        status_lbl.setStyleSheet("color: #10B981; font-size: 12px; font-weight: 700;")
        import_btn.setText("✅ Yuklandi")
        import_btn.setEnabled(False)
        import_btn.setStyleSheet(
            "background-color: #064E3B; color: #34D399; border-radius: 8px; padding: 8px 18px; font-size: 13px; font-weight: 600;"
        )

        logger.info(f"Paket yuklandi: {pack['title']} — {added} yangi so'z, {duplicates} dublikat")

        if self.on_words_imported:
            self.on_words_imported()

        msg = (
            f"🎉 <b>{pack['title']}</b> muvaffaqiyatli yuklandi!\n\n"
            f"• Qo'shilgan yangi so'zlar: <b>{added} ta</b>\n"
            f"• Allaqachon mavjud bo'lgan: <b>{duplicates} ta</b>\n\n"
            f"Ushbu so'zlarni hoziroq mashq qilasizmi?"
        )
        reply = QMessageBox.question(
            self,
            "To'plam yuklandi",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            all_pack_words = [w["english"] for w in words]
            with db.get_conn() as conn:
                placeholders = ",".join("?" for _ in all_pack_words)
                found = conn.execute(
                    f"SELECT id FROM words WHERE english IN ({placeholders})",
                    tuple(all_pack_words)
                ).fetchall()
                target_ids = [r["id"] for r in found]

            if target_ids and self.on_start_practice:
                self.accept()
                self.on_start_practice(target_ids, "en_uz")
