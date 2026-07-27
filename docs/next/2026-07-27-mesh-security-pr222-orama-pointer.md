# Mesh security PR #222 — Perpetua-Tools operator pointer (2026-07-27)

> **Env contract:** `$ORAMA_SYSTEM_PATH`, `$PERPETUA_TOOLS_PATH`, `$HERMES_HOME`, `${HOME}` only — no workstation literals in tracked docs.

## Orama PR stack

| Artifact | Location |
|----------|----------|
| PR #222 (Hermes staging hardening) | https://github.com/diazMelgarejo/orama-system/pull/222 |
| Migration ladder (Phases A–D) | `$ORAMA_SYSTEM_PATH/docs/v2/50-mesh-security-migration-ladder.md` |
| Pre-merge fleet backup runbook | `$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/references/results/fleet-2026-07-27-pre-pr222-backup-runbook.md` |
| Trusted install gate | `$ORAMA_SYSTEM_PATH/scripts/review/verify_trusted_install.py` |

## PT operator steps (Phase A — all LAN nodes)

Run **before** merging orama #222:

```bash
git -C "$PERPETUA_TOOLS_PATH" pull --ff-only origin main
git -C "$ORAMA_SYSTEM_PATH" fetch origin cursor/hermes-staging-security-hardening-f559

python3 "$ORAMA_SYSTEM_PATH/scripts/mesh/lan_topology_archive.py" --backup --ref origin/main
python3 "$ORAMA_SYSTEM_PATH/scripts/mesh/ensure_local_mesh_secrets.py"
```

1. Unify **one shared** `GOSSIP_SHARED_SECRET` across Mac + both Win nodes (OOB copy).
2. Verify mesh: discover, gossip tail, LMS probes — **green on every node** before merge.
3. Win: `hermes backup` → optional `install-hermes-harness.ps1 -RunDoctor`.

## Gossip / coordination notes

- GossipBus remains **intra-machine** until Phase C runtime gates (orama ladder).
- Coordination Phase 0F is **PT-owned** — see [`../coordination/README.md`](../coordination/README.md).
- STM/swarm Phase 0 is separate — see [`../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md`](../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md).

## Trusted install env (orama)

| Variable | Purpose |
|----------|---------|
| `ORAMA_SKIP_HERMES_SYNC=1` | Skip all Hermes materialization |
| `ORAMA_TRUST_HERMES_SYNC=1` | Explicit operator override on feature branches |
| `ORAMA_VERIFY_COMMIT_SIG=1` | Require GPG-verified HEAD |
| `ORAMA_ALLOWED_GPG_FINGERPRINTS` | Comma-separated maintainer key fingerprints (required when sig gate enabled) |
