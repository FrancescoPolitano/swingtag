#!/usr/bin/env python3
"""Print every FR-n and EC-n defined in SPEC.md that TEST-PLAN.md never mentions."""
import re
from pathlib import Path

here = Path(__file__).parent
spec = (here / "SPEC.md").read_text()
plan = (here / "TEST-PLAN.md").read_text()
defined = sorted(set(re.findall(r"\*\*(FR-\d+)\b", spec)) | set(re.findall(r"^\| (EC-\d+) \|", spec, re.M)),
                 key=lambda x: (x[:2], int(x.split("-")[1])))
covered = set(re.findall(r"\b(FR-\d+|EC-\d+)\b", plan))
missing = [x for x in defined if x not in covered]
for x in missing:
    print(x)
raise SystemExit(1 if missing else 0)
