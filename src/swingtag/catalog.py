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

# Largest object a single CopyObject can copy.
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


def _newer(candidate: SourceObject, current: SourceObject) -> bool:
    """True when `candidate` should replace `current` for the same NFC name:
    the newer `modified` wins, a known date beats an unknown one."""
    if candidate.modified is None:
        return current.modified is None
    if current.modified is None:
        return True
    return candidate.modified >= current.modified


def build_item(source_prefix: str, public_prefix: str, prefix: str,
               objects: list[SourceObject], link_bodies: Mapping[str, bytes]) -> Item:
    """The item model of one item prefix.

    `link_bodies` maps the source key of each link file (already size-checked by
    the caller) to its bytes; a link file missing from it is an invalid link.
    """
    collection, folder = split_prefix(source_prefix, prefix)
    label, token = convention.split_item_name(folder)
    item = Item(collection=collection, label=label, token=token or "")

    # entry name -> file name -> (object, format, url); NFC keys merge NFD twins,
    # keeping the most recently modified object.
    grouped: dict[str, dict[str, tuple[SourceObject, formats.Format, str | None]]] = {}
    for obj in objects:
        if obj.key.endswith("/"):
            continue  # folder placeholder created by some clients
        relative = convention.normalize(obj.key[len(prefix):])
        parts = relative.split("/")
        if len(parts) == 1:
            if not convention.is_ignored(parts[0]):
                item.anomalies.append(f"file in item root: {relative}")
            continue
        if len(parts) > 2:
            if not any(convention.is_ignored(p) for p in parts):
                item.anomalies.append(f"deeper than entry level: {relative}")
            continue
        entry_name, filename = parts
        if convention.is_ignored(entry_name) or convention.is_ignored(filename):
            continue
        fmt = formats.lookup(filename)
        if fmt is None:
            item.anomalies.append(f"format not accepted: {relative}")
            continue
        url = None
        if fmt.kind == "link":
            url = formats.parse_link(filename, link_bodies.get(obj.key, b""))
            if url is None:
                item.anomalies.append(f"invalid link: {relative}")
                continue
        elif obj.size > MAX_COPY_BYTES:
            item.anomalies.append(f"too large for single copy: {relative}")
            continue
        files = grouped.setdefault(entry_name, {})
        previous = files.get(filename)
        if previous is None or _newer(obj, previous[0]):
            files[filename] = (obj, fmt, url)

    entries = sorted(grouped.items(),
                     key=lambda e: (convention.sort_key(*convention.parse_order(e[0])), e[0]))
    entry_slugs: set[str] = set()
    ranked: list[tuple[tuple, tuple, Button]] = []
    for position, (entry_name, files) in enumerate(entries):
        order, entry_label = convention.parse_order(entry_name)
        entry_slug = convention.unique_slug(entry_label, entry_slugs, "entry")
        multiple = len(files) > 1
        file_slugs: set[str] = set()
        by_stem = sorted(
            ((filename[: -len(fmt.extension)], filename, obj, fmt, url)
             for filename, (obj, fmt, url) in files.items()),
            key=lambda f: convention.sort_key(*convention.parse_order(f[0])),
        )
        for stem, filename, obj, fmt, url in by_stem:
            file_order, file_label = convention.parse_order(stem)
            file_slug = convention.unique_slug(file_label, file_slugs, "file")
            if fmt.kind == "link":
                public_key, href = None, url
            else:
                path = f"{entry_slug}/{file_slug}{fmt.extension}"
                public_key, href = f"{public_prefix}{item.token}/{path}", f"/{item.token}/{path}"
            button = Button(
                order=order,
                label=file_label if multiple else entry_label,
                context=entry_label if multiple else "",
                kind=fmt.kind,
                href=href,
                public_key=public_key,
                source_key=obj.key,
                filename=filename,
                content_type=fmt.content_type,
                etag=obj.etag,
                size=obj.size,
                modified=obj.modified,
            )
            ranked.append((position, convention.sort_key(file_order, file_label), button))
    ranked.sort(key=lambda r: (r[0], r[1]))
    item.buttons = [r[2] for r in ranked]
    return item


def published_keys(public_prefix: str, item: Item) -> set[str]:
    """Keys the public zone must hold for this item: page, QR code, copied files."""
    base = f"{public_prefix}{item.token}/"
    keys = {f"{base}index.html", f"{base}qr.svg"}
    keys.update(b.public_key for b in item.buttons if b.public_key is not None)
    return keys
