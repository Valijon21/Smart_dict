"""
Vocab Master Pro — Tayyor So'z Paketlari (Word Packs) Modali.
Foydalanuvchiga saralangan so'z to'plamlarini ko'rsatadi va 1-bosish bilan bazaga yuklash imkonini beradi.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt

import database as db
import word_packs
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

        self.setWindowTitle("Tayyor Lug'at To'plamlari (Word Packs)")
        self.resize(760, 620)
        self.setStyleSheet(f"background-color: {t.bg_app}; color: {t.text_main};")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(16)

        # Header
        head_layout = QVBoxLayout()
        title = QLabel("📚 Tayyor Lug'at To'plamlari")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #FFFFFF;")
        head_layout.addWidget(title)

        subtitle = QLabel(
            "O'zingizga kerakli sohada eng ko'p ishlatiladigan so'zlarni bitta tugma bilan "
            "lug'atingizga qo'shing. Barcha so'zlar tarjimasi va misol gapi (example) bilan kiritiladi."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #9CA3AF; line-height: 1.4;")
        head_layout.addWidget(subtitle)
        root_layout.addLayout(head_layout)

        # Scroll area for pack cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setSpacing(14)

        self.pack_cards = {}
        for pack in word_packs.get_all_packs():
            card = self._create_pack_card(pack)
            self.cards_layout.addWidget(card)
            self.pack_cards[pack["id"]] = card

        self.cards_layout.addStretch()
        scroll.setWidget(container)
        root_layout.addWidget(scroll)

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

        # Top row: Title + Level badge
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

        # Word count pill
        count_lbl = QLabel(f"📊 {total_words} ta so'z")
        count_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: 600;")
        top_row.addWidget(count_lbl)
        card_layout.addLayout(top_row)

        # Description
        desc_lbl = QLabel(pack["description"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 13px; color: #C4C8D4;")
        card_layout.addWidget(desc_lbl)

        # Preview words sample
        samples = [f"<b>{w['english']}</b> ({w['uzbek']})" for w in pack["words"][:4]]
        preview_text = "💡 <i>Namunalar:</i> " + ", ".join(samples) + "..."
        prev_lbl = QLabel(preview_text)
        prev_lbl.setWordWrap(True)
        prev_lbl.setStyleSheet("font-size: 12px; color: #818CF8;")
        card_layout.addWidget(prev_lbl)

        # Action row
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
            # word_ids ni bazadan olamiz
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
