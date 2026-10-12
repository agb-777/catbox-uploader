"""One file waiting in the upload queue."""

from dataclasses import dataclass
from enum import Enum


class QueueStatus(Enum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    id: int
    path: str
    name: str
    size: int
    kind: str
    status: QueueStatus = QueueStatus.QUEUED
    detail: str = ""
