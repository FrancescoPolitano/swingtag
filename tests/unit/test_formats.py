"""Unit tests for formats.py (TEST-PLAN 2.2)."""
import plistlib

import pytest

from swingtag import formats as f

EXPECTED = {
    ".pdf": ("document", "application/pdf"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
    ".webp": ("image", "image/webp"),
    ".mp3": ("audio", "audio/mpeg"),
    ".m4a": ("audio", "audio/mp4"),
    ".mp4": ("video", "video/mp4"),
    ".url": ("link", None),
    ".webloc": ("link", None),
}


@pytest.mark.parametrize("ext", sorted(EXPECTED))
def test_lookup_every_extension(ext):
    fmt = f.lookup(f"name{ext}")
    assert (fmt.kind, fmt.content_type) == EXPECTED[ext]
    assert fmt.extension == ext


def test_lookup_uppercase():
    assert f.lookup("MENU.PDF") == f.Format("document", "application/pdf", ".pdf")
    assert f.lookup("clip.MP4") == f.Format("video", "video/mp4", ".mp4")


def test_lookup_unknown():
    assert f.lookup("notes.docx") is None
    assert f.lookup("archive") is None


def test_lookup_last_extension():
    """Review Focus 3."""
    assert f.lookup("menu.v2.final.pdf").kind == "document"


URL = "https://example.com/book?table=2"


def test_link_url_crlf():
    assert f.parse_link("x.url", f"[InternetShortcut]\r\nURL={URL}\r\n".encode()) == URL


def test_link_url_bom():
    body = ("﻿[InternetShortcut]\nURL=" + URL + "\n").encode("utf-8")
    assert f.parse_link("x.url", body) == URL


def test_link_webloc_xml():
    assert f.parse_link("x.webloc", plistlib.dumps({"URL": URL}, fmt=plistlib.FMT_XML)) == URL


def test_link_webloc_binary():
    assert f.parse_link("x.webloc", plistlib.dumps({"URL": URL}, fmt=plistlib.FMT_BINARY)) == URL


def test_link_rejects_javascript():
    assert f.parse_link("x.url", b"[InternetShortcut]\nURL=javascript:alert(1)\n") is None


def test_link_rejects_data():
    assert f.parse_link("x.webloc", plistlib.dumps({"URL": "data:text/html,x"})) is None


def test_link_rejects_file():
    assert f.parse_link("x.url", b"[InternetShortcut]\nURL=file:///etc/passwd\n") is None


def test_link_rejects_relative():
    assert f.parse_link("x.url", b"[InternetShortcut]\nURL=/book\n") is None


def test_link_rejects_no_section():
    assert f.parse_link("x.url", b"URL=https://example.com\n") is None


def test_link_rejects_garbage_plist():
    assert f.parse_link("x.webloc", b"\x00\x01not a plist") is None


def test_link_size_cap():
    body = f"[InternetShortcut]\nURL={URL}\n".encode().ljust(f.MAX_LINK_BYTES + 1, b" ")
    assert f.parse_link("x.url", body) is None


def test_link_non_ascii_url():
    """Review Focus 5."""
    url = "https://bücher.example/ü"
    assert f.parse_link("x.url", f"[InternetShortcut]\nURL={url}\n".encode()) == url
