from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu,
                               QMessageBox, QPushButton, QTabBar, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from ..core import game_import
from . import theme as T
from .assistant_tab import AssistantTab
from .calculator_tab import CalculatorTab
from .history_tab import HistoryTab
from .new_content_dialog import NewContentDialog
from .overview_tab import OverviewTab
from .prydwen_tab import PrydwenTab
from .simulator_tab import SimulatorTab
from .codes_tab import CodesTab
from .settings_tab import SettingsTab


class GameDataUpdateWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, store, url):
        super().__init__()
        self.store, self.url = store, url

    def run(self):
        self.done.emit(*self.store.check_update(self.url))


class GameImportWorker(QThread):
    log = Signal(str)
    done = Signal(list, str, str)

    def __init__(self, url, offset, latest):
        super().__init__()
        self.url, self.offset, self.latest = url, offset, latest

    def run(self):
        try:
            pulls, player = game_import.import_from_game(self.url, self.offset, self.latest, log=self.log.emit)
            self.done.emit(pulls, player, "")
        except Exception as e:
            self.done.emit([], "", str(e))


def app_icon() -> QIcon:
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "assets"
    icon = QIcon()
    for f in ("icon.ico", "icon.png"):
        if (base / f).exists():
            icon.addFile(str(base / f))
    return icon


def next_resets(utc_offset_h: float):
    tz = timezone(timedelta(hours=utc_offset_h))
    now = datetime.now(tz)
    daily = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if daily <= now:
        daily += timedelta(days=1)
    weekly = daily + timedelta(days=(0 - daily.weekday()) % 7)  # Monday 04:00 server time
    return daily - now, weekly - now


def fmt_td(td: timedelta) -> str:
    s = int(td.total_seconds())
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, s = divmod(s, 60)
    return (f"{d:02d}d " if d else "") + f"{h:02d}h {m:02d}m" + ("" if d else f" {s:02d}s")


class MainWindow(QMainWindow):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setWindowTitle("WuWa Pull Tracker")
        self.resize(1400, 900)

        root = QWidget(); root.setObjectName("root")
        v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)

        # ---------- top navigation bar (logo · tabs · player · menu) ----------
        top = QWidget(); top.setObjectName("topbar")
        tl = QHBoxLayout(top); tl.setContentsMargins(18, 0, 12, 0); tl.setSpacing(10)
        icon = QLabel(); icon.setPixmap(app_icon().pixmap(28, 28)); icon.setObjectName("plain")
        word = QLabel(f"<span style='color:{T.GOLD}'>WuWa</span> Pull Tracker"); word.setObjectName("wordmark")
        tl.addWidget(icon); tl.addWidget(word); tl.addSpacing(22)
        self.nav = QTabBar(); self.nav.setObjectName("nav"); self.nav.setDrawBase(False); self.nav.setExpanding(False)
        tl.addWidget(self.nav, 0, Qt.AlignBottom)
        tl.addStretch()
        self.player = QComboBox(); self.player.setObjectName("pill"); self.player.setMinimumWidth(120)
        self.player.setToolTip("Player (account)")
        tl.addWidget(self.player)
        self.menu_btn = QToolButton(); self.menu_btn.setObjectName("menuBtn"); self.menu_btn.setText("☰")
        self.menu_btn.setToolTip("Menu: import, export, updates, about")
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        tl.addWidget(self.menu_btn)
        v.addWidget(top)

        # ---------- thin status strip (game data · reset timers) ----------
        strip = QWidget(); strip.setObjectName("strip")
        sl = QHBoxLayout(strip); sl.setContentsMargins(20, 0, 20, 0); sl.setSpacing(18)
        self.gd_label = QPushButton(); self.gd_label.setObjectName("chip"); self.gd_label.setCursor(Qt.PointingHandCursor)
        self.gd_label.clicked.connect(self.about_gamedata)
        sl.addWidget(self.gd_label); sl.addStretch()
        self.daily = QLabel(); self.daily.setObjectName("stripText")
        self.weekly = QLabel(); self.weekly.setObjectName("stripText")
        sl.addWidget(self.daily); sl.addWidget(self.weekly)
        v.addWidget(strip)

        self.tabs = QTabWidget()
        self.tabs.addTab(OverviewTab(state), "Tracker")
        self.tabs.addTab(HistoryTab(state), "Pull History")
        self.tabs.addTab(CalculatorTab(state), "Probability")
        self.tabs.addTab(PrydwenTab(state), "Prydwen")
        self.tabs.addTab(SimulatorTab(state), "Convene Simulator")
        self.codes_tab = CodesTab(state, lambda m: self.statusBar().showMessage(m, 15000))
        self.tabs.addTab(self.codes_tab, "Codes")
        self.tabs.addTab(AssistantTab(state), "AI Assistant")
        self.tabs.addTab(SettingsTab(state, lambda m: self.statusBar().showMessage(m, 8000), self.check_gamedata),
                         "Settings")
        v.addWidget(self.tabs)
        self.setCentralWidget(root)
        # the nav bar in the header drives the pages; the QTabWidget's own bar is hidden
        self.tabs.tabBar().hide()
        self.tabs.setDocumentMode(True)
        for i in range(self.tabs.count()):
            self.nav.addTab(self.tabs.tabText(i))
        self.nav.currentChanged.connect(self.tabs.setCurrentIndex)
        self.codes_tab.new_codes.connect(self._codes_badge)
        self.tabs.currentChanged.connect(lambda i: self.nav.currentIndex() != i and self.nav.setCurrentIndex(i))
        self.setWindowIcon(app_icon())

        self._menu()
        self.player.currentTextChanged.connect(self.change_player)
        state.changed.connect(self.refresh_players)
        state.changed.connect(self.refresh_gd_label)
        self.refresh_players()
        self.refresh_gd_label()

        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(1000)
        self.tick()
        if not state.pulls:
            QTimer.singleShot(300, lambda: self.statusBar().showMessage(
                "No data yet: ☰ menu → Import wuwatracker JSON… (Ctrl+O)."))
        if state.get("gamedata_autocheck") and state.get("gamedata_url"):
            QTimer.singleShot(800, lambda: self.check_gamedata(False))
        QTimer.singleShot(1200, lambda: self.ask_new_content(only_if_any=True))

    def _menu(self):
        self.menuBar().hide()
        menu = QMenu(self)
        def add(text, fn, shortcut=None):
            a = QAction(text, self); a.triggered.connect(fn)
            if shortcut:
                a.setShortcut(shortcut)
                self.addAction(a)          # keep the shortcut working with the menu closed
            menu.addAction(a)
        menu.addSection("Data")
        add("Import wuwatracker JSON…", self.import_json, "Ctrl+O")
        add("Import from game (experimental)…", self.import_game, "Ctrl+G")
        add("Export CSV…", self.export_csv)
        add("Export wuwatracker JSON…", self.export_json)
        add("Delete this player's data…", self.clear)
        menu.addSection("Game data")
        add("Check for game data updates", lambda: self.check_gamedata(True), "F5")
        add("Classify new content…", lambda: self.ask_new_content(only_if_any=False))
        add("About game data…", self.about_gamedata)
        menu.addSection("My account")
        add("Owned outside pulls (gifts, free units)…", self.edit_extras)
        menu.addSection("App")
        add("About / disclaimer…", self.about)
        add("Exit", self.close, "Ctrl+Q")
        self.menu_btn.setMenu(menu)

    def _codes_badge(self, n):
        i = self.tabs.indexOf(self.codes_tab)
        self.nav.setTabText(i, f"Codes  🎁{n}" if n else "Codes")

    def edit_extras(self):
        from .extras_dialog import ExtrasDialog
        ExtrasDialog(self.state, self).exec()

    # ---------- game data ----------
    def refresh_gd_label(self):
        gd = self.state.gd
        items, pools = self.state.unknown_content()
        stale = not gd.current_banners()
        flag = " ⚠" if (items or pools or stale) else ""
        self.gd_label.setText(f"Patch {gd.patch}  ·  data v{gd.version}{flag}")
        self.gd_label.setToolTip("Game data is out of date or has unclassified items — click for details." if flag else
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

    def about(self):
        from .. import __version__
        QMessageBox.about(self, "About WuWa Pull Tracker",
            f"<h3>WuWa Pull Tracker {__version__}</h3>"
            "<p>Unofficial fan project, <b>strictly for personal use</b>.</p>"
            "<p>Based on the <a href='https://wuwatracker.com'>WuWa Tracker</a> pull tracker, but <b>not affiliated "
            "with, endorsed by or connected to WuWa Tracker, Prydwen.gg or Kuro Games</b>.</p>"
            "<p>Tier lists, ratings and images in the Prydwen tab belong to "
            "<a href='https://www.prydwen.gg/wuthering-waves'>Prydwen.gg</a>. Wuthering Waves names and art "
            "© Kuro Games.</p><p>Odds are estimates; provided as is, without warranty.</p>"
            "<p><a href='https://github.com/Nobodey11/WuwaTracker'>github.com/Nobodey11/WuwaTracker</a></p>")

    def about_gamedata(self):
        gd = self.state.gd
        cur = ", ".join(f"{b['patch']} P{b.get('phase')}" for b in gd.current_banners()) or "none (out of date)"
        QMessageBox.information(self, "Game data",
                                f"Version: {gd.version}\nGame patch: {gd.patch}\nSource: {gd.source}\n"
                                f"Current banner phase: {cur}\nKnown 5✦ items: {len(gd.known_5stars)}\n"
                                f"Banner types: {len(gd.raw['banner_types'])}\n\n"
                                f"Folder: {self.state.gd_store.app_dir}")

    def tick(self):
        off = game_import.SERVER_UTC_OFFSET.get(self.state.get("server_region"), 8)
        d, w = next_resets(off)
        self.daily.setText(f"Daily reset  <b>{fmt_td(d)}</b>")
        self.weekly.setText(f"Weekly reset  <b>{fmt_td(w)}</b>")

    def refresh_players(self):
        players = self.state.storage.players()
        self.player.blockSignals(True)
        self.player.clear(); self.player.addItems(players)
        self.player.setCurrentText(self.state.player)
        self.player.blockSignals(False)

    def change_player(self, p):
        if p and p != self.state.get("player"):
            self.state.set("player", p)
            self.state.reload()

    # ---------- actions ----------
    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "wuwatracker export", "", "JSON (*.json)")
        if not path:
            return
        try:
            new, total, player = self.state.storage.import_wuwatracker_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e)); return
        if player:
            self.state.set("player", player)
        self.state.reload()
        self.statusBar().showMessage(f"Imported {new:,} new pulls ({total:,} in file, duplicates skipped).", 8000)
        self.ask_new_content(only_if_any=True)

    def import_game(self):
        url = game_import.find_gacha_url(self.state.get("game_dir") or None)
        if not url:
            url, ok = QInputDialog.getText(
                self, "Import from game",
                "Couldn't find the Convene history URL in the game log.\n"
                "Open the game → Convene → History once, set your game folder in Settings, and retry.\n\n"
                "Or paste the history URL here:")
            if not ok or not url.strip():
                return
            url = url.strip()
        latest = {}
        for p in self.state.storage.load(game_import.parse_gacha_url(url)["playerId"] or None):
            if p.pool_type not in latest or p.time > latest[p.pool_type]:
                latest[p.pool_type] = p.time
        off = game_import.SERVER_UTC_OFFSET.get(self.state.get("server_region"), 8)
        self.statusBar().showMessage("Fetching from game servers…")
        self.gw = GameImportWorker(url, off, latest)
        self.gw.log.connect(lambda s: self.statusBar().showMessage(s))
        self.gw.done.connect(self.on_game_import)
        self.gw.start()

    def on_game_import(self, pulls, player, err):
        if err:
            QMessageBox.warning(self, "Game import failed", err + "\n\nThe history link expires after a while; "
                                "open Convene → History in-game again and retry."); return
        new = self.state.storage.add_pulls(pulls)
        if player:
            self.state.set("player", player)
        self.state.reload()
        self.statusBar().showMessage(f"Game import done: {new} new pulls.", 8000)
        self.ask_new_content(only_if_any=True)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "wuwa_pulls.csv", "CSV (*.csv)")
        if path:
            self.state.storage.export_csv(path, self.state.player or None)
            self.statusBar().showMessage(f"Saved {path}", 6000)

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "wuwa_pulls.json", "JSON (*.json)")
        if path:
            self.state.storage.export_wuwatracker_json(path, self.state.player)
            self.statusBar().showMessage(f"Saved {path}", 6000)

    def clear(self):
        p = self.state.player
        if p and QMessageBox.question(self, "Delete data", f"Delete all stored pulls of player {p}?") \
                == QMessageBox.Yes:
            self.state.storage.clear(p)
            self.state.set("player", "")
            self.state.reload()
