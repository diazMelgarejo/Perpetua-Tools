# PR #198 — Merged-State Closure Audit

## Status

PR #198 is closed and merged into `main`.

- PR: https://github.com/diazMelgarejo/Perpetua-Tools/pull/198
- Merge commit: `4c934e81e5ccae092670f21a8f5998cb49f58cf3`
- Head commit: `2f00a14f122ca01f2b16d6be1a4ede90bd3f8e34`
- Base at merge time: `faca14eea988a1764194ec5554419b7f3cb6f080`
- Changed files in PR: 3

Files landed by PR #198:

```text
orchestrator/model_registry.py
tests/test_hardware_routing.py
tests/test_scheme_preservation.py
```

Follow-up architecture now implemented on `main` after PR #198:

```text
src/utils/endpoint_policy_core.py
tests/test_endpoint_policy_core.py
scripts/security/check_endpoint_policy_core.py
.agent/endpoint-policy-contract.yml
.github/workflows/security-invariant-enforcer.yml
.github/workflows/invariant-monitor-bot.yml
AGENTS.md
```

---

## Executive Summary

PR #198 landed the minimal production fix for active-tilting routing on the Windows GPU host.

It fixed two critical runtime invariants:

1. Ollama models on `win-rtx3080` must use Ollama port `11434`, not the LM Studio port returned by active tilting.
2. Transport scheme is part of endpoint identity and must be preserved when reconstructing the Ollama URL.

The follow-up architecture now promotes that local PR fix into a shared endpoint transport policy boundary on `main`.

---

## Current Main Implementation

File: `src/utils/endpoint_policy_core.py`

Canonical transport helpers:

```python
def parse_transport_identity(source: str, *, default_scheme: str = "http") -> Optional[TransportIdentity]:
    ...


def build_transport_url(source: str, port: int, *, default_scheme: str = "http") -> Optional[str]:
    ...
```

The core owns URL parsing for transport reconstruction and returns `None` for malformed, credentialed, unsupported-scheme, or missing-host inputs so callers can fall back safely.

File: `orchestrator/model_registry.py`

The compatibility helper now delegates to the shared policy core:

```python
from utils.endpoint_policy_core import build_transport_url


def _build_tilting_url(tilted: str, port: int, *, default_scheme: str = "http") -> Optional[str]:
    return build_transport_url(tilted, port, default_scheme=default_scheme)
```

The active-tilting behavior remains:

```python
if dev_info.get("identity_method") == "active_tilting" and not live_disabled:
    from orchestrator.lan_discovery import detect_active_tilting_ip

    tilted = detect_active_tilting_ip()
    if item.get("backend") != "ollama":
        return tilted
    rebuilt = _build_tilting_url(tilted, int(item.get("port", 11434)))
    if rebuilt is None:
        return _expand_env_default(str(item.get("host", "")))
    return rebuilt
```

This means:

- LM Studio keeps the active-tilting endpoint unchanged.
- Ollama reuses the discovered scheme/host and swaps to the Ollama model port.
- Invalid discovery output falls back to the configured model host instead of constructing a malformed URL.

---

## Landed Invariants

| Invariant | Landed in PR #198 | Promoted on `main` after PR #198 | Evidence |
|---|---:|---:|---|
| Ollama on `win-rtx3080` uses `:11434` | Yes | Yes | `test_active_tilting_ollama_win_uses_model_port_not_lmstudio` |
| LM Studio remains on discovered `:1234` endpoint | Yes | Yes | same regression test |
| Scheme is preserved from active-tilting output | Yes | Yes | `tests/test_scheme_preservation.py` |
| No `http://http` double-scheme reconstruction | Yes | Yes | `test_build_tilting_url_no_double_scheme` plus workflow grep |
| Invalid tilted output falls back safely | Yes | Yes | `_build_tilting_url()` returns `None`; `_resolve_host()` falls back to config host |
| Live-probe bypass is preserved | Yes | Yes | existing `PT_DISABLE_LIVE_MODEL_PROBES` branch remains intact |
| Shared endpoint transport boundary | No | Yes | `src/utils/endpoint_policy_core.py` |
| Structural CI enforcement | No | Yes | `scripts/security/check_endpoint_policy_core.py` |
| Multi-repo contract record | No | Yes | `.agent/endpoint-policy-contract.yml` |
| Agent guidance for future edits | No | Yes | `AGENTS.md` endpoint transport policy section |

---

## Test Coverage

PR #198 landed:

- `tests/test_scheme_preservation.py`
- `tests/test_hardware_routing.py::test_active_tilting_ollama_win_uses_model_port_not_lmstudio`

Follow-up architecture added:

- `tests/test_endpoint_policy_core.py`

Coverage now includes:

- HTTPS preservation
- Bare host defaulting to HTTP only when no scheme exists
- No `http://http` duplication
- No-host parse failure returns `None`
- Credentialed endpoint rejection
- Unsupported scheme rejection
- Malformed port rejection
- IPv6 bracket-safe reconstruction
- `_resolve_host()` preserves HTTPS for Ollama
- `_resolve_host()` returns LM Studio tilted endpoint unchanged

---

## CodeRabbit Review Resolution

CodeRabbit's important finding was not merely "wrong port". The deeper issue was transport reconstruction.

Root issue:

```text
active_tilting output was being treated as a host-ish string instead of a transport identity.
```

Correct invariant:

```text
transport identity = scheme + hostname + backend-specific port
```

PR #198 resolved this locally. The follow-up architecture now centralizes the transport reconstruction boundary in `src/utils/endpoint_policy_core.py`.

---

## CI And Multi-Repo Enforcement

Present on `main`:

```text
.github/workflows/security-invariant-enforcer.yml
.github/workflows/invariant-monitor-bot.yml
scripts/security/check_endpoint_policy_core.py
.agent/endpoint-policy-contract.yml
AGENTS.md
```

The workflows now run:

```bash
python scripts/security/check_endpoint_policy_core.py
pytest tests/test_endpoint_policy_core.py \
  tests/test_scheme_preservation.py \
  tests/test_hardware_routing.py::test_active_tilting_ollama_win_uses_model_port_not_lmstudio \
  tests/test_model_endpoint_url.py -q --tb=short
```

The structural checker enforces:

- `model_registry.py` imports `build_transport_url` from `utils.endpoint_policy_core`
- `model_registry.py` does not call `urlparse()` directly
- the core owns the transport URL parsing boundary
- both invariant workflows run the core tests and checker
- `.agent/endpoint-policy-contract.yml` names Perpetua-Tools and orama-system as the contract pair
- production Python under `orchestrator/` and `src/` does not contain double-scheme transport literals

---

## Grand Plan Comparison

| Planned item | Landed in PR #198 | Implemented on `main` now | Notes |
|---|---:|---:|---|
| Scheme-preserving active-tilting reconstruction | Yes | Yes | Implemented locally, then promoted to core |
| Ollama vs LM Studio port isolation | Yes | Yes | Ollama uses configured model port; LM Studio unchanged |
| Regression tests for scheme and routing | Yes | Yes | PR tests remain |
| CI invariant monitor | No | Yes | Workflow updated to run core checker/tests |
| Security invariant enforcer workflow | No | Yes | Workflow updated to run core checker/tests |
| AGENTS.md invariant guidance | No | Yes | Endpoint transport policy section added |
| Shared `endpoint_policy_core` abstraction | No | Yes | `src/utils/endpoint_policy_core.py` |
| Multi-repo mesh contract | No | Yes, local contract | `.agent/endpoint-policy-contract.yml` records Perpetua + orama contract |
| Full SSRF platform redesign | No | Partial | Transport reconstruction is centralized; network allow/deny remains in `src/utils/model_endpoint_url.py` |

---

## Remaining Gaps

No blocking gap remains for PR #198's production bug or for the local endpoint transport architecture.

Remaining broader-system work:

1. Mirror or consume `.agent/endpoint-policy-contract.yml` from `diazMelgarejo/orama-system` so the contract is enforced from both sides.
2. Audit every endpoint construction site outside `model_registry.py` and decide whether each should call `endpoint_policy_core`, `model_endpoint_url`, or both.
3. Add an inter-repo scheduled workflow only if GitHub credentials/permissions are available for cross-repo reads.

These are cross-repo rollout tasks, not missing local main-branch implementation.

---

## Final Verdict

PR #198 is complete and landed on `main` for the bug it was created to fix.

The broader follow-up architecture is now also implemented locally on `main`:

- shared endpoint transport core
- direct core tests
- structural CI checker
- updated invariant workflows
- AGENTS policy guidance
- local multi-repo contract record

Execution rule retained from the design discussion:

```text
Preserve scheme first, normalize host second, route by backend-specific port third.
```