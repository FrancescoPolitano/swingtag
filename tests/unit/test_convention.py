"""Unit tests for convention.py (TEST-PLAN 2.1)."""
import unicodedata

from swingtag import convention as c


def test_normalize_merges_nfd():
    nfd = "Men" + "ù"
    assert nfd != "Menù"
    assert c.normalize(nfd) == c.normalize("Menù")
    assert len(c.normalize(nfd)) == 4


def test_parse_order_space():
    assert c.parse_order("10 Lunch") == (10, "Lunch")


def test_parse_order_dot():
    assert c.parse_order("10. Lunch") == (10, "Lunch")


def test_parse_order_dash():
    assert c.parse_order("10 - Lunch") == (10, "Lunch")


def test_parse_order_paren():
    assert c.parse_order("10) Lunch") == (10, "Lunch")


def test_parse_order_digits_only():
    assert c.parse_order("10") == (None, "10")


def test_parse_order_inner_number():
    assert c.parse_order("Table 3 north") == (None, "Table 3 north")


def test_parse_order_seven_digits():
    assert c.parse_order("1234567 X") == (None, "1234567 X")


def test_parse_order_leading_zeros():
    """Review Focus 4."""
    assert c.parse_order("010 Lunch") == (10, "Lunch")


def _sorted(names):
    return sorted(names, key=lambda n: c.sort_key(*c.parse_order(n)))


def test_sort_numbered_first():
    assert _sorted(["b", "20 a", "a", "10 c"]) == ["10 c", "20 a", "a", "b"]


def test_sort_case_insensitive():
    assert _sorted(["beta", "Alpha"]) == ["Alpha", "beta"]


def test_ignored_dot_underscore():
    assert c.is_ignored(".hidden")
    assert c.is_ignored("_draft.pdf")


def test_ignored_system_files():
    for name in [".DS_Store", "Thumbs.db", "desktop.ini", "Icon\r"]:
        assert c.is_ignored(name), name


def test_not_ignored_regular():
    assert not c.is_ignored("menu.pdf")


def test_separator_is_middle_dot():
    assert c.SEPARATOR == " · "
    assert unicodedata.normalize("NFC", c.SEPARATOR) == c.SEPARATOR
