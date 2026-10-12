"""Export / import of the upload history (JSON, CSV, TXT)."""

import csv
import io
import json
from dataclasses import dataclass, field

from .helpers import atomic_write, csv_safe, human_size
from .history_item import normalize_import_item


def format_from_extension(ext):
    ext = (ext or "").lower()
    return {".csv": "csv", ".txt": "txt"}.get(ext, "json")


def to_json(items):
    out = [{
        "filename": it.filename,
        "url": it.url,
        "type": it.kind,
        "mode": it.mode,
        "size": human_size(it.size),
        "size_bytes": it.size,
        "uploaded_at": it.ts,
    } for it in items]
    return json.dumps(out, indent=2, ensure_ascii=False).encode("utf-8")


def to_csv(items):
    """UTF-8 with BOM, CRLF (opens cleanly in Excel)."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow(["filename", "url", "type", "mode", "size", "size_bytes", "date"])
    for it in items:
        w.writerow([csv_safe(it.filename), csv_safe(it.url), it.kind, it.mode,
                    human_size(it.size), it.size, csv_safe(it.ts)])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def to_txt(items):
    """One URL per line."""
    return ("\n".join(it.url for it in items if it.url) + "\n").encode("utf-8")


def export_to_file(path, fmt, items):
    data = {"csv": to_csv, "txt": to_txt}.get(fmt, to_json)(items)
    atomic_write(path, data, private=False)


@dataclass
class ImportResult:
    items: list = field(default_factory=list)   # valid entries in file order (duplicates not filtered)
    invalid: int = 0
    error: str = ""                              # non-empty -> nothing usable


def parse_import(data):
    """`data` is the raw content of a JSON file: our export (list) or a config backup (object)."""
    res = ImportResult()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        doc = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        res.error = "not valid JSON"
        return res

    if isinstance(doc, dict):   # also accept a config backup
        doc = doc.get("history")
    if not isinstance(doc, list):
        res.error = "expected a JSON list of uploads"
        return res

    for raw in doc:
        clean = normalize_import_item(raw)
        if clean is None:
            res.invalid += 1
        else:
            res.items.append(clean)
    return res
