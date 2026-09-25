"""Accepted file kinds, their content types, and link files (FR-7, FR-8).

Pure: takes names and bytes, returns values. Nothing here knows about AWS.
"""

from __future__ import annotations

import configparser
import plistlib
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Format:
    kind: str                 # document | image | audio | video | link
    content_type: str | None  # None for links: they are read, not copied
    extension: str            # lowercase, with the dot


FORMATS: dict[str, Format] = {
    ext: Format(kind, ctype, ext)
    for ext, kind, ctype in [
        (".pdf", "document", "application/pdf"),
        (".jpg", "image", "image/jpeg"),
        (".jpeg", "image", "image/jpeg"),
        (".png", "image", "image/png"),
        (".webp", "image", "image/webp"),
        (".mp3", "audio", "audio/mpeg"),
        (".m4a", "audio", "audio/mp4"),
        (".mp4", "video", "video/mp4"),
        (".url", "link", None),
        (".webloc", "link", None),
    ]
}


def lookup(filename: str) -> Format | None:
    """Format of a file from its last extension, case-insensitive; None if not accepted."""
    stem, dot, ext = filename.rpartition(".")
    if not dot:
        return None
    return FORMATS.get(f".{ext.casefold()}")
