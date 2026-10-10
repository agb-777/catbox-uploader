"""Base class for workers that run on a daemon thread and report through Qt signals.

Workers run on daemon Python threads (not QThread) so that closing the app can never hit
"QThread destroyed while running" or require terminate(): a worker stuck on the network is
simply abandoned and dies with the process.
"""

import threading
import warnings

from PySide6.QtCore import QObject, Signal

LIVE_WORKERS = set()


class ThreadedWorker(QObject):
    done = Signal()          # always the LAST signal
    _SIGNALS = ("done",)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None

    def start(self):
        LIVE_WORKERS.add(self)
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def _thread_main(self):
        try:
            self.run_task()
        except BaseException as e:
            # run_task reports its own errors; this only fires on a real crash.
            try:
                self.on_crash(str(e) or e.__class__.__name__)
            except BaseException:
                pass
        finally:
            self._emit(self.done)

    def _emit(self, signal, *args):
        try:
            signal.emit(*args)
        except RuntimeError:
            pass   # the receiving side is already gone

    def run_task(self):
        raise NotImplementedError

    def on_crash(self, message):
        """Called (on the worker thread) when run_task died unexpectedly."""

    def detach(self):
        """Stop delivering any signals to the UI (used when the window closes)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for name in self._SIGNALS:
                try:
                    getattr(self, name).disconnect()
                except (RuntimeError, TypeError):
                    pass

    def release(self):
        """Call from the main thread after `done` arrives."""
        LIVE_WORKERS.discard(self)
        self.deleteLater()
