"""Unit tests for theme.py (TEST-PLAN 2.3)."""
import json
import logging

from swingtag import theme as t

RESTAURANT = {
    "locale": "it",
    "timezone": "Europe/Rome",
    "logo": "logo.svg",
    "header": "Osteria Quattro Mestoli",
    "footer": "Via del Borgo 3",
    "notice": "Demo",
    "colors": {"primary": "#8a2d1c", "background": "#fbf7f2", "text": "#1f1b16"},
    "strings": {"updated": "Menu aggiornato il"},
}


def body(data):
    return json.dumps(data).encode()


def test_default_theme(caplog):
    assert t.from_json(b"") == t.DEFAULT_THEME
    with caplog.at_level(logging.WARNING):
        assert t.from_json(b"{not json") == t.DEFAULT_THEME
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_full_theme():
    theme = t.from_json(body(RESTAURANT))
    assert theme.locale == "it"
    assert theme.timezone == "Europe/Rome"
    assert theme.logo == "logo.svg"
    assert theme.header == "Osteria Quattro Mestoli"
    assert theme.footer == "Via del Borgo 3"
    assert theme.notice == "Demo"
    assert theme.colors == t.Colors("#8a2d1c", "#fbf7f2", "#1f1b16")


def test_bad_colour_falls_back(caplog):
    data = {**RESTAURANT, "colors": {**RESTAURANT["colors"], "primary": "red"}}
    with caplog.at_level(logging.WARNING):
        theme = t.from_json(body(data))
    assert theme.colors.primary == t.DEFAULT_COLORS.primary
    assert theme.colors.background == "#fbf7f2"
    assert any("primary" in r.getMessage() for r in caplog.records)


def test_bad_timezone_falls_back(caplog):
    with caplog.at_level(logging.WARNING):
        theme = t.from_json(body({**RESTAURANT, "timezone": "Mars/Olympus"}))
    assert theme.timezone == "UTC"
    assert any("timezone" in r.getMessage() for r in caplog.records)


def test_string_override():
    assert t.from_json(body(RESTAURANT)).string("updated") == "Menu aggiornato il"


def test_string_builtin():
    assert t.from_json(body(RESTAURANT)).string("empty") == "Qui non c'è ancora nulla."


def test_dark_only_when_given():
    assert t.from_json(body(RESTAURANT)).colors_dark is None
    dark = {"primary": "#e0a15a", "background": "#171412", "text": "#f2ede6"}
    assert t.from_json(body({**RESTAURANT, "colors_dark": dark})).colors_dark == t.Colors(**dark)
    assert t.DEFAULT_THEME.colors_dark is not None


def test_unknown_string_key_dropped(caplog):
    with caplog.at_level(logging.WARNING):
        theme = t.from_json(body({**RESTAURANT, "strings": {"updatd": "x"}}))
    assert "updatd" not in theme.strings
