"""Import / export actions of the main window (mixin): JSON and game import with backups and sanity checks,
exports (JSON, CSV, Excel), comparison with an export, backups, and account management."""
from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from ..core import game_import, import_check
from ..core.storage import read_wuwatracker_json
from .background import GameImportWorker
from .dialogs import BackupsDialog, ReportDialog
from .i18n import tr


class ImportActions:
    """Expects: self.state, self.statusBar(), self.notify(title, text), self.ask_new_content()."""

    # ---------------- import
    def _name(self, pt):
        return self.state.gd.name(pt)

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "wuwatracker export", "", "JSON (*.json)")
        if not path:
            return
        try:
            pulls, player = read_wuwatracker_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e)); return
        existing = self.state.storage.load(None)
        self.state.storage.backup("before-json-import")
        new = self.state.storage.add_pulls(pulls)
        if player:
            self.state.set("player", player)
        self.state.reload()
        msg = f"Imported {new:,} new pulls ({len(pulls):,} in file, duplicates skipped)."
        self.statusBar().showMessage(msg, 8000)
        fresh = [p for p in pulls if p.key not in {q.key for q in existing}]
        problems = import_check.check_ten_pulls(fresh, self._name)
        if problems:
            ReportDialog("Import check", msg + "\n\n" + import_check.summarize(problems), self).exec()
        self.ask_new_content(only_if_any=True)

    def import_game(self, url: str | None = None, game_dir: str | None = None, auto: bool = False):
        if getattr(self, "gw", None) is not None and self.gw.isRunning():
            return
        game_dir = game_dir or self.state.get("game_dir") or None
        off = game_import.SERVER_UTC_OFFSET.get(self.state.get("server_region"), 8)
        existing = self.state.storage.load(None)
        self.statusBar().showMessage("Import from game: starting…")
        self.gw = GameImportWorker(game_dir, url, off, existing)
        self.gw.auto = auto
        self.gw.existing_snapshot = existing
        self.gw.log.connect(lambda s: self.statusBar().showMessage(s))
        self.gw.not_found.connect(self._game_link_not_found)
        self.gw.done.connect(self.on_game_import)
        self.gw.start()

    def _game_link_not_found(self, checked):
        self.statusBar().clearMessage()
        if getattr(self.gw, "auto", False):
            return
        box = QMessageBox(self)
        box.setWindowTitle("Import from game")
        box.setIcon(QMessageBox.Information)
        where = ("Checked these log files, but none contained a history link:\n• " + "\n• ".join(checked[:6])
                 if checked else "No Wuthering Waves install with log files was found automatically.")
        box.setText("Couldn't find your Convene history link.")
        box.setInformativeText("1. Start the game and open Convene → History (let the page load).\n"
                               "2. Then import again, or pick your game folder / paste the link below.\n\n" + where)
        pick = box.addButton("Choose game folder…", QMessageBox.ActionRole)
        paste = box.addButton("Paste link…", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is pick:
            d = QFileDialog.getExistingDirectory(self, "Select your Wuthering Waves folder", self.state.get("game_dir"))
            if d:
                self.state.set("game_dir", d)
                self.import_game(game_dir=d)
        elif box.clickedButton() is paste:
            url, ok = QInputDialog.getText(self, "Import from game", "Paste the Convene history link:")
            if ok and url.strip():
                self.import_game(url=url.strip())

    def on_game_import(self, result, err):
        auto = getattr(self.gw, "auto", False)
        if err:
            self.statusBar().clearMessage()
            if auto:
                self.statusBar().showMessage(f"Auto-import failed: {err}", 15000)
                self.notify("Auto-import failed", err[:200])
            else:
                QMessageBox.warning(self, "Game import failed", err)
            return
        src = getattr(self.gw, "found_in", None)
        if src is not None and not self.state.get("game_dir"):     # remember where the game is
            game_root = next((p for p in src.parents if (p / "Client").is_dir()), None)
            if game_root:
                self.state.set("game_dir", str(game_root))
        existing = self.gw.existing_snapshot
        if result.pulls:
            self.state.storage.backup("before-game-import")
        new = self.state.storage.add_pulls(result.pulls)
        if result.player_id:
            self.state.set("player", result.player_id)
        self.state.reload()
        findings = (import_check.check_new_vs_existing(existing, result.pulls, self._name)
                    + import_check.check_ten_pulls(result.pulls, self._name))
        text = f"Imported {new} new pull(s) for player {result.player_id}."
        self.statusBar().showMessage(("Auto-import: " if auto else "Game import done: ") + text, 12000)
        if auto:
            if new and self.state.get("notify_imports"):
                fives = [p.name for p in result.pulls if p.quality == 5]
                self.notify("New pulls imported", text + (f" 5★: {', '.join(fives)}" if fives else ""))
        else:
            report = text + "\n\n" + "\n".join(f"- {l.strip()}" for l in result.log if l.strip())
            if findings:
                report += "\n\n**Checks**\n\n" + import_check.summarize(findings).replace("\n", "\n\n")
            ReportDialog("Import from game", report, self).exec()
        self.ask_new_content(only_if_any=True)

    # ---------------- export
    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "wuwa_pulls.csv", "CSV (*.csv)")
        if path:
            self.state.storage.export_csv(path, self.state.player or None)
            self.statusBar().showMessage(f"Saved {path}", 6000)

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "wuwa_pulls.json", "JSON (*.json)")
        if path:
            self.state.storage.export_wuwatracker_json(path, self.state.player)
            self.statusBar().showMessage(f"Saved {path} (wuwatracker format)", 6000)

    def export_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel", "wuwa_pulls.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.state.storage.export_xlsx(path, self.state.player or None, self.state.gd)
        except ImportError:
            QMessageBox.warning(self, "Export Excel", "Excel export needs the openpyxl package.\n"
                                "Run run.bat once more (it installs it), or: pip install openpyxl")
            return
        self.statusBar().showMessage(f"Saved {path}", 6000)

    def compare_export(self):
        path, _ = QFileDialog.getOpenFileName(self, "wuwatracker export to compare with", "", "JSON (*.json)")
        if not path:
            return
        try:
            pulls, player = read_wuwatracker_json(path)
        except Exception as e:
            QMessageBox.critical(self, "Compare", str(e)); return
        stored = self.state.storage.load(player or self.state.player or None)
        f = import_check.compare_with_export(stored, pulls, self._name)
        ReportDialog("Compare with export", f"Player {player}\n\n" + import_check.summarize(f).replace("\n", "\n\n"),
                     self).exec()

    def show_backups(self):
        BackupsDialog(self.state, self).exec()

    # ---------------- accounts
    def rename_account(self):
        p = self.state.player
        if not p:
            return
        name, ok = QInputDialog.getText(self, tr("Rename this account…").rstrip("…"),
                                        f"Name for account {p} (empty = none):", text=self.state.nickname(p))
        if ok:
            self.state.storage.set_nickname(p, name)
            self.refresh_players()

    def clear(self):
        p = self.state.player
        if p and QMessageBox.question(self, "Delete data", f"Delete all stored pulls of player {p}?\n"
                                      "(A backup is made first.)") == QMessageBox.Yes:
            self.state.storage.backup("before-delete")
            self.state.storage.clear(p)
            self.state.set("player", "")
            self.state.reload()
