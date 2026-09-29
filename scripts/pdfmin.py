"""Minimal PDF writer: pages made of text lines and filled rectangles.

Standard library only. Text uses the built-in Helvetica font with WinAnsi encoding,
which is cp1252: typographic quotes, dashes and the euro sign survive; characters outside
cp1252 are replaced with '?'. Used by plates.py.
"""

from __future__ import annotations

A4 = (595, 842)  # points


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text(x: float, y: float, size: float, value: str, bold: bool = False) -> str:
    """Drawing commands for one line of text with its baseline at (x, y)."""
    font = "F2" if bold else "F1"
    return f"BT /{font} {size:g} Tf {x:.2f} {y:.2f} Td ({_escape(value)}) Tj ET"


def rect(x: float, y: float, width: float, height: float, gray: float = 0.0) -> str:
    """A filled rectangle; gray 0 is black, 1 is white."""
    return f"{gray:g} g {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f 0 g"


def make_pdf_pages(pages: list[list[str]], size: tuple[int, int] = A4) -> bytes:
    """A PDF whose pages draw the given command lists, in order."""
    objects: list[bytes] = []

    def add(body: str | bytes) -> int:
        objects.append(body.encode("latin-1") if isinstance(body, str) else body)
        return len(objects)

    catalog = add("")  # filled once the page tree number is known
    tree = add("")
    helvetica = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    helvetica_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
                         "/Encoding /WinAnsiEncoding >>")
    kids = []
    for commands in pages or [[]]:  # a PDF needs at least one page
        stream = "\n".join(commands).encode("cp1252", "replace")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        kids.append(add(
            f"<< /Type /Page /Parent {tree} 0 R /MediaBox [0 0 {size[0]} {size[1]}] "
            f"/Resources << /Font << /F1 {helvetica} 0 R /F2 {helvetica_bold} 0 R >> >> "
            f"/Contents {content} 0 R >>"
        ))
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {tree} 0 R >>".encode()
    objects[tree - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    ).encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, catalog, xref)
    return bytes(out)
