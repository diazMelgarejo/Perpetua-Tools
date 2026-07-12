# 11. agentic-stack `.agent/` Blend — Replaying Local Innovations Across Pin Bumps

**TL;DR:** `vendor/agentic-stack` ships upgrades to `.agent/`, a directory PT has heavily
customized. Blindly overwriting on upgrade would lose PT's fixes; blindly keeping PT's
copy forever would miss real upstream bug fixes. `scripts/git/agentic-stack-agent-blend.sh`
does a 3-way file merge per file, modeled on the same precedent as AlphaClaw's
`feature/MacOS-post-install` reverse-merge flow. This doc records the reusable pattern
**and** the conflict-resolution playbook learned resolving the first real cycle
(v0.9.0 → v0.18.0, 2026-07-11), so the next upgrade doesn't start from zero.

---

## The AlphaClaw precedent

Perpetua-Tools solved an analogous problem for the AlphaClaw fork years before this tool
existed — see `.agent/memory/semantic/lessons.jsonl` `lesson_881de77084d5` and
`lesson_9fffe4530a95`, and [`08-macos-alphaclaw-compat.md`](08-macos-alphaclaw-compat.md):

- Upstream always prevails on the integration line (`main`).
- Local customizations (`feature/MacOS-post-install`) never get overwritten wholesale —
  they sit on the **receiving end** of a merge (`main` reverse-merged INTO the
  customization branch), never the source.
- All merges are union: never delete, always harmonize.
- `setup_macos.py` adds a second, complementary pattern: idempotent patches keyed by a
  `detect` marker (already-applied) and an `old` marker (target) — self-healing every
  time upstream overwrites the file.

`.agent/` isn't its own submodule or branch — it's a tracked directory inside PT that
receives file copies from `vendor/agentic-stack`'s skeleton via `harness_manager.cli
upgrade`. The git-native equivalent of "reverse-merge" at file granularity is a 3-way
merge:

```
base   = vendor/agentic-stack content at the SHA .agent/ was last blended from
ours   = PT's current .agent/<path>          (our innovations)
theirs = vendor/agentic-stack at the new pinned SHA (upstream)
```

`git merge-file -p base ours theirs` unions cleanly whenever upstream and PT touched
different lines; conflicts are reported, never silently resolved, and never written
directly into a tracked `.agent/` file — everything stages under the gitignored
`.agent/.blend-preview/` first.

## Tooling

| Component | Path |
|---|---|
| Blend script | `scripts/git/agentic-stack-agent-blend.sh` (`status \| plan \| apply \| promote`) |
| Blend-state (tracks last-blended base SHA + audit trail) | `.agent/.agentic-stack-blend-state.json` |
| Submodule pin management | `scripts/git/agentic-stack-submodule-sync.sh` (`status \| update \| upgrade`) |
| Dry-run preview wrapper | `scripts/git/install-agentic-stack.sh` |
| Brain-integration blocklist policy | `orama-system/docs/v2/41-agentic-stack-gstack-gbrain-memory-blend.md` §5 |

**Blocklist (permanent, never staged regardless of diff cleanliness):**
`.agent/tools/brain_bridge.py`, `.agent/skills/brain/`. If a merged file *references*
a blocked path without being one itself (see the `_index.md` case below), that
reference must also be excluded — the blocklist is about the policy, not just the path.

## Workflow

```bash
bash scripts/git/agentic-stack-submodule-sync.sh upgrade   # bump vendor/agentic-stack pin
bash scripts/git/install-agentic-stack.sh                  # dry-run preview, sanity check
bash scripts/git/agentic-stack-agent-blend.sh status        # categorize the delta
bash scripts/git/agentic-stack-agent-blend.sh apply          # stage 3-way merges + new files
# review .agent/.blend-preview/ -- resolve any <<<<<<< conflicts by hand
bash scripts/git/agentic-stack-agent-blend.sh promote        # copy clean files into .agent/
```

`promote` only advances the blend-state base SHA once **nothing** is left conflicted —
otherwise the next cycle would diff from the wrong point and silently drop upstream's
intervening changes for the still-unresolved files.

---

## Conflict-resolution playbook (learned 2026-07-11, v0.9.0 → v0.18.0)

7 files conflicted on the first real run. None were resolved by blindly picking one
side — each needed the actual reasoning below. Future cycles should check new conflicts
against this table's *patterns* first; a conflict matching one of these shapes usually
resolves the same way.

| Pattern | Example | Resolution rule |
|---|---|---|
| **Dead duplicate line** — PT has two computations of the same value back-to-back (an old naive one immediately overwritten by a corrected tz-aware one), upstream has just the one clean line | `memory/decay.py` cutoff calc, `memory/promote.py` `now =` | Take upstream's single clean line. This is PT's own leftover artifact from an earlier hand-patch, not a real behavior difference. |
| **Naive-timestamp interpretation** — no tzinfo on a timestamp; is it already UTC, or local wall-clock time that needs converting? | `memory/decay.py` naive-entry normalization | **Keep PT's local-time-and-convert version.** PT's own memory-writing code historically called bare `datetime.datetime.now().isoformat()` (no tz) in several places — see the `tools/learn.py` case below — which captures *local* time, not UTC. Assuming naive-as-UTC (upstream's simpler shortcut) would misdate any of those historical entries by PT's UTC offset. |
| **Two independent fixes, same line** — PT added one fix, upstream independently added an unrelated fix, both on the line they each touched | `tools/learn.py` (PT's `sanitize_tracked_path_leaks()` path-hygiene wrapper vs upstream's `datetime.timezone.utc` fix); `harness/salience.py` (PT's `_parse_timestamp()` Z-suffix handling vs upstream's negative-age floor) | **Combine both — never pick one side.** Losing either reintroduces a real, already-fixed problem (a LINT-006 workstation-path leak, or a naive/negative-age bug). This is the case worth spending the most care on; it's rarely a coincidence when both sides touch the same line for different reasons. |
| **Pure mechanical refactor** — same logic, different shape (context-manager wrap, line reorder), no behavior change | `memory/render_lessons.py` (`with open(...) as f`), `memory/review_state.py` (3-line reorder) | Take upstream's version. Zero PT-unique logic at risk; upstream's is usually the more idiomatic form (e.g. explicit file-handle closing). |
| **New section inserted into an existing, non-blocked file, one of the new entries points at a blocked path** | `skills/_index.md` — PT's `## hardware-policy` entry vs upstream's 5 new skill entries, one of which (`## brain`) documents the blocked Brain skill | **Union everything except the blocked entry.** The file itself isn't on the blocklist, so the tool's path-level blocklist check doesn't catch this automatically — a human (or a future tool enhancement) has to check new *content* inside merged files against the blocklist, not just new file paths. |

### Tool enhancement identified, not yet built

The blocklist in `agentic-stack-agent-blend.sh` only excludes new files whose *path*
matches a blocked prefix. It does not scan merged content for references to blocked
skills inside otherwise-unblocked files (the `_index.md` case). Flagged for a future
pass; until then, treat any `~` (modified, not `+` new) conflict touching `_index.md`
or similar aggregator files as needing a manual blocklist re-check regardless of what
the tool reports.

---

## Related

- Session log: [`../LESSONS.md`](../LESSONS.md) (search `agentic-stack-agent-blend`)
- `.agent/memory/semantic/lessons.jsonl` — `lesson_9d1013fedd41` (pattern), plus the
  playbook-specific lesson graduated alongside this doc
- [`08-macos-alphaclaw-compat.md`](08-macos-alphaclaw-compat.md) — the precedent this
  pattern is adapted from
- orama-system `docs/v2/41-agentic-stack-gstack-gbrain-memory-blend.md` — the design
  doc this tool implements §7's union-merge rules for
- PR #208 (Perpetua-Tools) — where the tool was built and this first cycle was run
