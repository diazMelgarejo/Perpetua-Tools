"""Shared feature-flag reader for portable agent tooling."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def feature_enabled(features_path: PathLike, key: str) -> bool:
    """Return whether ``key`` is explicitly enabled; fail closed otherwise."""
    try:
        with Path(features_path).open(encoding="utf-8") as stream:
            features = json.load(stream)
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return False
    entry = features.get(key) or {}
    return bool(entry.get("enabled"))
