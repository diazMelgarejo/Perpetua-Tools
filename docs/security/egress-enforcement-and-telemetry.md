# Layer-3 Egress Enforcement, Observability & Multi-Agent Sentinels

> **Date:** 2026-08-25  
> **Status:** Operational Runbook & Production Reference  
> **Target Repositories:** [`Perpetua-Tools`](https://github.com/diazMelgarejo/Perpetua-Tools) ·
> [`orama-system`](https://github.com/diazMelgarejo/orama-system)  

---

## 1. Physical Layer-3 Egress Enforcement (macOS `pf`)

Perpetua-Tools enforces an interface-independent Layer-3 network egress floor on macOS to block
any SSRF exfiltration to cloud instance metadata services (AWS IMDS, ECS task metadata, IPv6
metadata, link-local):

```text
block drop out quick to 169.254.0.0/16
block drop out quick to 169.254.169.254
block drop out quick to fd00:ec2::254
block drop out quick to fe80::/10
```

### Verification Command

Run the verification script anytime to assert packet filter active status, loaded anchor
equality, and rule ordering priority:

```bash
bash scripts/security/verify-egress-pf-rules.sh --json
```

**Expected JSON Response:**

```json
{
  "layer": "pf-egress",
  "status": "ok",
  "anchor": "com.perpetua-tools.egress-deny",
  "rules_count": 4
}
```

---

## 2. Telemetry Cardinality & Domain Observations

Perpetua-Tools implements a strict **Core + Planes + Adapters** model via Pydantic v2
discriminated union `DomainObservation`:

```python
from src.observability.core import (
    DomainObservation,
    EgressCompleteObservation,
    EgressValidationObservation,
)
```

### Telemetry Events

1. **`egress.validation`:** Emitted per DNS/socket validation hop by `SSRFPinnedHTTPAdapter`.
   Records `validation_ms`, `destination_hash`, `outcome`, `deny_reason`.
2. **`egress.request.complete`:** Emitted exactly once per logical bridge request by
   `orchestrator/orama_bridge.py`. Records `duration_ms`, `status_code`, `destination_hash`.
3. **`task.lifecycle`:** Emitted on queue state changes (`enqueued`, `claimed`, `completed`,
   `failed`, `abandoned`).
4. **`coordination.bias_advisory`:** Emitted by `CoordinationBiasDetector`.

### Runtime OTLP Producer

The canonical egress telemetry `emit()` path remains the single producer boundary. After its
local redacted JSONL write, it hands the same `EgressEvent` to
`src/observability/runtime.py`, which constructs a typed redacted observation and submits it
through the existing OTLP exporter when an endpoint and optional OTel dependencies are present.

Important runtime rules:

- conversion consumes `EgressEvent.to_redacted_dict()` rather than raw host/IP fields;
- remote events map to `pinned_requests`; local bridge events map to `local_http`;
- exporter failure never fails the originating PT request;
- Collector connection events remain in the local redacted sink but are not re-exported,
  preventing telemetry-of-telemetry recursion;
- no request correlation identifier is synthesized because `EgressEvent` does not currently
  define one; adding that field requires a separate contract migration.

---

## 3. Two-Tier Privacy Trust Model

| Sink / Exporter | Privacy Classification | Payload Scope |
| :--- | :--- | :--- |
| **Local Periscope Sink** (`orchestrator/periscope_adapter.py`) | `internal_only` | Writes rich local JSONL (`user_text`, `assistant_text`, `cwd`, `model`) for local desktop viewing. Never exported over network. |
| **Remote OTLP Exporter** (`src/observability/otel_exporter.py`) | `redacted` | Projects to W3C Spans via official OpenTelemetry SDK. Prohibits prompts, raw hostnames, raw IPs, credentials, or absolute paths. |

`internal_only` observations are rejected before provider configuration or transport work. The
runtime egress bridge only constructs `redacted` observations from the canonical redacted event
projection.

---

## 4. Coordination Bias Sentinel & Amplifier Principle

- **Multi-Agent Evidence:** `CoordinationBiasDetector` tracks `agent_id` in its sliding window and
  requires **minimum 3 distinct logical agents** before triggering `agreement_collapse`.
- **Single-Agent Handling:** Repetitive outputs from a single agent are flagged as
  `echo_loop_detected`, never groupthink.
- **Amplifier Principle:** Sentinel output is strictly advisory (`coordination_risk: low | medium
  | high | insufficient_evidence`). It **never** blocks task claims, cancels approvals, or
  mutates agent state.

---

## 5. OTLP Runtime Lifecycle

Remote export is opt-in. Install the optional dependency group and configure an HTTPS trace
endpoint outside git:

```bash
uv sync --extra otel
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://otel-collector.example.com:4318/v1/traces"
```

For a private CA only:

```bash
export REQUESTS_CA_BUNDLE="/secure/operator-owned/collector-ca.pem"
```

The initial Collector must resolve only to addresses allowed by PT's existing global-destination
policy. Private exposure is achieved with ingress firewall/security-group restrictions, not by
weakening PT to allow RFC1918, CGNAT/Tailscale, WireGuard-private, ULA, or link-local addresses.

PT configures the exporter lazily on the first real runtime egress event (or explicitly through
the smoke command), once per process. At process exit it force-flushes buffered spans. PT only
calls provider `shutdown()` when PT created that provider; a provider installed by another
runtime is borrowed and is never terminated by PT.

---

## 6. Deterministic OTLP Smoke

The operator smoke command accepts no arbitrary destination, prompt, path, or user-text input:

```bash
python -m src.observability.smoke
```

A successful run returns JSON indicating that the exporter was configured, a synthetic redacted
observation was constructed and submitted, the provider was explicitly flushed, and an
`internal_only` negative control was rejected.

The smoke command proves PT submission and flush behavior. A real Collector rollout additionally
requires Collector-side evidence that the span arrived and that forbidden raw values are absent.

---

## 7. Per-Host Promotion Gates

Promote one macOS host at a time.

1. **Topology:** resolve the Collector DNS name and confirm every returned address is allowed by
   current PT egress policy.
2. **PF enforcement:** run `scripts/security/verify-egress-pf-rules.sh --json`; require exit 0 and
   `status="ok"`.
3. **TLS/SNI:** verify the Collector certificate independently with `openssl s_client`; do not use
   an arbitrary `GET /` as the OTLP TLS acceptance test.
4. **PT transport smoke:** run `python -m src.observability.smoke` with the configured HTTPS OTLP
   endpoint and require configured/submitted/flushed success.
5. **Collector proof:** during rollout, use the Collector debug exporter to confirm the expected
   safe attributes and absence of raw host/IP/prompt/secret/path data.
6. **Periscope local proof:** set `PERISCOPE_EMITTER_ENABLED=1`, configure Periscope `openclaw_dirs`
   to include the PT-owned trajectory root, emit a harmless local trajectory, and verify that the
   rich content remains local and absent from Collector output.
7. **CI:** require Python 3.11 and 3.12 suites plus security and repository invariants to be green
   on the exact promoted commit.

Do not claim host rollout complete from CI alone. PF, DNS, TLS, the real Collector receipt, and
Periscope discovery are host/operator evidence and must be verified on each actual Mac.
