"""Main window: header + status strip + pages. Import/export actions live in import_flow.py, background
workers in background.py, the header widgets in header.py and the tray icon in tray.py."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMenu, QMessageBox, QSystemTrayIcon, QTabWidget, \
    QVBoxLayout, QWidget

from .. import __version__
from ..core import game_import, paths
from . import theme as T
from .assistant_tab import AssistantTab
from .background import AppUpdateWorker, GameDataUpdateWorker, LogWatchWorker
from .calculator_tab import CalculatorTab
from .calendar_tab import CalendarTab
from .codes_tab import CodesTab
from .collection_tab import CollectionTab
from .header import StatusStrip, TopBar, app_icon, fmt_td, next_resets  # noqa: F401  (re-exported)
from .history_tab import HistoryTab
from .i18n import tr
from .import_flow import ImportActions
from .new_content_dialog import NewContentDialog
from .overview_tab import OverviewTab
from .planner_tab import PlannerTab
from .prydwen_tab import PrydwenTab
from .settings_tab import SettingsTab
from .simulator_tab import SimulatorTab


class MainWindow(ImportActions, QMainWindow):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._quitting = False
        self.watcher = None
        self.setWindowTitle("WuWa Pull Tracker")
        self.resize(1440, 900)

        root = QWidget(); root.setObjectName("root")
        v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        self.top = TopBar()
        self.strip = StatusStrip()
        self.nav, self.player, self.menu_btn = self.top.nav, self.top.player, self.top.menu_btn
        v.addWidget(self.top)
        v.addWidget(self.strip)

        status = lambda m: self.statusBar().showMessage(m, 8000)
        self.tabs = QTabWidget()
        self.codes_tab = CodesTab(state, lambda m: self.statusBar().showMessage(m, 15000))
        self.settings_tab = SettingsTab(state, status, self.check_gamedata, self.apply_automation)
        pages = [
            (OverviewTab(state), "Tracker"),
            (HistoryTab(state), "Pull History"),
            (CalculatorTab(state), "Probability"),
            (PlannerTab(state), "Planner"),
            (CollectionTab(state), "Collection"),
            (CalendarTab(state), "Calendar"),
            (PrydwenTab(state), "Prydwen"),
            (SimulatorTab(state), "Simulator"),
            (self.codes_tab, "Codes"),
            (AssistantTab(state), "AI"),
            (self.settings_tab, "Settings"),
        ]
        for w, name in pages:
            self.tabs.addTab(w, tr(name))
        v.addWidget(self.tabs)
        self.setCentralWidget(root)
        # the nav bar in the header drives the pages; the QTabWidget's own bar is hidden
        self.tabs.tabBar().hide()
        self.tabs.setDocumentMode(True)
        for i in range(self.tabs.count()):
            self.nav.addTab(self.tabs.tabText(i))
        self.nav.currentChanged.connect(self.tabs.setCurrentIndex)
        self.tabs.currentChanged.connect(lambda i: self.nav.currentIndex() != i and self.nav.setCurrentIndex(i))
        self.codes_tab.new_codes.connect(self._codes_badge)
        self.setWindowIcon(app_icon())

        self.strip.gd_chip.clicked.connect(self.about_gamedata)
        self.strip.update_chip.clicked.connect(self.open_release)
        self.strip.watch_chip.clicked.connect(lambda: self.tabs.setCurrentWidget(self.settings_tab))
        self.strip.ending_chip.clicked.connect(lambda: self.tabs.setCurrentIndex(5))

        self._menu()
        self.player.currentIndexChanged.connect(lambda _: self.change_player(self.player.currentData()))
        state.changed.connect(self.refresh_players)
        state.changed.connect(self.refresh_gd_label)
        self.refresh_players()
        self.refresh_gd_label()

        # tray
        from .tray import Tray
        self.tray = Tray(self) if QSystemTrayIcon.isSystemTrayAvailable() else None
        self.release = None

        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(1000)
        self.slow = QTimer(self); self.slow.timeout.connect(self.slow_tick); self.slow.start(60_000)
        self.tick()
        if not state.pulls:
            QTimer.singleShot(300, lambda: self.statusBar().showMessage(
                "No data yet: ☰ menu → Import wuwatracker JSON… (Ctrl+O) or Import from game (Ctrl+G)."))
        if state.get("gamedata_autocheck") and state.get("gamedata_url"):
            QTimer.singleShot(800, lambda: self.check_gamedata(False))
        QTimer.singleShot(1200, lambda: self.ask_new_content(only_if_any=True))
        QTimer.singleShot(1500, self.apply_automation)
        QTimer.singleShot(2500, lambda: self.check_app_update(False))
        QTimer.singleShot(3000, self.slow_tick)
        QTimer.singleShot(3500, self.maybe_weekly_summary)
        QTimer.singleShot(400, self._check_lock)

    # ---------------------------------------------------------------- menu
    def _menu(self):
        self.menuBar().hide()
        menu = QMenu(self)

        def add(text, fn, shortcut=None, parent=menu):
            a = QAction(tr(text), self); a.triggered.connect(fn)
            if shortcut:
                a.setShortcut(shortcut)
                self.addAction(a)          # keep the shortcut working with the menu closed
            parent.addAction(a)
            return a
        menu.addSection(tr("Data"))
        add("Import wuwatracker JSON…", self.import_json, "Ctrl+O")
        add("Import from game…", self.import_game, "Ctrl+G")
        exp = menu.addMenu(tr("Export…"))
        add("Export wuwatracker JSON…", self.export_json, parent=exp)
        add("Export CSV…", self.export_csv, parent=exp)
        add("Export Excel…", self.export_xlsx, "Ctrl+E", parent=exp)
        add("Compare with a wuwatracker export…", self.compare_export)
        add("Backups…", self.show_backups, "Ctrl+B")
        menu.addSection(tr("Game data"))
        add("Check for game data updates", lambda: self.check_gamedata(True), "F5")
        add("Classify new content…", lambda: self.ask_new_content(only_if_any=False))
        add("About game data…", self.about_gamedata)
        menu.addSection(tr("My account"))
        add("Rename this account…", self.rename_account)
        add("Owned outside pulls (gifts, free units)…", self.edit_extras)
        add("Delete this account's data…", self.clear)
        menu.addSection(tr("App"))
        add("Weekly summary…", self.weekly_summary, "Ctrl+W")
        add("Save share image…", self.save_share_image, "Ctrl+Shift+S")
        add("Check for app updates", lambda: self.check_app_update(True))
        add("About / disclaimer…", self.about)
        add("Exit", self.quit_app, "Ctrl+Q")
        self.menu_btn.setMenu(menu)

    def _codes_badge(self, n):
        i = self.tabs.indexOf(self.codes_tab)
        prev = getattr(self, "_codes_n", None)
        self.nav.setTabText(i, f"{tr('Codes')}  🎁{n}" if n else tr("Codes"))
        if prev is not None and n > prev and self.state.get("notify_codes"):
            self.notify("New redemption code", f"{n} code(s) still to redeem. Open the Codes tab to copy them.")
        self._codes_n = n

    def edit_extras(self):
        from .extras_dialog import ExtrasDialog
        ExtrasDialog(self.state, self).exec()

    # ---------------------------------------------------------------- notifications / tray
    def notify(self, title: str, text: str):
        if self.tray is not None and self.tray.isVisible():
            self.tray.notify(title, text)
        else:
            self.statusBar().showMessage(f"{title}: {text}", 15000)

    def apply_automation(self):
        """(Re)start the tray icon and the log watcher according to the settings."""
        if self.tray is not None:
            self.tray.setVisible(bool(self.state.get("tray")))
        want = bool(self.state.get("auto_import"))
        if want and self.watcher is None:
            self.watcher = LogWatchWorker(self.state.get("game_dir") or None)
            self.watcher.link_found.connect(self._auto_link)
            self.watcher.status.connect(lambda s: self.strip.watch_chip.setToolTip(s))
            self.watcher.start()
            self.strip.watch_chip.setText("● Auto-import on")
            self.strip.watch_chip.setToolTip("Open Convene → History in the game and new pulls are imported automatically.")
            self.strip.watch_chip.show()
        elif not want and self.watcher is not None:
            self.watcher.stop(); self.watcher.wait(2000)
            self.watcher = None
            self.strip.watch_chip.hide()

    def _auto_link(self, url):
        self.statusBar().showMessage("New Convene history link found in the game log: importing…", 8000)
        self.import_game(url=url, auto=True)

    def closeEvent(self, ev):
        if not self._quitting and self.state.get("close_to_tray") and self.tray is not None and self.tray.isVisible():
            ev.ignore()
            self.hide()
            self.tray.notify("Still running", "WuWa Pull Tracker keeps running in the tray. Right-click the icon to quit.")
            return
        self._shutdown()
        super().closeEvent(ev)

    def quit_app(self):
        self._quitting = True
        self.close()
        QApplication.quit()

    def _shutdown(self):
        if self.watcher is not None:
            self.watcher.stop(); self.watcher.wait(2000)
            self.watcher = None
        if self.tray is not None:
            self.tray.hide()
        paths.release_lock(self.state.data_dir)

    def _check_lock(self):
        other = paths.acquire_lock(self.state.data_dir)
        if other:
            QMessageBox.warning(self, "Data folder in use",
                                f"The data folder is also in use on {other}.\n\nIf both PCs change the data at the same "
                                "time (e.g. via OneDrive), one set of changes can be lost. Close the app on the other "
                                "PC to be safe.")
            paths.heartbeat(self.state.data_dir)

    # ---------------------------------------------------------------- timers
    def offset(self) -> float:
        return game_import.SERVER_UTC_OFFSET.get(self.state.get("server_region"), 8)

    def tick(self):
        self.strip.set_resets(self.offset())
        if self.tray is not None and self.tray.isVisible():
            d, w = next_resets(self.offset())
            self.tray.set_resets(fmt_td(d), fmt_td(w))

    def slow_tick(self):
        """Every minute: lock heartbeat and banner-ending alerts."""
        paths.heartbeat(self.state.data_dir)
        from ..core import calendar
        now = datetime.now(timezone.utc)
        try:
            entries = calendar.build(self.state.gd.raw, self.state.prydwen.cached_banners() if self.state.prydwen_on()
                                     else [], self.state.get("user_events"), self.state.get("server_region"),
                                     self.offset(), now)
        except Exception:
            return
        soon = calendar.ending_soon(entries, now)
        if soon:
            first = min(soon, key=lambda e: e.end)
            self.strip.ending_chip.setText(f"⏳ {first.title} ends in {fmt_td(first.end - now)}"
                                           + (f"  (+{len(soon) - 1})" if len(soon) > 1 else ""))
            self.strip.ending_chip.setToolTip("\n".join(f"{e.title}: {e.end.astimezone():%a %d %b %H:%M}" for e in soon))
            self.strip.ending_chip.show()
        else:
            self.strip.ending_chip.hide()
        if self.state.get("notify_banners"):
            seen = list(self.state.get("notified") or [])
            for e in soon:
                nid = f"{e.kind}|{e.title}|{e.end:%Y-%m-%d}"
                if nid not in seen:
                    self.notify(f"{e.title} ends soon", f"{e.kind.capitalize()} ends in {fmt_td(e.end - now)} "
                                                        f"({e.end.astimezone():%a %d %b %H:%M}).")
                    seen.append(nid)
            if seen != (self.state.get("notified") or []):
                self.state.set("notified", seen[-60:])

    # ---------------------------------------------------------------- updates
    def check_app_update(self, manual: bool):
        if not manual:
            if not self.state.get("update_check") or time.time() - (self.state.get("last_update_check") or 0) < 20 * 3600:
                return
        self.state.set("last_update_check", time.time())
        self.uw = AppUpdateWorker(__version__)
        self.uw.done.connect(lambda ok, rel: self._on_app_update(ok, rel, manual))
        self.uw.start()

    def _on_app_update(self, available, rel, manual):
        if isinstance(rel, str):
            if manual:
                QMessageBox.information(self, "App update", rel)
            return
        if available:
            self.release = rel
            self.strip.update_chip.setText(f"⬆ Update {rel['tag']} available")
            self.strip.update_chip.setToolTip(rel.get("name", "") + "\nClick to open the release page.")
            self.strip.update_chip.show()
            if manual:
                self.open_release()
            else:
                self.notify("Update available", f"WuWa Pull Tracker {rel['tag']} is out.")
        elif manual:
            QMessageBox.information(self, "App update", f"You have the latest version ({__version__}).")

    def open_release(self):
        from ..core.updates import RELEASES
        url = (self.release or {}).get("url") or RELEASES
        if self.release and self.release.get("notes"):
            box = QMessageBox(self); box.setWindowTitle(f"Update {self.release['tag']}")
            box.setTextFormat(Qt.MarkdownText)
            box.setText(f"**{self.release['name']}**\n\n{self.release['notes'][:1500]}")
            b = box.addButton("Open release page", QMessageBox.AcceptRole); box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() is not b:
                return
        QDesktopServices.openUrl(QUrl(url))

    # ---------------------------------------------------------------- game data
    def refresh_gd_label(self):
        gd = self.state.gd
        items, pools = self.state.unknown_content()
        stale = not gd.current_banners()
        flag = " ⚠" if (items or pools or stale) else ""
        self.strip.gd_chip.setText(f"Patch {gd.patch}  ·  data v{gd.version}{flag}")
        self.strip.gd_chip.setToolTip("Game data is out of date or has unclassified items — click for details." if flag else
                                      f"Game data source: {gd.source}")

    def check_gamedata(self, manual: bool):
        url = self.state.get("gamedata_url")
        if not url:
            if manual:
                QMessageBox.information(self, "Game data", "Set an update URL in Settings → Game data first.\n\n"
                                        "Without a URL the app still detects new characters/banners from your pulls "
                                        "and asks you to classify them.")
            return
        self.statusBar().showMessage("Checking for game data updates…", 5000)
        self.gdw = GameDataUpdateWorker(self.state.gd_store, url)
        self.gdw.done.connect(lambda updated, msg: self.on_gamedata_checked(updated, msg, manual))
        self.gdw.start()

    def on_gamedata_checked(self, updated, msg, manual):
        if updated or manual:          # silent when an automatic check finds nothing / is offline
            self.statusBar().showMessage(msg, 10000)
        if updated:
            self.state.reload_gamedata()
            self.ask_new_content(only_if_any=True)
        elif manual:
            QMessageBox.information(self, "Game data", msg)

    def ask_new_content(self, only_if_any=True):
        items, pools = self.state.unknown_content()
        if not items and not pools:
            if not only_if_any:
                QMessageBox.information(self, "Game data", "Everything in your pulls is already known. 👍")
            return
        dlg = NewContentDialog(items, pools, self)
        if dlg.exec():
            dlg.apply(self.state.gd_store)
            self.state.reload_gamedata()
            self.statusBar().showMessage("New content saved to your game data.", 8000)

    def about_gamedata(self):
        gd = self.state.gd
        cur = ", ".join(f"{b['patch']} P{b.get('phase')}" for b in gd.current_banners()) or "none (out of date)"
        QMessageBox.information(self, "Game data",
                                f"Version: {gd.version}\nGame patch: {gd.patch}\nSource: {gd.source}\n"
                                f"Current banner phase: {cur}\nKnown 5✦ items: {len(gd.known_5stars)}\n"
                                f"Banner types: {len(gd.raw['banner_types'])}\n\n"
                                f"Folder: {self.state.gd_store.app_dir}")

    # ---------------------------------------------------------------- misc
    def about(self):
        QMessageBox.about(self, "About WuWa Pull Tracker",
            f"<h3>WuWa Pull Tracker {__version__}</h3>"
            "<p>Unofficial fan project, <b>strictly for personal use</b>.</p>"
            "<p>Based on the <a href='https://wuwatracker.com'>WuWa Tracker</a> pull tracker, but <b>not affiliated "
            "with, endorsed by or connected to WuWa Tracker, Prydwen.gg or Kuro Games</b>.</p>"
            "<p>Tier lists, ratings, banner info and images from "
            "<a href='https://www.prydwen.gg/wuthering-waves'>Prydwen.gg</a> belong to Prydwen.gg. Wuthering Waves "
            "names and art © Kuro Games.</p><p>Odds are estimates; provided as is, without warranty.</p>"
            "<p><a href='https://github.com/Nobodey11/WuwaTracker'>github.com/Nobodey11/WuwaTracker</a></p>")

    def refresh_players(self):
        self.top.set_accounts(self.state.storage.players(), self.state.storage.nicknames(), self.state.player)

    def change_player(self, p):
        if p and p != self.state.get("player"):
            self.state.set("player", p)
            self.state.reload()

    def weekly_summary(self):
        from .dialogs import WeeklySummaryDialog
        self._summary = WeeklySummaryDialog(self.state, self)
        self._summary.show()

    def maybe_weekly_summary(self):
        if not self.state.get("weekly_summary") or not self.state.pulls:
            return
        week = datetime.now().strftime("%G-W%V")
        if self.state.get("last_summary_week") == week:
            return
        self.state.set("last_summary_week", week)
        newest = max(p.time for p in self.state.pulls)
        if (datetime.now(timezone.utc) - newest).days <= 7:
            self.weekly_summary()

    def save_share_image(self):
        from .share_card import render
        path, _ = QFileDialog.getSaveFileName(self, tr("Save share image…").rstrip("…"), "wuwa_pulls.png", "PNG (*.png)")
        if path:
            render(self.state).save(path, "PNG")
            self.statusBar().showMessage(f"Saved {path}", 6000)
