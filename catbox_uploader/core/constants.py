"""Application-wide constants. Pure data, no Qt."""

from pathlib import Path

# ---------- App identity ----------
APP_NAME = "Catbox Uploader"
APP_VERSION = "1.1.0"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"   # main window title
DESKTOP_FILE_NAME = "catbox-uploader"
GITHUB_URL = "https://github.com/agb-777/catbox-uploader"   # change if the repo is named differently
LICENSE_NAME = "MIT"

# ---------- Network ----------
API_URL = "https://catbox.moe/user/api.php"
SITE_URL = "https://catbox.moe/"
USER_AGENT = f"CatboxUploader/{APP_VERSION} (+https://catbox.moe)"
HTTP_HEADERS = {"User-Agent": USER_AGENT}

# Catbox's documented limit is 200 MB per file. We warn instead of hard-blocking
# in case the limit changes.
MAX_UPLOAD_BYTES = 200 * 1024 * 1024

CONNECT_TIMEOUT = 10
UPLOAD_READ_TIMEOUT = 120   # max wait for the server's reply after the body is sent
DELETE_READ_TIMEOUT = 30
STATUS_TIMEOUT = 6
MAX_RESPONSE_BYTES = 64 * 1024   # never read more than this from a server reply
MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_CONFIG_BYTES = 50 * 1024 * 1024
# A saved entry is several times bigger than an imported one, so the history is capped. 20k entries
# stay far below MAX_CONFIG_BYTES even in the worst case (255-char names), so a config the app wrote
# can never grow past the size it refuses to load.
MAX_HISTORY_ITEMS = 20_000
MAX_URL_LEN = 256
CANCEL_GRACE_MS = 3000   # after this, a cancelled but stalled upload is abandoned

# ---------- Storage ----------
def _home():
    try:
        return Path.home()
    except (RuntimeError, KeyError, OSError):   # no usable home directory
        try:
            return Path.cwd()
        except OSError:
            return Path(".")


HOME_DIR = _home()
CONFIG_FILE = HOME_DIR / ".catbox_uploader.json"
LOCK_FILE = HOME_DIR / ".catbox_uploader.lock"
KEYRING_SERVICE = "CatboxUploader"
KEYRING_USER = "userhash"

# ---------- File kinds ----------
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv", ".wmv", ".ts"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".avif",
              ".tif", ".tiff", ".ico", ".heic"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
VALID_KINDS = {"video", "image", "audio", "data"}

# Catbox refuses these types. Rejecting them locally gives instant feedback
# instead of a long upload followed by an error.
BLOCKED_EXTS = {".exe", ".scr", ".cpl", ".jar", ".doc", ".docx", ".docm"}

# ---------- Table columns ----------
MIN_COL_W = 40
MAX_COL_W = 2000
# Widths of every column EXCEPT the last one (the last column fills the rest).
QUEUE_DEFAULT_WIDTHS = [400, 90, 100]            # File, Type, Size | Status
HISTORY_DEFAULT_WIDTHS = [190, 270, 80, 70, 100]  # Filename, URL, Type, Mode, Size | Date

THEMES = ("light", "dark")
DEFAULT_THEME = "light"
