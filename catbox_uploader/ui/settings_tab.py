"""'Settings' tab. Controls only STAGE changes until the user presses Apply."""

import os
from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout, QWidget)


@dataclass
class SettingsValues:
    default_dir: str = ""
    auto_history: bool = True
    check_on_start: bool = True


class SettingsTab(QWidget):
    userhash_saved = Signal(str)
    notify = Signal(str, str)                 # message, kind
    setting_changed = Signal(str, object)     # config key, new value

    def __init__(self, saved_userhash, values, parent=None):
        super().__init__(parent)
        self._saved = saved_userhash or ""
        self._locked = False
        self._applied_dir = values.default_dir
        self._applied_checks = {"auto_history": values.auto_history,
                                "check_on_start": values.check_on_start}
        self._checks = {}

        root = QVBoxLayout(self)

        # ---- Account ----
        account = QGroupBox("Account")
        form = QFormLayout(account)
        row = QHBoxLayout()
        self.userhash_input = QLineEdit(self._saved)
        self.userhash_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.userhash_input.setMaxLength(128)
        self.userhash_input.textChanged.connect(lambda _t: self._refresh_controls())
        self.userhash_input.returnPressed.connect(self.apply)
        row.addWidget(self.userhash_input, 1)
        self.reveal_btn = QPushButton("Show")
        self.reveal_btn.setCheckable(True)
        self.reveal_btn.toggled.connect(self._on_reveal_toggled)
        row.addWidget(self.reveal_btn)
        form.addRow("Userhash:", row)
        root.addWidget(account)

        # ---- Upload ----
        upload = QGroupBox("Upload")
        uform = QFormLayout(upload)
        row = QHBoxLayout()
        self.dir_input = QLineEdit(values.default_dir)
        self.dir_input.setReadOnly(True)
        row.addWidget(self.dir_input, 1)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_dir)
        row.addWidget(browse)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_dir)
        row.addWidget(clear)
        uform.addRow("Default folder:", row)

        for key, text, value in (("auto_history", "Open History after upload", values.auto_history),
                                 ("check_on_start", "Check catbox.moe on startup", values.check_on_start)):
            chk = QCheckBox(text)
            chk.setChecked(value)
            chk.toggled.connect(lambda _v: self._refresh_controls())
            self._checks[key] = chk
            uform.addRow("", chk)
        root.addWidget(upload)

        root.addStretch(1)

        # ---- Apply bar ----
        bar = QHBoxLayout()
        bar.addStretch()
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.clicked.connect(self.discard)
        bar.addWidget(self.discard_btn)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self.apply)
        bar.addWidget(self.apply_btn)
        root.addLayout(bar)

        self._refresh_controls()

    # ---------- state ----------
    @property
    def dirty(self):
        """The userhash field differs from the saved value."""
        return self.userhash_input.text().strip() != self._saved

    def _pending_changes(self):
        """Staged settings (not the userhash) that differ from the applied values."""
        changes = {}
        for key, chk in self._checks.items():
            if chk.isChecked() != self._applied_checks[key]:
                changes[key] = chk.isChecked()
        if self.dir_input.text() != self._applied_dir:
            changes["default_dir"] = self.dir_input.text()
        return changes

    def _refresh_controls(self):
        self.userhash_input.setEnabled(not self._locked)
        self.reveal_btn.setEnabled(not self._locked)
        any_change = bool(self._pending_changes()) or (self.dirty and not self._locked)
        self.apply_btn.setEnabled(any_change)
        self.discard_btn.setEnabled(any_change)

    def apply(self):
        changes = self._pending_changes()
        userhash_pending = self.dirty and not self._locked
        if not changes and not userhash_pending:
            return
        for key, value in changes.items():
            if key == "default_dir":
                self._applied_dir = value
            else:
                self._applied_checks[key] = value
            self.setting_changed.emit(key, value)
        if userhash_pending:
            # MainWindow validates/saves it and calls set_saved_userhash() when it really worked.
            self.userhash_saved.emit(self.userhash_input.text().strip())
        else:
            self.notify.emit("Saved", "info")
        self._refresh_controls()

    def discard(self):
        for key, chk in self._checks.items():
            chk.blockSignals(True)
            chk.setChecked(self._applied_checks[key])
            chk.blockSignals(False)
        self.dir_input.setText(self._applied_dir)
        self.userhash_input.setText(self._saved)
        self._refresh_controls()

    def set_saved_userhash(self, value):
        self._saved = value
        self._refresh_controls()

    def set_locked(self, locked):
        self._locked = bool(locked)
        self._refresh_controls()

    def focus_userhash(self):
        self.userhash_input.setFocus()
        self.userhash_input.selectAll()

    def _on_reveal_toggled(self, checked):
        self.userhash_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.reveal_btn.setText("Hide" if checked else "Show")

    def _browse_dir(self):
        start = self.dir_input.text()
        if not start or not os.path.isdir(start):
            start = os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Default folder", start)
        if path:
            self.dir_input.setText(path)
            self._refresh_controls()

    def _clear_dir(self):
        self.dir_input.clear()
        self._refresh_controls()
