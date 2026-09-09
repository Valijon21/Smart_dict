import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QSpinBox, QPushButton, QScrollArea, QGridLayout,
    QLineEdit
)
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath

import database as db
import gamification
import theme_manager
import tts
import global_dict_service
from ui.achievements_dialog import AchievementsDialog
from logger import get_logger

logger = get_logger("dashboard")


class WeeklyChartWidget(QFrame):
    """So'nggi 7 kunlik mashqlar uchun toza PyQt6 QPainter grafik vidjeti."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.setMinimumHeight(220)
        self.grid_color = QColor("#26263A")
        self.title_color = QColor("white")
        self.text_color = QColor("#9CA3AF")
        t = theme_manager.get_active_theme()
        self.apply_theme(t)

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        self.grid_color = QColor(t.border)
        self.title_color = QColor(t.text_main)
        self.text_color = QColor(t.text_muted)
        self.update()

    def set_data(self, last7: list):
        self.data = last7
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # 1. Sarlavha
        painter.setPen(self.title_color)
        font_title = QFont()
        font_title.setPointSize(11)
        font_title.setBold(True)
        painter.setFont(font_title)
        painter.drawText(20, 28, "So'nggi 7 kunlik mashqlar")

        # 2. Legend (To'g'ri - Yashil, Xato - Qizil)
        legend_x = max(w - 190, 220)
        painter.setBrush(QBrush(QColor("#10B981")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(legend_x), 18, 10, 10)
        painter.setPen(self.text_color)
        font_sm = QFont()
        font_sm.setPointSize(9)
        painter.setFont(font_sm)
        painter.drawText(int(legend_x + 16), 27, "To'g'ri")

        painter.setBrush(QBrush(QColor("#EF4444")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(legend_x + 80), 18, 10, 10)
        painter.setPen(self.text_color)
        painter.drawText(int(legend_x + 96), 27, "Xato")

        # 3. Ustunlar maydoni
        chart_top = 52
        chart_bottom = h - 35
        chart_height = chart_bottom - chart_top
        chart_left = 25
        chart_right = w - 25
        chart_width = chart_right - chart_left

        # Gorizontal chiziqlar (grid)
        pen_grid = QPen(self.grid_color)
        pen_grid.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen_grid)
        for i in range(4):
            y_line = chart_top + (chart_height * i) / 3
            painter.drawLine(int(chart_left), int(y_line), int(chart_right), int(y_line))

        if not self.data:
            return

        totals = [r.get("correct", 0) + r.get("wrong", 0) for r in self.data]
        max_val = max(max(totals, default=0), 5)

        n = len(self.data)
        col_width = chart_width / max(n, 1)
        bar_width = min(max(col_width * 0.45, 18), 38)

        for i, r in enumerate(self.data):
            c_val = r.get("correct", 0)
            w_val = r.get("wrong", 0)
            tot = c_val + w_val

            cx = chart_left + col_width * i + col_width / 2
            bx = cx - bar_width / 2

            h_correct = (c_val / max_val) * (chart_height - 20)
            h_wrong = (w_val / max_val) * (chart_height - 20)

            # Sana yorlig'i
            date_str = r.get("date", "")
            label = date_str[5:].replace("-", ".") if len(date_str) >= 10 else str(i + 1)
            painter.setPen(self.text_color)
            painter.setFont(font_sm)
            painter.drawText(QRectF(cx - 30, chart_bottom + 6, 60, 20), Qt.AlignmentFlag.AlignCenter, label)

            # To'g'ri (yashil) ustun
            if h_correct > 0:
                y_c = chart_bottom - h_correct
                path_c = QPainterPath()
                r_top = 4 if h_wrong == 0 else 0
                path_c.addRoundedRect(QRectF(bx, y_c, bar_width, h_correct), r_top, r_top)
                painter.fillPath(path_c, QBrush(QColor("#10B981")))

            # Xato (qizil) ustun
            if h_wrong > 0:
                y_w = chart_bottom - h_correct - h_wrong
                path_w = QPainterPath()
                path_w.addRoundedRect(QRectF(bx, y_w, bar_width, h_wrong), 4, 4)
                painter.fillPath(path_w, QBrush(QColor("#EF4444")))

            # Ustun tepasidagi son
            if tot > 0:
                y_tot = chart_bottom - h_correct - h_wrong - 16
                painter.setPen(self.title_color)
                font_num = QFont()
                font_num.setPointSize(8)
                font_num.setBold(True)
                painter.setFont(font_num)
                painter.drawText(QRectF(cx - 20, y_tot, 40, 16), Qt.AlignmentFlag.AlignCenter, str(tot))


class BoxChartWidget(QFrame):
    """Leitner Box taqsimoti uchun toza PyQt6 QPainter grafik vidjeti."""
    BOX_COLORS = ["#6B7280", "#3B82F6", "#8B5CF6", "#F59E0B", "#10B981", "#059669"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {i: 0 for i in range(6)}
        self.setMinimumHeight(220)
        self.grid_color = QColor("#26263A")
        self.title_color = QColor("white")
        self.text_color = QColor("#9CA3AF")
        t = theme_manager.get_active_theme()
        self.apply_theme(t)

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        self.grid_color = QColor(t.border)
        self.title_color = QColor(t.text_main)
        self.text_color = QColor(t.text_muted)
        self.update()

    def set_data(self, box_dist: dict):
        self.data = {i: box_dist.get(i, 0) for i in range(6)}
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # 1. Sarlavha
        painter.setPen(self.title_color)
        font_title = QFont()
        font_title.setPointSize(11)
        font_title.setBold(True)
        painter.setFont(font_title)
        painter.drawText(20, 28, "Leitner Darajalari taqsimoti")

        chart_top = 52
        chart_bottom = h - 35
        chart_height = chart_bottom - chart_top
        chart_left = 25
        chart_right = w - 25
        chart_width = chart_right - chart_left

        # Grid chiziqlari
        pen_grid = QPen(self.grid_color)
        pen_grid.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen_grid)
        for i in range(4):
            y_line = chart_top + (chart_height * i) / 3
            painter.drawLine(int(chart_left), int(y_line), int(chart_right), int(y_line))

        counts = [self.data.get(i, 0) for i in range(6)]
        max_val = max(max(counts, default=0), 5)

        col_width = chart_width / 6
        bar_width = min(max(col_width * 0.5, 20), 42)

        font_sm = QFont()
        font_sm.setPointSize(9)

        font_num = QFont()
        font_num.setPointSize(8)
        font_num.setBold(True)

        for i in range(6):
            cnt = counts[i]
            color = QColor(self.BOX_COLORS[i])

            cx = chart_left + col_width * i + col_width / 2
            bx = cx - bar_width / 2
            bar_h = (cnt / max_val) * (chart_height - 20)

            # Ustun
            if bar_h > 0:
                by = chart_bottom - bar_h
                path = QPainterPath()
                path.addRoundedRect(QRectF(bx, by, bar_width, bar_h), 5, 5)
                painter.fillPath(path, QBrush(color))

                # Son yorlig'i
                painter.setPen(QColor("white"))
                painter.setFont(font_num)
                painter.drawText(QRectF(cx - 20, by - 16, 40, 16), Qt.AlignmentFlag.AlignCenter, str(cnt))
            else:
                painter.setPen(QColor(color.red(), color.green(), color.blue(), 100))
                painter.drawLine(int(bx), int(chart_bottom), int(bx + bar_width), int(chart_bottom))

            # Box yorlig'i
            painter.setPen(QColor("#9CA3AF"))
            painter.setFont(font_sm)
            painter.drawText(QRectF(cx - 30, chart_bottom + 6, 60, 20), Qt.AlignmentFlag.AlignCenter, f"Box {i}")


class ActivityHeatmapWidget(QFrame):
    """GitHub uslubidagi 365 kunlik (52 hafta) mashqlar faollik xaritasi (Heatmap)."""
    HEAT_COLORS = ["#1F2937", "#065F46", "#059669", "#10B981", "#34D399"]
    DAYS = ["Dush", "Chor", "Juma"]
    MONTHS = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.heatmap_data: dict[str, int] = {}
        self.cell_rects = []
        self.hover_info = ""
        self.setMinimumHeight(175)
        self.setMouseTracking(True)
        self.title_color = QColor("white")
        self.text_color = QColor("#9CA3AF")
        t = theme_manager.get_active_theme()
        self.apply_theme(t)

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        self.title_color = QColor(t.text_main)
        self.text_color = QColor(t.text_muted)
        self.update()

    def set_data(self, data: dict[str, int]):
        self.heatmap_data = data
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Sarlavha
        painter.setPen(self.title_color)
        font_title = QFont()
        font_title.setPointSize(11)
        font_title.setBold(True)
        painter.setFont(font_title)
        painter.drawText(20, 26, "Yillik Mashqlar Faolligi (Activity Heatmap)")

        # Hover info
        font_sm = QFont()
        font_sm.setPointSize(9)
        painter.setFont(font_sm)
        painter.setPen(self.text_color)
        if self.hover_info:
            painter.drawText(w - 240, 26, self.hover_info)

        # 52 hafta x 7 kun katakchalari
        cols = 52
        rows = 7
        tile_size = 11.0
        gap = 3.0
        start_x = 44.0
        start_y = 48.0

        # Hafta kunlari
        painter.setPen(self.text_color)
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(4, start_y + 1 * (tile_size + gap) - 2, 34, 14), Qt.AlignmentFlag.AlignRight, "Dush")
        painter.drawText(QRectF(4, start_y + 3 * (tile_size + gap) - 2, 34, 14), Qt.AlignmentFlag.AlignRight, "Chor")
        painter.drawText(QRectF(4, start_y + 5 * (tile_size + gap) - 2, 34, 14), Qt.AlignmentFlag.AlignRight, "Juma")

        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=cols * 7)
        curr_date = start_date
        self.cell_rects = []

        for c in range(cols):
            # Oy nomi
            if curr_date.day <= 7:
                m_idx = curr_date.month - 1
                painter.setPen(self.text_color)
                painter.drawText(int(start_x + c * (tile_size + gap)), int(start_y - 8), self.MONTHS[m_idx])

            for r in range(rows):
                date_str = curr_date.isoformat()
                count = self.heatmap_data.get(date_str, 0)

                if count == 0:
                    color = QColor(self.HEAT_COLORS[0])
                elif count <= 4:
                    color = QColor(self.HEAT_COLORS[1])
                elif count <= 10:
                    color = QColor(self.HEAT_COLORS[2])
                elif count <= 20:
                    color = QColor(self.HEAT_COLORS[3])
                else:
                    color = QColor(self.HEAT_COLORS[4])

                x = start_x + c * (tile_size + gap)
                y = start_y + r * (tile_size + gap)
                rect = QRectF(x, y, tile_size, tile_size)
                self.cell_rects.append((rect, date_str, count))

                path = QPainterPath()
                path.addRoundedRect(rect, 2.5, 2.5)
                painter.fillPath(path, QBrush(color))

                curr_date += datetime.timedelta(days=1)

        # Legend: Kam [■ ■ ■ ■ ■] Ko'p
        leg_x = w - 180
        leg_y = h - 22
        painter.setPen(self.text_color)
        painter.drawText(int(leg_x - 32), int(leg_y + 9), "Kam")
        for i, col_hex in enumerate(self.HEAT_COLORS):
            bx = leg_x + i * 14
            path = QPainterPath()
            path.addRoundedRect(QRectF(bx, leg_y, 10, 10), 2.0, 2.0)
            painter.fillPath(path, QBrush(QColor(col_hex)))
        painter.drawText(int(leg_x + 5 * 14 + 6), int(leg_y + 9), "Ko'p")

    def mouseMoveEvent(self, event):
        pos = event.position()
        found = False
        if hasattr(self, "cell_rects"):
            for rect, date_str, count in self.cell_rects:
                if rect.contains(pos):
                    self.hover_info = f"📅 {date_str}: {count} ta so'z"
                    self.setToolTip(f"{date_str}: {count} ta so'z mashq qilingan")
                    self.update()
                    found = True
                    break
        if not found and self.hover_info:
            self.hover_info = ""
            self.update()
        super().mouseMoveEvent(event)


def _stat_card(title: str, val_label: QLabel, color: str = "#4F46E5", t: theme_manager.Theme = None) -> QFrame:
    if t is None:
        t = theme_manager.get_active_theme()
    frame = QFrame()
    frame._accent_color = color
    frame.setStyleSheet(
        f"""
        QFrame {{
            background-color: {t.bg_card};
            border-radius: 12px;
            border: 1px solid {t.border};
            border-left: 4px solid {color};
        }}
        """
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    val_label.setStyleSheet(f"color: {t.text_main}; font-size: 26px; font-weight: 700;")
    title_label = QLabel(title)
    title_label.setStyleSheet(f"color: {t.text_muted}; font-size: 13px; font-weight: 600;")
    frame._val_label = val_label
    frame._title_label = title_label
    layout.addWidget(val_label)
    layout.addWidget(title_label)
    return frame


class DashboardWidget(QWidget):
    def __init__(self, on_navigate=None, on_goal_changed=None, on_start_practice=None):
        super().__init__()
        self.on_navigate = on_navigate
        self.on_goal_changed = on_goal_changed
        self.on_start_practice = on_start_practice

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.layout_root = QVBoxLayout(self.scroll_content)
        self.layout_root.setContentsMargins(24, 24, 24, 24)
        self.layout_root.setSpacing(16)
        self.scroll.setWidget(self.scroll_content)
        outer_layout.addWidget(self.scroll)

        header_row = QHBoxLayout()
        header = QLabel("Dashboard")
        header.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        header_row.addWidget(header)
        header_row.addStretch()

        # Gamifikatsiya: Daraja, XP va Yutuqlar tugmasi
        self.level_badge = QLabel("🟢 1-Daraja: Boshlovchi")
        self.level_badge.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; border: 1px solid #4338CA; "
            "border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 700;"
        )
        header_row.addWidget(self.level_badge)

        self.xp_badge = QLabel("⭐ 0 XP")
        self.xp_badge.setStyleSheet(
            "background-color: #2D2006; color: #FBBF24; border: 1px solid #B45309; "
            "border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 700;"
        )
        header_row.addWidget(self.xp_badge)

        self.achievements_btn = QPushButton("🏆 Yutuqlar (Badges)")
        self.achievements_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.achievements_btn.setStyleSheet(
            "QPushButton { background-color: #312E81; color: #C7D2FE; border: 1px solid #4338CA; "
            "border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #4338CA; color: white; }"
        )
        self.achievements_btn.clicked.connect(self._open_achievements)
        header_row.addWidget(self.achievements_btn)
        self.layout_root.addLayout(header_row)

        # =====================================================================
        # 🔍 UNIVERSAL SMART SEARCH (Hero Search Command Center)
        # 100% aniqlikdagi ikki tomonlama qidiruv (Inglizcha ↔ O'zbekcha)
        # =====================================================================
        self.search_container = QFrame()
        self.search_container.setObjectName("dashboard_search_container")
        t = theme_manager.get_active_theme()

        search_box_layout = QVBoxLayout(self.search_container)
        search_box_layout.setContentsMargins(0, 4, 0, 4)
        search_box_layout.setSpacing(8)

        # 1. Qidiruv paneli ramkasi (Search bar frame)
        self.search_bar_frame = QFrame()
        self.search_bar_frame.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border: 1.5px solid #4338CA; border-radius: 12px; }} "
            f"QFrame:hover {{ border: 1.5px solid #6366F1; }}"
        )
        bar_layout = QHBoxLayout(self.search_bar_frame)
        bar_layout.setContentsMargins(14, 8, 14, 8)
        bar_layout.setSpacing(10)

        # Qidiruv belgisi
        lbl_search_icon = QLabel("🔍")
        lbl_search_icon.setStyleSheet("font-size: 16px; border: none; background: transparent;")
        bar_layout.addWidget(lbl_search_icon)

        # Matn kiritish maydoni
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Aqlli qidiruv: inglizcha yoki o'zbekcha so'z kiriting (masalan: achieve, muvaffaqiyat, book, oila)..."
        )
        self.search_input.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {t.text_main}; "
            f"font-size: 14px; font-weight: 500; selection-background-color: {t.primary}; }}"
        )
        self.search_input.setClearButtonEnabled(False)
        bar_layout.addWidget(self.search_input, 1)

        # Status nishoni: "🌐 64k Oxford + 📚 Shaxsiy"
        self.badge_search_mode = QLabel("🌐 64k Oxford + 📚 Shaxsiy")
        self.badge_search_mode.setStyleSheet(
            "background-color: #1E1B4B; color: #A5B4FC; font-size: 12px; font-weight: 700; "
            "border: 1px solid #3730A3; border-radius: 6px; padding: 4px 10px;"
        )
        bar_layout.addWidget(self.badge_search_mode)

        # Tozalash tugmasi (✕)
        self.btn_search_clear = QPushButton("✕")
        self.btn_search_clear.setToolTip("Qidiruvni tozalash")
        self.btn_search_clear.setFixedSize(26, 26)
        self.btn_search_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search_clear.setStyleSheet(
            "QPushButton { background-color: #2A2A3C; color: #9CA3AF; border: none; "
            "border-radius: 13px; font-size: 12px; font-weight: 700; }"
            "QPushButton:hover { background-color: #EF4444; color: white; }"
        )
        self.btn_search_clear.setVisible(False)
        self.btn_search_clear.clicked.connect(self._clear_search)
        bar_layout.addWidget(self.btn_search_clear)

        search_box_layout.addWidget(self.search_bar_frame)

        # 2. Interaktiv natijalar paneli (Dropdown / Expandable panel)
        self.search_results_frame = QFrame()
        self.search_results_frame.setStyleSheet(
            f"background-color: {t.bg_card}; border: 1.5px solid {t.border}; border-radius: 12px;"
        )
        self.results_layout = QVBoxLayout(self.search_results_frame)
        self.results_layout.setContentsMargins(16, 12, 16, 12)
        self.results_layout.setSpacing(10)

        # Natijalar sarlavhasi qatori
        self.results_header_row = QHBoxLayout()
        self.lbl_results_status = QLabel("Natijalar")
        self.lbl_results_status.setStyleSheet(f"color: {t.text_main}; font-size: 14px; font-weight: 700;")
        self.results_header_row.addWidget(self.lbl_results_status)
        self.results_header_row.addStretch()

        btn_close_results = QPushButton("✕ Yopish")
        btn_close_results.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close_results.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {t.text_muted}; border: 1px solid {t.border}; "
            f"border-radius: 6px; padding: 4px 12px; font-size: 12px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: {t.border}; color: {t.text_main}; }}"
        )
        btn_close_results.clicked.connect(self._clear_search)
        self.results_header_row.addWidget(btn_close_results)
        self.results_layout.addLayout(self.results_header_row)

        # Natijalar kartalari konteyneri
        self.search_items_container = QVBoxLayout()
        self.search_items_container.setSpacing(8)
        self.results_layout.addLayout(self.search_items_container)

        self.search_results_frame.setVisible(False)
        search_box_layout.addWidget(self.search_results_frame)

        self.layout_root.addWidget(self.search_container)

        # Real-time tezkor qidiruv uchun 120ms debounce taymeri
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(120)
        self._search_timer.timeout.connect(self._do_search)

        self.search_input.textChanged.connect(self._on_search_text_changed)

        # 5 ta statistika kartalari qatori
        self.cards_row = QHBoxLayout()
        self.cards_row.setSpacing(12)

        self.val_total = QLabel("0")
        self.val_mastered = QLabel("0")
        self.val_today = QLabel("0")
        self.val_streak = QLabel("0 kun")
        self.val_accuracy = QLabel("0%")

        self.stat_cards = [
            _stat_card("Jami so'zlar", self.val_total, "#4F46E5"),
            _stat_card("O'zlashtirilgan", self.val_mastered, "#10B981"),
            _stat_card("Bugungi mashq", self.val_today, "#F59E0B"),
            _stat_card("Streak 🔥", self.val_streak, "#EF4444"),
            _stat_card("Aniqlik 🎯", self.val_accuracy, "#8B5CF6"),
        ]
        for card in self.stat_cards:
            self.cards_row.addWidget(card)

        self.layout_root.addLayout(self.cards_row)

        # --- Kunlik reja paneli ---
        self.goal_frame = QFrame()
        self.goal_frame.setStyleSheet("background-color: #1E1E2E; border-radius: 12px;")
        goal_layout = QVBoxLayout(self.goal_frame)
        goal_layout.setContentsMargins(18, 14, 18, 14)
        goal_layout.setSpacing(8)

        goal_top_row = QHBoxLayout()
        self.goal_title = QLabel("Kunlik reja")
        self.goal_title.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
        goal_top_row.addWidget(self.goal_title)
        goal_top_row.addStretch()

        goal_top_row.addWidget(self._muted_label("Maqsad (kuniga so'z):"))
        self.goal_spin = QSpinBox()
        self.goal_spin.setRange(1, 500)
        self.goal_spin.setStyleSheet(
            "background-color: #151521; color: white; border: 1px solid #2A2A3C;"
            "border-radius: 6px; padding: 4px 8px;"
        )
        self.goal_spin.editingFinished.connect(self.save_goal)
        self.goal_spin.valueChanged.connect(self._on_goal_spin_changed)
        goal_top_row.addWidget(self.goal_spin)
        save_btn = QPushButton("Saqlash")
        save_btn.setStyleSheet(
            "background-color: #4F46E5; color: white; border-radius: 6px; padding: 5px 12px; font-size: 13px;"
        )
        save_btn.clicked.connect(self.save_goal)
        goal_top_row.addWidget(save_btn)
        goal_layout.addLayout(goal_top_row)

        self.goal_bar = QProgressBar()
        self.goal_bar.setTextVisible(True)
        self.goal_bar.setStyleSheet(
            """
            QProgressBar { background-color: #151521; border-radius: 8px; height: 24px;
                color: white; text-align: center; font-size: 13px; }
            QProgressBar::chunk { background-color: #10B981; border-radius: 8px; }
            """
        )
        goal_layout.addWidget(self.goal_bar)

        self.goal_status = QLabel("")
        self.goal_status.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        goal_layout.addWidget(self.goal_status)

        self.layout_root.addWidget(self.goal_frame)

        # --- Tezkor amallar paneli (Quick Actions) ---
        self.actions_frame = QFrame()
        self.actions_frame.setStyleSheet("background-color: #1E1E2E; border-radius: 12px;")
        actions_layout = QHBoxLayout(self.actions_frame)
        actions_layout.setContentsMargins(18, 10, 18, 10)
        actions_layout.setSpacing(12)

        act_label = QLabel("⚡ Tezkor amallar:")
        act_label.setStyleSheet("color: white; font-size: 15px; font-weight: 600;")
        actions_layout.addWidget(act_label)

        btn_practice = QPushButton("🚀 Mashqni boshlash (EN→UZ)")
        btn_practice.setStyleSheet(self._action_btn_style("#4F46E5"))
        btn_practice.clicked.connect(lambda: self._go("en_uz"))
        actions_layout.addWidget(btn_practice)

        btn_practice_uz = QPushButton("🚀 Mashqni boshlash (UZ→EN)")
        btn_practice_uz.setStyleSheet(self._action_btn_style("#6366F1"))
        btn_practice_uz.clicked.connect(lambda: self._go("uz_en"))
        actions_layout.addWidget(btn_practice_uz)

        btn_dict = QPushButton("📖 Lug'atni ochish")
        btn_dict.setStyleSheet(self._action_btn_style("#10B981"))
        btn_dict.clicked.connect(lambda: self._go("dictionary"))
        actions_layout.addWidget(btn_dict)

        btn_import = QPushButton("📥 So'z qo'shish")
        btn_import.setStyleSheet(self._action_btn_style("#3730A3"))
        btn_import.clicked.connect(lambda: self._go("import"))
        actions_layout.addWidget(btn_import)

        btn_match = QPushButton("🎮 So'zlarni juftlash")
        btn_match.setStyleSheet(self._action_btn_style("#D946EF"))
        btn_match.clicked.connect(lambda: self._go("match"))
        actions_layout.addWidget(btn_match)

        btn_audio = QPushButton("🎧 Audio pleyer")
        btn_audio.setStyleSheet(self._action_btn_style("#0284C7"))
        btn_audio.clicked.connect(lambda: self._go("audio_player"))
        actions_layout.addWidget(btn_audio)

        btn_blitz = QPushButton("⚡ Blitz marafon")
        btn_blitz.setStyleSheet(self._action_btn_style("#D97706"))
        btn_blitz.clicked.connect(lambda: self._go("blitz"))
        actions_layout.addWidget(btn_blitz)

        actions_layout.addStretch()
        self.layout_root.addWidget(self.actions_frame)

        # --- Anki SM-2 Spaced Repetition Bugungi Takrorlash Paneli ---
        self.due_frame = QFrame()
        self.due_frame.setStyleSheet(
            "QFrame { background-color: #1E1B4B; border: 1.5px solid #4338CA; border-radius: 12px; }"
        )
        df_layout = QHBoxLayout(self.due_frame)
        df_layout.setContentsMargins(18, 12, 18, 12)
        df_layout.setSpacing(12)

        self.due_label = QLabel("🧠 Ebbinghaus/Anki takrorlash: Bugun takrorlash muddati kelgan so'zlar bor!")
        self.due_label.setStyleSheet("color: #C7D2FE; font-size: 14px; font-weight: 600;")
        df_layout.addWidget(self.due_label, 1)

        self.btn_practice_due = QPushButton("🧠 Hozir takrorlash (SM-2)")
        self.btn_practice_due.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_practice_due.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; border: none; "
            "border-radius: 6px; padding: 7px 16px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        self.btn_practice_due.clicked.connect(self._practice_due_words)
        df_layout.addWidget(self.btn_practice_due)

        self.due_frame.setVisible(False)
        self.layout_root.addWidget(self.due_frame)

        # --- Zaif so'zlar karantini ogohlantirish banneri ---
        self.weak_frame = QFrame()
        self.weak_frame.setStyleSheet(
            "QFrame { background-color: #2D1A1A; border: 1px solid #7F1D1D; border-radius: 12px; }"
        )
        wf_layout = QHBoxLayout(self.weak_frame)
        wf_layout.setContentsMargins(18, 12, 18, 12)
        wf_layout.setSpacing(12)

        self.weak_label = QLabel("⚠️ Diqqat: Sizda tez-tez xato qilinayotgan zaif so'zlar bor!")
        self.weak_label.setStyleSheet("color: #FCA5A5; font-size: 14px; font-weight: 600;")
        wf_layout.addWidget(self.weak_label, 1)

        self.btn_practice_weak = QPushButton("⚠️ Zaif so'zlarni mashq qilish")
        self.btn_practice_weak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_practice_weak.setStyleSheet(
            "QPushButton { background-color: #DC2626; color: white; border: none; "
            "border-radius: 6px; padding: 7px 16px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background-color: #B91C1C; }"
        )
        self.btn_practice_weak.clicked.connect(self._practice_weak_words)
        wf_layout.addWidget(self.btn_practice_weak)

        self.weak_frame.setVisible(False)
        self.layout_root.addWidget(self.weak_frame)

        # --- Grafiklar qatori (100% Native PyQt6 QPainter grafiklari) ---
        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        self.week_chart = WeeklyChartWidget()
        charts_row.addWidget(self.week_chart, 1)

        self.box_chart = BoxChartWidget()
        charts_row.addWidget(self.box_chart, 1)

        self.layout_root.addLayout(charts_row)

        # --- Yillik Faollik Issiqlik Xaritasi (Activity Heatmap) ---
        self.heatmap_chart = ActivityHeatmapWidget()
        self.layout_root.addWidget(self.heatmap_chart)

        # --- Zaif So'zlar Radari (Top 5 Weakest Words) ---
        self.radar_frame = QFrame()
        self.radar_frame.setStyleSheet("background-color: #1E1E2E; border-radius: 12px;")
        r_layout = QVBoxLayout(self.radar_frame)
        r_layout.setContentsMargins(18, 14, 18, 14)
        r_layout.setSpacing(10)

        r_top = QHBoxLayout()
        self.radar_title = QLabel("🎯 Zaif So'zlar Radari (Eng ko'p xato qilinganlar)")
        self.radar_title.setStyleSheet("color: white; font-size: 16px; font-weight: 700;")
        r_top.addWidget(self.radar_title)
        r_top.addStretch()

        self.btn_practice_radar = QPushButton("⚡ Hammasini Mashq Qilish")
        self.btn_practice_radar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_practice_radar.setStyleSheet(self._action_btn_style("#DC2626"))
        self.btn_practice_radar.clicked.connect(self._practice_weak_words)
        r_top.addWidget(self.btn_practice_radar)
        r_layout.addLayout(r_top)

        self.radar_list_layout = QVBoxLayout()
        self.radar_list_layout.setSpacing(6)
        r_layout.addLayout(self.radar_list_layout)

        self.layout_root.addWidget(self.radar_frame)
        self.layout_root.addStretch()

        self.goal_spin.setValue(db.get_daily_goal())
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        self.refresh()

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        for card in getattr(self, "stat_cards", []):
            acc = getattr(card, "_accent_color", "#4F46E5")
            card.setStyleSheet(
                f"QFrame {{ background-color: {t.bg_card}; border-radius: 12px; "
                f"border: 1px solid {t.border}; border-left: 4px solid {acc}; }}"
            )
            if hasattr(card, "_val_label"):
                card._val_label.setStyleSheet(f"color: {t.text_main}; font-size: 28px; font-weight: 700;")
            if hasattr(card, "_title_label"):
                card._title_label.setStyleSheet(f"color: {t.text_muted}; font-size: 13px; font-weight: 600;")

        if hasattr(self, "goal_frame"):
            self.goal_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        if hasattr(self, "goal_spin"):
            self.goal_spin.setStyleSheet(
                f"background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; "
                f"border-radius: 6px; padding: 4px 8px;"
            )
        if hasattr(self, "goal_bar"):
            self.goal_bar.setStyleSheet(
                f"""
                QProgressBar {{ background-color: {t.bg_card_secondary}; border-radius: 8px; height: 22px;
                    color: {t.text_main}; text-align: center; font-size: 12px; }}
                QProgressBar::chunk {{ background-color: {t.primary}; border-radius: 8px; }}
                """
            )
        if hasattr(self, "actions_frame"):
            self.actions_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        if hasattr(self, "due_frame"):
            self.due_frame.setStyleSheet(f"QFrame {{ background-color: {t.bg_card}; border: 1.5px solid {t.primary}; border-radius: 12px; }}")
        if hasattr(self, "week_chart"):
            self.week_chart.apply_theme(t)
        if hasattr(self, "box_chart"):
            self.box_chart.apply_theme(t)
        if hasattr(self, "scroll"):
            self.scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.bg_app}; }}")
        if hasattr(self, "scroll_content"):
            self.scroll_content.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "heatmap_chart"):
            self.heatmap_chart.apply_theme(t)
        if hasattr(self, "radar_frame"):
            self.radar_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 12px; border: 1px solid {t.border};")
        if hasattr(self, "radar_title"):
            self.radar_title.setStyleSheet(f"color: {t.text_main}; font-size: 14px; font-weight: 700;")
        if hasattr(self, "search_bar_frame"):
            self.search_bar_frame.setStyleSheet(
                f"QFrame {{ background-color: {t.bg_card}; border: 1.5px solid {t.primary}; border-radius: 12px; }} "
                f"QFrame:hover {{ border: 1.5px solid {t.primary_light}; }}"
            )
        if hasattr(self, "search_results_frame"):
            self.search_results_frame.setStyleSheet(
                f"background-color: {t.bg_card}; border: 1.5px solid {t.border}; border-radius: 12px;"
            )
        if hasattr(self, "search_input"):
            self.search_input.setStyleSheet(
                f"QLineEdit {{ background: transparent; border: none; color: {t.text_main}; "
                f"font-size: 13px; font-weight: 500; selection-background-color: {t.primary}; }}"
            )
        if hasattr(self, "lbl_results_status"):
            self.lbl_results_status.setStyleSheet(f"color: {t.text_main}; font-size: 13px; font-weight: 700;")

    def _muted_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        return lbl

    def _action_btn_style(self, color: str) -> str:
        return (
            f"QPushButton {{ background-color: {color}; color: white; border: none;"
            f"border-radius: 6px; padding: 7px 14px; font-size: 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ opacity: 0.9; }}"
        )

    def _go(self, page_key: str):
        if self.on_navigate:
            self.on_navigate(page_key)

    def _on_goal_spin_changed(self):
        if getattr(self, "_refreshing_goal", False):
            return
        val = self.goal_spin.value()
        if val != db.get_daily_goal():
            db.set_daily_goal(val)
            logger.info(f"Dashboard maqsadi o'zgarganda avtomatik saqlandi: {val} ta so'z")
            self.refresh()
            if self.on_goal_changed:
                self.on_goal_changed()

    def save_goal(self):
        val = self.goal_spin.value()
        db.set_daily_goal(val)
        logger.info(f"Dashboard maqsadi saqlandi: {val} ta so'z")
        self.refresh()
        if self.on_goal_changed:
            self.on_goal_changed()

    def _open_achievements(self):
        dlg = AchievementsDialog(self)
        dlg.exec()

    def _practice_due_words(self):
        due_words = db.get_due_words(limit=50)
        if due_words and self.on_start_practice:
            w_ids = [w["id"] for w in due_words]
            self.on_start_practice(w_ids, direction="en_uz")
        else:
            self._go("en_uz")

    def _practice_weak_words(self):
        weak_words = db.get_weak_words(limit=30)
        if weak_words and self.on_start_practice:
            w_ids = [w["id"] for w in weak_words]
            self.on_start_practice(w_ids, direction="en_uz")

    def refresh(self):
        self._refreshing_goal = True
        try:
            self.goal_spin.setValue(db.get_daily_goal())
        finally:
            self._refreshing_goal = False

        # --- Gamifikatsiya holati ---
        lvl_info = gamification.get_level_info()
        self.level_badge.setText(f"{lvl_info['badge']} {lvl_info['level']}-Daraja: {lvl_info['title']}")
        self.level_badge.setStyleSheet(
            f"background-color: #1A1A2E; color: {lvl_info['color']}; border: 1px solid {lvl_info['color']}; "
            f"border-radius: 8px; padding: 5px 12px; font-size: 12px; font-weight: 700;"
        )
        self.xp_badge.setText(f"⭐ {lvl_info['total_xp']} XP")

        # --- Anki SM-2 Spaced Repetition Bugungi Takrorlash tekshiruvi ---
        due_count = db.get_due_count()
        if due_count > 0:
            self.due_label.setText(f"🧠 Ebbinghaus/Anki takrorlash: Bugun {due_count} ta so'zni takrorlash vaqti keldi!")
            self.due_frame.setVisible(True)
        else:
            self.due_frame.setVisible(False)

        # --- Zaif so'zlar karantini tekshiruvi ---
        weak_count = db.get_weak_words_count()
        if weak_count > 0:
            self.weak_label.setText(f"⚠️ Karantin: Sizda {weak_count} ta tez-tez adashilayotgan zaif so'z bor! Ularni takrorlang.")
            self.weak_frame.setVisible(True)
        else:
            self.weak_frame.setVisible(False)

        # --- Kartalar ma'lumotlarini to'g'ridan-to'g'ri yangilash ---
        counts = db.word_count()
        streak = db.get_current_streak()
        last7 = db.get_last_n_days(7)
        today_practiced = last7[-1]["practiced"]
        goal_progress = db.get_today_progress()
        acc = db.get_accuracy_stats()

        self.val_total.setText(str(counts["total"]))
        self.val_mastered.setText(str(counts["mastered"]))
        self.val_today.setText(str(today_practiced))
        self.val_streak.setText(f"{streak} kun")
        self.val_accuracy.setText(f"{acc['percent']}%")

        # --- Kunlik reja progress ---
        self.goal_bar.setMaximum(goal_progress["goal"])
        self.goal_bar.setValue(min(goal_progress["practiced"], goal_progress["goal"]))
        self.goal_bar.setFormat(f"{goal_progress['practiced']} / {goal_progress['goal']}")
        if goal_progress["done"]:
            self.goal_status.setText("🎉 Bugungi reja bajarildi! Zo'r ketyapsiz.")
        else:
            remaining = goal_progress["goal"] - goal_progress["practiced"]
            self.goal_status.setText(f"Rejaga yetish uchun yana {remaining} ta so'z mashq qiling.")

        # --- 1-Grafik: 7 kunlik bar chart ---
        self.week_chart.set_data(last7)

        # --- 2-Grafik: Leitner Box taqsimoti ---
        box_dist = db.get_box_distribution()
        self.box_chart.set_data(box_dist)

        # --- 3-Grafik: Yillik Faollik Issiqlik Xaritasi ---
        if hasattr(self, "heatmap_chart"):
            heatmap_data = db.get_daily_activity_heatmap(365)
            self.heatmap_chart.set_data(heatmap_data)

        # --- Zaif so'zlar radari yangilanishi ---
        if hasattr(self, "radar_list_layout"):
            while self.radar_list_layout.count() > 0:
                item = self.radar_list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            weak_list = db.get_weakest_words(limit=5)
            if weak_list:
                self.radar_frame.setVisible(True)
                t = theme_manager.get_active_theme()
                for w in weak_list:
                    row_f = QFrame()
                    row_f.setStyleSheet(f"background-color: {t.bg_card_secondary}; border-radius: 8px; border: 1px solid {t.border};")
                    rf_lay = QHBoxLayout(row_f)
                    rf_lay.setContentsMargins(12, 6, 12, 6)

                    lbl_eng = QLabel(w.get("english", ""))
                    lbl_eng.setStyleSheet(f"color: {t.text_main}; font-weight: 700; font-size: 13px;")
                    rf_lay.addWidget(lbl_eng)

                    pho = w.get("phonetic", "")
                    if pho:
                        lbl_pho = QLabel(pho)
                        lbl_pho.setStyleSheet(f"color: {t.primary_light}; font-size: 12px;")
                        rf_lay.addWidget(lbl_pho)

                    rf_lay.addStretch()

                    lbl_uz = QLabel(w.get("uzbek", ""))
                    lbl_uz.setStyleSheet("color: #10B981; font-weight: 600; font-size: 13px;")
                    rf_lay.addWidget(lbl_uz)

                    wr_cnt = w.get("wrong_count", 0)
                    lbl_wrong = QLabel(f"❌ {wr_cnt} ta xato")
                    lbl_wrong.setStyleSheet(
                        "background-color: #7F1D1D; color: #FCA5A5; border-radius: 4px; "
                        "padding: 3px 8px; font-size: 12px; font-weight: 700;"
                    )
                    rf_lay.addWidget(lbl_wrong)

                    btn_p = QPushButton("Mashq")
                    btn_p.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_p.setStyleSheet(
                        f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: 4px; "
                        f"padding: 4px 12px; font-size: 12px; font-weight: 700; }}"
                    )
                    btn_p.clicked.connect(lambda _, wid=w["id"]: self._practice_single_word(wid))
                    rf_lay.addWidget(btn_p)


                    self.radar_list_layout.addWidget(row_f)
            else:
                self.radar_frame.setVisible(False)

    def _practice_single_word(self, word_id: int):
        if self.on_start_practice:
            self.on_start_practice([word_id], direction="en_uz")

    # =========================================================================
    # 🔍 UNIVERSAL SMART SEARCH EVENT HANDLERS
    # =========================================================================

    def _on_search_text_changed(self, text: str):
        query = text.strip()
        self.btn_search_clear.setVisible(bool(query))
        if not query:
            self._search_timer.stop()
            self.search_results_frame.setVisible(False)
            self._clear_result_widgets()
            return
        self._search_timer.start()

    def _clear_search(self):
        self.search_input.clear()
        self.search_results_frame.setVisible(False)
        self.btn_search_clear.setVisible(False)
        self._clear_result_widgets()

    def _clear_result_widgets(self):
        while self.search_items_container.count() > 0:
            item = self.search_items_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            self.search_results_frame.setVisible(False)
            return

        # 100% aniqlikdagi universal qidiruv
        results = global_dict_service.search_universal_words(query, limit=8)

        self._clear_result_widgets()
        t = theme_manager.get_active_theme()

        if not results:
            self.lbl_results_status.setText(f"🔍 '{query}' bo'yicha hech narsa topilmadi")
            empty_card = QFrame()
            empty_card.setStyleSheet(
                f"background-color: {t.bg_card_secondary}; border: 1px dashed {t.border}; border-radius: 8px;"
            )
            empty_layout = QHBoxLayout(empty_card)
            empty_layout.setContentsMargins(14, 10, 14, 10)

            lbl_info = QLabel("Imlo xatosi yo'qligini tekshiring yoki so'zni yangi so'z sifatida shaxsiy lug'atingizga kiriting:")
            lbl_info.setStyleSheet(f"color: {t.text_muted}; font-size: 12px;")
            empty_layout.addWidget(lbl_info, 1)

            btn_add_custom = QPushButton("➕ Yangi so'z qo'shish")
            btn_add_custom.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_add_custom.setStyleSheet(
                f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
                f"border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: 700; }} "
                f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
            )
            btn_add_custom.clicked.connect(lambda: self._go("import"))
            empty_layout.addWidget(btn_add_custom)

            self.search_items_container.addWidget(empty_card)
            self.search_results_frame.setVisible(True)
            return

        self.lbl_results_status.setText(
            f"🔍 Topildi: {len(results)} ta so'z (Inglizcha ↔ O'zbekcha universal moslik)"
        )

        for item in results:
            card = self._create_search_result_card(item, t)
            self.search_items_container.addWidget(card)

        self.search_results_frame.setVisible(True)

    def _create_search_result_card(self, item: dict, t: theme_manager.Theme) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card_secondary}; border: 1px solid {t.border}; border-radius: 10px; }} "
            f"QFrame:hover {{ border: 1px solid {t.primary}; }}"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 1. Audio Pronounce Button (🔊)
        audio_btn = QPushButton("🔊")
        audio_btn.setToolTip("Talaffuzni eshitish (TTS)")
        audio_btn.setFixedSize(36, 36)
        audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        audio_btn.setStyleSheet(
            f"QPushButton {{ background-color: {t.primary}; color: white; border: none; "
            f"border-radius: 8px; font-size: 15px; }} "
            f"QPushButton:hover {{ background-color: {t.primary_light}; }}"
        )
        eng_text = item["english"]
        audio_btn.clicked.connect(lambda _, w=eng_text: tts.speak(w))
        layout.addWidget(audio_btn)

        # 2. Details Column
        info_col = QVBoxLayout()
        info_col.setSpacing(3)

        # Top row: English word, Phonetic, POS, Star, Status badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_eng = QLabel(item["english"])
        lbl_eng.setStyleSheet(f"color: {t.text_main}; font-size: 16px; font-weight: 800;")
        top_row.addWidget(lbl_eng)

        if item.get("phonetic"):
            lbl_ph = QLabel(item["phonetic"])
            lbl_ph.setStyleSheet("color: #818CF8; font-size: 13px; font-weight: 600;")
            top_row.addWidget(lbl_ph)

        if item.get("pos"):
            lbl_pos = QLabel(f"[{item['pos']}]")
            lbl_pos.setStyleSheet(
                "background-color: #312E81; color: #C7D2FE; font-size: 12px; font-weight: 700; "
                "border-radius: 4px; padding: 2px 6px;"
            )
            top_row.addWidget(lbl_pos)

        star_val = str(item.get("star", "0"))
        if star_val and star_val != "0":
            lbl_star = QLabel(f"★ {star_val}/3")
            lbl_star.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: 700;")
            top_row.addWidget(lbl_star)

        top_row.addStretch()

        # Status Badge (Shaxsiy vs Global)
        if item.get("is_in_study_list"):
            lbl_badge = QLabel(f"✨ Shaxsiy: Box {item.get('box_level', 0)}")
            lbl_badge.setStyleSheet(
                "background-color: #064E3B; color: #34D399; border: 1px solid #059669; "
                "border-radius: 6px; padding: 3px 9px; font-size: 12px; font-weight: 700;"
            )
        else:
            lbl_badge = QLabel("🌐 64k Lug'at")
            lbl_badge.setStyleSheet(
                "background-color: #1E1B4B; color: #A5B4FC; border: 1px solid #4338CA; "
                "border-radius: 6px; padding: 3px 9px; font-size: 12px; font-weight: 700;"
            )
        top_row.addWidget(lbl_badge)
        info_col.addLayout(top_row)

        # Bottom row: Uzbek translation & example
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        lbl_uz = QLabel(item.get("uzbek", ""))
        lbl_uz.setStyleSheet("color: #10B981; font-size: 14px; font-weight: 700;")
        lbl_uz.setWordWrap(True)
        bottom_row.addWidget(lbl_uz, 1)

        info_col.addLayout(bottom_row)

        if item.get("example"):
            lbl_ex = QLabel(f"“{item['example']}”")
            lbl_ex.setStyleSheet("color: #94A3B8; font-size: 13px; font-style: italic;")
            lbl_ex.setWordWrap(True)
            info_col.addWidget(lbl_ex)

        layout.addLayout(info_col, 1)

        # 3. Action Buttons Column
        act_col = QHBoxLayout()
        act_col.setSpacing(6)

        # Add button (if not in study list)
        if not item.get("is_in_study_list"):
            btn_add = QPushButton("➕ Qo'shish")
            btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_add.setStyleSheet(
                "QPushButton { background-color: #10B981; color: white; border: none; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12.5px; font-weight: 700; } "
                "QPushButton:hover { background-color: #059669; }"
            )
            btn_add.clicked.connect(
                lambda _, it=item, b=btn_add, bg=lbl_badge: self._add_search_word_to_study(it, b, bg)
            )
            act_col.addWidget(btn_add)

        # Smart Insights Button
        btn_details = QPushButton("💡 Tahlil")
        btn_details.setToolTip("Kollokatsiyalar, sinonimlar va so'z tahlili")
        btn_details.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_details.setStyleSheet(
            f"QPushButton {{ background-color: #4338CA; color: white; border: none; "
            f"border-radius: 6px; padding: 6px 14px; font-size: 12.5px; font-weight: 700; }} "
            f"QPushButton:hover {{ background-color: #6366F1; }}"
        )
        btn_details.clicked.connect(lambda _, w=eng_text: self._open_word_details(w))
        act_col.addWidget(btn_details)

        layout.addLayout(act_col)
        return card

    def _add_search_word_to_study(self, item: dict, btn: QPushButton, badge: QLabel):
        success, msg, wid = global_dict_service.add_to_study_list(
            english=item["english"],
            uzbek=item.get("uzbek", ""),
            example=item.get("example", "")
        )
        if success:
            item["is_in_study_list"] = True
            item["local_id"] = wid
            item["box_level"] = 0
            btn.setText("✓ Qo'shildi")
            btn.setEnabled(False)
            btn.setStyleSheet(
                "background-color: #064E3B; color: #34D399; border: 1px solid #059669; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12.5px; font-weight: 700;"
            )
            badge.setText("✨ Shaxsiy: Box 0")
            badge.setStyleSheet(
                "background-color: #064E3B; color: #34D399; border: 1px solid #059669; "
                "border-radius: 6px; padding: 3px 9px; font-size: 12px; font-weight: 700;"
            )
            self.refresh()


    def _open_word_details(self, english: str):
        try:
            from ui.dictionary import WordDetailsDialog
            dlg = WordDetailsDialog(self, english=english, on_added=self.refresh)
            dlg.exec()
            self.refresh()
        except Exception as e:
            logger.error(f"WordDetailsDialog ochishda xatolik: {e}")


