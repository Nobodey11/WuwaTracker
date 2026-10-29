"""Small always-on-top 'pull session' overlay: current pity, guarantee and the odds for the next pull / next 10,
for the character and weapon banner. Updates after every import. Drag to move; × hides it until the next game.

Note: like any overlay window it shows over the game in (borderless) windowed mode, not in exclusive full screen.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core import probability as pr
from . import theme as T


class PullOverlay(QWidget):
    def __init__(self, state):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.state = state
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("WuWa pull overlay")
        box = QWidget(self); box.setObjectName("ovl")
        box.setStyleSheet("QWidget#ovl { background: rgba(14,15,19,215); border: 1px solid rgba(245,197,24,140);"
                          " border-radius: 10px; } QLabel { background: transparent; color: #e8e8ec; font-size: 9pt; }")
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(box)
        v = QVBoxLayout(box); v.setContentsMargins(12, 8, 12, 10); v.setSpacing(4)
        top = QHBoxLayout()
        t = QLabel(f"<b style='color:{T.GOLD if T.DARK else '#f5c518'}'>WuWa</b> <b>pulls</b>")
        close = QPushButton("×"); close.setFixedSize(20, 20); close.setCursor(Qt.PointingHandCursor)
        close.setStyleSheet("QPushButton { background: transparent; color: #9a9caa; border: none; font-size: 12pt; }"
                            "QPushButton:hover { color: #ffffff; }")
        close.setToolTip("Hide until the next game session (Settings → Automation to turn it off)")
        close.clicked.connect(self.hide)
        top.addWidget(t); top.addStretch(); top.addWidget(close)
        v.addLayout(top)
        self.grid = QGridLayout(); self.grid.setHorizontalSpacing(14); self.grid.setVerticalSpacing(2)
        v.addLayout(self.grid)
        self.rows = {}
        for r, (pt, name) in enumerate(((1, "Character"), (2, "Weapon"))):
            labels = [QLabel(name), QLabel(), QLabel(), QLabel()]
            labels[0].setStyleSheet("color:#9a9caa;")
            for c, l in enumerate(labels):
                self.grid.addWidget(l, r, c)
            self.rows[pt] = labels
        hint = QLabel("next 1 · next 10 = chance of the featured 5★")
        hint.setStyleSheet("color:#7d8090; font-size: 7pt;")
        v.addWidget(hint)
        self._drag: QPoint | None = None
        pos = state.get("overlay_pos")
        self.adjustSize()
        if pos:
            self.move(int(pos[0]), int(pos[1]))
        else:
            from PySide6.QtGui import QGuiApplication
            scr = QGuiApplication.primaryScreen().availableGeometry()
            self.move(scr.right() - 300, scr.top() + 80)
        state.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        h = self.state.hazard()
        for pt, labels in self.rows.items():
            s = self.state.stats.get(pt)
            if not s:
                for l in labels[1:]:
                    l.setText("–")
                continue
            fc = s.featured_chance if s.featured_chance is not None else (0.5 if pt == 1 else 1.0)
            odds = pr.next_pulls(h, s.pity5, s.guaranteed, fc, s.pity4, self.state.gd.rates)
            g = " · <span style='color:#2fbf71'>guaranteed</span>" if s.guaranteed and s.has_5050 else ""
            labels[1].setText(f"pity <b>{s.pity5}</b>/80{g}")
            labels[2].setText(f"next 1: <b>{odds[1]['featured'] * 100:.1f}%</b>")
            labels[3].setText(f"next 10: <b style='color:#f5c518'>{odds[10]['featured'] * 100:.0f}%</b>")
        self.adjustSize()

    # drag anywhere to move
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.state.set("overlay_pos", [self.x(), self.y()])
