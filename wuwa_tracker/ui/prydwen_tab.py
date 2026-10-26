"""Prydwen tab: tier list + character info (data and images from prydwen.gg, linked back to the full guides)."""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QTabWidget, QVBoxLayout, QWidget)

from ..core.prydwen import CHAR_URL, TIER_URL, key
from . import theme as T
from .widgets import FlowLayout, card, clear_layout

TIER_COLORS = {"T0": "#ff5c5c", "T0.5": "#ff8a4c", "T1": "#f5c518", "T1.5": "#c8d64a", "T2": "#4cc38a",
               "T3": "#4aa3df", "T4": "#8f8fb3", "T5": "#6b6e7b"}
ELEMENT_COLORS = {"Fusion": "#ff6b4a", "Glacio": "#5ec8ff", "Electro": "#b37aff", "Aero": "#4fe0b0",
                  "Spectro": "#f5d76e", "Havoc": "#d35a9c"}
MARKS = {"up": ("▲", T.GREEN, "Moved up"), "down": ("▼", T.RED, "Moved down"), "new": ("NEW", T.GOLD, "New")}


def tier_color(t: str) -> str:
    return TIER_COLORS.get(t.split()[0] if t else "", T.MUTED)


class Fetch(QThread):
    done = Signal(object, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(), "")
        except Exception as e:
            self.done.emit(None, f"{type(e).__name__}: {e}")


class Tile(QFrame):
    clicked = Signal(str, str)     # slug, name
    double_clicked = Signal(str)   # slug

    def __init__(self, entry, owned: int, images):
        super().__init__()
        self.entry = entry
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(84)
        border = T.GOLD if owned else T.BORDER
        self.setStyleSheet(f"QFrame#tile {{ background:{T.CARD2}; border:1px solid {border}; border-radius:8px; }}")
        self.setObjectName("tile")
        v = QVBoxLayout(self); v.setContentsMargins(4, 4, 4, 4); v.setSpacing(2)
        holder = QWidget(); holder.setFixedSize(74, 74)
        icon = QLabel(holder); icon.setFixedSize(74, 74); icon.setAlignment(Qt.AlignCenter)
        rar = T.GOLD if entry.rarity == 5 else T.PURPLE
        icon.setStyleSheet(f"background:{T.CARD}; border-radius:6px; border-bottom:3px solid {rar};")
        images.set_on(icon, entry.icon, 70)
        if entry.mark in MARKS:
            txt, col, tip = MARKS[entry.mark]
            m = QLabel(txt, holder); m.setStyleSheet(f"color:{col}; font-weight:800; font-size:8pt; background:transparent;")
            m.move(3, 2)
        el = QLabel(entry.element[:1], holder)
        el.setStyleSheet(f"background:{ELEMENT_COLORS.get(entry.element, T.MUTED)}; color:#111; border-radius:8px;"
                         "font-size:7pt; font-weight:800;")
        el.setFixedSize(16, 16); el.setAlignment(Qt.AlignCenter); el.move(56, 2)
        if owned:
            seq = "S6+" if owned > 7 and entry.rarity == 5 else (f"S{owned - 1}" if entry.rarity == 5 else f"×{owned}")
            o = QLabel(seq, holder)
            o.setStyleSheet(f"background:{T.GOLD}; color:#111; border-radius:4px; font-size:7pt; font-weight:800; padding:0 3px;")
            o.adjustSize(); o.move(74 - o.width() - 2, 74 - o.height() - 4)
        v.addWidget(holder, 0, Qt.AlignHCenter)
        n = QLabel(entry.name); n.setWordWrap(True); n.setAlignment(Qt.AlignCenter)
        n.setStyleSheet("font-size:8pt;")
        v.addWidget(n)
        self.setToolTip(f"{entry.name} · {entry.element} · {entry.role}\nTier {entry.tier} (at {entry.sequence or 'S0'})"
                        + (f"\nTags: {', '.join(entry.tags)}" if entry.tags else "")
                        + (f"\nYou own: {seq}" if owned else ""))

    def mousePressEvent(self, e):
        self.clicked.emit(self.entry.slug, self.entry.name)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit(self.entry.slug)


class PrydwenTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.tl = None
        self.workers = []
        outer = QVBoxLayout(self); outer.setContentsMargins(20, 10, 20, 16)
        self.sub = QTabWidget()
        outer.addWidget(self.sub)
        page = QWidget()
        root = QHBoxLayout(page); root.setContentsMargins(0, 8, 0, 0); root.setSpacing(18)
        self.sub.addTab(page, "Tier list && my characters")
        from .web_view import PrydwenWeb
        self.web = PrydwenWeb(state.prydwen.dir / "web")
        self.sub.addTab(self.web, "Prydwen website · guides")
        self.sub.currentChanged.connect(lambda i: self.web.ensure_loaded() if self.sub.widget(i) is self.web else None)

        # ---------------- left: tier list
        left = QVBoxLayout(); left.setSpacing(10)
        top = QHBoxLayout()
        t = QLabel("Tower of Adversity"); t.setObjectName("h1")
        t.setToolTip("Click a character for details, double-click for the full Prydwen guide")
        top.addWidget(t); top.addStretch()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search character…"); self.search.setFixedWidth(180)
        self.only_owned = QCheckBox("Only mine")
        self.refresh_btn = QPushButton("↻ Refresh")
        site = QPushButton("Prydwen tier list page")
        site.clicked.connect(lambda: self.open_guide(TIER_URL))
        for w in (self.search, self.only_owned, self.refresh_btn, site):
            top.addWidget(w)
        left.addLayout(top)
        self.status = QLabel(); self.status.setObjectName("muted"); self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.grid_w = QWidget(); self.grid_w.setObjectName("scrollInner")
        self.grid = QGridLayout(self.grid_w); self.grid.setHorizontalSpacing(10); self.grid.setVerticalSpacing(10)
        sc = QScrollArea(); sc.setWidget(self.grid_w); sc.setWidgetResizable(True)
        left.addWidget(sc, 1)
        credit = QLabel("Tier list, ratings and images © <a style='color:#f5c518' href='https://www.prydwen.gg/wuthering-waves'>"
                        "Prydwen.gg</a> · game art © Kuro Games. Loaded on demand and cached; open the guides on Prydwen "
                        "for the full reviews and builds. Not affiliated with Prydwen.gg · personal use only.")
        credit.setObjectName("muted"); credit.setOpenExternalLinks(True); credit.setWordWrap(True)
        left.addWidget(credit)
        root.addLayout(left, 1)

        # ---------------- right: character info
        cw, self.info = card()
        cw.setFixedWidth(400)
        self.info_scroll = QScrollArea(); self.info_scroll.setWidgetResizable(True)
        inner = QWidget(); inner.setObjectName("scrollInner"); self.info_lay = QVBoxLayout(inner); self.info_lay.setContentsMargins(0, 0, 0, 0)
        self.info_scroll.setWidget(inner)
        self.info.addWidget(self.info_scroll)
        root.addWidget(cw)
        self._placeholder("Click a character to see Prydwen's ratings, best weapons and echo sets.")

        self.refresh_btn.clicked.connect(lambda: self.load(force=True))
        self.search.textChanged.connect(self.render)
        self.only_owned.toggled.connect(self.render)
        state.changed.connect(self.render)
        # load (from cache if fresh) shortly after start-up, so portraits on the Tracker tab work too
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1200, self.load)

    # ---------------- loading
    def _run(self, fn, cb):
        w = Fetch(fn)
        w.done.connect(cb)
        w.finished.connect(lambda: self.workers.remove(w) if w in self.workers else None)
        self.workers.append(w)
        w.start()

    def load(self, force=False):
        if not self.state.prydwen_on():
            self.status.setText("Prydwen is turned off in Settings.")
            return
        self.status.setText("Loading tier list from prydwen.gg…")
        self.refresh_btn.setEnabled(False)
        def fetch():
            tl = self.state.prydwen.tier_list(force=force)
            try:
                self.state.prydwen.character_list(force=force)     # card art for the banner cards
            except Exception:
                pass
            return tl
        self._run(fetch, self.on_tier_list)

    def on_tier_list(self, tl, err):
        self.refresh_btn.setEnabled(True)
        if err:
            self.status.setText(f"⚠ Could not load the tier list ({err}). Check your internet connection, or use "
                                "'Open on prydwen.gg'.")
            return
        self.tl = tl
        age = time.time() - tl.fetched
        when = datetime.fromtimestamp(tl.fetched).strftime("%Y-%m-%d %H:%M")
        self.status.setText(f"{len(tl.entries)} entries · fetched {when}"
                            + (" (cached)" if age > 60 else "") + " · gold border = you own it (from your pulls)")
        first = getattr(self, "_had_list", False) is False
        self._had_list = True
        self.render()
        if first:
            self.state.changed.emit()   # portraits on the Tracker tab can now be resolved

    # ---------------- tier grid
    def render(self):
        if not self.tl:
            return
        clear_layout(self.grid)
        owned = self.state.owned()
        q = key(self.search.text())
        roles = ["DPS", "Hybrid", "Support"]
        for c, r in enumerate(roles, start=1):
            h = QLabel(r); h.setObjectName("h2"); h.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(h, 0, c)
        row = 1
        for tier in self.tl.tiers:
            entries = [e for e in self.tl.entries if e.tier == tier]
            if q:
                entries = [e for e in entries if q in key(e.name)]
            if self.only_owned.isChecked():
                entries = [e for e in entries if owned.get(key(e.name))]
            if not entries:
                continue
            badge = QLabel(tier); badge.setAlignment(Qt.AlignCenter); badge.setFixedWidth(56)
            badge.setStyleSheet(f"background:{tier_color(tier)}; color:#111; font-size:14pt; font-weight:800;"
                                "border-radius:8px;")
            self.grid.addWidget(badge, row, 0)
            for c, r in enumerate(roles, start=1):
                cell = QFrame(); cell.setStyleSheet(f"QFrame {{ background:{T.CARD}; border-radius:8px; }}")
                fl = FlowLayout(cell, spacing=6); fl.setContentsMargins(6, 6, 6, 6)
                for e in entries:
                    if e.role == r:
                        tile = Tile(e, owned.get(key(e.name), 0), self.state.images)
                        tile.clicked.connect(self.show_character)
                        tile.double_clicked.connect(lambda sl: self.open_guide(CHAR_URL.format(slug=sl)))
                        fl.addWidget(tile)
                self.grid.addWidget(cell, row, c)
            row += 1
        for c in (1, 2, 3):
            self.grid.setColumnStretch(c, 1)
        self.grid.setRowStretch(row, 1)

    def open_guide(self, url):
        if self.web.open(url):
            self.sub.setCurrentWidget(self.web)

    # ---------------- character panel
    def _placeholder(self, text):
        clear_layout(self.info_lay)
        l = QLabel(text); l.setObjectName("muted"); l.setWordWrap(True)
        self.info_lay.addWidget(l); self.info_lay.addStretch()

    def show_character(self, slug, name):
        self._placeholder(f"Loading {name} from prydwen.gg…")
        self._run(lambda: self.state.prydwen.character(slug), lambda c, err: self.on_character(c, err, slug, name))

    def on_character(self, c, err, slug, name):
        if err:
            self._placeholder(f"⚠ Could not load {name}: {err}")
            b = QPushButton("Open guide on prydwen.gg")
            b.clicked.connect(lambda: self.open_guide(CHAR_URL.format(slug=slug)))
            self.info_lay.insertWidget(1, b)
            return
        L = self.info_lay
        clear_layout(L)
        owned = self.state.owned()
        entry = self.tl.by_key().get(key(c.name)) if self.tl else None
        rarity = entry.rarity if entry else c.rarity

        img = QLabel(); img.setAlignment(Qt.AlignCenter); img.setFixedHeight(290)
        img.setStyleSheet(f"background:{T.CARD2}; border-radius:10px;")
        self.state.images.set_on(img, c.card, 220, 280)
        L.addWidget(img)

        title = QLabel(f"{c.name}"); title.setObjectName("h1")
        title.setStyleSheet(f"color:{ELEMENT_COLORS.get(c.element, T.TEXT)}; font-size:18pt; font-weight:800;")
        L.addWidget(title)
        n_own = owned.get(key(c.name), 0)
        extras = {key(k): (k, v) for k, v in self.state.extras().items()}
        gift = extras.get(key(c.name))
        if n_own:
            own_txt = f"You own it: <b>S{min(n_own - 1, 6)}</b>" if rarity == 5 else f"You own it ×{n_own}"
            if gift:
                own_txt += f" <span style='color:{T.MUTED}'>(incl. {gift[1]} not from pulls)</span>"
        else:
            own_txt = "Not owned yet"
        sub = QLabel(f"{'★' * rarity if rarity else ''}  {c.element}  ·  {own_txt}")
        sub.setTextFormat(Qt.RichText); sub.setWordWrap(True); L.addWidget(sub)
        gb = QPushButton("Remove from 'owned outside pulls'" if gift else "＋ I own this (gift / free unit)")
        gb.setToolTip("For characters you got without pulling (event gifts, free selectors). They then count as "
                      "owned in badges, filters and the AI assistant.")
        def toggle(_=False, name=c.name, g=gift):
            self.state.set_extra(g[0] if g else name, 0 if g else 1)
            self.on_character(c, "", slug, name)
        gb.clicked.connect(toggle)
        L.addWidget(gb)
        if entry and entry.tags:
            tags = QLabel("Tags: " + ", ".join(entry.tags)); tags.setObjectName("muted"); tags.setWordWrap(True)
            L.addWidget(tags)

        for r in c.roles:
            h = QLabel(f"{r['role']}  [{r['sequence'] or 'S0'}]"); h.setObjectName("h2"); L.addWidget(h)
            g = QGridLayout(); g.setHorizontalSpacing(8)
            for i, (lab, val) in enumerate(r["ratings"].items()):
                v = QLabel(val); v.setAlignment(Qt.AlignCenter); v.setFixedWidth(46)
                v.setStyleSheet(f"background:{tier_color(val)}; color:#111; font-weight:800; border-radius:5px;")
                g.addWidget(v, i, 0); g.addWidget(QLabel(lab), i, 1)
            L.addLayout(g)

        if c.weapons:
            h = QLabel("Best weapons"); h.setObjectName("h2"); L.addWidget(h)
            for w in c.weapons[:6]:
                row = QHBoxLayout()
                ic = QLabel(); ic.setFixedSize(34, 34)
                self.state.images.set_on(ic, w["icon"], 34)
                col = T.GOLD if w["rarity"] == 5 else (T.PURPLE if w["rarity"] == 4 else T.BLUE)
                mine = "  ✓ owned" if owned.get(key(w["name"])) else ""
                t = QLabel(f"<span style='color:{col}'>{w['name']}</span>"
                           f"{' (R' + str(w['refine']) + ')' if w['refine'] else ''}"
                           f"<span style='color:{T.GREEN}'>{mine}</span>")
                t.setTextFormat(Qt.RichText)
                row.addWidget(ic); row.addWidget(t, 1)
                L.addLayout(row)
        if c.echo_sets:
            h = QLabel("Echo sets"); h.setObjectName("h2"); L.addWidget(h)
            for s in c.echo_sets[:4]:
                row = QHBoxLayout()
                ic = QLabel(); ic.setFixedSize(30, 30)
                self.state.images.set_on(ic, s["icon"], 30)
                row.addWidget(ic); row.addWidget(QLabel(s["name"]), 1)
                L.addLayout(row)

        upd = QLabel(f"Prydwen guide last updated: {c.updated or '?'}"); upd.setObjectName("muted"); L.addWidget(upd)
        b = QPushButton("Read the full guide (Prydwen)"); b.setObjectName("primary")
        b.setToolTip("Opens Prydwen's guide page in the 'Prydwen website' sub-tab")
        b.clicked.connect(lambda: self.open_guide(c.url))
        L.addWidget(b)
        rb = QPushButton("↻ Reload this character")
        rb.clicked.connect(lambda: self._run(lambda: self.state.prydwen.character(slug, force=True),
                                             lambda cc, e: self.on_character(cc, e, slug, name)))
        L.addWidget(rb)
        L.addStretch()
