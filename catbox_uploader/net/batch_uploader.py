"""Uploads a list of files ONE AFTER ANOTHER and reports everything as signals.

It knows nothing about widgets: the UI (MainWindow) connects to the signals.
"""

import os
import time
import warnings
from dataclasses import dataclass, field
from functools import partial

from PySide6.QtCore import QObject, QTimer, Signal

from ..core.constants import CANCEL_GRACE_MS
from ..core.helpers import human_eta, human_size, human_speed
from ..core.queue_item import QueueStatus
from .upload_worker import UploadWorker


@dataclass
class BatchJob:
    id: int          # QueueItem.id
    path: str
    name: str
    size: int


@dataclass
class BatchSummary:
    total: int = 0
    ok: int = 0
    fail: int = 0
    cancelled: bool = False
    ok_bytes: int = 0
    done_ids: list = field(default_factory=list)   # jobs that were uploaded (they leave the queue)


class BatchUploader(QObject):
    item_status = Signal(int, object, str)             # id, QueueStatus, detail
    item_uploaded = Signal(int, str, str, object)      # id, url, filename, size
    item_failed = Signal(int, str, str)                # id, name, message
    progress = Signal(int, object)                     # overall pct, speed text (None = unchanged)
    can_cancel_changed = Signal(bool)
    finished = Signal(object)                          # BatchSummary

    def __init__(self, userhash, jobs, parent=None):
        super().__init__(parent)
        self._userhash = userhash
        self._jobs = list(jobs)
        self._index = -1
        self._worker = None
        self._running = False
        self._cancelled = False
        self._aborted = False
        self._can_cancel = False

        self._total_bytes = sum(j.size for j in self._jobs)
        self._done_bytes = 0
        self._done_ids = []
        self._ok_bytes = 0
        self._ok = 0
        self._fail = 0

        self._last_bytes = 0
        self._last_tick = 0.0
        self._speed = None

    @property
    def count(self):
        return len(self._jobs)

    @property
    def can_cancel(self):
        return self._can_cancel

    def start(self):
        if self._running:
            return
        self._running = True
        self._start_next()

    def _set_can_cancel(self, value):
        if self._can_cancel == value:
            return
        self._can_cancel = value
        self.can_cancel_changed.emit(value)

    def cancel(self):
        """Stops after (or aborts) the current file."""
        if not self._running or not self._can_cancel or self._worker is None:
            return
        self._cancelled = True
        worker = self._worker
        if worker.cancel():
            # A completely stalled connection never reaches the cancel check, so give up on
            # the worker after a short grace period.
            QTimer.singleShot(CANCEL_GRACE_MS, partial(self._force_cancel, worker))

    def _force_cancel(self, worker):
        if self._aborted or self._worker is not worker:
            return   # it already finished
        worker.detach()   # the cancel flag stays set: the thread stops once the transfer moves
        self._worker = None
        job = self._current()
        if job is not None:
            self.item_status.emit(job.id, QueueStatus.CANCELLED, "")
            self._done_bytes += job.size
        self._start_next()

    def abort_now(self):
        """Window closing: stop everything and emit nothing more."""
        self._aborted = True
        self._cancelled = True
        self._running = False
        if self._worker is not None:
            self._worker.detach()
            self._worker.cancel()
            self._worker = None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for sig in (self.item_status, self.item_uploaded, self.item_failed, self.progress,
                        self.can_cancel_changed, self.finished):
                try:
                    sig.disconnect()
                except (RuntimeError, TypeError):
                    pass   # nothing connected: keep going with the others

    # ---------- flow ----------
    def _start_next(self):
        if not self._running or self._worker is not None:
            return
        if self._aborted or self._cancelled:
            self._finish()
            return

        self._index += 1
        if self._index >= len(self._jobs):
            self._finish()
            return
        job = self._jobs[self._index]

        if not os.path.isfile(job.path):
            self.item_status.emit(job.id, QueueStatus.FAILED, "file no longer exists")
            self.item_failed.emit(job.id, job.name, "file no longer exists")
            self._fail += 1
            self._done_bytes += job.size
            QTimer.singleShot(0, self._start_next)
            return

        self._last_bytes = 0
        self._last_tick = time.monotonic()
        self._speed = None

        self._set_can_cancel(True)
        self.item_status.emit(job.id, QueueStatus.UPLOADING, "0%")

        w = UploadWorker(job.path, self._userhash)
        w.progress.connect(self._on_progress)
        w.finished_ok.connect(self._on_ok)
        w.failed.connect(self._on_fail)
        w.cancelled.connect(self._on_cancelled)
        w.done.connect(self._on_worker_done)
        self._worker = w
        w.start()

    def _current(self):
        if 0 <= self._index < len(self._jobs):
            return self._jobs[self._index]
        return None

    def _on_progress(self, pct, sent, total):
        job = self._current()
        if self._aborted or job is None:
            return
        cur = min(int(sent), job.size)
        done = self._done_bytes + cur
        overall = min(100, int(done * 100 / max(self._total_bytes, 1)))
        prefix = f"{self._index + 1}/{len(self._jobs)}  \u00b7  " if len(self._jobs) > 1 else ""

        if total and sent >= total:
            self._set_can_cancel(False)   # the whole body is out: the server is working on it
            self.item_status.emit(job.id, QueueStatus.PROCESSING, "")
            self.progress.emit(overall, f"{prefix}Waiting for server...")
            return

        self.item_status.emit(job.id, QueueStatus.UPLOADING, f"{pct}%")

        now = time.monotonic()
        dt = now - self._last_tick
        speed_text = None   # None = unchanged
        if dt >= 0.4 and sent > self._last_bytes:
            inst = (sent - self._last_bytes) / dt
            self._speed = inst if self._speed is None else 0.3 * inst + 0.7 * self._speed
            remaining = max(self._total_bytes - done, 0)
            eta = human_eta(remaining / self._speed) if self._speed > 0 else ""
            eta_part = f"  \u00b7  ETA {eta}" if eta else ""
            speed_text = (f"{prefix}{human_speed(self._speed)}  \u00b7  "
                          f"{human_size(done)} / {human_size(self._total_bytes)}{eta_part}")
            self._last_bytes = sent
            self._last_tick = now
        self.progress.emit(overall, speed_text)

    def _on_ok(self, url, filename, size):
        job = self._current()
        if self._aborted or job is None:
            return
        self._ok += 1
        self._ok_bytes += job.size
        self._done_ids.append(job.id)
        self.item_status.emit(job.id, QueueStatus.DONE, "")
        self.item_uploaded.emit(job.id, url, filename, size)

    def _on_fail(self, message):
        job = self._current()
        if self._aborted or job is None:
            return
        self._fail += 1
        self.item_status.emit(job.id, QueueStatus.FAILED, message)
        self.item_failed.emit(job.id, job.name, message)

    def _on_cancelled(self):
        job = self._current()
        if self._aborted or job is None:
            return
        self._cancelled = True
        self.item_status.emit(job.id, QueueStatus.CANCELLED, "")

    def _on_worker_done(self):
        w = self._worker
        self._worker = None
        if w is not None:
            w.release()
        if self._aborted:
            return
        job = self._current()
        if job is not None:
            self._done_bytes += job.size
        QTimer.singleShot(0, self._start_next)

    def _finish(self):
        if not self._running:
            return
        self._running = False
        self._set_can_cancel(False)
        self.finished.emit(BatchSummary(
            total=len(self._jobs), ok=self._ok, fail=self._fail, cancelled=self._cancelled,
            ok_bytes=self._ok_bytes, done_ids=list(self._done_ids)))
