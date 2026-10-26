"""Small reusable widgets: cards, stat rows, matplotlib canvas, flow layout."""
from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget

from . import theme as T


def card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setObjectName("h2")
        lay.addWidget(t)
    return f, lay


class StatRow(QWidget):
    def __init__(self, label: str, color: str | None = None):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        self.l = QLabel(label)
        self.v = QLabel("–")
        self.v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        style = f"font-size: 11pt; color: {color};" if color else "font-size: 11pt;"
        self.l.setStyleSheet(style)
        self.v.setStyleSheet(style + "font-weight: 600;")
        h.addWidget(self.l)
        h.addStretch()
        h.addWidget(self.v)

    def set(self, value: str):
        self.v.setText(value)


class Chart(FigureCanvasQTAgg):
    def __init__(self, height=3.0):
        self.fig = Figure(figsize=(6, height), facecolor=T.CARD, tight_layout=True)
        super().__init__(self.fig)
        self.setStyleSheet(f"background: {T.CARD};")
        self.ax = self.fig.add_subplot(111)
        self.style_ax(self.ax)

    @staticmethod
    def style_ax(ax):
        ax.set_facecolor(T.CARD)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(T.BORDER)
        ax.tick_params(colors=T.MUTED, labelsize=8)
        ax.yaxis.label.set_color(T.MUTED)
        ax.xaxis.label.set_color(T.MUTED)
        ax.title.set_color(T.TEXT)
        ax.grid(axis="y", color=T.BORDER, linewidth=0.6, alpha=0.7)
        ax.set_axisbelow(True)

    def reset(self):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.style_ax(self.ax)
        return self.ax

    def legend(self, *axes):
        axes = axes or (self.ax,)
        handles, labels = [], []
        for a in axes:
            hd, lb = a.get_legend_handles_labels()
            handles += hd; labels += lb
        lg = self.ax.legend(handles, labels, frameon=False, fontsize=8, loc="upper left")
        for t in lg.get_texts():
            t.set_color(T.TEXT)


class FlowLayout(QLayout):
    """Wrapping layout for the 5★ portrait chips."""

    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self.items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        return self.items[i] if 0 <= i < len(self.items) else None

    def takeAt(self, i):
        return self.items.pop(i) if 0 <= i < len(self.items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._do(r, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self.items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        sp = self.spacing()
        for it in self.items:
            hint = it.sizeHint()
            nx = x + hint.width() + sp
            if nx - sp > rect.right() and line_h > 0:
                x, y = rect.x(), y + line_h + sp
                nx, line_h = x + hint.width() + sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x, line_h = nx, max(line_h, hint.height())
        return y + line_h - rect.y()


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
