from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSize, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QTableView,
                               QVBoxLayout, QWidget)

from ..core.analysis import pity_with_rows, pity_with_rows_4
from . import theme as T

COLS = ["Pull No.", "Item Name", "Rarity", "Pity", "Banner", "Patch", "Date (local)"]
QCOLOR = {5: QColor(T.GOLD), 4: QColor(T.PURPLE), 3: QColor(T.BLUE)}


class PullModel(QAbstractTableModel):
    ICON = 30

    def __init__(self, state=None):
        super().__init__()
        self.rows = []
        self.state = state
        self.icons = {}        # url -> scaled QPixmap
        self.url_rows = {}     # url -> row indexes waiting for it
        if state is not None:
            state.images.ready.connect(self._icon_ready)

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.url_rows = {}
        self.endResetModel()

    def _blank(self):
        if not hasattr(self, "_blank_pm"):
            from PySide6.QtGui import QPixmap
            self._blank_pm = QPixmap(self.ICON, self.ICON)
            self._blank_pm.fill(QColor(0, 0, 0, 0))
        return self._blank_pm

    def _icon(self, row):
        r = self.rows[row]
        url = r.get("icon")
        if not url or self.state is None:
            return self._blank()
        if url in self.icons:
            return self.icons[url]
        pm = self.state.images.cached(url)
        if pm is None:
            self.url_rows.setdefault(url, set()).add(row)
            return self._blank()
        from PySide6.QtCore import Qt as _Qt
        self.icons[url] = pm.scaled(self.ICON, self.ICON, _Qt.KeepAspectRatio, _Qt.SmoothTransformation)
        return self.icons[url]

    def _icon_ready(self, url):
        for row in self.url_rows.pop(url, ()):
            if row < len(self.rows):
                i = self.index(row, 1)
                self.dataChanged.emit(i, i, [Qt.DecorationRole])

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(COLS)

    def headerData(self, s, o, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and o == Qt.Horizontal:
            return COLS[s]

    def data(self, idx, role=Qt.DisplayRole):
        r = self.rows[idx.row()]
        c = idx.column()
        if role == Qt.DisplayRole:
            return r["display"][c]
        if role == Qt.UserRole:          # sort key
            return r["sort"][c]
        if role == Qt.DecorationRole and c == 1:
            return self._icon(idx.row())
        if role == Qt.ForegroundRole and c in (1, 2, 3):
            return QCOLOR.get(r["quality"])
        if role == Qt.TextAlignmentRole and c in (0, 2, 3):
            return Qt.AlignCenter


class FilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.text = ""
        self.pool = None
        self.qualities = {3, 4, 5}
        self.setSortRole(Qt.UserRole)

    def filterAcceptsRow(self, row, parent):
        r = self.sourceModel().rows[row]
        if self.pool is not None and r["pool"] != self.pool:
            return False
        if r["quality"] not in self.qualities:
            return False
        return not self.text or self.text in r["display"][1].lower()


class HistoryTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        title = QLabel("Pull History"); title.setObjectName("h1")
        lay.addWidget(title)

        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("🔍  Search for something…")
        self.pool = QComboBox()
        self.q = {q: QCheckBox(f"{q}✦") for q in (5, 4, 3)}
        bar.addWidget(self.search, 2); bar.addWidget(self.pool, 1)
        for q, cb in self.q.items():
            cb.setChecked(q != 3)
            cb.setStyleSheet(f"color:{QCOLOR[q].name()}; font-weight:700;")
            bar.addWidget(cb)
        self.count = QLabel(); self.count.setObjectName("muted")
        bar.addWidget(self.count)
        lay.addLayout(bar)

        self.model = PullModel(state)
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setAlternatingRowColors(True)
        self.view.verticalHeader().hide()
        self.view.setSelectionBehavior(QTableView.SelectRows)
        self.view.setShowGrid(False)
        self.view.setIconSize(QSize(PullModel.ICON, PullModel.ICON))
        self.view.verticalHeader().setDefaultSectionSize(PullModel.ICON + 6)
        hh = self.view.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        lay.addWidget(self.view)

        self.search.textChanged.connect(self.apply)
        self.pool.currentIndexChanged.connect(self.apply)
        for cb in self.q.values():
            cb.toggled.connect(self.apply)
        state.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        gd = self.state.gd
        cur = self.pool.currentData()
        self.pool.blockSignals(True)
        self.pool.clear()
        self.pool.addItem("All banners", None)
        for pt in self.state.stats:
            self.pool.addItem(gd.name(pt), pt)
        i = self.pool.findData(cur if cur is not None else 1)
        self.pool.setCurrentIndex(max(i, 0))
        self.pool.blockSignals(False)

        p4 = pity_with_rows_4(self.state.pulls)
        rows, n_per_pool = [], {}
        for p, pity in pity_with_rows(self.state.pulls):
            n_per_pool[p.pool_type] = n_per_pool.get(p.pool_type, 0) + 1
            n = n_per_pool[p.pool_type]
            shown_pity = pity if p.quality == 5 else (p4[p.key] if p.quality == 4 else pity)
            local = p.time.astimezone()
            icon = (self.state.prydwen.portrait_url(p.name, p.resource_id)
                    if self.state.prydwen_on() and (p.quality >= 4 or p.resource_id >= 100000) else None)
            rows.append({
                "pool": p.pool_type, "quality": p.quality, "icon": icon,
                "display": [str(n), p.name, "✦" * p.quality, str(shown_pity), gd.name(p.pool_type),
                            gd.patch_of(p.time) or "", local.strftime("%Y-%m-%d %H:%M:%S")],
                "sort": [n, p.name, p.quality, shown_pity, p.pool_type, gd.patch_of(p.time) or "", p.time.timestamp() * 100 + p.group],
            })
        self.model.set_rows(rows)
        self.view.sortByColumn(6, Qt.DescendingOrder)
        self.apply()

    def apply(self):
        self.proxy.text = self.search.text().strip().lower()
        self.proxy.pool = self.pool.currentData()
        self.proxy.qualities = {q for q, cb in self.q.items() if cb.isChecked()}
        self.proxy.invalidate()
        self.count.setText(f"{self.proxy.rowCount():,} / {self.model.rowCount():,} pulls")
