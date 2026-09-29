"""Contract tests for the Cursor Cloud environment install hook."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cloud_install_provisions_the_locked_dev_test_environment() -> None:
    """Install syncs the locked dev extra and defaults HOME like orama-system.

    The missing-uv path runs Astral's standalone installer without an in-script
    checksum. A later run accepts an executable already at
    ``$HOME/.local/bin/uv`` without a provenance or ownership check.
    """
    environment = json.loads(
        (ROOT / ".cursor" / "environment.json").read_text(encoding="utf-8")
    )
    install_command = environment["install"]
    script = (ROOT / "scripts" / "cursor" / "cloud-install.sh").read_text(
        encoding="utf-8"
    )

    assert install_command == "bash scripts/cursor/cloud-install.sh"
    assert "sync --extra dev --frozen" in script
    assert ".venv/bin/python -m pytest --version" in script
    assert "astral.sh/uv/install.sh" in script
    assert "python3 -m venv" not in script
    assert 'HOME="${HOME:-/home/ubuntu}"' in script
    assert "export HOME" in script
