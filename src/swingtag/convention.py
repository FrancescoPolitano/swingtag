"""Naming rules: separator, order prefixes, Unicode, ignore rules, tokens and slugs.

Everything that interprets folder and file names lives here. Pure functions on
strings: nothing in this module knows about AWS.
"""

from __future__ import annotations

import re
import unicodedata

# Between the readable item label and its token. Space, middle dot (U+00B7), space:
# it does not occur in ordinary names and stays readable in file managers.
SEPARATOR = " · "

# Order prefix: "10 Lunch", "10. Lunch", "10 - Lunch", "10) Lunch".
_ORDER_RE = re.compile(r"^(\d{1,6})\s*(?:[.)\-]\s*|\s+)(.+)$")

# Names that are not content and must not be reported as anomalies.
_SYSTEM_NAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini", "icon\r"})


def normalize(value: str) -> str:
    """Composed Unicode form.

    macOS uploads produce decomposed accents: without this step the same name
    typed on macOS and on Windows is two different strings that look identical.
    """
    return unicodedata.normalize("NFC", value)


def parse_order(name: str) -> tuple[int | None, str]:
    """Split an optional order prefix off a name: returns (order, label)."""
    clean = normalize(name).strip()
    match = _ORDER_RE.match(clean)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None, clean


def sort_key(order: int | None, label: str) -> tuple[int, int, str]:
    """Numbered names first by number, then the others alphabetically, case-insensitive."""
    if order is None:
        return (1, 0, label.casefold())
    return (0, order, label.casefold())


def is_ignored(name: str) -> bool:
    """Names skipped silently: hidden, underscored, empty and OS housekeeping files."""
    raw = normalize(name)
    # Checked before stripping: macOS folder icons are named "Icon\r", and strip()
    # would remove the carriage return that identifies them.
    if raw.casefold() in _SYSTEM_NAMES:
        return True
    clean = raw.strip()
    if not clean:
        return True
    if clean.startswith((".", "_")):
        return True
    return clean.casefold() in _SYSTEM_NAMES
