"""The deployment theme as the publisher reads it.

Terraform validates theme.yaml strictly at plan time. Here the reading is
tolerant: whatever is missing or invalid falls back to a default and is logged,
so that a page is always published.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from .i18n import STRINGS

log = logging.getLogger(__name__)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_LOCALES = ("en", "it")


@dataclass(frozen=True)
class Colors:
    primary: str
    background: str
    text: str


DEFAULT_COLORS = Colors(primary="#1f5f8b", background="#f7f7f5", text="#1a1a1a")
DEFAULT_DARK = Colors(primary="#6fb3e0", background="#141619", text="#eef0f2")


@dataclass(frozen=True)
class Theme:
    locale: str = "en"
    timezone: str = "UTC"
    logo: str | None = None
    header: str | None = None
    footer: str | None = None
    notice: str | None = None
    show_updated: bool = True
    colors: Colors = DEFAULT_COLORS
    colors_dark: Colors | None = DEFAULT_DARK
    strings: Mapping[str, str] = field(default_factory=dict)

    def string(self, key: str) -> str:
        """The operator's override if any, else the built-in text for the locale."""
        return self.strings.get(key) or STRINGS.get(self.locale, STRINGS["en"])[key]


DEFAULT_THEME = Theme()


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    """WCAG 2.x contrast ratio of two #rrggbb colours (same formula as the Terraform check)."""
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _text(data: dict, key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _colors(raw: object, default: Colors, name: str) -> Colors:
    raw = raw if isinstance(raw, dict) else {}
    values = {}
    for key in ("primary", "background", "text"):
        value = raw.get(key)
        if isinstance(value, str) and _HEX.fullmatch(value):
            values[key] = value
        else:
            log.warning("theme: invalid %s.%s %r, using default", name, key, value)
            values[key] = getattr(default, key)
    return Colors(**values)


def from_json(body: bytes) -> Theme:
    """Theme from the config/theme.json written by Terraform; tolerant of errors."""
    if not body.strip():
        return DEFAULT_THEME
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError):
        log.warning("theme: config/theme.json is not valid JSON, using the default theme")
        return DEFAULT_THEME
    if not isinstance(data, dict):
        log.warning("theme: config/theme.json is not an object, using the default theme")
        return DEFAULT_THEME

    locale = data.get("locale", "en")
    if locale not in _LOCALES:
        log.warning("theme: invalid locale %r, using en", locale)
        locale = "en"

    timezone = data.get("timezone", "UTC")
    try:
        ZoneInfo(timezone)
    except Exception:  # ZoneInfoNotFoundError, ValueError, TypeError
        log.warning("theme: invalid timezone %r, using UTC", timezone)
        timezone = "UTC"

    show_updated = data.get("show_updated", True)
    if not isinstance(show_updated, bool):
        log.warning("theme: show_updated must be true or false, not %r; using true", show_updated)
        show_updated = True

    known = STRINGS["en"].keys()
    strings = {}
    raw_strings = data.get("strings") or {}
    if not isinstance(raw_strings, dict):
        log.warning("theme: strings is not an object, ignored")
        raw_strings = {}
    for key, value in raw_strings.items():
        if key in known and isinstance(value, str):
            strings[key] = value
        else:
            log.warning("theme: unknown or invalid strings.%s, ignored", key)

    return Theme(
        locale=locale,
        timezone=timezone,
        logo=_text(data, "logo"),
        header=_text(data, "header"),
        footer=_text(data, "footer"),
        notice=_text(data, "notice"),
        show_updated=show_updated,
        colors=_colors(data.get("colors"), DEFAULT_COLORS, "colors"),
        colors_dark=_colors(data["colors_dark"], DEFAULT_DARK, "colors_dark")
        if "colors_dark" in data else None,
        strings=strings,
    )
