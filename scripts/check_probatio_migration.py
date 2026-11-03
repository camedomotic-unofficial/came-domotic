"""Fail when the minimum HA version allows probatio but voluptuous is still used.

Home Assistant 2026.10 replaced voluptuous with probatio. The integration keeps
importing voluptuous (plus a mypy override) only while older HA versions are
supported. Once ``hacs.json`` requires 2026.10 or later, migrate to probatio.
See https://github.com/camedomotic-unofficial/came-domotic/issues/155
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

PROBATIO_MIN_HA = (2026, 10)
ROOT = Path(__file__).resolve().parent.parent


def _parse_version(version: str) -> tuple[int, int]:
    """Return (year, month) from an HA version string like '2025.6.0'."""
    year, month = version.split(".")[:2]
    return int(year), int(month)


def main() -> int:
    """Run the check and return the process exit code."""
    min_ha = json.loads((ROOT / "hacs.json").read_text())["homeassistant"]
    if _parse_version(min_ha) < PROBATIO_MIN_HA:
        return 0

    leftovers = [
        str(path.relative_to(ROOT))
        for folder in ("custom_components", "tests")
        for path in sorted((ROOT / folder).rglob("*.py"))
        if re.search(r"^\s*(import|from)\s+voluptuous\b", path.read_text(), re.M)
    ]
    if 'module = "voluptuous.*"' in (ROOT / "pyproject.toml").read_text():
        leftovers.append("pyproject.toml (voluptuous mypy override)")
    if not leftovers:
        return 0

    print(
        f"hacs.json requires Home Assistant {min_ha}, which ships probatio.\n"
        "Migrate from voluptuous to probatio ('import probatio as vol') and\n"
        "remove the voluptuous mypy override. Still using voluptuous:",
        file=sys.stderr,
    )
    for item in leftovers:
        print(f"  - {item}", file=sys.stderr)
    print(
        "See https://github.com/camedomotic-unofficial/came-domotic/issues/155",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
