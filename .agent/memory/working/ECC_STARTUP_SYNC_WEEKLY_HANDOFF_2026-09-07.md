# ECC Startup Sync Weekly Handoff

**Status:** Local memory-only handoff; not pushed or published.
**Scope:** Confirmed Perpetua-Tools work visible from local refs for 2026-09-01 through 2026-09-07. This is a coordination aid, not a claim that every repository or agent session is closed.

## Executive Summary

The active work separated a public health-route security fix from a follow-up
ECC harness repair. The repair removes an unsafe startup side effect: a FastAPI
lifespan could trigger a live ECC clone/pull and tracked-file sync merely by
starting the application or its test client. ECC synchronization is now
operator-opt-in at runtime; the authenticated forced maintenance endpoint
remains available.

The follow-up also retained the useful parts of incidental upstream changes:
schema-correct command frontmatter and accurate Codex guidance. It explicitly
rejected unreviewed configuration replacement, including floating MCP package
changes that would discard a reviewed project pin.

## Verified Timeline

| Time (UTC) | Ref | Event | Disposition |
| --- | --- | --- | --- |
| 2026-09-01 to 2026-09-04 | `origin/main` at `8df05883` | Coordination handoff validation and related memory-integrity work accumulated on the main lineage. | Landed on the locally fetched `origin/main`. |
| 2026-09-01 | `84ed45c7` | Weekly memory reconciliation branch recorded five priority lessons. | Separate local branch; not in `origin/main`. |
| 2026-09-06 | `96b17bdb` | Integration branch preserved a Sep 5 proactive-recall audit. | Separate local branch; not in `origin/main`. |
| 2026-09-06 | `a5066d94` | Endpoint-policy Gate 1 evidence vectors added. | Separate local branch; not in `origin/main`. |
| 2026-09-07 01:12 | `2d941d5b` | PR #380 head: public health endpoint hardening. | Published branch tip; not in `origin/main`. |
| 2026-09-07 01:18 | `2d941d5b` | Proactive recall ran in the newly created ECC harmonization worktree. | Preserved raw episodic record below. |
| 2026-09-07 01:29 | `652c8f2c` | ECC startup synchronization made explicit opt-in. | Local repair commit; not pushed. |
| 2026-09-07 01:29 | `990fc6b0` | Command metadata and Codex guidance harmonized. | Local repair commit; not pushed. |

## Important Fixes

### PR #380: public health endpoint

`2d941d5b` hardened the public health route while retaining the intended
unauthenticated observability surface. Its scope is limited to
`orchestrator/fastapi_app.py` and `tests/test_fastapi_health.py`.

### ECC startup synchronization

`652c8f2c` changed the operational contract:

- `ECC_SYNC_ENABLED` is read at invocation time rather than frozen at import.
- Its default is disabled; normal application and test startup cannot begin a
  live clone/pull or rewrite tracked harness files.
- Explicit opt-in retains approved startup maintenance behavior.
- `POST /ecc/sync?force=true` keeps its existing authenticated maintenance
  role even while background opt-in is disabled.
- Regression tests cover the disabled default, forced path, enabled path, and
  FastAPI lifespan scheduling.

### Harness metadata and Codex guidance

`990fc6b0` retained only the defensible portions of incidental ECC output:

- Five related command files use the schema-correct `allowed-tools` key.
- `.codex/AGENTS.md` now treats vendor changes as review proposals, removes
  nonexistent local script/document claims, and describes model choices by
  current capability rather than stale version labels.
- The reviewed `.codex/config.toml` MCP pin remains untouched. Upstream sync
  must not silently replace it with a floating package reference.

## Memory Provenance Correction

The original uncommitted recall row was initially described as a possible
concurrent writer. That classification was wrong.

Evidence establishes that the recall was performed from the ECC harmonization
worktree by the active Codex session:

1. The worktree branch was created from the PR #380 head at 01:17 UTC.
2. The episodic entry timestamp is 01:18 UTC and its `commit_sha` is exactly
   the current head, `2d941d5b`.
3. The recall tool records its provenance through the local worktree's
   `git rev-parse HEAD`; its PID-style run identifier is process provenance,
   not an agent identity.
4. The repair commits followed at 01:29 UTC, so the event is pre-change
   decision context, not a post-repair verification.

The raw record is deliberately preserved unchanged. A second recall in the
audit worktree is also retained as a separate timestamped record. Neither row
is a lesson or proof of implementation quality; tests and review evidence are
the implementation authority.

## Validation

The ECC repair branch completed these focused checks before this memory-only
handoff:

- 43 focused tests passed, covering resilience, observability lifespan,
  FastAPI health, connectivity, and model-endpoint behavior.
- Five changed command frontmatters were parsed and validated.
- `python3 scripts/review/repo_hygiene.py .` passed.
- `git diff --check` passed.

Known warnings were pre-existing deprecations from the Starlette TestClient
and the legacy orchestrator import path; no test failed.

## Current Branch Truth

| Branch | Tip | Purpose | Publication |
| --- | --- | --- | --- |
| `hotfix/health-route-ssrf-gap-20260907` | `2d941d5b` | PR #380 health fix | Remote branch exists. |
| `chore/ecc-sync-harmonization-20260907` | `990fc6b0` | ECC behavior and harness documentation | Local only. |
| `docs/ecc-startup-sync-memory-20260907` | parent `990fc6b0` plus this commit | Memory-only audit and handoff | Local only. |

## Handoff Contract

1. Do not merge or push any of these local commits without explicit review
   and publication authorization.
2. Keep the ECC behavior commits separate from this memory-only commit.
3. Preserve the raw episodic recall events byte-for-byte when integrating
   memory; append and deduplicate rather than rewriting history.
4. Before any ECC update, distinguish generated telemetry, reviewed local
   overlays, and upstream proposals. Only the second category may be restored
   automatically after its reviewed mechanism has run.
5. Before attributing a dirty JSONL row to another actor, inspect timestamp,
   current-head provenance, worktree reflog, file modification time, and the
   writer implementation.

## Coordination Pointer

Post this repository-relative path and the memory commit SHA to GossipBus only
after the commit exists. State that the handoff is local-only until a separate
push authorization is given.
