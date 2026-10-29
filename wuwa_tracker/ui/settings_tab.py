from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from ..core import paths
from .i18n import tr

from ..core.game_import import SERVER_UTC_OFFSET
from ..core.gamedata import KINDS
from .calculator_tab import MODEL_CHOICES
from .widgets import card


class SettingsTab(QWidget):
    def __init__(self, state, on_saved=None, on_check_update=None, on_automation=None):
        super().__init__()
        self.state = state
        self.on_saved = on_saved or (lambda m: None)
        self.on_check_update = on_check_update
        self.on_automation = on_automation or (lambda: None)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(18)

        # ---------------- general
        c1, l1 = card(tr("Settings"))
        f = QFormLayout(); f.setSpacing(10)
        self.host = QLineEdit()
        self.model = QComboBox()
        for k, v in MODEL_CHOICES:
            self.model.addItem(v, k)
        self.game_dir = QLineEdit(); self.game_dir.setPlaceholderText(r"e.g. D:\Wuthering Waves")
        browse = QPushButton("…"); browse.clicked.connect(self.pick_dir)
        gd_row = QHBoxLayout(); gd_row.addWidget(self.game_dir); gd_row.addWidget(browse)
        self.region = QComboBox(); self.region.addItems(list(SERVER_UTC_OFFSET))
        f.addRow("Ollama host", self.host)
        f.addRow("Default pity model", self.model)
        f.addRow("Game folder", gd_row)
        f.addRow("Server region", self.region)
        self.prydwen = QCheckBox("Use prydwen.gg (tier list, character info, portraits)")
        f.addRow("", self.prydwen)
        l1.addLayout(f)
        note = QLabel("Server region sets the reset timers and the time zone for direct game import.")
        note.setObjectName("muted"); note.setWordWrap(True)
        l1.addWidget(note)
        save1 = QPushButton(tr("Save general settings")); save1.setObjectName("primary")
        save1.clicked.connect(self.save_general)
        l1.addWidget(save1)
        l1.addSpacing(14)

        # ---------------- appearance
        ap = QLabel(tr("Appearance")); ap.setObjectName("h2")
        l1.addWidget(ap)
        fa = QFormLayout()
        self.theme = QComboBox(); self.theme.addItem(tr("Dark"), "dark"); self.theme.addItem(tr("Light"), "light")
        self.lang = QComboBox(); self.lang.addItem("English", "en"); self.lang.addItem("Nederlands", "nl")
        fa.addRow(tr("Theme"), self.theme); fa.addRow(tr("Language"), self.lang)
        l1.addLayout(fa)
        rn = QLabel(tr("Restart the app to apply.")); rn.setObjectName("muted")
        l1.addWidget(rn)
        prefs = paths.ui_prefs()
        self.theme.setCurrentIndex(max(0, self.theme.findData(prefs.get("theme", "dark"))))
        self.lang.setCurrentIndex(max(0, self.lang.findData(prefs.get("lang", "en"))))
        self.theme.currentIndexChanged.connect(lambda: paths.set_ui_pref("theme", self.theme.currentData()))
        self.lang.currentIndexChanged.connect(lambda: paths.set_ui_pref("lang", self.lang.currentData()))
        l1.addStretch()
        lay.addWidget(c1, 1)

        # ---------------- automation, notifications, data folder
        c3, l3 = card(tr("Automation"))
        self.autostart = QCheckBox("Start with Windows (quietly, in the tray)")
        self.autostart.setToolTip("Adds the tracker to your Windows start-up programs (per user, no admin rights).")
        self.game_detect = QCheckBox("Detect when Wuthering Waves starts and stops")
        self.auto_import = QCheckBox("Auto-import: sync as soon as you open Convene → History in the game")
        self.tray = QCheckBox("Show a tray icon (reset timers, quick import)")
        self.close_tray = QCheckBox("Closing the window keeps the app running in the tray")
        self.n_codes = QCheckBox("Notify me about new redemption codes")
        self.n_banners = QCheckBox("Notify me 2 days before a banner or event ends")
        self.n_imports = QCheckBox("Notify me when pulls were auto-imported")
        self.upd = QCheckBox("Check GitHub for app updates (once a day)")
        self.weekly = QCheckBox("Show the weekly summary on the first start of a week")
        self.open_on_game = QCheckBox("Open the tracker window when the game starts")
        self.overlay = QCheckBox("Show the pity overlay during the game (borderless/windowed mode)")
        self.sync_rem = QCheckBox("Remind me to open Convene → History when nothing was synced")
        self.close_game = QCheckBox("Close the tracker when the game closes")
        for w in (self.autostart, self.game_detect, self.auto_import, self.open_on_game, self.overlay, self.sync_rem,
                  self.close_game, self.tray, self.close_tray, self.n_codes, self.n_banners, self.n_imports, self.upd,
                  self.weekly):
            l3.addWidget(w)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Game program(s)"))
        self.procs = QLineEdit()
        self.procs.setPlaceholderText("Client-Win64-Shipping.exe, Wuthering Waves.exe")
        self.procs.setToolTip("Names of the game's .exe as shown in Task Manager → Details, comma separated.")
        prow.addWidget(self.procs, 1)
        steam = QPushButton("Copy Steam launch option")
        steam.setToolTip("Alternative to 'start with Windows': paste into Steam → Wuthering Waves → Properties → "
                         "Launch options, so the tracker starts together with the game.")
        steam.clicked.connect(self.copy_steam)
        prow.addWidget(steam)
        l3.addLayout(prow)
        save3 = QPushButton(tr("Save")); save3.setObjectName("primary"); save3.clicked.connect(self.save_automation)
        l3.addWidget(save3)
        l3.addSpacing(14)
        dt = QLabel(tr("Data folder")); dt.setObjectName("h2")
        l3.addWidget(dt)
        self.data_dir = QLabel(); self.data_dir.setWordWrap(True)
        self.data_dir.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l3.addWidget(self.data_dir)
        dn = QLabel("Put the data folder in e.g. OneDrive to sync your pulls, settings, notes and backups between "
                    "PCs. The app warns you when the folder is in use on another PC.")
        dn.setWordWrap(True); dn.setObjectName("muted")
        l3.addWidget(dn)
        drow = QHBoxLayout()
        b_move = QPushButton("Change…"); b_move.clicked.connect(self.change_data_dir)
        b_def = QPushButton("Back to default"); b_def.clicked.connect(lambda: self.change_data_dir(default=True))
        b_open = QPushButton("Open"); b_open.clicked.connect(lambda: self.open_path(self.state.data_dir))
        b_notes = QPushButton("Open notes folder"); b_notes.setToolTip("Markdown/text notes here are searched by the AI assistant")
        b_notes.clicked.connect(lambda: self.open_path(self.state.notes_dir))
        for b in (b_move, b_def, b_open, b_notes):
            drow.addWidget(b)
        drow.addStretch()
        l3.addLayout(drow)
        l3.addStretch()
        lay.addWidget(c3, 1)

        # ---------------- game data (patch updates)
        c2, l2 = card("Game data · stays up to date every patch")
        self.gd_info = QLabel(); self.gd_info.setWordWrap(True)
        l2.addWidget(self.gd_info)
        f2 = QFormLayout(); f2.setSpacing(10)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://raw.githubusercontent.com/<you>/WuwaTracker/main/wuwa_tracker/data/game_data.json")
        self.autocheck = QCheckBox("Check for updates on start-up")
        f2.addRow("Update URL", self.url)
        f2.addRow("", self.autocheck)
        l2.addLayout(f2)
        row = QHBoxLayout()
        b_check = QPushButton("Check now"); b_check.clicked.connect(self.check_now)
        b_folder = QPushButton("Open data folder"); b_folder.clicked.connect(self.open_folder)
        b_reset = QPushButton("Reset my overrides"); b_reset.clicked.connect(self.reset_overrides)
        row.addWidget(b_check); row.addWidget(b_folder); row.addWidget(b_reset); row.addStretch()
        l2.addLayout(row)

        l2.addWidget(QLabel("Banner types (id = name | kind)"))
        self.names = QPlainTextEdit()
        l2.addWidget(self.names, 1)
        l2.addWidget(QLabel("Standard 5✦ resonators (a lost 50/50), comma separated"))
        self.std = QLineEdit()
        l2.addWidget(self.std)
        hint = QLabel("Kinds: " + ", ".join(KINDS) + ".\nYour edits are saved as overrides in game_data.user.json, "
                      "so they survive game-data updates.")
        hint.setObjectName("muted"); hint.setWordWrap(True)
        l2.addWidget(hint)
        save2 = QPushButton("Save game data overrides"); save2.setObjectName("primary")
        save2.clicked.connect(self.save_gamedata)
        l2.addWidget(save2)
        lay.addWidget(c2, 1)

        state.changed.connect(self.load_gamedata)
        self.load()

    # ---------------- general
    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Wuthering Waves install folder", self.game_dir.text())
        if d:
            self.game_dir.setText(d)

    def load(self):
        s = self.state
        self.host.setText(s.get("ollama_host"))
        self.model.setCurrentIndex(max(0, self.model.findData(s.get("pity_model"))))
        self.game_dir.setText(s.get("game_dir"))
        self.region.setCurrentText(s.get("server_region"))
        self.prydwen.setChecked(bool(s.get("prydwen_enabled")))
        from ..core import autostart
        self.autostart.setEnabled(autostart.supported())
        try:
            self.autostart.setChecked(autostart.is_enabled())
        except OSError:
            self.autostart.setChecked(False)
        self.game_detect.setChecked(bool(s.get("game_detect")))
        self.open_on_game.setChecked(bool(s.get("open_on_game")))
        self.overlay.setChecked(bool(s.get("overlay")))
        self.sync_rem.setChecked(bool(s.get("sync_reminder")))
        self.close_game.setChecked(bool(s.get("close_with_game")))
        self.procs.setText(s.get("game_processes") or "")
        self.auto_import.setChecked(bool(s.get("auto_import")))
        self.tray.setChecked(bool(s.get("tray")))
        self.close_tray.setChecked(bool(s.get("close_to_tray")))
        self.n_codes.setChecked(bool(s.get("notify_codes")))
        self.n_banners.setChecked(bool(s.get("notify_banners")))
        self.n_imports.setChecked(bool(s.get("notify_imports")))
        self.upd.setChecked(bool(s.get("update_check")))
        self.weekly.setChecked(bool(s.get("weekly_summary")))
        self.data_dir.setText(f"<b>{s.data_dir}</b>")
        self.url.setText(s.get("gamedata_url"))
        self.autocheck.setChecked(bool(s.get("gamedata_autocheck")))
        self.load_gamedata()

    def save_general(self):
        s = self.state
        s.set("ollama_host", self.host.text().strip() or "http://localhost:11434")
        s.set("pity_model", self.model.currentData())
        s.set("game_dir", self.game_dir.text().strip())
        s.set("server_region", self.region.currentText())
        s.set("prydwen_enabled", self.prydwen.isChecked())
        s.reload()
        self.on_saved("Settings saved.")

    # ---------------- automation / data folder
    def save_automation(self):
        s = self.state
        from ..core import autostart
        if autostart.supported():
            try:
                (autostart.enable if self.autostart.isChecked() else autostart.disable)()
            except OSError as e:
                QMessageBox.warning(self, tr("Automation"), f"Couldn't change 'start with Windows': {e}")
        s.set("game_processes", self.procs.text().strip())
        for key, box in (("game_detect", self.game_detect), ("open_on_game", self.open_on_game),
                         ("overlay", self.overlay), ("sync_reminder", self.sync_rem),
                         ("close_with_game", self.close_game),
                         ("auto_import", self.auto_import), ("tray", self.tray), ("close_to_tray", self.close_tray),
                         ("notify_codes", self.n_codes), ("notify_banners", self.n_banners),
                         ("notify_imports", self.n_imports), ("update_check", self.upd), ("weekly_summary", self.weekly)):
            s.set(key, box.isChecked())
        self.on_automation()
        self.on_saved("Automation settings saved." + (" Auto-import is watching the game log." if
                                                      self.auto_import.isChecked() else ""))

    def copy_steam(self):
        from PySide6.QtWidgets import QApplication
        from ..core import autostart
        QApplication.clipboard().setText(autostart.steam_launch_option())
        QMessageBox.information(self, "Steam launch option",
                                "Copied. In Steam: right-click Wuthering Waves → Properties → General → Launch options, "
                                "paste, and close the window.\n\nSteam then starts the tracker (in the tray) together "
                                "with the game.\n\nNote: on Windows, Steam doesn't handle commands like this in every version. If the "
                                "game no longer starts, clear the launch option again. 'Start with Windows' is the "
                                "reliable way and makes this unnecessary.")

    def change_data_dir(self, default=False):
        if default:
            target = None
        else:
            target = QFileDialog.getExistingDirectory(self, "Choose a data folder (e.g. in OneDrive)", str(self.state.data_dir))
            if not target:
                return
        new = paths.set_data_dir(target)
        QMessageBox.information(self, tr("Data folder"),
                                f"The data folder is now:\n{new}\n\nYour data was copied there if the folder was empty. "
                                "Restart the app to use it.")
        self.data_dir.setText(f"<b>{self.state.data_dir}</b> → after restart: <b>{new}</b>")

    @staticmethod
    def open_path(path):
        from .util import open_path
        open_path(path)

    # ---------------- game data
    def load_gamedata(self):
        gd = self.state.gd
        unknown_items, unknown_pools = self.state.unknown_content()
        warn = ""
        if unknown_items or unknown_pools:
            warn = (f"<br><span style='color:#e0a020'>⚠ Unclassified new content: "
                    f"{', '.join(n for n, _ in unknown_items)} {' '.join(f'type {p}' for p in unknown_pools)} "
                    "— use ☰ menu → Classify new content.</span>")
        if not gd.current_banners():
            warn += ("<br><span style='color:#e0a020'>⚠ No banner in the data covers today: a new patch is "
                     "probably out. Check for updates or add it (docs/PATCH_UPDATE.md).</span>")
        self.gd_info.setText(f"Loaded <b>v{gd.version}</b> · game patch <b>{gd.patch}</b> · source: <b>{gd.source}</b>"
                             f" · {len(gd.raw.get('banners', []))} banner phases known{warn}")
        self.names.setPlainText("\n".join(f"{k} = {v['name']} | {v['kind']}"
                                          for k, v in sorted(gd.raw["banner_types"].items(), key=lambda x: int(x[0]))))
        self.std.setText(", ".join(sorted(gd.standard_resonators)))

    def save_gamedata(self):
        store, gd = self.state.gd_store, self.state.gd
        bad = []
        for line in self.names.toPlainText().splitlines():
            if "=" not in line:
                continue
            k, rest = line.split("=", 1)
            name, _, kind = rest.partition("|")
            k, name, kind = k.strip(), name.strip(), (kind.strip() or "event")
            if not k.isdigit() or kind not in KINDS:
                bad.append(line.strip()); continue
            cur = gd.raw["banner_types"].get(k, {})
            if cur.get("name") != name or cur.get("kind") != kind:
                store.set_banner_type(int(k), name, kind)
        new_std = {x.strip() for x in self.std.text().split(",") if x.strip()}
        old_std = gd.standard_resonators
        for n in new_std - old_std:
            store.classify(n, "standard")
        for n in old_std - new_std:
            store.classify(n, "limited")
        self.state.reload_gamedata()
        self.on_saved("Game data overrides saved." + (f" Ignored invalid lines: {bad}" if bad else ""))

    def check_now(self):
        self.state.set("gamedata_url", self.url.text().strip())
        self.state.set("gamedata_autocheck", self.autocheck.isChecked())
        if self.on_check_update:
            self.on_check_update(True)

    def open_folder(self):
        self.open_path(self.state.gd_store.app_dir)

    def reset_overrides(self):
        p = self.state.gd_store.user_path
        if p.exists():
            p.unlink()
        self.state.reload_gamedata()
        self.on_saved("Your game-data overrides were removed.")
