"""Planner tab: Astrite planner · Wishlist · Income · What if · Luck test."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from PySide6.QtCore import QDate, Qt, QThread, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QFormLayout, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
                               QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..core import planner, stats_tests
from ..core import probability as pr
from ..core.models import ASTRITE_PER_PULL
from . import theme as T
from .i18n import tr
from .util import pct
from .widgets import Chart, StatRow, card

SOURCES = ["Daily activity", "Lunite", "Tower of Adversity", "Whimpering Wastes", "Event", "Patch / maintenance",
           "Codes", "Exploration", "Other"]


def spin(maximum=10_000_000, value=0, step=1, suffix=""):
    s = QSpinBox(); s.setRange(0, maximum); s.setValue(value); s.setSingleStep(step)
    s.setGroupSeparatorShown(True)
    if suffix:
        s.setSuffix(suffix)
    return s


def big_label(text="–", color=None):
    l = QLabel(text); l.setObjectName("big")
    if color:
        l.setStyleSheet(f"color:{color};")
    return l


def qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def pydate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class PlannerTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        v = QVBoxLayout(self); v.setContentsMargins(20, 12, 20, 12)
        self.sub = QTabWidget(); self.sub.setObjectName("subtabs")
        self.plan = AstritePlanner(state)
        self.wish = WishlistPage(state)
        self.income = IncomePage(state)
        self.whatif = WhatIfPage(state)
        self.luck = LuckPage(state)
        for w, n in ((self.plan, "Astrite planner"), (self.wish, "Wishlist"), (self.income, "Income"),
                     (self.whatif, "What if"), (self.luck, "Luck test")):
            self.sub.addTab(w, tr(n))
        v.addWidget(self.sub)
        self.income.changed.connect(self.plan.refresh)
        self.income.changed.connect(self.wish.refresh)


# ====================================================================== shared state helpers
def banner_state(state, weapon: bool):
    pt = 2 if weapon else 1
    s = state.stats.get(pt)
    fc = 1.0 if weapon else 0.5
    if s and s.featured_chance is not None:
        fc = s.featured_chance
    return (s.pity5 if s else 0), (bool(s.guaranteed) if s and not weapon else False), fc


def banner_dates(state) -> list[tuple[str, date]]:
    """Useful target dates: end of the current banner phase and start of the next one."""
    from ..core.prydwen import banner_times
    out = []
    for b in state.gd.current_banners():
        out.append((f"End of {b['patch']} phase {b.get('phase')}", date.fromisoformat(b["end"])))
    for b in state.gd.upcoming_banners()[:2]:
        out.append((f"Start of {b['patch']} phase {b.get('phase')}", date.fromisoformat(b["start"])))
    if state.prydwen_on():
        for b in state.prydwen.cached_banners():
            s, e = banner_times(b)
            if b.get("section") == "current" and e:
                out.append((f"End of {b['name']} banner", date.fromisoformat(e[:10])))
    seen, uniq = set(), []
    for label, d in sorted(out, key=lambda x: x[1]):
        if d not in seen and d >= date.today():
            seen.add(d); uniq.append((label, d))
    return uniq


# ====================================================================== Astrite planner
class AstritePlanner(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 12, 0, 0); lay.setSpacing(16)
        c, l = card(tr("Astrite planner"))
        f = QFormLayout(); f.setSpacing(9); f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        saved = state.get("planner") or {}
        self.astrite = spin(value=saved.get("astrite", 0), step=160)
        self.tides = spin(10_000, saved.get("tides", 0))
        self.banner = QComboBox(); self.banner.addItem(tr("Character"), False); self.banner.addItem(tr("Weapon"), True)
        self.banner.setCurrentIndex(1 if saved.get("weapon") else 0)
        self.copies = spin(7, saved.get("copies", 1)); self.copies.setMinimum(1)
        self.target = QDateEdit(); self.target.setCalendarPopup(True); self.target.setDisplayFormat("ddd d MMM yyyy")
        dates = banner_dates(state)
        default = dates[0][1] if dates else date.today() + timedelta(days=21)
        try:
            t = date.fromisoformat(saved["target"]) if saved.get("target") else default
        except ValueError:
            t = default
        self.target.setDate(qdate(max(t, date.today())))
        self.quick = QComboBox(); self.quick.addItem("Jump to a banner date…", None)
        for label, d in dates:
            self.quick.addItem(f"{label} ({d:%d %b})", d.isoformat())
        self.quick.currentIndexChanged.connect(self._quick)
        self.rate = spin(5000, int(saved.get("rate", 0)))
        self.use_logged = QCheckBox(); self.use_logged.setChecked(saved.get("use_logged", True))
        self.extra = spin(value=saved.get("extra", 0), step=100)
        f.addRow(tr("Astrite now"), self.astrite)
        f.addRow(tr("Radiant Tides now") + " / Forging", self.tides)
        f.addRow(tr("Banner"), self.banner)
        f.addRow(tr("Copies wanted"), self.copies)
        f.addRow(tr("Target date"), self.target)
        f.addRow("", self.quick)
        f.addRow(tr("Use my logged income"), self.use_logged)
        f.addRow(tr("Income per day"), self.rate)
        self.extra.setToolTip(tr("Extra Astrite before then (events, patch rewards)"))
        f.addRow(tr("Extra Astrite"), self.extra)
        l.addLayout(f)
        self.rate_note = QLabel(); self.rate_note.setObjectName("muted"); self.rate_note.setWordWrap(True)
        l.addWidget(self.rate_note)
        self.state_note = QLabel(); self.state_note.setObjectName("muted"); self.state_note.setWordWrap(True)
        l.addWidget(self.state_note)
        l.addStretch()
        c.setFixedWidth(430)
        lay.addWidget(c)

        right = QVBoxLayout(); right.setSpacing(12)
        r, rl = card()
        grid = QGridLayout(); grid.setHorizontalSpacing(30)
        self.big = big_label()
        self.big_sub = QLabel(tr("Chance of getting it")); self.big_sub.setObjectName("muted")
        grid.addWidget(self.big, 0, 0); grid.addWidget(self.big_sub, 1, 0)
        self.pulls_big = big_label(color=T.TEXT)
        ps = QLabel(tr("Pulls on that date")); ps.setObjectName("muted")
        grid.addWidget(self.pulls_big, 0, 1); grid.addWidget(ps, 1, 1)
        rl.addLayout(grid)
        self.rows = {k: StatRow(tr(k)) for k in ("Days until then", "Astrite on that date", "Expected featured copies",
                                             "Pulls for 50 % / 90 %", "Date you reach 90 %", "Still needed for 90 %")}
        for w in self.rows.values():
            rl.addWidget(w)
        right.addWidget(r)
        ch, chl = card("Chance by date (saving at this income)")
        self.chart = Chart(3.0)
        chl.addWidget(self.chart)
        right.addWidget(ch, 1)
        lay.addLayout(right, 1)

        for w in (self.astrite, self.tides, self.copies, self.rate, self.extra):
            w.valueChanged.connect(self.refresh)
        self.banner.currentIndexChanged.connect(self.refresh)
        self.target.dateChanged.connect(self.refresh)
        self.use_logged.toggled.connect(self.refresh)
        state.changed.connect(self.refresh)
        self.refresh()

    def _quick(self, i):
        d = self.quick.itemData(i)
        if d:
            self.target.setDate(qdate(date.fromisoformat(d)))
        self.quick.blockSignals(True); self.quick.setCurrentIndex(0); self.quick.blockSignals(False)

    def income_per_day(self) -> float:
        if self.use_logged.isChecked():
            r = self.state.income_rate()
            self.rate.blockSignals(True); self.rate.setValue(int(round(r["astrite_per_day"]))); self.rate.blockSignals(False)
            self.rate.setEnabled(False)
            src = (f"logged over the last {r['days']} days" if r["source"] == "logged"
                   else "estimate from Income → sources (log at least 7 days to use your real income)")
            self.rate_note.setText(f"Income: {r['astrite_per_day']:.0f} Astrite/day, {src}.")
            return r["astrite_per_day"]
        self.rate.setEnabled(True)
        self.rate_note.setText("Income: your own number (Astrite per day).")
        return float(self.rate.value())

    def refresh(self):
        weapon = bool(self.banner.currentData())
        pity, g, fc = banner_state(self.state, weapon)
        self.state_note.setText(f"Starting from your real {'weapon' if weapon else 'character'} banner state: pity "
                                f"{pity}" + (", next 5★ guaranteed" if g else "") + ".")
        h = self.state.hazard()
        rate = self.income_per_day()
        target = pydate(self.target.date())
        a, t, cps, extra = self.astrite.value(), self.tides.value(), self.copies.value(), self.extra.value()
        p = planner.plan(h, a, t, target, rate, extra, copies=cps, pity=pity, guaranteed=g, featured_chance=fc)
        self.big.setText(pct(p.probability))
        self.big.setStyleSheet(f"color:{T.GREEN if p.probability >= 0.9 else T.GOLD if p.probability >= 0.5 else T.RED};")
        self.pulls_big.setText(f"{p.pulls:,}")
        self.rows["Days until then"].set(str(p.days))
        self.rows["Astrite on that date"].set(f"{p.astrite_at_target:,}")
        self.rows["Expected featured copies"].set(f"{p.expected_copies:.2f}")
        self.rows["Pulls for 50 % / 90 %"].set(f"{p.pulls_for_50} / {p.pulls_for_90}")
        d90 = planner.date_for_confidence(h, a + extra, t, rate, 0.9, cps, pity, g, fc)
        self.rows["Date you reach 90 %"].set(f"{d90:%a %d %b %Y}" if d90 else "not within 2 years")
        short = max(0, p.pulls_for_90 - p.pulls)
        self.rows["Still needed for 90 %"].set(f"{short} pulls ({short * ASTRITE_PER_PULL:,} Astrite)" if short else "✓ none")
        self.state.set("planner", {"astrite": a, "tides": t, "weapon": weapon, "copies": cps, "target": target.isoformat(),
                                   "rate": self.rate.value(), "use_logged": self.use_logged.isChecked(), "extra": extra})
        # chart: chance by date
        days = max(30, p.days + 45)
        max_pulls = (a + extra + int(rate * days)) // ASTRITE_PER_PULL + t
        curve = pr.featured_distribution(h, max_pulls, cps, pity, g, fc).curve
        xs = np.arange(days + 1)
        pulls = np.minimum((a + extra + rate * xs).astype(int) // ASTRITE_PER_PULL + t, len(curve) - 1)
        ax = self.chart.reset()
        dates = [date.today() + timedelta(days=int(x)) for x in xs]
        ax.plot(dates, curve[pulls] * 100, color=T.GOLD, lw=2)
        ax.axvline(target, color=T.PURPLE, lw=1, ls="--")
        ax.axhline(90, color=T.GREEN, lw=0.8, ls=":")
        ax.set_ylim(0, 102); ax.set_ylabel("chance %")
        ax.annotate(f" {pct(p.probability, 0)}", (target, p.probability * 100), color=T.TEXT, fontsize=9)
        self.chart.fig.autofmt_xdate()
        self.chart.draw_idle()


# ====================================================================== Wishlist
class WishlistPage(QWidget):
    COLS = ["Wish", "Type", "Copies", "Chance (with all above)", "Alone", "Avg. pulls", "Everything else if dropped"]

    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 12, 0, 0)
        top = QHBoxLayout()
        self.astrite = spin(step=160); self.tides = spin(10_000); self.forging = spin(10_000)
        saved = state.get("planner") or {}
        self.astrite.setValue(saved.get("astrite", 0)); self.tides.setValue(saved.get("tides", 0))
        self.until = QCheckBox("+ income until"); self.until_date = QDateEdit(); self.until_date.setCalendarPopup(True)
        self.until_date.setDate(qdate(date.today() + timedelta(days=42)))
        for lab, w in (("Astrite", self.astrite), ("Radiant Tides", self.tides), ("Forging Tides", self.forging)):
            top.addWidget(QLabel(lab)); top.addWidget(w)
        top.addWidget(self.until); top.addWidget(self.until_date); top.addStretch()
        lay.addLayout(top)
        info = QLabel("List what you want in priority order. Wishes are pulled top to bottom with one budget: Astrite is "
                      "shared, Radiant Tides only pay for characters and Forging Tides only for weapons. Your real pity "
                      "and guarantee are used for the first character and the first weapon.")
        info.setWordWrap(True); info.setObjectName("muted")
        lay.addWidget(info)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.name = QComboBox(); self.name.setEditable(True); self.name.setMinimumWidth(220)
        self.kind = QComboBox(); self.kind.addItem(tr("Character"), "character"); self.kind.addItem(tr("Weapon"), "weapon")
        self.copies = spin(7, 1); self.copies.setMinimum(1)
        b_add = QPushButton(tr("Add wish")); b_add.setObjectName("primary"); b_add.clicked.connect(self.add)
        b_up = QPushButton("▲"); b_up.setToolTip(tr("Move up")); b_up.clicked.connect(lambda: self.move(-1))
        b_dn = QPushButton("▼"); b_dn.setToolTip(tr("Move down")); b_dn.clicked.connect(lambda: self.move(1))
        b_rm = QPushButton(tr("Remove")); b_rm.clicked.connect(self.remove)
        for w in (self.name, self.kind, QLabel(tr("Copies")), self.copies, b_add):
            row.addWidget(w)
        row.addStretch()
        for w in (b_up, b_dn, b_rm):
            row.addWidget(w)
        lay.addLayout(row)
        self.advice = QLabel(); self.advice.setObjectName("h2"); self.advice.setWordWrap(True)
        lay.addWidget(self.advice)
        for w in (self.astrite, self.tides, self.forging):
            w.valueChanged.connect(self.refresh)
        self.until.toggled.connect(self.refresh); self.until_date.dateChanged.connect(self.refresh)
        self.kind.currentIndexChanged.connect(self._fill_names)
        state.changed.connect(self.refresh)
        self._fill_names()
        self.refresh()

    def _fill_names(self):
        gd = self.state.gd
        weapon = self.kind.currentData() == "weapon"
        names = []
        for b in gd.current_banners() + gd.upcoming_banners():
            names += b.get("featured_5star_weapons" if weapon else "featured_5star_resonators", [])
        if self.state.prydwen_on():
            for b in self.state.prydwen.cached_banners():
                if (b.get("category") == "weapon") == weapon:
                    names.append(b["name"].strip())
        names += sorted(gd.raw.get("limited_5star_weapons" if weapon else "limited_5star_resonators", []))
        self.name.clear()
        self.name.addItems(list(dict.fromkeys(names)))

    def wishes(self) -> list[planner.Wish]:
        return [planner.Wish(w["name"], w.get("kind", "character"), int(w.get("copies", 1)))
                for w in (self.state.get("wishlist") or [])]

    def _save(self, ws):
        self.state.set("wishlist", [{"name": w.name, "kind": w.kind, "copies": w.copies} for w in ws])
        self.refresh()

    def add(self):
        n = self.name.currentText().strip()
        if n:
            self._save(self.wishes() + [planner.Wish(n, self.kind.currentData(), self.copies.value())])

    def remove(self):
        r = self.table.currentRow()
        ws = self.wishes()
        if 0 <= r < len(ws):
            ws.pop(r); self._save(ws)

    def move(self, d):
        r = self.table.currentRow()
        ws = self.wishes()
        if 0 <= r < len(ws) and 0 <= r + d < len(ws):
            ws[r], ws[r + d] = ws[r + d], ws[r]
            self._save(ws)
            self.table.selectRow(r + d)

    def refresh(self):
        ws = self.wishes()
        h = self.state.hazard()
        cp, cg, fc = banner_state(self.state, False)
        wp, _, _ = banner_state(self.state, True)
        astrite = self.astrite.value()
        tides = self.tides.value()
        if self.until.isChecked():
            days = max(0, (pydate(self.until_date.date()) - date.today()).days)
            astrite += int(self.state.income_rate()["astrite_per_day"] * days)
        res = planner.wishlist(h, h, ws, astrite // ASTRITE_PER_PULL, tides, self.forging.value(), cp, cg, wp, fc)
        self.table.setRowCount(len(ws))
        for i, w in enumerate(ws):
            vals = [w.name, tr("Weapon") if w.kind == "weapon" else tr("Character"),
                    (f"R{w.copies}" if w.kind == "weapon" else f"S{w.copies - 1}") + f"  ({w.copies}×)",
                    pct(res.cumulative[i]), pct(res.alone[i]), f"{res.expected_pulls[i]:.0f}", pct(res.drop_one[i])]
            for j, val in enumerate(vals):
                it = QTableWidgetItem(val)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if j == 3:
                    c = res.cumulative[i]
                    it.setForeground(Qt.GlobalColor.green if c >= 0.9 else Qt.GlobalColor.yellow if c >= 0.5 else Qt.GlobalColor.red)
                self.table.setItem(i, j, it)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        budget = f"Budget: {res.budget_pulls} pulls from Astrite + {res.tides} Radiant + {res.forging} Forging Tides. "
        self.advice.setText(budget + res.advice())


# ====================================================================== Income
class IncomePage(QWidget):
    changed = Signal()

    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 12, 0, 0); lay.setSpacing(16)
        left = QVBoxLayout()
        c, l = card(tr("Log income"))
        f = QFormLayout(); f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.day = QDateEdit(); self.day.setCalendarPopup(True); self.day.setDate(qdate(date.today()))
        self.a = spin(step=10); self.t = spin(1000); self.fo = spin(1000)
        self.src = QComboBox(); self.src.addItems(SOURCES); self.src.setEditable(True)
        self.note = QLineEdit()
        f.addRow(tr("Date"), self.day); f.addRow("Astrite", self.a); f.addRow("Radiant Tides", self.t)
        f.addRow("Forging Tides", self.fo); f.addRow(tr("Source"), self.src); f.addRow(tr("Note"), self.note)
        l.addLayout(f)
        b = QPushButton(tr("Add")); b.setObjectName("primary"); b.clicked.connect(self.add)
        l.addWidget(b)
        quick = QHBoxLayout()
        for label, amount, src in (("+60 daily", 60, "Daily activity"), ("+90 Lunite", 90, "Lunite"),
                                   ("+300 codes", 300, "Codes")):
            qb = QPushButton(label); qb.clicked.connect(lambda _=False, a=amount, s=src: self.quick_add(a, s))
            quick.addWidget(qb)
        l.addLayout(quick)
        left.addWidget(c)
        c2, l2 = card("Estimate (used until you have logged 7+ days)")
        self.src_table = QTableWidget(0, 3)
        self.src_table.setHorizontalHeaderLabels(["On", "Source", "Astrite / day"])
        self.src_table.verticalHeader().setVisible(False)
        self.src_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        l2.addWidget(self.src_table)
        row = QHBoxLayout()
        b_add = QPushButton(tr("Add")); b_add.clicked.connect(self.add_source)
        b_save = QPushButton(tr("Save")); b_save.clicked.connect(self.save_sources)
        row.addWidget(b_add); row.addStretch(); row.addWidget(b_save)
        l2.addLayout(row)
        n = QLabel("These are rough guesses; change them to match your account (e.g. turn on Lunite if you have it).")
        n.setWordWrap(True); n.setObjectName("muted")
        l2.addWidget(n)
        left.addWidget(c2, 1)
        lw = QWidget(); lw.setLayout(left); lw.setMaximumWidth(440)
        lay.addWidget(lw)

        right = QVBoxLayout()
        c3, l3 = card()
        self.rate_label = QLabel(); self.rate_label.setObjectName("h2"); self.rate_label.setWordWrap(True)
        l3.addWidget(self.rate_label)
        self.chart = Chart(2.4)
        l3.addWidget(self.chart)
        right.addWidget(c3)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([tr("Date"), "Astrite", "Radiant", "Forging", tr("Source"), tr("Note")])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        right.addWidget(self.table, 1)
        rm = QPushButton(tr("Delete")); rm.clicked.connect(self.delete)
        rr = QHBoxLayout(); rr.addStretch(); rr.addWidget(rm)
        right.addLayout(rr)
        lay.addLayout(right, 1)
        state.changed.connect(self.refresh)
        self.fill_sources()
        self.refresh()

    def quick_add(self, amount, src):
        self.state.storage.add_income(date.today().isoformat(), amount, source=src, player_id=self.state.player)
        self.refresh(); self.changed.emit()

    def add(self):
        if not (self.a.value() or self.t.value() or self.fo.value()):
            return
        self.state.storage.add_income(pydate(self.day.date()).isoformat(), self.a.value(), self.t.value(),
                                      self.fo.value(), self.src.currentText(), self.note.text(), self.state.player)
        self.a.setValue(0); self.t.setValue(0); self.fo.setValue(0); self.note.clear()
        self.refresh(); self.changed.emit()

    def delete(self):
        r = self.table.currentRow()
        if r >= 0:
            self.state.storage.delete_income(int(self.table.item(r, 0).data(Qt.UserRole)))
            self.refresh(); self.changed.emit()

    def fill_sources(self):
        srcs = self.state.get("income_sources") or planner.DEFAULT_SOURCES
        self.src_table.setRowCount(0)
        for s in srcs:
            self._source_row(s)

    def _source_row(self, s):
        r = self.src_table.rowCount(); self.src_table.insertRow(r)
        on = QTableWidgetItem(); on.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        on.setCheckState(Qt.Checked if s.get("on") else Qt.Unchecked)
        self.src_table.setItem(r, 0, on)
        self.src_table.setItem(r, 1, QTableWidgetItem(s["name"]))
        self.src_table.setItem(r, 2, QTableWidgetItem(str(s["astrite_per_day"])))

    def add_source(self):
        self._source_row({"name": "New source", "astrite_per_day": 0, "on": True})

    def save_sources(self):
        out = []
        for r in range(self.src_table.rowCount()):
            try:
                val = float(self.src_table.item(r, 2).text().replace(",", "."))
            except (ValueError, AttributeError):
                val = 0
            name = self.src_table.item(r, 1).text().strip() if self.src_table.item(r, 1) else ""
            if name:
                out.append({"name": name, "astrite_per_day": val, "on": self.src_table.item(r, 0).checkState() == Qt.Checked})
        self.state.set("income_sources", out)
        self.refresh(); self.changed.emit()

    def refresh(self):
        entries = self.state.income_entries()
        r = self.state.income_rate()
        if r["source"] == "logged":
            self.rate_label.setText(f"You earn about {r['astrite_per_day']:.0f} Astrite/day "
                                    f"(≈ {r['astrite_per_day'] * 30 / ASTRITE_PER_PULL:.0f} pulls/month), "
                                    f"from {r['days']} logged days.")
        else:
            self.rate_label.setText(f"Estimate: {r['astrite_per_day']:.0f} Astrite/day "
                                    f"(≈ {r['astrite_per_day'] * 30 / ASTRITE_PER_PULL:.0f} pulls/month). "
                                    "Log your income for at least 7 days to use your real numbers.")
        self.table.setRowCount(len(entries))
        for i, e in enumerate(reversed(entries)):
            vals = [e["day"], f"{e['astrite']:,}", str(e["tides"]), str(e["forging"]), e["source"], e["note"]]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(Qt.UserRole, e["id"])
                self.table.setItem(i, j, it)
        months = planner.income_by_month(entries)
        ax = self.chart.reset()
        if months:
            ks = list(months)[-12:]
            ax.bar(ks, [months[k]["astrite"] for k in ks], color=T.GOLD, width=0.5)
            ax.set_xlim(-0.75, max(len(ks), 6) - 0.25)
            ax.set_ylabel("Astrite / month")
        else:
            ax.text(0.5, 0.5, "No income logged yet", ha="center", va="center", color=T.MUTED, transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
        self.chart.draw_idle()


# ====================================================================== What if
class WhatIfPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 12, 0, 0); lay.setSpacing(16)
        c, l = card("Your 50/50s, replayed")
        info = QLabel("Change the outcome of any 50/50 on the Featured Resonator banner and see how many featured "
                      "copies you would have had. Changing one result changes the guarantee after it, so later 5★s "
                      "become fair coin flips (counted as ½).")
        info.setWordWrap(True); info.setObjectName("muted")
        l.addWidget(info)
        presets = QHBoxLayout()
        for label, mode in (("Real", "real"), ("Win every 50/50", "won"), ("Lose every 50/50", "lost"),
                            ("Average luck (coin flips)", "coin")):
            b = QPushButton(label); b.clicked.connect(lambda _=False, m=mode: self.preset(m))
            presets.addWidget(b)
        presets.addStretch()
        l.addLayout(presets)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "5★", "Pity", "Real result", "What if"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        l.addWidget(self.table, 1)
        lay.addWidget(c, 3)
        r, rl = card("Result")
        self.res = QLabel(); self.res.setWordWrap(True); self.res.setObjectName("h2")
        rl.addWidget(self.res)
        self.rows = {k: StatRow(tr(k)) for k in ("Real featured copies", "What-if featured copies", "Difference")}
        for w in self.rows.values():
            rl.addWidget(w)
        rl.addSpacing(10)
        t2 = QLabel("If your pity had been average"); t2.setObjectName("h2")
        rl.addWidget(t2)
        self.avg_rows = {k: StatRow(tr(k)) for k in ("Your pulls on this banner", "Average player for the same copies",
                                                 "You saved (−) / spent extra (+)")}
        for w in self.avg_rows.values():
            rl.addWidget(w)
        rl.addStretch()
        lay.addWidget(r, 2)
        self.combos = []
        state.changed.connect(self.fill)
        self.fill()

    def events(self):
        s = self.state.stats.get(1)
        return list(s.five_stars) if s else []

    def fill(self):
        ev = self.events()
        self.table.setRowCount(len(ev))
        self.combos = []
        for i, e in enumerate(ev):
            for j, v in enumerate((str(i + 1), e.name, str(e.pity), e.result)):
                it = QTableWidgetItem(v); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, it)
            cb = QComboBox()
            cb.addItem("as it happened", None)
            if e.result in ("won", "lost"):
                cb.addItem("won instead" if e.result == "lost" else "lost instead", "won" if e.result == "lost" else "lost")
                cb.addItem("coin flip", "coin")
            cb.currentIndexChanged.connect(self.recompute)
            cb.setMinimumWidth(150)
            self.table.setCellWidget(i, 4, cb)
            self.combos.append(cb)
        self.table.setColumnWidth(4, 160)
        self.recompute()

    def preset(self, mode):
        for cb, e in zip(self.combos, self.events()):
            cb.blockSignals(True)
            if mode == "real" or e.result not in ("won", "lost"):
                cb.setCurrentIndex(0)
            else:
                i = cb.findData(mode)
                cb.setCurrentIndex(i if i >= 0 else 0)
            cb.blockSignals(False)
        self.recompute()

    def recompute(self):
        ev = self.events()
        if not ev:
            self.res.setText("No 5★ on the Featured Resonator banner yet.")
            return
        results = [e.result for e in ev]
        ov = {i: cb.currentData() for i, cb in enumerate(self.combos) if cb.currentData()}
        r = planner.what_if_5050(results, ov)
        self.rows["Real featured copies"].set(str(r["real_featured"]))
        self.rows["What-if featured copies"].set(f"{r['whatif_featured']:.1f}")
        self.rows["Difference"].set(f"{r['difference']:+.1f}")
        self.res.setText("Same as reality." if abs(r["difference"]) < 1e-9 else
                         f"You would have {abs(r['difference']):.1f} {'more' if r['difference'] > 0 else 'fewer'} "
                         "featured copies.")
        s = self.state.stats.get(1)
        a = planner.what_if_average_luck(self.state.hazard(), r["real_featured"], s.total_pulls - s.pity5)
        self.avg_rows["Your pulls on this banner"].set(f"{a['your_pulls']:,}")
        self.avg_rows["Average player for the same copies"].set(f"{a['expected_pulls']:.0f}")
        self.avg_rows["You saved (−) / spent extra (+)"].set(
            f"{-a['saved_pulls']:+.0f} pulls ({-a['saved_astrite']:+,} Astrite)")


# ====================================================================== Luck test
class _LuckWorker(QThread):
    done = Signal(object, object)

    def __init__(self, pities, censored, h, prior):
        super().__init__()
        self.args = (pities, censored, h, prior)

    def run(self):
        pities, censored, h, prior = self.args
        t = stats_tests.luck_test(pities, h)
        b = stats_tests.bayes_bands(pities, censored, prior) if pities else None
        self.done.emit(t, b)


class LuckPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 12, 0, 0); lay.setSpacing(16)
        c, l = card("Is my luck unusual?")
        self.verdict = QLabel("…"); self.verdict.setWordWrap(True); self.verdict.setObjectName("h2")
        l.addWidget(self.verdict)
        self.rows = {k: StatRow(tr(k)) for k in ("5★s tested", "Your average pity", "Expected average pity",
                                             "KS test p-value", "Chi-square p-value")}
        for w in self.rows.values():
            l.addWidget(w)
        self.bins = QTableWidget(0, 3)
        self.bins.setHorizontalHeaderLabels(["Pity", "You", "Expected"])
        self.bins.verticalHeader().setVisible(False)
        self.bins.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l.addWidget(self.bins)
        expl = QLabel("Both tests compare your 5★ pities (all banners with the normal rates) with the selected pity "
                      "model. A p-value is the chance of a pattern at least this extreme for an average player; "
                      "below 0.05 is unusual. P-values are simulated (4,000 runs), so they also work for few 5★s.")
        expl.setWordWrap(True); expl.setObjectName("muted")
        l.addWidget(expl)
        l.addStretch()
        lay.addWidget(c, 2)
        r, rl = card("Bayesian fit of the soft-pity curve (90 % credible band)")
        self.chart = Chart(3.2)
        rl.addWidget(self.chart)
        self.brows = {k: StatRow(tr(k)) for k in ("Consolidated 5★ rate", "P(featured within 80 pulls) from pity 0")}
        for w in self.brows.values():
            rl.addWidget(w)
        e2 = QLabel("Each pity's 5★ chance gets a Beta posterior, with the community curve as the prior "
                    "(8 pseudo-observations) and your pulls as data. The band shows what your data allows; it is wide "
                    "where you have few pulls (deep soft pity).")
        e2.setWordWrap(True); e2.setObjectName("muted")
        rl.addWidget(e2)
        lay.addWidget(r, 3)
        state.changed.connect(self.run)
        self.run()

    def run(self):
        from .state import FIT_KINDS
        pities, cens = [], []
        for s in self.state.stats.values():
            if s.kind in FIT_KINDS:
                pities += [f.pity for f in s.five_stars]
                cens.append(s.pity5)
        h = self.state.hazard()
        from ..core.probability import hazard_community
        self.w = _LuckWorker(pities, cens, h, hazard_community(self.state.gd.rates))
        self.w.done.connect(self.show_result)
        self.verdict.setText("Testing…")
        self.w.start()

    def show_result(self, t, b):
        if t is None:
            self.verdict.setText("No 5★ pulls yet.")
            return
        self.verdict.setText(t.verdict)
        self.rows["5★s tested"].set(str(t.n))
        self.rows["Your average pity"].set(f"{t.mean_pity:.1f}")
        self.rows["Expected average pity"].set(f"{t.model_mean:.1f}")
        self.rows["KS test p-value"].set(f"{t.ks_p:.3f}  (D = {t.ks_d:.3f})")
        self.rows["Chi-square p-value"].set(f"{t.chi2_p:.3f}  (χ² = {t.chi2:.1f})")
        labels = [f"{a}–{b_}" for a, b_ in stats_tests.BINS]
        self.bins.setRowCount(len(labels))
        for i, (lab, o, e) in enumerate(zip(labels, t.observed, t.expected)):
            for j, v in enumerate((lab, str(o), f"{e:.1f}")):
                self.bins.setItem(i, j, QTableWidgetItem(v))
        if b is None:
            return
        ax = self.chart.reset()
        n = b.pity[55:80]
        ax.fill_between(n, b.low[55:80] * 100, b.high[55:80] * 100, color=T.GOLD, alpha=0.25, label="90 % band (your data)")
        ax.plot(n, b.mid[55:80] * 100, color=T.GOLD, lw=2, label="posterior median")
        from ..core.probability import hazard_community
        hc = hazard_community(self.state.gd.rates)
        ax.plot(n, hc[55:80] * 100, color=T.PURPLE, lw=1.5, ls="--", label="community model")
        ax.set_xlabel("pity"); ax.set_ylabel("5★ chance on that pull (%)")
        self.chart.legend()
        self.chart.draw_idle()
        self.brows["Consolidated 5★ rate"].set(f"{b.rate_mid * 100:.2f} %  ({b.rate_low * 100:.2f} – {b.rate_high * 100:.2f})")
        lo, mid, hi = stats_tests.probability_interval(b, 80, 1, 0, False, 0.5, max_draws=80)
        self.brows["P(featured within 80 pulls) from pity 0"].set(f"{mid * 100:.1f} %  ({lo * 100:.1f} – {hi * 100:.1f})")
