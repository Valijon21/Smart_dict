from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel
from PyQt6.QtCore import Qt
import re
from ui.views.practice.base_mode import BasePracticeMode

class ClozeModeWidget(BasePracticeMode):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.cloze_data = None
        
        self.cloze_layout = QHBoxLayout()
        self.cloze_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cloze_layout.setSpacing(8)
        self.layout.addLayout(self.cloze_layout)

        self.cloze_hint = QLabel("💡 Gapdagi tushirib qoldirilgan so'zni yozing va Enter bosing")
        self.cloze_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cloze_hint.setStyleSheet("color: #6B7280; font-size: 12px; margin-top: 10px;")
        self.layout.addWidget(self.cloze_hint)
        
        self.cloze_input = None

    def set_word(self, word_data, direction="en_uz", **kwargs):
        super().set_word(word_data, **kwargs)
        self.clear_ui()
        if not self.current_word:
            return
            
        ex = self.current_word.get("example", "")
        if not ex:
            return
            
        target = self.current_word["english"] if direction == "en_uz" else self.current_word["uzbek"]
        
        # Regex orqali so'zni topamiz va ajratamiz
        pattern = re.compile(re.escape(target), re.IGNORECASE)
        match = pattern.search(ex)
        
        if not match:
            # Agar aniq topilmasa, shunchaki xato qaytaramiz yoki boshqa narsa
            self.cloze_data = {"ex": ex, "target": target, "found": False}
            lbl = QLabel(ex)
            lbl.setStyleSheet("font-size: 18px;")
            self.cloze_layout.addWidget(lbl)
            return
            
        self.cloze_data = {
            "prefix": ex[:match.start()],
            "target": match.group(),
            "suffix": ex[match.end():],
            "found": True
        }
        
        if self.cloze_data["prefix"]:
            lbl1 = QLabel(self.cloze_data["prefix"])
            lbl1.setStyleSheet("font-size: 18px;")
            self.cloze_layout.addWidget(lbl1)
            
        self.cloze_input = QLineEdit()
        self.cloze_input.setFixedWidth(max(80, len(target) * 15))
        self.cloze_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cloze_input.returnPressed.connect(self.check_answer)
        self.cloze_layout.addWidget(self.cloze_input)
        
        if self.cloze_data["suffix"]:
            lbl2 = QLabel(self.cloze_data["suffix"])
            lbl2.setStyleSheet("font-size: 18px;")
            self.cloze_layout.addWidget(lbl2)
            
        self.apply_theme(getattr(self, "theme", None))

    def clear_ui(self):
        self.cloze_data = None
        self.cloze_input = None
        while self.cloze_layout.count():
            item = self.cloze_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def get_focus_widget(self):
        return self.cloze_input

    def check_answer(self, **kwargs):
        if not self.cloze_data or not self.cloze_data.get("found") or not self.cloze_input:
            return
            
        user_text = self.cloze_input.text().strip().lower()
        target = self.cloze_data["target"].lower()
        
        is_correct = (user_text == target)
        
        if is_correct:
            self.cloze_input.setStyleSheet("border: 2px solid #10B981; background-color: #064E3B; color: white; font-size: 18px;")
        else:
            self.cloze_input.setStyleSheet("border: 2px solid #EF4444; background-color: #7F1D1D; color: white; font-size: 18px;")
            
        self.cloze_input.setEnabled(False)
        self.answer_submitted.emit(is_correct)
        
    def apply_theme(self, t):
        self.theme = t
        if not t: return
        
        for i in range(self.cloze_layout.count()):
            w = self.cloze_layout.itemAt(i).widget()
            if isinstance(w, QLabel):
                w.setStyleSheet(f"font-size: 18px; color: {t.text_main};")
            elif isinstance(w, QLineEdit):
                w.setStyleSheet(f"QLineEdit {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 2px solid {t.border}; border-radius: 6px; padding: 4px; font-size: 18px; }} QLineEdit:focus {{ border: 2px solid {t.primary}; }}")
