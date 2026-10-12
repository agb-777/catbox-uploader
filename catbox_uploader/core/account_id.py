"""Salted fingerprint of a userhash, used to detect account mix-ups in the history."""

import hashlib
import hmac
import os


def new_salt():
    """32 hex chars of randomness; generated once per installation."""
    return os.urandom(16).hex()


def acct_id(userhash, salt):
    """HMAC-SHA256(salt, userhash), first 16 hex chars. '' when either input is empty."""
    if not userhash or not salt:
        return ""
    return hmac.new(salt.encode("utf-8"), userhash.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def legacy_acct_id(userhash):
    """Fingerprint format used by older versions: SHA256(userhash), first 12 hex chars."""
    if not userhash:
        return ""
    return hashlib.sha256(userhash.encode("utf-8")).hexdigest()[:12]


def acct_matches(stored, userhash, salt):
    """True when a history entry belongs to `userhash` (or carries no fingerprint)."""
    if not stored or not userhash:
        return True
    return stored in (acct_id(userhash, salt), legacy_acct_id(userhash))
