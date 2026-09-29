"""Unit tests for scripts/pdfmin.py."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pdfmin  # noqa: E402


def two_pages():
    return pdfmin.make_pdf_pages([
        [pdfmin.text(72, 720, 18, "Menu (pranzo) \\ cena"), pdfmin.rect(72, 600, 100, 20)],
        [pdfmin.text(72, 720, 12, "Pagina due: caffè")],
    ])


def test_pdfmin_valid():
    pdf = two_pages()
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.rstrip().endswith(b"%%EOF")
    startxref = int(re.search(rb"startxref\s+(\d+)", pdf).group(1))
    assert pdf[startxref:startxref + 4] == b"xref"
    table = pdf[startxref:].split(b"trailer")[0].splitlines()[2:]
    offsets = [int(line.split()[0]) for line in table if line.strip()]
    for number, offset in enumerate(offsets[1:], start=1):
        assert pdf[offset:].startswith(f"{number} 0 obj".encode()), number


def test_pdfmin_page_count():
    assert b"/Count 2" in two_pages()


def test_pdfmin_escapes_strings():
    pdf = two_pages()
    assert rb"(Menu \(pranzo\) \\ cena)" in pdf


def test_pdfmin_latin1_text():
    assert "caffè".encode("latin-1") in two_pages()


def test_pdfmin_cp1252_typography():
    """WinAnsi is cp1252, so macOS typography must survive."""
    pdf = pdfmin.make_pdf_pages([[pdfmin.text(72, 720, 12, "L’olivo “Moka” – 5 €")]])
    assert "L’olivo “Moka” – 5 €".encode("cp1252") in pdf


def test_pdfmin_no_pages_gives_one_blank_page():
    assert b"/Count 1" in pdfmin.make_pdf_pages([])
