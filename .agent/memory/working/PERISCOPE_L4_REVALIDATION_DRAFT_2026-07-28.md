# DRAFT — Periscope mirror, desktop, and L4 adapter revalidation

**Date:** 2026-07-28  
**Status:** DRAFT — do not graduate or treat as committed policy until final review  
**Scope:** orama PR #236 review fixes; Periscope Track A; revised L4 B.1–B.3/B.5/B.10/B.11

## Crystallized findings

### Mirrors and integration lineage

| Ref | Intended source | Verified tip | Result |
| --- | --- | --- | --- |
| `periscope:main` | `latentsignal-org/periscope:main` | `852b8e381ead918dc70e64c25233c124b8ecb5e1` | Exact SHA/tree mirror |
| `periscope:agentsview` | `kenn-io/agentsview:main` | `6c3317ad69eb1383928833dda006957a7a2d1f0d` | Exact SHA/tree mirror |
| `periscope:merged` | Fork integration line | `cf070d84b79aeee88c1c21cac99810e946ac9978` | Contains both mirror tips; carries fork work |

No mirror push is currently needed. Do not merge `merged` into `main`.

`merged` has valid dual-pedigree ancestry but is not a clean semantic patch stack
on current AgentsView. Reconstructing it would require classifying 45 historical
fork patches against 583 AgentsView commits, then replaying the post-reanchor
20-file delta. Treat that as a separate lineage-modernization epic, not a
prerequisite for L4.

### Naming policy

- Keep `agentsview` branch names, upstream URLs, compatibility config paths,
  artifact names, fixtures, logs, and reviewer prose unless a functional contract
  requires a different name.
- Preserve all `agentsview.io` URLs while they remain functional; Periscope is a
  sidequest/repackaging, not a severed fork.
- `.air.toml` already runs `tmp/periscope`; no action.
- `.roborev.toml` is non-functional guidance; retain AgentsView wording.

### Desktop sidecar root cause

Tauri declares `externalBin: ["binaries/periscope"]` and the build script produces
`periscope-<target-triple>`, but Rust requested `sidecar("agentsview")`. Tauri
resolves the runtime binary by this stem, so desktop launch fails on every platform.

Minimal draft fix:

1. `desktop/src-tauri/src/lib.rs`: `sidecar("agentsview")` →
   `sidecar("periscope")`.
2. Preserve `~/.agentsview/desktop.env`; correct the misleading comment rather
   than migrating the path.
3. Add shell assertions for the runtime stem and retained legacy env path.

Shell tests pass. Rust tests are blocked in the cloud image because Cargo 1.83
cannot parse a transitive crate requiring edition 2024; this is an environment
toolchain blocker, not a test failure in the patch.

### Revised L4 architecture

The May plan is stale:

- B.1 already exists as the registered/tested Periscope OpenClaw parser.
- AlphaClaw operation events are in-memory SSE, not a durable JSONL source.
- PT's `.state/jobs.jsonl` is durable but is a state-transition stream, not a
  Periscope conversational session.
- Existing Periscope sessions/messages/events APIs make B.5 routes redundant.

PT should own adapters and normalization:

```text
PT supervisor terminal job ─> PT adapter → OpenClaw-compatible JSONL
                                              │
AlphaClaw operation event ───> discovery gate: no durable PT source yet
                                              │
                                              ▼
                     <resolved supervisor state_dir>/periscope/agents/
                                              │
                                              ▼
                           existing Periscope OpenClaw parser/API/UI
```

Periscope config already supports multiple `openclaw_dirs`; include both real
OpenClaw sessions and PT's generated observation directory. This keeps PT state
out of `~/.openclaw/agents` and requires no new Periscope parser or route.

The adapter must receive `self._state_dir` from `OrchestrationSupervisor`;
`$PT_STATE_DIR` is not a universal read authority across PT modules. Periscope
config requires resolved absolute paths, replaces default directories, and is
ignored when the single-valued `OPENCLAW_DIR` environment override is set.
Reserve `pt-supervisor` and `alphaclaw-routing` agent IDs to avoid
`openclaw:<agent>:<session>` key collisions across roots.

Do not claim B.2 complete by emitting `alphaclaw_manager` runtime topology:
manager resolution is startup state, while AlphaClaw operation events are
short-lived in-memory SSE. A real PT-owned per-operation boundary must be found
before wiring the shared serializer for AlphaClaw.

### Adapter prototype evidence (uncommitted)

Draft branch/worktree: `cursor/periscope-l4-adapter-f559`.

- `orchestrator/periscope_adapter.py` emits deterministic, atomic,
  mode-restricted OpenClaw-compatible JSONL under
  `$PT_STATE_DIR/periscope/agents/<agent>/sessions/`.
- `tests/test_periscope_adapter.py` covers disabled-by-default behavior, schema,
  idempotent replacement, path traversal rejection, and POSIX file mode.
- A temporary cross-repo Go contract test successfully parsed actual PT output
  with Periscope `ParseOpenClawSession`: one user message, one assistant message,
  model retained.
- The temporary Go contract test was removed after execution; no Periscope
  parser test or function remains in the draft branch.
- PT pytest could not run in the cloud image because pytest is not installed;
  Python compilation and direct adapter smoke checks passed.

### Token policy

Never commit a real `PERISCOPE_TOKEN`. Periscope API auth uses `auth_token` from
`~/.periscope/config.toml` via `Authorization: Bearer`; `cursor_secret` is a
different credential used for cursor signing. Commit only commented blank
`.env.example` entries. `require_auth = true` must also be set in Periscope
config or the middleware intentionally skips token checks.

### Security prerequisite

The tracked L4 glass design currently contains a previously committed concrete
`cursor_secret` value. Do not copy it into any draft, PR, command, or environment
template. Redaction, rotation, and any history action require a separate
security-policy-compliant branch/PR; this draft records the blocker without
embedding the value.

## Draft lesson candidates

1. **Mirror exactness does not prove a clean integration patch stack.** Verify
   `main` and `agentsview` independently; treat semantic reconstruction of
   `merged` as separate work.
2. **Rename only at functional contracts.** Preserve upstream identity everywhere
   compatible; rename the Tauri sidecar stem because configuration and runtime
   lookup must match.
3. **Adapters belong at the authority boundary.** PT owns AlphaClaw routing and
   supervisor state, so PT normalizes observations into an existing Periscope
   format rather than adding stack-specific functions to Periscope.
4. **A planned parser may already exist or its source may not.** Revalidate code
   and actual persisted data before implementing a dated plan.
5. **Real service tokens never enter tracked environment templates.** Blank
   placeholders name the correct source field; local secret files hold values.
6. **`commit-clean.sh` is not a selective `git commit`.** It writes the staged
   tree and then runs `git reset --hard`, destroying every unstaged edit. Before
   logical-batch commits, preserve other batches in separate worktrees or stage
   the entire intended tree. This session lost and reconstructed the uncommitted
   L4 plan batch after committing only the PR-review-fix paths.

## Review gates before graduation

- Review orama PR #236 fixes and revalidated plan.
- Review uncommitted Periscope desktop diff against the “keep AgentsView” policy.
- Contract-test one PT-emitted fixture with `ParseOpenClawSession`.
- Decide whether Track A closes operationally while lineage modernization remains
  a separate epic.
- Only then graduate lessons through `.agent/tools/learn.py`; do not hand-edit
  semantic JSON/LESSONS records during this draft stage.
