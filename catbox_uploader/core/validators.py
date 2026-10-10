"""Validation / classification of untrusted strings (URLs, userhash, file names)."""

import re
from pathlib import Path
from urllib.parse import urlparse

from .constants import (AUDIO_EXTS, BLOCKED_EXTS, IMAGE_EXTS, VALID_KINDS, VIDEO_EXTS)

# fullmatch + ASCII classes: `$` would also accept a trailing newline and `\w`
# would accept non-ASCII letters.
_FILE_URL_RE = re.compile(r"https://files\.catbox\.moe/(?=[._\-]*[A-Za-z0-9])[A-Za-z0-9._\-]+")

# A userhash is an opaque token: visible ASCII only, no spaces.
_USERHASH_RE = re.compile(r"[\x21-\x7e]{1,128}")


def extension_of(path_or_name):
    """Lower-case extension with leading dot ('.png'), or '' when there is none."""
    return Path(str(path_or_name)).suffix.lower()


def file_kind(path):
    """'video' / 'image' / 'audio' / 'data'."""
    ext = extension_of(path)
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in AUDIO_EXTS:
        return "audio"
    return "data"


def is_valid_kind(kind):
    return isinstance(kind, str) and kind in VALID_KINDS


def is_blocked_ext(ext):
    return (ext or "").lower() in BLOCKED_EXTS


def is_catbox_file_url(url):
    return isinstance(url, str) and _FILE_URL_RE.fullmatch(url) is not None


def shortcode_from_url(url):
    """'abc123.mp4' for a catbox file URL, otherwise ''."""
    if not is_catbox_file_url(url):
        return ""
    return urlparse(url).path.rsplit("/", 1)[-1]


def valid_userhash(value):
    """Empty is valid (anonymous mode)."""
    if not isinstance(value, str):
        return False
    return value == "" or _USERHASH_RE.fullmatch(value) is not None


def file_dialog_filter():
    def glob(exts):
        return " ".join(f"*{e}" for e in sorted(exts))
    return ";;".join([
        "All files (*)",
        f"Videos ({glob(VIDEO_EXTS)})",
        f"Images ({glob(IMAGE_EXTS)})",
        f"Audio ({glob(AUDIO_EXTS)})",
    ])
