"""Naming rules: separator, order prefixes, Unicode, ignore rules, tokens and slugs.

Everything that interprets folder and file names lives here. Pure functions on
strings: nothing in this module knows about AWS.
"""

from __future__ import annotations

import hashlib
import hmac
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
    if match and any(ch.isalnum() for ch in match.group(2)):
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


# Token alphabet: lowercase letters and digits without l, o, 0, 1, which get
# confused when a code is read aloud or printed small. 32 symbols x 12 = 60 bits.
TOKEN_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
TOKEN_LENGTH = 12
_TOKEN_RE = re.compile(rf"^[{TOKEN_ALPHABET}]{{{TOKEN_LENGTH}}}$")


def is_token(value: str) -> bool:
    return bool(_TOKEN_RE.match(value))


def token_for(collection: str, label: str, secret: str) -> str:
    """Token of an item, derived from its names with a secret key.

    Deterministic on purpose: two concurrent runs that find the same untokenised
    folder compute the same value and converge on one address instead of creating
    twin items. Unpredictable without the key. 256 is a multiple of 32, so reducing
    each byte modulo 32 is uniform.
    """
    material = f"{normalize(collection)}\x00{normalize(label)}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).digest()
    return "".join(TOKEN_ALPHABET[byte % len(TOKEN_ALPHABET)] for byte in digest[:TOKEN_LENGTH])


def split_item_name(folder: str) -> tuple[str, str | None]:
    """Split an item folder name into (label, token); token is None when absent.

    The last separator wins, so a label may itself contain the separator. A tail
    that is not a valid token is part of the label.
    """
    name = normalize(folder).strip()
    # Stripping turns " · token" (empty label) into "· token": restore the leading space.
    probe = f" {name}" if name.startswith(SEPARATOR.lstrip()) else name
    label, sep, candidate = probe.rpartition(SEPARATOR)
    if sep and is_token(candidate.strip()):
        return label.strip(), candidate.strip()
    return name, None


def with_token(label: str, token: str) -> str:
    return f"{label.strip()}{SEPARATOR}{token}"


# Letters with no ASCII decomposition: NFKD alone drops them ("Straße" -> "strae"),
# so they are replaced first.
TRANSLITERATION = str.maketrans({
    "ß": "ss", "ẞ": "SS", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
    "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "þ": "th", "Þ": "Th",
})


def slug(value: str, fallback: str) -> str:
    """URL-safe form: ASCII, lowercase, hyphens. Accents are transliterated, not dropped."""
    decomposed = unicodedata.normalize("NFKD", value.translate(TRANSLITERATION))
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").casefold()
    hyphenated = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return hyphenated or fallback


def unique_slug(value: str, taken: set[str], fallback: str) -> str:
    """A slug not yet in `taken` (a numeric suffix resolves collisions); records it."""
    base = slug(value, fallback)
    candidate, counter = base, 2
    while candidate in taken:
        candidate = f"{base}-{counter}"
        counter += 1
    taken.add(candidate)
    return candidate
