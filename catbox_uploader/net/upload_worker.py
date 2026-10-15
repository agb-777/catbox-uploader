"""Uploads ONE file to catbox.moe (streamed from disk, cancellable)."""

import errno
import os
import stat
import time

import requests
from PySide6.QtCore import Signal
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

from ..core.constants import (API_URL, CONNECT_TIMEOUT, HTTP_HEADERS, UPLOAD_READ_TIMEOUT)
from ..core.helpers import clean_msg
from ..core.validators import is_catbox_file_url
from .http_common import read_text_limited
from .threaded_worker import ThreadedWorker


class UploadCancelled(BaseException):
    pass


class UploadWorker(ThreadedWorker):
    progress = Signal(int, object, object)      # pct, bytes_sent, total (64-bit safe)
    finished_ok = Signal(str, str, object)      # url, filename, size
    failed = Signal(str)
    cancelled = Signal()
    _SIGNALS = ("done", "progress", "finished_ok", "failed", "cancelled")

    def __init__(self, filepath, userhash, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.userhash = userhash
        self._cancel = False
        self._body_sent = False

    @property
    def can_cancel(self):
        return not self._body_sent

    def cancel(self):
        """Too late once the whole body is out: the file is (or will be) on the server."""
        if self._body_sent:
            return False
        self._cancel = True
        return True

    def on_crash(self, message):
        self._emit(self.failed, clean_msg(message))

    def _open_checked(self):
        """Open the queued file safely. Returns (file object, size), or None after reporting why not.

        The queue only holds resolved, regular files, but the path could have been swapped for a
        symlink (to some other file of the user) or a FIFO since then. O_NOFOLLOW refuses a
        symlink, O_NONBLOCK keeps a FIFO from blocking the open, and the size comes from the very
        descriptor that will be read (no check-then-open race).
        """
        flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                 | getattr(os, "O_CLOEXEC", 0))
        try:
            fd = os.open(self.filepath, flags)
        except OSError as e:
            if e.errno in (errno.ELOOP, getattr(errno, "EMLINK", -1)):
                self._emit(self.failed, "File was replaced by a symbolic link; refusing to follow it.")
            else:
                self._emit(self.failed, f"Cannot read file: {clean_msg(e)}")
            return None
        try:
            fh = os.fdopen(fd, "rb")
        except OSError as e:
            os.close(fd)
            self._emit(self.failed, f"Cannot read file: {clean_msg(e)}")
            return None
        try:
            st = os.fstat(fh.fileno())
        except OSError as e:
            fh.close()
            self._emit(self.failed, f"Cannot read file: {clean_msg(e)}")
            return None
        if not stat.S_ISREG(st.st_mode):
            fh.close()
            self._emit(self.failed, "Not a regular file.")
            return None
        if st.st_size <= 0:
            fh.close()
            self._emit(self.failed, "File is empty.")
            return None
        try:
            os.set_blocking(fh.fileno(), True)   # O_NONBLOCK was only meant for the open itself
        except (OSError, ValueError, AttributeError):
            pass
        return fh, st.st_size

    def run_task(self):
        filename = os.path.basename(self.filepath)
        opened = self._open_checked()
        if opened is None:
            return
        fh, size = opened

        session = requests.Session()
        try:
            with fh:
                fields = {
                    "reqtype": "fileupload",
                    "fileToUpload": (filename, fh, "application/octet-stream"),
                }
                if self.userhash:
                    fields["userhash"] = self.userhash

                encoder = MultipartEncoder(fields=fields)
                last_emit = [0.0]
                final_sent = [False]

                def cb(monitor):
                    done_sending = monitor.bytes_read >= monitor.len
                    # Once the whole body is out we can no longer abort cleanly.
                    if self._cancel and not done_sending:
                        raise UploadCancelled()
                    if done_sending:
                        self._body_sent = True
                        if final_sent[0]:
                            return
                        final_sent[0] = True
                    now = time.monotonic()
                    if not done_sending and now - last_emit[0] < 0.05:
                        return
                    last_emit[0] = now
                    pct = int(monitor.bytes_read * 100 / max(monitor.len, 1))
                    self._emit(self.progress, pct, monitor.bytes_read, monitor.len)

                monitor = MultipartEncoderMonitor(encoder, cb)

                # TLS verification stays ON (requests default). Redirects are refused so the
                # request body (which carries the userhash) can never be replayed elsewhere.
                r = session.post(
                    API_URL,
                    data=monitor,
                    headers={"Content-Type": monitor.content_type, **HTTP_HEADERS},
                    timeout=(CONNECT_TIMEOUT, UPLOAD_READ_TIMEOUT),
                    allow_redirects=False,
                    stream=True,
                )

            status = r.status_code
            reason = r.reason or ""
            text = read_text_limited(r)

            if 300 <= status < 400:
                self._emit(self.failed, f"Unexpected redirect (HTTP {status}); upload aborted for safety.")
                return
            if status >= 400:
                self._emit(self.failed, clean_msg(text) or clean_msg(f"HTTP {status} {reason}"))
                return

            # A valid URL means the upload succeeded -- never lose a URL for a file that exists.
            if is_catbox_file_url(text):
                self._emit(self.finished_ok, text, filename, size)
                return
            self._emit(self.failed, clean_msg(text) or "Empty response from server.")

        except UploadCancelled:
            self._emit(self.cancelled)
        except requests.exceptions.ConnectTimeout:
            self._emit(self.failed, "Could not connect: timed out.")
        except requests.exceptions.ReadTimeout:
            self._emit(self.failed, "Server did not reply in time. The file may still have been "
                                    "uploaded; check before retrying.")
        except requests.exceptions.ConnectionError as e:
            self._emit(self.failed, f"Connection error: {clean_msg(e)}")
        except requests.exceptions.RequestException as e:
            self._emit(self.failed, f"Network error: {clean_msg(e)}")
        except Exception as e:
            self._emit(self.failed, clean_msg(e) or e.__class__.__name__)
        finally:
            try:
                session.close()
            except Exception:
                pass
