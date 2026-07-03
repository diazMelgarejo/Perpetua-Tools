# perpetua-endpoint-policy

Shared endpoint/URL **egress policy** for local/LAN model servers (LM Studio,
Ollama, Win coder pool). One invariant, one error type:

> A model endpoint is either a valid, normalized string, or a single
> `ModelEndpointPolicyError`. No raw URL-parsing exception escapes the policy layer.

Default-allow: loopback + RFC1918 private hosts (these are *local model
endpoints* — the inverse stance of a public-web SSRF blocker). Blocked always:
link-local `169.254.0.0/16` (cloud metadata SSRF, e.g. `169.254.169.254`),
including IPv4-mapped-IPv6 bypass forms (`[::ffff:169.254.169.254]`, cf.
CVE-2026-26324). Public hosts require the explicit
`ALLOW_PUBLIC_MODEL_ENDPOINTS=1` opt-in or `allow_public=True`.

```python
from endpoint_policy import validate_model_endpoint_url, ModelEndpointPolicyError

validate_model_endpoint_url("localhost:1234")            # -> "http://localhost:1234"
validate_model_endpoint_url("http://gpu:notaport")       # raises ModelEndpointPolicyError
validate_model_endpoint_url("http://169.254.169.254")    # raises ModelEndpointPolicyError
```

## Provenance & ownership

Authored in Perpetua-Tools (`packages/endpoint-policy/`, coord-023) by porting
the cross-repo parity-checked mirror `src/utils/model_endpoint_url.py` —
**behavior-identical, not re-derived**. Until consumers cut over (publish
time), the mirror remains the runtime source of truth; this package must be
kept in lockstep with it. Apache-2.0 (own LICENSE/NOTICE; host repo is
AGPL-3.0 — see NOTICE for the license-bleed guard).

Peer contract: orama-system `.agent/endpoint-policy-contract.yml` ·
`AGENTS.md § Endpoint transport policy` in both repos.
