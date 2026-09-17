# OSSF-1 Skill Format Standardization Saga

**Decision window:** 2026-08-07 through 2026-08-08  
**Status:** orama enforcement landed on branch
`2026-08-07-001-harden-skills-vendor-blend-lessons`; PT portable brain deferred
until v2 `oramasys/*`  
**Canonical enforcement repo:** orama-system (not Perpetua-Tools until org migration)

---

## 1. Why this arc exists

By 2026-08-07 the stack had **355** primary-scope `SKILL.md` files across
orama-system and Perpetua-Tools, but at least **six incompatible “good”
shapes** (Claude-minimal wrappers, orama skillify full/partial, OpenClaw
overlays, PT portable brain, Cursor metadata, and broken frontmatter).
Agents could not rely on a single validator or a single authoring card.

The response was not “pick Anthropic OR orama” — it was a **fusion
standard** with a enforceable subset for canonical orama skills first.

---

## 2. Timeline (retroactive record)

| When (UTC+8) | Event | Artifact / SHA |
|--------------|-------|----------------|
| **2026-08-07** | Full inventory + fusion spec drafted (USF-1 naming in fusion doc; implementation name **OSSF-1**) | OpenClaw hub `v1/2026-08-07-skill-format-fusion.md`, `v1/_skill-format-scan.json`, `v1/2026-08-07-skill-format-full-report.md` |
| **2026-08-07** | Priority queue locked to fusion §2.2 cluster labels (P1/P2/P4/P7 pilots) | `v1/2026-08-07-ossf1-skill-priority-queue.md` |
| **2026-08-07** | Operator notes captured | local operator notes (not in any repo) |
| **2026-08-08** | **Commit #1 — pre-commit gate** (orama only): `scripts/hooks/check_ossf1_skill_md.py` + `.githooks/pre-commit` wiring | orama `9fb770fd` (local); remote rebased as `7c276765` |
| **2026-08-08** | **Commit #2 — pilot wave** P1+P4 orama paths + `pt-orama-security-planner` wrapper; hermes body extracted to `references/ossf-operating-procedures.md` | orama `e5e2cc51` (local); remote rebased as `095469be` |
| **2026-08-08** | UTF-8 BOM on `afrp/SKILL.md` blocked frontmatter regex — stripped with `utf-8-sig` read | pilot commit hygiene fix |
| **2026-08-08** | AlphaClaw ECC PR #30 head: OSSF-1 orchestrator + `references/` split | AlphaClaw `faf894f2` (local worktree; **not** on current `origin/ecc-tools/AlphaClaw-1785989223295` tip at last check) |
| **2026-08-08** | PR #283 merge/reanchor silently dropped OSSF-1 tree content (~660 lines) — caught by diff vs `headRefOid`, not cherry message match | orama `docs/LESSONS.md` §2026-08-08; PT `lesson_adda4d2b02c3` |
| **2026-08-08+** | Remote branch received follow-up hook hardening (staged-index validation, portable subprocesses, tests) | orama `25c02500`, `57c8f0b1`, `e3bf301e` on `origin/2026-08-07-001-harden-skills-vendor-blend-lessons` |

---

## 3. What OSSF-1 is (enforced shape)

**OSSF-1** = *Oramasys Standard Skill Format v1* — the machine-checkable
subset of the fusion spec for **canonical** skills under
`bin/orama-system/**/SKILL.md`.

### Required frontmatter

- `name`, `description` (≥20 chars), `version`
- `triggers` **or** activation phrases embedded in `description` (`Activates when` / `Activates for`)
- `compatibility` **or** `agent_compatibility` (overlay cards)
- `allowed-tools`

### Required body sections

- `## Purpose` **or** `## When to Use`
- `## Boundaries` with `### Always Do`, `### Ask First`, `### Never Do`
- **≤500 lines** total file (hard ceiling in hook)

### Explicitly out of hook scope (2026-08-08 decision)

- `.agents/skills/*`, `.claude/skills/*` install mirrors
- Perpetua-Tools `.agent/skills/*` portable brain
- Entire PT repo until v2 `oramasys/*` org split

Pilot wrappers (e.g. `pt-orama-security-planner`) were upgraded manually
but are **not** gated by the hook until scope expands.

---

## 4. Where the standard is published (two-repo map)

| Layer | Location | OSSF-1 named? | Role |
|-------|----------|---------------|------|
| **Fusion / inventory (hub)** | OpenClaw `v1/2026-08-07-skill-format-fusion.md` | USF-1 in §3 title; OSSF-1 in operator notes | Authoritative *why* and cluster math |
| **Priority queue (hub)** | OpenClaw `v1/2026-08-07-ossf1-skill-priority-queue.md` | Yes | Pilot ordering tied to fusion §2.2 |
| **Precursor architecture** | orama `bin/orama-system/references/skill-architecture-guide.md` | No (predates OSSF-1 label) | Discovery FM, 6Cs, boundaries pattern |
| **v2 size policy** | orama `docs/v2/44-docs-v2-skills.md` | No | ≤200 preferred / ≤500 hard — aligns with OSSF ceiling |
| **Machine enforcement** | orama `scripts/hooks/check_ossf1_skill_md.py` | Yes | Pre-commit on staged canonical paths only |
| **Incident doctrine** | orama `docs/LESSONS.md` §2026-08-08 | Yes | PR #283 content-loss case study |
| **PT portable brain** | `.agent/skills/*` | No OSSF-1 gate yet | Triggers/tools/constraints native format |

**Gap (intentional as of 2026-08-08):** no single orama
`docs/v2/NN-ossf-1.md` ADR — OSSF-1 lives in hook docstring + hub fusion
docs + lessons. Promote to `docs/v2/` when the pilot wave merges to
`main`.

---

## 5. Pilot wave scope (orama paths only)

### P1 — no frontmatter / nonstandard

- `bin/orama-system/afrp/SKILL.md`
- `bin/orama-system/skills/openclaw-skills/SKILL.md`
- `bin/orama-system/skills/self-discovery/SKILL.md`
- `.agents/skills/pt-orama-security-planner/SKILL.md` (wrapper; manual pilot)

### P4 — orama skillify partial (canon subset)

- `bin/orama-system/skills/codex-mcp-debugging/SKILL.md`
- `bin/orama-system/skills/hardware-affinity-gate/SKILL.md`
- `bin/orama-system/skills/hermes-harness/SKILL.md` + `references/ossf-operating-procedures.md`
- `bin/orama-system/skills/mcp-orchestration/SKILL.md`

**Deferred:** P2 (PT wrappers), P7 (cursor-style), P11/P14 bulk upgrades.

---

## 6. Progressive disclosure pattern (hermes pilot)

When a canonical skill exceeds the 500-line ceiling:

1. Keep orchestration, Purpose/When/Boundaries, and load-order pointers in `SKILL.md`.
2. Move long operating procedures to `references/<topic>.md`.
3. Re-run hook on staged `SKILL.md` only (reference files are not gated).

`mcp-orchestration` stayed at 496 lines by compressing tail sections into
reference pointers before adding Boundaries.

---

## 7. Two-repo grounding rules (do not violate)

| Concern | Owner | PT role |
|---------|-------|---------|
| Skill architecture, envelopes, Hermes/OpenClaw fabric | orama-system | Thin wrappers in `.agents/skills/` |
| Portable brain, runtime memory, lessons pipeline | Perpetua-Tools `.agent/` | This saga + `lesson_*` entries |
| ADRs / decisions D1–D17+ | orama `docs/v2/` | Generated pointers only in `docs/adr/` |

PT must **not** copy OSSF-1 hook into CI until the v2 org migration plan
says otherwise — but PT **must** remember the saga so agents do not
re-litigate format clusters.

---

## 8. Related PT memory already on disk

| File | Coverage |
|------|----------|
| `.agent/memory/working/ALPHACLAW_OSSF1_AUDIT_2026-08-08.md` | AlphaClaw progressive-disclosure audit |
| `.agent/memory/working/SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md` | Cross-repo trust + OSSF mention |
| `.agent/memory/semantic/lessons.jsonl` `lesson_adda4d2b02c3` | Never trust cherry message match after reanchor — OSSF content loss |

---

## 9. Open items (as of saga authorship)

- [ ] Merge `2026-08-07-001-harden-skills-vendor-blend-lessons` to orama `main`
- [ ] Promote OSSF-1 from hook docstring → `docs/v2/` decision record
- [ ] Re-push / reanchor AlphaClaw `faf894f2` onto current PR #30 head if still desired
- [ ] PT P2 `hardware-policy` / `orama-repo-rules` wrappers (out of orama hook scope)
- [ ] Expand hook to `.agents/` mirrors after v2 `oramasys/*` cutover

---

## 10. Evidence anchors (for lesson `evidence_ids`)

Use these ISO timestamps when retro-linking episodic records:

- `2026-08-07T00:00:00+08:00` — fusion inventory + USF-1/OSSF-1 spec authored
- `2026-08-08T01:00:00+08:00` — orama commit #1 hook (`9fb770fd` / `7c276765`)
- `2026-08-08T02:00:00+08:00` — orama commit #2 pilot (`e5e2cc51` / `095469be`)
- `2026-08-08T05:05:24+00:00` — PR #283 OSSF content-loss lesson (`lesson_adda4d2b02c3`)
