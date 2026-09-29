"""Repository-level checks on the example deployments."""
from pathlib import Path

import pytest
import yaml

from swingtag import convention, formats
from swingtag.theme import contrast

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = {"restaurant": 1, "nursery": 6, "exhibition": 6}  # items per example
ENTRIES = {  # entry folders of every item
    "restaurant": ["10 Pranzo", "20 Cena", "30 Vini", "40 Allergeni", "50 Prenota"],
    "nursery": ["10 Scheda", "20 Foto", "30 Storia", "40 Come potarla", "50 Acquista"],
    "exhibition": ["10 The work", "20 The artist", "30 Listen", "40 Watch", "50 Read more"],
}
MEDIA = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".mp3", ".m4a", ".mp4"}


def item_dirs(example):
    content = ROOT / "examples" / example / "content"
    return [item for collection in content.iterdir() if collection.is_dir()
            for item in collection.iterdir() if item.is_dir()]


@pytest.mark.parametrize("example", sorted(EXAMPLES))
def test_examples_have_tokens(example):
    """every item folder already carries a valid token."""
    items = item_dirs(example)
    assert len(items) == EXAMPLES[example]
    for item in items:
        label, token = convention.split_item_name(item.name)
        assert token is not None, item.name
        assert label


@pytest.mark.parametrize("example", sorted(EXAMPLES))
def test_examples_formats_valid(example):
    """every file is an accepted format; every link file parses."""
    content = ROOT / "examples" / example / "content"
    files = [p for p in content.rglob("*") if p.is_file() and not convention.is_ignored(p.name)]
    assert len(files) == 5 * EXAMPLES[example]  # one file per entry
    for path in files:
        # exactly collection/item/entry/file: no file in an item root, nothing deeper
        assert len(path.relative_to(content).parts) == 4, path
    for item in item_dirs(example):
        assert sorted(e.name for e in item.iterdir() if e.is_dir()) == ENTRIES[example], item.name
    for path in files:
        fmt = formats.lookup(path.name)
        assert fmt is not None, path
        if fmt.kind == "link":
            assert formats.parse_link(path.name, path.read_bytes()), path


@pytest.mark.parametrize("example", sorted(EXAMPLES))
def test_examples_media_budget(example):
    """each media placeholder is under 100 KB."""
    media = [p for p in (ROOT / "examples" / example / "content").rglob("*")
             if p.suffix.lower() in MEDIA]
    assert media
    for path in media:
        assert path.stat().st_size < 102400, (path, path.stat().st_size)


@pytest.mark.parametrize("example", sorted(EXAMPLES))
def test_examples_contrast(example):
    """no example may trigger the contrast warning."""
    theme = yaml.safe_load((ROOT / "examples" / example / "theme" / "theme.yaml").read_text())
    colors = theme["colors"]
    assert contrast(colors["text"], colors["background"]) >= 4.5
    assert contrast(colors["primary"], colors["background"]) >= 3
    logo = theme.get("logo")
    assert logo is None or (ROOT / "examples" / example / "theme" / "assets" / logo).is_file()
