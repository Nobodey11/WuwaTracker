"""Convene simulator mini-game: pull for free with the real rules and an animated reveal."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)
from PySide6.QtGui import QColor

from ..core.simulator import ConveneSim, pools_from_pulls
from . import theme as T
from .widgets import StatRow, card

RARITY_BG = {
    5: "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #7a5a12, stop:0.6 #3a2c0a, stop:1 #1b1608)",
    4: "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4c2f80, stop:0.6 #271a44, stop:1 #15111f)",
    3: "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #24406a, stop:0.6 #18263c, stop:1 #10151f)",
}
RARITY_BORDER = {5: T.GOLD, 4: T.PURPLE, 3: "#4a6a9a"}


class Slot(QFrame):
    W, H = 128, 196

    def __init__(self):
        super().__init__()
        self.setFixedSize(self.W, self.H)
        v = QVBoxLayout(self); v.setContentsMargins(4, 4, 4, 6); v.setSpacing(2)
        self.img = QLabel(); self.img.setFixedSize(self.W - 8, 130); self.img.setAlignment(Qt.AlignCenter)
        self.stars = QLabel(); self.stars.setAlignment(Qt.AlignCenter)
        self.name = QLabel(); self.name.setAlignment(Qt.AlignCenter); self.name.setWordWrap(True)
        self.sub = QLabel(); self.sub.setAlignment(Qt.AlignCenter)
        for w in (self.img, self.stars, self.name, self.sub):
            w.setStyleSheet("background: transparent; border: none;")
            v.addWidget(w)
        self.hidden_card()

    def hidden_card(self):
        self.setStyleSheet(f"QFrame {{ background:{T.CARD2}; border:1px solid {T.BORDER}; border-radius:10px; }}")
        self.img.clear(); self.img.setText("✦"); self.img.setStyleSheet(f"color:{T.BORDER}; font-size:30pt; background:transparent; border:none;")
        self.stars.clear(); self.name.clear(); self.sub.clear()

    def reveal(self, item, images, prydwen):
        r = item.rarity
        self.setStyleSheet(f"QFrame {{ background:{RARITY_BG[r]}; border:2px solid {RARITY_BORDER[r]}; border-radius:10px; }}")
        self.img.setText(item.name[:2].upper() if r >= 4 else "⚔")
        self.img.setStyleSheet(f"color:{RARITY_BORDER[r]}; font-size:22pt; font-weight:800; background:transparent; border:none;")
        url = prydwen.card_url(item.name, item.resource_id) if r >= 4 or item.resource_id else None
        if url:
            images.set_on(self.img, url, self.W - 8, 130, cover=True)
        self.stars.setText("★" * r)
        self.stars.setStyleSheet(f"color:{RARITY_BORDER[r]}; font-size:10pt; background:transparent; border:none;")
        self.name.setText(item.name)
        self.name.setStyleSheet("font-size:8pt; font-weight:700; background:transparent; border:none;")
        if r == 5:
            tag = {"won": "WON 50/50", "lost": "LOST 50/50", "guaranteed": "GUARANTEED"}.get(item.result, "FEATURED")
            col = T.RED if item.result == "lost" else T.GREEN
            self.sub.setText(f"pity {item.pity} · {tag}")
            self.sub.setStyleSheet(f"color:{col}; font-size:7pt; font-weight:800; background:transparent; border:none;")
        elif r == 4 and item.featured:
            self.sub.setText("rate-up")
            self.sub.setStyleSheet(f"color:{T.PURPLE}; font-size:7pt; background:transparent; border:none;")


class SimulatorTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.sim = None
        self.queue = []
        self.timer = QTimer(self); self.timer.timeout.connect(self._reveal_next)
        root = QHBoxLayout(self); root.setContentsMargins(20, 16, 20, 16); root.setSpacing(18)

        # ---------------- left: setup + stats
        left = QVBoxLayout(); left.setSpacing(14)
        c1, l1 = card("Convene simulator")
        info = QLabel("Free pulls with the real rules (soft pity, 50/50, 4✦ every 10). Just for fun: nothing is saved.")
        info.setObjectName("muted"); info.setWordWrap(True); l1.addWidget(info)
        f = QFormLayout()
        self.kind = QComboBox(); self.kind.addItem("Featured Resonator", False); self.kind.addItem("Featured Weapon", True)
        self.featured = QComboBox()
        self.real = QCheckBox("Use my real pity")
        self.real.setToolTip("Start from your current pity and 50/50 guarantee on that banner")
        self.anim = QCheckBox("Play convene animation")
        self.anim.setChecked(True)
        f.addRow("Banner", self.kind); f.addRow("Featured 5✦", self.featured); f.addRow("", self.real)
        f.addRow("", self.anim)
        l1.addLayout(f)
        reset = QPushButton("New session"); reset.clicked.connect(self.new_session)
        l1.addWidget(reset)
        c1.setFixedWidth(340)
        left.addWidget(c1)

        c2, l2 = card("Session")
        self.r_pulls = StatRow("Pulls"); self.r_ast = StatRow("Astrite spent")
        self.r_5 = StatRow("5✦ (featured)", T.GOLD); self.r_4 = StatRow("4✦", T.PURPLE)
        self.r_5050 = StatRow("50/50 won / lost"); self.r_avg = StatRow("Avg 5✦ pity")
        self.r_pity = StatRow("Current pity")
        for r in (self.r_pulls, self.r_ast, self.r_5, self.r_4, self.r_5050, self.r_avg, self.r_pity):
            l2.addWidget(r)
        c2.setFixedWidth(340)
        left.addWidget(c2)

        c3, l3 = card("Session drops")
        self.log = QListWidget()
        self.log.setStyleSheet(f"QListWidget {{ background:{T.CARD}; border:none; }}")
        l3.addWidget(self.log)
        c3.setFixedWidth(340)
        left.addWidget(c3, 1)
        root.addLayout(left)

        # ---------------- right: banner + results
        right = QVBoxLayout(); right.setSpacing(14)
        self.banner = QFrame(); self.banner.setFixedHeight(170)
        self.banner.setStyleSheet(f"QFrame {{ background:{T.CARD}; border:1px solid {T.BORDER}; border-radius:12px; }}")
        bl = QHBoxLayout(self.banner); bl.setContentsMargins(20, 10, 10, 10)
        bt = QVBoxLayout()
        self.b_title = QLabel(); self.b_title.setStyleSheet(f"font-size:22pt; font-weight:800; color:{T.GOLD}; border:none;")
        self.b_sub = QLabel(); self.b_sub.setStyleSheet(f"color:{T.MUTED}; border:none;"); self.b_sub.setWordWrap(True)
        bt.addStretch(); bt.addWidget(self.b_title); bt.addWidget(self.b_sub); bt.addStretch()
        bl.addLayout(bt, 1)
        self.b_art = QLabel(); self.b_art.setFixedSize(220, 150); self.b_art.setStyleSheet("border:none; background:transparent;")
        bl.addWidget(self.b_art)
        right.addWidget(self.banner)

        grid_w = QWidget(); self.grid = QGridLayout(grid_w); self.grid.setSpacing(10)
        self.slots = [Slot() for _ in range(10)]
        for i, s in enumerate(self.slots):
            self.grid.addWidget(s, i // 5, i % 5)
        right.addWidget(grid_w, 0, Qt.AlignHCenter)

        btns = QHBoxLayout(); btns.addStretch()
        self.b1 = QPushButton("Convene ×1   (160 Astrite)")
        self.b10 = QPushButton("Convene ×10   (1,600 Astrite)"); self.b10.setObjectName("primary")
        for b in (self.b1, self.b10):
            b.setFixedHeight(46); b.setMinimumWidth(240); btns.addWidget(b)
        self.skip = QPushButton("Skip animation"); btns.addWidget(self.skip)
        btns.addStretch()
        right.addLayout(btns)
        right.addStretch()
        root.addLayout(right, 1)

        self.b1.clicked.connect(lambda: self.convene(1))
        self.b10.clicked.connect(lambda: self.convene(10))
        self.skip.clicked.connect(self._reveal_all)
        self.kind.currentIndexChanged.connect(self.fill_featured)
        self.featured.currentIndexChanged.connect(self.new_session)
        self.real.toggled.connect(self.new_session)
        state.changed.connect(self._state_changed)
        self.fill_featured()

    # ---------------- setup
    def _state_changed(self):
        if self.sim is None or self.sim.stats.pulls == 0:
            self.fill_featured()

    def fill_featured(self):
        gd = self.state.gd
        weapon = self.kind.currentData()
        cur = gd.current_banners() + gd.upcoming_banners()
        key = "featured_5star_weapons" if weapon else "featured_5star_resonators"
        names = list(dict.fromkeys(n for b in cur for n in b.get(key, [])))
        extra = sorted(gd.raw.get("limited_5star_weapons" if weapon else "limited_5star_resonators", []))
        names += [n for n in extra if n not in names]
        self.featured.blockSignals(True)
        self.featured.clear(); self.featured.addItems(names or ["Featured 5✦"])
        self.featured.blockSignals(False)
        self.new_session()

    def new_session(self):
        gd, st = self.state.gd, self.state
        weapon = bool(self.kind.currentData())
        name = self.featured.currentText()
        pool4, pool3, rids = pools_from_pulls(st.pulls)
        banner = next((b for b in gd.current_banners() + gd.upcoming_banners()
                       if name in b.get("featured_5star_weapons" if weapon else "featured_5star_resonators", [])), None)
        feat4 = (banner or {}).get("featured_4star_resonators", []) if not weapon else []
        pool4 = [p for p in pool4 if p[2] == weapon] or pool4          # char banner: 4★ chars, weapon: 4★ weapons
        pt = 2 if weapon else 1
        s = st.stats.get(pt)
        real = self.real.isChecked() and s is not None
        self.sim = ConveneSim(st.hazard(), gd.rates, weapon, name, sorted(gd.standard_resonators), feat4, pool4, pool3,
                              pity5=s.pity5 if real else 0, pity4=s.pity4 if real else 0,
                              guaranteed=bool(real and s.guaranteed), featured5_rid=rids.get(name))
        self.queue.clear(); self.timer.stop()
        for sl in self.slots:
            sl.hidden_card()
        self.log.clear()
        self.b_title.setText(name)
        when = f"{banner['patch']} phase {banner.get('phase')}" if banner else "simulated banner"
        self.b_sub.setText(f"{'Weapon' if weapon else 'Resonator'} Convene · {when}"
                           + (f" · rate-up 4✦: {', '.join(feat4)}" if feat4 else ""))
        self.b_art.clear()
        if st.prydwen_on():
            st.images.set_on(self.b_art, st.prydwen.card_url(name, rids.get(name)), 220, 150, cover=True)
        self.update_stats()

    # ---------------- pulling
    def convene(self, n):
        if not self.b10.isEnabled():
            return
        if self.queue:
            self._reveal_all()
        items = self.sim.pull(n)
        for sl in self.slots:
            sl.hidden_card()
            sl.setVisible(True)
        for sl in self.slots[n:]:
            sl.setVisible(False)
        self.queue = list(zip(self.slots, items))
        self.update_stats()
        for it in items:
            if it.rarity >= 4:
                self._log(it)
        if self.anim.isChecked():
            from .convene_animation import ConveneAnimation
            self.b1.setEnabled(False); self.b10.setEnabled(False)
            a = ConveneAnimation(self.window().centralWidget(), items, self.state.images, self.state.prydwen)
            a.finished.connect(lambda: self._after_animation(items))
        else:
            self._after_animation(items)

    def _after_animation(self, items):
        self.b1.setEnabled(True); self.b10.setEnabled(True)
        best = max(i.rarity for i in items)
        if best == 5:
            self._flash(T.GOLD)
        elif best == 4:
            self._flash(T.PURPLE)
        self.timer.start(140)

    def _flash(self, color):
        self.banner.setStyleSheet(f"QFrame {{ background:{T.CARD}; border:3px solid {color}; border-radius:12px; }}")
        QTimer.singleShot(900, lambda: self.banner.setStyleSheet(
            f"QFrame {{ background:{T.CARD}; border:1px solid {T.BORDER}; border-radius:12px; }}"))

    def _reveal_next(self):
        if not self.queue:
            self.timer.stop(); return
        slot, item = self.queue.pop(0)
        slot.reveal(item, self.state.images, self.state.prydwen)

    def _reveal_all(self):
        while self.queue:
            self._reveal_next()
        self.timer.stop()

    def _log(self, it):
        txt = f"{'★' * it.rarity}  {it.name}"
        if it.rarity == 5:
            txt += f"   (pity {it.pity}{', ' + it.result if it.result else ''})"
        li = QListWidgetItem(f"#{self.sim.stats.pulls}  {txt}")
        li.setForeground(QColor(T.GOLD if it.rarity == 5 else T.PURPLE))
        self.log.insertItem(0, li)

    def update_stats(self):
        s = self.sim.stats
        self.r_pulls.set(f"{s.pulls:,}")
        self.r_ast.set(f"{self.sim.astrite:,}")
        self.r_5.set(f"{s.five} ({s.featured5})")
        self.r_4.set(str(s.four))
        self.r_5050.set(f"{s.wins} / {s.losses}" if not self.sim.weapon_banner else "–")
        self.r_avg.set(f"{sum(s.five_pities) / len(s.five_pities):.1f}" if s.five_pities else "–")
        g = " · guaranteed" if self.sim.guaranteed and not self.sim.weapon_banner else ""
        self.r_pity.set(f"5✦ {self.sim.pity5}/80 · 4✦ {self.sim.pity4}/10{g}")
