"""Unit tests for render.py (TEST-PLAN 2.5)."""
import re
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from swingtag import catalog as cat
from swingtag import render as r
from swingtag import theme as t

TOKEN = "3xk9m2p7qhv4"
LONG = "Instructions for pruning and seasonal care, part number"  # 55 characters
EXT = {"document": ".pdf", "image": ".jpg", "audio": ".m4a", "video": ".mp4"}


def button(kind, i, label=LONG, context="Care and maintenance"):
    href = "https://example.com/book" if kind == "link" else f"/{TOKEN}/e{i}/f{i}{EXT[kind]}"
    return cat.Button(order=i, label=label, context=context, kind=kind, href=href,
                      public_key=None if kind == "link" else f"public{href}",
                      source_key=f"source/x/{i}", filename=f"f{i}", content_type=None,
                      etag="", size=1, modified=datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc))


@pytest.fixture
def item():
    kinds = ["document", "image", "audio", "video", "link"] * 2
    return cat.Item(collection="Vivaio Radici Lente", label="Olivo Leccino", token=TOKEN,
                    buttons=[button(k, i) for i, k in enumerate(kinds)])


@pytest.fixture
def theme():
    return t.Theme(locale="it", timezone="Europe/Rome", logo="logo.svg", header="Vivaio Radici Lente",
                   footer="Via dei Campi 12", notice="Demo environment",
                   colors=t.Colors("#3d6b4f", "#f4f1ea", "#1d241f"), colors_dark=None)


def test_no_script(item, theme):
    assert "<script" not in r.render_page(item, theme)


def test_one_style_block(item, theme):
    assert r.render_page(item, theme).count("<style>") == 1


def test_weight_ten_buttons(item, theme):
    assert len(r.render_page(item, theme).encode()) < 15360


def test_no_remote_resources(item, theme):
    html = r.render_page(item, theme)
    remote = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert remote == ["https://example.com/book", "https://example.com/book"]
    assert 'src="/_assets/logo.svg"' in html


def test_order_of_sections(item, theme):
    html = r.render_page(item, theme)
    body = html[html.index("<body>"):]
    marks = ["Demo environment", "class=brand", "/_assets/logo.svg", "<h1>",
             "class=sub", "<ul>", "Via dei Campi 12", "Aggiornato il"]
    positions = [body.index(m) for m in marks]
    assert positions == sorted(positions)


def test_subtitle_rule(item, theme):
    assert "class=sub" in r.render_page(item, theme)
    assert "class=sub" not in r.render_page(item, replace(theme, header=None))


def test_derived_tones_only(item, theme):
    css = re.search(r"<style>(.*)</style>", r.render_page(item, theme), re.S).group(1)
    mixes = re.findall(r"color-mix\(((?:[^()]|\([^()]*\))*)\)", css)
    assert mixes
    for args in mixes:
        assert "#" not in args
        assert set(re.findall(r"var\((--[a-z]+)\)", args)) <= {"--t", "--bg", "--p"}


def test_dark_block_rule(item, theme):
    dark = "prefers-color-scheme:dark"
    assert dark not in r.render_page(item, theme)
    assert dark in r.render_page(item, replace(theme, colors_dark=t.Colors("#e0a15a", "#171412", "#f2ede6")))
    assert dark in r.render_page(item, t.DEFAULT_THEME)


def test_file_href_absolute(item, theme):
    assert f'href="/{TOKEN}/e0/f0.pdf"' in r.render_page(item, theme)


def test_link_rel(item, theme):
    html = r.render_page(item, theme)
    assert 'href="https://example.com/book" rel="noopener noreferrer"' in html
    assert "target=" not in html


def test_icon_accessible_name(item, theme):
    labels = re.findall(r'aria-label="([^"]+)"', r.render_page(item, theme))
    assert labels[:5] == ["Documento", "Immagine", "Audio", "Video", "Link"]


def test_escaping(item, theme):
    evil = replace(item, label="<b>&\"'</b>", buttons=[
        button("link", 0, label="<i>x</i>"),
        replace(button("link", 1), href='https://bücher.example/"ü'),
    ])
    html = r.render_page(evil, replace(theme, footer="a & b"))
    assert "<b>" not in html and "<i>" not in html
    assert "&lt;b&gt;&amp;&quot;&#x27;&lt;/b&gt;" in html
    assert "a &amp; b" in html
    assert 'href="https://bücher.example/&quot;ü"' in html


def test_updated_line(item, theme):
    assert "Aggiornato il 25/09/2026 14:30" in r.render_page(item, theme)


def test_empty_item(theme):
    html = r.render_page(cat.Item(collection="C", label="L", token=TOKEN), theme)
    assert "Qui non c&#x27;è ancora nulla." in html
    assert "<ul>" not in html


def test_robots_noindex(item, theme):
    assert "<meta name=robots content=noindex,nofollow>" in r.render_page(item, theme)


def test_long_unbreakable_label_wraps(item, theme):
    """Review Focus 1."""
    html = r.render_page(replace(item, label="x" * 120), theme)
    css = re.search(r"<style>(.*)</style>", html, re.S).group(1)
    assert "overflow-wrap:anywhere" in css


def test_empty_label_heading_falls_back(theme):
    """Review Focus 2."""
    html = r.render_page(cat.Item(collection="Vivaio", label="", token=TOKEN), theme)
    assert "<h1>Vivaio</h1>" in html
