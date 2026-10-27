"""Small dialogs: backups, text reports, weekly summary."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QTextBrowser, QVBoxLayout)

from ..core import backup
from .i18n import tr


class BackupsDialog(QDialog):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle(tr("Backups…").rstrip("…"))
        self.resize(560, 420)
        v = QVBoxLayout(self)
        info = QLabel("A copy of your database is made automatically before every import (the last "
                      f"{backup.KEEP} are kept). Restoring replaces your current data with the backup; a backup of "
                      "the current state is made first, so a restore can be undone.")
        info.setWordWrap(True); info.setObjectName("muted")
        v.addWidget(info)
        self.list = QListWidget()
        v.addWidget(self.list, 1)
        row = QHBoxLayout()
        b_new = QPushButton("Make a backup now"); b_new.clicked.connect(self.make)
        b_restore = QPushButton(tr("Restore")); b_restore.setObjectName("primary"); b_restore.clicked.connect(self.restore)
        b_folder = QPushButton("Open folder"); b_folder.clicked.connect(self.open_folder)
        row.addWidget(b_new); row.addWidget(b_folder); row.addStretch(); row.addWidget(b_restore)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.fill()

    def fill(self):
        self.list.clear()
        for b in backup.list_backups(self.state.storage.path):
            it = QListWidgetItem(b.label)
            it.setData(256, str(b.path))
            self.list.addItem(it)
        if not self.list.count():
            self.list.addItem("No backups yet.")

    def make(self):
        self.state.storage.backup("manual")
        self.fill()

    def restore(self):
        it = self.list.currentItem()
        path = it.data(256) if it else None
        if not path:
            return
        if QMessageBox.question(self, "Restore backup", f"Replace your current data with\n{it.text()}?") != QMessageBox.Yes:
            return
        self.state.storage.backup("before-restore")
        self.state.storage.restore(path)
        self.state.reload()
        self.fill()
        QMessageBox.information(self, "Restore backup", "Backup restored.")

    def open_folder(self):
        from .util import open_path
        open_path(backup.backup_dir(self.state.storage.path))


class ReportDialog(QDialog):
    def __init__(self, title: str, markdown: str, parent=None, width=620, height=440):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(width, height)
        v = QVBoxLayout(self)
        self.view = QTextBrowser(); self.view.setOpenExternalLinks(True)
        self.view.setMarkdown(markdown)
        v.addWidget(self.view, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close); self.buttons.rejected.connect(self.reject)
        v.addWidget(self.buttons)


class _RephraseWorker(QThread):
    done = Signal(str, str)

    def __init__(self, host, model, msgs):
        super().__init__()
        self.host, self.model, self.msgs = host, model, msgs

    def run(self):
        from ..core.ollama_client import OllamaClient
        try:
            ans, _ = OllamaClient(self.host, timeout=120).chat(self.model, self.msgs, None, temperature=0.6)
            self.done.emit(ans, "")
        except Exception as e:
            self.done.emit("", str(e))


class WeeklySummaryDialog(ReportDialog):
    """The facts come from the app; the optional AI version only rephrases them."""

    def __init__(self, state, parent=None):
        from ..core import summary
        from ..core.ollama_client import PERSONAS
        self.state = state
        self.facts = summary.week_facts(state.pulls, state.stats, state.gd)
        super().__init__(tr("Weekly summary…").rstrip("…"), summary.week_text(self.facts), parent, 560, 360)
        self.ai = QPushButton("✨ Let the AI tell it")
        self.ai.setToolTip("Uses your Ollama model and the persona from the AI tab; the numbers stay the app's.")
        self.ai.clicked.connect(self.rephrase)
        self.buttons.addButton(self.ai, QDialogButtonBox.ActionRole)
        self.persona = PERSONAS.get(state.get("persona") or "", (None, ""))[1]

    def rephrase(self):
        from ..core import summary
        model = self.state.get("ollama_model")
        if not model:
            self.view.append("\n⚠ Pick an Ollama model in the AI tab first.")
            return
        self.ai.setEnabled(False)
        self.ai.setText("Writing…")
        self.w = _RephraseWorker(self.state.get("ollama_host"), model, summary.week_prompt(self.facts, self.persona))
        self.w.done.connect(self._done)
        self.w.start()

    def _done(self, text, err):
        self.ai.setEnabled(True)
        self.ai.setText("✨ Let the AI tell it")
        if err:
            self.view.append(f"\n⚠ {err}")
        else:
            from ..core import summary
            self.view.setMarkdown(text + "\n\n---\n\n*Facts:*\n\n" + summary.week_text(self.facts))
