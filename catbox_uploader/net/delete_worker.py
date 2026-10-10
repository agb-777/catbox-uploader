"""Deletes one or more files from catbox.moe (one request per file, reported one by one)."""

import requests
from PySide6.QtCore import Signal

from ..core.constants import API_URL, CONNECT_TIMEOUT, DELETE_READ_TIMEOUT, HTTP_HEADERS
from ..core.helpers import clean_msg
from .http_common import read_text_limited
from .threaded_worker import ThreadedWorker


def classify_delete_response(status, raw_text):
    """Interpret the server reply of a delete request. Returns (ok, message)."""
    raw = clean_msg(raw_text)
    text = raw.lower()

    if 300 <= status < 400:
        return False, f"Unexpected redirect (HTTP {status}); delete aborted."
    if status >= 400:
        return False, raw or f"HTTP {status}"
    if not text:
        return False, "Empty response from server; file may not be deleted."

    # Failure markers are checked first so e.g. "unsuccessful" is never mistaken for success.
    if "userhash" in text or "permission" in text or "unauthorized" in text:
        return False, "Invalid userhash or permission denied."
    if ("not found" in text or "no such" in text or "doesn't exist" in text
            or "does not exist" in text or "invalid" in text):
        return False, "File not found on catbox (may already be deleted)."
    if "unsuccess" in text or "not success" in text or "fail" in text or "error" in text:
        return False, f"Server: {raw}"
    if text.startswith("ok") or "success" in text:
        return True, ""
    return False, f"Server: {raw}"


class DeleteWorker(ThreadedWorker):
    deleted = Signal(str)               # shortcode
    delete_failed = Signal(str, str)    # shortcode, message
    _SIGNALS = ("done", "deleted", "delete_failed")

    def __init__(self, userhash, shortcodes, parent=None):
        super().__init__(parent)
        self.userhash = userhash
        self.shortcodes = list(shortcodes)
        self._reported = set()

    def _report(self, shortcode, ok, msg=""):
        self._reported.add(shortcode)
        if ok:
            self._emit(self.deleted, shortcode)
        else:
            self._emit(self.delete_failed, shortcode, msg)

    def on_crash(self, message):
        for sc in self.shortcodes:   # every file that was not reported yet counts as failed
            if sc not in self._reported:
                self._report(sc, False, clean_msg(message))

    def run_task(self):
        if not self.userhash:
            for sc in self.shortcodes:
                self._report(sc, False, "No userhash set. Cannot delete.")
            return
        for sc in self.shortcodes:
            if not sc:
                self._report(sc, False, "No file shortcode.")
                continue
            ok, msg = self._delete_one(sc)
            self._report(sc, ok, msg)

    def _delete_one(self, shortcode):
        try:
            r = requests.post(
                API_URL,
                data={"reqtype": "deletefiles", "userhash": self.userhash, "files": shortcode},
                headers=HTTP_HEADERS,
                timeout=(CONNECT_TIMEOUT, DELETE_READ_TIMEOUT),
                allow_redirects=False,
                stream=True,
            )
            return classify_delete_response(r.status_code, read_text_limited(r))
        except requests.exceptions.Timeout:
            return False, "Delete request timed out."
        except requests.exceptions.ConnectionError:
            return False, "Connection error. Check your network."
        except requests.exceptions.RequestException as e:
            return False, f"Network error: {clean_msg(e)}"
        except Exception as e:
            return False, clean_msg(e) or e.__class__.__name__
