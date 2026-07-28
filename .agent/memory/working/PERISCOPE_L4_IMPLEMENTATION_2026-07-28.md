# Periscope L4 implementation decisions — 2026-07-28

**Status:** committed policy on `cursor/periscope-l4-adapter-f559`  
**Scope:** security remediation, git hygiene, optional lineage epic, PT adapter wiring

## Security — retired L4 glass design doc

- `orama-system/docs/v2/21-periscope-l4-glass.md` contained a concrete
  `cursor_secret` value and was removed from git tracking.
- Path is gitignored so local copies may remain workstation-only.
- Canonical L4 policy: `orama-system/docs/plans/2026-05-24-periscope-l4-integration-plan.md`
  (2026-07-28 revalidation section).
- API auth uses Periscope `auth_token` (`Authorization: Bearer`), not `cursor_secret`.

## Git hygiene — `commit-clean.sh`

- Removed `git reset --hard` from `scripts/git/commit-clean.sh` (orama canonical).
- `commit-clean.sh` commits **only staged** paths; unstaged edits are preserved.
- Before logical-batch commits: `git add <paths>` (or `git add -A` when intentional),
  then run `commit-clean.sh`. Use separate worktrees for parallel batches.

## Optional lineage-modernization epic

- Reconstructing `periscope:merged` as a clean stack of 45 fork patches over 583
  AgentsView commits is **completely optional** and expensive.
- Documented in `orama-system/docs/plans/2026-07-28-periscope-lineage-modernization-epic.md`.
- Not a prerequisite for L4, ECC, mirror maintenance, or desktop sidecar fixes.

## PT L4 adapter — disabled by default

- Module: `orchestrator/periscope_adapter.py`
- Enable locally: `PERISCOPE_EMITTER_ENABLED=1`
- Periscope skills document the flag; no Periscope code changes required for v1.

### Emission surfaces

| Agent ID | Session ID | Trigger | Content |
| --- | --- | --- | --- |
| `pt-supervisor` | `job_id` | Supervisor terminal states (succeeded/failed/cancelled) | prompt → result/error summary |
| `alphaclaw-routing` | `routing-latest` | `save_routing_state()` after `routing.json` write | planned `route` event JSON → routing summary |

Output path: `<resolved supervisor state_dir>/periscope/agents/<agent>/sessions/*.jsonl`

Periscope consumes via existing `openclaw_dirs` + OpenClaw parser. Reserve agent IDs
`pt-supervisor` and `alphaclaw-routing` to avoid key collisions.

### Wiring guarantees

- Adapter hooks are best-effort (`maybe_emit_*`); failures never break routing
  persistence or job execution.
- `save_routing_state` receives routing dict; adapter uses `STATE_FILE.parent` as
  `state_dir` (same resolved tree as supervisor `self._state_dir` in production).

## Related

- `PERISCOPE_L4_REVALIDATION_DRAFT_2026-07-28.md` — evidence and architecture draft
- `PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md` — path-scoped PR replay
- orama PR #236 branch — doctrine + plan revalidation
