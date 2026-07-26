# Hermes + OpenClaw staging — progress tracker (2026-07-26)

> **orama `main`:** `6fff3f6c` (idempotent harness sync) + `68aad64f` (bin/agents flesh-out)

## Done

- [x] Full fleet `bin/agents/` SOUL distillates (17 OpenClaw agents + lifecycle Atlas)
- [x] Persona YAML catalog `bin/agents/personas/`
- [x] `install_hermes_profiles.py` with `--sync` idempotent body compare
- [x] `install-hermes-harness.ps1` verify-first profiles + thin wrappers
- [x] `platform/windows/install.ps1` calls harness sync + `-RunDoctor`
- [x] `install.sh` mesh hook (python secrets)
- [x] **`install.ps1`** + `Invoke-MeshLocalCache.ps1` (PT #287 — Windows parity)
- [x] Tests: `tests/test_hermes_profiles.py` (6 passing)

## Mesh security (PT #287 + orama #223/#224)

- [x] `orchestrator/mesh_auth.py` — `PT_BIND_LAN=1` fail-closed gossip auth
- [x] `scripts/mesh/*` ported from orama #223
- [x] Milestones doc: `.agent/memory/working/MESH_SECURITY_MIGRATION_2026-07-26.md`
- [ ] Operator: RTX 5080 `install.ps1` → mesh secrets + gossip smoke test

## Idempotent install doctrine

| Layer | Fresh (5080) | Existing Hermes (3080) |
|-------|----------------|-------------------------|
| Hermes app | Install separately (ECC / Hermes installer) | **Skip** — detected via CLI or `$HERMES_HOME` brain markers |
| orama profiles | `--sync` materializes missing profiles | `--sync` skips when distillate body already matches |
| Thin wrappers | install if verify fails | verify passes → skip; drift → install |
| orama `install.ps1` | Full venv + deps + harness sync | Re-run safe; harness is verify-first |

**Operator commands (Win):**

```powershell
cd $env:ORAMA_SYSTEM_PATH
powershell -File .\platform\windows\install.ps1          # full orama bootstrap + harness sync
powershell -File .\platform\windows\install-hermes-harness.ps1   # profiles/thin only
powershell -File .\platform\windows\install-hermes-harness.ps1 -DryRun
```

## Pending (operator live test)

- [ ] RTX 5080 fresh: `git pull` → `install.ps1` → `hermes doctor`
- [ ] RTX 3080 existing: `git pull` → `install-hermes-harness.ps1` (expect "already synced" if no drift)
- [ ] `hermes profile list` shows REGISTRY slugs
- [ ] `hermes claw migrate` dry-run (optional, if OpenClaw brain import needed)
- [ ] PT `.agent` lesson graduated (see semantic LESSONS via learn.py)

## Deferred

- PT Phase 6 lesson mining batch post-Win validation
- `perpetua-tools/src/hermes_harness.py` (09c) — profile install stable first
