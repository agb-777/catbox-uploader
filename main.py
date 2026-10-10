"""Catbox Uploader: entry point."""

import os
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from catbox_uploader.core.constants import APP_NAME, APP_VERSION, DESKTOP_FILE_NAME, LOCK_FILE
from catbox_uploader.net.threaded_worker import LIVE_WORKERS
from catbox_uploader.ui import app_icon
from catbox_uploader.ui.main_window import MainWindow
from catbox_uploader.ui.theme import apply_light_theme


def acquire_instance_lock():
    """Two running copies would overwrite each other's config and history.

    Returns (lock, ok). ok is False only when ANOTHER copy really holds the lock; any other
    problem (for example a read-only home) never blocks startup.
    """
    lock = QLockFile(str(LOCK_FILE))
    lock.setStaleLockTime(0)   # only a dead owner makes a lock stale
    if lock.tryLock(0):
        return lock, True
    return lock, lock.error() != QLockFile.LockError.LockFailedError


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("CatboxUploader")
    # Wayland: the window is matched to catbox-uploader.desktop (icon, taskbar entry) by this name.
    QGuiApplication.setDesktopFileName(DESKTOP_FILE_NAME)
    app.setWindowIcon(app_icon.icon())
    apply_light_theme(app)

    lock, ok = acquire_instance_lock()
    if not ok:
        QMessageBox.information(None, APP_NAME, "Already running.")
        return 0

    window = MainWindow()
    window.show()
    code = app.exec()
    lock.unlock()

    sys.stdout.flush()
    sys.stderr.flush()
    if LIVE_WORKERS:
        # A network call is still blocked in a daemon thread; don't wait for it.
        os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())
