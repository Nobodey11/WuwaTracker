"""Collection tab: every resonator and weapon, owned ones in colour with S0–S6 / R1–R5."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..core import collection
from . import theme as T
from .i18n import tr
from .prydwen_tab import ELEMENT_COLORS
from .widgets import FlowLayout, clear_layout

RAR = {5: T.GOLD, 4: T.PURPLE, 3: T.BLUE}


class _ListLoader(QThread):
    done = Signal(str)

    def __init__(self, prydwen, force=False):
        super().__init__()
        self.prydwen, self.force = prydwen, force

    def run(self):
        errs = []
        for fn in (self.prydwen.character_list, self.prydwen.weapon_list, self.prydwen.tier_list):
            try:
                fn(self.force)
            except Exception as e:
                errs.append(str(e))
        self.done.emit("; ".join(errs))


class Tile(QFrame):
    def __init__(self, item: collection.Item, images, prydwen_on):
        super().__init__()
        self.setFixedSize(108, 150)
        col = RAR.get(item.rarity, T.BORDER)
        self.setStyleSheet(f"QFrame {{ background:{T.CARD}; border:1px solid {col if item.owned else T.BORDER};"
                           f" border-radius:10px; }} QLabel {{ border:none; background:transparent; }}")
        v = QVBoxLayout(self); v.setContentsMargins(6, 6, 6, 6); v.setSpacing(2)
        pic = QLabel(); pic.setFixedSize(94, 94); pic.setAlignment(Qt.AlignCenter)
        pic.setStyleSheet(f"background:{T.CARD2}; border-radius:8px;")
        pic.setText(item.name[:2].upper())
        if prydwen_on and item.icon:
            images.set_on(pic, item.icon, 94, 94, cover=item.kind == "resonator")
        v.addWidget(pic, 0, Qt.AlignHCenter)
        name = QLabel(item.name); name.setAlignment(Qt.AlignCenter); name.setWordWrap(True)
        name.setStyleSheet("font-size:8pt; font-weight:600;")
        v.addWidget(name)
        sub = QLabel(); sub.setAlignment(Qt.AlignCenter); sub.setStyleSheet(f"font-size:8pt; color:{T.MUTED};")
        stars = "★" * item.rarity if item.rarity else ""
        sub.setText(f"<span style='color:{col}'>{stars}</span>  " + (f"<b style='color:{T.TEXT}'>{item.level}</b>"
                                                                       if item.owned else ""))
        v.addWidget(sub)
        tip = f"{item.name}\n{item.rarity}★ {item.kind}" + (f" · {item.group}" if item.group else "")
        if item.limited is not None:
            tip += " · limited" if item.limited else " · standard"
        tip += f"\n{('Owned: ' + str(item.copies) + ' copies (' + item.level + ')') if item.owned else 'Not owned'}"
        self.setToolTip(tip)
        if not item.owned:
            eff = QGraphicsOpacityEffect(self); eff.setOpacity(0.38)
            self.setGraphicsEffect(eff)


class CollectionTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        v = QVBoxLayout(self); v.setContentsMargins(20, 14, 20, 12)
        top = QHBoxLayout()
        t = QLabel(tr("Collection")); t.setObjectName("h1")
        top.addWidget(t); top.addSpacing(16)
        self.kind = QComboBox(); self.kind.addItem(tr("Resonators"), "resonator"); self.kind.addItem(tr("Weapons"), "weapon")
        self.rarity = QComboBox()
        for label, r in (("5★ + 4★", 0), ("5★", 5), ("4★", 4)):
            self.rarity.addItem(label, r)
        self.owned = QComboBox()
        for label, o in ((tr("All"), None), (tr("Owned"), True), (tr("Not owned"), False)):
            self.owned.addItem(label, o)
        self.group = QComboBox(); self.group.addItem("Any element / type", "")
        self.limited = QCheckBox("Limited only")
        self.search = QLineEdit(); self.search.setPlaceholderText(tr("Search…")); self.search.setMaximumWidth(180)
        self.reload_btn = QPushButton("↻"); self.reload_btn.setToolTip("Reload the character/weapon lists from Prydwen")
        for w in (self.kind, self.rarity, self.owned, self.group, self.limited, self.search):
            top.addWidget(w)
        top.addStretch(); top.addWidget(self.reload_btn)
        v.addLayout(top)
        self.summary = QLabel(); self.summary.setObjectName("muted")
        v.addWidget(self.summary)
        sc = QScrollArea(); sc.setWidgetResizable(True)
        inner = QWidget(); inner.setObjectName("scrollInner")
        self.flow = FlowLayout(inner, 10)
        sc.setWidget(inner)
        v.addWidget(sc, 1)
        credit = QLabel(f"Names, icons and character art from <a style='color:{T.GOLD}' "
                        "href='https://www.prydwen.gg/wuthering-waves'>Prydwen.gg</a>; ownership from your pulls and "
                        "☰ → Owned outside pulls.")
        credit.setOpenExternalLinks(True); credit.setObjectName("muted")
        v.addWidget(credit)
        for w in (self.kind, self.rarity, self.owned, self.group):
            w.currentIndexChanged.connect(self.refresh)
        self.kind.currentIndexChanged.connect(self._groups)
        self.limited.toggled.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.reload_btn.clicked.connect(lambda: self.load(True))
        state.changed.connect(self.refresh)
        self._loaded = False

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._loaded:
            self._loaded = True
            self.refresh()
            self.load(False)

    def load(self, force):
        if not self.state.prydwen_on():
            self.summary.setText("Prydwen is turned off (Settings): only items from your pulls are shown.")
            return
        self.reload_btn.setEnabled(False)
        self.loader = _ListLoader(self.state.prydwen, force)
        self.loader.done.connect(self._loaded_lists)
        self.loader.start()

    def _loaded_lists(self, err):
        self.reload_btn.setEnabled(True)
        self.refresh()
        if err and not self.items:
            self.summary.setText(f"Couldn't load the lists from Prydwen ({err}). Showing items from your pulls.")

    def _items(self):
        pw = self.state.prydwen
        on = self.state.prydwen_on()
        return collection.build(self.state.pulls, self.state.extras(), pw.cached_character_list() if on else {},
                                pw.cached_weapon_list() if on else {}, self.state.gd)

    def _groups(self):
        kind = self.kind.currentData()
        groups = sorted({i.group for i in getattr(self, "items", []) if i.kind == kind and i.group})
        self.group.blockSignals(True)
        cur = self.group.currentData()
        self.group.clear(); self.group.addItem("Any element" if kind == "resonator" else "Any weapon type", "")
        for g in groups:
            self.group.addItem(g, g)
        i = self.group.findData(cur)
        self.group.setCurrentIndex(max(0, i))
        self.group.blockSignals(False)

    def refresh(self):
        if not self._loaded:
            return
        self.items = self._items()
        self._groups()
        kind, rar, own, grp = (self.kind.currentData(), self.rarity.currentData(), self.owned.currentData(),
                               self.group.currentData())
        q = self.search.text().strip().lower()
        sel = [i for i in self.items if i.kind == kind and i.rarity >= 4 and (not rar or i.rarity == rar)
               and (own is None or i.owned == own) and (not grp or i.group == grp)
               and (not self.limited.isChecked() or i.limited) and (not q or q in i.name.lower())]
        clear_layout(self.flow)
        on = self.state.prydwen_on()
        for it in sel:
            self.flow.addWidget(Tile(it, self.state.images, on))
        s = collection.summary(self.items)
        name = "resonators" if kind == "resonator" else "weapons"
        a5, n5 = s[f"{kind}_5"]; a4, n4 = s[f"{kind}_4"]
        self.summary.setText(f"5★ {name}: <b>{a5}</b> / {n5} owned  ·  4★ {name}: <b>{a4}</b> / {n4} owned  ·  "
                             f"showing {len(sel)}")
