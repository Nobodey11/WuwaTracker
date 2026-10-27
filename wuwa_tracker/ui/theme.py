"""Colours and the Qt stylesheet. Two palettes; the choice is read once at start-up (Settings → Appearance)."""
from ..core.paths import ui_prefs

PALETTES = {
    "dark": dict(GOLD="#f5c518", PURPLE="#b48cff", BLUE="#6aa9ff", GREEN="#2fbf71", RED="#e5484d", ORANGE="#e0a020",
                 BG="#0e0f13", CARD="#181a20", CARD2="#20232b", TEXT="#e8e8ec", MUTED="#9a9caa", BORDER="#2a2d36",
                 ALT="#1c1e25", ON_ACCENT="#111111"),
    "light": dict(GOLD="#c99700", PURPLE="#7b4fd6", BLUE="#2f6fd6", GREEN="#1f9d5a", RED="#d13438", ORANGE="#c47f00",
                  BG="#f3f4f7", CARD="#ffffff", CARD2="#eceef3", TEXT="#1b1d24", MUTED="#5d6170", BORDER="#d6d9e1",
                  ALT="#f6f7fa", ON_ACCENT="#111111"),
}
NAME = ui_prefs().get("theme", "dark")
if NAME not in PALETTES:
    NAME = "dark"
_P = PALETTES[NAME]
GOLD, PURPLE, BLUE, GREEN, RED, ORANGE = (_P[k] for k in ("GOLD", "PURPLE", "BLUE", "GREEN", "RED", "ORANGE"))
BG, CARD, CARD2, TEXT, MUTED, BORDER, ALT = (_P[k] for k in ("BG", "CARD", "CARD2", "TEXT", "MUTED", "BORDER", "ALT"))
DARK = NAME == "dark"

QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QWidget#root, QDialog, QMessageBox, QInputDialog {{ background: {BG}; }}
QTabWidget::pane {{ border: none; background: {BG}; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 10px 18px; border: none;
               border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {GOLD}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#bannerCard {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#bannerCard[selected="true"] {{ border: 1px solid {GOLD}; background: {CARD2}; }}
QLabel#h1 {{ font-size: 15pt; font-weight: 700; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#big {{ font-size: 30pt; font-weight: 800; color: {GOLD}; }}
QPushButton {{ background: {CARD2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {GOLD}; }}
QPushButton#primary {{ background: {GOLD}; color: #111; font-weight: 700; border: none; }}
QPushButton#primary:hover {{ background: {GOLD}; border: 1px solid {TEXT}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QPlainTextEdit, QTextEdit, QTextBrowser {{
    background: {CARD2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px;
    selection-background-color: {GOLD}; selection-color: #111; }}
QComboBox QAbstractItemView {{ background: {CARD2}; border: 1px solid {BORDER}; }}
QDateEdit:disabled, QSpinBox:disabled {{ color: {MUTED}; }}
QCalendarWidget QWidget {{ background: {CARD2}; color: {TEXT}; }}
QCalendarWidget QAbstractItemView:enabled {{ background: {CARD}; color: {TEXT}; selection-background-color: {GOLD};
                                            selection-color: #111; }}
QCalendarWidget QToolButton {{ background: transparent; color: {TEXT}; }}
QTabWidget#subtabs::pane {{ border: none; }}
QTableView {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; gridline-color: {BORDER};
             alternate-background-color: {ALT}; }}
QHeaderView::section {{ background: {CARD}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
                        padding: 6px; font-weight: 600; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget#scrollInner {{ background: transparent; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QStatusBar {{ color: {MUTED}; background: {BG}; }}
/* ---------- header ---------- */
QWidget#topbar {{ background: {CARD}; border-bottom: 1px solid {BORDER}; min-height: 54px; max-height: 54px; }}
QLabel#wordmark {{ font-size: 13pt; font-weight: 800; color: {TEXT}; background: transparent; }}
QLabel#plain {{ background: transparent; }}
QTabBar#nav {{ background: transparent; border: none; }}
QTabBar#nav::tab {{ background: transparent; color: {MUTED}; padding: 17px 14px 15px 14px; margin: 0 2px;
                    border: none; border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar#nav::tab:hover {{ color: {TEXT}; }}
QTabBar#nav::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {GOLD}; }}
QComboBox#pill {{ background: {CARD2}; border: 1px solid {BORDER}; border-radius: 15px; padding: 4px 12px; min-height: 20px; }}
QToolButton#menuBtn {{ background: {CARD2}; border: 1px solid {BORDER}; border-radius: 15px; min-width: 30px;
                       min-height: 30px; font-size: 13pt; color: {TEXT}; }}
QToolButton#menuBtn:hover {{ border-color: {GOLD}; }}
QToolButton#menuBtn::menu-indicator {{ image: none; width: 0; }}
QWidget#strip {{ background: {BG}; border-bottom: 1px solid {BORDER}; min-height: 30px; max-height: 30px; }}
QLabel#stripText {{ color: {MUTED}; font-size: 9pt; background: transparent; }}
QPushButton#chip {{ background: transparent; border: 1px solid {BORDER}; border-radius: 10px; padding: 1px 10px;
                    color: {MUTED}; font-size: 9pt; }}
QPushButton#chip:hover {{ color: {TEXT}; border-color: {GOLD}; }}
QMenu::section {{ color: {MUTED}; padding: 6px 12px 2px 12px; font-size: 8pt; font-weight: 700; background: transparent; }}
QMenuBar {{ background: {CARD}; color: {TEXT}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item {{ padding: 4px 12px; background: transparent; }}
QMenuBar::item:selected {{ background: {CARD2}; }}
QMenu {{ background: {CARD2}; border: 1px solid {BORDER}; }}
QMenu::item {{ padding: 6px 24px; }}
QMenu::item:selected {{ background: {GOLD}; color: #111; }}
QToolTip {{ background: {CARD2}; color: {TEXT}; border: 1px solid {BORDER}; }}
"""


def pity_color(pity: int) -> str:
    """Green = early (lucky), orange = mid, red = late — like wuwatracker."""
    if pity <= 50:
        return GREEN
    if pity <= 65:
        return ORANGE
    return RED
