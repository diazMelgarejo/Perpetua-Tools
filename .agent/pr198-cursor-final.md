# PR #198 — Cursor Final Closure Plan (Executable)

## 🚨 Goal
Fully close PR #198 by enforcing remaining OramaSys v2 invariants and removing all CodeRabbit ambiguity.

This is the **authoritative Cursor execution file**.

---

# 🧠 CONTEXT

PR #198 fixes backend routing for:
- active_tilting discovery
- Ollama (11434)
- LM Studio (1234)

BUT still has a missing invariant:

> ❌ Transport scheme identity is not consistently preserved

---

# 🔧 REQUIRED FINAL FIX

## File:
`orchestrator/model_registry.py`

### Replace reconstruction logic with invariant-safe version:

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

# 🧠 ROOT CAUSE FIXED

This resolves:

- implicit http downgrade
- scheme loss from active_tilting output
- cross-backend transport contamination

---

# 🧪 REQUIRED TEST VALIDATION

Run:

```bash
pytest tests/test_hardware_routing.py -q
pytest tests/test_scheme_preservation.py -q
```

Must ensure:

- no `http://http` duplication
- scheme preserved if present
- Ollama stays on 11434
- LM Studio stays on 1234

---

# 🔐 FINAL INVARIANTS (MUST HOLD)

## 1. SSRF Safety
- no raw urlparse decision-making outside controlled boundary

## 2. Transport Integrity
- scheme is part of identity
- never silently downgraded

## 3. Backend Isolation
- Ollama ≠ LM Studio routing
- ports MUST remain isolated

---

# 🚀 MERGE CHECKLIST

- [ ] scheme-preserving helper applied
- [ ] no hardcoded http reconstruction
- [ ] tests passing
- [ ] no regression in routing logic

---

# 🧠 FINAL SYSTEM STATE AFTER APPLYING

PR #198 becomes:

✔ deterministic routing system
✔ invariant-safe transport layer
✔ SSRF-aligned architecture
✔ CodeRabbit fully satisfied

---

# 📌 EXECUTION RULE

If any uncertainty exists:

> ALWAYS preserve scheme first, normalize second, route third.
