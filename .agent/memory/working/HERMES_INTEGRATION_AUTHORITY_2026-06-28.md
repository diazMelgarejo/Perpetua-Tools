# Hermes Integration Authority — 2026-06-28

**Status:** Implemented on `orama-system` `main`  
**Plan:** `orama-system/docs/plans/2026-06-28-hermes-integration-authority.md`

## Decisions locked

| Topic | Choice |
|-------|--------|
| Branch policy | `main` + logical batches (no per-task feature branches) |
| Paths in repo | Env placeholders only; absolute at runtime in runners |
| Envelope | Core trio + harness extensions (superset/subset with OpenClaw) |
| Identity | `agent_id` (owner) + `executor_id` (runner) when delegating |
| L1 transport | **B** — opaque `transport` object on L2 for OTel/Periscope v1 |
| Path casing | Warn-only in `warnings[]` |
| Lesson mining | `commands/pt-orama-lesson-mining` → PT `.agent/tools/learn.py` |

## Canonical references

- `bin/orama-system/skills/hermes-harness/SKILL.md` v1.1.0
- `bin/orama-system/skills/hermes-harness/references/hermes-universal-invocation-protocol.md`
- Tests: `tests/test_hermes_invoke_envelope.py`, `tests/test_hermes_thin_skills.py`

## Thin wrappers (5)

`install_hermes_thin_skills.py` installs: council, review, delegate, lesson-mining, hardware-policy.

## Next batch (deferred)

- Mac cross-harness E2E (`openclaw-status` on fabric host)
- v2 transport schema in `/docs/v2` for Periscope replay
- `auto_dream.py` gate before tag bump
