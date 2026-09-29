"""Repository-level checks."""
from pathlib import Path

import swingtag

ROOT = Path(__file__).resolve().parents[2]


def test_package_imports():
    assert swingtag.NAME == "swingtag"
    assert swingtag.__version__ == "0.1.0"


def test_name_only_in_allowed_places():
    """the literal project name appears under src/ only in __init__.py."""
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src").rglob("*.py")
        if path.name != "__init__.py" and swingtag.NAME in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_terraform_never_reserves_concurrency():
    """reserved concurrency with an SQS source throttles every poller."""
    import re
    offenders = [p.name for p in (ROOT / "terraform").glob("*.tf")
                 if re.search(r"^\s*reserved_concurrent_executions\s*=", p.read_text(encoding="utf-8"), re.M)]
    assert offenders == []


def test_examples_force_destroy():
    """examples destroy cleanly; the module keeps force_destroy off by default."""
    for example in ("restaurant", "nursery", "exhibition"):
        text = (ROOT / "examples" / example / "main.tf").read_text(encoding="utf-8")
        assert "force_destroy    = true" in text, example
    variables = (ROOT / "terraform" / "variables.tf").read_text(encoding="utf-8")
    block = variables[variables.index('variable "force_destroy"'):]
    assert "default     = false" in block.split("}")[0]


def test_name_not_in_terraform_code():
    """in Terraform the literal name lives only in the name default and in the
    example project tags."""
    offenders = []
    files = list((ROOT / "terraform").rglob("*.tf")) + list((ROOT / "terraform").rglob("*.tftest.hcl"))
    files += list((ROOT / "examples").rglob("*.tf")) + list((ROOT / "examples").rglob("*.tftest.hcl"))
    for path in files:
        if ".terraform" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if swingtag.NAME not in line:
                continue
            allowed = (path.name == "variables.tf" and 'default     = "' + swingtag.NAME + '"' in line) or \
                      ('project = "' + swingtag.NAME + '"' in line and path.parent.parent.name == "examples")
            if not allowed:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []
