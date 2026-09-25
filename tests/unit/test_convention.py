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


SECRET = "test-secret"


def test_token_alphabet_and_length():
    token = c.token_for("C", "L", SECRET)
    assert len(token) == 12
    assert set(token) <= set(c.TOKEN_ALPHABET)
    assert not set(token) & set("lo01")


def test_token_deterministic():
    assert c.token_for("Vivaio", "Olivo", SECRET) == c.token_for("Vivaio", "Olivo", SECRET)


def test_token_key_sensitive():
    assert c.token_for("Vivaio", "Olivo", "a") != c.token_for("Vivaio", "Olivo", "b")


def test_token_nfc_insensitive():
    nfd = unicodedata.normalize("NFD", "Città")
    assert c.token_for(nfd, "Olivo", SECRET) == c.token_for("Città", "Olivo", SECRET)


def test_token_boundary():
    assert c.token_for("ab", "c", SECRET) != c.token_for("a", "bc", SECRET)


def test_split_item_valid_token():
    assert c.split_item_name("Olivo · 3xk9m2p7qhv4") == ("Olivo", "3xk9m2p7qhv4")


def test_split_item_last_separator():
    assert c.split_item_name("Olivo · north · 3xk9m2p7qhv4") == ("Olivo · north", "3xk9m2p7qhv4")


def test_split_item_invalid_tail():
    assert c.split_item_name("Olive · north terrace") == ("Olive · north terrace", None)


def test_split_item_bad_alphabet():
    assert c.split_item_name("Olivo · 3xk9m2p7qhv0") == ("Olivo · 3xk9m2p7qhv0", None)


def test_with_token_roundtrip():
    token = c.token_for("Vivaio", "Olivo", SECRET)
    assert c.split_item_name(c.with_token("Olivo", token)) == ("Olivo", token)


def test_empty_label_split():
    """Review Focus 2: a folder that is only separator and token."""
    assert c.split_item_name(" · 3xk9m2p7qhv4") == ("", "3xk9m2p7qhv4")


def test_slug_accents():
    assert c.slug("Manutenzione perché", "entry") == "manutenzione-perche"


def test_slug_table_letters():
    assert [c.slug(v, "entry") for v in ["Straße", "Œuvre", "Ølstue", "Łódź"]] == [
        "strasse",
        "oeuvre",
        "olstue",
        "lodz",
    ]


def test_slug_fallback():
    assert c.slug("★★★", "entry") == "entry"
    assert c.slug("★★★", "file") == "file"


def test_unique_slug_collision():
    taken: set[str] = set()
    assert c.unique_slug("Care/1", taken, "entry") == "care-1"
    assert c.unique_slug("Care 1", taken, "entry") == "care-1-2"
    assert c.unique_slug("Care 1", taken, "entry") == "care-1-3"
