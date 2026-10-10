"""'About' tab: name, version and links."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core.constants import APP_NAME, APP_VERSION, GITHUB_URL, LICENSE_NAME, SITE_URL


class AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.addStretch(1)

        title = QLabel(APP_NAME)
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(QLabel(f"Version {APP_VERSION}"), 0, Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(16)

        root.addWidget(self._link("Website", SITE_URL), 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._link("GitHub", GITHUB_URL), 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(QLabel(f"License: {LICENSE_NAME}"), 0, Qt.AlignmentFlag.AlignHCenter)

        root.addStretch(2)

    @staticmethod
    def _link(label, url):
        lab = QLabel(f'{label}: <a href="{url}">{url}</a>')
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setOpenExternalLinks(True)
        return lab
