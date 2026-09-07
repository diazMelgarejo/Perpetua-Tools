# Gate 4 Endpoint Capability Handoff

**Status:** local commits only; awaiting Claude review before any push.

## Scope And Boundary

This handoff records a v2-only Gate 4 transport-capability follow-up in
`oramasys/oramasys`. Per the v1/v2 regime boundary, Perpetua-Tools receives
memory and contract-surface observations only; it receives no implementation
change from this work.

## What Happened

1. A Cline review of the Gate 4 dialer identified an F07 residual risk: after
   DNS classification, the connector could use an arbitrary scheme and port
   if Telos authorization was over-broad.
2. The board's F07 follow-up initially could not be claimed because its
   completed dependency had been left in `queued` state. Completion was
   verified from the published source commit and test evidence before the
   stale queue record was reconciled; no implementation status was inferred
   from liveness alone.
3. The implementation used a fresh worktree at the verified Gate 4 PR source.
   It is a local follow-up commit, separate from the already-published Half A
   remediation.

## Recent Chronology

| Sequence | Verified outcome |
| --- | --- |
| Gate 1 and lifecycle repair | The canonical Telos endpoint contract and lifecycle cancellation repair became the stacked base for Gate 4. |
| Gate 4 Half A | The dedicated resolver-aware dialer was reviewed for DNS classification, public opt-in, decision expiry, and redacted lifecycle observability. |
| Independent review | Cline identified seventeen findings; the major and bounded minor fixes were consolidated into the reviewed Half A source, including IPv6 loopback and mixed-family regressions found during review. |
| F07 fast follow | This follow-up converts the documented transport/port residual risk into an explicit, tested capability floor. |
| PT hotfix lineage | The existing PT hotfix branch incorporated the health-route and Windows endpoint-failover work plus the reviewed ECC synchronization lineage. This handoff adds no v1 runtime behavior. |
| Memory maintenance | A generated proactive-recall row briefly blocked a fast-forward. The subsequent rebase retained both the upstream records and the new record, confirming the conflict was an ordinary append collision rather than lost work. |

## Evidence-Backed Endpoint Classes

| Class | Gate 4 treatment | Reason |
| --- | --- | --- |
| Ollama | `http:11434` | Documented local model-server convention. |
| LM Studio | `http:1234` | Documented local model-server convention. |
| OpenClaw control gateway | `http:18789` | Documented gateway endpoint; distinct from model-server APIs. |
| TLS model-server reverse proxy | `https:443`, explicit public opt-in | Narrow documented remote/TLS convention for the model-server providers. |
| MLX | excluded | `http:8081` exists in v1 configuration, but MLX is not yet a Gate 4 lifecycle provider. |
| Paid online LLM APIs | excluded | Model egress has a separate accounting and approval gate. |

## Implementation Decision

The v2 dial request now carries a provider kind. The dialer enforces both:

1. a purpose-keyed allowlist of transport-port pairs; and
2. a provider-keyed allowlist that prevents cross-provider port confusion.

The lifecycle fixture that uses port `18789` is now explicitly
`openclaw_gateway`, rather than incorrectly labelling the OpenClaw control
gateway as Ollama. Arbitrary TCP targets and non-TCP schemes fail before DNS
resolution; TLS `443` remains available only to the model-server providers
and only after the existing explicit-public policy check.

Telos remains the sole authorization authority for the exact endpoint and
purpose. The dialer transport floor is defense in depth, not a competing
policy store. New providers or non-default ports require an explicit lifecycle
contract change plus tests; they must not be added as generic TCP exceptions.

## Validation

- Gate 4 full suite: 67 passing tests.
- Tests cover accepted provider-port pairs, cross-provider port rejection,
  arbitrary TCP-port rejection, UDP rejection, no DNS/connector invocation
  after capability denial, and lifecycle fail-closed behavior.
- Diff whitespace check passed before the local commit.

## Local Review Set

| Repository | Branch | Commit | Role |
| --- | --- | --- | --- |
| `oramasys/oramasys` | `fix/gate4-f07-port-allowlist-20260907` | `0ccc87f` | Gate 4 F07 implementation. |
| `Perpetua-Tools` | `hotfix/health-route-ssrf-gap-20260907` | pending | This memory handoff and episodic record only. |

## Review Questions For Claude

1. Does `openclaw_gateway` accurately represent the existing Gateway Lifecycle
   contract, or should it become a separately named lifecycle in a later v2
   slice while retaining the port evidence here?
2. Is `https:443` appropriate for explicitly opted-in remote Ollama/LM Studio
   reverse proxies, or should Gate 4 stay strictly local HTTP until a TLS
   provider contract is introduced?
3. Does the explicit two-layer allowlist remain the narrowest durable defense
   against an over-broad Telos rule while preserving Telos as authorization
   authority?

## Operational Lessons

- Queue state must be reconciled against commits and validation evidence, not
  inferred from an agent heartbeat or task label.
- Memory rebases can create append-versus-append JSONL conflicts. Union all
  valid rows in chronological order; never select one side and discard the
  other.
- A port alone is not a sufficient capability. Pair it with transport and
  provider identity so a control-plane endpoint cannot be silently treated as
  a model-server endpoint.
