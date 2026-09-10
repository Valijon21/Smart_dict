"""
Vocab Master Pro — Professional Vizual Mavzular Menejeri (Theme Manager).
6 ta zamonaviy, estetik va ko'zni charchatmaydigan ranglar palitrasi.
Dasturni qayta ishga tushirmasdan dinamik uslublarni yangilaydi.
"""
from dataclasses import dataclass
from typing import Callable
import database as db
from logger import get_logger

logger = get_logger("theme_manager")


@dataclass
class Theme:
    id: str
    name: str
    icon: str
    description: str
    bg_app: str             # Dastur orqa foni
    bg_sidebar: str         # Chap panel (Sidebar)
    bg_card: str            # Kartochkalar va modallar
    bg_card_secondary: str  # Ichki bloklar va panellar
    border: str             # Chegara chiziqlari
    primary: str            # Asosiy tugma va aksent
    primary_hover: str      # Sichqoncha ustiga borganda
    primary_light: str      # Och aksent (matnlar, nishonlar)
    text_main: str          # Asosiy matn
    text_muted: str         # Ikkinchi darajali matn
    accent: str             # Maxsus yorqin elementlar (streak, yutuqlar)
    swatch_colors: list[str] # Miniatyura uchun 3 ta rang
    is_dark: bool = True    # Qorong'u yoki yorug' mavzu ekanligi


THEMES = [
    Theme(
        id="midnight",
        name="Midnight Indigo",
        icon="🌌",
        description="Klassik chuqur qorong'ulik va binafsha-ko'k aksentlar",
        bg_app="#0F0F17",
        bg_sidebar="#151521",
        bg_card="#1E1E2E",
        bg_card_secondary="#171724",
        border="#2A2A3C",
        primary="#4F46E5",
        primary_hover="#4338CA",
        primary_light="#A5B4FC",
        text_main="#FFFFFF",
        text_muted="#9CA3AF",
        accent="#F59E0B",
        swatch_colors=["#0F0F17", "#1E1E2E", "#4F46E5"],
    ),
    Theme(
        id="cyberpunk",
        name="Cyberpunk Neon",
        icon="⚡",
        description="Futuristik elektrik moviy va neon fuksiya uyg'unligi",
        bg_app="#0B0B14",
        bg_sidebar="#110E1F",
        bg_card="#17142A",
        bg_card_secondary="#1E1838",
        border="#3B2354",
        primary="#06B6D4",
        primary_hover="#0891B2",
        primary_light="#67E8F9",
        text_main="#F8FAFC",
        text_muted="#A78BFA",
        accent="#F43F5E",
        swatch_colors=["#0B0B14", "#17142A", "#06B6D4"],
    ),
    Theme(
        id="emerald",
        name="Emerald Forest",
        icon="🌲",
        description="Sokin zumrad yashil va boy quyuq o'rmon foni",
        bg_app="#07120C",
        bg_sidebar="#0C1D13",
        bg_card="#122B1E",
        bg_card_secondary="#183827",
        border="#204E35",
        primary="#10B981",
        primary_hover="#059669",
        primary_light="#6EE7B7",
        text_main="#F0FDF4",
        text_muted="#86EFAC",
        accent="#F59E0B",
        swatch_colors=["#07120C", "#122B1E", "#10B981"],
    ),
    Theme(
        id="amber",
        name="Warm Sunset",
        icon="☕",
        description="Issiq qahva, shinam espresso va oltin amber nurlari",
        bg_app="#140E0A",
        bg_sidebar="#1C140F",
        bg_card="#261C15",
        bg_card_secondary="#33241A",
        border="#4A3425",
        primary="#D97706",
        primary_hover="#B45309",
        primary_light="#FDE68A",
        text_main="#FFFBEB",
        text_muted="#D4B499",
        accent="#EF4444",
        swatch_colors=["#140E0A", "#261C15", "#D97706"],
    ),
    Theme(
        id="oled",
        name="OLED Pure Black",
        icon="🖤",
        description="Mutlaq qora (#000) fon, kontrastli kumush va sovuq moviy",
        bg_app="#000000",
        bg_sidebar="#0D0D0D",
        bg_card="#151515",
        bg_card_secondary="#1F1F1F",
        border="#2D2D2D",
        primary="#38BDF8",
        primary_hover="#0284C7",
        primary_light="#BAE6FD",
        text_main="#FFFFFF",
        text_muted="#A1A1AA",
        accent="#10B981",
        swatch_colors=["#000000", "#151515", "#38BDF8"],
    ),
    Theme(
        id="nordic",
        name="Nordic Ocean",
        icon="🌊",
        description="Shimoliy qutb va chuqur okean moviyligi",
        bg_app="#0A1124",
        bg_sidebar="#0E1935",
        bg_card="#142347",
        bg_card_secondary="#1B2F5C",
        border="#26417A",
        primary="#3B82F6",
        primary_hover="#2563EB",
        primary_light="#93C5FD",
        text_main="#F8FAFC",
        text_muted="#94A3B8",
        accent="#38BDF8",
        swatch_colors=["#0A1124", "#142347", "#3B82F6"],
    ),
    Theme(
        id="dracula",
        name="Dracula Crimson",
        icon="🧛",
        description="Klassik Dracula to'q binafsha va qirmizi neonlar",
        bg_app="#1E1F29",
        bg_sidebar="#191A24",
        bg_card="#282A36",
        bg_card_secondary="#21222C",
        border="#44475A",
        primary="#BD93F9",
        primary_hover="#9B66E8",
        primary_light="#D6BAFF",
        text_main="#F8F8F2",
        text_muted="#6272A4",
        accent="#FF5555",
        swatch_colors=["#1E1F29", "#282A36", "#BD93F9"],
    ),
    Theme(
        id="light",
        name="Light Elegant",
        icon="☀️",
        description="Kunduzgi o'qish uchun toza oq va sokin qog'oz rejimi",
        bg_app="#F8FAFC",
        bg_sidebar="#F1F5F9",
        bg_card="#FFFFFF",
        bg_card_secondary="#F1F5F9",
        border="#E2E8F0",
        primary="#4F46E5",
        primary_hover="#4338CA",
        primary_light="#4338CA",
        text_main="#0F172A",
        text_muted="#64748B",
        accent="#D97706",
        swatch_colors=["#F8FAFC", "#FFFFFF", "#4F46E5"],
        is_dark=False,
    ),
]

_THEME_MAP = {t.id: t for t in THEMES}
_LISTENERS: list[Callable[[Theme], None]] = []


def get_all_themes() -> list[Theme]:
    return THEMES


def get_theme(theme_id: str) -> Theme:
    return _THEME_MAP.get(theme_id, THEMES[0])


FONT_SCALE_OPTIONS = {
    "normal": {"name": "Standart (14px)", "scale": 1.0, "base_px": 14, "base_pt": 10.0},
    "large": {"name": "Katta (16px / Qulay)", "scale": 1.15, "base_px": 16, "base_pt": 11.5},
    "xlarge": {"name": "Juda Katta (18px)", "scale": 1.3, "base_px": 18, "base_pt": 13.0},
}

_FONT_LISTENERS: list[Callable[[str], None]] = []


def get_font_scale() -> str:
    scale = db.get_setting("font_scale", "large")
    return scale if scale in FONT_SCALE_OPTIONS else "large"



def set_font_scale(scale_id: str):
    if scale_id not in FONT_SCALE_OPTIONS:
        scale_id = "normal"
    db.set_setting("font_scale", scale_id)
    logger.info(f"Yangi matn o'lchami o'rnatildi: {scale_id}")

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont
    app = QApplication.instance()
    if app:
        opt = FONT_SCALE_OPTIONS[scale_id]
        f = QFont("Segoe UI")
        f.setPointSizeF(opt["base_pt"])
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        app.setFont(f)

    active_theme = get_active_theme()
    for listener in _LISTENERS:
        try:
            listener(active_theme)
        except Exception as e:
            logger.error(f"Theme listener font yangilanishida xatolik: {e}")

    for fl in _FONT_LISTENERS:
        try:
            fl(scale_id)
        except Exception as e:
            logger.error(f"Font listener xatoligi: {e}")


def apply_current_font_scale():
    """Dastur ishga tushganda yoki oyna yaratilganda saqlangan font scaleni QApplication ga qo'llash."""
    scale_id = get_font_scale()
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont
    app = QApplication.instance()
    if app:
        opt = FONT_SCALE_OPTIONS.get(scale_id, FONT_SCALE_OPTIONS["normal"])
        f = QFont("Segoe UI")
        f.setPointSizeF(opt["base_pt"])
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        app.setFont(f)


def register_font_listener(callback: Callable[[str], None]):
    if callback not in _FONT_LISTENERS:
        _FONT_LISTENERS.append(callback)



def get_active_theme() -> Theme:
    active_id = db.get_setting("app_theme", "midnight")
    return get_theme(active_id)


def set_active_theme(theme_id: str):
    if theme_id not in _THEME_MAP:
        theme_id = "midnight"
    db.set_setting("app_theme", theme_id)
    theme = get_theme(theme_id)
    logger.info(f"Yangi vizual mavzu faollashtirildi: {theme.name} ({theme_id})")

    for listener in _LISTENERS:
        try:
            listener(theme)
        except Exception as e:
            logger.error(f"Mavzuni yangilash listenerida xatolik: {e}", exc_info=True)


def register_listener(callback: Callable[[Theme], None]):
    if callback not in _LISTENERS:
        _LISTENERS.append(callback)


def get_global_stylesheet(t: Theme) -> str:
    """Ilova uchun to'liq global QSS dizayn uslublari va tipografiya bazasi."""
    scale_id = get_font_scale()
    opt = FONT_SCALE_OPTIONS.get(scale_id, FONT_SCALE_OPTIONS["normal"])
    base_px = opt["base_px"]
    tip_px = max(12, base_px - 2)

    return f"""
    QMainWindow {{
        background-color: {t.bg_app};
    }}
    QWidget {{
        color: {t.text_main};
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        font-size: {base_px}px;
    }}
    QScrollBar:vertical {{
        border: none;
        background: {t.bg_app};
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border};
        min-height: 25px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.primary};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        border: none;
        background: {t.bg_app};
        height: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.border};
        min-width: 25px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {t.primary};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QToolTip {{
        background-color: {t.bg_card};
        color: {t.text_main};
        border: 1px solid {t.border};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: {tip_px}px;
    }}
    QMenu {{
        background-color: {t.bg_card};
        color: {t.text_main};
        border: 1px solid {t.border};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 16px;
        border-radius: 6px;
        color: {t.text_main};
        font-size: {tip_px}px;
    }}
    QMenu::item:selected {{
        background-color: {t.primary};
        color: white;
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {t.border};
        margin: 4px 8px;
    }}
    """



# Reusable QSS Helpers (DRY & Clean Code)
def card_style(t: Theme, radius: int = 12, border: bool = True) -> str:
    """Kartochkalar uchun standart QSS uslubi."""
    b_css = f"border: 1px solid {t.border};" if border else "border: none;"
    return f"background-color: {t.bg_card}; border-radius: {radius}px; {b_css}"


def btn_primary_style(t: Theme, radius: int = 8, padding: str = "8px 16px") -> str:
    """Asosiy harakat (Primary) tugmalari uchun standart QSS."""
    return (
        f"QPushButton {{ background-color: {t.primary}; color: white; border-radius: {radius}px; "
        f"padding: {padding}; font-weight: 600; border: none; }} "
        f"QPushButton:hover {{ background-color: {t.primary_hover}; }}"
    )


def btn_secondary_style(t: Theme, radius: int = 8, padding: str = "8px 14px") -> str:
    """Ikkinchi darajali (Secondary) tugmalar uchun standart QSS."""
    return (
        f"QPushButton {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
        f"border: 1px solid {t.border}; border-radius: {radius}px; padding: {padding}; font-weight: 600; }} "
        f"QPushButton:hover {{ background-color: {t.border}; }}"
    )


def input_style(t: Theme, radius: int = 8) -> str:
    """Matn kiritish (QLineEdit) elementlari uchun standart QSS."""
    return (
        f"QLineEdit {{ background-color: {t.bg_card_secondary}; color: {t.text_main}; "
        f"border: 1px solid {t.border}; border-radius: {radius}px; padding: 8px 12px; font-size: 13px; }} "
        f"QLineEdit:focus {{ border: 1px solid {t.primary}; }}"
    )

