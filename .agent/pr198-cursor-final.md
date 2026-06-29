# PR #198 — Cursor Final Closure Plan (Parity Complete v2)

## 🚨 STATUS
This document is the **authoritative execution + reasoning contract** for fully closing PR #198.

It now includes full parity with:
- CodeRabbit review findings
- OramaSys v2 RFC security model
- CI invariant enforcement system
- Cross-repo transport architecture rules

---

# 🧠 1. EXECUTIVE SUMMARY

PR #198 implements backend routing fixes for:
- active_tilting discovery layer
- Ollama backend (port 11434)
- LM Studio backend (port 1234)

However, the system is still missing a critical invariant:

> ❌ Transport identity (scheme) is not consistently preserved across reconstruction boundaries

This leads to potential:
- implicit http downgrade
- semantic transport loss
- cross-backend routing inconsistency

---

# 🧩 2. SYSTEM CONTEXT (ORAMASYS MODEL)

The system operates under a 3-layer model:

## Layer 1 — Discovery
- active_tilting returns host identity (sometimes scheme-aware URL)

## Layer 2 — Routing
- model_registry assigns backend (ollama / lm-studio)

## Layer 3 — Transport Reconstruction
- URL is rebuilt for runtime usage

👉 BUG CLASS:
Mismatch between Layer 1 (semantic identity) and Layer 3 (transport reconstruction)

---

# ⚠️ 3. CODERABBIT FINDINGS (ROOT INTERPRETATION)

CodeRabbit identified:
- hardcoded http reconstruction
- missing scheme preservation

### BUT SYSTEMIC ROOT CAUSE:

> The system incorrectly treats discovery output as a raw host instead of a structured transport identity

This causes:
- protocol loss
- implicit fallback to HTTP
- hidden SSRF surface inconsistency

---

# 🧠 4. ORAMASYS ROOT CAUSE ANALYSIS

## True failure mode:

> Transport identity was not modeled as a first-class invariant

Instead of:
```
(URL = scheme + host + port)
```
System used:
```
host → assumed http → reconstructed URL
```

---

# 🔐 5. RFC v1 INVARIANT MAPPING

This PR must satisfy OramaSys RFC:

## RFC-001 Invariants:

### ✔ SSRF Boundary
- no unsafe URL parsing outside controlled logic

### ✔ Transport Integrity
- scheme MUST be preserved end-to-end
- no implicit downgrade allowed

### ✔ Backend Isolation
- ollama ≠ lm-studio routing must never overlap

---

# 🔧 6. REQUIRED FINAL FIX

## File:
`orchestrator/model_registry.py`

### Correct implementation:

```python
from urllib.parse import urlparse

def _build_tilting_url(tilted: str, port: int, default_scheme: str = "http") -> str:
    parsed = urlparse(tilted if "://" in tilted else f"{default_scheme}://{tilted}")

    scheme = parsed.scheme or default_scheme
    hostname = parsed.hostname

    if not hostname:
        return _expand_env_default(str(tilted))

    return f"{scheme}://{hostname}:{int(port)}"
```

---

# 🧪 7. CI ENFORCEMENT LINKAGE

This fix is enforced by:

- `.github/workflows/security-invariant-enforcer.yml`
- `.github/workflows/invariant-monitor-bot.yml`

## CI MUST FAIL IF:
- `http://http` pattern appears
- `urlparse()` used outside policy boundary
- scheme downgrade detected

---

# 🌐 8. CROSS-REPO CONSISTENCY RULE

This invariant applies to:
- Perpetua-Tools
- Orama-System

## MUST MATCH:
- SSRF policy behavior
- transport reconstruction rules
- authentication safety model

Any divergence = system integrity failure

---

# 🧠 9. FINAL SYSTEM STATE AFTER FIX

After applying this patch, PR #198 becomes:

✔ deterministic backend routing system
✔ invariant-safe transport reconstruction
✔ SSRF-aligned execution model
✔ CodeRabbit findings fully resolved at root cause level

---

# 🚀 10. MERGE CHECKLIST

- [ ] scheme preserved from upstream when present
- [ ] no hardcoded http reconstruction
- [ ] no cross-backend contamination
- [ ] CI passing with invariant enforcement

---

# 📌 EXECUTION RULE

> Always preserve scheme first, normalize second, route third.
