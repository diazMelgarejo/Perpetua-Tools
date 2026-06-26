# Workspace (live task state)

Last updated: 2026-06-26 by cursor-agent (PR #135 merge + AlphaClaw CI memory)

## Current task
None active. PR #135 merged locally to `main`; AlphaClaw CI memory integrated.

## Completed 2026-06-26 — AlphaClaw CI fix memory + PR #135 merge

| Item | Outcome | Ref |
|------|---------|-----|
| AlphaClaw CI diagnosis + fix | ✅ `ca5e3f28` on `feature/MacOS-post-install`; CI [28206351466](https://github.com/diazMelgarejo/AlphaClaw/actions/runs/28206351466) green | AlphaClaw |
| PT `.agent` episodic + 3 lessons | ✅ appended on `main` | `lesson_6bff2fffe56e`, `lesson_53c4e49a41d8`, `lesson_75dae01bcd29` |
| PR #135 Hermes memory + coauthor guard | ✅ merged to `main` @ `c97d89f` (CodeRabbit root-cause fixes) | `cursor/critical-bug-investigation-a924` |
| PR #135 dream-memory follow-up | ✅ `lesson_6fc89e22e3bb` (REVIEW_QUEUE sanitize at render) | `chore/agent-dream-memory-2026-06-26` |
| Migration verdict | ✅ L1 fixes stay in AlphaClaw — no PT code migration | `docs/MIGRATION.md` |

**Main synced:** `origin/main` @ `c97d89f`. Memory commits land on `chore/agent-dream-memory-*` branches, merged locally.

## Session record (2026-06-24 — Hermes hardware policy)

### orama-system (`cursor/hermes-hardware-policy-wire-c4ae` → PR #107)

| Commit | What |
|--------|------|
| `e898d41` | Wire Hermes to PT hardware policy SSoT; pt-hardware-policy skill; thin installer |
| `7d1da20` | Live Windows walkthrough plan (Phases A–F deferred) |
| `f3cd6e5` | workspace-path-resolution.md; fix platform/windows paths; CodeRabbit fixes |
| `ee4bf80` | Coauthor guard restore; start.sh env discovery; AGY save-first; dynamic installer provenance |

### Perpetua-Tools (`cursor/critical-bug-investigation-a924` → PR #135)

| Area | What |
|------|------|
| Runtime | Hardware policy gaps #128–#131 closed (CLI delegates to canonical API) |
| Skills | hardware-policy SKILL expanded; path resolution cross-ref added |
| Memory | DECISIONS + episodic + graduated lessons (this session) |
| Security | `check_commit_message.sh` coauthor email fail-closed + regression test |

### Integration invariant (AFRP)

One policy file → one API → one CLI → launcher gates on each harness:
- Mac/Linux: `start.sh --hardware-policy`
- Windows: `platform/windows/start.ps1 --hardware-policy`
- Hermes: `pt-hardware-policy` thin skill (pointer only)

### Open gates (human action required)

- orama-system main: `36b876e` — 41/41 tests green, hygiene OK, 3 plan files live
- Perpetua-Tools main: PR #135 merged locally — dream-cycle + Hermes memory integrated
- perpetua-core: local-only `feat/salvage-plugins-rc1`, push gate open
- Post-merge sweep: GitHub Action live (`.github/workflows/post-merge-review-sweep.yml`)
- **Merge order:** PT #135 + orama #107 together (lockstep YAML/API/harness)
- **Live Windows walkthrough:** Phases A–F on real Win11 Hermes host (plan doc)
- **L1 perpetua-core push gate** (unchanged from prior session)

## Next session start

1. `python .agent/tools/recall.py "Hermes hardware policy cross-repo"`
2. Verify `git diff origin/main...origin/cursor/hermes-hardware-policy-wire-c4ae` before merge
3. Run offline validation from plan doc § Offline validation
4. Execute live Windows walkthrough when Win11 host available
