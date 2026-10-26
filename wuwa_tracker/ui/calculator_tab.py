from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

from ..core import probability as pr
from . import theme as T
from .widgets import Chart, StatRow, card

MODEL_CHOICES = [("community", "Community estimate (soft pity 66+)"),
                 ("fitted", "Fitted on MY pulls (Bayesian-smoothed)"),
                 ("flat", "Flat 0.8 % + hard pity (worst case)")]
COPY_COLORS = [T.GOLD, T.PURPLE, T.BLUE, T.GREEN, T.ORANGE, T.RED, "#ff7ad9"]


class CalculatorTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(18)

        # ---------- inputs ----------
        ci, li = card("Your situation")
        form = QFormLayout(); form.setSpacing(10)
        self.banner = QComboBox()
        self.banner.setMinimumWidth(240)
        self.use_current = QCheckBox("Use my current state")
        self.use_current.setToolTip("Fill in pity and guarantee from your imported pulls")
        self.use_current.setChecked(True)
        self.pity = QSpinBox()
        self.guar = QCheckBox("Guaranteed (lost last 50/50)")
        self.astrite = QSpinBox(); self.astrite.setRange(0, 10_000_000); self.astrite.setSingleStep(160)
        self.astrite.setGroupSeparatorShown(True)
        self.tides = QSpinBox(); self.tides.setRange(0, 5000)
        self.pulls = QSpinBox(); self.pulls.setRange(1, 2000); self.pulls.setValue(80)
        self.copies = QSpinBox(); self.copies.setRange(1, 7); self.copies.setValue(1)
        self.copies.setToolTip("1 = get the character/weapon, 2 = S1/R2, … 7 = S6")
        self.model = QComboBox()
        for k, v in MODEL_CHOICES:
            self.model.addItem(v, k)
        form.addRow("Banner", self.banner)
        form.addRow("", self.use_current)
        form.addRow("Current 5✦ pity", self.pity)
        form.addRow("", self.guar)
        form.addRow("Astrite", self.astrite)
        form.addRow("Radiant/Forging Tides", self.tides)
        form.addRow("→ Pulls available", self.pulls)
        form.addRow("Copies wanted", self.copies)
        form.addRow("Pity model", self.model)
        li.addLayout(form)
        hint = QLabel("Astrite + Tides fill in the pulls automatically; you can also type pulls directly.\n"
                      "The soft-pity curve isn't published by Kuro, so compare the models.")
        hint.setObjectName("muted"); hint.setWordWrap(True)
        li.addWidget(hint)
        li.addStretch()
        ci.setFixedWidth(440)
        outer.addWidget(ci)

        # ---------- results ----------
        rw = QWidget(); right = QVBoxLayout(rw); right.setContentsMargins(0, 0, 6, 0); right.setSpacing(16)
        sc = QScrollArea(); sc.setWidget(rw); sc.setWidgetResizable(True)
        outer.addWidget(sc, 1)

        cr, lr = card("Result")
        self.big = QLabel("–"); self.big.setObjectName("big")
        self.big_sub = QLabel(); self.big_sub.setObjectName("muted"); self.big_sub.setWordWrap(True)
        lr.addWidget(self.big); lr.addWidget(self.big_sub)
        self.r_exp = StatRow("Expected pulls for that many copies")
        self.r_50 = StatRow("Pulls for a 50 % chance")
        self.r_90 = StatRow("Pulls for a 90 % chance")
        self.r_99 = StatRow("Pulls for a 99.99 % chance (practical worst case)")
        self.r_expc = StatRow("Expected featured copies with these pulls")
        self.r_dist = StatRow("Chance of exactly 0 / 1 / 2 / … copies")
        for r in (self.r_exp, self.r_50, self.r_90, self.r_99, self.r_expc, self.r_dist):
            lr.addWidget(r)
        right.addWidget(cr)

        cc, lc = card("Chance of reaching N copies vs. pulls spent")
        self.curve = Chart(3.0); self.curve.setMinimumHeight(260)
        lc.addWidget(self.curve)
        right.addWidget(cc)

        ch, lh = card("Pity model: 5✦ chance per pull")
        self.hz = Chart(2.4); self.hz.setMinimumHeight(220)
        lh.addWidget(self.hz)
        right.addWidget(ch)
        right.addStretch()

        for w in (self.banner, self.model):
            w.currentIndexChanged.connect(self.recalc)
        for w in (self.pity, self.pulls, self.copies):
            w.valueChanged.connect(self.recalc)
        self.astrite.valueChanged.connect(self.from_astrite)
        self.tides.valueChanged.connect(self.from_astrite)
        self.guar.toggled.connect(self.recalc)
        self.use_current.toggled.connect(self.load_current)
        self.banner.currentIndexChanged.connect(self.load_current)
        state.changed.connect(self.fill_banners)
        i = self.model.findData(state.get("pity_model"))
        self.model.setCurrentIndex(max(i, 0))
        self.fill_banners()

    def fill_banners(self):
        """Banner list + limits come from game data, so new banner types/rates appear automatically."""
        gd = self.state.gd
        cur = self.banner.currentData()
        self.banner.blockSignals(True)
        self.banner.clear()
        for pt in gd.featured_pools():
            fc = gd.featured_chance(pt)
            label = "50/50" if fc < 1 else "100 % featured"
            self.banner.addItem(f"{gd.name(pt)} ({label})", pt)
        i = self.banner.findData(cur)
        self.banner.setCurrentIndex(max(i, 0))
        self.banner.blockSignals(False)
        self.pity.setRange(0, int(gd.rates["hard_pity5"]) - 1)
        self.load_current()

    @property
    def per_pull(self) -> int:
        return int(self.state.gd.rates.get("astrite_per_pull", 160))

    def from_astrite(self):
        self.pulls.setValue(max(1, self.astrite.value() // self.per_pull + self.tides.value()))

    def load_current(self):
        on = self.use_current.isChecked()
        self.pity.setEnabled(not on)
        is_char = (self.state.gd.featured_chance(self.banner.currentData() or 1) or 1) < 1
        self.guar.setEnabled(not on and is_char)
        if on:
            s = self.state.stats.get(self.banner.currentData())
            self.pity.blockSignals(True); self.guar.blockSignals(True)
            self.pity.setValue(s.pity5 if s else 0)
            self.guar.setChecked(bool(s and s.guaranteed and is_char))
            self.pity.blockSignals(False); self.guar.blockSignals(False)
        self.recalc()

    def recalc(self):
        h = self.state.hazard(self.model.currentData())
        fc = self.state.gd.featured_chance(self.banner.currentData() or 1) or 1.0
        is_char = fc < 1
        pity, g = self.pity.value(), self.guar.isChecked() and is_char
        n, k = self.pulls.value(), self.copies.value()

        res = pr.featured_distribution(h, n, k, pity, g, fc)
        self.big.setText(f"{res.probability * 100:.1f}%")
        what = ("featured Resonator" if is_char else "featured Weapon") + (f" ×{k}" if k > 1 else "")
        self.big_sub.setText(f"Chance to get the {what} within {n} pulls ({n * self.per_pull:,} Astrite), "
                             f"starting at pity {pity}" + (", guaranteed" if g else (", 50/50" if is_char else "")) + ".")
        exp = pr.expected_pulls_featured(h, k, pity, g, fc)
        self.r_exp.set(f"{exp:.1f} pulls  ({exp * self.per_pull:,.0f} Astrite)")
        for row, c in ((self.r_50, 0.5), (self.r_90, 0.9), (self.r_99, 0.9999)):
            m = pr.pulls_needed(h, k, c, pity, g, fc)
            row.set(f"{m} pulls  ({m * self.per_pull:,} Astrite)")
        self.r_expc.set(f"{res.expected_featured:.2f}")
        self.r_dist.set(" / ".join(f"{p * 100:.0f}%" for p in res.copies_dist[:-1])
                        + f" / ≥{k}: {res.copies_dist[-1] * 100:.0f}%")

        # curve chart: P(>= c copies) for c = 1..k
        horizon = max(n, pr.pulls_needed(h, k, 0.999, pity, g, fc))
        ax = self.curve.reset()
        for c in range(1, k + 1):
            r = pr.featured_distribution(h, horizon, c, pity, g, fc)
            ax.plot(range(horizon + 1), r.curve * 100, color=COPY_COLORS[(c - 1) % 7], lw=1.8,
                    label=f"≥{c} cop{'y' if c == 1 else 'ies'}")
        ax.axvline(n, color=T.TEXT, lw=0.8, ls="--")
        ax.text(n + 1, 3, f"{n} pulls", color=T.TEXT, fontsize=8)
        ax.set_ylim(0, 102); ax.set_xlim(0, horizon)
        ax.set_xlabel("pulls from now"); ax.set_ylabel("% chance")
        self.curve.legend()
        self.curve.draw_idle()

        ax = self.hz.reset()
        xs = list(range(1, len(h)))
        ax.plot(xs, [h[x] * 100 for x in xs], color=T.GOLD, lw=1.8, label="5✦ chance on that pull")
        pmf = pr.pity_pmf(h, 0)
        ax2 = ax.twinx()
        self.hz.style_ax(ax2); ax2.grid(False)
        ax2.bar(xs, [pmf[x] * 100 for x in xs], color=T.PURPLE, alpha=0.55, label="P(5✦ lands exactly here) →")
        ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
        ax.axvline(pity, color=T.TEXT, lw=0.8, ls="--")
        ax.set_xlabel(f"pity    (consolidated rate {pr.consolidated_rate(h) * 100:.2f} %, "
                      f"avg {pr.expected_pulls_5star(h):.1f} pulls per 5✦)")
        ax.set_ylabel("chance on that pull %"); ax.set_ylim(0, 102)
        ax2.set_ylabel("distribution %")
        self.hz.legend(ax, ax2)
        self.hz.draw_idle()
