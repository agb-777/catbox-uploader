"""Shared pieces for every request."""

from ..core.constants import MAX_RESPONSE_BYTES


def read_text_limited(resp, limit=MAX_RESPONSE_BYTES):
    """Read at most `limit` bytes of a streamed response and close it."""
    buf = bytearray()
    try:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                buf.extend(chunk)
            if len(buf) >= limit:
                break
    finally:
        try:
            resp.close()
        except Exception:
            pass
    return bytes(buf[:limit]).decode("utf-8", errors="replace").strip()
