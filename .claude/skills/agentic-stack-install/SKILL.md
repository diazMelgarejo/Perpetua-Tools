---
name: agentic-stack-install
description: Bump the vendor/agentic-stack submodule pin and replay PT's .agent/ customizations across the upgrade via a 3-way merge. Run when upgrading vendor/agentic-stack, when .agent/ tools/skills feel stale relative to upstream, or when resolving a merge conflict staged under .agent/.blend-preview/.
user-invocable: true
---

# agentic-stack Install & Blend

**Load this skill when:** bumping `vendor/agentic-stack`, running
`agentic-stack-agent-blend.sh`, or resolving anything under
`.agent/.blend-preview/`.

Documents own content — this card navigates, it doesn't restate. If you're
about to explain *why* a specific conflict resolves one way, stop and read
the linked doc instead of re-deriving it here.

## When to Use

- Bumping the `vendor/agentic-stack` submodule pin to a newer upstream release.
- `.agent/tools/*` or `.agent/memory/*` look stale relative to what
  `harness_manager.cli upgrade --dry-run` reports upstream has changed.
- You hit a `<<<<<<<` conflict marker under `.agent/.blend-preview/` and don't
  know which side to keep.
- Auditing what agentic-stack version `.agent/` was last blended from.

## Architecture (read in this order)

| Layer | File | Role |
|-------|------|------|
| **Submodule pin** | `scripts/git/agentic-stack-submodule-sync.sh` | `status \| update \| upgrade` — bumps `vendor/agentic-stack` itself |
| **Dry-run preview** | `scripts/git/install-agentic-stack.sh` | Idempotent submodule sync + `upgrade --dry-run` preview (falls back to `doctor` on old pins) |
| **Blend engine** | `scripts/git/agentic-stack-agent-blend.sh` | `status \| plan \| apply \| promote` — 3-way merges `.agent/` files against the new pin |
| **Blend state (SSoT)** | `.agent/.agentic-stack-blend-state.json` | Base SHA `.agent/` was last blended from + audit trail of the last run |
| **Blend scratch space** | `.agent/.blend-preview/` (gitignored) | Where `apply` stages merges/new files; never written directly into `.agent/` |
| **Precedent + full playbook** | [`docs/wiki/11-agentic-stack-agent-blend.md`](../../../docs/wiki/11-agentic-stack-agent-blend.md) | AlphaClaw reverse-merge mapping, conflict-resolution playbook table — **read this before resolving any conflict by hand** |
| **Brain-integration policy** | orama-system `docs/v2/41-agentic-stack-gstack-gbrain-memory-blend.md` §5 | Canonical blocklist rules this tool enforces |

## Workflow

```bash
bash scripts/git/agentic-stack-submodule-sync.sh upgrade   # bump the pin
bash scripts/git/install-agentic-stack.sh                  # dry-run preview
bash scripts/git/agentic-stack-agent-blend.sh status         # categorize the delta
bash scripts/git/agentic-stack-agent-blend.sh apply           # stage merges + new files
# resolve any <<<<<<< conflicts in .agent/.blend-preview/ -- check the
# playbook table in wiki/11 first; most conflicts match a known pattern
bash scripts/git/agentic-stack-agent-blend.sh promote          # copy clean files into .agent/
```

`promote` only advances the blend-state base once nothing is left conflicted.
If it reports files skipped, resolve them and re-run `apply` + `promote` —
do not hand-edit `.agent/.agentic-stack-blend-state.json` directly.

## Boundaries

### Always Do
- Read `docs/wiki/11-agentic-stack-agent-blend.md`'s playbook table before
  resolving a conflict from scratch.
- Run `status` before `apply` — know what's flagged before touching anything.

### Never Do
- Write into `.agent/tools/brain_bridge.py` or `.agent/skills/brain/`, or add
  a reference to either from a merged file (e.g. a skill index entry) — see
  doc 41 §5. This is enforced by the tool for new files; content-level
  references inside merged existing files still need a manual check.
- Hand-edit `.agent/.agentic-stack-blend-state.json`'s `base_sha` — it should
  only ever be written by `promote`.
- Commit unresolved `<<<<<<<` markers.
