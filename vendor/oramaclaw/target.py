"""Target resolution for oramaclaw V1.

A ``ConfigTarget`` describes the workspace that oramaclaw manages —
where the openclaw.json config lives, where state is persisted, and
which workspace root owns the agent profile tree.

Resolution priority (highest to lowest):
1. Explicit CLI flags (``workspace``, ``config_path``, ``state_dir``)
2. Target embedded in the manifest (``manifest.target``)
3. Named target from the target catalog (``--target <name>`` CLI flag)
4. Environment defaults: ``$OPENCLAW_HOME`` if set, else ``~/.openclaw``

Legacy migration: ``$OPENCLAW_HOME`` is accepted as the workspace root
when no other source is available; the function emits a warning and
derives ``config_path`` and ``state_dir`` from it using the V1 standard
layout (``<home>/openclaw.json`` and ``<home>/state/oramaclaw``).

``$ORAMACLAW_TARGETS_PATH`` controls where the target catalog JSON is
read from (P2-5). Falls back to ``~/.openclaw/oramaclaw-targets.json``.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oramaclaw.types import ConfigTarget, ControlManifest

from oramaclaw.types import ConfigTarget

_log = logging.getLogger(__name__)

# ── Defaults ─────────────────────────────────────────────────────────────────

_DEFAULT_OPENCLAW_HOME = Path("~/.openclaw").expanduser()
_DEFAULT_CONFIG_FILENAME = "openclaw.json"
_DEFAULT_STATE_SUBDIR = "state/oramaclaw"
_DEFAULT_CATALOG_FILENAME = "oramaclaw-targets.json"


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_target(
    *,
    workspace: str | Path | None = None,
    config_path: str | Path | None = None,
    state_dir: str | Path | None = None,
    manifest: "ControlManifest | None" = None,
    target_name: str | None = None,
    catalog: "TargetCatalog | None" = None,
) -> ConfigTarget:
    """Return a fully resolved ConfigTarget.

    Resolution order:
    1. Explicit keyword args (all three must be supplied together)
    2. manifest.target when no explicit args
    3. Named target from catalog (target_name + catalog)
    4. $OPENCLAW_HOME env var (legacy migration — warns once)
    5. ~/.openclaw default layout

    $ORAMACLAW_TARGETS_PATH controls the catalog file path (P2-5).
    """
    # 1. Explicit CLI flags — all three must be provided, or none.
    if workspace is not None or config_path is not None or state_dir is not None:
        missing = [
            name for name, val in (
                ("workspace", workspace),
                ("config_path", config_path),
                ("state_dir", state_dir),
            ) if val is None
        ]
        if missing:
            raise ValueError(
                f"resolve_target: when any of workspace/config_path/state_dir is "
                f"supplied, all three are required; missing: {missing}"
            )
        return ConfigTarget(
            workspace_root=Path(workspace).expanduser().resolve(),  # type: ignore[arg-type]
            config_path=Path(config_path).expanduser().resolve(),   # type: ignore[arg-type]
            state_dir=Path(state_dir).expanduser().resolve(),        # type: ignore[arg-type]
        )

    # 2. Manifest embedded target.
    if manifest is not None and manifest.target is not None:
        return manifest.target

    # 3. Named target from catalog.
    if target_name is not None:
        cat = catalog if catalog is not None else TargetCatalog.load()
        return cat.get(target_name)

    # 4. Legacy $OPENCLAW_HOME migration.
    legacy_home = os.environ.get("OPENCLAW_HOME")
    if legacy_home:
        home = Path(legacy_home).expanduser().resolve()
        _log.warning(
            "OPENCLAW_HOME is deprecated as an oramaclaw target source. "
            "Define a named target in %s or supply --workspace/--config-path/--state-dir.",
            TargetCatalog.default_path(),
        )
        return _target_from_home(home)

    # 5. Default ~/.openclaw layout.
    return _target_from_home(_DEFAULT_OPENCLAW_HOME)


def _target_from_home(home: Path) -> ConfigTarget:
    """Derive a ConfigTarget from a workspace root using the V1 standard layout."""
    return ConfigTarget(
        workspace_root=home,
        config_path=home / _DEFAULT_CONFIG_FILENAME,
        state_dir=home / _DEFAULT_STATE_SUBDIR,
    )


# ── Target catalog ────────────────────────────────────────────────────────────

class TargetNotFound(KeyError):
    """Raised when a named target is not present in the catalog."""
    def __init__(self, name: str, catalog_path: Path) -> None:
        self.name = name
        self.catalog_path = catalog_path
        super().__init__(
            f"Target {name!r} not found in catalog {catalog_path}. "
            "Add it with: oramaclaw targets add <name> --workspace <path>"
        )


class TargetCatalog:
    """Ordered collection of named ConfigTargets loaded from a JSON file.

    The JSON format is:
    ```json
    {
      "targets": {
        "<name>": {
          "workspace_root": "/path/to/workspace",
          "config_path": "/path/to/openclaw.json",
          "state_dir": "/path/to/state"
        }
      }
    }
    ```

    ``$ORAMACLAW_TARGETS_PATH`` overrides the default path (P2-5).
    """

    def __init__(self, targets: dict[str, ConfigTarget], path: Path) -> None:
        self._targets = targets
        self._path = path

    @staticmethod
    def default_path() -> Path:
        """Return the catalog path, honouring $ORAMACLAW_TARGETS_PATH (P2-5)."""
        env = os.environ.get("ORAMACLAW_TARGETS_PATH")
        if env:
            return Path(env).expanduser().resolve()
        return _DEFAULT_OPENCLAW_HOME / _DEFAULT_CATALOG_FILENAME

    @classmethod
    def load(cls, path: Path | None = None) -> "TargetCatalog":
        """Load the catalog from disk.

        If the file does not exist, an empty catalog is returned (no error).
        """
        resolved = path if path is not None else cls.default_path()
        if not resolved.exists():
            return cls({}, resolved)
        try:
            data = json.loads(resolved.read_bytes())
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("TargetCatalog: could not read %s — %s; treating as empty", resolved, exc)
            return cls({}, resolved)

        raw_targets = data.get("targets", {})
        if not isinstance(raw_targets, dict):
            _log.warning("TargetCatalog: 'targets' key is not a dict in %s; treating as empty", resolved)
            return cls({}, resolved)

        parsed: dict[str, ConfigTarget] = {}
        for name, entry in raw_targets.items():
            if not isinstance(entry, dict):
                _log.warning("TargetCatalog: target %r is not a dict; skipping", name)
                continue
            missing = [f for f in ("workspace_root", "config_path", "state_dir") if f not in entry]
            if missing:
                _log.warning("TargetCatalog: target %r missing fields %s; skipping", name, missing)
                continue
            parsed[name] = ConfigTarget(
                workspace_root=Path(entry["workspace_root"]).expanduser().resolve(),
                config_path=Path(entry["config_path"]).expanduser().resolve(),
                state_dir=Path(entry["state_dir"]).expanduser().resolve(),
            )

        return cls(parsed, resolved)

    def get(self, name: str) -> ConfigTarget:
        """Return the named target, raising TargetNotFound if absent."""
        try:
            return self._targets[name]
        except KeyError:
            raise TargetNotFound(name, self._path)

    def names(self) -> list[str]:
        """Return all target names in insertion order."""
        return list(self._targets.keys())

    def __len__(self) -> int:
        return len(self._targets)

    def __repr__(self) -> str:
        return f"TargetCatalog(path={self._path}, targets={list(self._targets)})"
