"""Top navigation bar (logo · tabs · account · menu) and the thin status strip (data version · chips · resets)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTabBar, QToolButton, QWidget

from . import theme as T
from .i18n import tr


def app_icon() -> QIcon:
    base = Path(__file__).resolve().parent.parent / "assets"
    icon = QIcon()
    for f in ("icon.ico", "icon.png"):
        if (base / f).exists():
            icon.addFile(str(base / f))
    return icon


def next_resets(utc_offset_h: float):
    tz = timezone(timedelta(hours=utc_offset_h))
    now = datetime.now(tz)
    daily = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if daily <= now:
        daily += timedelta(days=1)
    weekly = daily + timedelta(days=(0 - daily.weekday()) % 7)  # Monday 04:00 server time
    return daily - now, weekly - now


def fmt_td(td: timedelta) -> str:
    s = max(0, int(td.total_seconds()))
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, s = divmod(s, 60)
    return (f"{d:02d}d " if d else "") + f"{h:02d}h {m:02d}m" + ("" if d else f" {s:02d}s")


class TopBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("topbar")
        tl = QHBoxLayout(self); tl.setContentsMargins(18, 0, 12, 0); tl.setSpacing(10)
        icon = QLabel(); icon.setPixmap(app_icon().pixmap(28, 28)); icon.setObjectName("plain")
        word = QLabel(f"<span style='color:{T.GOLD}'>WuWa</span> Pull Tracker"); word.setObjectName("wordmark")
        tl.addWidget(icon); tl.addWidget(word); tl.addSpacing(16)
        self.nav = QTabBar(); self.nav.setObjectName("nav"); self.nav.setDrawBase(False); self.nav.setExpanding(False)
        self.nav.setUsesScrollButtons(True)
        tl.addWidget(self.nav, 1, Qt.AlignBottom)
        self.player = QComboBox(); self.player.setObjectName("pill"); self.player.setMinimumWidth(130)
        self.player.setToolTip("Account (player id). ☰ → My account → Rename this account to give it a name.")
        tl.addWidget(self.player)
        self.menu_btn = QToolButton(); self.menu_btn.setObjectName("menuBtn"); self.menu_btn.setText("☰")
        self.menu_btn.setToolTip("Menu: import, export, backups, updates, about")
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        tl.addWidget(self.menu_btn)

    def set_accounts(self, players: list[str], nicknames: dict[str, str], current: str):
        self.player.blockSignals(True)
        self.player.clear()
        for p in players:
            nick = nicknames.get(p)
            self.player.addItem(f"{nick} · {p}" if nick else p, p)
        i = self.player.findData(current)
        self.player.setCurrentIndex(max(0, i))
        self.player.blockSignals(False)


class StatusStrip(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("strip")
        sl = QHBoxLayout(self); sl.setContentsMargins(20, 0, 20, 0); sl.setSpacing(12)
        self.gd_chip = self._chip()
        self.update_chip = self._chip(); self.update_chip.hide()
        self.watch_chip = self._chip(); self.watch_chip.hide()
        self.ending_chip = self._chip(); self.ending_chip.hide()
        for c in (self.gd_chip, self.update_chip, self.watch_chip, self.ending_chip):
            sl.addWidget(c)
        sl.addStretch()
        self.daily = QLabel(); self.daily.setObjectName("stripText")
        self.weekly = QLabel(); self.weekly.setObjectName("stripText")
        sl.addWidget(self.daily); sl.addWidget(self.weekly)

    @staticmethod
    def _chip() -> QPushButton:
        b = QPushButton(); b.setObjectName("chip"); b.setCursor(Qt.PointingHandCursor)
        return b

    def set_resets(self, offset_h: float):
        d, w = next_resets(offset_h)
        self.daily.setText(f"{tr('Daily reset')}  <b>{fmt_td(d)}</b>")
        self.weekly.setText(f"{tr('Weekly reset')}  <b>{fmt_td(w)}</b>")
