"""Unit tests for scripts/plates.py."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import plates  # noqa: E402

TOKENS = [f"{c}{c}k9m2p7qhv4" for c in "abcdefghijkmnpqrstuvwxyz"][:20]


class StubPaginator:
    def __init__(self, keys, page_size=7):
        self.keys, self.page_size = keys, page_size

    def paginate(self, Bucket, Prefix):
        keys = [k for k in self.keys if k.startswith(Prefix)]
        for i in range(0, len(keys), self.page_size):
            yield {"Contents": [{"Key": k} for k in keys[i:i + self.page_size]]}


class StubS3:
    def __init__(self, keys):
        self.keys = keys

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return StubPaginator(self.keys)


def keys():
    out = []
    for i, token in enumerate(TOKENS):
        collection = "Vivaio Radici Lente" if i < 10 else "The Brine Hour"
        out.append(f"source/{collection}/Plant {i:02d} · {token}/10 Sheet/sheet.pdf")
        out.append(f"source/{collection}/Plant {i:02d} · {token}/20 Photo/photo.jpg")
    out.append("source/Vivaio Radici Lente/New plant/10 Sheet/sheet.pdf")  # not christened
    out.append("public/xxxk9m2p7qhv4/index.html")
    return out


def test_list_items_christened_only():
    items = plates.list_items(StubS3(keys()), "bucket", "source/")
    assert len(items) == 20
    assert all(token in TOKENS for _, _, token in items)
    assert ("Vivaio Radici Lente", "Plant 00", TOKENS[0]) in items


def streams(pdf):
    return re.findall(rb"stream\n(.*?)\nendstream", pdf, re.S)


def test_plates_grid():
    items = plates.list_items(StubS3(keys()), "bucket", "source/")
    pdf = plates.plates_pdf(items, "https://d1.cloudfront.net")
    assert b"/Count 2" in pdf
    page1, page2 = streams(pdf)
    assert page1.count(b"(Plant ") == 18 and page2.count(b"(Plant ") == 2
    for i in range(20):
        assert f"(Plant {i:02d})".encode() in pdf
    assert b"(New plant)" not in pdf
    assert b"(Vivaio Radici Lente)" in pdf and b"(The Brine Hour)" in pdf


def test_cell_content_fits():
    """QR, quiet zone and text fit inside one cell."""
    assert plates.TOP_PAD + plates.QR_SIDE + plates.TEXT_BLOCK <= plates.CELL_H
    assert plates.QR_BORDER >= 4


def test_ignored_names_get_no_plate():
    """ignored collections or items never get a page."""
    extra = ["source/_archive/Old · aak9m2p7qhv4/10 A/a.pdf", "source/C/.Hidden · bbk9m2p7qhv4/10 A/a.pdf"]
    assert plates.list_items(StubS3(extra), "bucket", "source/") == []


def test_prefix_without_slash():
    assert len(plates.list_items(StubS3(keys()), "bucket", "source")) == 20


def test_duplicate_token_single_plate():
    dup = ["source/C/A · aak9m2p7qhv4/10 A/a.pdf", "source/C/B · aak9m2p7qhv4/10 A/a.pdf"]
    assert [i[1] for i in plates.list_items(StubS3(dup), "bucket", "source/")] == ["A"]


def test_long_label_truncated():
    pdf = plates.plates_pdf([("C", "x" * 80, "aak9m2p7qhv4")], "https://d1.cloudfront.net")
    assert b"x" * 80 not in pdf and "…".encode("cp1252") in pdf


def test_main_no_items_exits_nonzero(tmp_path, capsys):
    code = plates.main(["bucket", "https://d1", "-o", str(tmp_path / "p.pdf")], s3=StubS3([]))
    assert code == 1 and not (tmp_path / "p.pdf").exists()
