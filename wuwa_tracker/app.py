"""Entry point:  python -m wuwa_tracker.app   [--db path] [--import export.json]"""
from __future__ import annotations

import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="path to the SQLite database (default %%APPDATA%%\\WuwaTracker\\pulls.db)")
    ap.add_argument("--import", dest="imp", help="import a wuwatracker JSON export on start")
    ap.add_argument("--tab", type=int, default=0, help=argparse.SUPPRESS)
    ap.add_argument("--screenshot", help=argparse.SUPPRESS)
    args = ap.parse_args()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .core.storage import Storage
    from .ui.main_window import MainWindow
    from .ui.state import AppState
    from .ui.theme import QSS

    app = QApplication(sys.argv)
    app.setApplicationName("WuWa Pull Tracker")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    storage = Storage(args.db)
    if args.imp:
        _, _, player = storage.import_wuwatracker_json(args.imp)
        storage.set_setting("player", player)
    state = AppState(storage)
    win = MainWindow(state)
    win.tabs.setCurrentIndex(args.tab)
    win.show()
    if args.screenshot:  # used for automated visual checks
        QTimer.singleShot(1500, lambda: (win.grab().save(args.screenshot), app.quit()))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
