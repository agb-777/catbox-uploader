"""Square app icon drawn in code (no image asset needed). One drawing, two colour schemes."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF

BLUE = QColor(0x2A, 0x6F, 0xDB)

# theme -> (background, foreground)
SCHEMES = {
    "light": (QColor("white"), BLUE),
    "dark": (QColor(0x14, 0x16, 0x1C), QColor(0x5B, 0x9B, 0xFF)),
}


def draw(size=256, theme="light"):
    bg, fg = SCHEMES.get(theme, SCHEMES["light"])
    pm = QPixmap(size, size)
    pm.fill(bg)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    u = size / 512.0
    p.setPen(Qt.PenStyle.NoPen)

    # frame
    outer = QRectF(36 * u, 36 * u, size - 72 * u, size - 72 * u)
    p.setBrush(fg)
    p.drawRect(outer)
    p.setBrush(bg)
    p.drawRect(outer.adjusted(28 * u, 28 * u, -28 * u, -28 * u))

    # upload arrow + base bar
    cx = size / 2.0
    p.setBrush(fg)
    p.drawPolygon(QPolygonF([QPointF(cx, 130 * u), QPointF(cx + 96 * u, 238 * u),
                             QPointF(cx - 96 * u, 238 * u)]))
    p.drawRect(QRectF(cx - 36 * u, 238 * u, 72 * u, 120 * u))
    p.drawRect(QRectF(cx - 104 * u, 384 * u, 208 * u, 28 * u))
    p.end()
    return pm


def icon(theme="light"):
    ic = QIcon()
    for s in (16, 32, 48, 64, 128, 256):
        ic.addPixmap(draw(s, theme))
    return ic
