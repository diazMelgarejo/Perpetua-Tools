# Coordination Board — Tripwire → Telos Restoration — 2026-09-10

> **READ FIRST:** `.agent/memory/semantic/TRIPWIRE_TELOS_ENDPOINT_SECURITY_AUTHORITY_2026-09-10.md`
>
> That semantic memory is the durable architecture rule. This board is the
> execution/status projection for cross-agent coordination.

## Mission

Restore and preserve the accepted 2026-08-29 architecture: Telos is the sole
reusable v2 endpoint-security authority succeeding Tripwire. Eliminate
semantic-only Telos interpretations and permanent consumer-owned secure
connectors without breaking the v1/v2 regime boundary.

## Canonical ownership

| Repository / owner | Authority |
| --- | --- |
| `oramasys/telos` | **ALL endpoint-specific security**: identity, SSRF/address policy, DNS/rebinding, pinning, redirect/proxy/TLS destination safety, endpoint-use authorization |
| `oramasys/phylax` | generic security/safety admission, provenance/integrity/redaction, generic runtime-check and monitorability substrate |
| `oramasys/oramasys` | application/workflow composition, provider-purpose/port policy, route/budget/effect policy |
| `oramasys/Claude-Desktop-LLM` | Ollama/LM Studio protocol, lifecycle, readiness, provider-native observability; **consumer of Telos** |
| `oramasys/agate` | hardware capability, fit, placement evidence |
| `oramasys/perpetua-core` | irreducible execution mechanics |
| PT v1 | independent v1 endpoint security in its own regime; parity/provenance evidence for v2 only |

## Current restoration PRs

| Repo | PR / branch | Current head recorded by this board | Status / action |
| --- | --- | --- | --- |
| `oramasys/telos` | PR #1 / `2026-09-10-restore-tripwire-endpoint-authority` | `5c1d341b9b7b18703228dd27c81d5149495b418a` | full Tripwire/Telos implementation + harmonized evidence/errata; do not merge without owner command |
| `oramasys/Claude-Desktop-LLM` | PR #1 / `2026-09-10-transfer-endpoint-security-to-telos` | `6a602e8786708dbe62a112360ddde4ba63b8c3ad` | local secure connector transferred to Telos bridge; exact-head CI success |
| `oramasys/phylax` | PR #1 / `2026-09-10-restore-apache2-telos-boundary` | `cbdded2c556867d3867b2b8b071a333d025737cf` | Apache-2.0 + explicit Telos endpoint exclusion; runtime code unchanged |
| `diazMelgarejo/orama-system` | PR #351 / `docs/v2-audit-migration-harmonization-20260909` | re-fetch before edits | reused canonical docs/errata PR; never create a competing restoration docs PR |
| `diazMelgarejo/Perpetua-Tools` | PR #382 / `gate4/halfb-dialer-adoption-20260907` | this board's containing PR head | v1 dialer parity + durable restoration memory; v1 remains independent |

## Implemented Telos parity contract

The restored Telos branch includes:

- normalized `EndpointRef` without caller-trusted `is_public`;
- Telos-produced `EndpointIdentity` bound to vetted addresses;
- all-answer DNS validation and fail-closed mixed trust classes;
- loopback/private/link-local/multicast/unspecified/special-use/metadata handling;
- IPv4-mapped IPv6 normalization;
- public HTTPS policy where configured;
- purpose semantic authorization distinct from transport admission;
- pinned HTTP(S) connection to vetted IP;
- post-connect peer equality verification;
- authoritative HTTP Host and TLS SNI identity;
- direct transport that does not honor environment proxies;
- redirect re-entry through identity/resolution/transport/semantic policy;
- 301/302/303 → GET + body drop;
- 307/308 method/body preservation;
- cross-origin Authorization/Cookie/Proxy-Authorization stripping;
- bounded redirects, timeouts, and cooperative cancellation boundaries;
- language-neutral JSONL bridge for non-Python consumers.

Verification before docs-only harmonization: **28 passing tests, 91.29% line
coverage**. Project floor is >=80%; stricter component thresholds are binding
and MUST NOT be lowered.

## Claude consumer-transfer rule

`Claude-Desktop-LLM/src/policy/endpoint-policy.ts` is now only a compatibility
facade. Endpoint-security execution goes through `TelosBridgeClient` /
`python -m telos.bridge`.

Rules:

- no direct-fetch fallback;
- each provider is restricted to its configured `baseUrl` as an allowed
  endpoint;
- remote opt-in/host lists are operator intent passed to Telos;
- provider protocol tests may inject a deterministic Telos transport double,
  but production must not inject a policy-bypassing connector;
- Node 22 CI enforces >=80% line/function/branch coverage.

Exact-head `6a602e8786708dbe62a112360ddde4ba63b8c3ad` CI: **success**.

## Phylax correction rule

Phylax uses Apache-2.0 and explicitly excludes:

- URL parsing/canonicalization;
- SSRF/IP classification;
- DNS resolution/rebinding protection;
- pinning/dialer/socket behavior;
- redirect/proxy/TLS destination policy;
- endpoint semantic authorization.

All of those belong to Telos. Phylax retains generic security/safety admission,
provenance/integrity/redaction, and generic runtime-check/monitorability
mechanisms.

## PT PR #382 interpretation

PT PR #382 remains valid v1 hardening. Its native DNS/classification checks are
required because v1 never imports v2 packages.

Do **not** interpret its parity with the Oramasys Gateway dialer as granting PT
or Oramasys steady-state v2 endpoint-security authority. In v2, the owner is
Telos.

## Oramasys Gateway Lifecycle migration dependency

Current source:

`oramasys/oramasys/src/orama/gateway/dialer.py`

Current behavior contains valuable parity vectors but was designed under the
wrong semantic-only Telos scaffold. It still owns DNS/classification/connector
logic and consumes caller-supplied `EndpointRef.is_public`.

### Preserve as parity evidence

- CGNAT `100.64.0.0/10`;
- 6to4 relay anycast `192.88.99.0/24`;
- Teredo `2001::/32`;
- 6to4 `2002::/16`;
- validate every A/AAAA answer;
- bounded DNS + connector timeout;
- IPv4-mapped IPv6 handling.

### Migration constraint

Do not merely bump the Telos dependency SHA. The restored Telos contract removes
caller-trusted `EndpointRef.is_public`, so Gateway Lifecycle requires an
explicit consumer-contract rewrite. Oramasys may retain provider/application
purpose + port policy. DNS/classification/socket-pinning must move behind Telos.

## License policy

```text
oramasys/telos          Apache-2.0
oramasys/phylax         Apache-2.0
PT endpoint-policy      Apache-2.0 (v1 evidence/runtime in v1)
oramasys/oramasys       MIT
oramasys/perpetua-core  MIT
Claude-Desktop-LLM      MIT consumer
```

## Citation / evidence policy

Architecture claims MUST cite repository files, commits, PR/review evidence, PT
`.agent` memory, or explicit owner-approved decisions.

“Document 7” is untrusted secondary synthesis due to citation contamination.
Do not use unrelated external citations to establish private repository facts.
Do not invent unknown author/date/tool provenance.

## Hard agent rules

1. **Never reimplement a secure connector outside Telos in v2.**
2. **Never add a direct network fallback when Telos is unavailable or denies.**
3. **Never restore caller-supplied `is_public` as authorization evidence.**
4. **Never make PT v1 depend on Telos or another v2 package.**
5. **Never make Telos depend on PT v1 at runtime.**
6. Keep application/provider semantics with their domain owner; use Telos for
   endpoint-security mechanism/decision.
7. Maintain >=80% project coverage; preserve every higher component threshold.
8. Verify exact PR head + CI + review threads before completion claims.
9. Fix all live review findings in cohesive batches; re-sweep after push.
10. **Never merge unless the owner explicitly says merge.**

## Dependency / execution order

1. Keep Telos PR #1 as the canonical implementation target.
2. Keep Phylax PR #1 aligned to Telos exclusion/license governance.
3. Keep Claude PR #1 as the reference non-Python consumer pattern.
4. Rewrite the Oramasys Gateway dialer as a Telos consumer without losing its
   application-specific port/purpose constraints or parity vectors.
5. Reconcile Orama PR #351 with exact final heads and migration status.
6. Keep this PT semantic memory and board cross-linked to the exact evidence.
7. Human reviews and explicitly authorizes merges; agents do not merge.

## Durable memory link

Canonical memory path:

`.agent/memory/semantic/TRIPWIRE_TELOS_ENDPOINT_SECURITY_AUTHORITY_2026-09-10.md`

GitHub branch link:

`https://github.com/diazMelgarejo/Perpetua-Tools/blob/gate4/halfb-dialer-adoption-20260907/.agent/memory/semantic/TRIPWIRE_TELOS_ENDPOINT_SECURITY_AUTHORITY_2026-09-10.md`

If the branch/PR is later merged, prefer the merged-main location. Until then,
verify PR #382's current head before relying on transient status fields in this
board; the semantic ownership rule itself is durable.
