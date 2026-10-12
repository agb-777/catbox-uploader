"""Checks whether catbox.moe answers (only the headers matter, the page is never downloaded)."""

import requests
from PySide6.QtCore import Signal

from ..core.constants import HTTP_HEADERS, SITE_URL, STATUS_TIMEOUT
from ..core.helpers import clean_msg
from .threaded_worker import ThreadedWorker

_SEP = "  \u00b7  "


class StatusChecker(ThreadedWorker):
    result = Signal(bool, str)
    _SIGNALS = ("done", "result")

    def on_crash(self, message):
        self._emit(self.result, False, clean_msg(message))

    def run_task(self):
        try:
            # stream=True: only the headers are needed, never download the page.
            r = requests.get(SITE_URL, timeout=STATUS_TIMEOUT, allow_redirects=True,
                             headers=HTTP_HEADERS, stream=True)
            code = r.status_code
            r.close()
            if code in (403, 429):
                self._emit(self.result, False, f"blocked / rate-limited{_SEP}HTTP {code}")
            elif code < 500:
                self._emit(self.result, True, f"online{_SEP}HTTP {code}")
            else:
                self._emit(self.result, False, f"server error{_SEP}HTTP {code}")
        except requests.exceptions.Timeout:
            self._emit(self.result, False, f"timeout{_SEP}no response")
        except requests.exceptions.ConnectionError:
            self._emit(self.result, False, f"unreachable{_SEP}check connection")
        except Exception as e:
            self._emit(self.result, False, clean_msg(e) or e.__class__.__name__)
