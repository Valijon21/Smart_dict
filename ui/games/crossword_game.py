"""
Vocab Master Pro — Interactive Crossword Game (Interaktiv Krossvord).
Lug'atdagi so'zlardan avtomatik kesishuvchi krossvord panjarasini yasash va yechish.
Gamifikatsiya qat'iy qoidasi: 0 ball yoki 0 yechilgan so'z bilan chiqilganda XP berilmaydi!
"""
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGridLayout, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor

import database as db
import gamification
import sound_effects
import theme_manager
from logger import get_logger
from ui.components.game_source_selector import GameSourceSelector
from services import game_word_provider as gwp

logger = get_logger("crossword_game")

GRID_SIZE = 10


class CrosswordWord:
    """Krossvorddagi joylashgan so'z."""
    def __init__(self, number: int, word: str, clue: str, row: int, col: int, direction: str):
        self.number = number
        self.word = word.upper()
        self.clue = clue
        self.row = row
        self.col = col
        self.direction = direction  # 'across' yoki 'down'
        self.is_solved = False

    def get_cells(self) -> list[tuple[int, int]]:
        """Ushbu so'z egallagan kataklar koordinatalari."""
        coords = []
        for step in range(len(self.word)):
            r = self.row + (step if self.direction == "down" else 0)
            c = self.col + (0 if self.direction == "down" else step)
            coords.append((r, c))
        return coords


class CrosswordGenerator:
    """Baza so'zlaridan kesishuvchi krossvord panjarasini yasovchi aqlli algoritm."""
    @staticmethod
    def generate(words: list[dict], max_words: int = 7) -> tuple[list[list[str | None]], list[CrosswordWord]]:
        if not words:
            return [], []

        # Faqat 3 tadan 8 tagacha harfli toza inglizcha so'zlarni saralash
        clean_words = []
        for w in words:
            wd = dict(w) if not isinstance(w, dict) else w
            eng = wd.get("english", "").strip()
            uz = wd.get("uzbek", "").strip()
            if 3 <= len(eng) <= 8 and eng.isalpha():
                clean_words.append({"eng": eng.upper(), "uz": uz})

        if len(clean_words) < 3:
            return [], []

        random.shuffle(clean_words)
        grid = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        placed_words: list[CrosswordWord] = []
        word_num = 1

        # 1-so'zni o'rtaga gorizontal joylashtirish
        first = clean_words[0]
        first_eng = first["eng"]
        start_row = GRID_SIZE // 2
        start_col = max(0, (GRID_SIZE - len(first_eng)) // 2)

        for i, ch in enumerate(first_eng):
            grid[start_row][start_col + i] = ch
        placed_words.append(CrosswordWord(word_num, first_eng, first["uz"], start_row, start_col, "across"))
        word_num += 1

        # Qolgan so'zlarni kesishish nuqtalarini topib joylashtirish
        for cand in clean_words[1:]:
            if len(placed_words) >= max_words:
                break
            cand_eng = cand["eng"]
            cand_uz = cand["uz"]
            placed = False

            # Mavjud so'zlar bilan kesishish nuqtalarini tekshirish
            for existing in placed_words:
                if placed:
                    break
                target_dir = "down" if existing.direction == "across" else "across"

                for i, ex_char in enumerate(existing.word):
                    for j, cand_char in enumerate(cand_eng):
                        if ex_char == cand_char:
                            if target_dir == "down":
                                r = existing.row - j
                                c = existing.col + i
                            else:
                                r = existing.row + i
                                c = existing.col - j

                            if 0 <= r and r + (len(cand_eng) if target_dir == "down" else 1) <= GRID_SIZE:
                                if 0 <= c and c + (1 if target_dir == "down" else len(cand_eng)) <= GRID_SIZE:
                                    can_place = True
                                    for step in range(len(cand_eng)):
                                        curr_r = r + (step if target_dir == "down" else 0)
                                        curr_c = c + (0 if target_dir == "down" else step)
                                        cell_val = grid[curr_r][curr_c]
                                        if cell_val is not None and cell_val != cand_eng[step]:
                                            can_place = False
                                            break

                                    if can_place:
                                        for step in range(len(cand_eng)):
                                            curr_r = r + (step if target_dir == "down" else 0)
                                            curr_c = c + (0 if target_dir == "down" else step)
                                            grid[curr_r][curr_c] = cand_eng[step]
                                        placed_words.append(
                                            CrosswordWord(word_num, cand_eng, cand_uz, r, c, target_dir)
                                        )
                                        word_num += 1
                                        placed = True
                                        break
                    if placed:
                        break

        return grid, placed_words


class CrosswordCell(QLineEdit):
    """Krossvord katagi — avtomatik keyingi katakka o'tish, Backspace va raqam ko'rinishi bilan."""
    letter_entered = pyqtSignal(int, int)  # (row, col)
    backspace_pressed = pyqtSignal(int, int)  # (row, col)
    navigate_requested = pyqtSignal(int, int, str)  # (row, col, direction)
    cell_clicked = pyqtSignal(int, int)  # (row, col)
    enter_pressed = pyqtSignal()

    def __init__(self, expected_char: str, row: int, col: int, cell_number: str = "", parent=None):
        super().__init__(parent)
        self.expected_char = expected_char.upper()
        self.row = row
        self.col = col
        self.cell_number = str(cell_number) if cell_number else ""
        self.is_highlighted = False
        self.state = "normal"

        self.setMaxLength(1)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.setFixedSize(40, 40)
        self._apply_style()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.cell_number:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            p.setPen(QColor(165, 180, 252, 230))
            p.drawText(3, 10, self.cell_number)
            p.end()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.cell_clicked.emit(self.row, self.col)

    def keyPressEvent(self, event):
        key = event.key()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.enter_pressed.emit()
            return

        if key == Qt.Key.Key_Backspace:
            if self.text():
                self.setText("")
            else:
                self.backspace_pressed.emit(self.row, self.col)
            return

        if key == Qt.Key.Key_Left:
            self.navigate_requested.emit(self.row, self.col, "left")
            return
        if key == Qt.Key.Key_Right:
            self.navigate_requested.emit(self.row, self.col, "right")
            return
        if key == Qt.Key.Key_Up:
            self.navigate_requested.emit(self.row, self.col, "up")
            return
        if key == Qt.Key.Key_Down:
            self.navigate_requested.emit(self.row, self.col, "down")
            return

        text = event.text()
        if text and text.isalpha():
            char = text.upper()
            self.setText(char)
            self.letter_entered.emit(self.row, self.col)
            return

        super().keyPressEvent(event)

    def set_state(self, state: str):
        self.state = state
        self._apply_style()

    def set_highlight(self, active: bool):
        self.is_highlighted = active
        self._apply_style()

    def _apply_style(self):
        if self.state == "correct":
            self.setStyleSheet(
                "QLineEdit { background-color: #064E3B; color: #6EE7B7; border: 1.5px solid #10B981; "
                "border-radius: 6px; font-weight: 800; font-size: 14px; } "
                "QLineEdit:focus { border: 2px solid #34D399; }"
            )
            self.setEnabled(False)
        elif self.state == "wrong":
            self.setStyleSheet(
                "QLineEdit { background-color: #7F1D1D; color: #FCA5A5; border: 1.5px solid #EF4444; "
                "border-radius: 6px; font-weight: 800; font-size: 14px; } "
                "QLineEdit:focus { border: 2px solid #F87171; }"
            )
        elif self.state == "hint":
            self.setText(self.expected_char)
            self.setStyleSheet(
                "QLineEdit { background-color: #78350F; color: #FDE68A; border: 1.5px solid #F59E0B; "
                "border-radius: 6px; font-weight: 800; font-size: 14px; } "
                "QLineEdit:focus { border: 2px solid #FBBF24; }"
            )
            self.setEnabled(False)
        elif self.is_highlighted:
            self.setStyleSheet(
                "QLineEdit { background-color: #312E81; color: #FFFFFF; border: 1.5px solid #6366F1; "
                "border-radius: 6px; font-weight: 700; font-size: 14px; } "
                "QLineEdit:focus { border: 2px solid #A5B4FC; background-color: #3730A3; }"
            )
        else:
            self.setStyleSheet(
                "QLineEdit { background-color: #1E1B4B; color: white; border: 1.5px solid #4338CA; "
                "border-radius: 6px; font-size: 14px; } "
                "QLineEdit:focus { border: 2px solid #818CF8; background-color: #312E81; }"
            )


class CrosswordGameWidget(QWidget):
    """Interaktiv Krossvord Sahifasi."""
    game_finished = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_data = []
        self.words: list[CrosswordWord] = []
        self.cells: dict[tuple[int, int], CrosswordCell] = {}
        self.clue_buttons: dict[int, QPushButton] = {}
        self.active_word: CrosswordWord | None = None
        self.active_direction: str = "across"
        self.solved_words = 0
        self.hints_used = 0
        self.is_active = False

        self._build_ui()
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())
        self.generate_new_puzzle()

    def _build_ui(self):
        t = theme_manager.get_active_theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)

        # 1. Sarlavha qatori
        top_bar = QHBoxLayout()
        self.title_lbl = QLabel("🧩 Lug'at Krossvordi")
        self.title_lbl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.text_main};")
        top_bar.addWidget(self.title_lbl)
        top_bar.addStretch()

        self.lbl_progress = QLabel("✅ Yechildi: 0 / 0")
        self.lbl_progress.setStyleSheet(
            f"background-color: #064E3B; color: #6EE7B7; font-size: 13px; font-weight: 700; "
            f"border-radius: 8px; padding: 6px 14px;"
        )
        top_bar.addWidget(self.lbl_progress)
        root.addLayout(top_bar)

        desc = QLabel("Krossvord kataklariga yoki o'ngdagi ta'riflarga bosib so'zlarni yozing. Harflar avtomatik keyingisiga o'tadi.")
        desc.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")
        root.addWidget(desc)

        # To'plam tanlash paneli (Mavzular, To'plamlar, CEFR, Shaxsiy)
        self.source_selector = GameSourceSelector("crossword", self)
        self.source_selector.source_changed.connect(lambda _c, _s: self.generate_new_puzzle())
        root.addWidget(self.source_selector)

        # 2. Asosiy bo'linma (Chap: Panjara, O'ng: Ta'riflar)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Panjara konteyneri
        self.grid_container = QFrame()
        self.grid_container.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border: 1.5px solid {t.border}; border-radius: 14px; }}"
        )
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.addWidget(self.grid_container, 0, Qt.AlignmentFlag.AlignCenter)

        # O'ng: Ta'riflar ro'yxati (Clues)
        clues_frame = QFrame()
        clues_frame.setStyleSheet(
            f"QFrame {{ background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 14px; }}"
        )
        clues_vbox = QVBoxLayout(clues_frame)
        clues_vbox.setContentsMargins(16, 14, 16, 14)
        clues_vbox.setSpacing(10)

        lbl_clues_title = QLabel("📖 Savollar va Ta'riflar:")
        lbl_clues_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {t.text_main};")
        clues_vbox.addWidget(lbl_clues_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.clues_content = QWidget()
        self.clues_layout = QVBoxLayout(self.clues_content)
        self.clues_layout.setSpacing(8)
        self.clues_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.clues_content)
        clues_vbox.addWidget(scroll, 1)

        content_layout.addWidget(clues_frame, 1)
        root.addLayout(content_layout, 1)

        # 3. Pastki tugmalar qatori
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        self.btn_hint = QPushButton("💡 Harfni ochish (-2 ball)")
        self.btn_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hint.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: #F59E0B; border: 1px solid #D97706; "
            f"border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: #78350F; color: white; }}"
        )
        self.btn_hint.clicked.connect(self._give_hint)
        btn_bar.addWidget(self.btn_hint)

        self.btn_check = QPushButton("✅ Javoblarni Tekshirish (Enter)")
        self.btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; border-radius: 8px; "
            "padding: 10px 22px; font-size: 13px; font-weight: 700; } "
            "QPushButton:hover { background-color: #059669; }"
        )
        self.btn_check.clicked.connect(self.check_answers)
        btn_bar.addWidget(self.btn_check)

        btn_bar.addStretch()

        self.btn_new = QPushButton("🔄 Yangi Krossvord")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ border-color: {t.primary}; color: {t.primary}; }}"
        )
        self.btn_new.clicked.connect(self.generate_new_puzzle)
        btn_bar.addWidget(self.btn_new)

        self.btn_end = QPushButton("⏹️ Yakunlash")
        self.btn_end.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_end.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: #EF4444; border: 1px solid #7F1D1D; "
            f"border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: #7F1D1D; color: white; }}"
        )
        self.btn_end.clicked.connect(self.finish_game)
        btn_bar.addWidget(self.btn_end)

        root.addLayout(btn_bar)

    def generate_new_puzzle(self):
        """Tanlangan to'plam so'zlaridan yangi krossvord yasash."""
        if hasattr(self, "source_selector"):
            words = self.source_selector.get_words(limit=80, min_len=3, max_len=8, alpha_only=True)
        else:
            words = db.get_all_words()

        if len(words) < 4:
            if hasattr(self, "source_selector"):
                words = self.source_selector.get_words(limit=80)
            if len(words) < 4:
                words = db.get_all_words()

        if len(words) < 4:
            words = gwp.get_words_for_game(gwp.CAT_PACKS, "essential", limit=80, min_len=3, max_len=8, alpha_only=True)

        if len(words) < 3:
            QMessageBox.warning(self, "So'zlar kam", "Krossvord yaratish uchun kamida 3 ta mos so'z bo'lishi kerak!")
            return

        grid, placed = CrosswordGenerator.generate(words, max_words=6)
        if not placed:
            fallback_words = gwp.get_words_for_game(gwp.CAT_PACKS, "essential", limit=80, min_len=3, max_len=8, alpha_only=True)
            grid, placed = CrosswordGenerator.generate(fallback_words, max_words=6)

        if not placed:
            QMessageBox.warning(self, "Krossvord", "Krossvord uchun mos keluvchi kesishuvchi so'zlar topilmadi.")
            return

        self.grid_data = grid
        self.words = placed
        self.solved_words = 0
        self.hints_used = 0
        self.is_active = True
        self.active_word = None
        self.clue_buttons = {}

        # Panjarani tozalash
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cells = {}

        # Kataklardagi boshlang'ich raqamlarni aniqlash
        start_cell_numbers: dict[tuple[int, int], list[int]] = {}
        for w in self.words:
            start_cell_numbers.setdefault((w.row, w.col), []).append(w.number)

        # Kataklarni joylashtirish
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                ch = grid[r][c]
                if ch is not None:
                    nums = start_cell_numbers.get((r, c), [])
                    num_str = ",".join(str(n) for n in nums) if nums else ""
                    cell = CrosswordCell(ch, r, c, cell_number=num_str, parent=self)
                    cell.letter_entered.connect(self._on_cell_letter_entered)
                    cell.backspace_pressed.connect(self._on_cell_backspace_pressed)
                    cell.navigate_requested.connect(self._on_cell_navigate)
                    cell.cell_clicked.connect(self._on_cell_clicked)
                    cell.enter_pressed.connect(self.check_answers)

                    self.cells[(r, c)] = cell
                    self.grid_layout.addWidget(cell, r, c)
                else:
                    empty = QLabel()
                    empty.setFixedSize(40, 40)
                    empty.setStyleSheet("background-color: transparent;")
                    self.grid_layout.addWidget(empty, r, c)

        # Ta'riflar ro'yxatini chiqarish
        while self.clues_layout.count():
            item = self.clues_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        across_words = [w for w in self.words if w.direction == "across"]
        down_words = [w for w in self.words if w.direction == "down"]

        t = theme_manager.get_active_theme()

        if across_words:
            h_lbl = QLabel("➡️ <b>Eniga (Across):</b>")
            h_lbl.setStyleSheet(f"color: {t.primary}; font-size: 13px; font-weight: 700;")
            self.clues_layout.addWidget(h_lbl)
            for w in across_words:
                btn = QPushButton(f"{w.number}. {w.clue} ({len(w.word)} ta harf)")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton { text-align: left; background-color: #1E1B4B; color: #E0E7FF; "
                    "border: 1px solid #3730A3; border-radius: 8px; padding: 7px 12px; font-size: 12px; } "
                    "QPushButton:hover { background-color: #312E81; border-color: #6366F1; }"
                )
                btn.clicked.connect(lambda _, word=w: self._select_word(word))
                self.clue_buttons[w.number] = btn
                self.clues_layout.addWidget(btn)

        if down_words:
            v_lbl = QLabel("⬇️ <b>Bo'yiga (Down):</b>")
            v_lbl.setStyleSheet("color: #10B981; font-size: 13px; font-weight: 700; margin-top: 8px;")
            self.clues_layout.addWidget(v_lbl)
            for w in down_words:
                btn = QPushButton(f"{w.number}. {w.clue} ({len(w.word)} ta harf)")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton { text-align: left; background-color: #1E1B4B; color: #E0E7FF; "
                    "border: 1px solid #3730A3; border-radius: 8px; padding: 7px 12px; font-size: 12px; } "
                    "QPushButton:hover { background-color: #312E81; border-color: #6366F1; }"
                )
                btn.clicked.connect(lambda _, word=w: self._select_word(word))
                self.clue_buttons[w.number] = btn
                self.clues_layout.addWidget(btn)

        self.clues_layout.addStretch()
        self.lbl_progress.setText(f"✅ Yechildi: 0 / {len(self.words)}")

        # Dastlab birinchi so'zni tanlab qo'yish
        if self.words:
            self._select_word(self.words[0])

    def _select_word(self, word: CrosswordWord, focus_coord: tuple[int, int] | None = None):
        """Krossvorddagi faol so'zni tanlash va uning kataklarini yoritish."""
        self.active_word = word
        self.active_direction = word.direction

        word_coords = set(word.get_cells())

        # 1. Kataklar belgilanishini yangilash
        for coord, cell in self.cells.items():
            cell.set_highlight(coord in word_coords)

        # 2. Ta'rif tugmalarining uslubini yangilash
        for num, btn in self.clue_buttons.items():
            w = next((x for x in self.words if x.number == num), None)
            if w and w.is_solved:
                btn.setStyleSheet(
                    "QPushButton { text-align: left; background-color: #064E3B; color: #6EE7B7; "
                    "border: 1px solid #10B981; border-radius: 8px; padding: 7px 12px; font-size: 12px; font-weight: 600; }"
                )
            elif num == word.number:
                btn.setStyleSheet(
                    "QPushButton { text-align: left; background-color: #312E81; color: #FFFFFF; "
                    "border: 1.5px solid #818CF8; border-radius: 8px; padding: 7px 12px; font-size: 12px; font-weight: 700; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { text-align: left; background-color: #1E1B4B; color: #E0E7FF; "
                    "border: 1px solid #3730A3; border-radius: 8px; padding: 7px 12px; font-size: 12px; } "
                    "QPushButton:hover { background-color: #312E81; border-color: #6366F1; }"
                )

        # 3. Fokusni joylashtirish
        if focus_coord and focus_coord in self.cells:
            c = self.cells[focus_coord]
            if c.isEnabled():
                c.setFocus()
                c.selectAll()
                return

        # Bo'sh bo'lgan birinchi katakka fokus qilish
        for coord in word.get_cells():
            c = self.cells.get(coord)
            if c and c.isEnabled() and not c.text().strip():
                c.setFocus()
                c.selectAll()
                return

        # Aks holda birinchi faol katakka
        for coord in word.get_cells():
            c = self.cells.get(coord)
            if c and c.isEnabled():
                c.setFocus()
                c.selectAll()
                return

    def _on_cell_clicked(self, row: int, col: int):
        """Foydalanuvchi katakka bosganda tegishli so'zni tanlash."""
        matching = [w for w in self.words if (row, col) in w.get_cells()]
        if not matching:
            return

        if len(matching) == 1:
            self._select_word(matching[0], focus_coord=(row, col))
        else:
            # Ikki yo'nalish kesishgan katak: yana bosilsa yo'nalishni almashtirish
            if self.active_word and self.active_word in matching:
                other = next((w for w in matching if w != self.active_word), matching[0])
                self._select_word(other, focus_coord=(row, col))
            else:
                across_w = next((w for w in matching if w.direction == "across"), matching[0])
                self._select_word(across_w, focus_coord=(row, col))

    def _on_cell_letter_entered(self, row: int, col: int):
        """Harf kiritilganda avtomatik keyingi katakka o'tish."""
        if not self.active_word:
            matches = [w for w in self.words if (row, col) in w.get_cells()]
            if matches:
                self.active_word = matches[0]

        if self.active_word:
            coords = self.active_word.get_cells()
            if (row, col) in coords:
                idx = coords.index((row, col))
                for next_idx in range(idx + 1, len(coords)):
                    nc = self.cells.get(coords[next_idx])
                    if nc and nc.isEnabled():
                        nc.setFocus()
                        nc.selectAll()
                        return
        else:
            step_r = 1 if self.active_direction == "down" else 0
            step_c = 0 if self.active_direction == "down" else 1
            nc = self.cells.get((row + step_r, col + step_c))
            if nc and nc.isEnabled():
                nc.setFocus()
                nc.selectAll()

    def _on_cell_backspace_pressed(self, row: int, col: int):
        """Backspace bosilganda oldingi katakka qaytish."""
        if self.active_word:
            coords = self.active_word.get_cells()
            if (row, col) in coords:
                idx = coords.index((row, col))
                if idx > 0:
                    for prev_idx in range(idx - 1, -1, -1):
                        pc = self.cells.get(coords[prev_idx])
                        if pc and pc.isEnabled():
                            pc.setText("")
                            pc.setFocus()
                            return
        else:
            step_r = -1 if self.active_direction == "down" else 0
            step_c = 0 if self.active_direction == "down" else -1
            pc = self.cells.get((row + step_r, col + step_c))
            if pc and pc.isEnabled():
                pc.setText("")
                pc.setFocus()

    def _on_cell_navigate(self, row: int, col: int, direction: str):
        """Strelkalar yordamida harakatlanish."""
        dr, dc = 0, 0
        if direction == "left":
            dc = -1
        elif direction == "right":
            dc = 1
        elif direction == "up":
            dr = -1
        elif direction == "down":
            dr = 1

        target = self.cells.get((row + dr, col + dc))
        if target and target.isEnabled():
            target.setFocus()
            target.selectAll()

    def _give_hint(self):
        """Bitta bo'sh katakdagi to'g'ri harfni ochish."""
        if not self.is_active:
            return

        unsolved_cells = [cell for cell in self.cells.values() if cell.isEnabled() and cell.text().upper() != cell.expected_char]
        if unsolved_cells:
            chosen = random.choice(unsolved_cells)
            chosen.set_state("hint")
            self.hints_used += 1

    def check_answers(self):
        """Kiritilgan harflarni tekshirish va to'g'ri so'zlarni belgilash."""
        if not self.is_active or not self.words:
            return

        now_solved = 0
        for w in self.words:
            word_correct = True
            for r, c in w.get_cells():
                cell = self.cells.get((r, c))
                if not cell or cell.text().strip().upper() != cell.expected_char:
                    word_correct = False
                    break

            if word_correct:
                w.is_solved = True
                now_solved += 1
                for r, c in w.get_cells():
                    cell = self.cells.get((r, c))
                    if cell:
                        cell.set_state("correct")

                btn = self.clue_buttons.get(w.number)
                if btn:
                    btn.setText(f"✅ {w.number}. {w.clue} ({w.word})")
                    btn.setStyleSheet(
                        "QPushButton { text-align: left; background-color: #064E3B; color: #6EE7B7; "
                        "border: 1px solid #10B981; border-radius: 8px; padding: 7px 12px; font-size: 12px; font-weight: 600; }"
                    )

        self.solved_words = now_solved
        self.lbl_progress.setText(f"✅ Yechildi: {self.solved_words} / {len(self.words)}")

        if self.solved_words == len(self.words):
            sound_effects.play_victory()
            self.finish_game()
        elif self.solved_words > 0:
            sound_effects.play_correct()
        else:
            sound_effects.play_wrong()

    def finish_game(self):
        """Krossvordni yakunlash va XP berish."""
        if not self.is_active:
            return
        self.is_active = False

        source_title = self.source_selector.get_current_source_title() if hasattr(self, "source_selector") else "Lug'at"

        # GAMIFIKATSIYA QAT'IY QOIDASI: 0 ta so'z yechilsa 0 XP!
        if self.solved_words > 0:
            earned_xp = max(1, self.solved_words * 5 - self.hints_used * 2)
            new_total_xp, level_up, level_title = gamification.award_xp(earned_xp)
            sound_effects.play_victory()
            msg = (
                f"🧩 <b>Krossvord yakunlandi!</b><br><br>"
                f"🏷️ To'plam: <b>{source_title}</b><br>"
                f"✅ Yechilgan so'zlar: <b>{self.solved_words} / {len(self.words)} ta</b><br>"
                f"💡 Ishlatilgan maslahatlar: <b>{self.hints_used} ta</b><br>"
                f"⭐ Berilgan mukofot: <b>+{earned_xp} XP</b> (Jami: {new_total_xp} XP)"
            )
        else:
            msg = (
                f"🧩 <b>Krossvord yakunlandi!</b><br><br>"
                f"🏷️ To'plam: <b>{source_title}</b><br>"
                f"Yechilgan so'zlar: <b>0 ta</b><br>"
                f"<i>Qat'iy qoida: 0 ta so'z bilan XP berilmaydi.</i>"
            )

        QMessageBox.information(self, "Krossvord Yakuni", msg)
        self.game_finished.emit(self.solved_words)

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "title_lbl"):
            self.title_lbl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {t.text_main};")
        if hasattr(self, "source_selector"):
            self.source_selector.apply_theme(t)
        if hasattr(self, "grid_container"):
            self.grid_container.setStyleSheet(
                f"QFrame {{ background-color: {t.bg_card}; border: 1.5px solid {t.border}; border-radius: 14px; }}"
            )
