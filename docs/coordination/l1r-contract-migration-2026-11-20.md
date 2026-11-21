# L-1r pre-generation cleanup contract — 2026-11-20

This source candidate changes the historical manual-cleanup characterization.
It does not authorize a live cleanup or replace the planned private authority.
The accepted review amendment requires a hold or refusal where the old worker
cannot be fenced. An `agent_killed` gossip event is not verified process-death
evidence, and this runtime has no supported proof-bearing operator release API.

| Layer | Before | Candidate and evidence |
| --- | --- | --- |
| Persistence | Cleanup could append `agent_release` or remove a `task_claims` row and append `task_failed`. | Both automatic release helpers hold; no release event or row deletion is made. Existing L-1a transactional queue primitive remains in place for other callers. |
| Contract | DEAD classification could result in release. | Classification and scoring are unchanged; release returns an empty result, even after an `agent_killed` event. A missing heartbeat is not a process fence. |
| Callers | Manual heartbeat cleanup, direct queue cleanup, capture/release helper, and legacy helper could release. | The same names remain; both release routes hold. The CLI reports `no stale claims released`. Historical script shims continue to use the same handler. |
| Transport | Gossip may provide heartbeats and kill events. | Neither event proves termination; no new transport or authority is introduced. |
| Lifecycle | A silent worker could resume after another worker reclaimed its task. | A process-level test pauses a live worker while its heartbeat is scored DEAD, verifies same-name and different-name reclaim both lose, and resumes it. Its completion and external effect still occur, showing that this hold is not an execution or external-effect fence. |
| Operations | Manual cleanup could recover capacity based on liveness. | Claims remain unavailable pending a future fenced recovery or separately supported, verified process-termination procedure. No such procedure is introduced here; restart and worker quiescence requirements remain. |

The real-process test uses a controlled parent clock on POSIX. Native Windows
qualification and the generation-backed schedule remain outstanding. The new
private authority, admission, protected-writer closure, deployment and rollback
are outside this bounded change. Existing L-1a safety checks do not prove a
silent process has stopped. No claim is made that the preliminary hold fences
external effects or covers old binaries.
