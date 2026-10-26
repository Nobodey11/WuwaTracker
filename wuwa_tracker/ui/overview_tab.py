from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget)

from ..core import probability as pr
from . import theme as T
from .widgets import Chart, FlowLayout, StatRow, card, clear_layout

RESULT_BADGE = {"won": ("WON 50/50", T.GREEN), "lost": ("LOST 50/50", T.RED), "guaranteed": ("GUARANTEED", T.BLUE)}


class BannerCard(QFrame):
    clicked = Signal(int)

    def __init__(self, pool_type: int):
        super().__init__()
        self.pool_type = pool_type
        self.setObjectName("bannerCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(128)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(0)
        self.p5 = QLabel()
        self.p5.setStyleSheet(f"color:{T.GOLD}; font-size:17pt; font-weight:800;")
        self.p4 = QLabel()
        self.p4.setStyleSheet(f"color:{T.PURPLE}; font-size:14pt; font-weight:800;")
        self.name = QLabel()
        self.name.setStyleSheet("font-weight:700;")
        self.extra = QLabel()
        self.extra.setObjectName("muted")
        l5 = QLabel("5✦ Pity"); l5.setStyleSheet(f"color:{T.GOLD}; font-size:8pt;")
        l4 = QLabel("4✦ Pity"); l4.setStyleSheet(f"color:{T.PURPLE}; font-size:8pt;")
        top = QHBoxLayout()
        c1, c2 = QVBoxLayout(), QVBoxLayout()
        c1.addWidget(self.p5); c1.addWidget(l5)
        c2.addWidget(self.p4); c2.addWidget(l4)
        top.addLayout(c1); top.addSpacing(18); top.addLayout(c2); top.addStretch()
        lay.addLayout(top)
        lay.addStretch()
        lay.addWidget(self.name)
        lay.addWidget(self.extra)

    def update_stats(self, s, rates):
        self.p5.setText(f"{s.pity5}/{rates['hard_pity5']}")
        self.p4.setText(f"{s.pity4}/{rates['hard_pity4']}")
        self.name.setText(s.name)
        g = ""
        if s.has_5050:
            g = " · next 5✦ GUARANTEED" if s.guaranteed else " · next 5✦ is 50/50"
        self.extra.setText(f"{s.total_pulls:,} pulls{g}")

    def set_selected(self, on: bool):
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self); self.style().polish(self)

    def mousePressEvent(self, e):
        self.clicked.emit(self.pool_type)


def five_star_chip(f, patch: str | None = None) -> QFrame:
    w = QFrame()
    w.setStyleSheet(f"QFrame {{ background:{T.CARD2}; border:1px solid {T.BORDER}; border-radius:8px; }}")
    w.setToolTip(f"{f.name}\nPity {f.pity}\n{f.time.astimezone().strftime('%Y-%m-%d %H:%M')}"
                 + (f"\n{f.result}" if f.result else "") + (f"\nPatch {patch}" if patch else ""))
    h = QHBoxLayout(w)
    h.setContentsMargins(10, 6, 6, 6)
    h.setSpacing(8)
    star = "★ " if f.result in ("won", "guaranteed", "") else ""
    n = QLabel(star + f.name)
    n.setStyleSheet(f"border:none; font-weight:600; color:{T.GOLD if star else T.MUTED};")
    p = QLabel(str(f.pity))
    p.setAlignment(Qt.AlignCenter)
    p.setFixedSize(30, 22)
    p.setStyleSheet(f"border:none; background:{T.pity_color(f.pity)}; color:white; border-radius:11px; font-weight:700;")
    h.addWidget(n); h.addWidget(p)
    return w


class OverviewTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.selected = 1
        self.cards: dict[int, BannerCard] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(18)

        # left: banner cards
        left_w = QWidget()
        self.left = QVBoxLayout(left_w)
        self.left.setContentsMargins(0, 0, 6, 0)
        self.left.setSpacing(12)
        sc = QScrollArea(); sc.setWidget(left_w); sc.setWidgetResizable(True); sc.setFixedWidth(300)
        root.addWidget(sc)

        # right
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setContentsMargins(0, 0, 6, 0)
        right.setSpacing(16)
        rs = QScrollArea(); rs.setWidget(right_w); rs.setWidgetResizable(True)
        root.addWidget(rs, 1)

        top = QHBoxLayout(); top.setSpacing(16)
        c1, l1 = card()
        self.title = QLabel(); self.title.setObjectName("h1"); l1.addWidget(self.title)
        self.r_total = StatRow("Total Pulls"); self.r_astrite = StatRow("Total Astrites")
        self.r_5 = StatRow("5✦ Pulls", T.GOLD); self.r_4 = StatRow("4✦ Pulls", T.PURPLE)
        for r in (self.r_total, self.r_astrite, self.r_5, self.r_4):
            l1.addWidget(r)
        l1.addStretch()
        c2, l2 = card("5✦ Luck Rating")
        self.r_avgf = StatRow("Average Featured Pity"); self.r_avg5 = StatRow("Average 5✦ Pity")
        self.r_ratio = StatRow("Pull Ratio"); self.r_5050 = StatRow("50/50 Wins")
        self.r_luck = StatRow("Luck vs. model")
        for r in (self.r_avgf, self.r_avg5, self.r_ratio, self.r_5050, self.r_luck):
            l2.addWidget(r)
        self.luck_note = QLabel(); self.luck_note.setObjectName("muted"); self.luck_note.setWordWrap(True)
        l2.addWidget(self.luck_note)
        l2.addStretch()
        top.addWidget(c1, 1); top.addWidget(c2, 1)
        right.addLayout(top)

        cb, lb = card()
        self.now_title = QLabel(); self.now_title.setObjectName("h2")
        self.now_body = QLabel(); self.now_body.setWordWrap(True); self.now_body.setTextFormat(Qt.RichText)
        lb.addWidget(self.now_title); lb.addWidget(self.now_body)
        right.addWidget(cb)

        c3, l3 = card("Recent Convenes — 5✦ (newest first)")
        self.chips_w = QWidget(); self.chips = FlowLayout(self.chips_w)
        l3.addWidget(self.chips_w)
        right.addWidget(c3)

        c4, l4 = card("5✦ pity per drop")
        self.chart = Chart(2.6)
        self.chart.setMinimumHeight(220)
        l4.addWidget(self.chart)
        right.addWidget(c4)
        right.addStretch()

        state.changed.connect(self.refresh)
        self.refresh()

    def select(self, pt: int):
        self.selected = pt
        for k, c in self.cards.items():
            c.set_selected(k == pt)
        self.show_banner()

    def show_schedule(self):
        gd = self.state.gd
        cur, nxt = gd.current_banners(), gd.upcoming_banners()
        self.now_title.setText(f"Banners · game data v{gd.version} (patch {gd.patch}, {gd.source})")
        def fmt(b):
            return (f"<b style='color:{T.GOLD}'>{b['patch']} Phase {b.get('phase', '?')}</b> "
                    f"({b['start']} → {b['end']}): " + ", ".join(b.get("featured_5star_resonators", []))
                    + (f" <span style='color:{T.PURPLE}'>· 4✦ " + ", ".join(b.get("featured_4star_resonators", []))
                       + "</span>" if b.get("featured_4star_resonators") else ""))
        lines = [("Now: " + fmt(b)) for b in cur] + [("Next: " + fmt(b)) for b in nxt[:2]]
        if not lines:
            lines = [f"<span style='color:{T.ORANGE}'>No banner info for today — the game data is out of date. "
                     "Use Help → Check for game data updates, or add the new patch to game_data.json "
                     "(see docs/PATCH_UPDATE.md).</span>"]
        self.now_body.setText("<br>".join(lines))

    def refresh(self):
        self.show_schedule()
        clear_layout(self.left)
        self.cards.clear()
        for pt, s in self.state.stats.items():
            c = BannerCard(pt)
            c.update_stats(s, self.state.gd.rates)
            c.clicked.connect(self.select)
            self.left.addWidget(c)
            self.cards[pt] = c
        self.left.addStretch()
        if self.state.stats and self.selected not in self.state.stats:
            self.selected = next(iter(self.state.stats))
        if self.cards:
            self.select(self.selected)
        else:
            self.title.setText("No pulls yet — use File → Import")

    def show_banner(self):
        s = self.state.stats.get(self.selected)
        if not s:
            return
        self.title.setText(s.name)
        self.r_total.set(f"{s.total_pulls:,}")
        self.r_astrite.set(f"{s.astrite:,}")
        self.r_5.set(str(s.count5)); self.r_4.set(str(s.count4))
        is_char = s.has_5050
        self.r_avgf.set(f"{s.avg_featured_pity:.2f}" if s.avg_featured_pity and is_char else "–")
        self.r_avg5.set(f"{s.avg_pity5:.2f}" if s.avg_pity5 else "–")
        self.r_ratio.set(f"{s.rate5 * 100:.2f}%")
        self.r_5050.set(f"{s.win_rate * 100:.2f}%  ({s.wins}W / {s.losses}L)" if s.win_rate is not None else "–")
        pct = pr.luck_percentile(self.state.hazard(), [f.pity for f in s.five_stars])
        if pct is None:
            self.r_luck.set("–"); self.luck_note.setText("")
        else:
            luckier = 1 - pct
            self.r_luck.set(f"luckier than {luckier * 100:.0f}%")
            self.luck_note.setText("Share of simulated players (same number of 5✦) who needed MORE pulls than you. "
                                   "Uses the selected pity model in Settings.")

        clear_layout(self.chips)
        for f in reversed(s.five_stars):
            self.chips.addWidget(five_star_chip(f, self.state.gd.patch_of(f.time)))
        if not s.five_stars:
            self.chips.addWidget(QLabel("No 5✦ yet on this banner."))

        ax = self.chart.reset()
        if s.five_stars:
            xs = list(range(1, len(s.five_stars) + 1))
            cols = ["#5d606c" if f.result == "lost" else T.pity_color(f.pity) for f in s.five_stars]
            ax.bar(xs, [f.pity for f in s.five_stars], color=cols, width=0.7)
            ax.axhline(65.5, color=T.GOLD, lw=0.8, ls="--")
            ax.text(0.5, 67, "soft pity", color=T.GOLD, fontsize=7)
            ax.set_ylim(0, 82)
            ax.set_xticks(xs)
            ax.set_xticklabels([f.name.split(":")[0][:9] for f in s.five_stars], rotation=60, ha="right", fontsize=7)
            ax.set_ylabel("pity")
        self.chart.draw_idle()
