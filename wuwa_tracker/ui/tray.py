"""System tray icon: reset timers in the tooltip, quick actions, and notifications (balloons)."""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .header import app_icon
from .i18n import tr


class Tray(QSystemTrayIcon):
    def __init__(self, window):
        super().__init__(app_icon(), window)
        self.win = window
        m = QMenu()
        self.a_show = QAction(tr("Show window"), m); self.a_show.triggered.connect(self.show_window)
        self.a_import = QAction(tr("Import now"), m); self.a_import.triggered.connect(lambda: window.import_game())
        self.a_quit = QAction(tr("Quit"), m); self.a_quit.triggered.connect(window.quit_app)
        self.a_status = QAction("", m); self.a_status.setEnabled(False)
        m.addAction(self.a_status)
        self.a_daily = QAction("", m); self.a_daily.setEnabled(False)
        self.a_weekly = QAction("", m); self.a_weekly.setEnabled(False)
        for a in (self.a_daily, self.a_weekly):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_show, self.a_import):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_quit)
        self.setContextMenu(m)
        self._menu = m
        self.activated.connect(self._activated)
        self.setToolTip("WuWa Pull Tracker")

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self):
        self.win.show_window()

    def set_status(self, text: str):
        self.a_status.setText(text)

    def set_resets(self, daily: str, weekly: str):
        self.a_daily.setText(f"{tr('Daily reset')}: {daily}")
        self.a_weekly.setText(f"{tr('Weekly reset')}: {weekly}")
        status = self.a_status.text()
        self.setToolTip(f"WuWa Pull Tracker" + (f"\n{status}" if status else "")
                        + f"\n{tr('Daily reset')}: {daily}\n{tr('Weekly reset')}: {weekly}")

    def notify(self, title: str, text: str, ms: int = 8000):
        if self.isVisible() and self.supportsMessages():
            self.showMessage(title, text, app_icon(), ms)
