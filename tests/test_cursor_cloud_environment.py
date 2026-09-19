from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cloud_install_provisions_the_locked_dev_test_environment() -> None:
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
