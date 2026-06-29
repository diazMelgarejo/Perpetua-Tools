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

This document records what actually landed, what repo-level support exists outside the PR, and what remains outside the PR scope.

---

## Executive Summary

PR #198 landed the minimal production fix for active-tilting routing on the Windows GPU host.

It fixed two critical runtime invariants:

1. Ollama models on `win-rtx3080` must use Ollama port `11434`, not the LM Studio port returned by active tilting.
2. Transport scheme is part of endpoint identity and must be preserved when reconstructing the Ollama URL.

The PR is complete for the production bug it targeted. It is not a full endpoint-policy or cross-repo security architecture rollout.

---

## Actual Merged Implementation

File: `orchestrator/model_registry.py`

The merged helper is:

```python
from urllib.parse import urlparse


def _build_tilting_url(tilted: str, port: int, *, default_scheme: str = "http") -> Optional[str]:
    """Rebuild scheme://hostname:port from active_tilting discovery output.

    Preserves the transport scheme when discovery returns an absolute URL
    (e.g. https overrides). Returns None when hostname cannot be parsed so
    callers can fall back to models.yml host expansion.
    """
    parsed = urlparse(tilted if "://" in tilted else f"{default_scheme}://{tilted}")
    hostname = parsed.hostname
    if not hostname:
        return None
    scheme = parsed.scheme or default_scheme
    return f"{scheme}://{hostname}:{int(port)}"
```

The merged routing behavior is:

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
- Ollama reuses the discovered host and scheme, but swaps to the Ollama model port.
- Invalid discovery output falls back to the configured model host instead of constructing a malformed URL.

---

## Landed Invariants

| Invariant | Landed in PR #198 | Evidence |
|---|---:|---|
| Ollama on `win-rtx3080` uses `:11434` | Yes | `test_active_tilting_ollama_win_uses_model_port_not_lmstudio` |
| LM Studio remains on discovered `:1234` endpoint | Yes | same regression test |
| Scheme is preserved from active-tilting output | Yes | `tests/test_scheme_preservation.py` |
| No `http://http` double-scheme reconstruction | Yes | `test_build_tilting_url_no_double_scheme` |
| Invalid tilted output falls back safely | Yes | `_build_tilting_url()` returns `None`; `_resolve_host()` falls back to config host |
| Live-probe bypass is preserved | Yes | existing `PT_DISABLE_LIVE_MODEL_PROBES` branch remains intact |

---

## Test Coverage Landed

File: `tests/test_scheme_preservation.py`

Landed coverage includes:

- HTTPS preservation: `https://win-box.example:1234` -> `https://win-box.example:11434`
- Bare host defaulting to HTTP only when no scheme exists
- No `http://http` duplication
- No-host parse failure returns `None`
- `_resolve_host()` preserves HTTPS for Ollama
- `_resolve_host()` returns LM Studio tilted endpoint unchanged

File: `tests/test_hardware_routing.py`

Landed coverage includes:

- Active tilting returns LM Studio endpoint on `:1234`
- Ollama model on same device resolves to `:11434`
- LM Studio model resolves to `:1234`

---

## CodeRabbit Review Resolution

CodeRabbit's important finding was not merely "wrong port". The deeper issue was transport reconstruction.

Root issue:

```text
active_tilting output was being treated as a host-ish string instead of a transport identity.
```

Correct invariant:

```text
transport identity = scheme + host + port
```

PR #198 resolves this locally in `model_registry.py` by preserving `scheme`, extracting `hostname`, and replacing only the backend-specific port.

---

## Repo-Level Enforcement Outside PR #198

The broader enforcement work exists on `main`, but it was not part of PR #198's changed-file set.

Present on `main`:

```text
.github/workflows/security-invariant-enforcer.yml
.github/workflows/invariant-monitor-bot.yml
AGENTS.md
```

The workflows run targeted invariant tests and block obvious transport regressions such as `http://http` in production Python.

Important distinction:

- PR #198 landed the runtime fix and regression tests.
- The enforcement workflows and agent rules are repo-level support that exist outside the PR diff.

---

## Grand Plan Comparison

| Planned item | Landed in PR #198 | Present elsewhere on `main` | Notes |
|---|---:|---:|---|
| Scheme-preserving active-tilting reconstruction | Yes | Yes | Implemented in `_build_tilting_url()` |
| Ollama vs LM Studio port isolation | Yes | Yes | Ollama uses configured model port; LM Studio unchanged |
| Regression tests for scheme and routing | Yes | Yes | Two test files in PR |
| CI invariant monitor | No | Yes | Workflow exists outside PR #198 |
| Security invariant enforcer workflow | No | Yes | Workflow exists outside PR #198 |
| AGENTS.md invariant guidance | No | Yes | Repo-level agent guidance exists outside PR #198 |
| Shared `endpoint_policy_core` abstraction | No | No confirmed landing | Still not extracted as a shared endpoint-policy module |
| Multi-repo mesh enforcement | No | Partial / external | Not landed as a PR #198 artifact |
| Full SSRF platform redesign | No | Partial support only | PR #198 was intentionally a local routing fix |

---

## Remaining Gaps

No blocking gap remains for PR #198's production bug.

Remaining architecture gaps are outside PR #198 scope:

1. `endpoint_policy_core` has not been extracted as a shared module.
2. SSRF/transport policy is not yet centralized across every endpoint construction site.
3. Cross-repo mesh enforcement is not represented as a single auditable contract in this PR.
4. The current workflows catch targeted regressions, but they do not prove full system-wide endpoint-policy compliance.

These are follow-up architecture tasks, not defects in PR #198.

---

## Final Verdict

PR #198 is complete and landed on `main` for the bug it was created to fix.

It delivered:

- Correct Ollama routing under active tilting
- LM Studio routing preservation
- Scheme-preserving transport reconstruction
- Regression coverage for port isolation and scheme preservation

It did not deliver the full grand architecture rollout. That broader plan is partially present on `main` via workflows and AGENTS guidance, with `endpoint_policy_core` and full multi-repo enforcement still remaining as follow-up work.

Execution rule retained from the design discussion:

```text
Preserve scheme first, normalize host second, route by backend-specific port third.
```
