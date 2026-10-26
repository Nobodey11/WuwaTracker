from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QWidget)

from ..core.game_import import SERVER_UTC_OFFSET
from ..core.gamedata import KINDS
from .calculator_tab import MODEL_CHOICES
from .widgets import card


class SettingsTab(QWidget):
    def __init__(self, state, on_saved=None, on_check_update=None):
        super().__init__()
        self.state = state
        self.on_saved = on_saved or (lambda m: None)
        self.on_check_update = on_check_update
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(18)

        # ---------------- general
        c1, l1 = card("General")
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
        save1 = QPushButton("Save general settings"); save1.setObjectName("primary")
        save1.clicked.connect(self.save_general)
        l1.addWidget(save1)
        l1.addStretch()
        lay.addWidget(c1, 1)

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

    # ---------------- game data
    def load_gamedata(self):
        gd = self.state.gd
        unknown_items, unknown_pools = self.state.unknown_content()
        warn = ""
        if unknown_items or unknown_pools:
            warn = (f"<br><span style='color:#e0a020'>⚠ Unclassified new content: "
                    f"{', '.join(n for n, _ in unknown_items)} {' '.join(f'type {p}' for p in unknown_pools)} "
                    "— use Help → Classify new content.</span>")
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
        path = str(self.state.gd_store.app_dir)
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        else:
            subprocess.Popen(["xdg-open", path])

    def reset_overrides(self):
        p = self.state.gd_store.user_path
        if p.exists():
            p.unlink()
        self.state.reload_gamedata()
        self.on_saved("Your game-data overrides were removed.")
