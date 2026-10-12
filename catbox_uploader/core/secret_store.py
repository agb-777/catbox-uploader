"""Userhash storage in the OS keychain (via `keyring`, when it is installed).

Every keychain call runs on a helper thread with a time limit, so a locked or hung
keychain can freeze the window for a few seconds at most.
"""

import threading

from .constants import KEYRING_SERVICE, KEYRING_USER

try:  # optional: without it the userhash is kept in the config file (0600)
    import keyring
except Exception:  # pragma: no cover
    keyring = None

_TIMEOUT_S = 10


def available():
    return keyring is not None


def _call(fn, default):
    """Run fn() on a daemon thread; `default` when it fails or does not answer in time."""
    result = [default]

    def run():
        try:
            result[0] = fn()
        except Exception:
            pass

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(_TIMEOUT_S)
    return result[0]


def get():
    """'' when nothing is stored OR the keychain could not be read."""
    if keyring is None:
        return ""

    def fn():
        v = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        return v if isinstance(v, str) else ""

    return _call(fn, "")


def put(value):
    """Store the value, or delete the entry when empty. True on success."""
    if keyring is None:
        return False

    def fn():
        if value:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, value)
            return True
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        except Exception as e:
            # "nothing stored" is fine; any other failure must be reported.
            if e.__class__.__name__ != "PasswordDeleteError":
                return False
        return True

    return _call(fn, False)
