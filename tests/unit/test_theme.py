"""Unit tests for theme.py."""
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


def test_strings_not_an_object_falls_back(caplog):
    for bad in (["a"], "abc"):
        with caplog.at_level(logging.WARNING):
            theme = t.from_json(body({**RESTAURANT, "strings": bad}))
        assert dict(theme.strings) == {}
        assert theme.locale == "it"


def test_deeply_nested_body_falls_back():
    assert t.from_json(b"[" * 100000) == t.DEFAULT_THEME


def test_colour_trailing_newline_rejected():
    """Deferred minor M1: #rrggbb must match exactly."""
    data = {**RESTAURANT, "colors": {**RESTAURANT["colors"], "primary": "#ffffff\n"}}
    assert t.from_json(body(data)).colors.primary == t.DEFAULT_COLORS.primary


def test_contrast_helper():
    """theme.py exposes the contrast helper the example checks rely on."""
    assert round(t.contrast("#000000", "#ffffff"), 2) == 21.0
    assert round(t.contrast("#8c6d0f", "#fbf8f1"), 2) == 4.59
    assert t.contrast("#fbf8f1", "#8c6d0f") == t.contrast("#8c6d0f", "#fbf8f1")


def test_show_updated_flag(caplog):
    """show_updated is a boolean, true by default; a wrong type falls back to true."""
    assert t.from_json(body({**RESTAURANT, "show_updated": False})).show_updated is False
    assert t.from_json(body(RESTAURANT)).show_updated is True
    assert t.DEFAULT_THEME.show_updated is True
    with caplog.at_level(logging.WARNING):
        assert t.from_json(body({**RESTAURANT, "show_updated": "no"})).show_updated is True
    assert any("show_updated" in r.getMessage() for r in caplog.records)
