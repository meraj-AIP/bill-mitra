"""Upload checks shared by every channel: the bytes decide the type, never the client's label."""

import csv
import io

from fastapi import HTTPException, UploadFile

from app.config import get_settings

DOCUMENTS = frozenset({"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"})
AUDIO = frozenset({"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/aac"})
_HEIF_BRANDS = (b"heic", b"heix", b"heif", b"mif1", b"msf1", b"hevc")
_AUDIO_MP4_BRANDS = (b"M4A ", b"mp42", b"isom", b"dash")


def sniff(head: bytes) -> str | None:
    """Media type from the first bytes of a file, for the formats a bill or a voice note can arrive in."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head[:4] == b"RIFF" and head[8:12] in (b"WEBP", b"WAVE"):
        return "image/webp" if head[8:12] == b"WEBP" else "audio/wav"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        return "image/heic" if brand in _HEIF_BRANDS else "audio/mp4" if brand in _AUDIO_MP4_BRANDS else None
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if head[:2] in (b"\xff\xf1", b"\xff\xf9"):
        return "audio/aac"
    return None


async def read_checked(file: UploadFile, allowed: frozenset[str]) -> tuple[bytes, str]:
    """Read at most the size limit plus one byte, then trust the content, not the declared type."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if not data or len(data) > limit:
        raise HTTPException(413, f"The file must be under {get_settings().max_upload_mb} MB.")
    mime = sniff(data[:16])
    if mime is None or mime not in allowed:
        raise HTTPException(415, "Upload a photo (JPG, PNG, WEBP, HEIC) or a PDF of the bill, or a voice note.")
    return data, mime


CSV_MAX_BYTES = 1024 * 1024


async def read_csv(file: UploadFile, columns: tuple[str, ...], max_rows: int) -> list[tuple[int, dict[str, str]]]:
    """Rows of an admin CSV upload as (file line, values), line 1 being the header. Reads at most 1 MB."""
    data = await file.read(CSV_MAX_BYTES + 1)
    if len(data) > CSV_MAX_BYTES:
        raise HTTPException(413, "The CSV must be under 1 MB.")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        rows = [row for _, row in zip(range(max_rows + 1), reader, strict=False)]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(400, "The file is not a readable UTF-8 CSV.") from exc
    if not set(columns) <= set(reader.fieldnames or []):
        raise HTTPException(400, f"The header must be {','.join(columns)}.")
    if len(rows) > max_rows:
        raise HTTPException(413, f"At most {max_rows} rows per file.")
    return list(enumerate(rows, start=2))
