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
from PyQt6.QtGui import QFont

import database as db
import gamification
import sound_effects
import theme_manager
from logger import get_logger

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


class CrosswordGenerator:
    """Baza so'zlaridan kesishuvchi krossvord panjarasini yasovchi aqlli algoritm."""
    @staticmethod
    def generate(words: list[dict], max_words: int = 7) -> tuple[list[list[str | None]], list[CrosswordWord]]:
        if not words:
            return [], []

        # Faqat 3 tadan 9 tagacha harfli toza inglizcha so'zlarni saralash
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
                # Qarama-qarshi yo'nalishda joylashtirishga harakat qilish
                target_dir = "down" if existing.direction == "across" else "across"

                for i, ex_char in enumerate(existing.word):
                    for j, cand_char in enumerate(cand_eng):
                        if ex_char == cand_char:
                            # Kesishish koordinatasini aniqlash
                            if target_dir == "down":
                                r = existing.row - j
                                c = existing.col + i
                            else:
                                r = existing.row + i
                                c = existing.col - j

                            # Panjaradan chiqib ketmasligini tekshirish
                            if 0 <= r and r + (len(cand_eng) if target_dir == "down" else 1) <= GRID_SIZE:
                                if 0 <= c and c + (1 if target_dir == "down" else len(cand_eng)) <= GRID_SIZE:
                                    # Konflikt yo'qligini tekshirish
                                    can_place = True
                                    for step in range(len(cand_eng)):
                                        curr_r = r + (step if target_dir == "down" else 0)
                                        curr_c = c + (0 if target_dir == "down" else step)
                                        cell_val = grid[curr_r][curr_c]
                                        if cell_val is not None and cell_val != cand_eng[step]:
                                            can_place = False
                                            break

                                    if can_place:
                                        # Panjaraga kiritish
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
    """Krossvord katagi."""
    def __init__(self, expected_char: str, row: int, col: int, parent=None):
        super().__init__(parent)
        self.expected_char = expected_char.upper()
        self.row = row
        self.col = col
        self.setMaxLength(1)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.setFixedSize(38, 38)
        self.setStyleSheet(
            "QLineEdit { background-color: #1E1B4B; color: white; border: 1.5px solid #4338CA; border-radius: 6px; } "
            "QLineEdit:focus { border: 2px solid #818CF8; background-color: #312E81; }"
        )

    def set_state(self, state: str):
        if state == "correct":
            self.setStyleSheet(
                "QLineEdit { background-color: #064E3B; color: #6EE7B7; border: 1.5px solid #10B981; border-radius: 6px; font-weight: 800; }"
            )
            self.setEnabled(False)
        elif state == "wrong":
            self.setStyleSheet(
                "QLineEdit { background-color: #7F1D1D; color: #FCA5A5; border: 1.5px solid #EF4444; border-radius: 6px; font-weight: 800; }"
            )
        elif state == "hint":
            self.setText(self.expected_char)
            self.setStyleSheet(
                "QLineEdit { background-color: #78350F; color: #FDE68A; border: 1.5px solid #F59E0B; border-radius: 6px; font-weight: 800; }"
            )
            self.setEnabled(False)
        else:
            self.setStyleSheet(
                "QLineEdit { background-color: #1E1B4B; color: white; border: 1.5px solid #4338CA; border-radius: 6px; } "
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
        self.solved_words = 0
        self.hints_used = 0
        self.is_active = False

        self._build_ui()
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

        desc = QLabel("O'zbekcha ta'riflar bo'yicha inglizcha so'zlarni krossvord kataklariga yozing va tekshiring.")
        desc.setStyleSheet(f"color: {t.text_muted}; font-size: 13px;")
        root.addWidget(desc)

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

        self.btn_hint = QPushButton("💡 Harfni ochish (-5 ball)")
        self.btn_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hint.setStyleSheet(
            f"QPushButton {{ background-color: {t.bg_card}; color: #F59E0B; border: 1px solid #D97706; "
            f"border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 600; }} "
            f"QPushButton:hover {{ background-color: #78350F; color: white; }}"
        )
        self.btn_hint.clicked.connect(self._give_hint)
        btn_bar.addWidget(self.btn_hint)

        self.btn_check = QPushButton("✅ Javoblarni Tekshirish")
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
        """Baza so'zlaridan yangi krossvord yasash."""
        words = db.get_all_words()
        if len(words) < 5:
            QMessageBox.warning(self, "So'zlar kam", "Krossvord yaratish uchun bazada kamida 5 ta so'z bo'lishi kerak!")
            return

        grid, placed = CrosswordGenerator.generate(words, max_words=6)
        if not placed:
            QMessageBox.warning(self, "Krossvord", "Krossvord uchun mos keluvchi kesishuvchi so'zlar topilmadi.")
            return

        self.grid_data = grid
        self.words = placed
        self.solved_words = 0
        self.hints_used = 0
        self.is_active = True

        # Panjarani tozalash
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cells = {}

        # Kataklarni joylashtirish
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                ch = grid[r][c]
                if ch is not None:
                    cell = CrosswordCell(ch, r, c, self)
                    self.cells[(r, c)] = cell
                    self.grid_layout.addWidget(cell, r, c)
                else:
                    empty = QLabel()
                    empty.setFixedSize(38, 38)
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
            h_lbl.setStyleSheet(f"color: {t.primary}; font-size: 13px;")
            self.clues_layout.addWidget(h_lbl)
            for w in across_words:
                lbl = QLabel(f"<b>{w.number}.</b> {w.clue} <i>({len(w.word)} ta harf)</i>")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"color: {t.text_main}; font-size: 12px; padding: 2px 0;")
                self.clues_layout.addWidget(lbl)

        if down_words:
            v_lbl = QLabel("⬇️ <b>Bo'yiga (Down):</b>")
            v_lbl.setStyleSheet(f"color: #10B981; font-size: 13px; margin-top: 8px;")
            self.clues_layout.addWidget(v_lbl)
            for w in down_words:
                lbl = QLabel(f"<b>{w.number}.</b> {w.clue} <i>({len(w.word)} ta harf)</i>")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"color: {t.text_main}; font-size: 12px; padding: 2px 0;")
                self.clues_layout.addWidget(lbl)

        self.clues_layout.addStretch()
        self.lbl_progress.setText(f"✅ Yechildi: 0 / {len(self.words)}")

    def _give_hint(self):
        """Bitta bo'sh katakdagi to'g'ri harfni ochish."""
        if not self.is_active:
            return

        unsolved_cells = [cell for cell in self.cells.values() if cell.text().upper() != cell.expected_char]
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
            for step in range(len(w.word)):
                r = w.row + (step if w.direction == "down" else 0)
                c = w.col + (0 if w.direction == "down" else step)
                cell = self.cells.get((r, c))
                if not cell or cell.text().strip().upper() != w.word[step]:
                    word_correct = False
                    break

            if word_correct:
                w.is_solved = True
                now_solved += 1
                for step in range(len(w.word)):
                    r = w.row + (step if w.direction == "down" else 0)
                    c = w.col + (0 if w.direction == "down" else step)
                    cell = self.cells.get((r, c))
                    if cell:
                        cell.set_state("correct")

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

        # GAMIFIKATSIYA QAT'IY QOIDASI: 0 ta so'z yechilsa 0 XP!
        if self.solved_words > 0:
            earned_xp = max(1, self.solved_words * 5 - self.hints_used * 2)
            res = gamification.award_xp(earned_xp)
            msg = (
                f"🧩 <b>Krossvord yakunlandi!</b><br><br>"
                f"✅ Yechilgan so'zlar: <b>{self.solved_words} / {len(self.words)} ta</b><br>"
                f"💡 Ishlatilgan maslahatlar: <b>{self.hints_used} ta</b><br>"
                f"⭐ Berilgan mukofot: <b>+{earned_xp} XP</b> (Jami: {res['total_xp']} XP)"
            )
        else:
            msg = (
                f"🧩 <b>Krossvord yakunlandi!</b><br><br>"
                f"Yechilgan so'zlar: <b>0 ta</b><br>"
                f"<i>Qat'iy qoida: 0 ta so'z bilan XP berilmaydi.</i>"
            )

        QMessageBox.information(self, "Krossvord Yakuni", msg)
        self.game_finished.emit(self.solved_words)
