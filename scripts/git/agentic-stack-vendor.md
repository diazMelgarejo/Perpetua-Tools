# vendor/agentic-stack — upstream reference submodule

Perpetua-Tools vendors [agentic-stack](https://github.com/codejunkie99/agentic-stack)
at `vendor/agentic-stack`, parallel to `vendor/ecc-tools`.

## Roles

| Path | Role |
| ---- | ---- |
| `vendor/agentic-stack/` | Upstream git submodule — installer, harness adapters, release tags |
| `.agent/` (repo root) | **Live PT brain** — episodic/semantic memory, skills, protocols (customized) |
| `orama-system` `start.sh` | Symlinks `lib/shared/agentic_stack` → `$PT_DIR/vendor/agentic-stack` when PT is present |

PT does **not** treat the submodule as the runtime memory store. The submodule is the
canonical upstream for `install.sh`, `agentic-stack upgrade`, and adapter scaffolding.
Bump the gitlink after reviewing [CHANGELOG.md](https://github.com/codejunkie99/agentic-stack/blob/master/CHANGELOG.md).

## Init (fresh clone)

```bash
git submodule update --init vendor/agentic-stack
bash scripts/git/install-agentic-stack.sh   # idempotent: sync + upgrade --dry-run preview
bash scripts/git/agentic-stack-submodule-sync.sh status
```

## Union-merge doctrine (no vendor edits)

PT `.agent/` is the **live customized brain**. Upstream skeleton changes are previewed
with `agentic-stack upgrade --dry-run`, then harmonized manually into `.agent/` — same
patch-on-top model as orama `openclaw-skills` (submodule + local extensions).

**Never** commit blended output into `vendor/agentic-stack`. See
[orama doc 41](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/41-agentic-stack-gstack-gbrain-memory-blend.md)
for harness matrix, Gbrain/Brain policy, and merge rules.

### Blocked upstream integration

agentic-stack v0.18+ optional **Brain** (`brain_bridge.py`, `agentic-stack brain *`) is
**blocked** until PT ships a dual-backend bridge (`gbrain` canonical via gstack; Brain
optional). On every dry-run, reject Brain wiring.

## Bump upstream

```bash
bash scripts/git/agentic-stack-submodule-sync.sh upgrade
# optional: from PT root, preview skeleton refresh
# (cd vendor/agentic-stack && ./install.sh doctor)
git add vendor/agentic-stack
git commit -m "chore(vendor): bump agentic-stack submodule"
```

## Current pin

Recorded gitlink: see `git ls-tree HEAD vendor/agentic-stack`.
As of formalization (2026-06-26): `48fdc37` on upstream `master` (pre-v0.18.0 tag line in CHANGELOG).

Pin verified current 2026-07-16: `00eda65c` matches upstream `master`
exactly (`ahead_by: 0, behind_by: 0`). Any drift is in the blended `.agent/`
overlay, not the submodule pin.

**2026-08-07 — pinned ahead of upstream, `.gitmodules` url temporarily
points at the `diazMelgarejo` fork, not `codejunkie99/agentic-stack`.**
New pin `17f1bf65` = upstream `master` (`4f50262`) + 3 PT-authored fixes
open as upstream PRs [#60](https://github.com/codejunkie99/agentic-stack/pull/60)
(recall supersession), [#61](https://github.com/codejunkie99/agentic-stack/pull/61)
(UTF-8), [#62](https://github.com/codejunkie99/agentic-stack/pull/62)
(context manager) + a 4th fix (`harness_manager/upgrade.py` loop-skill
copy path bug, found during this blend, not yet opened upstream). All 3
open PRs verified `MERGEABLE` with passing tests before pinning to them.
**Revert path once all 4 land upstream:** point `.gitmodules` back at
`https://github.com/codejunkie99/agentic-stack`, then
`scripts/git/agentic-stack-submodule-sync.sh upgrade` to re-pin to
upstream `master`'s new tip. Full provenance:
`.agent/.agentic-stack-blend-state.json` → `last_blend.note`.

## Patch-overlay catalog

The blended local patches carried on top of the vendored skeleton are
catalogued in [`.agent/.agentic-stack-blend-state.json`](../../.agent/.agentic-stack-blend-state.json)
(`last_blend.applied_clean` + `new_patches_since_prior`, with prior events
under `blend_history`). Consult that catalog — not a fresh `git diff` — to
see which files carry local intent and whether each patch is portable
upstream. Contribution-back planning for these patches lives in
[`.agent/memory/working/2026-07-16-agentic-stack-upstream-contribution-plan.md`](../../.agent/memory/working/2026-07-16-agentic-stack-upstream-contribution-plan.md).
