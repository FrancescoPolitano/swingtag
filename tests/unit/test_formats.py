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
