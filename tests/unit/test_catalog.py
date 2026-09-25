"""Unit tests for catalog.py (TEST-PLAN 2.4)."""
import plistlib
import unicodedata
from datetime import datetime, timezone

from swingtag import catalog as cat

SRC, PUB, TOKEN = "source/", "public/", "3xk9m2p7qhv4"
PREFIX = f"source/Vivaio/Olivo · {TOKEN}/"


def obj(rel, size=10, day=1, prefix=PREFIX):
    return cat.SourceObject(key=prefix + rel, etag=f"e-{rel}", size=size,
                            modified=datetime(2026, 9, day, tzinfo=timezone.utc))


def build(*objs, links=None, prefix=PREFIX):
    return cat.build_item(SRC, PUB, prefix, list(objs), links or {})


def test_item_prefix_depth():
    assert cat.item_prefix(SRC, "source/C") is None
    assert cat.item_prefix(SRC, "source/C/I") is None
    assert cat.item_prefix(SRC, "source/C/I/x.pdf") == "source/C/I/"
    assert cat.item_prefix(SRC, "source/C/I/10 A/x.pdf") == "source/C/I/"
    assert cat.item_prefix(SRC, "public/C/I/x.pdf") is None


def test_split_prefix_nfc():
    nfd = unicodedata.normalize("NFD", "source/Città/Menù · 3xk9m2p7qhv4/")
    assert cat.split_prefix(SRC, nfd) == ("Città", "Menù · 3xk9m2p7qhv4")


def test_untokenised_item():
    item = build(obj("10 A/x.pdf", prefix="source/Vivaio/Olivo/"), prefix="source/Vivaio/Olivo/")
    assert item.token == ""
    assert item.label == "Olivo"


def test_empty_label_item():
    """Review Focus 2."""
    prefix = f"source/Vivaio/ · {TOKEN}/"
    item = build(obj("10 A/x.pdf", prefix=prefix), prefix=prefix)
    assert (item.label, item.token, item.collection) == ("", TOKEN, "Vivaio")
