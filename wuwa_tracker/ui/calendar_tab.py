"""Calendar tab: banners, events and resets with countdowns, your own events, and the rerun tracker."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from PySide6.QtCore import QDate, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDateEdit, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import calendar, game_import
from . import theme as T
from .header import fmt_td
from .i18n import tr
from .widgets import card

KIND_COLOR = {"banner": T.GOLD, "weapon banner": T.ORANGE, "event": T.BLUE, "my event": T.GREEN, "reset": T.MUTED}


class _BannerLoader(QThread):
    done = Signal(str)

    def __init__(self, prydwen, force):
        super().__init__()
        self.prydwen, self.force = prydwen, force

    def run(self):
        try:
            self.prydwen.banners(self.force)
            self.done.emit("")
        except Exception as e:
            self.done.emit(str(e))


class CalendarTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self); lay.setContentsMargins(20, 14, 20, 12); lay.setSpacing(16)

        left = QVBoxLayout()
        top = QHBoxLayout()
        t = QLabel(tr("Calendar")); t.setObjectName("h1")
        self.show_ended = QCheckBox("Show ended (last 14 days)")
        self.reload = QPushButton("↻"); self.reload.setToolTip("Reload banners from Prydwen")
        top.addWidget(t); top.addStretch(); top.addWidget(self.show_ended); top.addWidget(self.reload)
        left.addLayout(top)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "What", "Type", "When", "Details"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        left.addWidget(self.table, 1)
        self.note = QLabel(); self.note.setObjectName("muted"); self.note.setWordWrap(True)
        left.addWidget(self.note)
        c, l = card(tr("My events"))
        row = QHBoxLayout()
        self.ev_name = QLineEdit(); self.ev_name.setPlaceholderText("e.g. Tower of Adversity reset, event shop closes")
        self.ev_start = QDateEdit(); self.ev_start.setCalendarPopup(True); self.ev_start.setDate(QDate.currentDate())
        self.ev_end = QDateEdit(); self.ev_end.setCalendarPopup(True); self.ev_end.setDate(QDate.currentDate().addDays(14))
        add = QPushButton(tr("Add event")); add.setObjectName("primary"); add.clicked.connect(self.add_event)
        rm = QPushButton(tr("Delete")); rm.setToolTip("Delete the selected 'my event'"); rm.clicked.connect(self.del_event)
        for w in (self.ev_name, QLabel("from"), self.ev_start, QLabel("to"), self.ev_end, add, rm):
            row.addWidget(w)
        l.addLayout(row)
        left.addWidget(c)
        lay.addLayout(left, 3)

        c2, l2 = card(tr("Rerun tracker"))
        expl = QLabel("Known runs of each limited 5★ resonator, from the game data, Prydwen's banner page (remembered "
                      "every time the app loads it) and your own featured-banner pulls. Sorted by longest wait: those "
                      "are the likeliest reruns.")
        expl.setWordWrap(True); expl.setObjectName("muted")
        l2.addWidget(expl)
        self.reruns = QTableWidget(0, 4)
        self.reruns.setHorizontalHeaderLabels(["Resonator", "Status", "Last run ended", "Runs known"])
        self.reruns.verticalHeader().setVisible(False)
        self.reruns.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.reruns.setEditTriggers(QAbstractItemView.NoEditTriggers)
        l2.addWidget(self.reruns, 1)
        lay.addWidget(c2, 2)

        self.show_ended.toggled.connect(self.refresh)
        self.reload.clicked.connect(lambda: self.load(True))
        state.changed.connect(self.refresh)
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_countdowns); self.timer.start(30_000)
        self._entries = []
        self._loaded = False

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._loaded:
            self._loaded = True
            self.refresh()
            self.load(False)

    def load(self, force):
        if not self.state.prydwen_on():
            return
        self.reload.setEnabled(False)
        self.loader = _BannerLoader(self.state.prydwen, force)
        self.loader.done.connect(self._loaded_banners)
        self.loader.start()

    def _loaded_banners(self, err):
        self.reload.setEnabled(True)
        self.refresh()
        if err:
            self.note.setText(self.note.text() + f"  ⚠ Prydwen: {err}")

    def offset(self):
        return game_import.SERVER_UTC_OFFSET.get(self.state.get("server_region"), 8)

    def refresh(self):
        if not self._loaded:
            return
        now = datetime.now(timezone.utc)
        banners = self.state.prydwen.cached_banners() if self.state.prydwen_on() else []
        self._entries = calendar.build(self.state.gd.raw, banners, self.state.get("user_events"),
                                       self.state.get("server_region"), self.offset(), now,
                                       14 if self.show_ended.isChecked() else 0)
        self.table.setRowCount(len(self._entries))
        for i, e in enumerate(self._entries):
            st = e.status(now)
            dot = QTableWidgetItem("●")
            dot.setForeground(Qt.GlobalColor.green if st == "live" else Qt.GlobalColor.gray)
            dot.setToolTip(tr(st))
            self.table.setItem(i, 0, dot)
            name = QTableWidgetItem(e.title)
            f = name.font(); f.setBold(e.kind in ("banner", "weapon banner")); name.setFont(f)
            self.table.setItem(i, 1, name)
            k = QTableWidgetItem(e.kind)
            from PySide6.QtGui import QColor
            k.setForeground(QColor(KIND_COLOR.get(e.kind, T.MUTED)))
            self.table.setItem(i, 2, k)
            self.table.setItem(i, 3, QTableWidgetItem(""))
            self.table.setItem(i, 4, QTableWidgetItem(e.detail))
        self.update_countdowns()
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        src = "Prydwen.gg banner page + game data" if banners else "game data (Prydwen not loaded)"
        self.note.setText(f"Banners: {src}. Times for your server region ({self.state.get('server_region')}), shown in "
                          "your local time. Events: game data (`events`) and your own.")
        self.fill_reruns(banners)

    def update_countdowns(self):
        now = datetime.now(timezone.utc)
        for i, e in enumerate(self._entries):
            st = e.status(now)
            if st == "upcoming" and e.start:
                txt = f"{tr('Starts in')} {fmt_td(e.start - now)}  ({e.start.astimezone():%a %d %b %H:%M})"
            elif st == "live" and e.end:
                txt = f"{tr('Ends in')} {fmt_td(e.end - now)}  ({e.end.astimezone():%a %d %b %H:%M})"
            elif st == "ended" and e.end:
                txt = f"ended {e.end.astimezone():%d %b}"
            else:
                txt = "date not announced"
            it = self.table.item(i, 3)
            if it:
                it.setText(txt)

    def fill_reruns(self, banners):
        limited = sorted(self.state.gd.raw.get("limited_5star_resonators", []))
        hist = self.state.prydwen.banner_history() if self.state.prydwen_on() else []
        runs = calendar.rerun_tracker(limited, self.state.gd.raw, banners, hist, self.state.pulls)
        today = date.today()
        self.reruns.setRowCount(len(runs))
        for i, r in enumerate(runs):
            ds = r.days_since(today)
            status = "🟢 live now" if r.live else "🔜 upcoming" if r.upcoming else (f"{ds} days ago" if ds is not None else "unknown")
            last = r.last_end.strftime("%d %b %Y") if r.last_end else "–"
            srcs = sorted({s for _, _, s in r.runs})
            vals = [r.name, status, last, f"{len(r.runs)}" + (f"  ({', '.join(srcs)})" if srcs else "")]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if r.avg_gap:
                    it.setToolTip(f"Average time between runs: {r.avg_gap:.0f} days")
                self.reruns.setItem(i, j, it)

    def add_event(self):
        n = self.ev_name.text().strip()
        if not n:
            return
        s = self.ev_start.date().toString("yyyy-MM-dd"); e = self.ev_end.date().toString("yyyy-MM-dd")
        evs = list(self.state.get("user_events") or []) + [{"name": n, "start": s, "end": e, "note": ""}]
        self.state.set("user_events", evs)
        self.ev_name.clear()
        self.refresh()

    def del_event(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self._entries) or self._entries[r].kind != "my event":
            return
        title = self._entries[r].title
        evs = [e for e in (self.state.get("user_events") or []) if e.get("name") != title]
        self.state.set("user_events", evs)
        self.refresh()
