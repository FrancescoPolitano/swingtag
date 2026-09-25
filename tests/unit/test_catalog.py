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


def reasons(item):
    return [a.split(": ")[0] for a in item.anomalies]


def test_one_resource_entry_label():
    item = build(obj("10 Care sheet/care.pdf"))
    [b] = item.buttons
    assert (b.label, b.context, b.order, b.kind) == ("Care sheet", "", 10, "document")


def test_many_resources_entry():
    item = build(obj("20 Photos/a.jpg"), obj("20 Photos/b.jpg"))
    assert [(b.label, b.context) for b in item.buttons] == [("a", "Photos"), ("b", "Photos")]


def test_order_across_entries():
    item = build(obj("20 B/x.pdf"), obj("10 A/x.pdf"), obj("C/x.pdf"))
    assert [b.label for b in item.buttons] == ["A", "B", "C"]


def test_file_in_item_root():
    item = build(obj("readme.pdf"))
    assert item.buttons == [] and reasons(item) == ["file in item root"]


def test_too_deep():
    item = build(obj("10 A/sub/x.pdf"))
    assert item.buttons == [] and reasons(item) == ["deeper than entry level"]


def test_unknown_extension():
    item = build(obj("10 A/x.docx"))
    assert item.buttons == [] and reasons(item) == ["format not accepted"]


def test_folder_placeholder():
    item = build(cat.SourceObject(key=PREFIX + "10 A/"))
    assert item.buttons == [] and item.anomalies == []


def test_ignored_names_silent():
    item = build(obj("10 A/.DS_Store"), obj("_draft/x.pdf"), obj("10 A/.pdf"))
    assert item.buttons == [] and item.anomalies == []


def test_mixed_entry():
    item = build(obj("10 A/x.pdf"), obj("10 A/y.docx"))
    assert [b.filename for b in item.buttons] == ["x.pdf"]
    assert reasons(item) == ["format not accepted"]


def test_nfc_nfd_single_button():
    nfd = unicodedata.normalize("NFD", "10 Menù/a.pdf")
    item = build(obj("10 Menù/a.pdf"), obj(nfd, day=2))
    assert len(item.buttons) == 1


def test_public_path_lowercase_ext():
    [b] = build(obj("10 Clip/Pruning.MP4")).buttons
    assert b.public_key == f"public/{TOKEN}/clip/pruning.mp4"
    assert b.href == f"/{TOKEN}/clip/pruning.mp4"
    assert b.content_type == "video/mp4"


def test_slug_collision_entries():
    item = build(obj("10 Care 1/x.pdf"), obj("20 Care-1/y.pdf"))
    assert [b.href for b in item.buttons] == [f"/{TOKEN}/care-1/x.pdf", f"/{TOKEN}/care-1-2/y.pdf"]


def test_too_large_resource():
    item = build(obj("10 A/big.mp4", size=cat.MAX_COPY_BYTES + 1))
    assert item.buttons == [] and reasons(item) == ["too large for single copy"]


def test_multi_dot_filename():
    """Review Focus 3."""
    item = build(obj("10 Menus/menu.v2.final.pdf"), obj("10 Menus/other.pdf"))
    assert [b.label for b in item.buttons] == ["menu.v2.final", "other"]
