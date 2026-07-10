# Cross-Repo Documentation & Plans Index

**Purpose:** Canonical mapping of all plans, task lists, specifications, and ADRs across Perpetua-Tools (L2) and orama-system (L3). Prevents confusion and duplicate work.

**Last updated:** 2026-07-10  
**Maintain by:** updating both repos when adding new plans/specs

**Note on paths:** All canonical locations use relative paths from repo root. Use `git rev-parse --show-toplevel` to resolve to actual disk location.

---

## Perpetua-Tools (L2 — Runtime & State Authority)

| Document | Purpose | Location | Canonical? | Notes |
|---|---|---|---|---|
| PHASE-0-TASK-LIST.md | Phase 0 implementation tasks (TDD-first breakdown) | `docs/phase-0-specifications/` | ✅ YES | Synced from gstack cache 2026-07-10 |
| DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md | PeerObservation schema with multiplicative confidence fix | `docs/phase-0-specifications/` | ✅ YES | Critical blocker fixes; D1 iteration 2 |
| DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md | Heartbeat protocol + StateTransitionManager spec | `docs/phase-0-specifications/` | ✅ YES | 40–90s real-world SLA reframed; N=2 asymmetry fix |
| DELIVERABLE-4-THREAT-MODEL-REGENERATED.md | Threat model T1–T7 with Phase 0 mitigations | `docs/phase-0-specifications/` | ✅ YES | T7 (out-of-order defense) added 2026-07-10; field order fixed |
| PHASE-0-TEAM-REVIEW-CHECKLIST.md | Checkpoint 1.0–1.3 team async review gates | `docs/phase-0-specifications/` | ✅ YES | 6 design questions per checkpoint |
| 2026-05-31-tri-repo-alignment-completion-plan.md | Gate-2 alignment tracker (AlphaClaw→PT→orama) | `docs/` | ✅ YES | 8 gaps; lib/mcp retirement deferred |
| 2026-05-31-gate2-implementation-plan.md | Gate 2 task breakdown | `docs/plans/` | ✅ YES | Task-by-task scoping |
| RC_CHECKLIST.md | Release-candidate checklist | `docs/` | ✅ YES | Pre-ship validation |
| autoresearch-orchestrator-adoption.md | AutoResearcher integration plan | `docs/plans/` | ✅ YES | Fable 5 integration |
| 2026-05-31-track-bc-claude-desktop-mcpb.md | Claude Desktop MCP bridge tracking | `docs/plans/` | ✅ YES | V1 deferred |
| LESSONS.md | Session-by-session learning log | `docs/` | ✅ YES | Updated 2026-07-10 with 6 new lessons |

### Phase 0 Specifications Hierarchy

```
PT/docs/phase-0-specifications/
├── DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md  [CANONICAL]
├── DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md  [CANONICAL]
├── DELIVERABLE-4-THREAT-MODEL-REGENERATED.md  [CANONICAL]
├── PHASE-0-TASK-LIST.md  [CANONICAL]
└── PHASE-0-TEAM-REVIEW-CHECKLIST.md  [CANONICAL]
```

---

## orama-system (L3 — Stateless Planning & Methodology)

| Document | Purpose | Location | Canonical? | Notes |
|---|---|---|---|---|
| docs/v2/ | ADRs 0–17+ | `docs/v2/` | ✅ YES | Architectural decisions registry |
| 2026-05-14--UNIFIED-ABSORPTION-PLAN.md | Three-tier architecture | `docs/` | ✅ YES | Master plan; all projects inherit this |
| LESSONS.md | Cross-repo learning log | `docs/` | ✅ YES | Companion to PT LESSONS.md |

---

## Problematic Locations (DO NOT USE)

| Location | Issue | Correct Location |
|---|---|---|
| `~/.gstack/projects/diazMelgarejo-orama-system/` | gstack cache; stale copies of Phase 0 specs (2–6 hours behind disk) | PT `docs/phase-0-specifications/` (current working tree) |
| Legacy iCloud symlink trees | Outdated copies from prior iCloud epoch | Use current working tree only; verify with `git status` |

**Golden rule:** Before editing specs, verify location with `git rev-parse --show-toplevel && git status`. Never edit from cache or backup trees.

---

## PROPOSED: oramasys/alexandria — Centralized Documentation Repository

**Status:** Awaiting decision (ADR to be written to orama-system/docs/v2/41-alexandria-repository.md)

**Problem:** Phase 0 specifications, threat models, and design decisions are scattered:
- PT owns runtime code; specs live in `docs/phase-0-specifications/` (correct, runtime-adjacent)
- orama-system owns architecture ADRs; design should live in `docs/v2/` (not yet migrated)
- Interim: gstack cache has stale copies, causing navigation confusion

**Solution:** Create `oramasys/alexandria` as documentation-only, zero-code repository:

| Repo | Purpose | Contents | Excludes |
|---|---|---|---|
| `Perpetua-Tools` | L2 Runtime & State | Implementation, orchestrator/, config/, packages/ | Architecture specs, decision history |
| `alexandria` | Documentation hub | Specifications (D1–D4), threat models, ADRs, team reviews, lessons | NO source code, NO build artifacts |
| `orama-system` | L3 Stateless planning | Methodology, skills, gate criteria | Duplicate specs (defer to alexandria) |

### Benefits

1. **Single source of truth** for all specs + decisions (not scattered across PT + gstack cache)
2. **No code = no build/test burden** on alexandria (pure docs, always readable)
3. **Stable URL anchors** for cross-project references
4. **Clear delineation:** specs are architecture (orama domain), implementation is runtime (PT domain)
5. **Prevents confusion:** next time, navigation order is alexandria → PT → orama, not gstack cache first

### Proposed Directory Structure

```
alexandria/
├── docs/
│   ├── adr/                     # ADRs D0–D17+ (migrated from orama-system/docs/v2/)
│   ├── phase-0/                 # Phase 0 deliverables (D1, D2, D4)
│   ├── specifications/          # General specs and architectural designs
│   ├── threat-models/           # T1–T7 and beyond
│   ├── team-reviews/            # Checkpoint checklists, gate criteria
│   └── lessons/                 # Cross-repo learning logs
├── README.md                    # Navigation guide
└── .gitignore                   # No binaries, no build artifacts
```

---

## Session Mistakes Mapping (2026-07-10)

**Error:** Edited D1/D2/D4 specs from gstack cache instead of canonical PT location

**Root cause:** No canonical mapping existed; gstack cache looked like "the specs repo"

**Fix:** This document + alexandria repo decision

**Prevention:** Before editing specs, verify via this cross-reference that you're in the canonical location

---

## Cross-Repo Dependencies

| PT document | Links to | orama document | Status |
|---|---|---|---|
| PHASE-0-TASK-LIST.md | architectural decisions | orama-system docs/v2/ (future alexandria) | Sync needed: task dependencies map to ADRs |
| 2026-05-31-tri-repo-alignment-completion-plan.md | gate criteria | orama-system docs/v2/19-worktree-parallel-agents.md | Sync current |
| LESSONS.md | cross-repo learnings | orama-system LESSONS.md | Sync current (2026-07-10 entries added to both) |

---

## Maintenance Checklist

- [ ] Before publishing a new spec/plan, confirm it's in PT (`docs/`) or alexandria (future), NOT gstack
- [ ] Before editing an existing spec, verify via this cross-reference that you're in the canonical location
- [ ] After alexandria is created, migrate Phase 0 specs + ADRs into it; update this index
- [ ] Sync PT LESSONS.md and orama-system LESSONS.md bi-directionally when either is updated
- [ ] When creating new plans, route by type:
  - **Implementation tasks** → PT `docs/plans/` or `docs/phase-0-specifications/`
  - **Architectural decisions** → alexandria (future) or orama-system `docs/v2/`
  - **Session learnings** → Both PT and orama-system `LESSONS.md`

