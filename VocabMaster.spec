# -*- mode: python ; coding: utf-8 -*-
"""
Vocab Master Pro — Professional PyInstaller Build Specification.
Windows PE Version Info, Per-Monitor DPI Manifest, barcha Qt/Service plaginlari va
optimallashtirilgan exclude ro'yxati bilan to'liq jihozlangan.
"""
import os
import sys
from pathlib import Path

block_cipher = None

# Resurslar va statik ma'lumotlar
datas = [
    ('app_icon.png', '.'),
    ('app.ico', '.'),
    ('assets', 'assets'),
    ('sample_words.txt', '.'),
]

binaries = []

# Dinamik va yashirin importlar (Dynamic & Hidden Imports)
hiddenimports = [
    # PyQt6 Asosiy modullari
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtNetwork',        # Single Instance IPC server va socketlar uchun
    'PyQt6.QtMultimedia',     # Nutqni yozib olish va audio uchun
    'PyQt6.QtPrintSupport',    # Flashcards va test varaqlarini chop etish (QPrinter)
    'PyQt6.sip',

    # Windows Native COM & Audio
    'win32com.client',
    'pythoncom',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',

    # Hujjatlar bilan ishlash
    'docx',

    # Core Biznes Logikasi
    'core',
    'core.database',
    'core.fsrs',
    'core.gamification',
    'core.retention_analytics',
    'core.phonetics',
    'core.word_packs',
    'core.daily_quests',

    # Servis Qatlami
    'services',
    'services.tts_service',
    'services.speech_service',
    'services.sound_effects',
    'services.cefr_service',
    'services.topic_service',
    'services.clipboard_service',
    'services.global_dict_service',
    'services.game_word_provider',
    'services.daily_quests_service',
    'services.irregular_verbs_service',

    # Yordamchi vositalar
    'utils',
    'utils.logger',
    'utils.importer',
    'utils.reader_data',
    'utils.single_instance',
    'utils.text_search_utils',

    # UI Qatlami
    'ui',
    'ui.theme_manager',
    'ui.main_window',
    'ui.views',
    'ui.views.dashboard_view',
    'ui.views.dictionary_view',
    'ui.views.practice_view',
    'ui.views.practice_helpers',
    'ui.views.audio_player_view',
    'ui.views.reader_view',
    'ui.views.topic_words_view',
    'ui.views.settings_view',
    'ui.views.irregular_verbs_view',
    'ui.games',
    'ui.games.blitz_game',
    'ui.games.match_game',
    'ui.games.word_fall_game',
    'ui.games.crossword_game',
    'ui.dialogs',
    'ui.dialogs.word_packs_dialog',
    'ui.dialogs.quick_capture_dialog',
    'ui.dialogs.spotlight_search_dialog',
    'ui.dialogs.achievements_dialog',
    'ui.dialogs.worksheet_dialog',
    'ui.dialogs.import_dialog',
    'ui.components',
    'ui.components.mini_widget',
    'ui.components.daily_quests_widget',
    'ui.components.game_source_selector',

    # Root Shim Modullari (Backward Compatibility)
    'logger',
    'database',
    'tts',
    'theme_manager',
    'gamification',
    'phonetics',
    'retention_analytics',
    'sound_effects',
    'speech_recognizer',
    'topic_service',
    'word_packs',
    'daily_quests_service',
    'global_dict_service',
    'cefr_service',
    'clipboard_monitor',
    'reader_data',
    'importer',
    'text_search_utils',
]

# Ishlatilmaydigan og'ir kutubxonalarni chiqarib tashlash (EXE hajmini va ochilish tezligini optimallashtirish)
excludes = [
    'numpy',        # Loyihada sof Python wave/math/struct ishlatilgan, numpy kerak emas (~30MB tejaladi)
    'matplotlib',
    'scipy',
    'pandas',
    'tkinter',
    'IPython',
    'notebook',
    'pytest',
    '_pytest',
    'unittest',
    'lib2to3',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VocabMaster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # GUI ilovasi (orqa fonda qora konsol oynasi chiqmaydi)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],               # Ilova ikonkasi (Windows PE resursi)
    version='version_info.txt',     # Windows PE Version ma'lumotlari (Properties -> Details)
    manifest='app.manifest',        # DPI-Aware PerMonitorV2, UTF-8, UAC asInvoker manifest
)
