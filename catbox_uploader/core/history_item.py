"""One entry of the upload history + (de)serialisation of untrusted JSON."""

import itertools
import math
from dataclasses import dataclass, field

from .validators import file_kind, is_catbox_file_url, is_valid_kind


class Mode:
    USERHASH = "userhash"
    ANONYMOUS = "anonymous"
    UNKNOWN = "unknown"

    ALL = (USERHASH, ANONYMOUS, UNKNOWN)


def mode_label(mode):
    return {Mode.USERHASH: "auth", Mode.ANONYMOUS: "anon"}.get(mode, "?")


def mode_sort_key(mode):
    """auth first, then unknown, then anon."""
    return {Mode.USERHASH: 0, Mode.UNKNOWN: 1, Mode.ANONYMOUS: 2}.get(mode, 1)


_uid_counter = itertools.count(1)


def next_uid():
    return next(_uid_counter)


@dataclass
class HistoryItem:
    filename: str = ""
    url: str = ""            # '' when the stored URL was not a real catbox URL
    size: int = 0
    ts: str = ""
    mode: str = Mode.UNKNOWN
    kind: str = "data"
    acct: str = ""           # salted account fingerprint, '' when unknown
    uid: int = field(default_factory=next_uid)   # runtime identity (never saved)

    def to_json(self):
        out = {
            "filename": self.filename,
            "url": self.url,
            "size": self.size,
            "ts": self.ts,
            "mode": self.mode,
            "kind": self.kind,
        }
        if self.acct:
            out["acct"] = self.acct
        return out


def _coerce_size(value):
    if isinstance(value, bool):
        return 0
    try:
        if isinstance(value, (int, float)):
            n = float(value)
        elif isinstance(value, str):
            n = float(value.strip())
        else:
            return 0
    except (ValueError, OverflowError):
        return 0
    if math.isnan(n) or n <= 0:
        return 0
    return int(min(n, 9.0e15))


def sanitize_item(raw):
    """Coerce a history entry loaded from disk into a well-typed HistoryItem (or None)."""
    if not isinstance(raw, dict):
        return None
    url = raw.get("url")
    url = url.strip() if isinstance(url, str) else ""
    if not is_catbox_file_url(url):
        url = ""
    name = raw.get("filename")
    name = name if isinstance(name, str) else ""
    name = "".join(ch for ch in name if ch.isprintable())[:255]
    if not name and url:
        name = url.rsplit("/", 1)[-1]
    if not name and not url:
        return None

    ts = raw.get("ts")
    ts = "".join(ch for ch in ts if ch.isprintable())[:64] if isinstance(ts, str) else ""
    mode = raw.get("mode")
    kind = raw.get("kind")
    acct = raw.get("acct")
    return HistoryItem(
        filename=name,
        url=url,
        size=_coerce_size(raw.get("size", 0)),
        ts=ts,
        mode=mode if mode in Mode.ALL else Mode.UNKNOWN,
        kind=kind if is_valid_kind(kind) else file_kind(name),
        acct=acct if isinstance(acct, str) and 0 < len(acct) <= 64 else "",
    )


def normalize_import_item(raw):
    """Turn one entry of an imported JSON file into a HistoryItem (or None).

    Accepts both our Export format (type / uploaded_at / size_bytes) and the internal
    config format (kind / ts / size). Only real catbox file URLs are kept. The account
    fingerprint is never imported (it is only meaningful with this install's salt).
    """
    if not isinstance(raw, dict):
        return None
    url = raw.get("url")
    if not isinstance(url, str) or not is_catbox_file_url(url.strip()):
        return None

    size = raw.get("size_bytes", raw.get("size", 0))
    if isinstance(size, bool) or not isinstance(size, (int, float)):
        size = 0   # our export also has a human-readable "size" string: ignore it
    return sanitize_item({
        "filename": raw.get("filename"),
        "url": url.strip(),
        "size": size,
        "ts": raw.get("ts", raw.get("uploaded_at", "")),
        "mode": raw.get("mode"),
        "kind": raw.get("kind", raw.get("type")),
    })
