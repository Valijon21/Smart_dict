from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import Qt
import random
from ui.views.practice.base_mode import BasePracticeMode

class ScrambleModeWidget(BasePracticeMode):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scramble_tiles_data = []
        self.scramble_typed_chars = []
        self.target_word_len = 0
        
        self.scramble_input_layout = QHBoxLayout()
        self.scramble_input_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scramble_input_layout.setSpacing(8)
        self.layout.addLayout(self.scramble_input_layout)

        self.scramble_pool_layout = QHBoxLayout()
        self.scramble_pool_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scramble_pool_layout.setSpacing(10)
        self.layout.addLayout(self.scramble_pool_layout)

        self.scramble_hint = QLabel("Harflarni to'g'ri tartibda tering (klaviaturadan foydalaning)")
        self.scramble_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scramble_hint.setStyleSheet("color: #6B7280; font-size: 12px; margin-top: 10px;")
        self.layout.addWidget(self.scramble_hint)

    def set_word(self, word_data, direction="en_uz", **kwargs):
        super().set_word(word_data, **kwargs)
        self.clear_ui()
        if not self.current_word:
            return
            
        target = self.current_word["english"] if direction == "en_uz" else self.current_word["uzbek"]
        target_lower = target.lower().strip()
        self.target_word_len = len(target_lower)
        
        chars = list(target_lower)
        random.shuffle(chars)
        self.scramble_tiles_data = [{"char": c, "used": False} for c in chars]
        
        for _ in range(self.target_word_len):
            lbl = QLabel("")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(36, 44)
            self.scramble_input_layout.addWidget(lbl)
            
        for i, t in enumerate(self.scramble_tiles_data):
            btn = QPushButton(t["char"])
            btn.setFixedSize(40, 40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self.on_tile_clicked(idx))
            self.scramble_pool_layout.addWidget(btn)
            
        self.apply_theme(getattr(self, "theme", None))

    def clear_ui(self):
        self.scramble_tiles_data = []
        self.scramble_typed_chars = []
        
        while self.scramble_input_layout.count():
            item = self.scramble_input_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        while self.scramble_pool_layout.count():
            item = self.scramble_pool_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def on_tile_clicked(self, idx: int):
        if self.scramble_tiles_data[idx]["used"]:
            return
            
        char = self.scramble_tiles_data[idx]["char"]
        self.scramble_tiles_data[idx]["used"] = True
        self.scramble_pool_layout.itemAt(idx).widget().setVisible(False)
        
        self.scramble_typed_chars.append({"char": char, "pool_idx": idx})
        self._update_input_display()
        
        if len(self.scramble_typed_chars) == self.target_word_len:
            self.check_answer()

    def handle_backspace(self):
        if not self.scramble_typed_chars:
            return
        last = self.scramble_typed_chars.pop()
        pool_idx = last["pool_idx"]
        self.scramble_tiles_data[pool_idx]["used"] = False
        self.scramble_pool_layout.itemAt(pool_idx).widget().setVisible(True)
        self._update_input_display()

    def handle_keypress(self, text: str):
        if len(self.scramble_typed_chars) >= self.target_word_len:
            return
            
        char = text.lower()
        # Bo'sh harfni qidiramiz
        for i, t in enumerate(self.scramble_tiles_data):
            if not t["used"] and t["char"] == char:
                self.on_tile_clicked(i)
                break

    def _update_input_display(self):
        t = getattr(self, "theme", None)
        active_border = t.primary if t else "#3B82F6"
        normal_border = t.border if t else "#4B5563"
        bg = t.bg_card if t else "#1A1A2E"
        fg = t.text_main if t else "white"
        
        for i in range(self.target_word_len):
            lbl = self.scramble_input_layout.itemAt(i).widget()
            if i < len(self.scramble_typed_chars):
                lbl.setText(self.scramble_typed_chars[i]["char"])
                lbl.setStyleSheet(f"border-bottom: 2px solid {active_border}; font-size: 20px; font-weight: bold; color: {fg}; background: {bg};")
            else:
                lbl.setText("")
                lbl.setStyleSheet(f"border-bottom: 2px solid {normal_border}; background: transparent;")

    def check_answer(self, **kwargs):
        if not self.current_word or len(self.scramble_typed_chars) < self.target_word_len:
            return
            
        typed_word = "".join([c["char"] for c in self.scramble_typed_chars])
        
        # Ota klass xizmat orqali tekshirish uchun string jo'natamiz
        # Lekin biz BasePracticeMode'da `is_correct` ni jo'natyapmiz, 
        # Shuning uchun bu yerda to'g'riligini aniqlaymiz:
        direction = getattr(self, "direction", "en_uz") # Default, aslidagi parent biladi
        target = self.current_word["english"] if direction == "en_uz" else self.current_word["uzbek"]
        
        is_correct = (typed_word.lower().strip() == target.lower().strip())
        
        # Vizual feedback
        color = "#10B981" if is_correct else "#EF4444"
        for i in range(self.target_word_len):
            lbl = self.scramble_input_layout.itemAt(i).widget()
            lbl.setStyleSheet(f"border-bottom: 2px solid {color}; font-size: 20px; font-weight: bold; color: {color}; background: transparent;")
            
        self.answer_submitted.emit(is_correct)

    def apply_theme(self, t):
        self.theme = t
        if not t: return
        
        btn_style = f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; border-radius: 8px; font-size: 18px; font-weight: 600; }} QPushButton:hover {{ background-color: {t.bg_card}; border: 1px solid {t.primary}; }}"
        
        for i in range(self.scramble_pool_layout.count()):
            w = self.scramble_pool_layout.itemAt(i).widget()
            if w:
                w.setStyleSheet(btn_style)
                
        self._update_input_display()
