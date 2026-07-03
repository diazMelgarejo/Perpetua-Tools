# ORAMA v0.9.4.0 AutoResearch Subsection - Historical Helper

This file was originally a copy-paste helper for orama-system `SKILL.md` on branch `v0.9.4.0`.

Current canonical plan: [`docs/plans/autoresearch-orchestrator-adoption.md`](plans/autoresearch-orchestrator-adoption.md).

Use this file only as historical context. The current implementation should follow the adoption plan, `orchestrator/autoresearch_bridge.py`, and orama-system `bin/agents/autoresearcher/SOUL.md`.

---

## Current AutoResearch Integration Rule

When the coordinating system reports `task_type` of `autoresearch` or `ml-experiment` from Perpetua-Tools:

1. Start with Perpetua dry-run planning for long-running goals:

   ```python
   from orchestrator.autoresearch_bridge import preflight

   plan = preflight(goal="<goal>", dry_run=True, use_orama=True)
   ```

2. Defer runtime topology to Perpetua-Tools. Perpetua owns plugin install, local/GPU sync, LM Studio probes, GPU guard, and `swarm_state.md`.

3. Let orama-system apply methodology only after Perpetua has produced a state + goal + archetype + safety-gate plan. orama must not execute plugin, SSH, SCP, LM Studio, or GPU work during dry-run.

4. Treat `swarm_state.md`, `log.txt`, and `val_bpb` as the truth for ML experiment state and metrics.

5. Use uditgoenka/autoresearch as the primary upstream. Use karpathy/autoresearch only as a secondary catch-all audit reference for the original ML loop.

---

## Cross-Repo Stack

Perpetua-Tools runtime/state authority -> optional orama-system methodology -> ECC-style skill routing -> uditgoenka/autoresearch plugin/submodule -> GPU substrate only for `ml-experiment` verification.

---

## Related

- [`docs/plans/autoresearch-orchestrator-adoption.md`](plans/autoresearch-orchestrator-adoption.md)
- [`docs/wiki/05-autoresearcher-migration.md`](wiki/05-autoresearcher-migration.md)
- [`orchestrator/autoresearch_bridge.py`](../orchestrator/autoresearch_bridge.py)
