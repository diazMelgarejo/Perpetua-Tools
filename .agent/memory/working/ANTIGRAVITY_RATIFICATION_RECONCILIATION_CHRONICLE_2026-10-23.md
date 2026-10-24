# AntiGravity Verification Chronicle: Signing & Replay Ratification Reconciliation

Date: 2026-10-23
Author: agnes-antigravity-gemini
Status: committed_to_branch; review evidence only; ORAMA_GRANT_SERVING strictly unset.
Branch: `cursor/model-governance-align-574b` (Perpetua-Tools PR #422)
Base: `9514ea65`

## 1. Context & Background

Following the completion and operator merges of Milestone 2 (Phylax PR #17, Oramasys PR #71, Orama PR #432/433/434), active coordination shifted to Model Governance (PR #381 / PR #422) and the question of single-use escalation tokens (GossipBus Row 5578).

Initial discussion on the board temporarily considered implementing a bespoke `jti` (UUIDv4) claim and an ad-hoc SQLite consumption table with novel TTL tiers. AntiGravity, Claude, and Codex conducted an exhaustive cross-reference across `docs/v2`, repo references, and PT `.agent/memory`.

## 2. Key Architectural Confirmations

1. **Three Distinct, Non-Interchangeable Cryptographic Boundaries**:
   - **Boundary 1: P5 Human Approval Receipt (`p5_approval.py`)**: Authenticates operator intent for an exact protected action. Consumed atomically via `SqliteP5ApprovalStore.consume` using `BEGIN IMMEDIATE` under write lock. 300-second preview/receipt window.
   - **Boundary 2: Adjustment-Grant Attestation (`adjustment_grant.py`)**: Issued by `PhylaxGrantAuthority` only after consuming a valid P5 receipt. RFC 8032 Ed25519ph over `b"phylax-adjustment-grant-v1\x00"` + RFC 8785 JCS body. Verified seed-free in serving process with revocation freshness `< 60s`. Consumed transactionally in Oramasys `StepLedger`.
   - **Boundary 3: E1 Dispatch Permits & Finalizations (`dispatch_permit_store.py`)**: Port-injected `IssuerSigner` over `b"phylax-issuer-event-v1\x00"`.
2. **Prior Ratifications Already Locked**:
   - **Single-Use Invariant**: Ratified in Durable HITL Contract §2 ("use limit: exactly one; multi-use grants are not defined") and ADR 71.
   - **No New JTI Scheme Required**: Server-minted opaque IDs (`preview_id`, `approval_id`, `grant_id`, `run_id`) supply unique identity.
   - **Two-Clock Authority Model**: Automated window = 300s execution; human adjustment grant = 5,400s execution (ceiling 9,900s). Clock origin begins at durable dispatch authorization transaction, never at first provider output.
   - **Shared-Bearer Principal**: Identifies the control-plane capability principal, not individual human identity. True human review requires external out-of-band P5 evidence.

## 3. Governance Integration Blueprint

- Do not implement process-local token tables or duplicate signers.
- Model-launch escalations map to a P5 approval intent binding `(task_id, model_id, effort, fast, budget_cap)`.
- The P5 store is the authoritative single-use ledger.
- Local governance commits (`8f0ca41e` Grok 4.7, `4240d5d2` Astra ban) verified clean.
