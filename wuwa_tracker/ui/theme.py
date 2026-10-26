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
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QStatusBar {{ color: {MUTED}; background: {BG}; }}
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
