# Hardware Policy Manager — Skill

Manage hardware-bound model affinity for the OpenClaw / orama / Perpetua-Tools stack.

**Load this skill when:** touching model IDs, `openclaw.json`, `launch_researchers.py`,
`hardware_policy_cli.py`, `utils/hardware_policy.py`, or `model_hardware_policy.yml`.

## When to Use

- Assigning models to hardware platforms (mac / win)
- Validating `openclaw.json` or LM Studio configurations
- Adding new models to any provider
- Reviewing PRs that change model resolution or routing
- Running discovery (`discover.py --force`)
- After changing `src/utils/hardware_policy.py` — **grep for duplicate parsers** (see § Anti-fragmentation)

## Key Concepts

- **NEVER_MAC**: `windows_only` models — MUST NOT run on Mac (RTX 3080 GGUF). Risk: OOM, missing CUDA kernel, **double-barrel GPU** when Mac LM Studio mirror proxies the model and Win dispatches concurrently.
- **NEVER_WIN**: `mac_only` models — MUST NOT run on Windows (MLX / Apple Silicon).
- **shared**: models verified on both platforms; routing chooses per task.
- **LM Studio proxy gotcha**: Mac `/v1/models` lists **Win models too** (LAN proxy). You cannot infer physical hardware from which endpoint lists a model. Enforcement uses **provider name** (`lmstudio-mac` vs `lmstudio-win`), not model-list membership.
- **Alias sections**: LM Studio uses quant-suffixed ids (e.g. `gemma-4-26B-A4B-it-Q4_K_M`). These live in `windows_only_aliases` / `mac_only_aliases` and are merged at load time — never enforce only the base id.

## Platform Harness Model (OpenClaw vs Hermes)

| Host | Harness | Policy gate | Notes |
|------|---------|-------------|-------|
| macOS | OpenClaw (`orama-system/start.sh`) | `./start.sh --hardware-policy` | Mac orchestrator; NEVER_MAC for Win GGUF |
| Linux | OpenClaw (`start.sh`) | same | Same software as macOS; all PT hardware profiles documented in `hardware/SKILL.md` |
| Windows 11 | Hermes + `start.ps1` | `.\platform\windows\start.ps1 --hardware-policy` | Local orchestrator counterpart; `lmstudio-win` → localhost:1234 |

**Do not infer affinity at runtime.** All harnesses consume `config/model_hardware_policy.yml`
via `src/utils/hardware_policy.py`. Hermes: `orama-system` → `hermes-harness` → `pt-hardware-policy`.

**Path resolution (workspace-agnostic):** Set `PERPETUA_TOOLS_ROOT` or `PERPETUA_TOOLS_PATH`
before direct CLI use. orama launchers (`start.sh`, `platform/windows/start.ps1`) discover PT
automatically. Reference: `orama-system/bin/orama-system/skills/hermes-harness/references/workspace-path-resolution.md`.

## Architecture (read in this order)

| Layer | File | Role |
|-------|------|------|
| **Policy SSoT** | `config/model_hardware_policy.yml` | Machine truth — lists + aliases |
| **Canonical API** | `src/utils/hardware_policy.py` | `load_policy()`, `_normalize_policy()`, `check_affinity()`, `filter_models_for_platform()` |
| **CLI validation** | `scripts/hardware_policy_cli.py` | Delegates to canonical API — **never duplicate parsers here** |
| **Researcher dispatch** | `scripts/launch_researchers.py` | `_platform_for_role()`, `_pick_model_with_affinity()`, resolvers |
| **Runtime gates** | `agent_launcher.py`, `orchestrator/supervisor.py`, `worker_registry.py` | `check_affinity` before spawn / inference |
| **Discovery filter** | `src/perpetua/discovery/selector.py` | `_MIRROR_BACKENDS` excludes `lmstudio-mac` from Win-only dispatch |
| **Human entry** | `orama-system/start.sh --hardware-policy` | Calls CLI `--list` + `--check-openclaw` |

## Unified Human Surfaces

Do **not** create new human entry points. Use existing orama CLI and Portal:

```bash
cd ../orama-system
./start.sh --hardware-policy    # macOS / Linux OpenClaw
./start.sh --status

# Windows Hermes host (PowerShell, from orama-system repo root):
# .\platform\windows\start.ps1 --hardware-policy

./start.sh                      # Portal: http://localhost:8002 → Hardware Policy panel
```

## Internal Helper Commands

```bash
# Check live openclaw.json (called by ./start.sh --hardware-policy)
python scripts/hardware_policy_cli.py --check-openclaw

# List merged policy (aliases included after _normalize_policy)
python scripts/hardware_policy_cli.py --list

# Validate one model ↔ platform pair (exit 1 on NEVER_MAC / NEVER_WIN)
python scripts/hardware_policy_cli.py --validate "gemma-4-26B-A4B-it-Q4_K_M" mac

# Filter candidate list through affinity
python scripts/hardware_policy_cli.py --filter model1 model2 --platform mac

# Discovery
python3 ~/.openclaw/scripts/discover.py --force
python3 ~/.openclaw/scripts/discover.py --status
```

## Policy Source of Truth

`config/model_hardware_policy.yml` — cite it; do not duplicate full lists in markdown.

**Current shape (verify on disk before citing ids):**

- `windows_only` + `windows_only_aliases` → NEVER_MAC
- `mac_only` + `mac_only_aliases` → NEVER_WIN
- `shared` + `shared_aliases` → both platforms

## Enforcement Layers

| Layer | Component | Action |
|-------|-----------|--------|
| L1 | `discover.py`, `selector.py` | Filter before writing `openclaw.json`; mirror backends excluded |
| L2 | `agent_launcher.py`, `alphaclaw_manager.py` | `HardwareAffinityError` before spawn |
| L2b | `orchestrator/supervisor.py`, `worker_registry.py`, `utils/dispatch_models.py` | Explicit model + affinity before inference |
| **L2c** | `scripts/launch_researchers.py` | `_pick_model_with_affinity` — no blind `models[0]`; platform from `_platform_for_role`; preferred only if allowed post-filter |
| L3 | `api_server.py` | HTTP 400 `HARDWARE_MISMATCH` |
| **Validation** | `hardware_policy_cli.py` | Startup / OpenClaw config gate (bypasses supervisor) |

### Gap history (PRs #128–#131) — do not reintroduce

| Gap | Symptom | Fix location |
|-----|---------|--------------|
| Blind fallback | `mac-researcher` picked first mirror-listed model | `_pick_model_with_affinity` |
| Platform not passed | Win researchers used Mac rules | `run_researcher` → `platform=_platform_for_role(role)` |
| Preferred bypass | Listed Win-only model accepted on Mac | Filter before returning preferred |
| Aliases ignored | Quant-suffixed ids skipped NEVER_MAC | `_normalize_policy` in `load_policy()` |
| Duplicate CLI parser | `start.sh --check-openclaw` false-negative | CLI delegates to `utils.hardware_policy` |

## Rules for AI Agents

1. **Never add unverified model IDs** to policy or config. Confirm with `discover.py --status` on actual hardware.
2. **Never duplicate parsers** — all paths import `src/utils/hardware_policy.py`. After upgrading canonical module, run:
   ```bash
   rg '_simple_policy_parse|def _forbidden' --glob '*.py'
   ```
3. **Case-insensitive matching** — enforcement lowercases model ids.
4. **Three-layer enforcement** — if one layer fails silently, the next should catch it; validation CLI covers OpenClaw direct dispatch.
5. **Anti-mirror — explicit model ids only**: Never POST `model=""` to `lmstudio-mac`. Use `utils.dispatch_models.resolve_dispatch_model()`.
6. **Import direction**: orama imports PT affinity one-way; PT never imports orama for policy.
7. **Cloud bypass**: `check_affinity` skipped when `coder_platform == "cloud"` (see `hardware/startup-intelligence/SKILL.md`).

## Adding a New Model

1. `discover.py --force` on live hardware
2. `--validate MODEL_ID mac` and `--validate MODEL_ID win`
3. Add to `model_hardware_policy.yml` (base id + `*_aliases` if LM Studio uses different casing/quant suffix)
4. `--check-openclaw` must pass
5. Update `hardware/SKILL.md` role matrix Constraint column
6. Run: `pytest tests/test_launch_researchers_affinity.py tests/test_hardware_routing.py -q`

## Pre-dispatch Checklist (with model-routing-check)

Before agent dispatch:

1. Endpoint reachability (`model-routing-check` skill)
2. **Affinity validation:**
   ```bash
   python scripts/hardware_policy_cli.py --check-openclaw
   ```
3. Routing table cross-check (`config/routing.yml` vs `config/models.yml`)

## Common Fixes

```bash
python3 ~/.openclaw/scripts/discover.py --force
python scripts/hardware_policy_cli.py --check-openclaw
```

## Related Skills

- `perpetua-hardware` → `hardware/SKILL.md` (role matrix, VRAM)
- `perpetua-startup-intelligence` → cloud affinity bypass, `start.sh` integration
- `model-routing-check` → endpoint probes + affinity gate (step 2 above)
- orama `hardware-affinity-gate` → imports PT rules one-way; do not duplicate

## Portal GUI

Orama Portal `http://localhost:8002` → **Hardware Policy & Safe Defaults**
