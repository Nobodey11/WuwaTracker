"""Redemption codes tab: active codes from Prydwen.gg with rewards, copy button and a 'redeemed' tick-off."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from ..core.prydwen import CODES_URL
from . import theme as T
from .widgets import FlowLayout, card, clear_layout


class _Fetch(QThread):
    done = Signal(object, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(), "")
        except Exception as e:
            self.done.emit(None, f"{type(e).__name__}: {e}")


class CodesTab(QWidget):
    new_codes = Signal(int)          # number of active codes not yet redeemed (for the tab badge)

    def __init__(self, state, status=None):
        super().__init__()
        self.state = state
        self.status = status or (lambda m: None)
        self.data = None
        self.worker = None
        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 16); root.setSpacing(12)

        top = QHBoxLayout()
        t = QLabel("Redemption codes"); t.setObjectName("h1")
        top.addWidget(t); top.addStretch()
        self.refresh_btn = QPushButton("↻ Refresh")
        page = QPushButton("Prydwen codes page ↗")
        page.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CODES_URL)))
        top.addWidget(self.refresh_btn); top.addWidget(page)
        root.addLayout(top)
        self.info = QLabel(); self.info.setObjectName("muted"); self.info.setWordWrap(True)
        root.addWidget(self.info)

        body_w = QWidget(); body_w.setObjectName("scrollInner")
        self.body = QVBoxLayout(body_w); self.body.setContentsMargins(0, 0, 6, 0); self.body.setSpacing(12)
        sc = QScrollArea(); sc.setWidget(body_w); sc.setWidgetResizable(True)
        root.addWidget(sc, 1)

        how = QLabel("<b>How to redeem:</b> reach Union Level 2 · Terminal (Esc) → Settings → Other Settings → "
                     "Redemption Code → Redeem · paste the code → Confirm · rewards arrive in your in-game Mail. "
                     "Codes are case-sensitive and can be used once per account.")
        how.setWordWrap(True); how.setObjectName("muted")
        root.addWidget(how)
        credit = QLabel("Code list © <a style='color:#f5c518' href='https://www.prydwen.gg/wuthering-waves/codes'>"
                        "Prydwen.gg</a> · not affiliated with Prydwen.gg or Kuro Games · personal use only.")
        credit.setObjectName("muted"); credit.setOpenExternalLinks(True)
        root.addWidget(credit)

        self.refresh_btn.clicked.connect(lambda: self.load(force=True))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1800, self.load)

    # ---------------- data
    def load(self, force=False):
        if not self.state.prydwen_on():
            self.info.setText("Prydwen is turned off in Settings, so codes can't be loaded.")
            return
        self.info.setText("Loading codes from prydwen.gg…")
        self.refresh_btn.setEnabled(False)
        self.worker = _Fetch(lambda: self.state.prydwen.codes(force=force))
        self.worker.done.connect(self.on_codes)
        self.worker.start()

    def on_codes(self, data, err):
        self.refresh_btn.setEnabled(True)
        if err:
            self.info.setText(f"⚠ Could not load codes ({err}). Check your internet connection or open the Prydwen page.")
            return
        self.data = data
        fetched = datetime.fromtimestamp(data.get("fetched", 0)).strftime("%Y-%m-%d %H:%M")
        self.info.setText(f"{len(data['active'])} active code(s) · Prydwen list updated {data.get('updated') or '?'}"
                          f" · fetched {fetched}. Tick a code once you've redeemed it.")
        # alert about codes that appeared since last time
        seen = set(self.state.get("seen_codes") or [])
        fresh = [c["code"] for c in data["active"] if c["code"] not in seen]
        if fresh:
            self.status(f"🎁 New redemption code(s): {', '.join(fresh)} (see the Codes tab)")
            self.state.set("seen_codes", sorted(seen | {c["code"] for c in data["active"]}))
        self.render()

    # ---------------- ui
    def render(self):
        clear_layout(self.body)
        if not self.data:
            return
        redeemed = set(self.state.get("redeemed_codes") or [])
        active = self.data["active"]
        todo = [c for c in active if c["code"] not in redeemed]
        self.new_codes.emit(len(todo))
        h = QLabel(f"Active ({len(todo)} to redeem)" if active else "Active"); h.setObjectName("h2")
        self.body.addWidget(h)
        if not active:
            n = QLabel("No active codes right now. New ones usually appear with livestreams and patches.")
            n.setObjectName("muted"); self.body.addWidget(n)
        for c in sorted(active, key=lambda c: c["code"] in redeemed):
            self.body.addWidget(self._code_card(c, c["code"] in redeemed))
        if self.data["expired"]:
            self.exp_toggle = QPushButton(f"Show expired codes ({len(self.data['expired'])})")
            self.exp_box = QWidget(); eb = QVBoxLayout(self.exp_box); eb.setContentsMargins(0, 0, 0, 0)
            for c in self.data["expired"]:
                rew = ", ".join(f"{r['name']} ×{r['amount']}" for r in c["rewards"]) or "–"
                l = QLabel(f"<span style='font-family:Consolas,monospace; color:{T.MUTED}'><s>{c['code']}</s></span>"
                           f"  <span style='color:{T.MUTED}'>{rew}</span>")
                l.setTextFormat(Qt.RichText); l.setWordWrap(True)
                eb.addWidget(l)
            self.exp_box.setVisible(False)
            self.exp_toggle.clicked.connect(lambda: (self.exp_box.setVisible(not self.exp_box.isVisible()),
                                                     self.exp_toggle.setText(("Hide" if self.exp_box.isVisible() else "Show")
                                                                             + f" expired codes ({len(self.data['expired'])})")))
            self.body.addSpacing(8)
            self.body.addWidget(self.exp_toggle, 0, Qt.AlignLeft)
            self.body.addWidget(self.exp_box)
        self.body.addStretch()

    def _code_card(self, c, done):
        f, lay = card()
        if done:
            f.setStyleSheet(f"QFrame#card {{ background:{T.CARD}; border:1px solid {T.BORDER}; border-radius:10px; }}")
        else:
            f.setStyleSheet(f"QFrame#card {{ background:{T.CARD}; border:1px solid {T.GOLD}; border-radius:10px; }}")
        row = QHBoxLayout()
        code = QLabel(c["code"])
        code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        code.setStyleSheet(f"font-family: Consolas, 'Cascadia Mono', monospace; font-size: 18pt; font-weight: 800;"
                           f"color: {T.MUTED if done else T.GOLD}; letter-spacing: 1px;"
                           + ("text-decoration: line-through;" if done else ""))
        row.addWidget(code); row.addStretch()
        copy = QPushButton("Copy"); copy.setObjectName("primary" if not done else "")
        def do_copy(_=False, text=c["code"]):
            QGuiApplication.clipboard().setText(text)
            copy.setText("Copied ✓")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: copy.setText("Copy"))
        copy.clicked.connect(do_copy)
        tick = QCheckBox("Redeemed"); tick.setChecked(done)
        tick.toggled.connect(lambda on, code_=c["code"]: self._mark(code_, on))
        row.addWidget(copy); row.addWidget(tick)
        lay.addLayout(row)
        rw = QWidget(); fl = FlowLayout(rw, spacing=10)
        for r in c["rewards"]:
            chip = QFrame(); chip.setStyleSheet(f"QFrame {{ background:{T.CARD2}; border-radius:8px; }}")
            h = QHBoxLayout(chip); h.setContentsMargins(6, 4, 10, 4); h.setSpacing(6)
            ic = QLabel(); ic.setFixedSize(28, 28); ic.setStyleSheet("background:transparent;")
            self.state.images.set_on(ic, r.get("icon"), 28)
            t = QLabel(f"{r['name']} <b>×{r['amount']}</b>"); t.setTextFormat(Qt.RichText)
            t.setStyleSheet("background:transparent;")
            h.addWidget(ic); h.addWidget(t)
            fl.addWidget(chip)
        lay.addWidget(rw)
        rw.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        rw.setFixedHeight(max(44, fl.heightForWidth(900)))
        f.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        return f

    def _mark(self, code, on):
        red = set(self.state.get("redeemed_codes") or [])
        (red.add if on else red.discard)(code)
        self.state.set("redeemed_codes", sorted(red))
        self.render()
