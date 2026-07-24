"""Guard alphaclaw-mcp package.json against npm 10 EOVERRIDE install failures."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parent.parent
PACKAGE_JSON = ROOT / "packages" / "alphaclaw-mcp" / "package.json"


def test_alphaclaw_mcp_overrides_do_not_overlap_direct_dependencies():
    """npm 10+ rejects overrides for packages that are also direct dependencies."""
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    direct = set(data.get("dependencies", {}))
    overrides = set(data.get("overrides", {}))

    overlap = sorted(direct & overrides)
    assert overlap == [], (
        "npm EOVERRIDE: remove overrides for direct dependencies "
        f"({', '.join(overlap)}) — pin versions in dependencies instead"
    )
