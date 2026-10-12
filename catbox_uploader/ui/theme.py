"""Plain light theme with standard widgets (independent of the system dark theme)."""

from PySide6.QtGui import QColor, QPalette

RED = QColor(0xC6, 0x28, 0x28)
GREEN = QColor(0x2E, 0x7D, 0x32)


def apply_light_theme(app):
    app.setStyle("Fusion")
    p = QPalette()
    CR, CG = QPalette.ColorRole, QPalette.ColorGroup
    white, black, grey = QColor("white"), QColor("black"), QColor(0x90, 0x90, 0x90)
    p.setColor(CR.Window, white)
    p.setColor(CR.WindowText, black)
    p.setColor(CR.Base, white)
    p.setColor(CR.AlternateBase, QColor(0xF5, 0xF5, 0xF5))
    p.setColor(CR.Text, black)
    p.setColor(CR.Button, QColor(0xF0, 0xF0, 0xF0))
    p.setColor(CR.ButtonText, black)
    p.setColor(CR.PlaceholderText, QColor(0x80, 0x80, 0x80))
    p.setColor(CR.ToolTipBase, white)
    p.setColor(CR.ToolTipText, black)
    p.setColor(CR.Highlight, QColor(0x00, 0x78, 0xD7))
    p.setColor(CR.HighlightedText, white)
    for role in (CR.Text, CR.ButtonText, CR.WindowText):
        p.setColor(CG.Disabled, role, grey)
    app.setPalette(p)
