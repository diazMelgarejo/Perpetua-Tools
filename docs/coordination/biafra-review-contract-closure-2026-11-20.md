# Biafra review contract closure — 2026-11-20

This ledger follows Orama's contract-migration method. PT owns spending and
coordination state; Orama consumes those contracts. Source verification does
not authorize provider requests, queue cleanup, deployment or serving.

| Layer | Previous contract | Repair and proving evidence |
| --- | --- | --- |
| Persistence | Expired holds could be swept after both settlement attempts failed. Legacy JSON could be renamed before its import transaction survived. | SpendGate creates durable uncertain holds before dispatch. Old SQLite reservations and retained swept entries migrate conservatively to uncertain holds. Schema/import commits independently before a refusing operation; post-commit archive completion is retryable. Fresh, populated, crash and two-instance tests cover the boundary. |
| Contract | Preflight used a policy output estimate regardless of the actual requested limit. | Optional positive `max_tokens` reserves at least the declared estimated output. Existing two-argument callers remain compatible. Expired uncertain holds produce `spend-reconciliation-required`, `ok=false`, `stop=true`; unexpected failures propagate. |
| Callers | The PT worker request forwarded an output limit that admission ignored. | Harness forwards the same limit into admission. Orama's adapter accepts the optional limit; its governed live launcher refuses before reservation until an aggregate output/request boundary is proved. |
| Transport | The generic OpenAI endpoint could target W&B without admission. | Existing endpoint-policy parsing refuses that bypass before client creation. No new provider, identity parser or alternate paid route is added. |
| Lifecycle | A sent request could become unaccounted after hold expiry. | Unresolved holds survive expiry/restart; settlement or an evidence-based explicit release is required. A successful charge followed by audit failure does not charge twice. Known-unsent startup failure releases its hold. |
| Operations | A guard with the wrong period could change a shared ceiling. | `set_budget` rejects mismatched periods without changing spend or ceiling. No automatic reconciliation invents billing evidence. |

## Compatibility and rollback

An uncertain hold is accounting evidence, not proof of a provider charge. It is
retained conservatively until its owner reconciles the outcome. Older runtime
code can sweep these holds, so do not roll back to an implementation that ignores
the new column while unresolved holds remain. Already-forgotten old swept entries
cannot be reconstructed from this migration. No intermediate candidate was
authorized for production.

Legacy coordination recovery is a separate contract described in the
[L-1r ledger](l1r-contract-migration-2026-11-20.md). Heartbeat silence does not
establish worker termination. The hold prevents replacement ownership; it does
not stop an existing worker or fence external effects. The private authority,
generation fencing and actual-host qualification remain separate unfinished work.

## Memory corrections

The original spend lesson remains in history. Native graduation appends an
accepted superseding lesson distinguishing provider errors from successful
responses. A mistakenly duplicated new lesson was subsequently retracted through
the native correction tool. Rendering and recall use the current semantic state.
Graduation now propagates supersession metadata to its candidate on first run
and retry; retries retain the first semantic decision. Historical candidate
snapshots are preserved.

The episodic byte-prefix gate, memory record validator and actual candidate
presence tests must pass before publication. PT #517 is replayed only after
this #516 repair is complete; its independent historical appends require a
three-way union with full provenance, not replacement of either side.
