# Local runtime overlay — `config/devices.yml` and `config/models.yml`

> **Category:** local topology runtime cache (companion to orama D47 / PT portable-memory rules).
> **Enforcement:** `scripts/git/check_local_runtime_overlay.py` (pre-commit + CI).

## Two layers

| Layer | What it is | Git rule |
|-------|------------|----------|
| **Committed schema** (`HEAD`) | Device/model structure, empty `lan_ip`, loopback or env-var host defaults | Must stay free of operator LAN addresses |
| **Working-tree overlay** | Last discovery / dispatch probe wrote real DHCP IPs into the same files | **Keep locally** — never discard with `git checkout` |

Discovery and dispatch may refresh `lan_ip` and model `host` defaults from live probes
(`orchestrator/lan_discovery.py`, `discover.py`, model registry). That drift is
**expected operator state**, not accidental dirty files.

Canonical live topology also flows through ignored runtime files
(`.env.local`, `~/.openclaw/state/last_discovery.json`). The YAML overlay is a
**repo-local convenience cache** so PT can boot without re-probing every process.

## Agent and operator rules

1. **Never commit** RFC1918 / operator LAN values in these two files. Pre-commit blocks staged content.
2. **Never `git checkout` / `git restore`** these paths to “clean up” before pull, rebase, or integrity checks. Stash them if a merge would overwrite them: `git stash push -m "runtime overlay" -- config/devices.yml config/models.yml`.
3. **After pull / merge**, let discovery refresh them, or restore stash with hooks safeguard: `git -c core.hooksPath=/dev/null stash pop` then `bash scripts/git/install-local-hooks.sh` (see orama [`stash-hooks-safeguard`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-history-surgery/references/stash-hooks-safeguard-reference-card.md) card).
4. **`git status` showing `M config/devices.yml`** is normal on an active machine — not a hygiene failure.

## Integrity checks (fresh clone vs local)

When comparing a fresh `origin/main` checkout to a local worktree:

- **`M config/devices.yml` / `M config/models.yml` with LAN values** = expected overlay, not merge corruption.
- Compare **committed** trees (`git archive origin/main`) or run `check_local_runtime_overlay.py --mode tree` on the fresh clone only.
- Do **not** treat local overlay drift as something to `git checkout` away.

## Enforcement modes

| Mode | Command | When |
|------|---------|------|
| `staged` (default) | `check_local_runtime_overlay.py` | pre-commit — blocks `git add` of LAN IPs |
| `tree` | `check_local_runtime_overlay.py --mode tree` | CI — validates committed branch content |


To make `git add -A` less footgun-prone on this machine:

```bash
git update-index --skip-worktree config/devices.yml config/models.yml
```

Undo with `--no-skip-worktree`. This is **local only** (not committed).

## See also

- `../CLAUDE.md` §6 — Git hygiene
- orama skill cards (canonical git doctrine):
  - [`local-runtime-overlay-reference-card.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/using-git-worktrees/references/local-runtime-overlay-reference-card.md)
  - [`fresh-main-integrity-diff-claygo.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/using-git-worktrees/references/fresh-main-integrity-diff-claygo.md)
  - [`stash-hooks-safeguard-reference-card.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-history-surgery/references/stash-hooks-safeguard-reference-card.md)
- `../orama-system/docs/wiki/08-git-hygiene-and-branching.md` — stash-first + overlay + CLAYGO (orama wiki)
- `../orama-system/docs/v2/17-hardware-policy-enforcement.md` — hardware topology layer
- `../orama-system/docs/v2/47-portable-memory-local-topology-invariant.md` — tracked policy vs local fragments
