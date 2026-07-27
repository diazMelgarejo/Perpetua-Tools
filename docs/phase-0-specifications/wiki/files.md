# File Nodes

Each row names the file's graph role. "Downstream" means the file that should be
read next when following implementation or review consequences.

| File | Role | Downstream |
| --- | --- | --- |
| [`PATTERN-SYNTHESIS.md`](../PATTERN-SYNTHESIS.md) | Source pattern library for P2P security controls. | [`MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`](../MULTIAGENT-SWARM-SECURITY-ANALYSIS.md), [`DELIVERABLE-4-THREAT-MODEL-REGENERATED.md`](../DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) |
| [`PATTERN-MULTIAGENT-EXECUTION-PLAN.md`](../PATTERN-MULTIAGENT-EXECUTION-PLAN.md) | Execution plan for turning pattern research into deliverables. | [`PHASE-0-TASK-LIST.md`](../PHASE-0-TASK-LIST.md) |
| [`MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`](../MULTIAGENT-SWARM-SECURITY-ANALYSIS.md) | Maps swarm topology to threat categories and gaps. | [`DELIVERABLE-4-THREAT-MODEL-REGENERATED.md`](../DELIVERABLE-4-THREAT-MODEL-REGENERATED.md), [`../../../SECURITY.md`](../../../SECURITY.md) |
| [`DELIVERABLE-1-PEER-OBSERVATION-MODEL-EXPANDED.md`](../DELIVERABLE-1-PEER-OBSERVATION-MODEL-EXPANDED.md) | Expanded schema and confidence design. | [`DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md`](../DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md) |
| [`DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md`](../DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md) | Repaired canonical PeerObservation and multiplicative confidence formula. | [`peer_observation_tdd.md`](../peer_observation_tdd.md), [`2026-07-11-state-transition-manager-integration-plan.md`](../2026-07-11-state-transition-manager-integration-plan.md) |
| [`peer_observation_tdd.md`](../peer_observation_tdd.md) | Test vectors and fixtures for schema, immutability, and scoring. | [`TASK_A2_FINDINGS.md`](../TASK_A2_FINDINGS.md) |
| [`TASK_A2_FINDINGS.md`](../TASK_A2_FINDINGS.md) | Implementation findings for confidence scoring. | [`PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md`](../PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md) |
| [`DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md`](../DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md) | Liveness, timeout, failure detector, and hysteresis contract. | [`2026-07-11-state-transition-manager-integration-plan.md`](../2026-07-11-state-transition-manager-integration-plan.md), [`PHASE-1-SCOPE-DRAFT.md`](../PHASE-1-SCOPE-DRAFT.md) |
| [`DELIVERABLE-4-THREAT-MODEL-REGENERATED.md`](../DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) | Threat model T1-T7. | [`2026-07-12-stm-next-increment-plan.md`](../2026-07-12-stm-next-increment-plan.md), [`security-trace.md`](security-trace.md) |
| [`MEDIUM-ITEMS-DECISION-MATRICES.md`](../MEDIUM-ITEMS-DECISION-MATRICES.md) | Decision matrix for sequence width, ghost peers, STM protection, gates, fallback, eviction, and rate limiting. | [`PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md`](../PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md) |
| [`PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md`](../PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md) | Reconciles conflicting STM model assumptions. | [`2026-07-11-state-transition-manager-integration-plan.md`](../2026-07-11-state-transition-manager-integration-plan.md) |
| [`PHASE-0-TASK-LIST.md`](../PHASE-0-TASK-LIST.md) | Original TDD-first work breakdown, later partly superseded by shipped STM path. | [`PHASE-1-SCOPE-DRAFT.md`](../PHASE-1-SCOPE-DRAFT.md) |
| [`PHASE-1-SCOPE-DRAFT.md`](../PHASE-1-SCOPE-DRAFT.md) | Phase 0 to Phase 1 handoff model. | [`PHASE-2-JOB-BOARD.md`](../PHASE-2-JOB-BOARD.md) |
| [`2026-07-11-phase1b-integration-review.md`](../2026-07-11-phase1b-integration-review.md) | Finds the cross-module integration gap. | [`2026-07-11-state-transition-manager-integration-plan.md`](../2026-07-11-state-transition-manager-integration-plan.md) |
| [`2026-07-11-state-transition-manager-integration-plan.md`](../2026-07-11-state-transition-manager-integration-plan.md) | Central STM integration plan. | [`2026-07-11-pr203-multiagent-orchestration.md`](../2026-07-11-pr203-multiagent-orchestration.md), [`2026-07-12-stm-remediation-plan.md`](../2026-07-12-stm-remediation-plan.md) |
| [`2026-07-11-pr203-multiagent-orchestration.md`](../2026-07-11-pr203-multiagent-orchestration.md) | Assigns PR #203 multi-agent execution. | [`2026-07-11-PR203-BLEND-VERDICT.md`](../2026-07-11-PR203-BLEND-VERDICT.md) |
| [`2026-07-11-PR203-BLEND-VERDICT.md`](../2026-07-11-PR203-BLEND-VERDICT.md) | Reconciles competing PR #203 lineages. | [`README-PR203-BLEND.md`](../README-PR203-BLEND.md) |
| [`README-PR203-BLEND.md`](../README-PR203-BLEND.md) | Agent navigator for the blend strategy. | [`2026-07-11-PHASE-2-BLOCKERS.md`](../2026-07-11-PHASE-2-BLOCKERS.md) |
| [`2026-07-11-PHASE-2-BLOCKERS.md`](../2026-07-11-PHASE-2-BLOCKERS.md) | Deferred concurrency and dedup blockers. | [`2026-07-12-autoplan-final-approval-gate.md`](../2026-07-12-autoplan-final-approval-gate.md) |
| [`2026-07-12-autoplan-final-approval-gate.md`](../2026-07-12-autoplan-final-approval-gate.md) | Final approval gate for PR #205. | [`2026-07-12-stm-next-increment-plan.md`](../2026-07-12-stm-next-increment-plan.md) |
| [`2026-07-12-stm-remediation-plan.md`](../2026-07-12-stm-remediation-plan.md) | Short remediation plan for production wiring and threat re-check. | [`2026-07-12-stm-next-increment-plan.md`](../2026-07-12-stm-next-increment-plan.md) |
| [`2026-07-12-stm-next-increment-plan.md`](../2026-07-12-stm-next-increment-plan.md) | Closed plan for next STM increment and P5/P6/P13 hardening gate. | [`docs/next`](../../next/README.md), [`../../../SECURITY.md`](../../../SECURITY.md) |
| Review voice folders | CEO and engineering evidence packs, with stale/false claims preserved and annotated. | [`2026-07-12-autoplan-final-approval-gate.md`](../2026-07-12-autoplan-final-approval-gate.md) |
