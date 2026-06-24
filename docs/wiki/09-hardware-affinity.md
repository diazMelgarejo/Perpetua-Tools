# 09. Hardware Affinity Enforcement

**TL;DR:** `windows_only` models on Mac = OOM or double-barrel GPU damage. Policy lives in YAML; enforcement in `src/utils/hardware_policy.py`; never duplicate parsers.

---

## Root Cause Class

LM Studio on Mac **proxies Win models** over LAN. Mac `/v1/models` lists ids like `gemma-4-26B-A4B-it-Q4_K_M` even though they are physically Win-only GGUF. Enforcement must use **provider/platform** (`lmstudio-mac` vs `lmstudio-win`), not model-list membership.

## Policy (invariant)

`config/model_hardware_policy.yml`:

- `windows_only` + `windows_only_aliases` → **NEVER_MAC**
- `mac_only` + `mac_only_aliases` → **NEVER_WIN**
- `shared` + `shared_aliases` → both platforms

## Canonical API

`src/utils/hardware_policy.py`:

- `_normalize_policy()` merges `*_aliases` into enforceable lists (PR #130)
- `check_affinity()`, `filter_models_for_platform()`, `load_policy()`

## Five gaps closed (PRs #128–#131)

| Gap | Where | Fix |
|-----|-------|-----|
| Blind `models[0]` fallback | `launch_researchers.py` | `_pick_model_with_affinity` |
| Platform not passed | `run_researcher()` | `_platform_for_role(role)` |
| Preferred bypass when listed | resolvers | Filter before returning preferred |
| Aliases ignored | `load_policy()` | `_normalize_policy` |
| Duplicate CLI parser | `hardware_policy_cli.py` | Delegate to canonical API |

## Validation path

```bash
python scripts/hardware_policy_cli.py --check-openclaw
python scripts/hardware_policy_cli.py --validate gemma-4-26B-A4B-it-Q4_K_M mac  # exit 1
cd ../orama-system && ./start.sh --hardware-policy
```

## Tests

```bash
pytest tests/test_launch_researchers_affinity.py tests/test_hardware_routing.py -q
```

## Agent skill

`.claude/skills/hardware-policy/SKILL.md` — operational playbook for all harnesses.

## Hermes Windows (parallel orchestrator)

On Windows 11, Hermes consumes **this same policy** via `start.ps1 --hardware-policy`.
`windows_only` models are allowed on localhost LM Studio; role is reversed from Mac OpenClaw.
See orama `hermes-harness` → `commands/pt-hardware-policy/SKILL.md`.

## Prevention

After changing `hardware_policy.py`:

```bash
rg '_simple_policy_parse|def _forbidden' --glob '*.py'
```

Duplicate parsers silently diverge (DECISIONS.md §2026-06-24, PR #131).
