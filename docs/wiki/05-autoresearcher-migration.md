# 05. AutoResearcher Migration - uditgoenka Plugin, Submodule, and Dry-Run

**TL;DR:** Primary mode is `uditgoenka/autoresearch`.
Perpetua adopts it as a source mirror at `vendor/autoresearch` and as the Claude Code plugin.
The GPU runner stays a secondary Verify substrate for ML experiments.
Long-running goals start with `preflight(dry_run=True)`.

---

## Current Canonical Plan

See the adoption plan:
[`../plans/autoresearch-orchestrator-adoption.md`](../plans/autoresearch-orchestrator-adoption.md).

That plan is the source of truth for:

- uditgoenka as primary upstream
- karpathy as secondary catch-all audit reference only
- `vendor/autoresearch` submodule parity
- dry-run first behavior
- Perpetua/orama responsibility split
- future `POST /autoresearch/plan` v2 API candidate

---

## What Changed

The autoresearch loop moved from a hardcoded GPU-runner script to the Claude Code plugin
and the Perpetua bridge.

The current architecture is:

1. Source mirror: `vendor/autoresearch` tracks uditgoenka/autoresearch on `master`.
2. Runtime plugin: marketplace add, then `claude plugin install autoresearch@autoresearch`.
3. Bridge: `orchestrator/autoresearch_bridge.py` owns install, sync, preflight, and dry-run.
4. Optional orama modulation receives state, goal, archetype, and safety gates.
   It does not run plugin or GPU work in a dry-run.

---

## Environment Defaults

```bash
# .env, not source code
AUTORESEARCH_REMOTE=https://github.com/uditgoenka/autoresearch.git
AUTORESEARCH_BRANCH=master
LOCAL_AUTORESEARCH_PATH=~/autoresearch
GPU_REPO_PATH=autoresearch
```

`AUTORESEARCH_BRANCH` stays configurable. The default is `master`, the primary upstream branch.

---

## Dry-Run First

Use dry-run before long-running goals:

```python
from orchestrator.autoresearch_bridge import preflight

plan = preflight(
    goal="harden gateway auth token handling",
    dry_run=True,
    use_orama=True,
)
```

Dry-run returns a plan and skips:

- Claude/plugin install or slash commands
- git bootstrap/sync
- SSH
- SCP
- LM Studio HTTP probes
- GPU dispatch
- paid/cloud model calls

---

## Plugin Install - Primary Runtime

```bash
claude plugin marketplace add uditgoenka/autoresearch
claude plugin install autoresearch@autoresearch
```

`install_autoresearch_plugin()` handles this idempotently by checking `claude plugin list` first.

---

## GPU Runner - Secondary Verify Substrate

Still used for `ml-experiment` task types only. Requires:

- SSH access to the GPU runner
- `swarm_state.md` reports `GPU: IDLE`
- sequential GPU load discipline

Do not dispatch while `swarm_state.md` reports `GPU: BUSY`.

---

## Bootstrap Rule

Use:

```bash
uv sync --dev
```

Never regress to bare `pip install` bootstrap paths.

---

## Model Rule

Never hardcode model names. Query the runtime endpoint before use:

```bash
GET $LM_STUDIO_BASE_URL/v1/models
```

---

## `preflight()` Return Shape

Normal execution returns plugin, sync, and GPU-local fields. Dry-run adds a `plan` object.
That v1 plan records the bilevel bounds.
It does not start a runner, and it does not call a v2 repository.

```python
{
    "dry_run": True,
    "preflight_mode": "dry-run",
    "plan": {
        "goal": str,
        "archetype": str,
        "pipeline": list[str],
        "predicate": str,
        "max_cycles": int,
        "upstream_primary": str,
        "upstream_secondary": str,
        "mechanism": "bilevel",
        "tri_level": "optional-not-started",
        "metaresearcher": "adopted-not-started",
        "v2_migration": "pending",
        "serving_grant": False,
    },
    "plugin_ok": None,
    "sync_ok": None,
    "lm_studio_ok": None,
}
```

---

## Related

- [`../plans/autoresearch-orchestrator-adoption.md`](../plans/autoresearch-orchestrator-adoption.md)
- [`../../orchestrator/autoresearch_bridge.py`](../../orchestrator/autoresearch_bridge.py)
- [`../../tests/test_autoresearch_bridge.py`](../../tests/test_autoresearch_bridge.py)
- [`../../CLAUDE.md`](../../CLAUDE.md) section 4
- orama-system `bin/agents/autoresearcher/SOUL.md`
