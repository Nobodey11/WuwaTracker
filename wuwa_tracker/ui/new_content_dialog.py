"""Shown when imported pulls contain 5★ items or banner types the game data doesn't know yet
(i.e. a new patch came out). Your answers are saved to game_data.user.json."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout)

from ..core.gamedata import KINDS

KIND_LABELS = {
    "featured_character": "Featured character (50/50 rules)",
    "featured_weapon": "Featured weapon (always featured)",
    "standard": "Standard (permanent)",
    "beginner": "Beginner",
    "selector": "Selector / choice",
    "event": "Other event banner",
}


class NewContentDialog(QDialog):
    def __init__(self, items: list[tuple[str, bool]], pools: list[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("New patch content detected")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        intro = QLabel("Your pulls contain things the game data doesn't know yet, probably from a new patch.\n"
                       "Classify them so pity and 50/50 stats stay correct. (You can change this later in "
                       "Settings → Game data.)")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.item_boxes = []
        for name, is_weapon in items:
            cb = QComboBox()
            cb.addItem("Limited / featured (counts as a WON 50/50)", "limited")
            cb.addItem("Standard pool (counts as a LOST 50/50)", "standard")
            form.addRow(f"5✦ {'weapon' if is_weapon else 'resonator'}: <b>{name}</b>", cb)
            self.item_boxes.append((name, is_weapon, cb))
        self.pool_boxes = []
        for pt in pools:
            name = QLineEdit(f"Banner type {pt}")
            kind = QComboBox()
            for k in KINDS:
                kind.addItem(KIND_LABELS[k], k)
            kind.setCurrentIndex(KINDS.index("event"))
            form.addRow(f"New banner type <b>{pt}</b> name", name)
            form.addRow("   kind", kind)
            self.pool_boxes.append((pt, name, kind))
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Save to game data")
        bb.button(QDialogButtonBox.Cancel).setText("Later")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def apply(self, store):
        for name, is_weapon, cb in self.item_boxes:
            store.classify(name, cb.currentData(), is_weapon)
        for pt, name, kind in self.pool_boxes:
            store.set_banner_type(pt, name.text().strip() or f"Banner type {pt}", kind.currentData())
