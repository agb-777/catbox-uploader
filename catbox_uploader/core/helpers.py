"""Small formatting / text / file helpers. No Qt."""

import os
from pathlib import Path


def human_size(n):
    n = float(n) if n and n > 0 else 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def human_speed(bps):
    return f"{human_size(bps)}/s"


def human_eta(seconds):
    if seconds is None or seconds < 0:
        return ""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return ">1d"


def short_text(text, limit=40):
    text = text or ""
    return text if len(text) <= limit else text[:limit - 3] + "..."


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def clean_msg(text, limit=200):
    """Collapse whitespace / control characters of a server message for display."""
    text = " ".join(str(text or "").split())
    text = "".join(ch for ch in text if ch.isprintable())
    return text[:limit]


def csv_safe(value):
    """Neutralise spreadsheet formula injection."""
    value = "" if value is None else str(value)
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def atomic_write(path, data, private=True):
    """Write bytes atomically (temp file + replace) so a crash never leaves a half file.

    private=True creates the file with 0600 permissions from the very first byte
    (config / history). private=False follows the normal umask (user exports).
    """
    path = Path(path)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if private else 0o666)
    try:
        if private:
            try:
                os.chmod(tmp, 0o600)   # in case a stale temp file already existed
            except OSError:
                pass
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
