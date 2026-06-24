#!/usr/bin/env python3
"""Hardware policy CLI — validation surface for model↔hardware affinity.

Human entry points:
  - ``orama-system/start.sh --hardware-policy`` (startup gate)
  - Orama Portal http://localhost:8002

**Invariant (do not violate):** All affinity enforcement MUST delegate to
``src/utils/hardware_policy.py``.  Never duplicate YAML parsers here — a stale
fork caused PR #131: ``windows_only_aliases`` (e.g. quant-suffixed LM Studio
ids like ``gemma-4-26B-A4B-it-Q4_K_M``) were invisible to this CLI while the
canonical module enforced them correctly.

**LM Studio proxy gotcha:** Mac ``/v1/models`` lists Win models via LAN proxy.
Provider name (``lmstudio-mac`` vs ``lmstudio-win``) is the routing key — not
which endpoint listed the model.  See ``config/model_hardware_policy.yml``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (ROOT / "src", ROOT):
    sys.path.insert(0, str(_path))

from utils.hardware_policy import (  # noqa: E402
    HardwareAffinityError,
    check_affinity as check_affinity_canonical,
    forbidden_models_for_platform,
    load_policy as load_canonical_policy,
)

POLICY_PATH = ROOT / "config" / "model_hardware_policy.yml"


def load_policy() -> dict[str, list[str]]:
    """Load hardware policy via the canonical module (alias-aware).

    Returns empty lists when ``config/model_hardware_policy.yml`` is absent.
    Uses ``force_reload=True`` so CLI invocations always reflect the on-disk
    policy — startup validation must not serve a stale in-process cache.
    """
    if not POLICY_PATH.exists():
        return {"windows_only": [], "mac_only": [], "shared": []}
    return load_canonical_policy(policy_path=POLICY_PATH, force_reload=True)


def check_affinity(model_id: str, platform: str, policy: dict[str, list[str]]) -> tuple[bool, str]:
    """Return whether *model_id* may run on *platform* (CLI-friendly wrapper).

    Wraps :func:`utils.hardware_policy.check_affinity` which raises
    :class:`HardwareAffinityError` on violation.  Returns ``(True, "")`` when
    allowed, ``(False, detail)`` when forbidden (NEVER_MAC / NEVER_WIN).

    *platform* accepts synonyms documented in ``forbidden_models_for_platform``
    (e.g. ``mac``, ``lmstudio-mac``, ``win``, ``lmstudio-win``).
    """
    try:
        check_affinity_canonical(model_id, platform, policy=policy)
        return True, ""
    except HardwareAffinityError as exc:
        return False, str(exc)


def cmd_list() -> int:
    """Print windows_only / mac_only / shared model lists from policy YAML."""
    policy = load_policy()
    print("Windows-only (NEVER_MAC):", ", ".join(policy["windows_only"]) or "none")
    print("Mac-only     (NEVER_WIN):", ", ".join(policy["mac_only"]) or "none")
    print("Shared                  :", ", ".join(policy["shared"]) or "none (intentional)")
    return 0


def cmd_check_openclaw() -> int:
    """Validate ``~/.openclaw/openclaw.json`` LM Studio provider assignments.

    Iterates ``lmstudio-*`` providers only.  Platform is inferred from the
    provider id (``mac`` in id → Mac, else Win).  OpenClaw can dispatch directly
    from this file without passing through the supervisor affinity gate, so false
    negatives here risk OOM / double-barrel GPU use for NEVER_MAC models.

    Returns 0 when clean, 1 when violations exist or config is missing.
    """
    policy = load_policy()
    path = Path.home() / ".openclaw" / "openclaw.json"
    if not path.exists():
        print(f"⚠ {path} not found")
        return 1
    cfg = json.loads(path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for pid, provider in cfg.get("models", {}).get("providers", {}).items():
        if "lmstudio" not in pid.lower():
            continue
        platform = "mac" if "mac" in pid.lower() else "win"
        for model in provider.get("models", []):
            ok, detail = check_affinity(model.get("id", ""), platform, policy)
            if not ok:
                violations.append(f"{pid}: {detail}")
    if violations:
        print("❌ openclaw.json hardware policy violations:")
        for v in violations:
            print(f"  {v}")
        return 1
    print("✅ openclaw.json clean")
    for pid in ["lmstudio-mac", "lmstudio-win"]:
        models = [m["id"] for m in cfg.get("models", {}).get("providers", {}).get(pid, {}).get("models", [])]
        print(f"  {pid}: {models}")
    return 0


def cmd_validate(model_id: str, platform: str) -> int:
    """Check a single model↔platform pair; print result and return exit code.

    Example: ``--validate gemma-4-26B-A4B-it-Q4_K_M mac`` must exit 1 with
    NEVER_MAC when the quant-suffixed alias is in ``windows_only_aliases``.
    """
    ok, detail = check_affinity(model_id, platform, load_policy())
    if ok:
        print(f"✅ {model_id} → {platform}")
        return 0
    print(f"❌ {detail}")
    return 1


def cmd_filter(models: list[str], platform: str) -> int:
    """Print models from *models* allowed on *platform* (affinity filter)."""
    forbidden = forbidden_models_for_platform(platform, load_policy())
    allowed = [m for m in models if m.lower() not in forbidden]
    removed = [m for m in models if m.lower() in forbidden]
    print(f"Allowed: {allowed}")
    if removed:
        print(f"Removed: {removed}")
    return 0


def main() -> int:
    """Parse CLI flags and dispatch to the appropriate subcommand."""
    p = argparse.ArgumentParser(description="Hardware model affinity helper")
    p.add_argument("--list", action="store_true")
    p.add_argument("--check-openclaw", action="store_true")
    p.add_argument("--validate", nargs=2, metavar=("MODEL_ID", "PLATFORM"))
    p.add_argument("--filter", nargs="+")
    p.add_argument("--platform", default="mac")
    args = p.parse_args()
    if args.list:
        return cmd_list()
    if args.check_openclaw:
        return cmd_check_openclaw()
    if args.validate:
        return cmd_validate(args.validate[0], args.validate[1])
    if args.filter:
        return cmd_filter(args.filter, args.platform)
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
