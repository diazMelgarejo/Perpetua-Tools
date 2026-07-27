# Plan: Coordination Phase 0F canon + Part 2 (`liveness.py`)

**Source:** User confirm 2026-07-27; revitalized from coordination consolidation +
STM master plan work  
**Selected milestone:** Coordination Phase 0F completion + Part 2 `liveness.py`  
**Complexity:** Medium  
**Canonical repo:** Perpetua-Tools (orama: pointer docs only)  
**Autoplan intake:** run `/autoplan` against this file on PT `main`

## Summary

Canonicalize **coordination Phase 0F** (CLI contract freeze) separately from **STM
Phase 0** (swarm security graph). Land `docs/coordination/` with shared
terminology disambiguation, revive `docs/references/coordination-consolidation-plan-review-2026-07-18.md` as the in-repo evidence copy, extract heartbeat handlers into `orchestrator/coordination/liveness.py`, and commit remaining doc/code work.

**Terminology (mandatory):** [`../coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md`](../coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md)

## Patterns to mirror

| Category | Source | Pattern |
| --- | --- | --- |
| Module extraction | `orchestrator/coordination/task_queue.py` | Module docstring cites consolidation plan; `_error`/`_warning` helpers; async bus functions |
| CLI dispatch | `orchestrator/coordination/cli.py` | Import capability functions; thin `_heartbeat_*` wrappers calling module |
| Contract tests | `tests/test_agent_coordination_cli_contract.py` | `EXPECTED_LEAVES` (29); `build_parser()` leaf walk; handler monkeypatch |
| Heartbeat tests | `tests/test_agent_coordination_heartbeat.py` | Import from `cli` today — re-point to `liveness` after extraction |
| Doc hub | `docs/phase-0-specifications/README.md` | Banner + cross-links; disambiguation pointer |
| Review evidence | `docs/references/coordination-consolidation-plan-review-2026-07-18.md` | In-repo canonical; supersedes off-repo references |

## Files to change

| File | Action | Why |
| --- | --- | --- |
| `docs/coordination/README.md` | DONE | Coordination hub |
| `docs/coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md` | DONE | Canonical naming |
| `docs/references/coordination-consolidation-plan-review-2026-07-18.md` | DONE | Status 2026-07-27 banner |
| `orchestrator/coordination/liveness.py` | CREATE | Move `_heartbeat_*` from `cli.py` |
| `orchestrator/coordination/cli.py` | UPDATE | Import from `liveness`; keep parser + dispatch |
| `orchestrator/coordination/__init__.py` | UPDATE | Export liveness symbols if needed |
| `tests/test_agent_coordination_heartbeat.py` | UPDATE | Import from `liveness` |
| `tests/test_agent_coordination_cli_contract.py` | UPDATE | Docstring → canon path |
| `docs/next/2026-07-17-coordination-module-consolidation-plan.md` | UPDATE | Link `docs/coordination/` |
| `docs/phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md` | DONE | Coordination row → `docs/coordination/` |
| `docs/wiki/13-coordination-phase-0f-cli-contract.md` | CREATE | Wiki TL;DR + disambiguation link |
| `docs/wiki/README.md` | UPDATE | Index #13 |
| `orama-system/docs/next/2026-07-27-coordination-phase-0f-pointer.md` | CREATE | Orama pointer + disambiguation link |

**Do not** edit off-repo reference handoff copies — PT `docs/references/` supersedes.

## Tasks

### Task 1: Terminology + hubs — DONE

### Task 2: Revive in-repo review doc — DONE

### Task 3: Extract `liveness.py`

- **Action:** Move `_heartbeat_list`, `_heartbeat_check`, `_heartbeat_dashboard`,
  `_heartbeat_pulse`, `_heartbeat_kill`, `_heartbeat_timeline`,
  `_heartbeat_cleanup` (+ helpers they need) from `cli.py` to `liveness.py`
- **Mirror:** `task_queue.py` / `phases.py` extraction commits
- **Validate:**

```bash
pytest tests/test_agent_coordination_cli_contract.py \
       tests/test_agent_coordination_heartbeat.py -q
```

### Task 4: Cleanup characterization test (review item #2)

- **Action:** Ensure heartbeat cleanup test uses `kind=agent_release`, time-patched
  DEAD threshold — align with `coordination-consolidation-plan-review` §2
- **Validate:** `pytest tests/test_agent_coordination_heartbeat.py -k cleanup -q`

### Task 5: Stale reference sweep

- **Action:** Replace stale “nonexistent Phase 0F” with link to `docs/coordination/`
- **Validate:** `rg -n 'nonexistent.*0F|0F document' docs/`

### Task 6: Wiki #13 + orama pointer

### Task 7: Land code commits on `main`

## Validation

```bash
pytest tests/test_agent_coordination_cli_contract.py \
       tests/test_agent_coordination_heartbeat.py \
       tests/test_agent_coordination_queue.py -q
rg -n 'Phase 0F|STM Phase 0' docs/coordination docs/phase-0-specifications/README.md
```

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Confuse STM Phase 0 with 0F in future docs | Medium | Mandatory link to disambiguation file |
| Heartbeat import cycle cli ↔ liveness | Low | liveness imports monitor only; cli imports liveness |

## Acceptance

- [x] `docs/coordination/` hub + disambiguation file exist
- [x] `phase-0-specifications/README` + wiki banner point to disambiguation
- [x] Review doc revived with 2026-07-27 status
- [ ] `liveness.py` extracted; tests green
- [x] No “nonexistent Phase 0F” in PT `docs/`
- [x] Plan on `docs/next/` and pushed

## Autoplan intake (/autoplan)

When running `/autoplan` in Codex against this plan:

1. Read [`../coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md`](../coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md) first.
2. Scope = Task 3–4 (code) + Task 6 (remaining docs) — not STM wiring or mesh.
3. Do not place coordination canon under `phase-0-specifications/`.
4. Evidence copy lives only under `docs/references/` in PT.
