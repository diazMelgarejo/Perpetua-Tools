# Codex G7 Continuity And Procedure Record

Date: 2026-07-15
Status: working memory / cross-session recovery record
Scope: G7 authenticated SSE planning, Firecrawl research procedure, PT memory continuity, and context-loss safeguards.

## Why This Record Exists

This record preserves the last 48 hours of work that crossed the Orama and Perpetua-Tools repositories. It complements:

- .agent/memory/working/FLEET_MESH_AVALANCHE_TRACE_2026-07-14.md
- .agent/memory/working/FLEET_MESH_CROSS_REPO_INDEX_2026-07-14.md

The fleet documents explain why G7 is Phase-7-adjacent. This document records the G7 implementation-planning work, the research procedure, and the operational failures that must not be repeated after a long chat, a harness reset, or a different Codex session resumes the task.

## Confirmed G7 Artifacts

On the Orama branch G7-Async-notifications-mvp, these commits were created and synchronized:

| Commit | Artifact | Purpose |
| --- | --- | --- |
| f796fa1a | docs/G7-ASYNC-NOTIFICATIONS-ANALYSIS.md and docs/plans/2026-07-14-g7-async-notifications-next-steps.md | Hardened the existing G7 notification plan, confirmed docs/v2 precedence, and kept the MVP portal-local. |
| d2a78405 | docs/superpowers/references/2026-07-14-g7-sse-production-patterns.md | Saved a cited Firecrawl research result plus a repository-specific implementation plan. |
| ee1caa7d | docs/superpowers/plans/2026-07-14-g7-authenticated-sse-mvp.md | Saved the detailed TDD implementation plan. |

The branch was verified equal to origin/G7-Async-notifications-mvp after the final fetch.

The committed G7 research establishes these decisions:

1. The MVP remains a default-off, process-local, best-effort portal stream.
2. The envelope needs an opaque event_id in addition to version, type, event_type, ts, source, data, and payload.
3. Stream frames use standard SSE id, event, and JSON data fields.
4. Per-subscriber queues are bounded. On overflow, discard the oldest queued event and retain the newest. Record loss in process.
5. Reconnect means fetch a fresh redacted portal snapshot and resume live delivery. There is no durable replay, ten-day replay window, or thirty-day retention rule in G7.
6. Durable storage, mesh replication, Redis or NATS, webhooks, and v2.5 safety enforcement remain outside the MVP.

## Firecrawl Procedure And Correction

The user had already installed and authenticated Firecrawl before the research pass. The supplied setup included the CLI, MCP configuration for Claude Code and Codex, available CLI skills, and a successful scrape smoke test.

User-reported process failure: the agent repeatedly treated Firecrawl as unavailable or insufficiently specified and asked for repeated confirmation instead of starting the bounded research task. The user reports having to restate or force that procedure five times. Preserve this as a correction, not as a claim that Firecrawl itself failed.

What eventually worked:

1. Read the deep-research and Firecrawl CLI skill instructions.
2. Use a five-minute cap when the user supplies that cap.
3. Search four narrow evidence sets: FastAPI SSE and browser auth, Starlette queue and backpressure behavior, SSE protocol/reconnect semantics, and production OSS examples.
4. When the sandbox could not resolve api.firecrawl.dev, rerun with approved network access rather than abandoning research.
5. Save the synthesis under docs/superpowers/references rather than leaving results only in chat.
6. Prefer primary sources: HTML SSE standard, FastAPI documentation, MDN, OWASP CSRF guidance, and the maintained sse-starlette project. Treat demos, blogs, and forum posts only as secondary evidence.
7. Record negative evidence: no discovered FastAPI notification demo met the requested production-reference bar, so no demo code was adopted as a convention.

Procedure rule:

- When the user provides a working Firecrawl installation, credentials, a successful smoke test, the research question, authority filter, output shape, and time budget, begin the bounded research pass. Do not re-litigate setup, ask for the same information again, or substitute a generic answer.
- If the network sandbox blocks the CLI, retry with approved network access. If hosted research remains unavailable, use the available basic web search fallback and label the evidence quality.
- Save the research report and source links before writing the implementation plan.

## Authenticated SSE Findings That Must Survive Context Loss

The pre-existing scaffold is in:

- Orama src/orama_system/portal_notifications.py
- Orama src/orama_system/portal_server.py
- Orama tests/test_portal_notifications.py

Important implementation gap found during research:

- A native browser EventSource cannot attach an Authorization header.
- The portal auth helper accepts either a bearer header or the existing orama_control_plane_token cookie.
- The existing portal code did not issue that cookie for the notification stream.
- A 401 denial test alone does not prove an authenticated browser can subscribe.

The plan therefore specifies a narrow POST /api/notifications/session bootstrap that requires an existing bearer, validates same-origin lifecycle rules, and sets a short-lived host-only HttpOnly SameSite=Strict cookie scoped to /api/notifications. It must never accept a bearer query parameter and is not a general portal-login feature.

## Autoplan Boundary

The requested Autoplan pass was not fabricated. In this Codex runtime, the Autoplan skill requires an AskUserQuestion approval tool that was not available. The correct result was BLOCKED — AskUserQuestion unavailable.

Do not claim that Autoplan completed, do not invent approval-gate output, and do not silently replace it with auto-decisions. The detailed writing-plans artifact is a usable implementation handoff, but it is not an Autoplan result.

## Long-Conversation And Web-Codex Recovery Failure

User-reported behavior: a web Codex counterpart with a very long conversation can lose the current conversational tail and resume from the last recorded thread exchange before the length limit. This record does not diagnose the platform internals; it records the operational consequence and the recovery method.

Recovery protocol for any harness after compaction, browser refresh, context limit, or unexpected return to an older exchange:

1. Read this record and the fleet avalanche trace before proposing work.
2. Verify the live repository, worktree, branch, HEAD, remote tracking state, and dirty paths. Do not trust a remembered branch name.
3. Read the current G7 research and implementation plan before asking questions already answered there.
4. Treat user-supplied tool setup and prior verified output as evidence unless the filesystem or live command contradicts it.
5. Write or update a small working-memory checkpoint before a long research, review, or multi-repository operation.
6. Commit only intentional memory or documentation changes. Stage explicit paths, never use a broad add.
7. Report unrelated dirty paths separately and do not reset, stash, merge, or include them merely to make a status display clean.

## Recovered Web-Codex Folder-Reconstruction Handoff

User-reported handoff: a web Codex session reconstructed the fleet-mesh document
lineage and wrote the active/archive indexes, but could not run the Python memory
tools needed to preserve its own experience. It could write inside the document
folders, but its process did not complete a PT `.agent` memory capture.

Confirmed work from the existing avalanche trace:

- Orama active index: `docs/next/fleet-mesh/README.md` in commit `3ef0bbf`.
- Orama archive index: `docs/archive/fleet-mesh/README.md` in commit `72dbb59`.
- Orama continuation map: `docs/next/fleet-mesh/phase-7-to-10-roadmap.md` in
  commit `5efe356`.
- The active/archive index pass deliberately did not physically relocate legacy
  files. A real local checkout and `git mv` remain required if physical relocation
  is desired; delete-and-recreate would lose useful history.

Recovery action performed by this PT session:

1. Preserve the web-session report as a user-reported handoff rather than claiming
   that the original session ran `recall.py`, `learn.py`, or `memory_reflect.py`.
2. Link the result to the existing avalanche trace and cross-repo index.
3. Run PT's `python3` memory tools here to record the durable procedure and the
   episodic action.
4. Keep the folders/indexes as completed evidence; do not repeat the indexing or
   silently turn an index-only pass into an unverified physical move.

Rule for assisting a constrained harness:

- If an agent can produce a coherent index or reconstruction but cannot execute
  the local memory tooling, a capable PT session should verify the reported Git
  evidence, record the report with its provenance, run the supported memory tools,
  and name any unperformed operation explicitly. The repair is additive memory
  capture, not a rewrite of the original session's history.

## Verified Fleet-Mesh Relocation

On 2026-07-15, a local Orama `main` checkout was synchronized to `43a3cde5`,
then performed the previously deferred history-preserving relocation with
`git mv`. The validated relocation, repaired links, and navigation indexes were
committed to Orama `main` as `599a08e3`.

Active documents now live in `docs/next/fleet-mesh/`:

- `2026-07-08-self-healing-mesh-degradation-modes.md`
- `2026-07-10-phase-integration-map.md`
- `2026-07-10-oasn-p2p-architecture-research.md`
- `G7-ASYNC-NOTIFICATIONS-ANALYSIS.md`
- `2026-07-14-g7-async-notifications-next-steps.md`

Completed or historical records now live in `docs/archive/fleet-mesh/`:

- `PHASE-6-IMPLEMENTATION.md`
- `2026-07-10-pr2-phase0-review-crossreference.md`

The active/archive indexes, roadmap, internal Markdown links, and explicit
repository-relative paths were updated in the same worktree. `git diff --check`
and `python3 scripts/review/repo_hygiene.py .` passed. The file moves are
reported by Git as renames, so their history remains traceable.

## Cross-Repository Navigation Graph

The local Orama worktrees now contain a deliberate graph for context recovery,
not an all-to-all collection of links:

1. The active fleet-mesh index points to canonical `docs/v2/`, the mesh and
   security hubs, the mother plan, the integration map, OASN research, G7
   analysis, branch-local SSE research, the implementation handoff, PT runtime
   companions, PT security companions, and the completed-evidence archive.
2. The archive index points back to the active index and canonical authority so
   a completed report or historical ledger cannot become an accidental source of
   implementation authority.
3. The G7 authenticated-SSE plan has the matching authority order, node map,
   and directed paths. It treats the G7 MVP as Phase-7-adjacent, default-off,
   portal-local work and keeps durable replay, cross-process fan-out, mesh
   replication, and safety enforcement in their separately governed future
   plans.
4. The graph uses direct links for high-value neighbors and clear directional
   paths for longer relationships. This preserves a small-hop route to the
   governing source without making every document a duplicate wiki page.

Validation performed after these additions:

- all local Markdown links in both fleet-mesh indexes resolve;
- all local Markdown links in the G7 implementation plan resolve;
- `git diff --check` passed in both Orama worktrees;
- `python3 scripts/review/repo_hygiene.py .` passed in both Orama worktrees.

The active G7 branch was then integrated with the organized documentation tree
through merge commit `c1a4a31d` on Orama `main`. That merge carries the portal
notification scaffold, tests, G7 analysis, production research, detailed TDD
handoff, and this navigation graph. The G7 worktree still has pre-existing
untracked `.firecrawl/` research cache; it remains excluded.

## PT Worktree State At The Time Of This Record

Perpetua-Tools main was synchronized through commit 3be30907. That commit added the fleet avalanche trace. The short cross-repo pointer remains present.

A separate Perpetua-Tools checkout remained on kimi-meta-remediation with pre-existing vendor/ecc-tools modification and untracked packages/agentic-stack content. Those paths were explicitly excluded and left untouched. The checkout could not switch to main because main was already checked out by the clean PT main worktree. This was correct Git worktree protection, not a reason to force-detach the other worktree.

## Resume Checklist

Before continuing G7 implementation:

1. Open the G7-Async-notifications-mvp worktree and verify its branch against origin.
2. Read docs/superpowers/references/2026-07-14-g7-sse-production-patterns.md.
3. Read docs/superpowers/plans/2026-07-14-g7-authenticated-sse-mvp.md.
4. Read the canonical Orama docs/v2 security and GossipBus specifications before changing code.
5. Execute the plan in its stated TDD order: envelope and queue, redacted delta publisher, browser session path, SSE framing, then operator documentation and acceptance coverage.
6. If an Autoplan environment with its approval tool is available, run it against the saved implementation plan and save its genuine output. Otherwise retain the explicit blocked status.

## Durable Lessons To Extract

- Research readiness comes from the verified user-provided tool state and task inputs, not repeated agent uncertainty.
- Context recovery must start from committed working-memory artifacts plus live Git state, not the oldest surviving chat turn.
- A plan or research result is not evidence that an approval-gated review pipeline ran; preserve the difference.
- Cross-repo continuity records must use repository-relative paths, commit IDs, branch names, and generic tool names only.
