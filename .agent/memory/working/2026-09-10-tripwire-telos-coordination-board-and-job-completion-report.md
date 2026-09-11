# Coordination Board + Job Completion Report — Tripwire → Telos Restoration

**Date:** 2026-09-10  
**Distribution:** all OramaSys agents working on Telos, Phylax, Gateway, provider networking, endpoint policy, or v1/v2 migration  
**Status:** Oramasys Gateway review remediation complete; PT handoff published with explicit remaining PT verification debt  
**Merge authority:** **NONE — no PR listed here is authorized to merge without explicit owner instruction.**

## 1. Mission

Restore and preserve the accepted 2026-08-29 architecture in which `oramasys/telos` is the sole reusable v2 endpoint-security authority succeeding Tripwire. Telos owns endpoint identity, DNS/address validation, SSRF defense, DNS-rebinding resistance, pinned transport, peer verification, redirect/proxy/TLS destination safety, and endpoint-use authorization. Consumer repositories retain application/provider semantics and orchestration but MUST NOT establish a second permanent endpoint-security authority.

The v1/v2 boundary remains strict: `diazMelgarejo/Perpetua-Tools` remains an independent v1 implementation and clean-room evidence source. v2 packages MUST NOT depend on PT at runtime, and PT MUST NOT depend on v2 Telos at runtime.

## 2. Canonical ownership matrix

| Repository / owner | Canonical responsibility |
| --- | --- |
| `oramasys/telos` | **ALL endpoint-specific security**: canonical endpoint identity, DNS/every-answer validation, address/SSRF policy, rebinding resistance, connection pinning, peer verification, redirects, proxy isolation, TLS destination identity, endpoint-use authorization |
| `oramasys/phylax` | General compile/runtime security and safety admission, provenance, integrity/redaction, generic runtime-check and monitorability substrate; explicitly **not** endpoint-specific transport security |
| `oramasys/oramasys` | Application/workflow composition, route/budget/effect and provider-purpose policy; mandatory Telos consumer |
| `oramasys/Claude-Desktop-LLM` | Ollama/LM Studio protocol, lifecycle, readiness, provider-native observability; mandatory Telos consumer |
| `oramasys/agate` | Hardware capability, fit and placement evidence |
| `oramasys/perpetua-core` | Irreducible execution mechanics |
| PT v1 | Independent v1 endpoint-security runtime plus clean-room provenance/parity evidence for v2 |

**Ownership is not the same as universal enforcement.** Historical outbound paths become Telos-enforced only after explicit consumer migration and verification.

## 3. Current exact heads and completion state

| Repo / PR | Exact head / pinned evidence | Current state |
| --- | --- | --- |
| `oramasys/oramasys` PR #5 | `2d6ebc3a03661a69bc94475c1a1291e84dff1a21` | **Review remediation complete.** Open, not merged. CodeRabbit review `5160504280` fully addressed. Exact-head Actions run `34413937288` succeeded on Python 3.11 and 3.12; coverage/test and compile-smoke steps succeeded; fresh review sweep found **0 unresolved review threads**. |
| `oramasys/telos` | pinned dependency/evidence head `19810d0493344aa507c29c462f68afbc1b98ecf8` for Oramasys PR #5; prior restoration verification head recorded in the canonical board as `509d38299011d82f8df14e577169898bdebc344c` | Telos is the endpoint-security authority consumed by Gateway. Agents MUST re-fetch the active PR head before additional edits. |
| `oramasys/Claude-Desktop-LLM` PR #1 | `6a602e8786708dbe62a112360ddde4ba63b8c3ad` | Consumer transfer previously verified; no direct-fallback authority permitted. |
| `oramasys/phylax` PR #1 | `9c5ad79e95c0400a0e24ef7c4f5d6fd90a9b27c5` | Apache-2.0 / Telos-boundary correction previously verified. |
| `diazMelgarejo/orama-system` PR #351 | existing branch reused; prior ADR correction commits recorded in canonical board | Canonical restoration documentation PR. Re-fetch exact head/checks before further edits. |
| `diazMelgarejo/Perpetua-Tools` PR #382 | `2b06c20cff94c7450f0fe71c56eff6bb50290542` before this report commit | Open, not merged. Security invariants, Markdown Lint, multi-repo security mesh and PR-body guard succeeded. Main CI run `34413824926` failed: Python 3.11 `Run tests` failed and Python 3.12 was cancelled. One unresolved/outdated rendered-memory review thread remains in `.agent/memory/semantic/LESSONS.md`; fix must be made through the canonical memory source/generation path rather than hand-editing the rendered file. |

## 4. Oramasys PR #5 — completed job report

### Review remediations completed

All findings from CodeRabbit review `5160504280` were implemented on the existing PR branch:

1. Pull-request CI checkout credentials are no longer persisted.
2. Migration evidence records immutable Telos and Oramasys implementation heads.
3. Unsupported endpoint schemes translate to `transport_not_permitted` rather than an incorrect port error.
4. Empty Telos `resolved_addresses` cannot produce an `IndexError` during Gateway result translation.

### Final Gateway/Telos boundary

Telos owns:

- endpoint canonical identity;
- DNS and every-answer validation;
- SSRF/address classification;
- IPv4-mapped IPv6 normalization;
- metadata, special-use, CGNAT and transition-network policy;
- public/private/loopback transport admission;
- purpose-scoped endpoint authorization;
- vetted pin selection;
- connected-peer pin verification;
- redirect/proxy/TLS destination security;
- dial timeout and security-failure semantics.

Oramasys retains:

- compatibility/application-policy names (`ModelServerDialRequest`, `ModelServerDialResult`, `ModelServerDialer`);
- `DialConnector` only as the compatibility pointer/alias to Telos `SecureDialConnector`;
- stable Gateway reason aliases;
- provider/purpose/port application capability policy;
- lifecycle orchestration, progress, idempotency, readiness and routing-state construction.

There is no trusted caller-supplied `EndpointRef.is_public` authority and no optional non-Telos secure-dial fallback.

### Verification evidence

- Exact Oramasys PR #5 head: `2d6ebc3a03661a69bc94475c1a1291e84dff1a21`.
- GitHub Actions run: `34413937288`.
- Python 3.11: success.
- Python 3.12: success.
- test-with-coverage: success on both matrix jobs.
- compile smoke: success on both matrix jobs.
- unresolved review threads after remediation: **0**.
- PR state: **open, not merged**.

## 5. PT `.agent` durable-memory state

Agents MUST retrieve these before making endpoint-security ownership changes:

1. `.agent/memory/semantic/TRIPWIRE_TELOS_ENDPOINT_SECURITY_AUTHORITY_2026-09-10.md`
2. graduated lesson `lesson_5efb8cefb8af`
3. `.agent/memory/semantic/LESSONS.md` — **rendered artifact; do not hand-edit**
4. `.agent/memory/working/2026-09-10-tripwire-telos-restoration-coordination-board.md`
5. this report

The canonical lesson states that Telos is the sole reusable v2 endpoint-security authority succeeding Tripwire and that v2 consumers must not permanently reimplement secure connectors.

### PT verification debt that is NOT complete

Do not propagate a false all-green status for PT PR #382.

At exact pre-report head `2b06c20cff94c7450f0fe71c56eff6bb50290542`:

- `OramaSys Security Invariants` run `34413824918`: success;
- `Markdown Lint` run `34413824910`: success;
- `OramaSys Multi-Repo Security Mesh` run `34413824941`: success;
- `PR body anti-clobber guard` run `34413825005`: success;
- main `CI` run `34413824926`: **failure**;
- `lint-and-test (3.11)`: **failure** in `Run tests`;
- `lint-and-test (3.12)`: **cancelled** during `Run tests`;
- review threads: one unresolved/outdated thread concerning sanitized examples in rendered `.agent/memory/semantic/LESSONS.md`.

The rendered `LESSONS.md` issue MUST be corrected via the canonical source/tooling path. Direct manual edits to the generated semantic render are prohibited because they would break memory provenance and regeneration guarantees.

## 6. Coverage invariant

Across all projects in this workstream:

> Maintain at least **80% test coverage across the project**. If a component defines a stricter threshold, that stricter threshold applies and MUST NOT be lowered.

Passing targeted tests does not waive this floor. A docs-only or metadata-only commit does not retroactively make a failing code head green; exact-head checks remain authoritative.

## 7. Hard rules for every agent

1. **Never create a permanent secure connector outside Telos in v2.**
2. **Never add a direct network fallback when Telos is unavailable or denies.**
3. **Never restore caller-provided `is_public` as trusted security evidence.**
4. **Never make PT v1 depend on Telos or another v2 package.**
5. **Never make Telos depend on PT v1 at runtime.**
6. Preserve provider/application semantics with their domain owner while outsourcing endpoint-security mechanics and decisions to Telos.
7. Maintain >=80% project coverage and every stricter component threshold.
8. Re-fetch the exact PR head, checks and unresolved review threads before any completion claim.
9. Reconcile concurrent branch updates before writing; never overwrite another agent's additive work blindly.
10. **Never merge without explicit owner authorization.**

## 8. Immediate next-agent queue

### A. PT PR #382 — required before declaring PT complete

- Retrieve the full failing Python 3.11 test log for run `34413824926` and identify the exact failing test(s).
- Fix only verified current failures.
- Locate the canonical memory source that generated the broken sanitized examples; repair that source/tooling path, regenerate `LESSONS.md`, validate JSONL/memory invariants, and resolve the remaining review thread.
- Re-run/observe exact-head Python 3.11 and 3.12 CI.
- Do not call PT complete until exact-head CI is green and unresolved review-thread count is zero.

### B. Cross-repo consumers

- Audit remaining direct `curl`, `urllib`, `httpx`, fetch/socket, or bespoke dialer paths individually.
- Do not infer universal Telos enforcement from canonical ownership alone.
- For every migrated path, preserve application semantics while delegating endpoint identity, DNS/SSRF, pinning, redirect/proxy/TLS policy and peer verification to Telos.

### C. Documentation/evidence

- Keep `diazMelgarejo/orama-system` PR #351 as the single canonical restoration-docs PR.
- Keep contaminated/unverified “Document 7” claims quarantined unless regrounded in repository/commit/PR/owner evidence.

## 9. Distribution checklist

An agent receiving this file should:

1. read the durable PT Telos authority memory and graduated lesson;
2. re-fetch current heads for every PR it will touch;
3. compare those heads against this report rather than assuming they are unchanged;
4. treat completed Oramasys PR #5 remediation as verified at the recorded exact head;
5. treat PT PR #382 as **not yet complete** until its current CI/review debt is resolved;
6. preserve the 80% coverage floor and stricter local thresholds;
7. make additive, authority-preserving changes only;
8. never merge without explicit owner instruction.

## 10. Completion declaration for this handoff

**Completed:**

- canonical Tripwire → Telos ownership restored in durable coordination material;
- Oramasys Gateway dedicated-dialer review remediation for PR #5 implemented on the existing branch;
- all four PR #5 review findings closed;
- exact-head Oramasys PR #5 matrix/coverage/compile checks green;
- Oramasys PR #5 has zero unresolved review threads;
- distributable coordination/job-completion report published to PT's current PR branch.

**Not completed / intentionally still open:**

- PT PR #382 main CI is not green at the recorded pre-report head;
- one PT rendered-memory review thread remains unresolved pending canonical-source repair;
- no PR has been merged by this handoff;
- universal migration of every historical outbound path is not claimed.

This distinction is mandatory: agents must not collapse architectural ownership, one-consumer migration completion, and repository-wide enforcement into the same status claim.
