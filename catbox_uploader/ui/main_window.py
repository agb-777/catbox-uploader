"""Main window: owns config + history, connects the tabs and drives uploads / deletes."""

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QMainWindow, QMessageBox, QTableWidgetItem,
                               QTableWidgetSelectionRange, QTabWidget)

from ..core import history_exporter, validators
from ..core.account_id import acct_id, acct_matches
from ..core.config import ConfigStore
from ..core.constants import APP_NAME, MAX_COL_W, MAX_IMPORT_BYTES, MAX_UPLOAD_BYTES, MIN_COL_W
from ..core.helpers import clean_msg, human_size, plural, short_text
from ..core.history_item import HistoryItem, Mode, mode_label, mode_sort_key, sanitize_item
from ..core.queue_item import QueueStatus
from ..net.batch_uploader import BatchJob, BatchUploader
from ..net.delete_worker import DeleteWorker
from .about_tab import AboutTab
from .results_tab import ResultsTab
from .settings_tab import SettingsTab, SettingsValues
from .upload_tab import UploadTab

DOT = "  \u00b7  "


def confirm(parent, title, text, info="", plain=False):
    """Yes / No question; No is the default."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    if plain:
        box.setTextFormat(Qt.TextFormat.PlainText)   # file names are untrusted text
    box.setText(text)
    if info:
        box.setInformativeText(info)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(760, 460)
        self.resize(900, 560)

        self.store = ConfigStore()
        self._startup_notices = self.store.load()

        self.batch = None
        self._batch_mode = Mode.UNKNOWN
        self._batch_acct = ""
        self._batch_ok = 0

        self.delete_worker = None
        self._delete_targets = {}    # shortcode -> history uid
        self._delete_ok = []
        self._delete_errors = []

        self._row_uids = []          # history uid shown in each table row
        self._applying_widths = False
        self._closing = False
        self._confirming_cancel = False

        # One timer restores the window title, one saves column widths (debounced).
        self._title_timer = QTimer(self)
        self._title_timer.setSingleShot(True)
        self._title_timer.setInterval(800)
        self._title_timer.timeout.connect(self._maybe_reset_title)
        self._col_timer = QTimer(self)
        self._col_timer.setSingleShot(True)
        self._col_timer.setInterval(500)
        self._col_timer.timeout.connect(self._flush_col_widths)

        self._build_ui()
        self._connect_signals()
        self._create_shortcuts()

        self._apply_runtime_settings()
        self._refresh_history()
        self._update_history_buttons()

        if self._startup_notices:
            QTimer.singleShot(400, self._show_startup_notices)

    # =================================================================== setup
    @property
    def cfg(self):
        return self.store.cfg

    def _build_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        cfg = self.cfg
        self.upload_tab = UploadTab(check_on_start=cfg.check_on_start)
        self.upload_tab.set_start_dir(cfg.last_dir)
        self.results_tab = ResultsTab()
        self.settings_tab = SettingsTab(cfg.userhash, SettingsValues(
            default_dir=cfg.default_dir, auto_history=cfg.auto_history, check_on_start=cfg.check_on_start))

        self.tabs.addTab(self.upload_tab, "Upload")
        self.tabs.addTab(self.results_tab, "History")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(AboutTab(), "About")
        self.statusBar()   # create it

        # Restore saved column widths, THEN start listening for resizes.
        self._apply_saved_widths()
        for table in self._width_tables().values():
            table.horizontalHeader().sectionResized.connect(
                lambda logical, _old, _new, t=table: self._on_section_resized(t, logical))

    def _connect_signals(self):
        ut, rt, st = self.upload_tab, self.results_tab, self.settings_tab
        ut.upload_requested.connect(self.start_upload)
        ut.cancel_requested.connect(self.cancel_upload)
        ut.uploading_changed.connect(st.set_locked)
        ut.notify.connect(self._on_notify)

        st.userhash_saved.connect(self.save_userhash)
        st.notify.connect(self._on_notify)
        st.setting_changed.connect(self._on_setting_changed)

        rt.copy_requested.connect(self.copy_selected)
        rt.open_requested.connect(self.open_selected)
        rt.remove_requested.connect(self.remove_selected)
        rt.clear_requested.connect(self.clear_history)
        rt.export_requested.connect(self.export_history)
        rt.import_requested.connect(self.import_history)
        rt.delete_from_catbox_requested.connect(self.delete_from_catbox)
        rt.filter_changed.connect(self._refresh_history)
        rt.sort_changed.connect(self._refresh_history)
        rt.selection_changed.connect(self._update_history_buttons)
        # NOTE: double-click on a row is intentionally NOT bound to open the URL.

    def _create_shortcuts(self):
        def add(seq, parent, slot, ctx=Qt.ShortcutContext.WindowShortcut):
            sc = QShortcut(QKeySequence(seq), parent)
            sc.setContext(ctx)
            sc.activated.connect(slot)

        add("Ctrl+O", self, self._browse)
        add("Ctrl+Return", self, self._upload_shortcut)
        add("Ctrl+Enter", self, self._upload_shortcut)
        add("Ctrl+E", self, self.export_history)
        add("Ctrl+I", self, self.import_history)
        add("Ctrl+R", self, self._check_service_safe)
        add("Ctrl+F", self, self._focus_search)
        add("Esc", self, self._escape_pressed)
        add("Ctrl+1", self, lambda: self.tabs.setCurrentIndex(0))
        add("Ctrl+2", self, lambda: self.tabs.setCurrentIndex(1))
        add("Ctrl+3", self, lambda: self.tabs.setCurrentIndex(2))
        add("Ctrl+4", self, lambda: self.tabs.setCurrentIndex(3))
        add("Ctrl+,", self, lambda: self.tabs.setCurrentIndex(2))

        table = self.results_tab.table
        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        add("Ctrl+A", table, self._select_all_history, ctx)
        add("Ctrl+C", table, self.copy_selected, ctx)
        add("Return", table, self.open_selected, ctx)
        add("Enter", table, self.open_selected, ctx)

    def _show_startup_notices(self):
        for msg in self._startup_notices:
            self.show_status(msg, "error", 6000)
        self._startup_notices = []

    # ============================================================== status bar
    def show_status(self, message, kind="info", duration=3000):
        if self._closing:
            return
        if kind == "error":
            duration = max(duration, 6000)
        self.statusBar().showMessage(clean_msg(message, 300), duration)

    def _on_notify(self, message, kind):
        self.show_status(message, kind)

    # =============================================================== settings
    def _apply_runtime_settings(self):
        self.upload_tab.set_fixed_dir(self.cfg.default_dir)

    def _on_setting_changed(self, key, value):
        cfg = self.cfg
        if key == "default_dir":
            cfg.default_dir = value if isinstance(value, str) else ""
        elif key in ("auto_history", "check_on_start"):
            setattr(cfg, key, bool(value))
        else:
            return
        self._apply_runtime_settings()
        self._save_config()

    def _maybe_show_history(self):
        if self.cfg.auto_history:
            self.tabs.setCurrentIndex(1)

    def _focus_userhash(self):
        self.tabs.setCurrentIndex(2)
        self.settings_tab.focus_userhash()

    def _saved_userhash(self):
        return self.cfg.userhash

    # ============================================================ column widths
    def _width_tables(self):
        return {"queue": self.upload_tab.queue_table, "history": self.results_tab.table}

    def _apply_saved_widths(self):
        self._applying_widths = True
        try:
            for key, table in self._width_tables().items():
                widths = self.cfg.col_widths.get(key) or []
                # The last column is never stored (it always stretches).
                for i, w in enumerate(widths[:table.columnCount() - 1]):
                    table.setColumnWidth(i, w)
        finally:
            self._applying_widths = False

    def _on_section_resized(self, table, logical):
        if self._applying_widths or self._closing:
            return
        # The last column stretches automatically; only a user-driven change of the others
        # is worth saving.
        if logical >= table.columnCount() - 1:
            return
        self._col_timer.start()

    def _flush_col_widths(self):
        self._col_timer.stop()
        for key, table in self._width_tables().items():
            self.cfg.col_widths[key] = [
                max(MIN_COL_W, min(MAX_COL_W, int(table.columnWidth(i))))
                for i in range(table.columnCount() - 1)]
        self._save_config(quiet=True)

    # ================================================================== config
    def _save_config(self, quiet=False):
        ok, err = self.store.save()
        if ok:
            return True
        if self.store.save_blocked:
            if not quiet:
                self.show_status("Cannot save: config file is not readable", "error")
        else:
            # A status message instead of a modal box: a dialog opened from a worker slot
            # would run a nested event loop at a bad time.
            self.show_status(f"Cannot save config: {clean_msg(err, 70)}", "error")
        return False

    def save_userhash(self, value):
        if self._busy_uploading():
            self.show_status("Upload in progress", "info")
            return
        value = (value or "").strip()
        if not validators.valid_userhash(value):
            self.show_status("Invalid userhash", "error")
            self.settings_tab.focus_userhash()
            return
        ok, err = self.store.set_userhash(value)
        if not ok:
            self.show_status(f"Cannot save config: {clean_msg(err, 70)}", "error")
            return
        self.settings_tab.set_saved_userhash(value)
        self._update_history_buttons()
        self.show_status("Userhash saved" if value else "Anonymous mode", "info")

    # =================================================================== misc
    def _busy_uploading(self):
        return self.batch is not None

    def _browse(self):
        if self._busy_uploading():
            return
        self.tabs.setCurrentIndex(0)
        self.upload_tab.pick_files()

    def _upload_shortcut(self):
        if self.tabs.currentIndex() == 0:   # only on the Upload tab
            self.upload_tab.emit_upload()

    def _focus_search(self):
        if self.tabs.currentIndex() == 1:
            self.results_tab.search.setFocus()
            self.results_tab.search.selectAll()

    def _check_service_safe(self):
        if not self._busy_uploading():
            self.upload_tab.check_service()

    def _maybe_reset_title(self):
        if not self._closing and not self._busy_uploading():
            self.setWindowTitle(APP_NAME)

    def _escape_pressed(self):
        if self._confirming_cancel or self.batch is None or not self.upload_tab.can_cancel:
            return
        self._confirming_cancel = True
        try:
            info = "Remaining files stay in the list." if self.batch.count > 1 else ""
            yes = confirm(self, "Cancel upload", "Cancel the current upload?", info)
        finally:
            self._confirming_cancel = False
        if yes:
            self.cancel_upload()

    # ================================================================== upload
    def start_upload(self):
        if self._busy_uploading():
            return
        items = [it for it in self.upload_tab.pending_items() if it.path]
        if not items:
            self.show_status("Add at least one file first", "error")
            return
        if self.settings_tab.dirty:
            self.show_status("Press Apply in Settings first", "error")
            self._focus_userhash()
            return

        self.upload_tab.reset_statuses()

        # Validate every file up front so problems show before anything is sent.
        valid, problems = [], 0
        for it in items:
            try:
                size = os.path.getsize(it.path)
            except OSError:
                problems += 1
                self.upload_tab.set_item_status(it.id, QueueStatus.FAILED, "file no longer exists")
                continue
            if size <= 0:
                problems += 1
                self.upload_tab.set_item_status(it.id, QueueStatus.FAILED, "file is empty (0 bytes)")
                continue
            it.size = size
            valid.append(it)
        if problems:
            self.show_status(f"{plural(problems, 'file')} skipped: missing or empty", "error")
        if not valid:
            return

        large = [it for it in valid if it.size > MAX_UPLOAD_BYTES]
        if large:
            box = QMessageBox(self)
            box.setWindowTitle("Large files")
            box.setText(f"{plural(len(large), 'file')} exceed Catbox's limit of about "
                        f"{human_size(MAX_UPLOAD_BYTES)}.")
            b_all = box.addButton("Upload anyway", QMessageBox.ButtonRole.AcceptRole)
            b_skip = box.addButton("Skip large files", QMessageBox.ButtonRole.ActionRole)
            b_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(b_skip)
            box.setEscapeButton(b_cancel)
            box.exec()
            clicked = box.clickedButton()
            if clicked is b_skip:
                valid = [it for it in valid if it.size <= MAX_UPLOAD_BYTES]
                if not valid:
                    return
            elif clicked is not b_all:
                return

        userhash = self._saved_userhash()
        self.cfg.last_dir = str(Path(valid[-1].path).parent)
        self._save_config(quiet=True)

        jobs = [BatchJob(it.id, it.path, it.name, it.size) for it in valid]
        self._batch_mode = Mode.USERHASH if userhash else Mode.ANONYMOUS
        self._batch_acct = acct_id(userhash, self.cfg.acct_salt)
        self._batch_ok = 0

        b = BatchUploader(userhash, jobs, self)
        self.batch = b
        b.item_status.connect(
            lambda id_, st, detail: self.upload_tab.set_item_status(
                id_, st, detail, reveal=(st == QueueStatus.UPLOADING and detail == "0%")))
        b.item_uploaded.connect(self._on_item_uploaded)
        b.item_failed.connect(self._on_item_failed)
        b.progress.connect(self._on_batch_progress)
        b.can_cancel_changed.connect(self.upload_tab.set_can_cancel)
        b.finished.connect(self._on_batch_finished)

        self._title_timer.stop()
        self.setWindowTitle(f"{APP_NAME} - 0%")
        self.upload_tab.update_progress(0, "Starting...")
        self.upload_tab.set_uploading(True)
        if len(valid) == 1:
            self.show_status(f"Uploading {short_text(valid[0].name)}...")
        else:
            self.show_status(f"Uploading {len(valid)} files...")
        b.start()

    def cancel_upload(self):
        if self.batch is not None and self.upload_tab.can_cancel:
            self.batch.cancel()
            self.upload_tab.set_speed_text("Cancelling...")

    def _on_batch_progress(self, overall, speed_text):
        if self._closing:
            return
        self.setWindowTitle(f"{APP_NAME} - {overall}%")
        self.upload_tab.update_progress(overall, speed_text)

    def _on_item_uploaded(self, _id, url, filename, size):
        """A file that exists on the server must never lose its URL just because the app was
        closed a moment later: the history is saved right away."""
        self._batch_ok += 1
        item = sanitize_item({
            "filename": filename, "url": url, "size": int(size),
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": self._batch_mode, "kind": validators.file_kind(filename), "acct": self._batch_acct})
        if item is None:   # cannot happen for a valid URL, but never lose it
            item = HistoryItem(filename=url.rsplit("/", 1)[-1], url=url, size=int(size),
                               mode=self._batch_mode)
        self.cfg.history.insert(0, item)
        self._save_config()

        self.results_tab.search.blockSignals(True)
        self.results_tab.search.clear()
        self.results_tab.search.blockSignals(False)
        self._refresh_history()

        count = self.batch.count if self.batch is not None else 1
        if count > 1:
            self.show_status(f"Uploaded {self._batch_ok}/{count}  \u00b7  {short_text(filename, 32)}")

    def _on_item_failed(self, _id, name, message):
        if self._closing:
            return
        self.upload_tab.set_speed_text("Failed")
        label = f"{short_text(name, 28)}: " if name else ""
        self.show_status(f"Upload failed: {label}{message}", "error")

    def _on_batch_finished(self, s):
        if self.batch is not None:
            self.batch.deleteLater()
        self.batch = None
        self.upload_tab.set_uploading(False)
        if self._closing:
            return

        # Uploaded files leave the queue (no accidental re-upload).
        self.upload_tab.remove_items(s.done_ids)

        up = self.upload_tab
        if s.cancelled:
            up.set_speed_text("Cancelled")
            if not s.ok:
                up.reset_progress()
            self.show_status(f"Cancelled  \u00b7  {s.ok} of {s.total} uploaded")
        elif s.fail == 0:
            up.update_progress(100, f"Done: {plural(s.ok, 'file')}, {human_size(s.ok_bytes)}")
            self.show_status("Uploaded" if s.total == 1 else f"Uploaded {s.total} files")
            self._maybe_show_history()
        else:
            if s.ok:
                up.update_progress(100, f"{s.ok} done, {s.fail} failed")
                self._maybe_show_history()
            else:
                up.set_speed_text("Failed")
                up.reset_progress()
            if s.total > 1:
                self.show_status(f"{s.ok} uploaded \u00b7 {s.fail} failed", "info" if s.ok else "error")
        self._title_timer.start()

    # ================================================================== delete
    def _delete_eligibility(self, items):
        """Split a selection into deletable (item, shortcode) pairs + skip counts."""
        userhash = self._saved_userhash()
        salt = self.cfg.acct_salt
        skip = {"anon": 0, "acct": 0, "bad": 0}
        eligible = []
        for it in items:
            if it.mode == Mode.ANONYMOUS:
                skip["anon"] += 1
                continue
            if userhash and not acct_matches(it.acct, userhash, salt):
                skip["acct"] += 1
                continue
            short = validators.shortcode_from_url(it.url)
            if not short:
                skip["bad"] += 1
                continue
            eligible.append((it, short))
        if not userhash:
            eligible = []
        return eligible, skip

    def delete_from_catbox(self):
        if self.delete_worker is not None:
            return
        items = self._selected_items()
        if not items:
            return
        eligible, skip = self._delete_eligibility(items)
        userhash = self._saved_userhash()

        if not userhash and skip["anon"] < len(items):
            self.show_status("Set a userhash first", "error")
            self._focus_userhash()
            return
        if not eligible:
            if skip["anon"]:
                msg = "Uploaded anonymously, cannot delete"
            elif skip["acct"]:
                msg = "Uploaded with a different userhash, cannot delete"
            else:
                msg = "No valid file URL"
            self.show_status(msg, "error")
            return

        n = len(eligible)
        if n == 1:
            it, short = eligible[0]
            info = f"{it.filename}{DOT}{short}"
        else:
            info = "\n".join(short_text(it.filename, 60) for it, _ in eligible[:5])
            if n > 5:
                info += f"\n...and {n - 5} more"
        skipped = sum(skip.values())
        if skipped:
            info += f"\n\n{plural(skipped, 'selected file')} will be skipped (anonymous, other userhash or no URL)."
        info += "\n\nThis cannot be undone."

        text = ("Permanently delete this file from catbox.moe?" if n == 1
                else f"Permanently delete {n} files from catbox.moe?")
        if not confirm(self, "Delete from Catbox", text, info, plain=True):
            return

        self.show_status(f"Deleting {plural(n, 'file')}...")
        w = DeleteWorker(userhash, [s for _, s in eligible])
        w.deleted.connect(self._on_file_deleted)
        w.delete_failed.connect(self._on_file_delete_failed)
        w.done.connect(self._on_delete_worker_done)
        self._delete_targets = {s: it.uid for it, s in eligible}
        self._delete_ok, self._delete_errors = [], []
        self.delete_worker = w
        self._update_history_buttons()
        w.start()

    def _on_file_deleted(self, shortcode):
        if not self._closing and shortcode in self._delete_targets:
            self._delete_ok.append(self._delete_targets[shortcode])

    def _on_file_delete_failed(self, _shortcode, message):
        if not self._closing:
            self._delete_errors.append(message)

    def _on_delete_worker_done(self):
        w, self.delete_worker = self.delete_worker, None
        if w is not None:
            w.release()
        ok_uids, errors = self._delete_ok, self._delete_errors
        self._delete_targets, self._delete_ok, self._delete_errors = {}, [], []
        if self._closing:
            return

        first_name = ""
        if ok_uids:
            for h in self.cfg.history:
                if h.uid == ok_uids[0]:
                    first_name = short_text(h.filename, 40)
                    break
            self._remove_history_uids(set(ok_uids))
        else:
            self._update_history_buttons()

        nok, nfail = len(ok_uids), len(errors)
        if nok and not nfail:
            self.show_status(f"Deleted from catbox  {first_name}" if nok == 1
                             else f"Deleted {nok} files from catbox")
        elif nok and nfail:
            self.show_status(f"{nok} deleted \u00b7 {nfail} failed: {short_text(errors[0], 40)}")
        elif nfail:
            self.show_status(f"Delete failed: {errors[0]}" if nfail == 1
                             else f"Delete failed ({nfail} files): {short_text(errors[0], 40)}", "error")

    def _remove_history_uids(self, uids):
        self.cfg.history = [h for h in self.cfg.history if h.uid not in uids]
        self._save_config()
        self._refresh_history()

    # ============================================================ history table
    def _sort_key(self, col):
        return {
            0: lambda it: it.filename.lower(),
            1: lambda it: it.url.lower(),
            2: lambda it: it.kind,
            3: lambda it: mode_sort_key(it.mode),
            4: lambda it: it.size,
        }.get(col, lambda it: it.ts)

    def _refresh_history(self):
        rt = self.results_tab
        table = rt.table

        # Selection is tracked by uid (not by row), so it survives inserts, removals,
        # imports and re-sorting.
        prev = {h.uid for h in self._selected_items()}
        prev_scroll = table.verticalScrollBar().value()

        table.setUpdatesEnabled(False)
        table.setRowCount(0)
        self._row_uids = []

        q = rt.search.text().strip().lower()
        items = list(self.cfg.history)
        if q:
            items = [it for it in items
                     if q in it.filename.lower() or q in it.url.lower() or q in it.ts.lower()
                     or q in it.mode or q in it.kind.lower() or q in mode_label(it.mode)]
        items.sort(key=self._sort_key(rt.sort_col), reverse=not rt.sort_asc)

        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for it in items:
            r = table.rowCount()
            table.insertRow(r)
            self._row_uids.append(it.uid)
            size = QTableWidgetItem(human_size(it.size))
            size.setTextAlignment(right)
            for c, cell in enumerate([QTableWidgetItem(it.filename), QTableWidgetItem(it.url),
                                      QTableWidgetItem(it.kind), QTableWidgetItem(mode_label(it.mode)),
                                      size, QTableWidgetItem(it.ts)]):
                table.setItem(r, c, cell)
        table.setUpdatesEnabled(True)

        # Restore the whole selection (multi-select aware) + scroll position.
        if prev:
            last_col = table.columnCount() - 1
            table.blockSignals(True)
            try:
                for r, uid in enumerate(self._row_uids):
                    if uid in prev:
                        table.setRangeSelected(QTableWidgetSelectionRange(r, 0, r, last_col), True)
            finally:
                table.blockSignals(False)
        table.verticalScrollBar().setValue(prev_scroll)
        self._update_history_buttons()   # also refreshes the counter

    def _update_count(self):
        rt = self.results_tab
        total = len(self.cfg.history)
        total_bytes = sum(h.size for h in self.cfg.history)
        sel = len(self._selected_items())
        sel_part = f"{sel} selected{DOT}" if sel > 1 else ""
        if rt.search.text().strip():
            rt.hist_count.setText(f"{sel_part}{rt.table.rowCount()} / {total}{DOT}{human_size(total_bytes)}")
        elif total == 0:
            rt.hist_count.setText("")
        else:
            rt.hist_count.setText(f"{sel_part}{plural(total, 'item')}{DOT}{human_size(total_bytes)}")

    def _update_history_buttons(self):
        items = self._selected_items()
        n = len(items)
        eligible, _skip = self._delete_eligibility(items)
        n_del = len(eligible)
        has_history = bool(self.cfg.history)

        rt = self.results_tab
        rt.copy_btn.setEnabled(n > 0)
        rt.open_btn.setEnabled(n > 0)
        rt.remove_btn.setEnabled(n > 0)
        rt.delete_btn.setEnabled(n_del > 0 and self.delete_worker is None)
        rt.export_btn.setEnabled(has_history)
        rt.clear_btn.setEnabled(has_history)

        rt.copy_btn.setText("Copy URL" if n <= 1 else f"Copy {n} URLs")
        rt.open_btn.setText("Open" if n <= 1 else f"Open {n}")
        rt.remove_btn.setText("Remove" if n <= 1 else f"Remove {n}")
        rt.delete_btn.setText("Delete from Catbox" if n_del <= 1 else f"Delete {n_del} from Catbox")
        self._update_count()

    def _selected_items(self):
        """History entries of all selected rows, in the order they are shown."""
        rt = getattr(self, "results_tab", None)
        if rt is None:
            return []
        sm = rt.table.selectionModel()
        if sm is None:
            return []
        by_uid = {h.uid: h for h in self.cfg.history}
        rows = sorted({i.row() for i in sm.selectedRows()})
        return [by_uid[self._row_uids[r]] for r in rows
                if 0 <= r < len(self._row_uids) and self._row_uids[r] in by_uid]

    def _select_all_history(self):
        table = self.results_tab.table
        if table.rowCount():
            table.selectAll()

    def copy_selected(self):
        items = self._selected_items()
        if not items:
            self.show_status("Select a row first")
            return
        urls = [it.url for it in items if it.url]
        if not urls:
            self.show_status("No valid URL", "error")
            return
        QApplication.clipboard().setText("\n".join(urls))
        self.show_status("Copied to clipboard" if len(urls) == 1 else f"Copied {len(urls)} URLs to clipboard")

    def open_selected(self):
        items = self._selected_items()
        if not items:
            self.show_status("Select a row first")
            return
        urls = [it.url.strip() for it in items if validators.is_catbox_file_url(it.url.strip())]
        if not urls:
            self.show_status("No valid URL", "error")
            return
        if len(urls) > 5 and not confirm(self, "Open in browser", f"Open {len(urls)} files in your browser?"):
            return
        for u in urls:
            QDesktopServices.openUrl(QUrl(u))

    def remove_selected(self):
        items = self._selected_items()
        if not items:
            return
        if len(items) > 1 and not confirm(self, "Remove from history",
                                          f"Remove {len(items)} records from your local history?"):
            return
        self._remove_history_uids({it.uid for it in items})
        self.show_status("Removed")

    def clear_history(self):
        if not self.cfg.history:
            return
        count = len(self.cfg.history)
        if confirm(self, "Clear history", f"Delete {count} upload records?"):
            self.cfg.history = []
            self._save_config()
            self._refresh_history()
            self.show_status(f"Cleared {count} records")

    # ============================================================ import/export
    def import_history(self):
        start_dir = self.cfg.last_dir or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Import history", start_dir,
                                              "JSON (*.json);;All files (*)")
        if not path:
            return
        try:
            if os.path.getsize(path) > MAX_IMPORT_BYTES:
                self.show_status("Import failed: file is too large", "error")
                return
            data = Path(path).read_bytes()
        except OSError as e:
            self.show_status(f"Import failed: {e.__class__.__name__}", "error")
            return

        res = history_exporter.parse_import(data)
        if res.error:
            self.show_status(f"Import failed: {res.error}", "error")
            return

        known = {it.url for it in self.cfg.history}
        fresh, dup = [], 0
        for it in res.items:
            if it.url in known:
                dup += 1
                continue
            known.add(it.url)
            fresh.append(it)
        if not fresh:
            self.show_status(f"Nothing to import{DOT}{dup} duplicate, {res.invalid} invalid")
            return

        old = self.cfg.history
        merged = old + fresh
        merged.sort(key=lambda it: it.ts, reverse=True)   # newest first
        self.cfg.history = merged
        if not self._save_config():
            self.cfg.history = old
            return
        self._refresh_history()
        self.tabs.setCurrentIndex(1)
        extra = ""
        if dup:
            extra += f"{DOT}{dup} duplicate skipped"
        if res.invalid:
            extra += f"{DOT}{res.invalid} invalid skipped"
        self.show_status(f"Imported {len(fresh)} {'entry' if len(fresh) == 1 else 'entries'}{extra}")

    def export_history(self):
        if not self.cfg.history:
            return
        default = str(Path.home() / f"catbox_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        path, selected = QFileDialog.getSaveFileName(
            self, "Export history", default, "JSON (*.json);;CSV (*.csv);;Plain text (*.txt)")
        if not path:
            return
        ext = validators.extension_of(path)
        if ext not in (".json", ".csv", ".txt"):
            sf = (selected or "").lower()
            ext = ".csv" if "csv" in sf else ".txt" if "txt" in sf else ".json"
            path += ext
        try:
            history_exporter.export_to_file(path, history_exporter.format_from_extension(ext), self.cfg.history)
        except Exception as e:
            self.show_status(f"Export failed: {clean_msg(e, 70)}", "error")
            return
        self.show_status(f"Exported {len(self.cfg.history)} entries")

    # =================================================================== close
    def closeEvent(self, e):
        if self.delete_worker is not None:
            if not confirm(self, "Quit", "A delete from catbox.moe is still running. Quit anyway?"):
                e.ignore()
                return
        if self.batch is not None:
            cancellable = self.upload_tab.can_cancel
            text = ("An upload is in progress. Cancel and quit?" if cancellable
                    else "The server is still processing the upload. Quit anyway?")
            if not confirm(self, "Quit", text):
                e.ignore()
                return

        # Persist the column widths (also if the debounce timer is still pending).
        try:
            self._flush_col_widths()
        except Exception:
            pass
        self._closing = True

        # The dialogs above run a nested event loop, so re-read the state afterwards.
        if self.batch is not None:
            self.batch.abort_now()
            self.batch = None
        if self.delete_worker is not None:
            self.delete_worker.detach()
        self.upload_tab.shutdown()

        # Unsaved userhash edits are intentionally discarded (no silent saves).
        super().closeEvent(e)
