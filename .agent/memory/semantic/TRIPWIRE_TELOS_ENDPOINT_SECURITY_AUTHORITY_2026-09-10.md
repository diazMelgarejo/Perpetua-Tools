# Tripwire → Telos endpoint-security authority restoration — 2026-09-10

## Purpose

Preserve the canonical cross-repository decision so future agents do not infer
from the September 2026 Telos scaffold that endpoint security was intentionally
split between a semantic Telos authorizer and independent DNS/dialer
implementations in every consumer.

That split was implementation drift. It did **not** supersede the accepted
2026-08-29 architecture.

## Canonical decision

`oramasys/telos` is the sole reusable **v2 endpoint-security authority** and the
successor to the original Tripwire concept.

Telos owns the complete endpoint-specific security path:

1. endpoint parsing and canonical identity;
2. IP/CIDR/special-use/cloud-metadata classification;
3. SSRF policy;
4. DNS resolution and DNS-rebinding/TOCTOU defense;
5. connection-time IP/socket pinning and peer verification;
6. redirect revalidation;
7. proxy isolation;
8. TLS destination identity, HTTP Host, and SNI preservation;
9. purpose-scoped semantic endpoint-use authorization.

Transport safety and semantic endpoint permission are separate decisions, but
**both belong to Telos**. Neither can substitute for the other.

```text
raw endpoint
    |
    v
Telos canonical EndpointRef
    |
    v
Telos resolution + address evidence
    |
    v
Telos transport admission
    |
    +----> deny if destination/path unsafe
    |
    v
Telos purpose authorization
    |
    +----> deny if endpoint use not permitted
    |
    v
AuthorizedEndpoint
    |
    v
Telos pinned transport / bridge
```

## Why the semantic-only scaffold is not authoritative

The initial September Telos scaffold stated that Telos did not parse URLs,
resolve DNS, classify addresses, pin connections, follow/revalidate redirects,
or execute safe transport. It also placed a caller-supplied `is_public` bit on
`EndpointRef` as trusted evidence.

Those choices contradicted the already accepted 2026-08-29 ownership design and
reintroduced exactly the duplication Tripwire was intended to prevent. They are
therefore treated as implementation mistakes preserved for provenance, not a
new architecture decision.

The restored Telos contract removes caller-supplied public/private authority.
Telos derives classification from its own resolution evidence and produces an
`EndpointIdentity` bound to vetted addresses.

## v1 / v2 regime boundary

This memory does **not** deprecate or weaken PT v1 endpoint security.

PT remains an independent v1 authority inside the v1 regime. Its endpoint
hardening remains native PT code and does not import v2 packages.

Conversely, v2 MUST NOT import, shell out to, discover, or otherwise depend on
PT at runtime. PT provides golden behavior/provenance evidence for the clean-room
Telos reimplementation only.

```text
PT v1
  native endpoint policy / SSRF / pinned transport
  independent runtime authority in v1
        |
        | behavior + decision evidence only
        v
Telos v2 clean-room implementation
  independent v2 runtime authority
```

## PT evidence lineage

The restored v2 design is grounded in real PT implementation and memory rather
than unrelated external citations.

### Endpoint identity and Layer-1 policy

At `diazMelgarejo/Perpetua-Tools@a551da4fa97e5fbc6f908ad077c7b6d8030a3220`:

- `packages/endpoint-policy/` — independently packaged endpoint-policy authority,
  Apache-2.0;
- `src/utils/endpoint_policy_core.py` — endpoint identity reconstruction;
- `src/utils/ssrf_fetch_policy.py` — deny-by-default arbitrary/remote SSRF
  preflight and special-address policy;
- `config/endpoint-policy-contract.yml` — endpoint-policy contract evidence.

### Connection-time authority

- `src/utils/ssrf_pinned_adapter.py` — Layer-2 resolve/validate/pin transport;
- `tests/test_ssrf_pinned_adapter.py` — split NAME/PLACE identity, peer recheck,
  mixed DNS-answer denial, redirect revalidation, pool/pin isolation, and
  concurrency regression evidence;
- `docs/plans/2026-08-21-pt-endpoint-hardening-checklists.md` — Layer 1 + Layer 2
  + operator Layer 3 hardening model.

### PT `.agent` decision evidence

Relevant durable/working evidence includes:

- `.agent/memory/semantic/DECISIONS.md` entries covering the 2026-08-21 pinned
  transport and review remediation;
- `.agent/memory/working/SESSION_SYNTHESIS_SSRF_LAYER2_AND_FRUGAL_PYTHON_REUSE_2026-08-21.md`;
- `.agent/memory/working/2026-08-23-ssrf-split-identity-and-dependency-remediation-session.md`;
- graduated candidate evidence around unsafe caller-supplied sessions,
  redirect handling, and the local-vs-arbitrary-fetch policy split.

These records establish the historical requirement that preflight URL checks
alone do not close DNS-rebinding or redirect SSRF; the actual connection must be
bound to vetted address evidence.

## Accepted 2026-08-29 ownership decision

The accepted architecture assigned **all endpoint-specific security** to Telos
and generic security/safety admission to Phylax. This remains canonical and was
never legitimately superseded.

Steady-state split:

| Owner | Canonical responsibility |
| --- | --- |
| `oramasys/telos` | endpoint identity, SSRF/DNS/rebinding, pinning, redirects/proxy/TLS destination safety, endpoint-use authorization |
| `oramasys/phylax` | generic compile/runtime security and safety admission, integrity/provenance/redaction, generic runtime-check/monitorability mechanisms |
| `oramasys/oramasys` | application/workflow composition, route/budget/effect policy |
| `oramasys/agate` | hardware capability/fit/placement evidence |
| `oramasys/Claude-Desktop-LLM` | Ollama/LM Studio provider protocol, operation, readiness and provider-native observability |
| `oramasys/perpetua-core` | irreducible execution mechanics |

Domain owners may consume Telos. They MUST NOT rebuild Telos endpoint-security
mechanisms locally.

## Current v2 restoration evidence

### Telos

`oramasys/telos` PR #1:

- branch: `2026-09-10-restore-tripwire-endpoint-authority`;
- current restoration/evidence head at memory creation:
  `5c1d341b9b7b18703228dd27c81d5149495b418a`;
- implementation hardening base evidence:
  `aee02988955c6abc181cd24b29e640c8891f928a`;
- 28 tests passed with 91.29% line coverage before the docs-only harmonization;
- project coverage floor is >=80%; stricter component thresholds are binding
  and MUST NOT be lowered;
- Apache-2.0.

Implemented behavior includes canonical endpoint identity/IDNA, all-answer DNS
validation, special-address/metadata denial, semantic/transport separation,
pinned HTTP(S), post-connect peer equality checks, authoritative Host/TLS SNI,
proxy isolation, redirect re-entry, 301/302/303 method/body conversion,
307/308 preservation, cross-origin credential stripping, bounded redirects,
timeouts, and cooperative cancellation boundaries.

Canonical correction record:

- `oramasys/telos/docs/ERRATA-2026-09-10.md`;
- `oramasys/telos/docs/MIGRATION-EVIDENCE.md`.

### Claude-Desktop-LLM consumer transfer

`oramasys/Claude-Desktop-LLM` PR #1:

- branch: `2026-09-10-transfer-endpoint-security-to-telos`;
- final squashed transfer head at memory creation:
  `6a602e8786708dbe62a112360ddde4ba63b8c3ad`;
- the former TypeScript endpoint-policy implementation is retained only as
  historical/parity evidence;
- `guardedFetch()` becomes a compatibility facade over a language-neutral
  Telos JSONL bridge;
- no direct-fetch fallback;
- each provider is scoped to its configured endpoint;
- provider protocol tests inject a deterministic Telos transport double rather
  than reimplement security;
- CI uses Node 22 and enforces >=80% line/function/branch coverage.

The pre-squash verified transfer tree passed `npm ci`, TypeScript build, and the
full Node test/coverage workflow. Exact final-head CI must still be checked
before merge claims; this memory records architecture, not merge readiness.

### Phylax correction

`oramasys/phylax` PR #1:

- branch: `2026-09-10-restore-apache2-telos-boundary`;
- head at memory creation: `cbdded2c556867d3867b2b8b071a333d025737cf`;
- uses the same canonical Apache-2.0 license text as Telos;
- explicitly excludes endpoint-specific security;
- keeps generic security/safety admission only;
- adds >=80% coverage floor while preserving stricter thresholds;
- existing runtime scaffold verified 4/4 tests, 100% line coverage before the
  governance-only correction.

### Orama canonical documentation

`diazMelgarejo/orama-system` PR #351 is the reused documentation/reconciliation
PR. It records that the 2026-08-29 design remains canonical, quarantines the
citation-contaminated “Document 7” as untrusted secondary synthesis, records the
Apache-2.0 correction, and requires the global >=80% coverage floor.

Do not create a competing docs PR for this restoration; continue reconciling
that existing PR until explicitly merged or closed by the owner.

## Oramasys Gateway Lifecycle migration dependency

A second v2 implementation-drift surface was discovered during restoration:

- `oramasys/oramasys/src/orama/gateway/dialer.py` on
  `8ad2574010013d9f5b40b193d316516872462130`.

It was designed under the semantic-only Telos scaffold and currently owns DNS
resolution, special-address classification, public/local admission, and the
connector step. It also contains useful parity vectors not to lose:

- CGNAT `100.64.0.0/10`;
- 6to4 relay anycast `192.88.99.0/24`;
- Teredo `2001::/32`;
- 6to4 `2002::/16`;
- validate every DNS answer before dispatch;
- bounded DNS + connector deadline;
- IPv4-mapped IPv6 handling.

These behaviors are **evidence to absorb/preserve in Telos**, not justification
for a second endpoint-security authority.

A blind dependency bump is unsafe because the Gateway still consumes the
superseded caller-supplied `EndpointRef.is_public` contract. Its migration must
be an explicit consumer-contract rewrite against restored Telos. Oramasys may
retain application/provider-specific purpose/port policy, but DNS,
classification, socket pinning, redirects, proxy/TLS destination safety and
endpoint semantic authorization remain Telos-owned.

## PT PR #382 interpretation

PT PR #382 (`gate4/halfb-dialer-adoption-20260907`) remains valid **inside v1**.
It closes real PT model-server DNS/classification gaps and deliberately uses a
native PT implementation because v1 never imports v2 packages.

Its wording that it mirrors the Oramasys v2 Gateway dialer must be interpreted as
**behavioral parity evidence**, not an ownership statement. The restored v2
owner is Telos. PT's implementation remains native because of the v1/v2 regime
boundary.

## License doctrine

Canonical license policy for this capability family:

```text
oramasys/telos       Apache-2.0
oramasys/phylax      Apache-2.0
oramasys/oramasys    MIT
oramasys/perpetua-core MIT
PT endpoint-policy package (v1 evidence) Apache-2.0
```

The initial MIT Telos/Phylax scaffolds were erroneous and are corrected through
explicit commits/PRs rather than history rewriting.

## Citation/provenance doctrine

Repository-specific architecture claims must be grounded in repository files,
commits, PR/review evidence, PT `.agent` memory, or explicit owner-approved
architecture records.

The Telos/Phylax evolution writeup referred to as “Document 7” is untrusted
secondary synthesis because unrelated external sources were cited as if they
established private repository facts. Do not use it as authority until each
claim is re-grounded. Do not invent the artifact's author, date, or generating
tool when provenance is unknown.

## Agent rules

Future agents working on endpoint security MUST:

1. read this memory before changing endpoint, SSRF, dialer, DNS, redirect,
   proxy, TLS-destination, or endpoint-authorization code;
2. treat Telos as the sole v2 endpoint-security mechanism owner;
3. treat PT v1 implementation as independent v1 runtime code and v2 parity
   evidence only;
4. never reintroduce caller-trusted public/private classification;
5. never add a direct-network fallback around a Telos denial/unavailability;
6. preserve provider/application policy above Telos without copying transport
   security below it;
7. maintain >=80% project coverage, or the higher existing component threshold;
8. verify exact PR head, CI, and review threads before claiming completion;
9. never merge without an explicit owner instruction to merge.

## Retrieval cues

Recall this memory for:

- Tripwire;
- Telos;
- Phylax;
- endpoint-policy;
- SSRF;
- DNS rebinding;
- pinned dialer / socket pinning;
- Host / SNI / TLS destination identity;
- metadata endpoints;
- Claude-Desktop-LLM provider networking;
- Oramasys Gateway Lifecycle dialer;
- PT PR #382;
- v1/v2 regime separation;
- endpoint security ownership;
- Apache-2.0 security satellites;
- citation contamination and architecture provenance.
