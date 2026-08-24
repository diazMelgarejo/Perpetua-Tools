# Layer-3 Egress Enforcement, Observability & Multi-Agent Sentinels

> **Date:** 2026-08-24  
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

---

## 3. Two-Tier Privacy Trust Model

| Sink / Exporter | Privacy Classification | Payload Scope |
| :--- | :--- | :--- |
| **Local Periscope Sink** (`orchestrator/periscope_adapter.py`) | `internal_only` | Writes rich local JSONL (`user_text`, `assistant_text`, `cwd`, `model`) for local desktop viewing. Never exported over network. |
| **Remote OTLP Exporter** (`src/observability/otel_exporter.py`) | `redacted` | Projects to W3C Spans and Log EventRecords via official OpenTelemetry SDK. Prohibits prompts, raw hostnames, raw IPs, credentials, or absolute paths. |

---

## 4. Coordination Bias Sentinel & Amplifier Principle

- **Multi-Agent Evidence:** `CoordinationBiasDetector` tracks `agent_id` in its sliding window and
  requires **minimum 3 distinct logical agents** before triggering `agreement_collapse`.
- **Single-Agent Handling:** Repetitive outputs from a single agent are flagged as
  `echo_loop_detected`, never groupthink.
- **Amplifier Principle:** Sentinel output is strictly advisory (`coordination_risk: low | medium
  | high | insufficient_evidence`). It **never** blocks task claims, cancels approvals, or
  mutates agent state.
