# swingtag core library: implementation plan (plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-Python core of swingtag (naming rules, formats, theme, wording, item model, page rendering, QR code) with its unit tests and CI, with no AWS dependency.

**Architecture:** Seven pure modules under `src/swingtag/`, each with one responsibility and the exact interfaces of SPEC 10.3: `convention` (names), `formats` (file kinds, link files), `i18n` (fixed wording, dates), `theme` (theme model), `catalog` (folder listing to item model), `render` (item to HTML), `qr` (URL to SVG). They take and return plain values; the publisher (plan 2) will be the only AWS-aware code.

**Tech Stack:** Python 3.12, `qrcode==8.2` (runtime), pytest, `opencv-python-headless` (dev, QR decoding test), GitHub Actions, Terraform 1.9 (fmt only in CI for now).

**Verified:** every code block of this plan was assembled in a scratch copy and its tests run before review: 111 passed (Python 3.12.9, qrcode 8.2). That dry run found the `Icon\r` bug fixed in Task 2.

**Spec:** `spec/SPEC.md` 1.1 (approved), `spec/TEST-PLAN.md` 1.0 (approved), `spec/ASSUMPTIONS.md`. Backlog keys in brackets refer to `plans/backlog.py`.

## Global Constraints

- Python `>=3.12`; the only runtime dependency is `qrcode==8.2` (A-7). No `boto3` import in any module of this plan.
- All code, comments, identifiers and test names in English (A-1).
- Every folder and file name is normalised to NFC before any use (FR-6).
- Separator ` · ` (space, U+00B7, space); token alphabet `abcdefghijkmnpqrstuvwxyz23456789`; token length 12 (FR-2, FR-3).
- Order prefix regex `^(\d{1,6})\s*(?:[.)\-]\s*|\s+)(.+)$` (FR-5).
- Transliteration table before NFKD: `ß→ss ẞ→SS æ→ae Æ→AE œ→oe Œ→OE ø→o Ø→O đ→d Đ→D ł→l Ł→L þ→th Þ→Th`; slug fallbacks `entry` and `file` (FR-38).
- Anomaly reasons are exactly: `file in item root`, `deeper than entry level`, `format not accepted`, `too large for single copy`, `invalid link`, `duplicate token`, `key outside convention` (SPEC FR-9, AMB-4).
- Pages: no JavaScript, one `<style>`, under 15,360 bytes with ten buttons, secondary tones only via `color-mix()` of `--t`, `--bg`, `--p` (FR-30, FR-31).
- Link schemes accepted: `http`, `https`, with a host; link files larger than 65,536 bytes are not read (FR-8).
- Naming rule: the literal `swingtag` appears under `src/` only in `src/swingtag/__init__.py`; imports inside the package are relative (SPEC 10.2).
- Test function names are the lowercase test-plan names (`U-CONV-03 parse_order_dot` → `test_parse_order_dot`).

## Review Focus

Inputs the spec implies but the test plan does not exercise, most likely first. Each has a test added to the owning task.

1. **Unbreakable long labels** (a 120-character name with no spaces): the page must not overflow; `h1` and labels carry `word-break` / `overflow-wrap`. Test `test_long_unbreakable_label_wraps` in Task 12.
2. **Item folder with an empty label** (` · 3xk9m2p7qhv4`): rendering must not crash and the `h1` falls back to the collection name. Tests `test_empty_label_item` (Task 9) and `test_empty_label_heading_falls_back` (Task 12).
3. **File names with several dots** (`menu.v2.final.pdf`): the kind comes from the last extension, the label keeps the inner dots (`menu.v2.final`). Test `test_multi_dot_filename` in Task 10.
4. **Order prefixes with leading zeros** (`010 Lunch`): order 10, label `Lunch`. Test `test_parse_order_leading_zeros` in Task 2.
5. **Non-ASCII link targets** (`https://bücher.example/ü`): accepted by `parse_link` (scheme and host present) and HTML-escaped in the page. Tests `test_link_non_ascii_url` (Task 6) and `test_escaping` extended (Task 12).

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | package metadata, dependencies, pytest configuration |
| `Makefile` | `venv`, `test` targets (more targets come with later plans) |
| `.github/workflows/ci.yml` | tests, coverage check of the test plan, `terraform fmt -check` |
| `src/swingtag/__init__.py` | package name and version, the only place with the literal name |
| `src/swingtag/convention.py` | NFC, order prefixes, sorting, ignore rules, tokens, slugs |
| `src/swingtag/formats.py` | `Format`, `FORMATS`, `lookup()`, `parse_link()` |
| `src/swingtag/i18n.py` | `STRINGS`, `format_date()` |
| `src/swingtag/theme.py` | `Colors`, `Theme`, `DEFAULT_THEME`, `from_json()` |
| `src/swingtag/catalog.py` | `SourceObject`, `Button`, `Item`, `item_prefix()`, `split_prefix()`, `build_item()`, `published_keys()` |
| `src/swingtag/render.py` | `render_page()`, `render_not_found()` |
| `src/swingtag/qr.py` | `qr_svg()` |
| `tests/unit/test_*.py` | one test module per source module, plus `test_repo.py` |

---

### Task 1: Project scaffolding and CI [scaffold, ci]

**Files:**
- Create: `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `src/swingtag/__init__.py`, `tests/unit/test_repo.py`
- Modify: `.gitignore` (add `.venv/` if missing; it is already listed)

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `swingtag` with `NAME = "swingtag"` and `__version__ = "0.1.0"`; `make venv`, `make test`.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_repo.py`:

```python
"""Repository-level checks (TEST-PLAN 2.8)."""
from pathlib import Path

import swingtag

ROOT = Path(__file__).resolve().parents[2]


def test_package_imports():
    assert swingtag.NAME == "swingtag"
    assert swingtag.__version__ == "0.1.0"


def test_name_only_in_allowed_places():
    """U-REPO-04: the literal project name appears under src/ only in __init__.py."""
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src").rglob("*.py")
        if path.name != "__init__.py" and swingtag.NAME in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
```

- [ ] **Step 2: Create packaging so the test can run, and run it to see it fail**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "swingtag"
version = "0.1.0"
description = "A linktree for physical things: a folder on S3 becomes a permanent page behind a printed QR code"
requires-python = ">=3.12"
license = "MIT"
dependencies = ["qrcode==8.2"]

[project.optional-dependencies]
dev = ["pytest>=8", "opencv-python-headless>=4.9"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

`Makefile`:

```make
SHELL := /bin/bash
PYTHON ?= python3
PY := .venv/bin/python

.PHONY: help venv test

help: ## List targets
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t16

venv: ## Create .venv with runtime and dev dependencies
	$(PYTHON) -m venv .venv && $(PY) -m pip install --quiet --upgrade pip && $(PY) -m pip install --quiet -e '.[dev]'

test: ## Run the unit tests
	$(PY) -m pytest -q
```

Run: `make venv && make test`
Expected: FAIL, `ModuleNotFoundError: No module named 'swingtag'` (the package directory does not exist yet).

- [ ] **Step 3: Write the package**

`src/swingtag/__init__.py`:

```python
"""swingtag: a folder on S3 becomes a permanent page behind a printed QR code."""

NAME = "swingtag"
__version__ = "0.1.0"
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `make venv && make test`
Expected: `2 passed`.

- [ ] **Step 5: Add CI**

`.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e '.[dev]'
      - run: python -m pytest -q
      - run: python spec/check_coverage.py
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9.8"
      - run: terraform fmt -check -recursive
```

- [ ] **Step 6: Commit and verify CI**

```bash
git add pyproject.toml Makefile .github/workflows/ci.yml src/swingtag/__init__.py tests/unit/test_repo.py
git commit -m "Scaffold package, test runner and CI"
git push
gh run watch --exit-status   # personal gh account active
```

Expected: the `ci` run succeeds. Then, once, prove CI fails on formatting: create `terraform/tmp.tf` containing `variable "x" {default=1}`, push, see `terraform fmt -check` fail, remove the file, push again, see it pass (backlog `ci` acceptance criterion).

---

### Task 2: convention.py, names and ordering [core-names]

**Files:**
- Create: `src/swingtag/convention.py`, `tests/unit/test_convention.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SEPARATOR: str`, `normalize(value: str) -> str`, `parse_order(name: str) -> tuple[int | None, str]`, `sort_key(order: int | None, label: str) -> tuple[int, int, str]`, `is_ignored(name: str) -> bool`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_convention.py`:

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_convention.py -q`
Expected: FAIL, `ImportError: cannot import name 'convention'`.

- [ ] **Step 3: Implement**

`src/swingtag/convention.py`:

```python
"""Naming rules: separator, order prefixes, Unicode, ignore rules, tokens and slugs.

Everything that interprets folder and file names lives here. Pure functions on
strings: nothing in this module knows about AWS.
"""

from __future__ import annotations

import re
import unicodedata

# Between the readable item label and its token. Space, middle dot (U+00B7), space:
# it does not occur in ordinary names and stays readable in file managers.
SEPARATOR = " · "

# Order prefix: "10 Lunch", "10. Lunch", "10 - Lunch", "10) Lunch".
_ORDER_RE = re.compile(r"^(\d{1,6})\s*(?:[.)\-]\s*|\s+)(.+)$")

# Names that are not content and must not be reported as anomalies.
_SYSTEM_NAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini", "icon\r"})


def normalize(value: str) -> str:
    """Composed Unicode form.

    macOS uploads produce decomposed accents: without this step the same name
    typed on macOS and on Windows is two different strings that look identical.
    """
    return unicodedata.normalize("NFC", value)


def parse_order(name: str) -> tuple[int | None, str]:
    """Split an optional order prefix off a name: returns (order, label)."""
    clean = normalize(name).strip()
    match = _ORDER_RE.match(clean)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None, clean


def sort_key(order: int | None, label: str) -> tuple[int, int, str]:
    """Numbered names first by number, then the others alphabetically, case-insensitive."""
    if order is None:
        return (1, 0, label.casefold())
    return (0, order, label.casefold())


def is_ignored(name: str) -> bool:
    """Names skipped silently: hidden, underscored, empty and OS housekeeping files."""
    raw = normalize(name)
    # Checked before stripping: macOS folder icons are named "Icon\r", and strip()
    # would remove the carriage return that identifies them.
    if raw.casefold() in _SYSTEM_NAMES:
        return True
    clean = raw.strip()
    if not clean:
        return True
    if clean.startswith((".", "_")):
        return True
    return clean.casefold() in _SYSTEM_NAMES
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_convention.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/convention.py tests/unit/test_convention.py
git commit -m "convention: NFC, order prefixes, sorting, ignore rules"
```

---

### Task 3: convention.py, tokens [core-tokens]

**Files:**
- Modify: `src/swingtag/convention.py` (append), `tests/unit/test_convention.py` (append)

**Interfaces:**
- Consumes: `normalize`, `SEPARATOR` (Task 2).
- Produces: `TOKEN_ALPHABET: str`, `TOKEN_LENGTH: int`, `is_token(value: str) -> bool`, `token_for(collection: str, label: str, secret: str) -> str`, `split_item_name(folder: str) -> tuple[str, str | None]`, `with_token(label: str, token: str) -> str`.

- [ ] **Step 1: Write the failing tests** (append to `tests/unit/test_convention.py`)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_convention.py -q`
Expected: FAIL, `AttributeError: module 'swingtag.convention' has no attribute 'token_for'`.

- [ ] **Step 3: Implement** (append to `src/swingtag/convention.py`; add `import hashlib` and `import hmac` at the top with the other imports)

```python
# Token alphabet: lowercase letters and digits without l, o, 0, 1, which get
# confused when a code is read aloud or printed small. 32 symbols x 12 = 60 bits.
TOKEN_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
TOKEN_LENGTH = 12
_TOKEN_RE = re.compile(rf"^[{TOKEN_ALPHABET}]{{{TOKEN_LENGTH}}}$")


def is_token(value: str) -> bool:
    return bool(_TOKEN_RE.match(value))


def token_for(collection: str, label: str, secret: str) -> str:
    """Token of an item, derived from its names with a secret key.

    Deterministic on purpose: two concurrent runs that find the same untokenised
    folder compute the same value and converge on one address instead of creating
    twin items. Unpredictable without the key. 256 is a multiple of 32, so reducing
    each byte modulo 32 is uniform.
    """
    material = f"{normalize(collection)}\x00{normalize(label)}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).digest()
    return "".join(TOKEN_ALPHABET[byte % len(TOKEN_ALPHABET)] for byte in digest[:TOKEN_LENGTH])


def split_item_name(folder: str) -> tuple[str, str | None]:
    """Split an item folder name into (label, token); token is None when absent.

    The last separator wins, so a label may itself contain the separator. A tail
    that is not a valid token is part of the label.
    """
    name = normalize(folder).strip()
    # Stripping turns " · token" (empty label) into "· token": restore the leading space.
    probe = f" {name}" if name.startswith(SEPARATOR.lstrip()) else name
    label, sep, candidate = probe.rpartition(SEPARATOR)
    if sep and is_token(candidate.strip()):
        return label.strip(), candidate.strip()
    return name, None


def with_token(label: str, token: str) -> str:
    return f"{label.strip()}{SEPARATOR}{token}"
```

Note on `split_item_name`: only the full separator (space, dot, space) counts, so `Olivo·3xk9m2p7qhv4` is an untokenised label; the leading-space restore handles the empty-label folder of Review Focus 2.

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_convention.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/convention.py tests/unit/test_convention.py
git commit -m "convention: derived tokens and item name parsing"
```

---

### Task 4: convention.py, slugs [core-slugs]

**Files:**
- Modify: `src/swingtag/convention.py` (append), `tests/unit/test_convention.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `slug(value: str, fallback: str) -> str`, `unique_slug(value: str, taken: set[str], fallback: str) -> str`.

- [ ] **Step 1: Write the failing tests** (append)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_convention.py -q`
Expected: FAIL, `AttributeError: ... has no attribute 'slug'`.

- [ ] **Step 3: Implement** (append)

```python
# Letters with no ASCII decomposition: NFKD alone drops them ("Straße" -> "strae",
# spec/ASSUMPTIONS.md T-05), so they are replaced first.
_TRANSLITERATION = str.maketrans({
    "ß": "ss", "ẞ": "SS", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
    "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "þ": "th", "Þ": "Th",
})


def slug(value: str, fallback: str) -> str:
    """URL-safe form: ASCII, lowercase, hyphens. Accents are transliterated, not dropped."""
    decomposed = unicodedata.normalize("NFKD", value.translate(_TRANSLITERATION))
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii").casefold()
    hyphenated = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return hyphenated or fallback


def unique_slug(value: str, taken: set[str], fallback: str) -> str:
    """A slug not yet in `taken` (a numeric suffix resolves collisions); records it."""
    base = slug(value, fallback)
    candidate, counter = base, 2
    while candidate in taken:
        candidate = f"{base}-{counter}"
        counter += 1
    taken.add(candidate)
    return candidate
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_convention.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/convention.py tests/unit/test_convention.py
git commit -m "convention: slugs with transliteration table"
```

---

### Task 5: formats.py, format table [core-formats]

**Files:**
- Create: `src/swingtag/formats.py`, `tests/unit/test_formats.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Format(kind: str, content_type: str | None, extension: str)` frozen dataclass; `FORMATS: dict[str, Format]`; `lookup(filename: str) -> Format | None`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_formats.py`:

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_formats.py -q`
Expected: FAIL, `ImportError: cannot import name 'formats'`.

- [ ] **Step 3: Implement**

`src/swingtag/formats.py`:

```python
"""Accepted file kinds, their content types, and link files (FR-7, FR-8).

Pure: takes names and bytes, returns values. Nothing here knows about AWS.
"""

from __future__ import annotations

import configparser
import plistlib
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Format:
    kind: str                 # document | image | audio | video | link
    content_type: str | None  # None for links: they are read, not copied
    extension: str            # lowercase, with the dot


FORMATS: dict[str, Format] = {
    ext: Format(kind, ctype, ext)
    for ext, kind, ctype in [
        (".pdf", "document", "application/pdf"),
        (".jpg", "image", "image/jpeg"),
        (".jpeg", "image", "image/jpeg"),
        (".png", "image", "image/png"),
        (".webp", "image", "image/webp"),
        (".mp3", "audio", "audio/mpeg"),
        (".m4a", "audio", "audio/mp4"),
        (".mp4", "video", "video/mp4"),
        (".url", "link", None),
        (".webloc", "link", None),
    ]
}


def lookup(filename: str) -> Format | None:
    """Format of a file from its last extension, case-insensitive; None if not accepted."""
    stem, dot, ext = filename.rpartition(".")
    if not dot:
        return None
    return FORMATS.get(f".{ext.casefold()}")
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_formats.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/formats.py tests/unit/test_formats.py
git commit -m "formats: accepted kinds and lookup"
```

---

### Task 6: formats.py, link files [core-links]

**Files:**
- Modify: `src/swingtag/formats.py` (append), `tests/unit/test_formats.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `MAX_LINK_BYTES = 65536`; `parse_link(filename: str, body: bytes) -> str | None`.

Reference implementation: `spec/spikes/reference/link-parsing/parse_link.py` (PROVES the parsing and the whitelist; SHORTCUT: no size cap, which this task adds).

- [ ] **Step 1: Write the failing tests** (append)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_formats.py -q`
Expected: FAIL, `AttributeError: ... has no attribute 'parse_link'`.

- [ ] **Step 3: Implement** (append)

```python
MAX_LINK_BYTES = 65536
_ALLOWED_SCHEMES = frozenset({"http", "https"})


def parse_link(filename: str, body: bytes) -> str | None:
    """Target URL of a .url or .webloc file, or None if unreadable or not http(s).

    .url is an INI file ([InternetShortcut], key URL); .webloc is a property list,
    XML or binary (macOS writes binary when a link is dragged from a browser).
    """
    if len(body) > MAX_LINK_BYTES:
        return None
    name = filename.casefold()
    url: object = None
    if name.endswith(".url"):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read_string(body.decode("utf-8-sig", errors="replace"))
        except configparser.Error:
            return None
        url = parser.get("InternetShortcut", "URL", fallback=None)
    elif name.endswith(".webloc"):
        try:
            data = plistlib.loads(body)
        except Exception:  # plistlib raises several unrelated types on bad input
            return None
        url = data.get("URL") if isinstance(data, dict) else None
    if not isinstance(url, str):
        return None
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in _ALLOWED_SCHEMES or not parts.netloc:
        return None
    return url
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_formats.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/formats.py tests/unit/test_formats.py
git commit -m "formats: link files with scheme whitelist and size cap"
```

---

### Task 7: i18n.py [theme-i18n]

**Files:**
- Create: `src/swingtag/i18n.py`, `tests/unit/test_i18n.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `STRINGS: dict[str, dict[str, str]]` (locales `en`, `it`; keys of FR-14); `format_date(moment: datetime, locale: str, timezone: str) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_i18n.py`:

```python
"""Unit tests for i18n.py (TEST-PLAN 2.3)."""
from datetime import datetime, timezone

from swingtag import i18n

FR14 = {
    "updated": ("Updated on", "Aggiornato il"),
    "empty": ("Nothing is available here yet.", "Qui non c'è ancora nulla."),
    "not_found_title": ("Page not available", "Pagina non disponibile"),
    "not_found_body": (
        "This code does not match any published page. Check that you scanned the whole code.",
        "Questo codice non corrisponde a nessuna pagina pubblicata. Verifica di aver inquadrato il codice per intero.",
    ),
    "kind_document": ("Document", "Documento"),
    "kind_image": ("Image", "Immagine"),
    "kind_audio": ("Audio", "Audio"),
    "kind_video": ("Video", "Video"),
    "kind_link": ("Link", "Link"),
}
MOMENT = datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc)


def test_every_key_every_locale():
    for key, (en, it) in FR14.items():
        assert i18n.STRINGS["en"][key] == en
        assert i18n.STRINGS["it"][key] == it
    assert set(i18n.STRINGS["en"]) == set(FR14) == set(i18n.STRINGS["it"])


def test_date_it():
    assert i18n.format_date(MOMENT, "it", "Europe/Rome") == "25/09/2026 14:30"


def test_date_en():
    assert i18n.format_date(MOMENT, "en", "Europe/Rome") == "25 Sep 2026, 14:30"
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_i18n.py -q`
Expected: FAIL, `ImportError`.

- [ ] **Step 3: Implement**

`src/swingtag/i18n.py`:

```python
"""Fixed wording of the pages in each locale, and date formatting (FR-14, FR-33)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "updated": "Updated on",
        "empty": "Nothing is available here yet.",
        "not_found_title": "Page not available",
        "not_found_body": "This code does not match any published page. "
        "Check that you scanned the whole code.",
        "kind_document": "Document",
        "kind_image": "Image",
        "kind_audio": "Audio",
        "kind_video": "Video",
        "kind_link": "Link",
    },
    "it": {
        "updated": "Aggiornato il",
        "empty": "Qui non c'è ancora nulla.",
        "not_found_title": "Pagina non disponibile",
        "not_found_body": "Questo codice non corrisponde a nessuna pagina pubblicata. "
        "Verifica di aver inquadrato il codice per intero.",
        "kind_document": "Documento",
        "kind_image": "Immagine",
        "kind_audio": "Audio",
        "kind_video": "Video",
        "kind_link": "Link",
    },
}

# English month abbreviations spelled out: the Lambda runtime has only the C locale,
# so strftime("%b") cannot be trusted to follow the page locale.
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_date(moment: datetime, locale: str, timezone: str) -> str:
    """`25/09/2026 14:30` for it, `25 Sep 2026, 14:30` for en (and any other locale)."""
    local = moment.astimezone(ZoneInfo(timezone))
    if locale == "it":
        return local.strftime("%d/%m/%Y %H:%M")
    return f"{local.day} {_MONTHS_EN[local.month - 1]} {local.year}, {local:%H:%M}"
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_i18n.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/i18n.py tests/unit/test_i18n.py
git commit -m "i18n: fixed wording en/it and locale-independent dates"
```

---

### Task 8: theme.py [theme-model]

**Files:**
- Create: `src/swingtag/theme.py`, `tests/unit/test_theme.py`

**Interfaces:**
- Consumes: `i18n.STRINGS` (Task 7).
- Produces: `Colors(primary: str, background: str, text: str)`; `Theme(locale="en", timezone="UTC", logo=None, header=None, footer=None, notice=None, colors=DEFAULT_COLORS, colors_dark=DEFAULT_DARK, strings={})` with `string(key: str) -> str`; `DEFAULT_COLORS`, `DEFAULT_DARK`, `DEFAULT_THEME`; `from_json(body: bytes) -> Theme`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_theme.py`:

```python
"""Unit tests for theme.py (TEST-PLAN 2.3)."""
import json
import logging

from swingtag import theme as t

RESTAURANT = {
    "locale": "it",
    "timezone": "Europe/Rome",
    "logo": "logo.svg",
    "header": "Osteria Quattro Mestoli",
    "footer": "Via del Borgo 3",
    "notice": "Demo",
    "colors": {"primary": "#8a2d1c", "background": "#fbf7f2", "text": "#1f1b16"},
    "strings": {"updated": "Menu aggiornato il"},
}


def body(data):
    return json.dumps(data).encode()


def test_default_theme(caplog):
    assert t.from_json(b"") == t.DEFAULT_THEME
    with caplog.at_level(logging.WARNING):
        assert t.from_json(b"{not json") == t.DEFAULT_THEME
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_full_theme():
    theme = t.from_json(body(RESTAURANT))
    assert theme.locale == "it"
    assert theme.timezone == "Europe/Rome"
    assert theme.logo == "logo.svg"
    assert theme.header == "Osteria Quattro Mestoli"
    assert theme.footer == "Via del Borgo 3"
    assert theme.notice == "Demo"
    assert theme.colors == t.Colors("#8a2d1c", "#fbf7f2", "#1f1b16")


def test_bad_colour_falls_back(caplog):
    data = {**RESTAURANT, "colors": {**RESTAURANT["colors"], "primary": "red"}}
    with caplog.at_level(logging.WARNING):
        theme = t.from_json(body(data))
    assert theme.colors.primary == t.DEFAULT_COLORS.primary
    assert theme.colors.background == "#fbf7f2"
    assert any("primary" in r.getMessage() for r in caplog.records)


def test_bad_timezone_falls_back(caplog):
    with caplog.at_level(logging.WARNING):
        theme = t.from_json(body({**RESTAURANT, "timezone": "Mars/Olympus"}))
    assert theme.timezone == "UTC"
    assert any("timezone" in r.getMessage() for r in caplog.records)


def test_string_override():
    assert t.from_json(body(RESTAURANT)).string("updated") == "Menu aggiornato il"


def test_string_builtin():
    assert t.from_json(body(RESTAURANT)).string("empty") == "Qui non c'è ancora nulla."


def test_dark_only_when_given():
    assert t.from_json(body(RESTAURANT)).colors_dark is None
    dark = {"primary": "#e0a15a", "background": "#171412", "text": "#f2ede6"}
    assert t.from_json(body({**RESTAURANT, "colors_dark": dark})).colors_dark == t.Colors(**dark)
    assert t.DEFAULT_THEME.colors_dark is not None


def test_unknown_string_key_dropped(caplog):
    with caplog.at_level(logging.WARNING):
        theme = t.from_json(body({**RESTAURANT, "strings": {"updatd": "x"}}))
    assert "updatd" not in theme.strings
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_theme.py -q`
Expected: FAIL, `ImportError`.

- [ ] **Step 3: Implement**

`src/swingtag/theme.py`:

```python
"""The deployment theme as the publisher reads it (FR-12..FR-15).

Terraform validates theme.yaml strictly at plan time. Here the reading is
tolerant: whatever is missing or invalid falls back to a default and is logged,
so that a page is always published (EC-20, EC-21).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from .i18n import STRINGS

log = logging.getLogger(__name__)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_LOCALES = ("en", "it")


@dataclass(frozen=True)
class Colors:
    primary: str
    background: str
    text: str


DEFAULT_COLORS = Colors(primary="#1f5f8b", background="#f7f7f5", text="#1a1a1a")
DEFAULT_DARK = Colors(primary="#6fb3e0", background="#141619", text="#eef0f2")


@dataclass(frozen=True)
class Theme:
    locale: str = "en"
    timezone: str = "UTC"
    logo: str | None = None
    header: str | None = None
    footer: str | None = None
    notice: str | None = None
    colors: Colors = DEFAULT_COLORS
    colors_dark: Colors | None = DEFAULT_DARK
    strings: Mapping[str, str] = field(default_factory=dict)

    def string(self, key: str) -> str:
        """The operator's override if any, else the built-in text for the locale."""
        return self.strings.get(key) or STRINGS.get(self.locale, STRINGS["en"])[key]


DEFAULT_THEME = Theme()


def _text(data: dict, key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _colors(raw: object, default: Colors, name: str) -> Colors:
    raw = raw if isinstance(raw, dict) else {}
    values = {}
    for key in ("primary", "background", "text"):
        value = raw.get(key)
        if isinstance(value, str) and _HEX.match(value):
            values[key] = value
        else:
            log.warning("theme: invalid %s.%s %r, using default", name, key, value)
            values[key] = getattr(default, key)
    return Colors(**values)


def from_json(body: bytes) -> Theme:
    """Theme from the config/theme.json written by Terraform; tolerant of errors."""
    if not body.strip():
        return DEFAULT_THEME
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        log.warning("theme: config/theme.json is not valid JSON, using the default theme")
        return DEFAULT_THEME
    if not isinstance(data, dict):
        log.warning("theme: config/theme.json is not an object, using the default theme")
        return DEFAULT_THEME

    locale = data.get("locale", "en")
    if locale not in _LOCALES:
        log.warning("theme: invalid locale %r, using en", locale)
        locale = "en"

    timezone = data.get("timezone", "UTC")
    try:
        ZoneInfo(timezone)
    except Exception:  # ZoneInfoNotFoundError, ValueError, TypeError
        log.warning("theme: invalid timezone %r, using UTC", timezone)
        timezone = "UTC"

    known = STRINGS["en"].keys()
    strings = {}
    for key, value in (data.get("strings") or {}).items():
        if key in known and isinstance(value, str):
            strings[key] = value
        else:
            log.warning("theme: unknown or invalid strings.%s, ignored", key)

    return Theme(
        locale=locale,
        timezone=timezone,
        logo=_text(data, "logo"),
        header=_text(data, "header"),
        footer=_text(data, "footer"),
        notice=_text(data, "notice"),
        colors=_colors(data.get("colors"), DEFAULT_COLORS, "colors"),
        colors_dark=_colors(data["colors_dark"], DEFAULT_DARK, "colors_dark")
        if "colors_dark" in data else None,
        strings=strings,
    )
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_theme.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/theme.py tests/unit/test_theme.py
git commit -m "theme: tolerant theme model with defaults"
```

---

### Task 9: catalog.py, model and prefixes [core-catalog-model]

**Files:**
- Create: `src/swingtag/catalog.py`, `tests/unit/test_catalog.py`

**Interfaces:**
- Consumes: `convention.normalize`, `convention.split_item_name` (Tasks 2-3).
- Produces: `SourceObject(key: str, etag: str = "", size: int = 0, modified: datetime | None = None)`; `Button(order, label, context, kind, href, public_key, source_key, filename, content_type, etag, size, modified)`; `Item(collection, label, token, buttons, anomalies)` with properties `empty` and `updated_at`; `MAX_COPY_BYTES = 5 * 1024**3`; `item_prefix(source_prefix: str, key: str) -> str | None`; `split_prefix(source_prefix: str, prefix: str) -> tuple[str, str]`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_catalog.py`:

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_catalog.py -q`
Expected: FAIL, `ImportError`.

- [ ] **Step 3: Implement the model, prefixes and a `build_item` skeleton**

`src/swingtag/catalog.py`:

```python
"""From the flat listing of an item folder to the model its page represents.

Pure: receives the objects under one item prefix (and the bodies of its link
files) and returns an Item. Nothing here knows about AWS.

The menu is flat: one tap, one resource. An entry folder with one resource gives
one button titled like the folder; an entry with several resources gives one
button per resource, titled like the file, with the folder name as context.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from . import convention, formats

# Largest object a single CopyObject can copy (SPEC 10.13).
MAX_COPY_BYTES = 5 * 1024**3


@dataclass(frozen=True)
class SourceObject:
    key: str
    etag: str = ""
    size: int = 0
    modified: datetime | None = None


@dataclass(frozen=True)
class Button:
    order: int | None
    label: str
    context: str
    kind: str
    href: str               # absolute public path for files, external URL for links
    public_key: str | None  # None for links: they are not copied
    source_key: str
    filename: str
    content_type: str | None
    etag: str
    size: int
    modified: datetime | None


@dataclass
class Item:
    collection: str
    label: str
    token: str
    buttons: list[Button] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.buttons

    @property
    def updated_at(self) -> datetime | None:
        dates = [b.modified for b in self.buttons if b.modified is not None]
        return max(dates) if dates else None


def item_prefix(source_prefix: str, key: str) -> str | None:
    """Prefix of the item a key belongs to: `source/{collection}/{item}/`, or None."""
    if not key.startswith(source_prefix):
        return None
    parts = key[len(source_prefix):].split("/")
    if len(parts) < 3 or not parts[0] or not parts[1]:
        return None
    return f"{source_prefix}{parts[0]}/{parts[1]}/"


def split_prefix(source_prefix: str, prefix: str) -> tuple[str, str]:
    """(collection, item folder name) of an item prefix, NFC-normalised."""
    remainder = prefix[len(source_prefix):].rstrip("/")
    collection, _, folder = remainder.partition("/")
    return convention.normalize(collection), convention.normalize(folder)


def build_item(source_prefix: str, public_prefix: str, prefix: str,
               objects: list[SourceObject], link_bodies: Mapping[str, bytes]) -> Item:
    """The item model of one item prefix (buttons are filled in Task 10)."""
    collection, folder = split_prefix(source_prefix, prefix)
    label, token = convention.split_item_name(folder)
    return Item(collection=collection, label=label, token=token or "")


def published_keys(public_prefix: str, item: Item) -> set[str]:
    """Keys the public zone must hold for this item (completed in Task 11)."""
    base = f"{public_prefix}{item.token}/"
    return {f"{base}index.html", f"{base}qr.svg"}
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_catalog.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/catalog.py tests/unit/test_catalog.py
git commit -m "catalog: item model and prefix helpers"
```

---

### Task 10: catalog.py, build_item [core-catalog-build]

**Files:**
- Modify: `src/swingtag/catalog.py` (replace `build_item`), `tests/unit/test_catalog.py` (append)

**Interfaces:**
- Consumes: `convention.parse_order`, `sort_key`, `is_ignored`, `normalize`, `unique_slug` (Tasks 2, 4); `formats.lookup`, `formats.parse_link` (Tasks 5-6).
- Produces: complete `build_item(...)` for file resources and links; anomaly strings formatted `"{reason}: {relative path}"`.

- [ ] **Step 1: Write the failing tests** (append)

```python
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
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_catalog.py -q`
Expected: FAIL (e.g. `ValueError: not enough values to unpack` in `test_one_resource_entry_label`, since `buttons` is empty).

- [ ] **Step 3: Implement** (replace the `build_item` skeleton in `src/swingtag/catalog.py`)

```python
def _newer(candidate: SourceObject, current: SourceObject) -> bool:
    """True when `candidate` should replace `current` for the same NFC name:
    the newer `modified` wins, a known date beats an unknown one."""
    if candidate.modified is None:
        return current.modified is None
    if current.modified is None:
        return True
    return candidate.modified >= current.modified


def build_item(source_prefix: str, public_prefix: str, prefix: str,
               objects: list[SourceObject], link_bodies: Mapping[str, bytes]) -> Item:
    """The item model of one item prefix.

    `link_bodies` maps the source key of each link file (already size-checked by
    the caller) to its bytes; a link file missing from it is an invalid link.
    """
    collection, folder = split_prefix(source_prefix, prefix)
    label, token = convention.split_item_name(folder)
    item = Item(collection=collection, label=label, token=token or "")

    # entry name -> file name -> (object, format, url); NFC keys merge NFD twins,
    # keeping the most recently modified object.
    grouped: dict[str, dict[str, tuple[SourceObject, formats.Format, str | None]]] = {}
    for obj in objects:
        if obj.key.endswith("/"):
            continue  # folder placeholder created by some clients
        relative = convention.normalize(obj.key[len(prefix):])
        parts = relative.split("/")
        if len(parts) == 1:
            if not convention.is_ignored(parts[0]):
                item.anomalies.append(f"file in item root: {relative}")
            continue
        if len(parts) > 2:
            if not any(convention.is_ignored(p) for p in parts):
                item.anomalies.append(f"deeper than entry level: {relative}")
            continue
        entry_name, filename = parts
        if convention.is_ignored(entry_name) or convention.is_ignored(filename):
            continue
        fmt = formats.lookup(filename)
        if fmt is None:
            item.anomalies.append(f"format not accepted: {relative}")
            continue
        url = None
        if fmt.kind == "link":
            url = formats.parse_link(filename, link_bodies.get(obj.key, b""))
            if url is None:
                item.anomalies.append(f"invalid link: {relative}")
                continue
        elif obj.size > MAX_COPY_BYTES:
            item.anomalies.append(f"too large for single copy: {relative}")
            continue
        files = grouped.setdefault(entry_name, {})
        previous = files.get(filename)
        if previous is None or _newer(obj, previous[0]):
            files[filename] = (obj, fmt, url)

    entries = sorted(grouped.items(),
                     key=lambda e: convention.sort_key(*convention.parse_order(e[0])))
    entry_slugs: set[str] = set()
    ranked: list[tuple[tuple, tuple, Button]] = []
    for entry_name, files in entries:
        order, entry_label = convention.parse_order(entry_name)
        entry_slug = convention.unique_slug(entry_label, entry_slugs, "entry")
        multiple = len(files) > 1
        file_slugs: set[str] = set()
        by_stem = sorted(
            ((filename[: -len(fmt.extension)], filename, obj, fmt, url)
             for filename, (obj, fmt, url) in files.items()),
            key=lambda f: convention.sort_key(*convention.parse_order(f[0])),
        )
        for stem, filename, obj, fmt, url in by_stem:
            file_order, file_label = convention.parse_order(stem)
            file_slug = convention.unique_slug(file_label, file_slugs, "file")
            if fmt.kind == "link":
                public_key, href = None, url
            else:
                path = f"{entry_slug}/{file_slug}{fmt.extension}"
                public_key, href = f"{public_prefix}{item.token}/{path}", f"/{item.token}/{path}"
            button = Button(
                order=order,
                label=file_label if multiple else entry_label,
                context=entry_label if multiple else "",
                kind=fmt.kind,
                href=href,
                public_key=public_key,
                source_key=obj.key,
                filename=filename,
                content_type=fmt.content_type,
                etag=obj.etag,
                size=obj.size,
                modified=obj.modified,
            )
            ranked.append((convention.sort_key(order, entry_label),
                           convention.sort_key(file_order, file_label), button))
    ranked.sort(key=lambda r: (r[0], r[1]))
    item.buttons = [r[2] for r in ranked]
    return item
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_catalog.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/catalog.py tests/unit/test_catalog.py
git commit -m "catalog: build_item with labels, order, slugs and anomalies"
```

---

### Task 11: catalog.py, links, published keys, update date [core-catalog-links]

**Files:**
- Modify: `src/swingtag/catalog.py` (replace `published_keys`), `tests/unit/test_catalog.py` (append)

**Interfaces:**
- Consumes: Task 10.
- Produces: complete `published_keys(public_prefix, item) -> set[str]`; `Item.updated_at` behaviour verified with links.

- [ ] **Step 1: Write the failing tests** (append)

```python
BOOK = "https://example.com/book"


def url_body(url):
    return f"[InternetShortcut]\nURL={url}\n".encode()


def test_link_button():
    link = obj("50 Book/book.url")
    [b] = build(link, links={link.key: url_body(BOOK)}).buttons
    assert (b.kind, b.href, b.public_key, b.label) == ("link", BOOK, None, "Book")


def test_invalid_link_anomaly():
    link = obj("50 Book/book.url")
    item = build(link, links={link.key: url_body("javascript:alert(1)")})
    assert item.buttons == [] and reasons(item) == ["invalid link"]


def test_links_not_published():
    link = obj("50 Book/book.url")
    item = build(obj("10 A/x.pdf"), link, links={link.key: url_body(BOOK)})
    assert cat.published_keys(PUB, item) == {
        f"public/{TOKEN}/index.html",
        f"public/{TOKEN}/qr.svg",
        f"public/{TOKEN}/a/x.pdf",
    }


def test_only_invalid_links_is_empty():
    link = obj("50 Book/book.webloc")
    item = build(link, links={link.key: plistlib.dumps({"URL": "data:x"})})
    assert item.empty


def test_updated_at_max_including_links():
    link = obj("50 Book/book.url", day=5)
    item = build(obj("10 A/x.pdf", day=1), link, links={link.key: url_body(BOOK)})
    assert item.updated_at == datetime(2026, 9, 5, tzinfo=timezone.utc)
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_catalog.py -q`
Expected: FAIL only `test_links_not_published` (the pdf key is missing from `published_keys`).

- [ ] **Step 3: Implement** (replace `published_keys`)

```python
def published_keys(public_prefix: str, item: Item) -> set[str]:
    """Keys the public zone must hold for this item: page, QR code, copied files."""
    base = f"{public_prefix}{item.token}/"
    keys = {f"{base}index.html", f"{base}qr.svg"}
    keys.update(b.public_key for b in item.buttons if b.public_key is not None)
    return keys
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_catalog.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/catalog.py tests/unit/test_catalog.py
git commit -m "catalog: link entries, published keys, update date"
```

---

### Task 12: render.py, page [page-style, page-render]

**Files:**
- Create: `src/swingtag/render.py`, `tests/unit/test_render.py`

**Interfaces:**
- Consumes: `catalog.Item`, `catalog.Button` (Tasks 9-11); `theme.Theme`, `DEFAULT_THEME`, `Colors` (Task 8); `i18n.format_date` (Task 7).
- Produces: `render_page(item: Item, theme: Theme) -> str`.

Reference: `spec/experiments/e_page.py` (PROVES weight, icons, `color-mix` derivation after the T-14 fix; SHORTCUT: hardcoded content, no escaping helper, no locale).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_render.py`:

```python
"""Unit tests for render.py (TEST-PLAN 2.5)."""
import re
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from swingtag import catalog as cat
from swingtag import render as r
from swingtag import theme as t

TOKEN = "3xk9m2p7qhv4"
LONG = "Instructions for pruning and seasonal care, part number"  # 55 characters
EXT = {"document": ".pdf", "image": ".jpg", "audio": ".m4a", "video": ".mp4"}


def button(kind, i, label=LONG, context="Care and maintenance"):
    href = "https://example.com/book" if kind == "link" else f"/{TOKEN}/e{i}/f{i}{EXT[kind]}"
    return cat.Button(order=i, label=label, context=context, kind=kind, href=href,
                      public_key=None if kind == "link" else f"public{href}",
                      source_key=f"source/x/{i}", filename=f"f{i}", content_type=None,
                      etag="", size=1, modified=datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc))


@pytest.fixture
def item():
    kinds = ["document", "image", "audio", "video", "link"] * 2
    return cat.Item(collection="Vivaio Radici Lente", label="Olivo Leccino", token=TOKEN,
                    buttons=[button(k, i) for i, k in enumerate(kinds)])


@pytest.fixture
def theme():
    return t.Theme(locale="it", timezone="Europe/Rome", logo="logo.svg", header="Vivaio Radici Lente",
                   footer="Via dei Campi 12", notice="Demo environment",
                   colors=t.Colors("#3d6b4f", "#f4f1ea", "#1d241f"), colors_dark=None)


def test_no_script(item, theme):
    assert "<script" not in r.render_page(item, theme)


def test_one_style_block(item, theme):
    assert r.render_page(item, theme).count("<style>") == 1


def test_weight_ten_buttons(item, theme):
    assert len(r.render_page(item, theme).encode()) < 15360


def test_no_remote_resources(item, theme):
    html = r.render_page(item, theme)
    remote = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert remote == ["https://example.com/book", "https://example.com/book"]
    assert 'src="/_assets/logo.svg"' in html


def test_order_of_sections(item, theme):
    html = r.render_page(item, theme)
    body = html[html.index("<body>"):]
    marks = ["Demo environment", "class=brand", "/_assets/logo.svg", "<h1>",
             "class=sub", "<ul>", "Via dei Campi 12", "Aggiornato il"]
    positions = [body.index(m) for m in marks]
    assert positions == sorted(positions)


def test_subtitle_rule(item, theme):
    assert "class=sub" in r.render_page(item, theme)
    assert "class=sub" not in r.render_page(item, replace(theme, header=None))


def test_derived_tones_only(item, theme):
    css = re.search(r"<style>(.*)</style>", r.render_page(item, theme), re.S).group(1)
    mixes = re.findall(r"color-mix\(((?:[^()]|\([^()]*\))*)\)", css)
    assert mixes
    for args in mixes:
        assert "#" not in args
        assert set(re.findall(r"var\((--[a-z]+)\)", args)) <= {"--t", "--bg", "--p"}


def test_dark_block_rule(item, theme):
    dark = "prefers-color-scheme:dark"
    assert dark not in r.render_page(item, theme)
    assert dark in r.render_page(item, replace(theme, colors_dark=t.Colors("#e0a15a", "#171412", "#f2ede6")))
    assert dark in r.render_page(item, t.DEFAULT_THEME)


def test_file_href_absolute(item, theme):
    assert f'href="/{TOKEN}/e0/f0.pdf"' in r.render_page(item, theme)


def test_link_rel(item, theme):
    html = r.render_page(item, theme)
    assert 'href="https://example.com/book" rel="noopener noreferrer"' in html
    assert "target=" not in html


def test_icon_accessible_name(item, theme):
    labels = re.findall(r'aria-label="([^"]+)"', r.render_page(item, theme))
    assert labels[:5] == ["Documento", "Immagine", "Audio", "Video", "Link"]


def test_escaping(item, theme):
    evil = replace(item, label="<b>&\"'</b>", buttons=[
        button("link", 0, label="<i>x</i>"),
        replace(button("link", 1), href='https://bücher.example/"ü'),
    ])
    html = r.render_page(evil, replace(theme, footer="a & b"))
    assert "<b>" not in html and "<i>" not in html
    assert "&lt;b&gt;&amp;&quot;&#x27;&lt;/b&gt;" in html
    assert "a &amp; b" in html
    assert 'href="https://bücher.example/&quot;ü"' in html


def test_updated_line(item, theme):
    assert "Aggiornato il 25/09/2026 14:30" in r.render_page(item, theme)


def test_empty_item(theme):
    html = r.render_page(cat.Item(collection="C", label="L", token=TOKEN), theme)
    assert "Qui non c&#x27;è ancora nulla." in html
    assert "<ul>" not in html


def test_robots_noindex(item, theme):
    assert "<meta name=robots content=noindex,nofollow>" in r.render_page(item, theme)


def test_long_unbreakable_label_wraps(item, theme):
    """Review Focus 1."""
    html = r.render_page(replace(item, label="x" * 120), theme)
    css = re.search(r"<style>(.*)</style>", html, re.S).group(1)
    assert "overflow-wrap:anywhere" in css


def test_empty_label_heading_falls_back(theme):
    """Review Focus 2."""
    html = r.render_page(cat.Item(collection="Vivaio", label="", token=TOKEN), theme)
    assert "<h1>Vivaio</h1>" in html
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_render.py -q`
Expected: FAIL, `ImportError`.

- [ ] **Step 3: Implement**

`src/swingtag/render.py`:

```python
"""The page of an item and the error page, as HTML strings (FR-30..FR-35).

Pure: model and theme in, HTML out. No JavaScript, one inline style block, one
request to reach the menu. Every value from names, links or the theme is escaped.
"""

from __future__ import annotations

from html import escape

from .catalog import Button, Item
from .i18n import format_date
from .theme import Colors, Theme

# 24x24 stroke icons, one per kind.
_ICONS = {
    "document": '<path d="M6 2h9l5 5v15H6zM14 2v6h6"/>',
    "image": '<path d="M3 4h18v16H3zM3 16l5-5 5 5 3-3 5 5"/><circle cx="16" cy="8" r="2"/>',
    "audio": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "video": '<path d="M3 5h13v14H3zM16 10l5-3v10l-5-3"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
}

# Secondary tones derive only from --t, --bg and --p (spec/ASSUMPTIONS.md T-14).
_CSS = """*{box-sizing:border-box}
:root{%(vars)s;--muted:color-mix(in srgb,var(--t) 62%%,var(--bg));
--line:color-mix(in srgb,var(--t) 14%%,var(--bg));--card:color-mix(in srgb,var(--t) 5%%,var(--bg))}
%(dark)shtml{-webkit-text-size-adjust:100%%}body{margin:0;background:var(--bg);color:var(--t);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:44rem;margin:0 auto;padding:1rem 1rem 3rem;overflow-wrap:anywhere}
.notice{background:color-mix(in srgb,var(--p) 12%%,var(--bg));border:1px solid var(--line);
border-radius:.5rem;padding:.6rem .8rem;font-size:.85rem;margin-bottom:1rem}
header{padding:.5rem 0 1.25rem;border-bottom:1px solid var(--line);margin-bottom:1.25rem}
.brand{display:flex;align-items:center;gap:.6rem;font-weight:700;color:var(--muted);margin-bottom:.75rem}
.brand img{height:40px;width:auto}h1{font-size:1.6rem;line-height:1.25;margin:0 0 .35rem}
.sub{color:var(--muted);margin:0}ul{list-style:none;margin:0;padding:0}li{margin-bottom:.75rem}
a.b{display:flex;align-items:center;gap:.75rem;min-height:56px;padding:.85rem 1rem;background:var(--card);
border:1px solid var(--line);border-radius:.6rem;text-decoration:none;color:var(--t);font-weight:600}
a.b:focus-visible{outline:3px solid var(--p);outline-offset:2px}
svg{flex:none;width:24px;height:24px;fill:none;stroke:var(--p);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.l{flex:1;min-width:0}.c{display:block;color:var(--muted);font-weight:400;font-size:.8rem;margin-top:.15rem}
.empty{background:var(--card);border:1px solid var(--line);border-radius:.6rem;padding:1.25rem;color:var(--muted)}
footer{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}
footer p{margin:0 0 .25rem}"""


def _vars(colors: Colors) -> str:
    return f"--p:{colors.primary};--bg:{colors.background};--t:{colors.text}"


def _style(theme: Theme) -> str:
    dark = ""
    if theme.colors_dark is not None:
        dark = "@media (prefers-color-scheme:dark){:root{%s}}\n" % _vars(theme.colors_dark)
    return _CSS % {"vars": _vars(theme.colors), "dark": dark}


def _head(title: str, theme: Theme) -> str:
    return (
        f"<!doctype html><html lang={escape(theme.locale)}><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        "<meta name=robots content=noindex,nofollow>"
        f"<title>{escape(title)}</title><style>{_style(theme)}</style>"
    )


def _header(theme: Theme, collection: str) -> str:
    logo = f'<img src="/_assets/{escape(theme.logo)}" alt="">' if theme.logo else ""
    return f"<div class=brand>{logo}{escape(theme.header or collection)}</div>"


def _button(button: Button, theme: Theme) -> str:
    rel = ' rel="noopener noreferrer"' if button.kind == "link" else ""
    context = f"<span class=c>{escape(button.context)}</span>" if button.context else ""
    name = escape(theme.string(f"kind_{button.kind}"))
    return (
        f'<li><a class=b href="{escape(button.href)}"{rel}>'
        f'<svg viewBox="0 0 24 24" role=img aria-label="{name}">{_ICONS[button.kind]}</svg>'
        f"<span class=l>{escape(button.label)}{context}</span></a></li>"
    )


def render_page(item: Item, theme: Theme) -> str:
    heading = item.label or item.collection
    brand = theme.header or item.collection
    parts = [_head(f"{heading} · {brand}", theme), "<body><div class=wrap>"]
    if theme.notice:
        parts.append(f"<div class=notice>{escape(theme.notice)}</div>")
    parts.append(f"<header>{_header(theme, item.collection)}<h1>{escape(heading)}</h1>")
    if theme.header:
        parts.append(f"<p class=sub>{escape(item.collection)}</p>")
    parts.append("</header>")
    if item.buttons:
        parts.append("<ul>" + "".join(_button(b, theme) for b in item.buttons) + "</ul>")
    else:
        parts.append(f"<div class=empty>{escape(theme.string('empty'))}</div>")
    footer = []
    if theme.footer:
        footer.append(f"<p>{escape(theme.footer)}</p>")
    if item.updated_at is not None:
        stamp = format_date(item.updated_at, theme.locale, theme.timezone)
        footer.append(f"<p>{escape(theme.string('updated'))} {escape(stamp)}</p>")
    if footer:
        parts.append("<footer>" + "".join(footer) + "</footer>")
    parts.append("</div></body></html>")
    return "".join(parts)
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_render.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/render.py tests/unit/test_render.py
git commit -m "render: themed item page"
```

---

### Task 13: render.py, error page [page-404]

**Files:**
- Modify: `src/swingtag/render.py` (append), `tests/unit/test_render.py` (append)

**Interfaces:**
- Consumes: Task 12 helpers `_head`, `_header`.
- Produces: `render_not_found(theme: Theme) -> str`.

- [ ] **Step 1: Write the failing test** (append)

```python
def test_not_found_page():
    theme = t.Theme(locale="en", header="Tides of Light")
    html = r.render_not_found(theme)
    assert "<h1>Page not available</h1>" in html
    assert "This code does not match any published page." in html
    assert TOKEN not in html
    assert "<script" not in html
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python -m pytest tests/unit/test_render.py::test_not_found_page -q`
Expected: FAIL, `AttributeError: ... has no attribute 'render_not_found'`.

- [ ] **Step 3: Implement** (append)

```python
def render_not_found(theme: Theme) -> str:
    """Page for any unknown path. Reveals nothing about which tokens exist."""
    title = theme.string("not_found_title")
    return "".join([
        _head(title, theme),
        "<body><div class=wrap>",
        f"<div class=notice>{escape(theme.notice)}</div>" if theme.notice else "",
        f"<header>{_header(theme, '')}<h1>{escape(title)}</h1></header>",
        f"<div class=empty>{escape(theme.string('not_found_body'))}</div>",
        "</div></body></html>",
    ])
```

- [ ] **Step 4: Run to see it pass**

Run: `.venv/bin/python -m pytest tests/unit/test_render.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/swingtag/render.py tests/unit/test_render.py
git commit -m "render: themed error page"
```

---

### Task 14: qr.py [page-qr]

**Files:**
- Create: `src/swingtag/qr.py`, `tests/unit/test_qr.py`

**Interfaces:**
- Consumes: `qrcode` 8.2.
- Produces: `qr_svg(url: str) -> bytes`; internal `_code(url: str) -> qrcode.QRCode`.

Note on U-QR-01: the SVG rendering itself was proven decodable in T-13 (browser rendering, `spec/experiments/e_qr_decode.py`). The unit test rasterises the same module matrix that the SVG draws and decodes it with OpenCV, so it runs headless in CI.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_qr.py`:

```python
"""Unit tests for qr.py (TEST-PLAN 2.5)."""
import cv2
import numpy as np
import qrcode

from swingtag import qr

URL = "https://d1234567890abc.cloudfront.net/3xk9m2p7qhv4"


def test_qr_decodes():
    svg = qr.qr_svg(URL)
    assert svg.startswith(b"<?xml") and b"<path" in svg
    matrix = np.array(qr._code(URL).get_matrix(), dtype=np.uint8)  # includes the border
    image = np.where(matrix == 1, 0, 255).astype(np.uint8)
    image = cv2.resize(image, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
    image = np.pad(image, 40, constant_values=255)  # generous quiet zone for the detector
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    assert data == URL


def test_qr_level_q():
    assert qr._code(URL).error_correction == qrcode.constants.ERROR_CORRECT_Q
```

- [ ] **Step 2: Run to see them fail**

Run: `.venv/bin/python -m pytest tests/unit/test_qr.py -q`
Expected: FAIL, `ImportError`.

- [ ] **Step 3: Implement**

`src/swingtag/qr.py`:

```python
"""Vector QR code of an item URL (FR-37).

Level Q (about 25 % of modules recoverable): the code lives on a label exposed
to handling, sun and dirt. Vector output because the print size is unknown.
"""

from __future__ import annotations

import io

import qrcode
from qrcode.image.svg import SvgPathImage


def _code(url: str) -> qrcode.QRCode:
    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=10,
        border=2,
        image_factory=SvgPathImage,
    )
    code.add_data(url)
    code.make(fit=True)
    return code


def qr_svg(url: str) -> bytes:
    buffer = io.BytesIO()
    _code(url).make_image().save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: Run to see them pass**

Run: `.venv/bin/python -m pytest tests/unit/test_qr.py -q`
Expected: 2 passed. Then the whole suite: `make test`, all green.

- [ ] **Step 5: Commit and push**

```bash
git add src/swingtag/qr.py tests/unit/test_qr.py
git commit -m "qr: vector QR code at level Q"
git push
gh run watch --exit-status
```

---

## After this plan

Close the backlog items implemented here (`scaffold`, `ci`, `core-names`, `core-tokens`, `core-slugs`, `core-formats`, `core-links`, `theme-model`, `theme-i18n`, `core-catalog-model`, `core-catalog-build`, `core-catalog-links`, `page-style`, `page-render`, `page-404`, `page-qr`) by setting `closed=True` in `plans/backlog.py` and running `python3 plans/create_backlog.py` with the personal `gh` account.

## Plans that follow (not written yet, blocked by experiments)

| Plan | Scope (backlog keys) | Blocked by |
|---|---|---|
| 2. Publisher | `pub-*` | T-32 (#20), T-48 (#27); write after they are CONFIRMED |
| 3. Infrastructure module | `infra-*`, `build-lambda` | T-30, T-38, T-40, T-41, T-44, T-46, T-49 and the harness (#16) |
| 4. Examples and tooling | `make-demo`, `examples-*`, `media-*`, `ex-*`, `pdfmin`, `plates`, `verify`, U-REPO-01..03 and 05 | T-45, T-47; plans 2 and 3 |
