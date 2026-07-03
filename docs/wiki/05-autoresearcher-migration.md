# 05. AutoResearcher Migration - uditgoenka Plugin, Submodule, and Dry-Run

**TL;DR:** Primary mode is `uditgoenka/autoresearch`. Perpetua adopts it in two forms: a tracked source mirror at `vendor/autoresearch` and the Claude Code plugin runtime. GPU runner remains secondary and is only a Verify substrate for ML experiments. Long-running goals must start with `preflight(dry_run=True)`.

---

## Current Canonical Plan

See [`../plans/autoresearch-orchestrator-adoption.md`](../plans/autoresearch-orchestrator-adoption.md).

That plan is the source of truth for:

- uditgoenka as primary upstream
- karpathy as secondary catch-all audit reference only
- `vendor/autoresearch` submodule parity
- dry-run first behavior
- Perpetua/orama responsibility split
- future `POST /autoresearch/plan` v2 API candidate

---

## What Changed

The autoresearch loop migrated from a hardcoded Python script cloned to a GPU runner into a goal-directed Claude Code plugin and Perpetua bridge workflow.

The current architecture is:

1. Source/reference mirror: `vendor/autoresearch` tracks `https://github.com/uditgoenka/autoresearch.git` on `master`.
2. Runtime plugin: `claude plugin marketplace add uditgoenka/autoresearch` plus `claude plugin install autoresearch@autoresearch`.
3. Perpetua bridge: `orchestrator/autoresearch_bridge.py` handles idempotent plugin install, local/GPU sync, preflight, GPU guard, and dry-run autoplan.
4. Optional orama modulation: orama receives state + goal + archetype + safety gates and may apply methodology, but must not execute plugin/GPU work during dry-run.

---

## Environment Defaults

```bash
# .env, not source code
AUTORESEARCH_REMOTE=https://github.com/uditgoenka/autoresearch.git
AUTORESEARCH_BRANCH=master
LOCAL_AUTORESEARCH_PATH=~/autoresearch
GPU_REPO_PATH=autoresearch
```

`AUTORESEARCH_BRANCH` remains configurable, but the default is `master` because the primary upstream currently uses `master`.

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

Normal execution returns plugin/sync/GPU-local fields. Dry-run returns the same envelope plus a `plan` object:

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
