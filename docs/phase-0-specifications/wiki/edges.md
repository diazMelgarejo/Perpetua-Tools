# Node-Edge Relationships

Use this page when an agent needs to traverse the folder as a graph instead of
as a date-sorted list.

| Source | Relation | Target |
| --- | --- | --- |
| `PATTERN-SYNTHESIS.md` | extracts | P2P security controls |
| P2P security controls | instantiate as | PeerObservation, witness quorum, replay dedup, bounded caches |
| `PATTERN-SYNTHESIS.md` | feeds | `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md` |
| `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md` | maps | swarm topology to threat analogues |
| `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md` | informs | `DELIVERABLE-4-THREAT-MODEL-REGENERATED.md` |
| `DELIVERABLE-1-PEER-OBSERVATION-MODEL-EXPANDED.md` | superseded-by | `DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md` |
| `DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md` | defines | PeerObservation |
| `DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md` | defines | confidence scoring |
| `peer_observation_tdd.md` | tests | PeerObservation and confidence scoring |
| `TASK_A2_FINDINGS.md` | reports | confidence implementation status |
| confidence scoring | inputs | StateTransitionManager |
| `DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md` | defines | liveness and hysteresis |
| liveness and hysteresis | inputs | StateTransitionManager |
| `DELIVERABLE-4-THREAT-MODEL-REGENERATED.md` | defines | T1-T7 threat controls |
| T1-T7 threat controls | gate | StateTransitionManager hardening |
| `MEDIUM-ITEMS-DECISION-MATRICES.md` | decides | sequence width, ghost peers, STM interface, checkpoint gate, fallback, eviction, rate limiting |
| `PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md` | reconciles | STM model conflicts |
| `2026-07-11-phase1b-integration-review.md` | finds | zero-production-caller integration gap |
| zero-production-caller integration gap | motivates | `2026-07-11-state-transition-manager-integration-plan.md` |
| `2026-07-11-state-transition-manager-integration-plan.md` | centralizes | peer observation, liveness, quorum, replay, audit |
| `2026-07-11-pr203-multiagent-orchestration.md` | assigns | multi-agent implementation work |
| `2026-07-11-PR203-BLEND-VERDICT.md` | resolves | competing PR #203 patch lineages |
| `README-PR203-BLEND.md` | navigates | PR #203 blend context |
| `2026-07-11-PHASE-2-BLOCKERS.md` | defers | bounded observation dedup and async concurrency model |
| CEO quad-review folder | challenges | threat-model premise and build-vs-adopt risk |
| Engineering review folders | verify | bounded structures, dead branches, production wiring, stale claims |
| `2026-07-12-autoplan-final-approval-gate.md` | aggregates | CEO and engineering review voices |
| `2026-07-12-stm-remediation-plan.md` | narrows | production wiring plus threat-model re-check |
| `2026-07-12-stm-next-increment-plan.md` | closes | next STM increment and P5/P6/P13 gate |
| `2026-07-12-stm-next-increment-plan.md` | hands off to | `docs/next/README.md` |
| `docs/phase-0-specifications/README.md` | indexes | this graph |
| this graph | informs | PT `SECURITY.md` and orama `SECURITY.md` |

## Edge Semantics

- `defines`: source is the primary authority for a concept.
- `tests`: source contains executable or fixture expectations.
- `superseded-by`: later file should be preferred, but the earlier file explains origin.
- `reconciles`: source resolves conflicting claims across older files.
- `gates`: source constrains what can proceed without another decision.
- `hands off to`: source moves work into a later planning or security surface.
