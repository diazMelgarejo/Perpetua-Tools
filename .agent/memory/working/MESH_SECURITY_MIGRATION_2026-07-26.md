# Mesh security migration — milestones and lessons (2026-07-26)

> **PR:** Perpetua-Tools [#287](https://github.com/diazMelgarejo/Perpetua-Tools/pull/287) (`cursor/gossip-lan-mandate-f559`)
> **Sibling orama PRs:** [#223](https://github.com/diazMelgarejo/orama-system/pull/223) (prep), [#224](https://github.com/diazMelgarejo/orama-system/pull/224) (P5/P6 runtime), [#222](https://github.com/diazMelgarejo/orama-system/pull/222) (v2 security ladder — merge **last**)  
> **Session memory:** `.agent/memory/working/PR222_HERMES_STAGING_SESSION_2026-07-27.md` (integrative PR body, CodeRabbit 4792277312, CIDF doctrine)

## Executive summary

Cross-repo mesh hardening adds **integrative** local-secret harmonization (`GOSSIP_SHARED_SECRET`), LAN-bind fail-closed auth on PT FastAPI gossip endpoints, and **Windows parity** via `Invoke-MeshLocalCache.ps1` wired into `install.ps1` (PT) and `platform/windows/install.ps1` + `start.ps1` (orama). Tracked configs shed real LAN IPs in a later phase; local caches and `.env.local` hold topology and secrets.

## Merge order (operator safety)

| Step | Action | Why |
|------|--------|-----|
| 1 | Merge orama **#223** | `dotenv_merge`, `ensure_local_mesh_secrets`, `lan_topology_archive`, install.sh mesh hook |
| 2 | **Operator backup** on every fleet node | `.env.local`, `.local/mesh-secrets.json`, `.local/lan-topology.json` (orama) |
| 3 | Merge orama **#224** + PT **#287** together | Runtime gates + PT gossip auth must land with shared secret contract |
| 4 | Verify mesh on all nodes | `install.sh` / `install.ps1`, gossip emit/tail, LM Studio probes |
| 5 | Merge orama **#222** last | IP expunge + v2 security migration ladder docs |

**Never merge #222 before #223/#224/#287** — operators need local caches and secrets before tracked IP removal.

## Phase ladder (v2 launch — orama #222)

**Execution order:** A → C → B → D (not alphabetical).

| Phase | Name | Scope |
|-------|------|-------|
| **A** | Prep | Local caches, secrets, install hooks (this work) |
| **C** | Runtime gates | `start.sh` / `start.ps1` GOSSIP gate, discovery trust, swarm approval |
| **B** | IP expunge | Remove real LAN IPs from tracked YAML/JSON |
| **D** | Strict cutover | v2 launch — fail closed without secrets/topology |

Phase D is **deferred to v2 launch**; Phases A–C ship first.

---

## Milestones achieved

### orama-system #223 (`cursor/mesh-prep-main-f559`)

- [x] `scripts/mesh/lan_topology_archive.py` — backup/restore LAN topology to `.local/` before IP expunge
- [x] `scripts/mesh/ensure_local_mesh_secrets.py` — harmonize `GOSSIP_SHARED_SECRET` (PT sibling via `PERPETUA_TOOLS_PATH`)
- [x] `scripts/mesh/dotenv_merge.py` — integrative merge: fill missing/empty only; rotate via commented supersede; **never delete** operator values
- [x] `scripts/mesh/mesh_logging.py` — `.local/mesh.log`, UTF-8, Windows-safe paths
- [x] `install.sh` mesh block (topology archive + secrets)
- [x] `.env.local.example` — Ollama vs LM Studio mutual exclusivity documented
- [x] Tests: `test_lan_topology_archive.py`, `test_mesh_secrets.py`, `test_dotenv_merge.py`
- [x] CodeRabbit fixes: 5080 endpoint classification (immediate role-key context), duplicate dotenv key handling (update **last** declaration), fixture tests
- [x] **#288-class fix (ported):** adopt `.env.local` gossip secret without silent rotation — same `read_dotenv_key` + bootstrap JSON pattern as PT #288

### orama-system #224 (`cursor/p5-p6-mesh-hardening-f559`)

- [x] P5/P6 grandfathering for legacy mesh callers
- [x] `start.sh` GOSSIP gate when LAN bind enabled
- [x] `discovery_trust.py`, `swarm_approval.py`
- [x] `scripts/mesh/Invoke-MeshLocalCache.ps1` — Windows companion (`Install` + `LanBind` modes)
- [x] Wired into `platform/windows/install.ps1`, `start.ps1`, `install-hermes-harness.ps1`
- [x] PS 5.1 compatibility: no `??` null-coalescing in mesh PS scripts

### orama-system #222 (`cursor/hermes-staging-security-hardening-f559`)

- [x] `docs/v2/50-mesh-security-migration-ladder.md` — canonical phase A–D ladder
- [x] Cross-links from v2 README and Hermes staging docs
- [x] IP expunge + security hardening (merge **after** prep/runtime PRs)

### Perpetua-Tools #287 + #288 (`cursor/gossip-lan-mandate-f559`)

- [x] `orchestrator/mesh_auth.py` — `require_gossip_auth` when `PT_BIND_LAN=1`
- [x] `orchestrator/fastapi_app.py` — gossip routes use shared auth
- [x] Ported `scripts/mesh/{dotenv_merge,mesh_logging,ensure_local_mesh_secrets}.py` from orama #223
- [x] `install.sh` mesh hook (python secrets)
- [x] **`install.ps1`** — Windows companion mirroring `install.sh` (submodule, MCPB via bash, mesh hook)
- [x] **`scripts/mesh/Invoke-MeshLocalCache.ps1`** — PT variant (secrets only; no `lan_topology_archive`)
- [x] `.env.local.example`, `.gitignore` for `.local/`
- [x] Tests: `test_mesh_auth.py`, `test_mesh_secrets.py` (9 passed after #288)
- [x] **#288 fix:** adopt `.env.local` gossip secret without silent rotation (`read_dotenv_key`, bootstrap JSON, no duplicate append)
- [x] **Merged to `main`** @ `8b38f8a` (2026-07-26)

### orama-system #224 follow-up (CodeRabbit review `4782743245`)

- [x] `install-hermes-harness.ps1` — check `$LASTEXITCODE` after nested `powershell.exe` mesh prep (non-zero exit does not trigger `$ErrorActionPreference = 'Stop'`)
- [x] `discovery_trust.py` — `_block_untrusted_peer` uses `get_mesh_logger` warning (not `print`); blank `win_peers` IPs excluded
- [x] `verify_trusted_install.py` — exact branch ref match in `reanchor_scan.sh` output (no substring false positives)
- [x] Tests: swarm fingerprint/HMAC negatives, discovery handshake TTL expiry, `mesh_gate` blank env/dotenv secrets
- [x] Finality report: `docs/next/fleet-mesh/2026-07-26-pr224-mesh-security-finality-report.md`

---

## Cross-repo contracts

| Env var | Repo | Purpose |
|---------|------|---------|
| `GOSSIP_SHARED_SECRET` | Both | Shared HMAC for gossip + discovery handshake |
| `PT_BIND_LAN=1` | PT | Fail-closed 503 without secret on gossip endpoints |
| `ORAMA_SYSTEM_PATH` | PT | Sibling harmonization target for orama `.env.local` |
| `PERPETUA_TOOLS_PATH` | orama | Sibling harmonization target for PT `.env.local` |

**Header:** `X-Gossip-Secret` must match `GOSSIP_SHARED_SECRET` when secret is set.

**Local files (gitignored):**

- `.env.local` — harmonized secrets
- `.local/mesh-secrets.json` — JSON mirror for tooling
- `.local/mesh.log` — mesh script audit trail
- `.local/lan-topology.json` — orama only (pre-IP-expunge archive)

---

## Lessons learned (both repos)

### Integrative dotenv merge (never delete)

- `harmonize_dotenv_keys` fills **missing or empty** keys only.
- Duplicate keys: update the **last** declaration; comment earlier duplicates.
- Rotation (`--force`): supersede old values as commented lines — **additive, never delete** operator history.
- Applies to both repos' `scripts/mesh/dotenv_merge.py`.
- **#288 lesson:** when secret exists only in `.env.local` (no JSON store), **adopt** it via `read_dotenv_key` before generating — otherwise harmonize appends a second declaration and dotenv last-wins silently rotates fleet auth (403 storm).

### v1 transition vs v2 authority model (deferred strict compliance)

**v1.x (now — lax, standalone installs):** Both repos install independently. When co-installed, they **share secrets** via sibling path env vars (`ORAMA_SYSTEM_PATH` / `PERPETUA_TOOLS_PATH`) and harmonize `.env.local` bidirectionally. This is intentional transition behavior.

**v2 target (strict — new repos):** `perpetua-core` is the **single runtime and state authority**; `oramasys` remains **stateless** and imports shared types from `perpetua-core`, never the reverse. Mesh secrets, topology, and durable state live in a centralized mesh module under `perpetua-core`. Do **not** enforce this boundary strictly in v1.x PRs — document and defer.

### CodeRabbit review #287 — deferred hardening (v1 acceptable, v2 cleanup)

Reference: [PR #287 review](https://github.com/diazMelgarejo/Perpetua-Tools/pull/287#pullrequestreview-4782549522). Accepted for v1 transition; revisit in v2:

| Item | Guidance |
|------|----------|
| Atomic JSON write (`tmp` + replace) | Deferred — v1 tolerates rare partial writes; v2 mesh module uses atomic persist |
| Defensive `_load_json` (corrupt → `{}`) | Deferred — bootstrap should not abort on bad JSON in v1; v2 centralizes validation |
| `GOSSIP_SHARED_SECRET__PREVIOUS_*` retention | v1 only — historical secrets accumulate in JSON/dotenv comments during rotation; v2 repos drop this pattern |
| Windows ACL hardening in `harden_local_file` | Deferred — chmod-only on Unix; v2 adds ACL path |
| LanBind: require non-empty secret after `load-local.ps1` | Deferred — current `.env.local` existence bypass is lax v1; tighten at v2 cutover |
| UTF-8 BOM on PS1 installers | **Done** — `install.ps1` + `Invoke-MeshLocalCache.ps1` saved UTF-8 with BOM for PS 5.1 glyph decoding |

### Windows / Mac / Linux parity

- Every `install.sh` mesh hook needs a **`Invoke-MeshLocalCache.ps1`** companion for Windows operators.
- PT: `install.ps1` at repo root; orama: `platform/windows/install.ps1` + `start.ps1` (`LanBind` mode).
- PowerShell **5.1** target: avoid `??`; use explicit `if` / `.Trim()` guards.
- MCPB build on Windows still delegates to bash (`install-claude-desktop-llm.sh`); `HERMES_GIT_BASH_PATH` or Git for Windows `bash.exe`.
- **Nested `powershell.exe` calls:** `$ErrorActionPreference = 'Stop'` does **not** propagate child exit codes — always check `$LASTEXITCODE` after `& powershell.exe -File ...` before reporting harness sync success (`install-hermes-harness.ps1`).

### LAN bind fail-closed

- PT: `PT_BIND_LAN=1` without `GOSSIP_SHARED_SECRET` → HTTP **503** on gossip emit/tail (not silent localhost bypass).
- orama: `start.sh` / `start.ps1` `LanBind` mode exits if secret and `.env.local` both absent.
- `mesh_gate.gossip_secret_configured`: whitespace-only env or empty/quoted-empty `.env.local` values count as **not configured** (fail closed).

### Discovery trust and swarm approval (P5/P6)

- Untrusted peer notices go through `get_mesh_logger` (`.local/mesh.log`), not stdout `print`.
- Discovery handshake pending entries expire after `HANDSHAKE_TTL_SEC` (600s); expired nonces reject verify.
- Swarm strict mode: `verify_launch` rejects preview drift (fingerprint mismatch) and invalid HMAC tokens independently.
- `win_peers` entries with blank/missing IPs are excluded from persist, not passed through.

### Topology and private literals (v2 carry-forward)

- Tracked repos: policy + loader + synthetic fixtures only.
- Real LAN IPs and private identity literals: **local-only** files (`.env.local`, ignored state).
- See `.agent/memory/working/PRIVATE_LITERALS_AND_LOCAL_TOPOLOGY_V2_LESSON_2026-07-18.md`.

### CodeRabbit / review incidents

- **5080 misclassification:** `lan_topology_archive.py` needed immediate role-key context so RTX 5080 LM Studio endpoint is not classified as generic Windows.
- **Ollama vs LM Studio:** document mutual exclusivity in `.env.local.example` — one inference backend per node class.
- **Fixture tests:** mesh secret tests must use synthetic values, never real fleet secrets.

### Operator commands

```bash
# Unix / Mac
cd $PERPETUA_TOOLS_PATH
bash install.sh
python3 scripts/mesh/ensure_local_mesh_secrets.py
```

```powershell
# Windows
cd $env:PERPETUA_TOOLS_PATH
powershell -ExecutionPolicy Bypass -File .\install.ps1
.\.venv\Scripts\python.exe scripts\mesh\ensure_local_mesh_secrets.py
```

```powershell
# orama Windows (full stack)
cd $env:ORAMA_SYSTEM_PATH
powershell -File .\platform\windows\install.ps1
powershell -File .\platform\windows\start.ps1   # LanBind gate when LAN mesh enabled
```

---

## Related PT memory

| Doc | Topic |
|-----|-------|
| `FLEET_MESH_CROSS_REPO_INDEX_2026-07-14.md` | Fleet mesh navigation |
| `FLEET_MESH_AVALANCHE_TRACE_2026-07-14.md` | Historical phase 5–6 mesh work |
| `HERMES_OPENCLAW_STAGING_2026-07-26.md` | Hermes harness + install.ps1 doctrine |
| `PRIVATE_LITERALS_AND_LOCAL_TOPOLOGY_V2_LESSON_2026-07-18.md` | IP/literal scrub policy |
| `SKILL_SECURITY_WORDING_AGUARA_2026-07-27.md` | Aguara-safe skill wording; naive-agent literal execution |
| `GRACEFUL_DEGRADATION_LAN_2026-06-28.md` | SOLO/PAIR/FLEET degradation |

## Recall

```bash
python .agent/tools/recall.py "mesh security migration gossip lan bind"
python .agent/tools/recall.py "Invoke-MeshLocalCache install.ps1 windows parity"
```

## Open / deferred

- [ ] Operator live test: RTX 5080 `install.ps1` → verify `.local/mesh-secrets.json` + gossip auth
- [ ] PT `start.ps1` LanBind hook (when PT gains LAN start script parity with orama)
- [ ] Phase B IP expunge (orama #222) after fleet backup verified
- [ ] Phase D strict cutover at v2 launch
- [ ] Merge orama **#224** + verify mesh after operator backup (PT #287 already on `main`)
