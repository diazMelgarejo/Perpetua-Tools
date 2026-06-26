# vendor/agentic-stack — upstream reference submodule

Perpetua-Tools vendors [agentic-stack](https://github.com/codejunkie99/agentic-stack)
at `vendor/agentic-stack`, parallel to `vendor/ecc-tools`.

## Roles

| Path | Role |
|------|------|
| `vendor/agentic-stack/` | Upstream git submodule — installer, harness adapters, release tags |
| `.agent/` (repo root) | **Live PT brain** — episodic/semantic memory, skills, protocols (customized) |
| `orama-system` `start.sh` | Symlinks `lib/shared/agentic_stack` → `$PT_DIR/vendor/agentic-stack` when PT is present |

PT does **not** treat the submodule as the runtime memory store. The submodule is the
canonical upstream for `install.sh`, `agentic-stack upgrade`, and adapter scaffolding.
Bump the gitlink after reviewing [CHANGELOG.md](https://github.com/codejunkie99/agentic-stack/blob/master/CHANGELOG.md).

## Init (fresh clone)

```bash
git submodule update --init vendor/agentic-stack
bash scripts/git/agentic-stack-submodule-sync.sh status
```

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
