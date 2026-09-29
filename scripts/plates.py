#!/usr/bin/env python3
"""Printable A4 sheet with the QR code, label and collection of every item.

Reads the source zone listing: an item appears once it has been christened (its
folder name carries a token). The QR codes are drawn as vector squares at error
correction level Q, like the published qr.svg.

Usage: python3 scripts/plates.py <bucket> <base-url> [-o build/plates.pdf] [--prefix source/]
Needs boto3 and AWS credentials only for the listing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import qrcode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdfmin import A4, make_pdf_pages, rect, text  # noqa: E402
from swingtag.catalog import item_prefix, split_prefix  # noqa: E402
from swingtag.convention import is_ignored, split_item_name  # noqa: E402

COLUMNS, ROWS = 3, 6
MARGIN_X, MARGIN_Y = 42.0, 48.0
CELL_W = (A4[0] - 2 * MARGIN_X) / COLUMNS
CELL_H = (A4[1] - 2 * MARGIN_Y) / ROWS
QR_SIDE = 88.0      # includes the quiet zone below
QR_BORDER = 4       # modules of quiet zone, as the QR standard asks
TOP_PAD = 4.0       # from the top of the cell to the top of the code
TEXT_BLOCK = 26.0   # label and collection lines under the code, descenders included
MAX_LABEL = 34      # characters of the bold label at 9 pt that fit in a cell


def list_items(s3, bucket: str, source_prefix: str = "source/") -> list[tuple[str, str, str]]:
    """(collection, label, token) of every christened item, sorted; one plate per token."""
    source_prefix = source_prefix.rstrip("/") + "/"
    found: dict[str, tuple[str, str, str]] = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=source_prefix):
        for entry in page.get("Contents", []):
            prefix = item_prefix(source_prefix, entry["Key"])
            if prefix is None:
                continue
            collection, folder = split_prefix(source_prefix, prefix)
            if is_ignored(collection) or is_ignored(folder):
                continue  # never published, so a plate would lead to a 404
            label, token = split_item_name(folder)
            # Duplicate tokens: the publisher serves the lexically smallest prefix.
            if token and (token not in found or prefix < found[token][0]):
                found[token] = (prefix, collection, label)
    items = [(collection, label, token) for token, (_, collection, label) in found.items()]
    return sorted(items, key=lambda i: (i[0].casefold(), i[1].casefold(), i[2]))


def _qr_commands(url: str, x: float, y: float, side: float) -> list[str]:
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, border=QR_BORDER)
    code.add_data(url)
    code.make(fit=True)
    matrix = code.get_matrix()  # rows top to bottom, border included
    module = side / len(matrix)
    overlap = module * 0.02  # hides anti-aliasing seams between adjacent squares
    commands = []
    for r, row in enumerate(matrix):
        c = 0
        while c < len(row):
            if not row[c]:
                c += 1
                continue
            start = c
            while c < len(row) and row[c]:
                c += 1
            # One rectangle per run of dark modules; PDF y grows upwards (row 0 is the top).
            commands.append(rect(x + start * module, y + side - (r + 1) * module - overlap,
                                 (c - start) * module + overlap, module + overlap))
    return commands


def plates_pdf(items: list[tuple[str, str, str]], base_url: str) -> bytes:
    per_page = COLUMNS * ROWS
    pages = []
    for start in range(0, len(items), per_page) or [0]:
        commands: list[str] = []
        for index, (collection, label, token) in enumerate(items[start:start + per_page]):
            col, row = index % COLUMNS, index // COLUMNS
            left = MARGIN_X + col * CELL_W
            top = A4[1] - MARGIN_Y - row * CELL_H
            qr_x = left + (CELL_W - QR_SIDE) / 2
            qr_y = top - TOP_PAD - QR_SIDE
            commands += _qr_commands(f"{base_url.rstrip('/')}/{token}", qr_x, qr_y, QR_SIDE)
            name = label or collection
            if len(name) > MAX_LABEL:
                name = name[: MAX_LABEL - 1] + "\u2026"
            commands.append(text(left + 6, qr_y - 10, 9, name, bold=True))
            commands.append(text(left + 6, qr_y - 20, 7.5, collection[:MAX_LABEL + 6]))
        pages.append(commands)
    return make_pdf_pages(pages)


def main(argv: list[str] | None = None, s3=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bucket")
    parser.add_argument("base_url")
    parser.add_argument("-o", "--output", default="build/plates.pdf")
    parser.add_argument("--prefix", default="source/")
    args = parser.parse_args(argv)

    if s3 is None:
        import boto3  # only needed for the real listing

        s3 = boto3.client("s3")
    items = list_items(s3, args.bucket, args.prefix)
    if not items:
        print(f"no christened items under s3://{args.bucket}/{args.prefix}", file=sys.stderr)
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(plates_pdf(items, args.base_url))
    print(f"{len(items)} plates written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
