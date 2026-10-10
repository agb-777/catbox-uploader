"""Square app icon drawn in code (no image asset needed)."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF

BLUE = QColor(0x2A, 0x6F, 0xDB)


def draw(size=256):
    pm = QPixmap(size, size)
    pm.fill(QColor("white"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    u = size / 512.0
    p.setPen(Qt.PenStyle.NoPen)

    # frame
    outer = QRectF(36 * u, 36 * u, size - 72 * u, size - 72 * u)
    p.setBrush(BLUE)
    p.drawRect(outer)
    p.setBrush(QColor("white"))
    p.drawRect(outer.adjusted(28 * u, 28 * u, -28 * u, -28 * u))

    # upload arrow + base bar
    cx = size / 2.0
    p.setBrush(BLUE)
    p.drawPolygon(QPolygonF([QPointF(cx, 130 * u), QPointF(cx + 96 * u, 238 * u),
                             QPointF(cx - 96 * u, 238 * u)]))
    p.drawRect(QRectF(cx - 36 * u, 238 * u, 72 * u, 120 * u))
    p.drawRect(QRectF(cx - 104 * u, 384 * u, 208 * u, 28 * u))
    p.end()
    return pm


def icon():
    ic = QIcon()
    for s in (16, 32, 48, 64, 128, 256):
        ic.addPixmap(draw(s))
    return ic
