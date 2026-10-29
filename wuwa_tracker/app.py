"""Entry point:  python -m wuwa_tracker.app   [--db path] [--import export.json]"""
from __future__ import annotations

import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="path to the SQLite database (default %%APPDATA%%\\WuwaTracker\\pulls.db)")
    ap.add_argument("--import", dest="imp", help="import a wuwatracker JSON export on start")
    ap.add_argument("--tray", action="store_true", help="start hidden in the system tray (used by 'start with Windows')")
    ap.add_argument("--tab", type=int, default=0, help=argparse.SUPPRESS)
    ap.add_argument("--screenshot", help=argparse.SUPPRESS)
    args = ap.parse_args()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .core.storage import Storage
    from .ui.main_window import MainWindow, app_icon
    from .ui.state import AppState
    from .ui.theme import QSS

    if sys.platform.startswith("win"):
        try:   # own taskbar icon/group instead of python.exe's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Nobodey11.WuwaPullTracker")
        except Exception:
            pass
    app = QApplication(sys.argv)
    if not args.screenshot and _hand_over(args.tray):     # already running: bring that window up instead
        return
    app.setApplicationName("WuWa Pull Tracker")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(QSS)

    storage = Storage(args.db)
    if args.imp:
        _, _, player = storage.import_wuwatracker_json(args.imp)
        storage.set_setting("player", player)
    state = AppState(storage)
    from PySide6.QtWidgets import QSystemTrayIcon
    hidden = args.tray and QSystemTrayIcon.isSystemTrayAvailable()
    win = MainWindow(state, start_hidden=hidden)
    win.tabs.setCurrentIndex(args.tab)
    _serve(win)
    if hidden:
        app.setQuitOnLastWindowClosed(False)
    else:
        win.show()
    try:
        from .core import autostart
        if autostart.supported():
            autostart.refresh()              # keep 'start with Windows' pointing at this installation
    except OSError:
        pass
    if args.screenshot:  # used for automated visual checks
        QTimer.singleShot(1500, lambda: (win.grab().save(args.screenshot), app.quit()))
    sys.exit(app.exec())


SERVER = "WuwaPullTracker-" + __import__("getpass").getuser()


def _hand_over(quiet: bool) -> bool:
    """True if another copy is running (it is asked to show its window unless this start was a quiet --tray start)."""
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(SERVER)
    if not s.waitForConnected(400):
        return False
    s.write(b"tray" if quiet else b"show")
    s.flush(); s.waitForBytesWritten(400); s.disconnectFromServer()
    return True


def _serve(win):
    from PySide6.QtNetwork import QLocalServer
    QLocalServer.removeServer(SERVER)          # stale server after a crash
    srv = QLocalServer(win)
    srv.listen(SERVER)

    def on_conn():
        c = srv.nextPendingConnection()
        if c is None:
            return
        c.waitForReadyRead(300)
        if bytes(c.readAll()) != b"tray":
            win.show_window()
        c.disconnectFromServer()
    srv.newConnection.connect(on_conn)
    win._single_instance = srv


if __name__ == "__main__":
    main()
