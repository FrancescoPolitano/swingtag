"""From the flat listing of an item folder to the model its page represents.

Pure: receives the objects under one item prefix (and the bodies of its link
files) and returns an Item. Nothing here knows about AWS.

The menu is flat: one tap, one resource. An entry folder with one resource gives
one button titled like the folder; an entry with several resources gives one
button per resource, titled like the file, with the folder name as context.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from . import convention, formats

# Largest object a single CopyObject can copy (SPEC 10.13).
MAX_COPY_BYTES = 5 * 1024**3


@dataclass(frozen=True)
class SourceObject:
    key: str
    etag: str = ""
    size: int = 0
    modified: datetime | None = None


@dataclass(frozen=True)
class Button:
    order: int | None
    label: str
    context: str
    kind: str
    href: str               # absolute public path for files, external URL for links
    public_key: str | None  # None for links: they are not copied
    source_key: str
    filename: str
    content_type: str | None
    etag: str
    size: int
    modified: datetime | None


@dataclass
class Item:
    collection: str
    label: str
    token: str
    buttons: list[Button] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.buttons

    @property
    def updated_at(self) -> datetime | None:
        dates = [b.modified for b in self.buttons if b.modified is not None]
        return max(dates) if dates else None


def item_prefix(source_prefix: str, key: str) -> str | None:
    """Prefix of the item a key belongs to: `source/{collection}/{item}/`, or None."""
    if not key.startswith(source_prefix):
        return None
    parts = key[len(source_prefix):].split("/")
    if len(parts) < 3 or not parts[0] or not parts[1]:
        return None
    return f"{source_prefix}{parts[0]}/{parts[1]}/"


def split_prefix(source_prefix: str, prefix: str) -> tuple[str, str]:
    """(collection, item folder name) of an item prefix, NFC-normalised."""
    remainder = prefix[len(source_prefix):].rstrip("/")
    collection, _, folder = remainder.partition("/")
    return convention.normalize(collection), convention.normalize(folder)


def build_item(source_prefix: str, public_prefix: str, prefix: str,
               objects: list[SourceObject], link_bodies: Mapping[str, bytes]) -> Item:
    """The item model of one item prefix (buttons are filled in Task 10)."""
    collection, folder = split_prefix(source_prefix, prefix)
    label, token = convention.split_item_name(folder)
    return Item(collection=collection, label=label, token=token or "")


def published_keys(public_prefix: str, item: Item) -> set[str]:
    """Keys the public zone must hold for this item (completed in Task 11)."""
    base = f"{public_prefix}{item.token}/"
    return {f"{base}index.html", f"{base}qr.svg"}
