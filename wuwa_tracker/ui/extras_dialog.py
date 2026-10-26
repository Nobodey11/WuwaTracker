"""Manage characters/weapons owned outside of pulls (event gifts, free units, selectors)."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QPushButton,
                               QSpinBox, QVBoxLayout)


class ExtrasDialog(QDialog):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("Owned outside pulls")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        info = QLabel("Characters or weapons you got without pulling (event gifts, free units, selectors). "
                      "They count as owned in the Prydwen tab (badges, 'Only mine'), the character panel and the AI "
                      "assistant. Your pull statistics are not changed.")
        info.setWordWrap(True); info.setObjectName("muted")
        v.addWidget(info)
        self.list = QListWidget(); v.addWidget(self.list)
        row = QHBoxLayout()
        self.name = QComboBox(); self.name.setEditable(True); self.name.setMinimumWidth(220)
        names = sorted({c["name"] for c in state.prydwen.cached_character_list().values()} | state.gd.known_5stars)
        self.name.addItems(names); self.name.setCurrentText("")
        self.copies = QSpinBox(); self.copies.setRange(1, 7); self.copies.setPrefix("× ")
        add = QPushButton("Add / update"); rem = QPushButton("Remove selected")
        row.addWidget(self.name, 1); row.addWidget(self.copies); row.addWidget(add)
        v.addLayout(row)
        v.addWidget(rem)
        bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(self.accept); v.addWidget(bb)
        add.clicked.connect(self.add)
        rem.clicked.connect(self.remove)
        self.list.currentTextChanged.connect(self.pick)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for n, c in sorted(self.state.extras().items()):
            self.list.addItem(f"{n}  ×{c}")

    def pick(self, text):
        if text:
            n, _, c = text.rpartition("  ×")
            self.name.setCurrentText(n); self.copies.setValue(int(c or 1))

    def add(self):
        n = self.name.currentText().strip()
        if n:
            self.state.set_extra(n, self.copies.value()); self.refresh()

    def remove(self):
        it = self.list.currentItem()
        if it:
            self.state.set_extra(it.text().rpartition("  ×")[0], 0); self.refresh()
