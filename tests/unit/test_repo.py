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
