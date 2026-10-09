# Coordinated lockstep pinning protocol

Status: active working-memory record. The durable procedure is in
`docs/plans/2026-10-09-minigraph-compatibility-evidence-plan.md` under
"Coordinated lockstep pinning protocol".

Apply it to the two pairs:

- Perpetua-Tools and Orama-System: pin exact peer revisions and shared
  contract/fixture digests; update both handoffs, the active Orama `docs/v2`
  record, PT evidence, and paired acceptance results.
- Perpetua Core and Oramasys: use a test-only Core candidate overlay until
  Core merges; keep the previous merged Core SHA as the production pin; then
  update the production pin only after full downstream and oracle revalidation.

Every handoff records both heads, candidate or production role, environment and
contract digests, changed authorities, commands and outcomes, CI status,
review-fix SHAs, merge order, and the next promotion or rollback action.

This record qualifies earlier incomplete lockstep descriptions. Preserve those
historical records and link them to this protocol; do not rewrite their claims.

Current qualification: `R3_REGISTRY_REPLAY_REVIEW_2026-10-10.md` records exact
published heads, both candidate profile digests, immutable canonical-docs CI
binding and replay limits. The baseline registry and production Core `04759a5`
remain unchanged. Candidate evidence must never silently promote production.
