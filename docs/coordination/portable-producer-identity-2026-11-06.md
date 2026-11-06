# Portable producer identity and topology hygiene (2026-11-06)

Closure row C4, Perpetua-Tools part. Canonical register: Orama
`docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md` ("Part 3 review
and revised scope", item 4, and the C4 paragraph). Tests:
`tests/test_coordination_portable_identity.py`.

## New events

`current_worktree_label()` keeps its name (D2) but no longer returns
`<branch>@<cwd>`. It returns a random identifier `ptp-<32 hex>` from
`orchestrator/coordination/producer_identity.py`:

- Created once per worktree with `O_CREAT | O_EXCL` and mode 0600, in
  `$(git rev-parse --git-dir)/pt-producer-id`. That directory is per worktree
  and never tracked. Outside git, the file goes in the runtime state directory.
  `PT_PRODUCER_ID_FILE` names the file explicitly; the test suite uses it to
  keep test runs out of the developer's git metadata.
- The same identifier is reused across restarts. Concurrent first use converges
  on whichever file was created first.
- A candidate already used by a sibling worktree's file is drawn again. After
  five failed draws the call fails closed. A malformed existing file is
  reported and never overwritten.
- On any identity error the label is `ptp-unavailable`; emit paths never crash.

A branch, worktree name or hash of a predictable path is not used: those values
can be confirmed by guessing. No separate mapping file is created. The
identifier file's location is the only local link between the identifier and
its worktree, and it has owner-only permissions.

### Compatibility and caller migration

The public function name, import paths, no-argument signature and string
return type remain compatible. The string's format deliberately changes for
privacy: consumers must treat `worktree` as an advisory label, not split it
on `@`, infer authorization, or use it as a task's durable identity. Event
UUIDs and task IDs retain those separate roles. The known-caller audit covers
repository consumers, not every external installation.

Previously stored labels remain unchanged in append-only history. Derived
readers accept both formats through `classify_payload`/`sanitize_topology`:
legacy labels are redacted, opaque identifiers are retained, and unclassified
shapes are withheld. Existing keys must not be relabeled or correlated with
new IDs by guessing a branch/path. A consumer that persisted old labels as
keys must retain its legacy records and migrate explicitly using an approved
node-local association or start a separate opaque-label namespace. That
association must never be exported to peers. No compatibility mode restores
workstation paths to newly emitted shared events.

## Historical rows and derived views

The new identifier does not repair stored rows. Tracked append-only sources are
not rewritten. `orchestrator/coordination/topology_hygiene.py` acts on derived
views only:

| Class | Meaning | Memory recall | Portable export |
| --- | --- | --- | --- |
| `opaque` | Topology fields hold `ptp-` identifiers | Unchanged | Unchanged |
| `no_topology` | No topology field, or a placeholder (`?`, `None`) | Unchanged | Blocked if a private-looking path remains |
| `legacy_label` | `<branch>@<absolute path>` | Label, branch and path replaced with `legacy-redacted` | Same, then blocked if a private-looking path remains |
| `unclassified` | Any other topology shape | Withheld | Blocked |

Memory recall (`orchestrator/memory_node.py`) sanitizes gossip hits before it
builds recall text. Portable export
(`python -m orchestrator.coordination.topology_hygiene export --db PATH --out FILE`)
writes sanitized JSONL rows and reports exported and blocked counts. The
inventory commands (`inventory --db PATH`, `inventory-episodic PATH`) print
counts only and open their inputs read-only.

## Inventory on 2026-11-06

Run in this worktree on the base revision's tracked data:

| Source | Rows | Flagged |
| --- | --- | --- |
| `.agent/memory/episodic/AGENT_LEARNINGS.jsonl` | 1319 | 0 |
| `.agent/memory/episodic/snapshots/*.jsonl` (3 files) | 13 | 0 |
| `.agent/memory/semantic/lessons.jsonl` | 1647 | 3 |
| Other tracked JSONL under `.agent/` (2 files) | 29 | 0 |

The three flagged lesson rows mention generic home-directory roots for macOS and
Windows in prose, with no user segment. They are false positives of the conservative
detector, not workstation paths, so no additive correction is needed. No local
gossip database existed in the checkouts inspected, so a live store inventory is
owner-held. Run `inventory --db` against each operator's own store.

## Not covered

- LAN replication forwards each payload as stored. New events carry opaque
  identifiers, but the `/gossip/tail` endpoint and the LAN bridge still serve
  historical rows unsanitized. Whether peers count as an export boundary is an
  owner decision.
- Restricting or quarantining raw legacy stores, and any sensitive-history
  removal, need the approved local retention policy or incident procedure.
  Neither is done here.
- Other `cwd` producers outside gossip (`orchestrator/periscope_adapter.py`
  session files, `scripts/cursor/topology_probe.py`) are not changed.
