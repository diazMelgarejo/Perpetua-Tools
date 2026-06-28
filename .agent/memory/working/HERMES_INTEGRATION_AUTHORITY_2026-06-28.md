# Hermes Integration Authority — 2026-06-28

**Status:** Implemented on `orama-system` `main`  
**Plan:** `orama-system/docs/plans/2026-06-28-hermes-integration-authority.md`

## Decisions locked

| Topic | Choice |
|-------|--------|
| Branch policy | `main` + logical batches |
| Paths in repo | Env placeholders only; absolute at runtime in runners |
| Envelope | Core trio + harness extensions (superset/subset with OpenClaw) |
| Identity | `agent_id` (owner) + `executor_id` (runner) when delegating |
| L1 transport | **B** — opaque `transport` object on L2 for OTel/Periscope v1 |
| Path casing | Warn-only in `warnings[]` |
| Lesson mining | **Optional** — `OPTIONAL_WRAPPERS`; `--include-optional`; **no PT dependency** |

## Canonical references

- `bin/orama-system/skills/hermes-harness/SKILL.md` v1.1.0.0
- `bin/orama-system/skills/hermes-harness/references/hermes-universal-invocation-protocol.md`
- Tests: `tests/test_hermes_invoke_envelope.py`, `tests/test_hermes_thin_skills.py`

## Thin wrappers

**Required (4):** council, review, delegate, hardware-policy — `install_hermes_thin_skills.py --install`

**Optional (1):** lesson-mining — `--include-optional` only; orama-system does not depend on Perpetua-Tools.

## Next batch (deferred)

- Mac cross-harness E2E (`openclaw-status` on fabric host)
- v2 transport schema in `/docs/v2` for Periscope replay
