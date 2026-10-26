GOLD = "#f5c518"
PURPLE = "#b48cff"
BLUE = "#6aa9ff"
GREEN = "#2fbf71"
RED = "#e5484d"
ORANGE = "#e0a020"
BG = "#0e0f13"
CARD = "#181a20"
CARD2 = "#20232b"
TEXT = "#e8e8ec"
MUTED = "#9a9caa"
BORDER = "#2a2d36"

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
QPushButton#primary:hover {{ background: #ffd84a; }}
QPushButton:disabled {{ color: {MUTED}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit, QTextBrowser {{
    background: {CARD2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px;
    selection-background-color: {GOLD}; selection-color: #111; }}
QComboBox QAbstractItemView {{ background: {CARD2}; border: 1px solid {BORDER}; }}
QTableView {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; gridline-color: {BORDER};
             alternate-background-color: #1c1e25; }}
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
