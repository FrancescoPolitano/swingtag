"""Accepted file kinds, their content types, and link files.

Pure: takes names and bytes, returns values. Nothing here knows about AWS.
"""

from __future__ import annotations

import configparser
import plistlib
import unicodedata
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


MAX_LINK_BYTES = 65536
_ALLOWED_SCHEMES = frozenset({"http", "https"})


def parse_link(filename: str, body: bytes) -> str | None:
    """Target URL of a .url or .webloc file, or None if unreadable or not http(s).

    .url is an INI file ([InternetShortcut], key URL); .webloc is a property list,
    XML or binary (macOS writes binary when a link is dragged from a browser).
    """
    if len(body) > MAX_LINK_BYTES:
        return None
    name = filename.casefold()
    url: object = None
    if name.endswith(".url"):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read_string(body.decode("utf-8-sig", errors="replace"))
        except configparser.Error:
            return None
        url = parser.get("InternetShortcut", "URL", fallback=None)
    elif name.endswith(".webloc"):
        try:
            data = plistlib.loads(body)
        except Exception:  # plistlib raises several unrelated types on bad input
            return None
        url = data.get("URL") if isinstance(data, dict) else None
    if not isinstance(url, str):
        return None
    url = url.strip()
    # Control characters or whitespace inside a URL: browsers would silently
    # strip or split them, so the file is treated as invalid.
    if any(ch.isspace() or unicodedata.category(ch) == "Cc" for ch in url):
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:  # e.g. "http://[::1" or a netloc invalid under NFKC
        return None
    if parts.scheme.lower() not in _ALLOWED_SCHEMES or not host:
        return None
    return url
