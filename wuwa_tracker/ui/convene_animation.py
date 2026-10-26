"""Full-window Convene animation for the simulator (original artwork, drawn with QPainter).

Phases:  launch (comet streak, colour = best rarity, gold 'upgrade' late)  ->  burst (flash + shockwave)
         -> one reveal per 4★/5★ (light rays, portrait slides in, stars pop in, shine sweep)  ->  done.
Click anywhere to advance a phase; 'Skip' jumps to the results.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import QPushButton, QWidget

WHITE = QColor("#e8f0ff")
BLUE = QColor("#6aa9ff")
PURPLE = QColor("#b48cff")
GOLD = QColor("#ffcc33")
RARITY = {3: BLUE, 4: PURPLE, 5: GOLD}

LAUNCH, BURST = 1.9, 0.7                     # seconds
REVEAL = {3: 1.0, 4: 2.0, 5: 2.8}            # timeline length per reveal, by rarity
SPEED = {3: 2.0, 4: 1.0, 5: 1.0}             # 3★ reveals play at double speed


def ease(t):          # smoothstep 0..1
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def alpha(c: QColor, a: float) -> QColor:
    c = QColor(c)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


class ConveneAnimation(QWidget):
    finished = Signal()

    def __init__(self, parent, items, images, prydwen, sound=None):
        super().__init__(parent)
        self.items = items
        self.images = images
        self.sound = sound
        self.best = max(i.rarity for i in items)
        self.reveals = list(items)                           # every item, in pull order (3★ go fast)
        self.played = set()
        self.urls = {id(i): prydwen.card_url(i.name, i.resource_id) if (i.rarity >= 4 or i.resource_id) else None
                     for i in self.reveals}
        for u in self.urls.values():                          # start downloading during the launch
            if u:
                images.cached(u)
        images.ready.connect(self._on_image)
        rnd = random.Random()
        self.stars = [(rnd.random(), rnd.random(), rnd.uniform(0.6, 2.2), rnd.uniform(0.01, 0.05), rnd.random() * 6.28)
                      for _ in range(160)]
        self.sparks = [(rnd.uniform(0, 6.28), rnd.uniform(0.35, 1.0), rnd.uniform(1.5, 4)) for _ in range(70)]
        self.phase = "launch"
        self.offset = 0.0
        self.idx = 0
        self.clock = QElapsedTimer(); self.clock.start()
        self.total = QElapsedTimer(); self.total.start()
        self.timer = QTimer(self); self.timer.timeout.connect(self.update); self.timer.start(16)
        self.skip_btn = QPushButton("Skip  ▶▶", self)
        self.skip_btn.setStyleSheet("QPushButton { background: rgba(0,0,0,110); color: white; border: 1px solid "
                                    "rgba(255,255,255,90); border-radius: 14px; padding: 6px 16px; }"
                                    "QPushButton:hover { border-color: #ffcc33; }")
        self.skip_btn.clicked.connect(self.finish)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setCursor(Qt.PointingHandCursor)
        self.setGeometry(parent.rect())
        self.show(); self.raise_()
        self._sfx("whoosh")

    def _sfx(self, name, once_key=None):
        if self.sound is None:
            return
        if once_key is not None:
            if once_key in self.played:
                return
            self.played.add(once_key)
        self.sound.play(name)

    def _on_image(self, _url):
        self.update()

    # ---------------- control
    def resizeEvent(self, e):
        self.skip_btn.adjustSize()
        self.skip_btn.move(self.width() - self.skip_btn.width() - 24, 20)

    def mousePressEvent(self, e):
        self.advance()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.finish()
        else:
            self.advance()

    def advance(self):
        if self.phase in ("launch", "burst"):
            self._start_reveals()
        elif self.phase == "reveal":
            if not self._reveal_done():             # first click: finish this reveal instantly
                self.offset = 99.0
                return
            self.idx += 1
            self.offset = 0.0
            self.clock.restart()
            if self.idx >= len(self.reveals):
                self.finish()
            else:
                self._sfx(f"reveal{self.reveals[self.idx].rarity}")

    def _reveal_t(self):
        it = self.reveals[self.idx]
        return (self.clock.elapsed() / 1000.0 + self.offset) * SPEED[it.rarity]

    def _reveal_done(self):
        return self._reveal_t() >= REVEAL[self.reveals[self.idx].rarity]

    def _start_reveals(self):
        self.offset = 0.0
        self.clock.restart()
        if self.reveals:
            self.phase, self.idx = "reveal", 0
            self._sfx(f"reveal{self.reveals[0].rarity}")
        else:
            self.finish()

    def finish(self):
        if self.phase == "done":
            return
        self.phase = "done"
        self.timer.stop()
        try:
            self.images.ready.disconnect(self._on_image)
        except (RuntimeError, TypeError):
            pass
        self.hide()
        self.finished.emit()
        self.deleteLater()

    # ---------------- painting
    def paintEvent(self, e):
        t = self.clock.elapsed() / 1000.0
        if self.phase == "launch" and t >= LAUNCH:
            self.phase = "burst"; self.clock.restart(); t = 0
            self._sfx(f"burst{self.best}")
        elif self.phase == "burst" and t >= BURST:
            self._start_reveals(); t = 0
        # reveals never auto-advance: they wait for a click / key press
        if self.phase == "done":
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._sky(p)
        if self.phase == "launch":
            self._launch(p, t)
        elif self.phase == "burst":
            self._burst(p, t)
        elif self.phase == "reveal":
            it = self.reveals[self.idx]
            self._reveal(p, min(self._reveal_t(), REVEAL[it.rarity] + 50), it)
        p.end()

    def _sky(self, p):
        w, h = self.width(), self.height()
        g = QRadialGradient(QPointF(w * 0.5, h * 0.62), max(w, h) * 0.8)
        g.setColorAt(0, QColor("#1b2140")); g.setColorAt(0.55, QColor("#0c1022")); g.setColorAt(1, QColor("#05060c"))
        p.fillRect(self.rect(), g)
        now = self.total.elapsed() / 1000.0
        p.setPen(Qt.NoPen)
        for x, y, s, sp, ph in self.stars:
            yy = (y - now * sp) % 1.0
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(now * 2.2 + ph))
            p.setBrush(alpha(WHITE, a * 0.8))
            p.drawEllipse(QPointF(x * w, yy * h), s, s)

    def _comet_color(self, u):
        c = mix(WHITE, BLUE, u / 0.35)
        if self.best >= 4 and u > 0.45:
            c = mix(c, PURPLE, (u - 0.45) / 0.15)
        if self.best == 5 and u > 0.72:                 # late "upgrade" to gold
            c = mix(c, GOLD, (u - 0.72) / 0.1)
        return c

    def _launch(self, p, t):
        w, h = self.width(), self.height()
        u = t / LAUNCH
        start, ctrl, end = QPointF(w * 0.08, h * 1.05), QPointF(w * 0.2, h * 0.25), QPointF(w * 0.5, h * 0.45)

        def bez(s):
            a = (1 - s) ** 2; b = 2 * (1 - s) * s; c = s * s
            return QPointF(a * start.x() + b * ctrl.x() + c * end.x(), a * start.y() + b * ctrl.y() + c * end.y())
        head_s = ease(u)
        col = self._comet_color(u)
        if self.best == 5 and u > 0.72:
            self._sfx("shimmer", "shimmer")
        # tail
        for k in range(40):
            s = head_s - k * 0.012
            if s < 0:
                break
            pt = bez(s)
            r = max(1.0, 16 - k * 0.38)
            p.setBrush(alpha(col, 0.55 * (1 - k / 40)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(pt, r, r)
        head = bez(head_s)
        glow = QRadialGradient(head, 80 + 60 * u)
        glow.setColorAt(0, alpha(WHITE, 0.95)); glow.setColorAt(0.25, alpha(col, 0.8)); glow.setColorAt(1, alpha(col, 0))
        p.setBrush(glow)
        p.drawEllipse(head, 80 + 60 * u, 80 + 60 * u)
        # pulsing target ring
        ring = 40 + 25 * math.sin(t * 6)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(alpha(col, 0.25 + 0.25 * u), 2))
        p.drawEllipse(end, ring + 60 * u, ring + 60 * u)
        self._caption(p, "Convening…", alpha(WHITE, 0.6 * (1 - u)))

    def _burst(self, p, t):
        w, h = self.width(), self.height()
        u = t / BURST
        c = QPointF(w * 0.5, h * 0.45)
        col = RARITY[self.best]
        flash = QRadialGradient(c, max(w, h) * (0.3 + 0.9 * ease(u)))
        flash.setColorAt(0, alpha(WHITE, 1 - u)); flash.setColorAt(0.3, alpha(col, 0.85 * (1 - u))); flash.setColorAt(1, alpha(col, 0))
        p.setPen(Qt.NoPen); p.setBrush(flash); p.drawRect(self.rect())
        p.setBrush(Qt.NoBrush)
        for k, r in enumerate((0.0, 0.12)):
            rr = max(0.0, ease(u - r)) * max(w, h) * 0.6
            p.setPen(QPen(alpha(col, 0.8 * (1 - u)), 6 - 3 * k))
            p.drawEllipse(c, rr, rr)
        p.setPen(Qt.NoPen)
        for ang, spd, size in self.sparks:
            d = ease(u) * spd * max(w, h) * 0.5
            p.setBrush(alpha(mix(WHITE, col, 0.5), 1 - u))
            p.drawEllipse(QPointF(c.x() + math.cos(ang) * d, c.y() + math.sin(ang) * d), size, size)

    def _reveal(self, p, t, item):
        w, h = self.width(), self.height()
        col = RARITY[item.rarity]
        # background tint + rotating light rays
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, alpha(col, 0.28)); bg.setColorAt(0.6, alpha(col, 0.08)); bg.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), bg)
        cx, cy = w * 0.62, h * 0.48
        p.save(); p.translate(cx, cy); p.rotate(t * 12)
        p.setPen(Qt.NoPen)
        for k in range(14):
            p.rotate(360 / 14)
            path = QPainterPath(); path.moveTo(0, 0)
            path.lineTo(max(w, h), -40); path.lineTo(max(w, h), 40); path.closeSubpath()
            strength = 0.5 if item.rarity == 3 else 1.0
            p.setBrush(alpha(col, (0.07 if k % 2 else 0.035) * strength))
            p.drawPath(path)
        p.restore()
        # portrait slides in from the right
        slide = ease(t / 0.55)
        card_h = h * 0.78
        card_w = card_h * 0.7
        x = w * 0.62 - card_w / 2 + (1 - slide) * w * 0.4
        y = h * 0.5 - card_h / 2
        rect = QRectF(x, y, card_w, card_h)
        url = self.urls.get(id(item))
        pm = self.images.cached(url) if url else None
        p.setOpacity(slide)
        glow = QRadialGradient(rect.center(), card_h * 0.7)
        glow.setColorAt(0, alpha(col, 0.45)); glow.setColorAt(1, alpha(col, 0))
        p.setBrush(glow); p.drawEllipse(rect.center(), card_h * 0.7, card_h * 0.7)
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(int(card_w), int(card_h), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(int(rect.center().x() - scaled.width() / 2), int(rect.center().y() - scaled.height() / 2), scaled)
            frame = QRectF(rect.center().x() - scaled.width() / 2, rect.center().y() - scaled.height() / 2,
                           scaled.width(), scaled.height())
        else:   # no art (offline / not on Prydwen): emblem
            frame = rect
            p.setPen(QPen(alpha(col, 0.9), 3)); p.setBrush(alpha(col, 0.15))
            p.drawRoundedRect(rect, 18, 18)
            p.setPen(alpha(WHITE, 0.9)); f = QFont(); f.setPointSize(int(card_h / 7)); f.setBold(True); p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, item.name[:2].upper())
        # shine sweep across the portrait
        sweep = (t - 0.5) / 0.7
        if 0 <= sweep <= 1:
            p.save(); p.setClipRect(frame)
            sx = frame.left() - frame.width() * 0.5 + sweep * frame.width() * 2
            sh = QLinearGradient(sx - 60, 0, sx + 60, 0)
            sh.setColorAt(0, QColor(255, 255, 255, 0)); sh.setColorAt(0.5, QColor(255, 255, 255, 110)); sh.setColorAt(1, QColor(255, 255, 255, 0))
            p.setPen(Qt.NoPen); p.setBrush(sh); p.drawRect(frame)
            p.restore()
        p.setOpacity(1.0)
        # name, stars and tag on the left
        tx = w * 0.08
        a = ease((t - 0.35) / 0.4)
        f = QFont(); f.setBold(True)
        max_w = (w * 0.62 - card_w / 2) - tx - 30          # keep the name left of the portrait
        size = 40
        while size > 14:
            f.setPointSize(size)
            if QFontMetrics(f).horizontalAdvance(item.name) <= max_w:
                break
            size -= 2
        p.setFont(f)
        p.setPen(alpha(WHITE, a)); p.drawText(QPointF(tx, h * 0.62), item.name)
        f.setPointSize(30); p.setFont(f)
        for k in range(item.rarity):
            sa = ease((t - 0.6 - k * 0.12) / 0.2)
            if sa > 0 and item.rarity >= 4 and self.offset == 0:
                self._sfx(f"star{k}", ("star", self.idx, k))
            p.setPen(alpha(col, sa))
            p.drawText(QPointF(tx + k * 44, h * 0.62 + 60), "★")
        f.setPointSize(13); f.setBold(True); p.setFont(f)
        tag = ""
        if item.rarity == 5:
            tag = {"won": "WON 50/50", "lost": "LOST 50/50 · next one guaranteed", "guaranteed": "GUARANTEED"}.get(
                item.result, "FEATURED") + f"   ·   pity {item.pity}"
        elif item.featured:
            tag = "RATE-UP"
        if tag:
            p.setPen(alpha(QColor("#ff8a8a") if item.result == "lost" else QColor("#7ef0b0"), ease((t - 1.0) / 0.3)))
            p.drawText(QPointF(tx, h * 0.62 + 100), tag)
        done = t >= REVEAL[item.rarity]
        pulse = 0.45 + 0.4 * (0.5 + 0.5 * math.sin(self.total.elapsed() / 1000.0 * 4)) if done else 0.3
        last = self.idx + 1 == len(self.reveals)
        hint = ("Click to see results  ▶" if last else "Click to continue  ▶") if done else ""
        self._caption(p, f"{self.idx + 1} / {len(self.reveals)}" + (f"      {hint}" if hint else ""), alpha(WHITE, pulse))

    def _caption(self, p, text, color):
        f = QFont(); f.setPointSize(11); p.setFont(f); p.setPen(color)
        p.drawText(QRectF(0, self.height() - 50, self.width(), 30), Qt.AlignCenter, text)
