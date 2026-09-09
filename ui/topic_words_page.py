"""
Vocab Master Pro — Topic Based Words Page.
36 ta tematik to'plamni 4 ustunlik kartalarda ko'rsatish, mavzular bo'yicha
so'zlarni o'rganish, qidirish, talaffuz qilish va trenajyorda mashq qilish interfeysi.
"""
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QGridLayout, QProgressBar, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QPixmap

import topic_service
import global_dict_service
import tts
import theme_manager
from logger import get_logger

from ui.dictionary import WordDetailsDialog

logger = get_logger("topic_words_page")

ROOT_DIR = Path(__file__).resolve().parent.parent



class TopicCardWidget(QFrame):
    """36 ta mavzu uchun 4 ustunlik gridda joylashuvchi zamonaviy karta."""
    clicked = pyqtSignal(str)

    def __init__(self, topic_data: dict, parent=None):
        super().__init__(parent)
        self.topic = topic_data
        self.topic_id = topic_data["id"]
        t = theme_manager.get_active_theme()

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("TopicCard")
        self.setFixedHeight(204)

        color = self.topic.get("color", "#6366F1")
        self.color = color

        self._default_style = (
            f"QFrame#TopicCard {{ "
            f"background-color: {t.bg_card}; border: 1px solid {t.border}; "
            f"border-radius: 14px; padding: 14px; }} "
            f"QFrame#TopicCard:hover {{ "
            f"border: 1.5px solid {color}; "
            f"background-color: {t.bg_card_secondary}; }}"
        )
        self.setStyleSheet(self._default_style)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Yuqori qator: Mavzu rasmi (Illustration) va so'zlar soni chipi
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Topic Rasmi
        img_path = ROOT_DIR / "assets" / "topics" / f"{self.topic_id}.png"
        self.icon_badge = QLabel()
        self.icon_badge.setFixedSize(54, 54)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if img_path.exists():
            pm = QPixmap(str(img_path)).scaled(
                54, 54,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.icon_badge.setPixmap(pm)
            self.icon_badge.setStyleSheet("background: transparent; border: none;")
        else:
            self.icon_badge.setText(self.topic.get("emoji", "📚"))
            self.icon_badge.setStyleSheet(
                f"background-color: {color}22; color: {color}; border: 1.5px solid {color}55; "
                f"border-radius: 14px; font-size: 24px;"
            )
        top_row.addWidget(self.icon_badge)

        top_row.addStretch()

        words_count = len(self.topic.get("words", []))
        self.count_badge = QLabel(f"{words_count} words")
        self.count_badge.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_muted}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 700;"
        )
        top_row.addWidget(self.count_badge)
        layout.addLayout(top_row)

        # Mavzu nomi va o'zbekcha tarjimasi
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.title_lbl = QLabel(self.topic.get("title", ""))
        self.title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 16px; font-weight: 700;")
        title_box.addWidget(self.title_lbl)

        uz_title = self.topic.get("title_uz", "")
        if uz_title:
            self.sub_title_lbl = QLabel(uz_title)
            self.sub_title_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;")
            title_box.addWidget(self.sub_title_lbl)
        else:
            self.sub_title_lbl = None

        layout.addLayout(title_box)

        # Qisqa tavsif
        desc = self.topic.get("description", "")
        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px; line-height: 1.35;")
        layout.addWidget(self.desc_lbl, 1)

        # Progress satri (foydalanuvchining shaxsiy o'rganish progressi)
        self.progress_row = QHBoxLayout()
        self.progress_row.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {t.bg_app}; border: none; border-radius: 2px; }} "
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 2px; }}"
        )
        self.progress_row.addWidget(self.progress_bar, 1)

        self.progress_lbl = QLabel("0/0")
        self.progress_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px; font-weight: 700;")
        self.progress_row.addWidget(self.progress_lbl)

        layout.addLayout(self.progress_row)

        self.update_progress()

    def apply_theme(self, t):
        """Mavzu ranglari o'zgarganda kartani yangilash."""
        self._default_style = (
            f"QFrame#TopicCard {{ "
            f"background-color: {t.bg_card}; border: 1px solid {t.border}; "
            f"border-radius: 14px; padding: 14px; }} "
            f"QFrame#TopicCard:hover {{ "
            f"border: 1.5px solid {self.color}; "
            f"background-color: {t.bg_card_secondary}; }}"
        )
        self.setStyleSheet(self._default_style)
        self.title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 16px; font-weight: 700;")
        if getattr(self, "sub_title_lbl", None):
            self.sub_title_lbl.setStyleSheet(f"color: {self.color}; font-size: 13px; font-weight: 600;")
        self.desc_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px; line-height: 1.35;")
        self.count_badge.setStyleSheet(
            f"background-color: {t.bg_app}; color: {t.text_muted}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 700;"
        )
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {t.bg_app}; border: none; border-radius: 2px; }} "
            f"QProgressBar::chunk {{ background-color: {self.color}; border-radius: 2px; }}"
        )
        self.progress_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px; font-weight: 700;")



    def update_progress(self):
        """Foydalanuvchining ushbu mavzuni o'zlashtirish progressini yangilash."""
        learned, total = topic_service.get_topic_progress(self.topic_id)
        if total > 0:
            pct = int((learned / total) * 100)
            self.progress_bar.setValue(pct)
            self.progress_lbl.setText(f"{learned}/{total}")
        else:
            self.progress_bar.setValue(0)
            self.progress_lbl.setText("0/0")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.topic_id)
        super().mousePressEvent(event)


class TopicWordsWidget(QWidget):
    """
    Topic Based Words — 36 ta tematik to'plamlar asosiy sahifasi.
    4 ustunlik kartalar paneli va har bir mavzuning to'liq o'rganish oynasi.
    """
    def __init__(self, parent=None, on_words_changed=None, on_start_practice=None):
        super().__init__(parent)
        self.on_words_changed = on_words_changed
        self.on_start_practice = on_start_practice

        self.current_topic_id = None
        self.topic_cards: list[TopicCardWidget] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        # Sahifalar almashtirgichi (0: Grid View, 1: Detail View)
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack)

        self.grid_page = self._build_grid_page()
        self.detail_page = self._build_detail_page()

        self.stack.addWidget(self.grid_page)
        self.stack.addWidget(self.detail_page)

        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

    def _build_grid_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        t = theme_manager.get_active_theme()

        # 1. Header paneli
        header_box = QVBoxLayout()
        header_box.setSpacing(4)

        title_lbl = QLabel("📚 Topic Based Words")
        title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 22px; font-weight: 800;")
        header_box.addWidget(title_lbl)

        sub_lbl = QLabel("Browse 36 themed collections of vocabulary to expand your English knowledge.")
        sub_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")
        header_box.addWidget(sub_lbl)

        layout.addLayout(header_box)

        # 2. Qidiruv va filtrlar paneli
        search_frame = QFrame()
        search_frame.setStyleSheet(
            f"background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 10px; padding: 6px 12px;"
        )
        s_lay = QHBoxLayout(search_frame)
        s_lay.setContentsMargins(6, 4, 6, 4)
        s_lay.setSpacing(10)

        s_icon = QLabel("🔍")
        s_icon.setStyleSheet("font-size: 15px;")
        s_lay.addWidget(s_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Mavzu nomi yoki so'zlarni qidiring (masalan: family, health, doctor)...")
        self.search_input.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {t.text_main}; border: none; font-size: 14px; }}"
        )
        self.search_input.textChanged.connect(self._filter_topics)
        s_lay.addWidget(self.search_input, 1)

        self.stats_lbl = QLabel("36 ta mavzu • 901 ta so'z")
        self.stats_lbl.setStyleSheet(
            f"background-color: {t.bg_app}; color: #818CF8; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 12.5px; font-weight: 700;"
        )
        s_lay.addWidget(self.stats_lbl)


        layout.addWidget(search_frame)

        # 3. 4 Ustunlik Kartalar Gridi (ScrollArea)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: transparent; }} "
            f"QScrollBar:vertical {{ background: {t.bg_card}; width: 8px; border-radius: 4px; }} "
            f"QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 4px; }}"
        )

        grid_container = QWidget()
        self.cards_grid = QGridLayout(grid_container)
        self.cards_grid.setContentsMargins(0, 6, 0, 6)
        self.cards_grid.setSpacing(14)

        topics = topic_service.get_all_topics()
        cols_count = 4

        for idx, topic in enumerate(topics):
            row = idx // cols_count
            col = idx % cols_count
            card = TopicCardWidget(topic)
            card.clicked.connect(self.open_topic_detail)
            self.cards_grid.addWidget(card, row, col)
            self.topic_cards.append(card)

        scroll.setWidget(grid_container)
        layout.addWidget(scroll, 1)

        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        t = theme_manager.get_active_theme()

        # 1. Navigatsiya paneli: Orqaga qaytish
        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("← Barcha mavzularga qaytish")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: {t.bg_card_secondary}; border-color: {t.primary}; }}"
        )
        self.btn_back.clicked.connect(self.back_to_grid)
        top_bar.addWidget(self.btn_back)
        top_bar.addStretch()

        self.btn_practice = QPushButton("🎯 Ushbu mavzuni mashq qilish")
        self.btn_practice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_practice.setStyleSheet(
            "QPushButton { background-color: #8B5CF6; color: white; border: none; "
            "border-radius: 8px; padding: 8px 18px; font-size: 12px; font-weight: 700; } "
            "QPushButton:hover { background-color: #7C3AED; }"
        )
        self.btn_practice.clicked.connect(self._practice_topic_words)
        top_bar.addWidget(self.btn_practice)

        self.btn_batch_add = QPushButton("➕ Barchasini rejaga qo'shish")
        self.btn_batch_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_batch_add.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; border: none; "
            "border-radius: 8px; padding: 8px 18px; font-size: 12px; font-weight: 700; } "
            "QPushButton:hover { background-color: #059669; }"
        )
        self.btn_batch_add.clicked.connect(self._batch_add_action)
        top_bar.addWidget(self.btn_batch_add)

        layout.addLayout(top_bar)

        # 2. Mavzu tafsilotlari kartasi
        self.detail_header_frame = QFrame()
        self.detail_header_frame.setStyleSheet(
            f"background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 14px; padding: 14px 18px;"
        )
        dh_lay = QHBoxLayout(self.detail_header_frame)
        dh_lay.setContentsMargins(12, 8, 12, 8)
        dh_lay.setSpacing(14)

        self.detail_img_lbl = QLabel()
        self.detail_img_lbl.setFixedSize(68, 68)
        self.detail_img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_img_lbl.setStyleSheet("background: transparent; border: none;")
        dh_lay.addWidget(self.detail_img_lbl)

        d_col = QVBoxLayout()
        d_col.setSpacing(4)
        self.detail_title_lbl = QLabel("Topic Title")
        self.detail_title_lbl.setStyleSheet(f"color: {t.text_main}; font-size: 20px; font-weight: 800;")
        d_col.addWidget(self.detail_title_lbl)

        self.detail_desc_lbl = QLabel("Topic description here...")
        self.detail_desc_lbl.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
        d_col.addWidget(self.detail_desc_lbl)
        dh_lay.addLayout(d_col, 1)

        self.detail_stat_lbl = QLabel("0 so'z")
        self.detail_stat_lbl.setStyleSheet(
            f"background-color: {t.bg_app}; color: #34D399; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 700;"
        )
        dh_lay.addWidget(self.detail_stat_lbl)

        layout.addWidget(self.detail_header_frame)

        # 3. So'zlar jadvali
        self.words_table = QTableWidget()
        self.words_table.setColumnCount(5)
        self.words_table.setHorizontalHeaderLabels([
            "Inglizcha (Talaffuz)", "O'zbekcha tarjima", "Misol gap", "Holat", "Amallar"
        ])
        self.words_table.setColumnWidth(0, 220)
        self.words_table.setColumnWidth(1, 240)
        self.words_table.setColumnWidth(3, 140)
        self.words_table.setColumnWidth(4, 130)

        header = self.words_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)

        self.words_table.verticalHeader().setVisible(False)
        self.words_table.verticalHeader().setDefaultSectionSize(54)

        self.words_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.words_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        layout.addWidget(self.words_table, 1)

        return page

    def open_topic_detail(self, topic_id: str):
        """Mavzu kartasi bosilganda tafsilotlar sahifasini ochish."""
        topic = topic_service.get_topic_by_id(topic_id)
        if not topic:
            return

        self.current_topic_id = topic_id
        color = topic.get("color", "#6366F1")

        img_path = ROOT_DIR / "assets" / "topics" / f"{topic_id}.png"
        if img_path.exists():
            pm = QPixmap(str(img_path)).scaled(
                68, 68,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.detail_img_lbl.setPixmap(pm)
            self.detail_img_lbl.setStyleSheet("background: transparent; border: none;")
        else:
            self.detail_img_lbl.setText(topic.get("emoji", "📚"))
            self.detail_img_lbl.setStyleSheet(
                f"background-color: {color}22; color: {color}; border: 1.5px solid {color}55; "
                f"border-radius: 18px; font-size: 28px;"
            )

        self.detail_title_lbl.setText(f"{topic.get('title')}  •  {topic.get('title_uz', '')}")
        self.detail_desc_lbl.setText(topic.get("description", ""))

        words_data = topic_service.get_topic_words_details(topic_id)
        learned, total = topic_service.get_topic_progress(topic_id)
        self.detail_stat_lbl.setText(f"{learned} / {total} ta o'rganilmoqda")

        self._populate_words_table(words_data)
        self.stack.setCurrentIndex(1)

    def back_to_grid(self):
        """Asosiy 36 ta mavzu kartalari sahifasiga qaytish."""
        for card in self.topic_cards:
            card.update_progress()
        self.stack.setCurrentIndex(0)

    def _populate_words_table(self, words: list[dict]):
        self.words_table.setRowCount(len(words))
        t = theme_manager.get_active_theme()

        for i, row in enumerate(words):
            eng = row["english"]

            # 0: English + Audio button
            cell_en = QWidget()
            lay_en = QHBoxLayout(cell_en)
            lay_en.setContentsMargins(8, 4, 8, 4)
            lay_en.setSpacing(8)

            btn_speak = QPushButton("🔊")
            btn_speak.setFixedSize(30, 30)
            btn_speak.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_speak.setStyleSheet(
                f"QPushButton {{ background-color: {t.bg_app}; color: {t.text_main}; "
                f"border: 1px solid {t.border}; border-radius: 6px; font-size: 13px; }} "
                f"QPushButton:hover {{ background-color: {t.primary}; color: white; }}"
            )
            btn_speak.clicked.connect(lambda checked, w=eng: tts.speak(w))
            lay_en.addWidget(btn_speak)

            col_en = QVBoxLayout()
            col_en.setSpacing(2)
            lbl_en = QLabel(eng)
            lbl_en.setStyleSheet(f"color: {t.text_main}; font-size: 15px; font-weight: 700;")
            col_en.addWidget(lbl_en)

            ph = row.get("phonetic", "")
            pos = row.get("pos", "")
            lbl_sub = QLabel(f"<span style='color: #A5B4FC; font-size: 12px; font-weight: 600;'>{ph}</span> <span style='color: #34D399; font-size: 12px; font-weight: 700;'>[{pos}]</span>")
            col_en.addWidget(lbl_sub)
            lay_en.addLayout(col_en, 1)

            self.words_table.setCellWidget(i, 0, cell_en)

            # 1: Uzbek translation
            cell_uz = QWidget()
            lay_uz = QVBoxLayout(cell_uz)
            lay_uz.setContentsMargins(8, 4, 8, 4)
            lay_uz.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            lbl_uz = QLabel(row.get("uzbek", ""))
            lbl_uz.setStyleSheet(f"color: {t.text_main}; font-size: 14px; font-weight: 600;")
            lbl_uz.setWordWrap(True)
            lay_uz.addWidget(lbl_uz)
            self.words_table.setCellWidget(i, 1, cell_uz)

            # 2: Example
            cell_ex = QWidget()
            lay_ex = QVBoxLayout(cell_ex)
            lay_ex.setContentsMargins(8, 4, 8, 4)
            lay_ex.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            ex = row.get("example", "")
            lbl_ex = QLabel(f"“{ex}”" if ex else "—")
            lbl_ex.setStyleSheet(f"color: {t.text_muted}; font-size: 13px; font-style: italic;")
            lbl_ex.setWordWrap(True)
            lay_ex.addWidget(lbl_ex)
            self.words_table.setCellWidget(i, 2, cell_ex)

            # 3: Status
            is_in = row.get("is_in_study_list", False)
            if is_in:
                b_lvl = row.get("box_level", 1)
                lbl_st = QLabel(f"✅ Box {b_lvl}")
                lbl_st.setStyleSheet(
                    "background-color: #064E3B; color: #6EE7B7; font-size: 12px; font-weight: 700; "
                    "border-radius: 6px; padding: 4px 8px;"
                )
            else:
                lbl_st = QLabel("Mavjud emas")
                lbl_st.setStyleSheet(
                    f"background-color: {t.bg_app}; color: {t.text_muted}; font-size: 12px; font-weight: 600; "
                    f"border-radius: 6px; padding: 4px 8px;"
                )
            lbl_st.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.words_table.setCellWidget(i, 3, lbl_st)


            # 4: Actions (Smart Insights 💡 + Quick Add ➕)
            cell_act = QWidget()
            lay_act = QHBoxLayout(cell_act)
            lay_act.setContentsMargins(4, 4, 4, 4)
            lay_act.setSpacing(6)
            lay_act.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_insights = QPushButton("💡")
            btn_insights.setToolTip("Kollokatsiyalar, farqlar va sinonimlar")
            btn_insights.setFixedSize(30, 30)
            btn_insights.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_insights.setStyleSheet(
                "QPushButton { background-color: #262040; color: #F59E0B; border: 1px solid #4D3D70;"
                "border-radius: 6px; font-size: 13px; }"
                "QPushButton:hover { background-color: #D97706; color: white; border-color: #FBBF24; }"
            )
            btn_insights.clicked.connect(lambda checked, w=eng: self._open_insights(w))
            lay_act.addWidget(btn_insights)

            if not is_in:
                btn_add = QPushButton("➕")
                btn_add.setToolTip("Shaxsiy o'rganish rejasiga qo'shish")
                btn_add.setFixedSize(30, 30)
                btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_add.setStyleSheet(
                    "QPushButton { background-color: #10B981; color: white; border: none; "
                    "border-radius: 6px; font-size: 13px; font-weight: 700; }"
                    "QPushButton:hover { background-color: #059669; }"
                )
                btn_add.clicked.connect(lambda checked, w=row, b=btn_add: self._add_single_word(w, b))
                lay_act.addWidget(btn_add)

            self.words_table.setCellWidget(i, 4, cell_act)

    def _open_insights(self, english: str):
        """So'zning Smart Insights oynasini ochish."""
        dlg = WordDetailsDialog(self, english, on_added=self._on_local_word_added)
        dlg.exec()

    def _add_single_word(self, word_data: dict, button: QPushButton):
        """Bitta so'zni 1-bosishda qo'shish."""
        eng = word_data["english"]
        uz = word_data.get("uzbek", "")
        ex = word_data.get("example", "")
        success, msg, _ = global_dict_service.add_to_study_list(eng, uz, ex)
        if success:
            button.setText("✅")
            button.setEnabled(False)
            button.setStyleSheet(
                "QPushButton { background-color: #065F46; color: #A7F3D0; border: none; border-radius: 6px; }"
            )
            self._on_local_word_added()
            QMessageBox.information(self, "Muvaffaqiyatli", f"'{eng}' o'rganish rejangizga qo'shildi!")
        else:
            QMessageBox.information(self, "Ma'lumot", msg)

    def _batch_add_action(self):
        """Mavzudagi barcha yangi so'zlarni bir vaqtda qo'shish."""
        if not self.current_topic_id:
            return

        added, total = topic_service.batch_add_topic_to_study(self.current_topic_id)
        self._on_local_word_added()
        # Jadvalni yangilash
        words_data = topic_service.get_topic_words_details(self.current_topic_id)
        self._populate_words_table(words_data)

        learned, total_cnt = topic_service.get_topic_progress(self.current_topic_id)
        self.detail_stat_lbl.setText(f"{learned} / {total_cnt} ta o'rganilmoqda")

        QMessageBox.information(
            self, "To'plam qo'shildi",
            f"Mavzudan {added} ta yangi so'z shaxsiy o'rganish rejangizga muvaffaqiyatli qo'shildi!"
        )

    def _practice_topic_words(self):
        """Mavzudagi so'zlarni mashq qilishga yuborish."""
        if not self.current_topic_id:
            return

        words_data = topic_service.get_topic_words_details(self.current_topic_id)
        word_ids = []

        for item in words_data:
            local_id = item.get("local_id")
            if not local_id:
                success, _, new_id = global_dict_service.add_to_study_list(
                    english=item["english"],
                    uzbek=item["uzbek"],
                    example=item["example"]
                )
                if success and new_id > 0:
                    word_ids.append(new_id)
            else:
                word_ids.append(local_id)

        self._on_local_word_added()

        if self.on_start_practice and word_ids:
            logger.info(f"Mavzu trenajyoriga yuborildi: {self.current_topic_id} ({len(word_ids)} ta so'z)")
            self.on_start_practice(word_ids)
        else:
            QMessageBox.information(
                self, "Mashq boshlash",
                f"'{self.detail_title_lbl.text()}' to'plamidagi {len(word_ids)} ta so'z mashqqa tayyorlandi!"
            )

    def _on_local_word_added(self):
        if self.on_words_changed:
            self.on_words_changed()

    def _filter_topics(self, text: str):
        """36 ta mavzuni qidiruv matniga qarab filtrlash."""
        query = text.strip().lower()
        visible_count = 0

        for card in self.topic_cards:
            topic = card.topic
            title = topic.get("title", "").lower()
            desc = topic.get("description", "").lower()
            words = [w.lower() for w in topic.get("words", [])]

            matches = not query or query in title or query in desc or any(query in w for w in words)
            card.setVisible(matches)
            if matches:
                visible_count += 1

        self.stats_lbl.setText(f"{visible_count} ta mavzu topildi")

    def apply_theme(self, t: theme_manager.Theme):
        """Mavzu ranglarini qo'llash."""
        self.setStyleSheet(f"background-color: {t.bg_app}; color: {t.text_main};")
        if hasattr(self, "words_table"):
            self.words_table.setStyleSheet(
                f"""
                QTableWidget {{
                    background-color: {t.bg_sidebar};
                    alternate-background-color: {t.bg_card_secondary};
                    color: {t.text_main};
                    gridline-color: {t.border};
                    border: 1px solid {t.border};
                    border-radius: 12px;
                    font-size: 13px;
                }}
                QHeaderView::section {{
                    background-color: {t.bg_card};
                    color: {t.text_muted};
                    font-size: 12px;
                    font-weight: 700;
                    padding: 8px;
                    border: none;
                    border-bottom: 2px solid {t.border};
                }}
                """
            )
        for card in self.topic_cards:
            card.apply_theme(t)

