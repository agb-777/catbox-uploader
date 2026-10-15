"""Settings + history persisted in ~/.catbox_uploader.json (same file the older versions used)."""

import json
import re
import time
from dataclasses import dataclass, field

from . import secret_store
from .account_id import new_salt
from .constants import (CONFIG_FILE, DEFAULT_THEME, MAX_COL_W, MAX_CONFIG_BYTES, MAX_HISTORY_ITEMS,
                        MIN_COL_W, THEMES)
from .helpers import FileTooLarge, atomic_write, read_regular_file
from .history_item import sanitize_item
from .validators import valid_userhash

_SALT_RE = re.compile(r"[0-9a-f]{16,64}")


@dataclass
class AppConfig:
    userhash: str = ""
    last_dir: str = ""
    acct_salt: str = ""
    default_dir: str = ""
    auto_history: bool = True
    check_on_start: bool = True
    theme: str = DEFAULT_THEME
    col_widths: dict = field(default_factory=dict)   # "queue" / "history" (last column never stored)
    history: list = field(default_factory=list)      # list[HistoryItem], newest first


def sanitize_col_widths(raw):
    """Validate the column widths loaded from the config file."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for key in ("queue", "history"):
        v = raw.get(key)
        if not isinstance(v, list):
            continue
        if all(isinstance(w, int) and not isinstance(w, bool) and MIN_COL_W <= w <= MAX_COL_W for w in v):
            out[key] = list(v)
    return out


class ConfigStore:
    def __init__(self, path=CONFIG_FILE, use_keychain=True):
        self.path = path
        self.use_keychain = use_keychain
        self.cfg = AppConfig(acct_salt=new_salt())
        self.save_blocked = False
        self._keychain_unreadable = False   # keychain held the userhash but could not be read
        self._kr_value = ""                 # what we know is stored in the keychain
        self._kc_failed_for = ""            # userhash the keychain already refused/timed out on
        self._warning = ""                  # one-shot message for the UI (see pop_warning)

    def _keychain_enabled(self):
        return self.use_keychain and secret_store.available()

    def _init_keychain_value(self):
        if not self._keychain_enabled():
            return
        kr = secret_store.get()
        if kr and valid_userhash(kr):
            self.cfg.userhash = kr
            self._kr_value = kr

    # ---------- load ----------
    def load(self):
        """Read the file (or set defaults). Returns messages to show the user at startup."""
        notices = []
        self.cfg = AppConfig(acct_salt=new_salt())
        self.save_blocked = False
        self._keychain_unreadable = False
        self._kr_value = ""
        self._kc_failed_for = ""

        try:
            raw = read_regular_file(self.path, MAX_CONFIG_BYTES)
            data = json.loads(raw.decode("utf-8-sig"))   # tolerate a BOM added by an editor
            if not isinstance(data, dict):
                raise ValueError("config root is not an object")
        except FileNotFoundError:
            self._init_keychain_value()
            return notices
        except FileTooLarge:
            # Do not read it, and do not overwrite it either.
            self.save_blocked = True
            notices.append("Config file is too large; changes won't be saved")
            self._init_keychain_value()
            return notices
        except (ValueError, UnicodeDecodeError, RecursionError):
            # Genuinely corrupt content -> keep a backup and start fresh.
            try:
                backup = self.path.with_suffix(f".corrupt-{int(time.time())}.json")
                self.path.replace(backup)
                notices.append(f"Config was corrupt; backed up to {backup.name}")
            except OSError:
                self.save_blocked = True
                notices.append("Config is corrupt and could not be backed up; saving disabled")
            self._init_keychain_value()
            return notices
        except OSError as e:
            # Locked / permission problem / not a regular file: do NOT touch or overwrite it.
            self.save_blocked = True
            notices.append(f"Cannot read config ({e.__class__.__name__}); changes won't be saved")
            self._init_keychain_value()
            return notices

        cfg = self.cfg
        uh = data.get("userhash", "")
        uh = uh.strip() if isinstance(uh, str) else ""
        if uh and not valid_userhash(uh):
            uh = ""
            notices.append("The userhash in the config file is invalid and was ignored")
        cfg.userhash = uh

        ld = data.get("last_dir", "")
        cfg.last_dir = ld if isinstance(ld, str) else ""
        dd = data.get("default_dir", "")
        cfg.default_dir = dd if isinstance(dd, str) else ""
        cfg.col_widths = sanitize_col_widths(data.get("col_widths"))
        for key in ("auto_history", "check_on_start"):
            v = data.get(key)
            if isinstance(v, bool):
                setattr(cfg, key, v)
        th = data.get("theme")
        if isinstance(th, str) and th in THEMES:
            cfg.theme = th
        salt = data.get("acct_salt")
        if isinstance(salt, str) and _SALT_RE.fullmatch(salt):
            cfg.acct_salt = salt
        raw = data.get("history")
        if isinstance(raw, list):
            for it in raw[:MAX_HISTORY_ITEMS]:
                clean = sanitize_item(it)
                if clean is not None:
                    cfg.history.append(clean)
            if len(raw) > MAX_HISTORY_ITEMS:
                notices.append(f"History was too long; only the newest {MAX_HISTORY_ITEMS} entries were kept")

        # Look in the keychain only when the userhash was stored there (or when the file
        # comes from a version that did not record it). A deliberate switch to anonymous
        # mode must never be undone by a stale keychain entry.
        uses_kc = data.get("uses_keychain")
        if not cfg.userhash and uses_kc is not False and self._keychain_enabled():
            kr = secret_store.get()
            if kr and valid_userhash(kr):
                cfg.userhash = kr
                self._kr_value = kr
            elif uses_kc is True:
                self._keychain_unreadable = True
                notices.append("Could not read the userhash from the system keychain; "
                               "running anonymously until it is available")
        return notices

    # ---------- save ----------
    def save(self):
        """Write everything atomically (0600). Returns (ok, error_message)."""
        if self.save_blocked:
            return False, "Saving disabled: config file was not readable at startup"

        cfg = self.cfg
        uh = cfg.userhash
        file_uh = uh
        uses_kc = False
        if self._keychain_enabled():
            if uh:
                # One attempt per value: a hung keychain would otherwise block the UI thread for
                # the whole timeout on EVERY save (each upload, each column resize).
                if self._kr_value != uh and self._kc_failed_for != uh:
                    if secret_store.put(uh):
                        self._kr_value = uh
                    else:
                        self._kc_failed_for = uh
                        self._warning = ("System keychain unavailable: the userhash is stored in the "
                                         "config file (owner-only) instead")
                if self._kr_value == uh:
                    file_uh = ""   # safely in the keychain; keep it out of the JSON
                    uses_kc = True
            elif self._kr_value:
                # Anonymous mode: remove the stored secret, but only when we know one
                # exists. A keychain that merely failed to answer at startup must never
                # be treated as empty and wiped.
                if secret_store.put(""):
                    self._kr_value = ""
        if not uh and self._keychain_unreadable:
            uses_kc = True   # keep the pointer: the secret exists but could not be read

        data = {
            "userhash": file_uh,
            "uses_keychain": uses_kc,
            "last_dir": cfg.last_dir,
            "acct_salt": cfg.acct_salt,
            "col_widths": cfg.col_widths,
            "default_dir": cfg.default_dir,
            "auto_history": cfg.auto_history,
            "check_on_start": cfg.check_on_start,
            "theme": cfg.theme,
            "history": [h.to_json() for h in cfg.history],
        }
        try:
            atomic_write(self.path, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8", errors="replace"),
                         private=True)
        except Exception as e:
            return False, str(e) or e.__class__.__name__
        return True, ""

    def pop_warning(self):
        """A one-time message about a degraded (but working) save, '' when there is none."""
        msg, self._warning = self._warning, ""
        return msg

    def set_userhash(self, value):
        """Persist a new userhash (caller validates it). On failure the old value is restored.

        Returns (ok, error_message).
        """
        old = self.cfg.userhash
        old_unreadable = self._keychain_unreadable
        if not value and old_unreadable and self._keychain_enabled():
            secret_store.put("")   # best effort: drop the entry we could not read earlier
        self._keychain_unreadable = False
        self._kc_failed_for = ""   # an explicit Apply tries the keychain again
        self.cfg.userhash = value
        ok, err = self.save()
        if not ok:
            self.cfg.userhash = old
            self._keychain_unreadable = old_unreadable
        return ok, err
