"""Content-addressed media store for bill photos, voice notes and chart images."""

import hashlib
import mimetypes
import re
import time
from collections.abc import Iterable
from pathlib import Path

from app.config import get_settings
from app.store.db import tx

_ID = re.compile(r"^[a-f0-9]{24}\.[a-z0-9]{2,5}$")
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf",
        "audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3", "audio/ogg": "ogg",
        "audio/webm": "webm", "audio/mp4": "m4a", "audio/aac": "aac"}


def _dir() -> Path:
    return get_settings().data_dir / "media"


def extension_for(mime: str) -> str:
    return _EXT.get(mime.split(";")[0].strip().lower(), "bin")


def save(data: bytes, mime: str) -> str:
    media_id = f"{hashlib.sha256(data).hexdigest()[:24]}.{extension_for(mime)}"
    path = _dir() / media_id
    if path.exists():
        path.touch()  # a fresh upload of a known file restarts its retention clock
    else:
        path.write_bytes(data)
    return media_id


def path_for(media_id: str) -> Path | None:
    """Return the file for a media id, or None. Ids are validated so no path can escape the store."""
    if not _ID.match(media_id):
        return None
    path = _dir() / media_id
    return path if path.exists() else None


def load(media_id: str) -> bytes | None:
    path = path_for(media_id)
    return path.read_bytes() if path else None


def mime_for(media_id: str) -> str:
    guessed, _ = mimetypes.guess_type(media_id)
    return guessed or "application/octet-stream"


def discard_unreferenced(media_ids: Iterable[str]) -> int:
    """Delete the files no bill points at any more. Complaints reach their photo only through a bill, so this
    covers both. Files are shared by content, so another user's copy of the same photo keeps it alive."""
    removed = 0
    with tx() as conn:  # held while unlinking, so a bill saved meanwhile cannot lose its file
        for media_id in {m for m in media_ids if m}:
            if conn.execute("SELECT 1 FROM bills WHERE media_id = ? LIMIT 1", (media_id,)).fetchone():
                continue
            path = path_for(media_id)
            if path is not None:
                path.unlink(missing_ok=True)
                removed += 1
    return removed


def discard_stale(days: int) -> int:
    """Unreferenced files older than the retention period: voice notes, charts and photos that never became a bill."""
    cutoff = time.time() - days * 86400
    old = [p.name for p in _dir().iterdir() if p.is_file() and p.stat().st_mtime < cutoff]
    return discard_unreferenced(old)
