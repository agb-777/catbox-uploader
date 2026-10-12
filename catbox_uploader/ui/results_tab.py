"""'History' tab. Pure view: it emits requests, MainWindow owns the data."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMenu, QPushButton, QTableWidget, QVBoxLayout, QWidget)

from ..core.constants import HISTORY_DEFAULT_WIDTHS, MIN_COL_W

COLUMNS = ["Filename", "URL", "Type", "Mode", "Size", "Date"]


class ResultsTab(QWidget):
    copy_requested = Signal()
    open_requested = Signal()
    remove_requested = Signal()
    clear_requested = Signal()
    export_requested = Signal()
    import_requested = Signal()
    delete_from_catbox_requested = Signal()

    filter_changed = Signal()
    sort_changed = Signal()
    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sort_col = 5
        self.sort_asc = False

        root = QVBoxLayout(self)

        # ---- search + count ----
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.filter_changed.emit())
        top.addWidget(self.search, 1)
        self.hist_count = QLabel("")
        top.addWidget(self.hist_count)
        root.addLayout(top)

        # ---- table ----
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setMinimumSectionSize(MIN_COL_W)
        hh.setSectionsMovable(False)
        hh.setStretchLastSection(True)
        for i in range(self.table.columnCount()):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate(HISTORY_DEFAULT_WIDTHS):
            self.table.setColumnWidth(i, w)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self._on_header_clicked)
        hh.setSortIndicator(5, Qt.SortOrder.DescendingOrder)
        hh.setSortIndicatorShown(True)
        root.addWidget(self.table, 1)

        # ---- buttons ----
        ha = QHBoxLayout()
        self.copy_btn = QPushButton("Copy URL")
        self.open_btn = QPushButton("Open")
        self.remove_btn = QPushButton("Remove")
        self.delete_btn = QPushButton("Delete from Catbox")
        self.import_btn = QPushButton("Import...")
        self.export_btn = QPushButton("Export...")
        self.clear_btn = QPushButton("Clear All")

        self.copy_btn.clicked.connect(self.copy_requested.emit)
        self.open_btn.clicked.connect(self.open_requested.emit)
        self.remove_btn.clicked.connect(self.remove_requested.emit)
        self.delete_btn.clicked.connect(self.delete_from_catbox_requested.emit)
        self.import_btn.clicked.connect(self.import_requested.emit)
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.clear_btn.clicked.connect(self.clear_requested.emit)

        for b in (self.copy_btn, self.open_btn, self.remove_btn, self.delete_btn):
            ha.addWidget(b)
        ha.addStretch()
        for b in (self.import_btn, self.export_btn, self.clear_btn):
            ha.addWidget(b)
        root.addLayout(ha)

        self.table.itemSelectionChanged.connect(self.selection_changed.emit)

    def _on_header_clicked(self, col):
        if col == self.sort_col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = col <= 3   # text columns ascending first, size / date descending first
        hh = self.table.horizontalHeader()
        hh.setSortIndicator(col, Qt.SortOrder.AscendingOrder if self.sort_asc else Qt.SortOrder.DescendingOrder)
        hh.setSortIndicatorShown(True)
        self.sort_changed.emit()

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return
        sm = self.table.selectionModel()
        selected = {i.row() for i in sm.selectedRows()} if sm is not None else set()
        if item.row() not in selected:
            self.table.selectRow(item.row())   # right-click inside the selection keeps it

        menu = QMenu(self)
        a_copy = menu.addAction("Copy URL")
        a_open = menu.addAction("Open")
        menu.addSeparator()
        a_delete = menu.addAction("Delete from Catbox")
        a_remove = menu.addAction("Remove")
        a_copy.triggered.connect(self.copy_requested.emit)
        a_open.triggered.connect(self.open_requested.emit)
        a_delete.triggered.connect(self.delete_from_catbox_requested.emit)
        a_remove.triggered.connect(self.remove_requested.emit)
        a_delete.setEnabled(self.delete_btn.isEnabled())
        menu.exec(self.table.viewport().mapToGlobal(pos))
        menu.deleteLater()
