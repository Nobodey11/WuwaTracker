"""Shareable summary image (PNG): banner stats and your latest 5★ portraits, drawn with QPainter."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from .header import app_icon

W, H = 1200, 675
GOLD, PURPLE, TEXT, MUTED = QColor("#f5c518"), QColor("#b48cff"), QColor("#eef0f6"), QColor("#9a9caa")
CARD, BORDER = QColor(255, 255, 255, 14), QColor(255, 255, 255, 34)


def _font(size, bold=False):
    f = QFont("Segoe UI"); f.setPixelSize(size); f.setBold(bold)
    return f


def render(state, banners: tuple[int, ...] = (1, 2, 3)) -> QImage:
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
    g = QLinearGradient(0, 0, W, H)
    g.setColorAt(0, QColor("#141a33")); g.setColorAt(0.55, QColor("#0d1020")); g.setColorAt(1, QColor("#1d1430"))
    p.fillRect(0, 0, W, H, g)
    # soft gold glow
    for r, a in ((420, 18), (260, 22)):
        p.setPen(Qt.NoPen); p.setBrush(QColor(245, 197, 24, a)); p.drawEllipse(W - 260 - r // 2, -r // 2, r, r)
    # header
    p.drawPixmap(48, 40, app_icon().pixmap(56, 56))
    p.setPen(TEXT); p.setFont(_font(34, True)); p.drawText(120, 82, "WuWa Pull Tracker")
    nick = state.nickname() or ""
    p.setPen(MUTED); p.setFont(_font(18))
    sub = (f"{nick} · " if nick else "") + f"UID {state.player or '–'} · {date.today():%d %b %Y} · patch {state.gd.patch}"
    p.drawText(122, 110, sub)
    total = sum(s.total_pulls for s in state.stats.values())
    p.setPen(GOLD); p.setFont(_font(20, True))
    p.drawText(QRectF(W - 460, 54, 412, 30), Qt.AlignRight, f"{total:,} pulls · {total * 160:,} Astrite")
    # banner cards
    stats = [state.stats[b] for b in banners if b in state.stats]
    x, y, cw, ch = 48, 150, (W - 96 - 2 * 24) / 3, 250
    for s in stats[:3]:
        path = QPainterPath(); path.addRoundedRect(QRectF(x, y, cw, ch), 18, 18)
        p.fillPath(path, CARD); p.setPen(QPen(BORDER, 1.2)); p.drawPath(path)
        p.setPen(TEXT); p.setFont(_font(22, True)); p.drawText(QRectF(x + 24, y + 20, cw - 48, 30), Qt.AlignLeft, s.name)
        p.setPen(GOLD); p.setFont(_font(56, True))
        p.drawText(QRectF(x + 24, y + 58, cw - 48, 70), Qt.AlignLeft, str(s.pity5))
        p.setPen(MUTED); p.setFont(_font(16)); p.drawText(QRectF(x + 24, y + 128, cw - 48, 24), Qt.AlignLeft,
                                                         "pulls since the last 5★" + ("  ·  guaranteed" if s.guaranteed else ""))
        rows = [("Pulls", f"{s.total_pulls:,}"), ("5★", str(s.count5)),
                ("Avg. 5★ pity", f"{s.avg_pity5:.1f}" if s.avg_pity5 else "–")]
        if s.has_5050:
            rows.append(("50/50", f"{s.wins} won · {s.losses} lost"))
        p.setFont(_font(17))
        for i, (k, v) in enumerate(rows):
            yy = y + 160 + i * 22
            p.setPen(MUTED); p.drawText(QRectF(x + 24, yy, cw / 2, 22), Qt.AlignLeft, k)
            p.setPen(TEXT); p.drawText(QRectF(x + cw / 2, yy, cw / 2 - 24, 22), Qt.AlignRight, v)
        x += cw + 24
    # latest 5★ portraits
    fives = sorted((f for s in state.stats.values() for f in s.five_stars), key=lambda f: f.time, reverse=True)[:9]
    p.setPen(TEXT); p.setFont(_font(20, True)); p.drawText(48, 452, "Latest 5★")
    px, size = 48, 108
    for f in fives:
        rect = QRectF(px, 470, size, size + 30)
        clip = QPainterPath(); clip.addRoundedRect(QRectF(px, 470, size, size), 14, 14)
        p.fillPath(clip, QColor(245, 197, 24, 40))
        pm = None
        if state.prydwen_on():
            url = state.prydwen.portrait_url(f.name, f.resource_id)
            path_ = state.prydwen.image_path(url) if url else None
            if path_:
                pm = QPixmap(str(path_))
        if pm is not None and not pm.isNull():
            sc = pm.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.save(); p.setClipPath(clip)
            p.drawPixmap(int(px + (size - sc.width()) / 2), int(470 + (size - sc.height()) / 2), sc)
            p.restore()
        else:
            p.setPen(GOLD); p.setFont(_font(34, True)); p.drawText(QRectF(px, 470, size, size), Qt.AlignCenter, f.name[:2].upper())
        col = QColor("#ff8a8a") if f.result == "lost" else GOLD
        p.setPen(QPen(col, 2)); p.setBrush(Qt.NoBrush); p.drawPath(clip)
        p.setPen(TEXT); p.setFont(_font(14, True))
        p.drawText(QRectF(px - 6, 470 + size + 4, size + 12, 18), Qt.AlignCenter, f.name if len(f.name) < 15 else f.name[:13] + "…")
        p.setPen(MUTED); p.setFont(_font(13))
        p.drawText(QRectF(px, 470 + size + 22, size, 18), Qt.AlignCenter, f"pity {f.pity}")
        px += size + 18
        if px + size > W - 40:
            break
    p.setPen(QColor(255, 255, 255, 90)); p.setFont(_font(12))
    p.drawText(QRectF(48, H - 34, W - 96, 20), Qt.AlignRight,
               "Unofficial fan tool · not affiliated with Kuro Games, WuWa Tracker or Prydwen.gg")
    p.end()
    return img
