"""The deployment theme as the publisher reads it (FR-12..FR-15).

Terraform validates theme.yaml strictly at plan time. Here the reading is
tolerant: whatever is missing or invalid falls back to a default and is logged,
so that a page is always published (EC-20, EC-21).
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
    colors: Colors = DEFAULT_COLORS
    colors_dark: Colors | None = DEFAULT_DARK
    strings: Mapping[str, str] = field(default_factory=dict)

    def string(self, key: str) -> str:
        """The operator's override if any, else the built-in text for the locale."""
        return self.strings.get(key) or STRINGS.get(self.locale, STRINGS["en"])[key]


DEFAULT_THEME = Theme()


def _text(data: dict, key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _colors(raw: object, default: Colors, name: str) -> Colors:
    raw = raw if isinstance(raw, dict) else {}
    values = {}
    for key in ("primary", "background", "text"):
        value = raw.get(key)
        if isinstance(value, str) and _HEX.match(value):
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
    except (ValueError, UnicodeDecodeError):
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

    known = STRINGS["en"].keys()
    strings = {}
    for key, value in (data.get("strings") or {}).items():
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
        colors=_colors(data.get("colors"), DEFAULT_COLORS, "colors"),
        colors_dark=_colors(data["colors_dark"], DEFAULT_DARK, "colors_dark")
        if "colors_dark" in data else None,
        strings=strings,
    )
