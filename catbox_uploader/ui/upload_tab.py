"""'Upload' tab: file queue and upload controls. The upload itself is driven by MainWindow."""

import os

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..core import validators
from ..core.constants import MIN_COL_W, QUEUE_DEFAULT_WIDTHS
from ..core.helpers import human_size, plural
from ..core.queue_item import QueueItem, QueueStatus
from ..net.status_checker import StatusChecker
from .theme import GREEN, RED


class UploadTab(QWidget):
    upload_requested = Signal()
    cancel_requested = Signal()
    uploading_changed = Signal(bool)
    notify = Signal(str, str)             # message, kind ("info" / "error")

    def __init__(self, check_on_start=True, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._start_dir = os.path.expanduser("~")
        self._fixed_dir = ""
        self._uploading = False
        self._can_cancel = False
        self._checking = False
        self._closing = False
        self._next_id = 1
        self.items = []
        self._status_worker = None

        root = QVBoxLayout(self)

        # ---- top row: add / remove / service status ----
        top = QHBoxLayout()
        self.add_btn = QPushButton("Add files...")
        self.add_btn.clicked.connect(lambda: self.pick_files())
        top.addWidget(self.add_btn)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_selected)
        top.addWidget(self.remove_btn)
        top.addStretch()
        self.service_status = QLabel("")
        self.service_status.setTextFormat(Qt.TextFormat.PlainText)
        top.addWidget(self.service_status)
        self.check_btn = QPushButton("Check")
        self.check_btn.clicked.connect(lambda: self.check_service())
        top.addWidget(self.check_btn)
        root.addLayout(top)

        # ---- queue ----
        self.queue_table = QTableWidget(0, 4)
        self.queue_table.setHorizontalHeaderLabels(["File", "Type", "Size", "Status"])
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setShowGrid(False)
        self.queue_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        hh = self.queue_table.horizontalHeader()
        hh.setMinimumSectionSize(MIN_COL_W)
        hh.setSectionsMovable(False)
        hh.setStretchLastSection(True)
        hh.setHighlightSections(False)
        for i in range(self.queue_table.columnCount()):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate(QUEUE_DEFAULT_WIDTHS):
            self.queue_table.setColumnWidth(i, w)
        root.addWidget(self.queue_table, 1)

        del_sc = QShortcut(QKeySequence("Delete"), self.queue_table)
        del_sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        del_sc.activated.connect(self.remove_selected)

        # ---- upload row ----
        up = QHBoxLayout()
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self.emit_upload)
        up.addWidget(self.upload_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._request_cancel)
        up.addWidget(self.cancel_btn)
        up.addStretch()
        self.speed_label = QLabel("")
        self.speed_label.setTextFormat(Qt.TextFormat.PlainText)
        up.addWidget(self.speed_label)
        root.addLayout(up)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.queue_table.itemSelectionChanged.connect(self._refresh_controls)

        self._initial_check = QTimer(self)
        self._initial_check.setSingleShot(True)
        self._initial_check.timeout.connect(lambda: self.check_service())
        if check_on_start:
            self._initial_check.start(200)

        self._after_queue_change()

    # ---------- public settings ----------
    def set_start_dir(self, path):
        self._start_dir = path or os.path.expanduser("~")

    def set_fixed_dir(self, path):
        self._fixed_dir = path or ""

    @property
    def uploading(self):
        return self._uploading

    @property
    def can_cancel(self):
        return self._uploading and self._can_cancel

    def pick_files(self):
        def is_dir(p):
            return bool(p) and os.path.isdir(p)
        directory = self._start_dir
        if is_dir(self._fixed_dir):
            directory = self._fixed_dir
        elif not is_dir(directory):
            directory = os.path.expanduser("~")
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files", directory,
                                                validators.file_dialog_filter())
        if not paths:
            return False
        self.add_paths(paths)
        return True

    # ---------- state ----------
    def _selected_rows(self):
        sm = self.queue_table.selectionModel()
        return sorted({i.row() for i in sm.selectedRows()}) if sm is not None else []

    def _refresh_controls(self):
        up = self._uploading
        self.upload_btn.setEnabled(not up and bool(self.items))
        self.cancel_btn.setEnabled(up and self._can_cancel)
        self.add_btn.setEnabled(not up)
        self.remove_btn.setEnabled(not up and bool(self._selected_rows()))
        self.check_btn.setEnabled(not up and not self._checking)

    def _request_cancel(self):
        if not self.can_cancel:
            return
        self.speed_label.setText("Cancelling...")
        self.cancel_btn.setEnabled(False)
        self.cancel_requested.emit()

    # ---------- service check ----------
    def _set_service_text(self, text, color=None):
        pal = self.service_status.palette()
        pal.setColor(QPalette.ColorRole.WindowText,
                     color if color is not None else self.palette().color(QPalette.ColorRole.WindowText))
        self.service_status.setPalette(pal)
        self.service_status.setText(text)

    def check_service(self):
        if self._closing or self._checking:
            return
        self._checking = True
        self._set_service_text("catbox.moe: checking...")
        self._refresh_controls()
        w = StatusChecker()
        w.result.connect(self._on_status_result)
        w.done.connect(self._on_status_done)
        self._status_worker = w
        w.start()

    def _on_status_result(self, ok, message):
        self._set_service_text(f"catbox.moe: {message}", GREEN if ok else RED)

    def _on_status_done(self):
        w, self._status_worker = self._status_worker, None
        self._checking = False
        if w is not None:
            w.release()
        self._refresh_controls()

    def shutdown(self):
        self._closing = True
        self._initial_check.stop()
        if self._status_worker is not None:
            self._status_worker.detach()

    # ---------- drag & drop ----------
    @staticmethod
    def _local_paths(mime):
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]

    def dragEnterEvent(self, event):
        if not self._uploading and event.mimeData().hasUrls() and self._local_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self._uploading and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [] if self._uploading else self._local_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.add_paths(paths)

    # ---------- queue ----------
    def add_paths(self, paths):
        """Single entry point for Add files and drag & drop."""
        if self._uploading:
            return

        # normcase: on case-insensitive file systems (Windows) "A.png" == "a.png".
        known = {os.path.normcase(it.path) for it in self.items}
        added = dup = skipped = 0
        blocked = set()
        last_dir = ""

        for p in paths:
            if not os.path.isfile(p):
                skipped += 1
                continue
            ap = os.path.abspath(p)
            ext = validators.extension_of(ap)
            if validators.is_blocked_ext(ext):
                blocked.add(ext)
                continue
            key = os.path.normcase(ap)
            if key in known:
                dup += 1
                continue
            try:
                size = os.path.getsize(ap)
            except OSError:
                skipped += 1
                continue
            if size <= 0:
                skipped += 1
                continue
            self.items.append(QueueItem(id=self._next_id, path=ap, name=os.path.basename(ap),
                                        size=size, kind=validators.file_kind(ap)))
            self._next_id += 1
            known.add(key)
            last_dir = os.path.dirname(ap)
            added += 1

        if added:
            self._start_dir = last_dir
            self.speed_label.clear()
            self.progress.setValue(0)
            self._after_queue_change()
        if blocked:
            self.notify.emit(f"Not accepted: {', '.join(sorted(blocked))}", "error")
        elif skipped:
            self.notify.emit(f"{plural(skipped, 'file')} skipped", "error")
        elif dup and not added:
            self.notify.emit("Already in the list", "info")

    def _after_queue_change(self):
        t = self.queue_table
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        for item in self.items:
            self._append_row(item)
        t.setUpdatesEnabled(True)
        n = len(self.items)
        self.upload_btn.setText(f"Upload ({n})" if n else "Upload")
        self._refresh_controls()

    def _append_row(self, item):
        t = self.queue_table
        r = t.rowCount()
        t.insertRow(r)
        size = QTableWidgetItem(human_size(item.size))
        size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        t.setItem(r, 0, QTableWidgetItem(item.name))
        t.setItem(r, 1, QTableWidgetItem(item.kind))
        t.setItem(r, 2, size)
        t.setItem(r, 3, QTableWidgetItem(""))
        self._paint_status(r, item)

    def _paint_status(self, row, item):
        cell = self.queue_table.item(row, 3)
        if cell is None:
            return
        S = QueueStatus
        brush = None
        if item.status == S.QUEUED:
            text = "Queued"
        elif item.status == S.UPLOADING:
            text = f"Uploading {item.detail}".strip()
        elif item.status == S.PROCESSING:
            text = "Processing"
        elif item.status == S.DONE:
            text, brush = "Done", GREEN
        elif item.status == S.FAILED:
            text, brush = (f"Failed: {item.detail}" if item.detail else "Failed"), RED
        else:
            text = "Cancelled"
        cell.setText(text)
        cell.setForeground(QBrush(brush) if brush is not None else QBrush())

    def _row_of(self, item_id):
        for i, it in enumerate(self.items):
            if it.id == item_id:
                return i
        return -1

    def set_item_status(self, item_id, status, detail="", reveal=False):
        row = self._row_of(item_id)
        if row < 0:
            return
        it = self.items[row]
        it.status, it.detail = status, detail
        self._paint_status(row, it)
        if reveal:
            cell = self.queue_table.item(row, 0)
            if cell is not None:
                self.queue_table.scrollToItem(cell)

    def reset_statuses(self):
        for i, it in enumerate(self.items):
            it.status, it.detail = QueueStatus.QUEUED, ""
            self._paint_status(i, it)

    def remove_items(self, ids):
        ids = set(ids)
        self.items = [it for it in self.items if it.id not in ids]
        self._after_queue_change()

    def remove_selected(self):
        if self._uploading:
            return
        ids = [self.items[r].id for r in self._selected_rows() if 0 <= r < len(self.items)]
        if ids:
            self.remove_items(ids)

    def pending_items(self):
        return [it for it in self.items if it.status != QueueStatus.DONE]

    def emit_upload(self):
        if self._uploading or not self.pending_items():
            return
        self.upload_requested.emit()

    # ---------- upload state ----------
    def set_uploading(self, uploading):
        self._uploading = uploading
        self._can_cancel = uploading
        self._refresh_controls()
        self.uploading_changed.emit(bool(uploading))

    def set_can_cancel(self, value):
        self._can_cancel = bool(value) and self._uploading
        self._refresh_controls()

    def update_progress(self, pct, speed_text=None):
        """speed_text=None leaves the current text unchanged."""
        self.progress.setValue(pct)
        if speed_text is not None:
            self.speed_label.setText(speed_text)

    def set_speed_text(self, text):
        self.speed_label.setText(text)

    def reset_progress(self):
        self.progress.setValue(0)
