# Coordination Closure Packet - PT PR #260 / Orama v2 Privacy Boundary

Date: 2026-07-18
Audience: Claude, ClinePass, Kimi, Codex, offline LAN agents, and future
OramaSys v2 migration agents

## Status

The privacy and portable-memory closure is complete.

PT PR #260:
- Branch: `replace/pr258-clean-snapshot-20260718`
- Tip: `41521e0c`
- State: pushed and synced
- PR: `https://github.com/diazMelgarejo/Perpetua-Tools/pull/260`

Orama:
- Branch: `main`
- Tip: `b6fea437`
- State: pushed and synced

## What Changed

PT:
- Hardened `.agent` privacy scanning so agent memory is a first-class guarded
  surface.
- Added PT memory lessons for source-row scanning and category-only security
  rules.
- Added a Cybersecurity / OpSec / SecOps domain rule to PT memory.
- Added a durable whiteboard pinned note for future agents.
- Added a heartbeat-vs-log liveness handoff note for future coordination loops.
- Kept exact private values out of tracked files; guards load them from an
  off-repo local-only registry.

Orama:
- Added `docs/v2/47-portable-memory-local-topology-invariant.md`.
- Cross-linked that invariant from adjacent v2 security, repository, memory,
  and methodology docs.
- Updated `oramasys-method` so future agents apply this invariant before
  editing tracked memory, guards, skills, or multi-repo security policy.
- Scrubbed concrete local-topology examples from the touched v2 docs.

## Validation Evidence

PT:
- `python3 scripts/review/repo_hygiene.py .` passed.
- Full `.agent` scan covered 332 files with 0 errors.
- Focused hygiene and attribution tests passed: 82/82.

Orama:
- `git diff --check` passed.
- `python3 scripts/review/repo_hygiene.py .` passed.
- Updated-doc local-topology scan found no hits.
- Main-push attribution hook reported the pushed range clean.

## Pinned Invariant

Portable agent memory is a security boundary.

Tracked files may name sensitive categories only:
- private identity literals
- private or unclassified email addresses
- credentials and API keys
- device addresses and local endpoints
- workstation topology
- temp-worktree topology
- local path fragments

Tracked files must not contain concrete values for those categories. Exact
private values stay in an off-repo local-only registry and are loaded by guards
at runtime.

## Operational Rules For Future Agents

- A negative rule must not leak the literal it is trying to ban.
- Supersession is not sanitization. A replacement note or rendered view does
  not clean the older source row that produced it.
- Scan both source rows and rendered views:
  - episodic JSONL
  - semantic JSONL
  - candidates
  - working notes
  - protocols
  - skills
  - rendered summaries
- Guard output should report category, file, and line only. Do not print matched
  private values.
- Board `log()` messages and `heartbeat pulse()` events are separate. Posting
  detailed logs does not refresh liveness; long-running agents must call
  `heartbeat pulse <agent_id>` directly and periodically.
- Before ending a security/privacy session: scan, test, commit, push, fetch,
  verify branch state, and inventory dirty worktrees.
- Keep the critical whiteboard queue item open until all offline agents have
  had a chance to read it.

## Coordination Surfaces Already Updated

- GossipBus coordination log: closure posted by `codex-primary-orchestrator`.
- Heartbeat board: `codex-primary-orchestrator` pulsed after closure.
- PR #260: closure comment posted.
- Critical queue item remains open:
  `Coordination-whiteboard-pinned-privacy-memory-opsec-20260718-879de23f`.
- Claude added the heartbeat-vs-log liveness-gap handoff and confirmed the
  stalled-state fix by pulsing its heartbeat directly.

## Offline LAN Handoff

When an offline Windows/LAN agent comes back:

1. Read this closure packet first.
2. Pull or fetch the relevant repo before editing.
3. Re-read the pinned invariant in PT and Orama.
4. Run the guard before touching memory or security docs.
5. Post a board acknowledgement without echoing private values.

## Cross-Repo Pointers

PT:
- `.agent/memory/semantic/DOMAIN_KNOWLEDGE.md`
- `.agent/memory/semantic/LESSONS.md`
- `.agent/memory/working/WHITEBOARD_PINNED_PRIVACY_MEMORY_OPSEC_2026-07-18.md`
- `.agent/memory/working/HEARTBEAT_VS_LOG_LIVENESS_GAP_2026-07-18.md`
- `scripts/review/repo_hygiene.py`

Orama:
- `docs/v2/47-portable-memory-local-topology-invariant.md`
- `bin/orama-system/skills/oramasys-method/SKILL.md`
