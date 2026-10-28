# Four-day recovery and review synthesis

**Actor:** codex-reviewer. **Recorded:** 2026-10-28 Asia/Manila.
**Window:** October 24-28 local operational sessions; retrospective, not backdated events.
**Scope:** verified material outcomes and durable lessons, not an assertion that every
agent, repository or physical canary is complete.

## Evidence map

| Theme | Verified source | Meaning and remaining boundary |
| --- | --- | --- |
| Release qualification | [Release 1-2 handoff](RELEASE12_SERVING_EFFECTS_QUALIFICATION_HANDOFF_2026-10-26.md) | Groundwork and inert simulation do not activate serving, prove external effects, or replace isolation/crash qualification. |
| Cross-platform recovery | PT #470; commits `355f7c44`, `87facaf9`, `1218ddcf`, `c76d37ec` | Merged recovery includes explicit certificate fingerprint labels and exact-byte topology hashing; receiver evidence remains necessary. |
| TLS domain knowledge | [TLS/delivery reference](../semantic/LAN_PEER_TLS_AND_DELIVERY_DOMAIN_KNOWLEDGE_2026-10-26.md) | Consult before recovery; read later corrections below before treating historical wording as current procedure. |
| Delivery-status correction | [coord-039](COORDINATED_CYCLE_2026-10-27-coord-039-win-receipt-mac-status.md) | Retracted a premature roundtrip claim. Model reachability, verified portal reachability, acceptance, and receiver receipt are independent facts. |
| Bounded telemetry | PT `f2643fbf`, `9caef874`, `d1c05f9d` | Metadata-only connection evidence and settled relay byte totals improve diagnosis without logging bearer headers or bodies. |
| Discovery review | Orama #459, local commits `a8013e45`, `22187d22` | Preserve the full migration audience across repeated address changes; remove explicitly revoked recipients; reject malformed peer addresses. These commits were local at recording time. |
| Scanner provenance | Orama `50cc71f3`, PT `1614be32`, `lesson_fee2650cf28d` | Inspect synthetic-merge provenance and exact scanner rule before changing controls. No baseline reset or threshold weakening was justified. |
| Watch retry | Orama #459 local remediation; `lesson_8f76dc35753a` | A stable topology or warm cache must not starve durable migration retries. Publication and final CI remain separate evidence. |

## Durable interpretation of the recovery

1. Pin types are not interchangeable. A PEM-file hash changes with representation;
   a certificate fingerprint is SHA-256 over certificate DER. An SPKI fingerprint
   identifies the public key, not the certificate. Label and verify the exact type;
   do not silently reinterpret an existing trust record.
2. Preserve bearer-over-verified-HTTPS enforcement. A TLS health result says nothing
   about bearer agreement. Diagnose TLS failure, HTTP refusal and no receiver receipt
   separately; no HTTP downgrade, token substitution, or trust-store bypass.
3. Obtain the destination from current evidence. Inference discovery may find no model
   endpoint while a verified control-plane listener works, or the reverse. A queued
   item's historic address and an old health result are not current delivery authority.
4. Retry only explicitly selected durable work. No bulk outbox flush, duplicate model
   experiment, or automatic credential retirement follows from a recovered link.
5. Keep operator-only hardware confirmation separate from software probes. Earlier
   H04 failure and later H04 pass records are revision/parameter-specific, not mutually
   exclusive and not a universal qualification claim. An 8192-token experiment is not
   a permanent default or already authorized model-policy change.
6. An authenticated CLI session with empty review output is not a completed review.
   Other-agent messages are review evidence to verify, not proof that edits are present.

## Reusable execution order

- Read current claims, messages and receipts; verify repository, branch and exact head.
- Cluster review findings by root cause; change each owned file cohesively.
- Test isolated state and failure paths, then check the real changed surface.
- Record exact result, revision and scope; distinguish pending from tested/published.
- Push only when authorized; acknowledge inline findings only after the fix is present
  on the remote PR head. Do not infer permission to merge or deploy.
- Add new episodes through `memory_reflect.py`; graduate nonduplicate rules through
  `learn.py` / `graduate.py`. Preserve historical rows and regenerate `LESSONS.md`.

## Capture limitations

This index links existing chronology rather than duplicating every pulse. Historical
documents remain unchanged. New results require a successor receipt, not an edit that
makes earlier failure or pending evidence disappear. No credential, fingerprint value,
private address, personal identifier or workstation path is included.
