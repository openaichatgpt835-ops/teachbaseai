"""KB storage helpers: save uploads to local disk."""
import os
import hashlib
from typing import BinaryIO

from apps.backend.config import get_settings


def _base_path() -> str:
    s = get_settings()
    return (s.kb_storage_path or "/app/storage/kb").rstrip("/")


def ensure_portal_dir(portal_id: int) -> str:
    base = _base_path()
    path = os.path.join(base, str(portal_id))
    os.makedirs(path, exist_ok=True)
    return path


def save_upload(stream: BinaryIO, dst_path: str) -> tuple[int, str]:
    """Save stream to path and return (size_bytes, sha256)."""
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    h = hashlib.sha256()
    size = 0
    with open(dst_path, "wb") as f:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            size += len(chunk)
    return size, h.hexdigest()
