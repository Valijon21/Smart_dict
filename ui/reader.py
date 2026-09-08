"""
Vocab Master Pro — Aqlli O'qish Rejimi (Smart Reader).
Foydalanuvchiga matnlarni o'qish, bazadagi so'zlarni rangli ko'rish,
ustiga bosganda tarjimasini olish va yangi so'zlarni 1-bosish bilan lug'atga qo'shish imkonini beradi.
"""
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextBrowser, QFrame, QLineEdit, QSplitter,
    QTextEdit, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl, QTimer
import database as db
import tts
import reader_data
import theme_manager
import phonetics
from logger import get_logger

logger = get_logger("reader")


class CustomTextDialog(QDialog):
    """Foydalanuvchi o'z inglizcha matnini kiritishi uchun oyna."""
    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme_manager.get_active_theme()
        self.setWindowTitle("✍️ Shaxsiy matn kiritish")
        self.setFixedSize(540, 420)
        self.setStyleSheet(f"background-color: {t.bg_app}; color: {t.text_main}; border-radius: 12px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Inglizcha matn yoki maqolangizni joylashtiring:")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {t.text_main};")
        layout.addWidget(lbl)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Paste your English text here...")
        self.text_edit.setStyleSheet(
            f"background-color: {t.bg_card}; color: {t.text_main}; border: 1px solid {t.border}; "
            f"border-radius: 8px; padding: 10px; font-size: 13px;"
        )
        layout.addWidget(self.text_edit, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Bekor qilish")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "background-color: #2A2A3C; color: #9CA3AF; border-radius: 8px; padding: 7px 16px;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("O'qishni boshlash")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(
            "background-color: #4F46E5; color: white; font-weight: 600; border-radius: 8px; padding: 7px 18px;"
        )
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()


class ReaderWidget(QWidget):
    def __init__(self, on_words_changed=None, on_start_practice=None):
        super().__init__()
        self.on_words_changed = on_words_changed
        self.on_start_practice = on_start_practice
        self.current_story_content = ""
        self.dict_cache = {}  # {normalized_eng: dict}
        self.selected_word = ""
        self._is_playing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # 1. Sarlavha paneli
        header_row = QHBoxLayout()
        v_head = QVBoxLayout()
        title = QLabel("📖 Aqlli O'qish (Smart Reader)")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: 700;")
        v_head.addWidget(title)

        subtitle = QLabel("Matndagi so'zlarni bosing: tarjimasi chiqadi yoki 1-bosish bilan lug'atga qo'shiladi.")
        subtitle.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        v_head.addWidget(subtitle)
        header_row.addLayout(v_head)
        header_row.addStretch()

        # Legend
        self.legend_frame = QFrame()
        self.legend_frame.setStyleSheet("background-color: #1A1A28; border: 1px solid #2A2A3C; border-radius: 8px; padding: 2px 8px;")
        l_layout = QHBoxLayout(self.legend_frame)
        l_layout.setContentsMargins(8, 4, 8, 4)
        l_layout.setSpacing(12)

        dot_known = QLabel("● Bazangizdagi so'zlar")
        dot_known.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 600;")
        l_layout.addWidget(dot_known)

        dot_new = QLabel("○ Yangi so'zlar")
        dot_new.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        l_layout.addWidget(dot_new)

        header_row.addWidget(self.legend_frame)
        layout.addLayout(header_row)

        # 2. Boshqaruv paneli (Hikoyalar tanlash, TTS)
        self.control_frame = QFrame()
        self.control_frame.setStyleSheet("background-color: #1E1E2E; border-radius: 10px; border: 1px solid #2A2A3C;")
        ctrl_layout = QHBoxLayout(self.control_frame)
        ctrl_layout.setContentsMargins(14, 10, 14, 10)
        ctrl_layout.setSpacing(12)

        ctrl_layout.addWidget(QLabel("Hikoya:"))
        self.story_combo = QComboBox()
        self.story_combo.setStyleSheet(
            "QComboBox { background-color: #151521; color: white; border: 1px solid #374151; "
            "border-radius: 6px; padding: 6px 12px; min-width: 250px; font-weight: 500; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1E1E2E; color: white; selection-background-color: #4F46E5; }"
        )
        for s in reader_data.CURATED_STORIES:
            self.story_combo.addItem(f"{s['title']} ({s['level']})", s["id"])
        self.story_combo.addItem("✍️ Shaxsiy matn kiritish...", "custom")
        self.story_combo.currentIndexChanged.connect(self._on_story_changed)
        ctrl_layout.addWidget(self.story_combo)

        # Audio boshqaruv (Tinglash, Pauza, To'xtatish)
        self.speak_btn = QPushButton("🔊 Tinglash")
        self.speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speak_btn.clicked.connect(self._speak_all)
        ctrl_layout.addWidget(self.speak_btn)

        self.pause_btn = QPushButton("⏸ Pauza")
        self.pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_btn.clicked.connect(self._toggle_pause)
        ctrl_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹ To'xtatish")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self._stop_audio)
        ctrl_layout.addWidget(self.stop_btn)

        # Audio holatini kuzatuvchi taymer
        self._audio_timer = QTimer(self)
        self._audio_timer.setInterval(400)
        self._audio_timer.timeout.connect(self._check_audio_status)

        self._update_audio_ui(playing=False, paused=False)

        ctrl_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Tahlilni yangilash")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet(
            "QPushButton { background-color: #2A2A3C; color: #9CA3AF; border-radius: 6px; padding: 6px 12px; font-size: 12px; }"
            "QPushButton:hover { background-color: #374151; color: white; }"
        )
        self.refresh_btn.clicked.connect(self.refresh_reader)
        ctrl_layout.addWidget(self.refresh_btn)

        layout.addWidget(self.control_frame)

        # 3. Asosiy bo'linma (Splitter: Chapda matn, O'ngda so'z kartochkasi)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #2A2A3C; width: 2px; }")

        # Matn ko'ruvchi
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenLinks(False)
        self.text_browser.anchorClicked.connect(self._on_word_clicked)
        self.text_browser.setStyleSheet(
            """
            QTextBrowser {
                background-color: #1E1E2E;
                color: #E2E8F0;
                border: 1px solid #2A2A3C;
                border-radius: 12px;
                padding: 20px;
                font-size: 15px;
                line-height: 1.8;
                font-family: 'Segoe UI', sans-serif;
            }
            """
        )
        splitter.addWidget(self.text_browser)

        # O'ng panel: Tanlangan so'z inspektori (Word Inspector Card)
        self.inspector_panel = self._create_inspector_panel()
        splitter.addWidget(self.inspector_panel)
        splitter.setStretchFactor(0, 65)
        splitter.setStretchFactor(1, 35)

        layout.addWidget(splitter, 1)

        # Theme qo'llab-quvvatlash
        theme_manager.register_listener(self.apply_theme)
        self.apply_theme(theme_manager.get_active_theme())

        # Boshlang'ich yuklash
        self.load_story_by_index(0)

    def apply_theme(self, t: theme_manager.Theme):
        self.setStyleSheet(f"background-color: {t.bg_app};")
        if hasattr(self, "legend_frame"):
            self.legend_frame.setStyleSheet(f"background-color: {t.bg_card_secondary}; border: 1px solid {t.border}; border-radius: 8px; padding: 2px 8px;")
        if hasattr(self, "control_frame"):
            self.control_frame.setStyleSheet(f"background-color: {t.bg_card}; border-radius: 10px; border: 1px solid {t.border};")
        if hasattr(self, "story_combo"):
            self.story_combo.setStyleSheet(
                f"QComboBox {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; border: 1px solid {t.border}; "
                f"border-radius: 6px; padding: 6px 12px; min-width: 250px; font-weight: 500; }} "
                f"QComboBox::drop-down {{ border: none; }} "
                f"QComboBox QAbstractItemView {{ background-color: {t.bg_card}; color: {t.text_main}; selection-background-color: {t.primary}; }}"
            )
        if hasattr(self, "text_browser"):
            self.text_browser.setStyleSheet(
                f"""
                QTextBrowser {{
                    background-color: {t.bg_card};
                    color: {t.text_main};
                    border: 1px solid {t.border};
                    border-radius: 12px;
                    padding: 20px;
                    font-size: 15px;
                    line-height: 1.8;
                    font-family: 'Segoe UI', sans-serif;
                }}
                """
            )
        if hasattr(self, "inspector_panel"):
            self.inspector_panel.setStyleSheet(
                f"QFrame {{ background-color: {t.bg_card}; border: 1px solid {t.border}; border-radius: 12px; }}"
            )
        if hasattr(self, "known_container"):
            self.known_container.setStyleSheet(f"background-color: {t.bg_card_secondary}; border-radius: 8px; padding: 8px;")
        if hasattr(self, "new_container"):
            self.new_container.setStyleSheet(f"background-color: {t.bg_card_secondary}; border-radius: 8px; padding: 8px;")
        if hasattr(self, "new_uz_input"):
            self.new_uz_input.setStyleSheet(
                f"background-color: {t.bg_app}; color: {t.text_main}; border: 1px solid {t.border}; "
                f"border-radius: 6px; padding: 6px 10px; font-size: 13px;"
            )

    def _create_inspector_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame { background-color: #171724; border: 1px solid #2A2A3C; border-radius: 12px; }"
        )
        p_layout = QVBoxLayout(panel)
        p_layout.setContentsMargins(18, 18, 18, 18)
        p_layout.setSpacing(12)

        head_lbl = QLabel("🔍 So'z inspektori")
        head_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; font-weight: 600; text-transform: uppercase;")
        p_layout.addWidget(head_lbl)

        # So'z va audio qatori
        word_row = QHBoxLayout()
        self.insp_word_lbl = QLabel("So'zni tanlang")
        self.insp_word_lbl.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        word_row.addWidget(self.insp_word_lbl, 1)

        self.insp_tts_btn = QPushButton("🔊")
        self.insp_tts_btn.setFixedSize(36, 36)
        self.insp_tts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.insp_tts_btn.setStyleSheet(
            "QPushButton { background-color: #2A2A3C; border-radius: 8px; font-size: 16px; border: 1px solid #374151; }"
            "QPushButton:hover { background-color: #4F46E5; border-color: #6366F1; }"
        )
        self.insp_tts_btn.clicked.connect(self._speak_selected_word)
        self.insp_tts_btn.setVisible(False)
        word_row.addWidget(self.insp_tts_btn)
        p_layout.addLayout(word_row)

        # Fonetika (IPA) va So'z turkumi (POS) qatori
        self.insp_phonetic_container = QWidget()
        insp_ph_layout = QHBoxLayout(self.insp_phonetic_container)
        insp_ph_layout.setContentsMargins(0, 0, 0, 0)
        insp_ph_layout.setSpacing(6)

        self.insp_phonetic_lbl = QLabel("")
        self.insp_phonetic_lbl.setStyleSheet("color: #A5B4FC; font-size: 13px; font-weight: 500;")
        insp_ph_layout.addWidget(self.insp_phonetic_lbl)

        self.insp_pos_badge = QLabel("")
        self.insp_pos_badge.setStyleSheet(
            "background-color: #312E81; color: #C7D2FE; font-size: 10px; font-weight: 700; "
            "border-radius: 4px; padding: 1px 6px;"
        )
        insp_ph_layout.addWidget(self.insp_pos_badge)
        insp_ph_layout.addStretch()

        self.insp_phonetic_container.setVisible(False)
        p_layout.addWidget(self.insp_phonetic_container)

        # Holat nishonchasi
        self.insp_badge = QLabel("Matndagi istalgan so'z ustiga bosing")
        self.insp_badge.setStyleSheet("color: #6B7280; font-size: 12px;")
        self.insp_badge.setWordWrap(True)
        p_layout.addWidget(self.insp_badge)

        # 1. Mavjud so'z tafsilotlari (Known word container)
        self.known_container = QFrame()
        self.known_container.setStyleSheet("background-color: #12121C; border-radius: 8px; padding: 8px;")
        k_layout = QVBoxLayout(self.known_container)
        k_layout.setSpacing(8)

        self.known_uz_lbl = QLabel("")
        self.known_uz_lbl.setStyleSheet("color: #38BDF8; font-size: 15px; font-weight: 600;")
        self.known_uz_lbl.setWordWrap(True)
        k_layout.addWidget(self.known_uz_lbl)

        self.known_ex_lbl = QLabel("")
        self.known_ex_lbl.setStyleSheet("color: #FBBF24; font-size: 12px; font-style: italic;")
        self.known_ex_lbl.setWordWrap(True)
        k_layout.addWidget(self.known_ex_lbl)

        self.practice_btn = QPushButton("⚡ Ushbu so'zda mashq qilish")
        self.practice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.practice_btn.setStyleSheet(
            "QPushButton { background-color: #4F46E5; color: white; font-weight: 600; border-radius: 6px; padding: 6px; font-size: 12px; }"
            "QPushButton:hover { background-color: #4338CA; }"
        )
        self.practice_btn.clicked.connect(self._practice_current_word)
        k_layout.addWidget(self.practice_btn)

        self.known_container.setVisible(False)
        p_layout.addWidget(self.known_container)

        # 2. Yangi so'z qo'shish formasi (New word container)
        self.new_container = QFrame()
        self.new_container.setStyleSheet("background-color: #12121C; border-radius: 8px; padding: 8px;")
        n_layout = QVBoxLayout(self.new_container)
        n_layout.setSpacing(8)

        n_lbl = QLabel("O'zbekcha tarjimasini kiriting:")
        n_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        n_layout.addWidget(n_lbl)

        self.new_uz_input = QLineEdit()
        self.new_uz_input.setPlaceholderText("Tarjima...")
        self.new_uz_input.setStyleSheet(
            "background-color: #1E1E2E; color: white; border: 1px solid #374151; "
            "border-radius: 6px; padding: 6px 10px; font-size: 13px;"
        )
        self.new_uz_input.returnPressed.connect(self._add_selected_to_dict)
        n_layout.addWidget(self.new_uz_input)

        self.add_btn = QPushButton("➕ Lug'atga saqlash")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(
            "QPushButton { background-color: #10B981; color: white; font-weight: 600; border-radius: 6px; padding: 7px; font-size: 12px; }"
            "QPushButton:hover { background-color: #059669; }"
        )
        self.add_btn.clicked.connect(self._add_selected_to_dict)
        n_layout.addWidget(self.add_btn)

        self.new_container.setVisible(False)
        p_layout.addWidget(self.new_container)

        p_layout.addStretch()
        return panel

    def _load_dict_cache(self):
        words = db.get_all_words()
        self.dict_cache = {w["english"].strip().lower(): dict(w) for w in words}

    def _on_story_changed(self, index: int):
        self._stop_audio()
        data = self.story_combo.currentData()
        if data == "custom":
            dlg = CustomTextDialog(self)
            if dlg.exec():
                txt = dlg.get_text()
                if txt:
                    self.current_story_content = txt
                    self._render_text()
                else:
                    self.story_combo.setCurrentIndex(0)
            else:
                self.story_combo.setCurrentIndex(0)
        else:
            self.load_story_by_index(index)

    def load_story_by_index(self, index: int):
        if 0 <= index < len(reader_data.CURATED_STORIES):
            self.current_story_content = reader_data.CURATED_STORIES[index]["content"]
            self._render_text()

    def refresh_reader(self):
        self._render_text()

    def _render_text(self):
        self._load_dict_cache()
        if not self.current_story_content:
            self.text_browser.setHtml("<p style='color: #6B7280;'>Matn mavjud emas.</p>")
            return

        paragraphs = self.current_story_content.split("\n\n")
        html_paragraphs = []

        for p in paragraphs:
            p_html = self._format_paragraph_to_html(p)
            html_paragraphs.append(f"<p style='margin-bottom: 18px; line-height: 1.8;'>{p_html}</p>")

        full_html = (
            "<body style='font-family: \"Segoe UI\", Roboto, sans-serif; font-size: 15px; color: #E2E8F0;'>"
            + "".join(html_paragraphs)
            + "</body>"
        )
        self.text_browser.setHtml(full_html)

    def _format_paragraph_to_html(self, text: str) -> str:
        tokens = re.split(r"([a-zA-Z\'-]+)", text)
        result = []
        for t in tokens:
            if not t:
                continue
            clean_word = re.sub(r"[^a-zA-Z\'-]", "", t).strip("'- ").lower()
            if clean_word and len(clean_word) >= 2:
                # Bazadagi so'zmi? (asl yoki apostrofsiz shakli)
                dict_hit = clean_word in self.dict_cache or clean_word.replace("'", "") in self.dict_cache
                target_key = clean_word if clean_word in self.dict_cache else clean_word.replace("'", "")
                if dict_hit:
                    # Yoritilgan so'z (Siyan / Moviy)
                    result.append(
                        f"<a href='word:{target_key}' style='color: #38BDF8; font-weight: 600; "
                        f"text-decoration: underline; background-color: rgba(56, 189, 248, 0.12); "
                        f"padding: 1px 3px; border-radius: 4px;'>{t}</a>"
                    )
                else:
                    # Yangi so'z
                    result.append(
                        f"<a href='word:{clean_word}' style='color: #E2E8F0; text-decoration: none;'>{t}</a>"
                    )
            else:
                result.append(t)
        return "".join(result)

    def _on_word_clicked(self, url: QUrl):
        s = url.toString()
        if s.startswith("word:"):
            word = s[5:].strip().lower()
            self._inspect_word(word)

    def _inspect_word(self, word: str):
        self.selected_word = word
        self.insp_word_lbl.setText(word)
        self.insp_tts_btn.setVisible(True)

        # Fonetik va POS ma'lumotlarini yuklash
        ph_info = phonetics.get_word_info(word)
        ph_val = ph_info["phonetic"]
        pos_val = ph_info["part_of_speech"]

        if word in self.dict_cache:
            w_info = self.dict_cache[word]
            if w_info.get("phonetic"):
                ph_val = w_info["phonetic"]
            if w_info.get("part_of_speech"):
                pos_val = w_info["part_of_speech"]

            self.insp_badge.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 600;")
            self.insp_badge.setText(f"✅ Lug'atingizda bor (Status: {w_info.get('status', 'new')})")

            self.known_uz_lbl.setText(f"Tarjimasi: {w_info.get('uzbek', '')}")
            ex = w_info.get('example', '')
            if ex:
                self.known_ex_lbl.setText(f"💡 Misol: {ex}")
                self.known_ex_lbl.setVisible(True)
            else:
                self.known_ex_lbl.setVisible(False)

            self.known_container.setVisible(True)
            self.new_container.setVisible(False)
        else:
            self.insp_badge.setStyleSheet("color: #F59E0B; font-size: 11px; font-weight: 600;")
            self.insp_badge.setText("🆕 Yangi so'z (Bazangizda yo'q)")

            self.known_container.setVisible(False)
            self.new_container.setVisible(True)
            self.new_uz_input.clear()
            self.new_uz_input.setFocus()

        self.insp_phonetic_lbl.setText(ph_val)
        self.insp_pos_badge.setText(f"[{pos_val}]")
        self.insp_phonetic_container.setVisible(True)

        # Ovozni avtomatik eshittirish
        if hasattr(self, "_audio_timer") and self._audio_timer.isActive():
            self._update_audio_ui(playing=False, paused=False)
            self._audio_timer.stop()
        tts.speak_async(word)

    def _speak_selected_word(self):
        if self.selected_word:
            tts.speak_async(self.selected_word)

    def _add_selected_to_dict(self):
        uz = self.new_uz_input.text().strip()
        if not self.selected_word or not uz:
            return

        word_id = db.add_word(self.selected_word, uz, source="smart_reader")
        if word_id:
            if self.on_words_changed:
                self.on_words_changed()
            self._render_text()
            self._inspect_word(self.selected_word)

    def _practice_current_word(self):
        if self.selected_word in self.dict_cache:
            w_id = self.dict_cache[self.selected_word]["id"]
            if self.on_start_practice:
                self.on_start_practice([w_id])

    def _speak_all(self):
        if not self.current_story_content:
            return

        if tts.is_paused():
            tts.resume()
            self._is_playing = True
            self._update_audio_ui(playing=True, paused=False)
            logger.info("Smart Reader: Pauzadan davom ettirildi")
        else:
            logger.info(f"Smart Reader: Butun matnni tinglash boshlandi ({len(self.current_story_content)} belgi)")
            self._is_playing = True
            tts.speak_async(self.current_story_content)
            self._update_audio_ui(playing=True, paused=False)
        self._audio_timer.start()

    def _toggle_pause(self):
        """Pauza va Davom etish (Pause/Resume) holatini almashtirish."""
        if tts.is_paused():
            tts.resume()
            self._is_playing = True
            self._update_audio_ui(playing=True, paused=False)
            logger.info("Smart Reader: 'Davom etish' bosildi — qolgan joyidan davom ettirildi")
        elif self._is_playing or tts.is_speaking():
            tts.pause()
            self._is_playing = False
            self._update_audio_ui(playing=True, paused=True)
            logger.info("Smart Reader: 'Pauza' bosildi — o'qish to'xtatildi")
        else:
            self._speak_all()

    def _stop_audio(self):
        """Ovoz ijrosini to'liq to'xtatish."""
        if self._is_playing or tts.is_speaking() or tts.is_paused():
            logger.info("Smart Reader: Foydalanuvchi ovoz ijrosini to'xtatdi")
            self._is_playing = False
            tts.stop()
        self._update_audio_ui(playing=False, paused=False)
        self._audio_timer.stop()

    def _check_audio_status(self):
        """Audio tabiiy ravishda tugaganda tugmalarni dastlabki holatga qaytarish."""
        if not tts.is_speaking() and not tts.is_paused():
            self._is_playing = False
            self._update_audio_ui(playing=False, paused=False)
            self._audio_timer.stop()

    def _update_audio_ui(self, playing: bool, paused: bool):
        """Audio holatiga qarab tugmalar matni va uslublarini dinamik yangilash."""
        if paused:
            self.pause_btn.setText("▶ Davom etish")
            self.pause_btn.setStyleSheet(
                "QPushButton { background-color: #D97706; color: white; border: 1px solid #F59E0B; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 700; }"
                "QPushButton:hover { background-color: #B45309; }"
            )
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.speak_btn.setText("🔊 Boshidan")
            self.speak_btn.setStyleSheet(
                "QPushButton { background-color: #1E1E2E; color: #9CA3AF; border: 1px solid #374151; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background-color: #374151; color: white; }"
            )
        elif playing:
            self.pause_btn.setText("⏸ Pauza")
            self.pause_btn.setStyleSheet(
                "QPushButton { background-color: #3730A3; color: #C7D2FE; border: 1px solid #4F46E5; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background-color: #4F46E5; color: white; }"
            )
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.speak_btn.setText("🔊 Boshidan")
            self.speak_btn.setStyleSheet(
                "QPushButton { background-color: #1E1E2E; color: #9CA3AF; border: 1px solid #374151; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background-color: #374151; color: white; }"
            )
        else:
            self.pause_btn.setText("⏸ Pauza")
            self.pause_btn.setStyleSheet(
                "QPushButton { background-color: #1A1A28; color: #4B5563; border: 1px solid #2A2A3C; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            )
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.speak_btn.setText("🔊 Butun matnni tinglash")
            self.speak_btn.setStyleSheet(
                "QPushButton { background-color: #4F46E5; color: white; border: none; "
                "border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; }"
                "QPushButton:hover { background-color: #4338CA; }"
            )

    def hideEvent(self, event):
        """Boshqa sahifaga o'tilganda ovozni to'xtatish."""
        self._stop_audio()
        super().hideEvent(event)
