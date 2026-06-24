# Workspace (live task state)

Last updated: 2026-06-24 by cursor-cloud-agent

## Current task
Cross-repo Hermes hardware policy integration — orama #107 + PT #134. Code complete;
memory integrated; live Windows walkthrough deferred.

## Session record (2026-06-24 — Hermes hardware policy)

### orama-system (`cursor/hermes-hardware-policy-wire-c4ae` → PR #107)

| Commit | What |
|--------|------|
| `e898d41` | Wire Hermes to PT hardware policy SSoT; pt-hardware-policy skill; thin installer |
| `7d1da20` | Live Windows walkthrough plan (Phases A–F deferred) |
| `f3cd6e5` | workspace-path-resolution.md; fix platform/windows paths; CodeRabbit fixes |
| `ee4bf80` | Coauthor guard restore; start.sh env discovery; AGY save-first; dynamic installer provenance |

### Perpetua-Tools (`cursor/critical-bug-investigation-a924` → PR #134)

| Area | What |
|------|------|
| Runtime | Hardware policy gaps #128–#131 closed (CLI delegates to canonical API) |
| Skills | hardware-policy SKILL expanded; path resolution cross-ref added |
| Memory | DECISIONS + episodic + graduated lessons (this session) |

### Integration invariant (AFRP)

One policy file → one API → one CLI → launcher gates on each harness:
- Mac/Linux: `start.sh --hardware-policy`
- Windows: `platform/windows/start.ps1 --hardware-policy`
- Hermes: `pt-hardware-policy` thin skill (pointer only)

### Open gates (human action required)

1. **Merge order:** PT #134 + orama #107 together (lockstep YAML/API/harness)
2. **Live Windows walkthrough:** Phases A–F on real Win11 Hermes host (plan doc)
3. **L1 perpetua-core push gate** (unchanged from prior session)

## Next session start

1. `python .agent/tools/recall.py "Hermes hardware policy cross-repo"`
2. Verify `git diff origin/main...origin/cursor/hermes-hardware-policy-wire-c4ae` before merge
3. Run offline validation from plan doc § Offline validation
4. Execute live Windows walkthrough when Win11 host available
