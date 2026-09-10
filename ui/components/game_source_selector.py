"""
Vocab Master Pro — Game Source Selector Component.
Barcha mini-o'yinlar (Word Match, Blitz, Word Fall, Crossword) uchun
universal, zamonaviy va temaga to'liq moslashuvchi to'plam tanlash vidjeti.
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal

try:
    from core import database as db
    from services import game_word_provider as gwp
    import theme_manager
    from utils.logger import get_logger
except ImportError:
    import database as db
    import game_word_provider as gwp
    import theme_manager
    from logger import get_logger

logger = get_logger("game_source_selector")


class GameSourceSelector(QFrame):
    """
    O'yinlar uchun universal mavzu va to'plam tanlagich vidjeti.
    Toifa (Shaxsiy, 36 ta mavzu, Tayyor to'plamlar, CEFR) va ichki to'plamni tanlash imkonini beradi.
    """
    # Signal: (category_id, source_id)
    source_changed = pyqtSignal(str, str)

    def __init__(self, game_id: str, parent=None):
        super().__init__(parent)
        self.game_id = game_id
        self._block_signals = False

        self._setup_ui()
        self._load_saved_selection()
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

    def _setup_ui(self):
        self.setObjectName("gameSourceSelector")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # 1. Yorliq
        self.lbl_title = QLabel("📚 Manba:")
        self.lbl_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #9CA3AF;")
        layout.addWidget(self.lbl_title)

        # 2. Toifa ComboBox (Shaxsiy, Mavzular, To'plamlar, CEFR)
        self.combo_category = QComboBox()
        self.combo_category.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_category.setMinimumWidth(150)
        for cat in gwp.get_available_categories():
            self.combo_category.addItem(f"{cat['icon']} {cat['title']}", cat["id"])
        self.combo_category.currentIndexChanged.connect(self._on_category_changed)
        layout.addWidget(self.combo_category)

        # 3. Ichki To'plam ComboBox
        self.combo_source = QComboBox()
        self.combo_source.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_source.setMinimumWidth(210)
        self.combo_source.currentIndexChanged.connect(self._on_source_changed)
        layout.addWidget(self.combo_source)

        # 4. So'zlar soni nishonchasi (Badge)
        self.lbl_count_badge = QLabel("0 ta so'z")
        self.lbl_count_badge.setStyleSheet(
            "background-color: #374151; color: #D1D5DB; border-radius: 6px; "
            "padding: 4px 10px; font-size: 11px; font-weight: 700;"
        )
        layout.addWidget(self.lbl_count_badge)

        layout.addStretch()

    def _load_saved_selection(self):
        """Oldingi sessiyadan saqlangan tanlovni tiklash."""
        self._block_signals = True
        saved_cat = db.get_setting(f"game_source_{self.game_id}_cat", gwp.CAT_PERSONAL)
        saved_src = db.get_setting(f"game_source_{self.game_id}_src", "all")

        # Toifani tanlash
        cat_idx = 0
        for i in range(self.combo_category.count()):
            if self.combo_category.itemData(i) == saved_cat:
                cat_idx = i
                break
        self.combo_category.setCurrentIndex(cat_idx)

        # To'plamlarni to'ldirish va tanlash
        self._populate_sources(saved_cat, preferred_source_id=saved_src)
        self._block_signals = False

    def _populate_sources(self, category_id: str, preferred_source_id: str | None = None):
        """Tanlangan toifaga ko'ra ichki to'plamlar ro'yxatini yuklash."""
        self.combo_source.blockSignals(True)
        self.combo_source.clear()

        sources = gwp.get_sources_for_category(category_id)
        selected_idx = 0

        for idx, s in enumerate(sources):
            self.combo_source.addItem(s["title"], s["id"])
            if preferred_source_id and s["id"] == preferred_source_id:
                selected_idx = idx

        if self.combo_source.count() > 0:
            self.combo_source.setCurrentIndex(selected_idx)
            self._update_badge_count()

        self.combo_source.blockSignals(False)

    def _on_category_changed(self, index: int):
        if self._block_signals:
            return
        cat_id = self.combo_category.currentData()
        if not cat_id:
            return

        db.set_setting(f"game_source_{self.game_id}_cat", str(cat_id))
        self._populate_sources(cat_id)
        self._emit_change()

    def _on_source_changed(self, index: int):
        if self._block_signals:
            return
        self._update_badge_count()
        cat_id = self.get_current_category()
        src_id = self.get_current_source_id()
        if cat_id and src_id:
            db.set_setting(f"game_source_{self.game_id}_src", str(src_id))
            self._emit_change()

    def _update_badge_count(self):
        """Hozirgi to'plamning so'zlar sonini yangilash."""
        cat_id = self.get_current_category()
        src_id = self.get_current_source_id()
        if not cat_id or not src_id:
            return

        sources = gwp.get_sources_for_category(cat_id)
        match = next((s for s in sources if s["id"] == src_id), None)
        if match:
            cnt = match.get("count", 0)
            self.lbl_count_badge.setText(f"🎯 {cnt} ta so'z")
        else:
            self.lbl_count_badge.setText("🎯 Faol")

    def _emit_change(self):
        cat_id = self.get_current_category()
        src_id = self.get_current_source_id()
        if cat_id and src_id:
            self.source_changed.emit(cat_id, src_id)

    def get_current_category(self) -> str:
        return self.combo_category.currentData() or gwp.CAT_PERSONAL

    def get_current_source_id(self) -> str:
        return self.combo_source.currentData() or "all"

    def get_current_source_title(self) -> str:
        return self.combo_source.currentText() or "Asosiy to'plam"

    def get_words(
        self,
        limit: int = 100,
        min_len: int = 0,
        max_len: int = 999,
        alpha_only: bool = False
    ) -> list[dict]:
        """Ushbu vidjetda hozir tanlangan to'plam so'zlarini qaytaradi."""
        cat_id = self.get_current_category()
        src_id = self.get_current_source_id()
        return gwp.get_words_for_game(
            category_id=cat_id,
            source_id=src_id,
            limit=limit,
            min_len=min_len,
            max_len=max_len,
            alpha_only=alpha_only
        )

    def set_enabled(self, enabled: bool):
        """O'yin boshlanganda o'zgartirishni bloklash uchun."""
        self.combo_category.setEnabled(enabled)
        self.combo_source.setEnabled(enabled)

    def apply_theme(self, t: theme_manager.Theme):
        """Vidjet ranglarini joriy temaga moslash."""
        self.setStyleSheet(
            f"#gameSourceSelector {{"
            f"  background-color: {t.bg_card};"
            f"  border: 1px solid {t.border};"
            f"  border-radius: 12px;"
            f"}}"
        )
        self.lbl_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {t.text_muted};")

        combo_style = (
            f"QComboBox {{"
            f"  background-color: {t.bg_card_secondary};"
            f"  color: {t.text_main};"
            f"  border: 1.5px solid {t.border};"
            f"  border-radius: 8px;"
            f"  padding: 5px 10px;"
            f"  font-size: 12px;"
            f"  font-weight: 600;"
            f"}}"
            f"QComboBox:hover {{"
            f"  border-color: {t.primary};"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: {t.bg_card};"
            f"  color: {t.text_main};"
            f"  selection-background-color: {t.primary};"
            f"  selection-color: #FFFFFF;"
            f"  border: 1px solid {t.border};"
            f"  border-radius: 8px;"
            f"  padding: 4px;"
            f"}}"
        )
        self.combo_category.setStyleSheet(combo_style)
        self.combo_source.setStyleSheet(combo_style)

        self.lbl_count_badge.setStyleSheet(
            f"background-color: {t.bg_card_secondary}; color: {t.primary_light}; "
            f"border: 1px solid {t.border}; border-radius: 6px; padding: 4px 10px; "
            f"font-size: 11px; font-weight: 700;"
        )
