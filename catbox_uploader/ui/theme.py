"""Light / dark themes: Fusion + palette + one shared stylesheet (only the colours differ)."""

from string import Template

from PySide6.QtGui import QColor, QPalette

from ..core.constants import DEFAULT_THEME, THEMES
from . import app_icon

# Status colours: light theme (kept for compatibility) and brighter ones for the dark theme.
RED = QColor(0xC6, 0x28, 0x28)
GREEN = QColor(0x2E, 0x7D, 0x32)
RED_DARK = QColor(0xFF, 0x6B, 0x6B)
GREEN_DARK = QColor(0x4A, 0xDE, 0x80)

_current = DEFAULT_THEME


def current():
    return _current


def ok_color():
    return GREEN_DARK if _current == "dark" else GREEN


def err_color():
    return RED_DARK if _current == "dark" else RED


# ------------------------------------------------------------------ colour tokens
# Both themes use the SAME palette code and the SAME stylesheet; only these colours differ,
# so shapes, spacing and behaviour are identical in light and dark.
LIGHT = {
    "bg": "#FFFFFF",          # window
    "surface": "#FFFFFF",     # inputs, tables, menus
    "alt": "#F5F6F8",         # alternate table rows
    "border": "#D5D9E0",
    "btn": "#F0F2F5",
    "btn_hover": "#E6E9EE",
    "btn_pressed": "#DADEE4",
    "text": "#1B1F24",
    "muted": "#6B7280",
    "disabled": "#A0A6B0",
    "placeholder": "#8A919C",
    "accent": "#2A6FDB",
    "sel": "#2A6FDB",
    "handle": "#C3C8D0",
    "handle_hover": "#A9AFB9",
    "bright": "#C62828",
}

DARK = {
    "bg": "#15171C",
    "surface": "#1B1E25",
    "alt": "#20242C",
    "border": "#2C313B",
    "btn": "#262B34",
    "btn_hover": "#2F3541",
    "btn_pressed": "#1F232A",
    "text": "#E4E7EC",
    "muted": "#8B93A1",
    "disabled": "#5C6370",
    "placeholder": "#6B7280",
    "accent": "#4C8DFF",
    "sel": "#2F6BD8",
    "handle": "#3A414D",
    "handle_hover": "#4A5361",
    "bright": "#FF6B6B",
}


def _palette(t):
    p = QPalette()
    CR, CG = QPalette.ColorRole, QPalette.ColorGroup
    c = {k: QColor(v) for k, v in t.items()}
    p.setColor(CR.Window, c["bg"])
    p.setColor(CR.WindowText, c["text"])
    p.setColor(CR.Base, c["surface"])
    p.setColor(CR.AlternateBase, c["alt"])
    p.setColor(CR.Text, c["text"])
    p.setColor(CR.Button, c["btn"])
    p.setColor(CR.ButtonText, c["text"])
    p.setColor(CR.BrightText, c["bright"])
    p.setColor(CR.PlaceholderText, c["placeholder"])
    p.setColor(CR.ToolTipBase, c["btn"])
    p.setColor(CR.ToolTipText, c["text"])
    p.setColor(CR.Link, c["accent"])
    p.setColor(CR.Highlight, c["sel"])
    p.setColor(CR.HighlightedText, QColor("white"))
    for role in (CR.Text, CR.ButtonText, CR.WindowText):
        p.setColor(CG.Disabled, role, c["disabled"])
    return p


_QSS = Template("""
QMainWindow, QDialog, QMessageBox { background: $bg; }

QTabBar { qproperty-drawBase: 0; }
QTabWidget::pane { border: 1px solid $border; background: $bg; top: -1px; }
QTabBar::tab { background: transparent; color: $muted; padding: 9px 18px; margin-right: 2px;
               border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:hover { color: $text; }
QTabBar::tab:selected { color: $text; border-bottom: 2px solid $accent; }

QPushButton { background: $btn; color: $text; border: 1px solid $border;
              padding: 6px 14px; }
QPushButton:hover { background: $btn_hover; border-color: $handle_hover; }
QPushButton:pressed { background: $btn_pressed; }
QPushButton:default { border-color: $accent; }
QPushButton:disabled { color: $disabled; background: $surface; border-color: $border; }
QPushButton[hasMenu="true"] { padding-right: 26px; }
QPushButton::menu-indicator { subcontrol-origin: padding; subcontrol-position: center right; right: 9px; }

QLineEdit, QComboBox { background: $surface; color: $text; border: 1px solid $border;
                       padding: 5px 8px; selection-background-color: $sel; }
QLineEdit:focus, QComboBox:focus { border-color: $accent; }
QLineEdit:disabled, QComboBox:disabled { color: $disabled; }
QComboBox QAbstractItemView { background: $surface; border: 1px solid $border;
                              selection-background-color: $sel; outline: 0; }

QTableView, QTableWidget { background: $surface; alternate-background-color: $alt; color: $text;
                           border: 1px solid $border; gridline-color: $border;
                           selection-background-color: $sel; selection-color: white; outline: 0; }
QTableWidget::item { padding: 4px 6px; border: none; }

QGroupBox { border: 1px solid $border; margin-top: 14px; padding: 14px 12px 10px 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: $muted; }

QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid $handle_hover; background: $surface; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; }
QCheckBox::indicator:disabled { border-color: $border; background: $bg; }

QProgressBar { background: $surface; border: 1px solid $border;
               text-align: center; color: $text; min-height: 18px; }
QProgressBar::chunk { background: $accent; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $handle; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $handle_hover; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: $handle; min-width: 28px; }
QScrollBar::handle:horizontal:hover { background: $handle_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QMenu { background: $surface; color: $text; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 7px 24px; }
QMenu::item:selected { background: $sel; color: white; }
QMenu::item:disabled { color: $disabled; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }

QToolTip { background: $btn; color: $text; border: 1px solid $border; padding: 4px 6px; }
QStatusBar { color: $muted; }
QStatusBar::item { border: none; }
""")


# ------------------------------------------------------------------ public
def apply_theme(app, name):
    """Apply 'light' or 'dark' (anything else falls back to the default).

    Also switches the application icon to the matching colour scheme.
    """
    global _current
    if name not in THEMES:
        name = DEFAULT_THEME
    _current = name
    tokens = DARK if name == "dark" else LIGHT
    app.setStyle("Fusion")
    app.setPalette(_palette(tokens))
    app.setStyleSheet(_QSS.substitute(tokens))
    app.setWindowIcon(app_icon.icon(name))


def apply_light_theme(app):
    apply_theme(app, "light")
