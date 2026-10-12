"""Small formatting / text / file helpers. No Qt."""

import os
import stat
import tempfile
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


class FileTooLarge(OSError):
    pass


class NotRegularFile(OSError):
    pass


def read_regular_file(path, limit):
    """Read a regular file of at most `limit` bytes.

    Devices and FIFOs are refused (reading /dev/zero would never end, opening a FIFO would
    block forever), and so is anything bigger than `limit`.
    """
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise NotRegularFile("not a regular file")
        data = f.read(limit + 1)
    if len(data) > limit:
        raise FileTooLarge("file is too large")
    return data


def atomic_write(path, data, private=True):
    """Write bytes atomically (temp file + replace) so a crash never leaves a half file.

    The temp file gets a random name and is created exclusively (never through a symlink an
    attacker could have planted in a shared folder such as /tmp). A symlinked target is
    followed, so a dotfile-manager link is kept. private=True gives owner-only permissions;
    private=False follows the normal umask (user exports).
    """
    target = Path(os.path.realpath(str(path)))
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            if not private:
                umask = os.umask(0)
                os.umask(umask)
                try:
                    os.chmod(tmp, 0o666 & ~umask)
                except OSError:
                    pass
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
