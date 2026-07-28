# Fleet Mesh Cross-Repo Index

Date: 2026-07-14

Orama-system now has explicit fleet-mesh planning indexes:

- Active / unfinished plans: `orama-system/docs/next/fleet-mesh/README.md`
- Active Phase 7–10+ roadmap: `orama-system/docs/next/fleet-mesh/phase-7-to-10-roadmap.md`
- Completed / historical records: `orama-system/docs/archive/fleet-mesh/README.md`

## Cross-repo role

Perpetua-Tools remains the Layer 2 implementation/companion side for:

- FleetMode classifier and topology state management when present on current PT main.
- Heartbeat/liveness/security primitives that feed Orama fleet-mesh recovery.
- Phase 0/1/2 swarm security docs and witness/equivocation patterns that feed Orama Phase 10+.

## Navigation rule

When resuming SOLO / PAIR / FLEET, Phase 7/G7, Phase 8, Phase 9, or Phase 10+ work:

1. Start from `orama-system/docs/next/fleet-mesh/README.md`.
2. Check `orama-system/docs/next/fleet-mesh/phase-7-to-10-roadmap.md` for the active continuation.
3. Treat `PHASE-6-IMPLEMENTATION.md` as completed evidence, not the root plan.
4. Use `docs/archive/fleet-mesh/README.md` only for historical provenance.

## OpenClaw live fleet (MERGE-10, 2026-07-26)

Operator-local retrofit (not yet promoted to orama git):

- **PT playbook:** `.agent/references/openclaw-oramasys-fleet-retrofit-playbook.md`
- **Session:** `.agent/memory/working/OPENCLAW_MERGE10_FLEET_RETROFIT_2026-07-26.md`
- **Mesh security (PR #287):** `.agent/memory/working/MESH_SECURITY_MIGRATION_2026-07-26.md`
- **Live hub:** `${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace/docs/oramasys/CROSSREF.md` (17 agents)
- **Recall:** `python .agent/tools/recall.py "openclaw fleet merge-10"`

## Git-mv note

The Orama connector pass added canonical indexes without moving legacy source files because the available connector path could not perform a true local `git mv` over the current tree. A future local checkout should physically move the indexed documents with `git mv` if the project wants path relocation in addition to canonical indexing.

## Integration branch policy (2026-07-28)

Agent PRs in sibling repos **must not target `main`** when an integration line exists:

- **AlphaClaw** → base `feature/MacOS-post-install` ([tree](https://github.com/diazMelgarejo/AlphaClaw/tree/feature/MacOS-post-install))
- **periscope** → base `merged` ([tree](https://github.com/diazMelgarejo/periscope/tree/merged))

Working memory: `.agent/memory/working/WORKSPACE_PR_BASE_BRANCHES_2026-07-28.md`
