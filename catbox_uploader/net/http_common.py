"""Shared pieces for every request."""

import time

from ..core.constants import MAX_RESPONSE_BYTES

READ_DEADLINE_S = 30   # a server that drips its reply cannot keep a worker busy forever


def read_text_limited(resp, limit=MAX_RESPONSE_BYTES, deadline_s=None):
    """Read at most `limit` bytes (and for at most `deadline_s` seconds) of a streamed reply."""
    deadline = time.monotonic() + (READ_DEADLINE_S if deadline_s is None else deadline_s)
    buf = bytearray()
    try:
        # One byte at a time: a larger chunk makes the read wait until it is completely full,
        # which a server dripping its reply could stretch for hours. Replies are tiny anyway.
        for chunk in resp.iter_content(chunk_size=1):
            if chunk:
                buf.extend(chunk)
            if len(buf) >= limit or time.monotonic() > deadline:
                break
    finally:
        try:
            resp.close()
        except Exception:
            pass
    return bytes(buf[:limit]).decode("utf-8", errors="replace").strip()
