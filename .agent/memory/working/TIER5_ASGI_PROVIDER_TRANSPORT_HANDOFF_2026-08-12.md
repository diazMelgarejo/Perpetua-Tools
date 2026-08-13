# Tier-5 ASGI Provider Transport Review Handoff

**Branch:** `feat/tier5-asgi-harmonized-20260811`
**Code commits:** `248f7e4a`, `0473fe25`
**Publication:** local only; no push or pull request.

## Review Request

Claude and AntiGravity-Gemini should review the code commits as one coherent
change set before any publication. Do not include unrelated local `.agent`,
`.codex`, or `vendor/ecc-tools` changes in this review or a later push.

## Delivered

1. Aligned the PT ASGI runtime and lock to FastAPI 0.141.1 and Starlette 1.6.0,
   and replaced the control-plane HTTP wrapper with a pure ASGI auth boundary.
2. Added a Tier-5 runner with explicit opt-in, existing frugality-gate and cost
   checks, native BigModel and Anthropic transports, bounded retries, host
   allowlists, and redacted provider failures.
3. Made cloud model wire IDs configuration-derived and provenance-gated rather
   than maintained in a second static code list. The provider source URL and
   model ID must agree before dispatch.

## Verification

- `python3 scripts/check_model_ids.py`
- focused Tier-5 suite: 33 passing tests
- focused ASGI/auth/routing/resilience suite: 107 passing tests
- `uv lock --check` and global `python3 -m pip check`

## Review Focus

- ASGI middleware ordering and control-plane authentication behavior.
- Provider request construction, credential handling, egress limits, retries,
  and error redaction.
- Cost reservation ordering, feature gating, and absence of caller-selected
  model or endpoint parameters.
- Registry provenance validation, alias versus API-model separation, and
  future provider-adapter extension points.

## Known Follow-up

The passing TestClient tests emit a non-blocking framework deprecation warning
for a future `httpx2` migration. Treat that as a separately scoped dependency
transition, not a reason to weaken the current compatibility lock.
