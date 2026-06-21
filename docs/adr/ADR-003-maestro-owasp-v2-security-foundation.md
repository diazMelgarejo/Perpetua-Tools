# ADR-003: MAESTRO/OWASP v2 Runtime Security Foundation

**Status:** Accepted
**Date:** 2026-06-18
**Deciders:** cyre (diazMelgarejo)

---

## Context

orama-system is the canonical documentation and security-intelligence layer for
the three-repo stack. Perpetua-Tools is the stateful runtime layer that owns
adapters, local workers, AlphaClaw MCP packages, memory/RAG persistence, model
discovery, and endpoint routing.

The v2 security foundation now incorporates the attached MAESTRO and OWASP GenAI
research materials into the orama v2 docs:

- <https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/31-security-harness-excellence-plan.md>
- <https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/32-agentic-security-controls.md>
- <https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/39-maestro-owasp-genai-reference.md>

Those documents establish the strict guideline baseline for v2.0.0-STABLE and
the v2.1 security target: MAESTRO layer tracing, OWASP Agentic/MCP threat
coverage, local threat IDs, AIVSS candidate scoring, and runtime controls for
MCP, memory, identity, and egress.
The canonical online verification link index is maintained in orama
`docs/v2/39-maestro-owasp-genai-reference.md` §10.

---

## Decision

Perpetua-Tools adopts the orama v2 security foundation as its runtime security
contract.

PT will use local threat IDs in the `PT-01`, `PT-02`, ... `PT-09` format for
repo-owned threats. PT must not insert an extra `T` after the repo prefix or use
any other local pattern that resembles the OWASP `T1`-style namespace.

PT is responsible for implementing the stateful runtime controls that orama
documents but intentionally does not own:

| Runtime surface | PT obligation |
|---|---|
| MCP tools | Pin tool definitions with SHA-256 baselines and block unapproved drift. |
| Memory/RAG | Persist source attribution, content hashes, TTLs, and session/user isolation metadata. |
| Model and MCP egress | Micro-segment approved endpoints; strip control-plane auth from probes and third-party calls. |
| Worker identity | Use short-lived, task-scoped credentials; keep long-lived secrets out of prompts, memory, MCP config, and worker env. |
| Local artifacts | Keep logs, traces, screenshots, databases, and `/tasks/` in ignored runtime paths only. |
| Dependency state | Treat lockfiles as security surfaces and fix Dependabot alerts in the exact named lockfile. |

Every new orbit/runtime integration must declare:

- MAESTRO layer or layers touched.
- Local `PT-01`-style threat trace.
- Whether it adds state, egress, tool execution, or cross-agent communication.
- Verification gates for the touched surface.

---

## v2.0.0-STABLE Foundation

v2.0.0-STABLE must ship with the scaffold ready:

- PT policy points to the orama v2 canonical security docs.
- Runtime docs and comments use `PT-01` style local threat IDs only.
- MCP and worker defaults remain least-privilege and opt-in for dangerous
  capabilities.
- Memory and prompt artifacts are treated as sensitive even when generated
  locally.
- Provider and control-plane bearer tokens stay in environment/keychain storage,
  never tracked config or examples.

---

## v2.1 Target

v2.1 should turn the scaffold into enforceable gates:

- MCP tool-definition hash pinning with explicit operator approval for changes.
- Memory write metadata for source, content hash, TTL, scope, and retrieval audit.
- Micro-segmented model/MCP egress policy around approved hosts and ports.
- AIVSS candidate scoring for high-risk local `PT-01`-style findings.
- Test coverage that proves auth stripping, profile merging, path boundaries,
  ignored runtime artifacts, and lockfile-security behavior.

---

## Consequences

**What becomes clearer:**

- orama remains the canonical standards and threat-model home.
- PT is the runtime implementation owner for stateful controls.
- Local PT threat IDs cannot be confused with OWASP Agentic/MCP `T1`-style IDs.

**What becomes stricter:**

- Security docs, package changes, and runtime integrations must include threat
  traceability.
- Lockfile and config drift is treated as security drift.
- MCP, memory, egress, and worker identity changes require explicit verification
  instead of relying on operator convention.

---

## Verification

Minimum gates for changes under this ADR:

- `python3 scripts/review/repo_hygiene.py .`
- Package-specific tests for the touched runtime, such as
  `npm test` in `packages/alphaclaw-mcp`
- Focused tests for auth stripping, tool/profile restrictions, memory metadata,
  or endpoint pinning when those surfaces change
