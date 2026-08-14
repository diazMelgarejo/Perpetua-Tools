# Phase 0 Master Plan & Pre-v2 Checklist (2026-07-27)

<!-- markdownlint-disable MD013 MD040 MD056 -->
<!--
  This is a preserved historical master record with legacy long evidence lines,
  unlabeled diagrams, and tables whose source structure predates the Markdown
  lint ratchet. The 2026-08-14 addendum is intentionally narrow; do not
  reformat historical evidence as part of a disposition-only update.
-->

> **Canonical location:** Perpetua-Tools `docs/phase-0-specifications/` (STM/swarm security graph home).  
> **Orama mirror pointer:** [`orama-system/docs/next/2026-07-27-phase-0-master-plan.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-27-phase-0-master-plan.md)  
> **Supersedes for disposition:** both `docs/next/2026-07-25-pending-work-tracker.md` files (still linked for history).

**Verified against `main`:** PT `4f1a9936` · orama `41b77300` · 2026-07-27.

**Operational refresh (2026-08-14):**
[`../next/2026-08-14-operational-work-disposition.md`](../next/2026-08-14-operational-work-disposition.md)
records the current execution queue without rewriting the superseded trackers.
It verifies PT/Orama identity Phase 3 parity, preserves Tier-5 publication as
blocked on its recorded review gate, and separates operator evidence from
future code work.

---

## 1. Executive summary

Phase 0 asked one question: *how do peer observations, liveness, replay protection, witness quorum, and threat controls become operationally meaningful?* The answer shipped as **tested STM machinery** plus a **mesh security constellation** — but the **single-operator LAN descope** (D23) deliberately keeps BFT/Sybil/equivocation paths **dormant** until Fleet Mode changes the trust boundary.

**Penultimate posture before v2:**

| Layer | Status | Operator meaning |
| --- | --- | --- |
| **Mesh prep (Phase A)** | **DONE** (#223) | Local secrets, dotenv merge, topology archive hooks |
| **Mesh runtime (Phase C)** | **DONE** (#224 + PT #287) | `GOSSIP_SHARED_SECRET`, `mesh_gate`, discovery trust, swarm approval, PT `mesh_auth` |
| **Mesh IP expunge (Phase B)** | **IN PROGRESS** (#222 draft) | Tracked LAN IPs removed only after operator backup + mesh verify |
| **Mesh strict cutover (Phase D)** | **DEFERRED v2** | Fail-closed without local topology/secrets authority |
| **STM P5/P6/P13 pipeline** | **DONE code, DORMANT prod** | `evaluate_observation()` has **zero production callers**; descope verdict 2026-07-12 |
| **STM hygiene (T2/T3)** | **DONE** | Reorder-buffer bound, dedup key includes `sequence` |
| **Identity audit** | **Phases 1–3 DONE**, **4 NOW** | Shared policy/engine parity verified; audit before removing any remaining duplicate authority |
| **Hermes/OpenClaw staging** | **Mac DONE**, **Win operator NOW** | Live RTX harness smoke pending |
| **G7 portal hub** | **OPEN** (v1 optional) | Pre-v2 backlog closed; MVP not started |
| **Peer-mesh TLS/auth (orama 49)** | **MINIMUM DONE**, rest **DEFERRED v2** | Bearer-not-on-plain-HTTP guard only |

**Read first for graph context:** [`README.md`](README.md) → [`wiki/`](wiki/) (files, concepts, edges, security-trace).

---

## 2. Security posture (STM ↔ mesh)

### 2.1 Threat trace (T1–T7)

From [`wiki/security-trace.md`](wiki/security-trace.md) — mapped to **live controls today**:

| Threat | Phase 0 source | v1 posture (2026-07-27) | Status |
| --- | --- | --- | --- |
| **T1** malicious relay | D4 | Redaction, authenticated control plane, trusted endpoints | **PARTIAL** — mesh auth when LAN-bound; STM equivocation **dormant** |
| **T2** stale peer | D2 | Heartbeat/liveness in orchestrator paths | **DONE** — operational liveness; STM witness path **not wired** |
| **T3** replay | D4 | Dedup + monotonic gates in STM | **DONE code** — dedup key fix landed; **no prod ingestion** |
| **T4** Sybil witnesses | Pattern synthesis | Premise check before adversarial mesh claims | **DESCOPE** — revisit at Fleet external tenants |
| **T5** flooding/DoS | Medium matrices | Bounded caches, rate limits | **DONE** — STM caches bounded; mesh rate limits per fleet docs |
| **T6** confidence inflation | D1 | Confidence + witness diversity | **DORMANT** — no production `PeerObservation` producers |
| **T7** out-of-order | Phase 2 blockers | Reorder buffer + monotonic apply | **DONE code** — buffer bounded; **not in prod loop** |

**Safe v1 path (documented):** small trusted-operator mesh, loopback-first, authenticated LAN exposure, redaction, bounded buffers, explicit operator recovery. **v2** multi-site/adversarial mesh gated by evidence graph, not assumption.

### 2.2 Mesh security constellation (cross-repo)

Full integrated report: **§12** (source: [orama PR #224 finality report](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-26-pr224-mesh-security-finality-report.md)).

```
mesh_gate.py (GOSSIP truth)
  → start.sh / start.ps1 (fail-closed on LAN bind)
  → ensure_local_mesh_secrets + dotenv_merge
  → discovery_trust (P6) + swarm_approval (P5)
  → PT mesh_auth (PT_BIND_LAN=1)
```

Working memory: PT `.agent/memory/working/MESH_SECURITY_MIGRATION_2026-07-26.md`.

### 2.3 STM descope verdict (binding)

[`2026-07-12-stm-next-increment-plan.md`](2026-07-12-stm-next-increment-plan.md) **CLOSED 2026-07-12:**

- Threat-model re-check → **DESCOPE** P5/P6/P13 at current scale (2 machines, 1 operator, zero adversarial incidents).
- **Do not** wire `evaluate_observation()` into `/health` as originally scoped.
- **Revisit when:** Fleet Mode introduces **real external tenants** (not just more self-owned nodes).

Aligned with orama [`docs/v2/45-single-operator-lan-threat-model-descope.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/45-single-operator-lan-threat-model-descope.md) (D23).

---

## 3. Status legend

| Tag | Meaning |
| --- | --- |
| **DONE** | On `main`, verified or self-contained historical record |
| **IN PROGRESS** | Open PR, operator gate, or claimed coordination-board work |
| **NOW** | Worth completing before v2 migration (low ambiguity, v1 stack) |
| **DEFERRED v2** | Explicitly deferred to v2 `oramasys/*` or post-migration |
| **REFERENCE** | Investigation, pattern, or retrospective — not a backlog item |
| **SUPERSEDED** | Replaced by a newer canonical doc (pointer only) |

---

## 4. Master checklist — security & mesh (cross-repo)

| Item | Repo | Tag | Evidence / next step |
| --- | --- | --- | --- |
| Mesh Phase A prep (#223) | orama | **DONE** | `main` @ `a0ced30c` lineage |
| Mesh Phase C runtime (#224) | orama | **DONE** | `main` @ `41b77300` |
| PT gossip LAN auth (#287/#288) | PT | **DONE** | `mesh_auth.py`, `8b38f8ad` |
| Operator backup before IP expunge | fleet | **NOW** | `.env.local`, `.local/mesh-secrets.json`, `.local/lan-topology.json` |
| Mesh verify on all nodes | fleet | **NOW** | `install.sh`/`install.ps1`, gossip emit/tail, LM Studio probes |
| Mesh Phase B IP expunge (#222) | orama | **IN PROGRESS** | Draft PR; merge **after** backup + verify |
| `docs/v2/50-mesh-security-migration-ladder.md` | orama | **IN PROGRESS** | Ships with #222 (not on `main` yet) |
| Mesh Phase D strict cutover | both | **DEFERRED v2** | `perpetua-core` authority at v2 launch |
| Identity audit Phase 3 (PT parity) | PT | **DONE** | Policy, schema, and audit engine are byte-identical with Orama; no copy-only PR is needed |
| Identity audit Phase 4 (audit/remove lists) | both | **NOW** | Prove every consumer delegates before removing a duplicate authority; see the operational disposition |
| AlphaClaw TLS core (#276/#278) | PT | **DONE** | Opt-in `ALPHACLAW_TLS_ENABLED` |
| TLS admin-pinned fingerprints | PT | **DEFERRED v2** | TOFU-only today |
| TLS mTLS / auto-enable | PT | **DEFERRED v2** | Plan doc v1/v2 split |
| TLS stalled-client test fix | PT | **NOW** | `test_proxy_bounds_stalled_client_connections` |
| Peer-mesh `secure_transport.py` | orama | **DEFERRED v2** | [`docs/v2/49-peer-mesh-auth-tls-v2-plan.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/49-peer-mesh-auth-tls-v2-plan.md) |
| Hermes Mac staging execution | orama | **DONE** | [`docs/plans/2026-07-26-hermes-openclaw-staging-execution.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-26-hermes-openclaw-staging-execution.md) |
| Hermes Win live harness smoke | fleet | **NOW** | RTX 3080/5080 `install.ps1` / harness sync |
| Agent registry/SOUL alignment | orama | **DONE** | Config canonicalization, Glen AFRP, wrappers (pre-`41b77300` work) |
| STM production wiring (`evaluate_observation`) | PT | **SUPERSEDED** | Descope verdict — do not implement as originally scoped |
| STM reorder + dedup fixes | PT | **DONE** | `62b66119`, `128e69eb` |
| STM AuditLog persist_path | PT | **DONE** | JSONL sink; Reputation/Equivocation persist **DEFERRED** until P5/P6 live |
| STM high-peer-count benchmark | both | **DEFERRED v2** | `docs/v2/03-safety-v2.5.md` |
| ecc-tools submodule drift | PT | **NOW** | Local modified pointer — reconcile or commit |

---

## 5. Phase 0 specifications — every file accounted for

### 5.1 Wiki graph (Codex agent, `4f1a9936`)

| File | Tag | Notes |
| --- | --- | --- |
| [`wiki/README.md`](wiki/README.md) | **DONE** | Wiki index |
| [`wiki/files.md`](wiki/files.md) | **DONE** | File nodes |
| [`wiki/concepts.md`](wiki/concepts.md) | **DONE** | Concept dictionary |
| [`wiki/edges.md`](wiki/edges.md) | **DONE** | Explicit edges |
| [`wiki/security-trace.md`](wiki/security-trace.md) | **DONE** | T1–T7 → policy links |

### 5.2 Pattern & threat research

| File | Tag | Notes |
| --- | --- | --- |
| [`PATTERN-SYNTHESIS.md`](PATTERN-SYNTHESIS.md) | **DONE** | Pattern library; P5/P6/P13 gate closed per descope |
| [`PATTERN-MULTIAGENT-EXECUTION-PLAN.md`](PATTERN-MULTIAGENT-EXECUTION-PLAN.md) | **REFERENCE** | Execution history |
| [`MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`](MULTIAGENT-SWARM-SECURITY-ANALYSIS.md) | **DONE** | Descope addendum appended 2026-07-12 |
| [`DELIVERABLE-1-*`](DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md) | **DONE** | Canonical D1; expanded variant **REFERENCE** |
| [`peer_observation_tdd.md`](peer_observation_tdd.md) | **DONE** | Fixtures |
| [`TASK_A2_FINDINGS.md`](TASK_A2_FINDINGS.md) | **REFERENCE** | A2 findings |
| [`DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md`](DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md) | **DONE** | D2 contract |
| [`DELIVERABLE-4-THREAT-MODEL-REGENERATED.md`](DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) | **DONE** | T1–T7 |
| [`MEDIUM-ITEMS-DECISION-MATRICES.md`](MEDIUM-ITEMS-DECISION-MATRICES.md) | **DONE** | M1–M7 decisions |
| [`PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md`](PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md) | **DONE** | STM reconciliation |

### 5.3 STM integration & PR #203/#205 lineage

| File | Tag | Notes |
| --- | --- | --- |
| [`PHASE-0-TASK-LIST.md`](PHASE-0-TASK-LIST.md) | **SUPERSEDED** | Provenance; shipped STM path |
| [`PHASE-1-SCOPE-DRAFT.md`](PHASE-1-SCOPE-DRAFT.md) | **DONE** | Phase 1.0–1.3 complete 2026-07-11 |
| [`2026-07-11-phase1b-integration-review.md`](2026-07-11-phase1b-integration-review.md) | **REFERENCE** | Gap analysis |
| [`2026-07-11-state-transition-manager-integration-plan.md`](2026-07-11-state-transition-manager-integration-plan.md) | **DONE** | Integration shipped; wiring target guess **superseded** by remediation plan |
| [`2026-07-11-pr203-multiagent-orchestration.md`](2026-07-11-pr203-multiagent-orchestration.md) | **REFERENCE** | PR #203 orchestration |
| [`2026-07-11-PR203-BLEND-VERDICT.md`](2026-07-11-PR203-BLEND-VERDICT.md) | **DONE** | Blend reconciled |
| [`README-PR203-BLEND.md`](README-PR203-BLEND.md) | **REFERENCE** | Navigator; some checkboxes stale |
| [`2026-07-11-PHASE-2-BLOCKERS.md`](2026-07-11-PHASE-2-BLOCKERS.md) | **DONE** | Blockers addressed in #205 |
| [`PHASE-2-JOB-BOARD.md`](PHASE-2-JOB-BOARD.md) | **DONE** | Tasks done; benchmark **DEFERRED v2** |
| [`2026-07-12-autoplan-final-approval-gate.md`](2026-07-12-autoplan-final-approval-gate.md) | **DONE** | #205 approval |
| [`2026-07-12-stm-remediation-plan.md`](2026-07-12-stm-remediation-plan.md) | **DONE** | Correct wiring target identified |
| [`2026-07-12-stm-next-increment-plan.md`](2026-07-12-stm-next-increment-plan.md) | **DONE** | **CLOSED** — descope + T2/T3 |
| [`2026-07-12-ceo-review-quad-voices/`](2026-07-12-ceo-review-quad-voices/00-README.md) | **REFERENCE** | Evidence pack |
| [`2026-07-12-eng-review-voices/`](2026-07-12-eng-review-voices/00-README.md) | **REFERENCE** | Evidence pack |
| [`2026-07-12-eng-review-triple-voices/`](2026-07-12-eng-review-triple-voices/01-claude-sonnet5.md) | **REFERENCE** | Evidence pack |
| **This file** | **DONE** | Penultimate master plan |

---

## 6. Perpetua-Tools `docs/next/` — every file accounted for

| File | Tag | Notes |
| --- | --- | --- |
| [`README.md`](../next/README.md) | **DONE** | Index — update pointer to this master plan |
| [`2026-07-25-pending-work-tracker.md`](../next/2026-07-25-pending-work-tracker.md) | **SUPERSEDED** | Stale branch refs — use §4 above |
| [`2026-07-17-coordination-module-consolidation-plan.md`](../next/2026-07-17-coordination-module-consolidation-plan.md) | **DONE** + **IN PROGRESS** | Parts 1/1b/1c/1d merged; Part 2 + coordination **Phase 0F** → [`../coordination/README.md`](../coordination/README.md) (not STM Phase 0) |
| [`2026-07-17-phase-board-fragmentation-analysis.md`](../next/2026-07-17-phase-board-fragmentation-analysis.md) | **REFERENCE** | Fixed `9642ae24` |
| [`2026-07-17-tool-use-limits-session-reflection.md`](../next/2026-07-17-tool-use-limits-session-reflection.md) | **REFERENCE** | Retrospective |
| [`2026-07-17-frugal-pr-review-triage-pattern.md`](../next/2026-07-17-frugal-pr-review-triage-pattern.md) | **REFERENCE** | Pattern from PR #256 |
| [`2026-07-19-heartbeat-daemon-design.md`](../next/2026-07-19-heartbeat-daemon-design.md) | **DEFERRED v2** | Design only — scope now, build later |
| [`2026-07-24-alphaclaw-tls-proxy-scaffolding.md`](../next/2026-07-24-alphaclaw-tls-proxy-scaffolding.md) | **DONE** | Merged #276/#278 |
| [`2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md`](../next/2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md) | **DONE** | ACL in #278 |
| Tri-repo plan | [`../2026-05-31-tri-repo-alignment-completion-plan.md`](../2026-05-31-tri-repo-alignment-completion-plan.md) | **DONE** + **DEFERRED v2** | Item #1 done; #2/#3/#8 deferred |

---

## 7. orama-system `docs/next/` — every file accounted for

| File | Tag | Notes |
| --- | --- | --- |
| [`README.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/README.md) | **DONE** | Index |
| [`2026-07-25-pending-work-tracker.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-25-pending-work-tracker.md) | **SUPERSEDED** | Use §4 |
| [`2026-07-25-docs-scan-and-integrity-report.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-25-docs-scan-and-integrity-report.md) | **SUPERSEDED** | HEAD stale (`5b05f545`); §4 refreshes |
| [`2026-07-24-plan-unified-identity-audit.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-24-plan-unified-identity-audit.md) | **DONE** + **NOW** | Phases 1–2 done; 3–4 open |
| [`2026-07-17-pr166-pr169-git-recovery-analysis.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-17-pr166-pr169-git-recovery-analysis.md) | **REFERENCE** | No rewrite performed |
| [`2026-07-17-preserve-branch-pr-cleanup-plan.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-17-preserve-branch-pr-cleanup-plan.md) | **REFERENCE** | Review before deletion |
| [`preserve-branch-manifest.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/preserve-branch-manifest.md) | **DONE** | Phase 1 complete 2026-07-17 |
| [`2026-07-27-phase-0-master-plan.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-27-phase-0-master-plan.md) | **DONE** | Orama pointer + §8 Hermes |

### 7.1 `docs/next/fleet-mesh/` — every file accounted for

| File | Tag | Notes |
| --- | --- | --- |
| [`README.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/README.md) | **DONE** | Active index |
| [`2026-07-08-self-healing-mesh-degradation-modes.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-08-self-healing-mesh-degradation-modes.md) | **DONE** + **DEFERRED v2** | Mother plan; Phases 8–10+ open |
| [`2026-07-10-phase-integration-map.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-10-phase-integration-map.md) | **REFERENCE** | Timeline map |
| [`2026-07-10-oasn-p2p-architecture-research.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-10-oasn-p2p-architecture-research.md) | **REFERENCE** | Research only |
| [`G7-ASYNC-NOTIFICATIONS-ANALYSIS.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/G7-ASYNC-NOTIFICATIONS-ANALYSIS.md) | **NOW** (optional) | Portal hub MVP not started |
| [`2026-07-14-g7-async-notifications-next-steps.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-14-g7-async-notifications-next-steps.md) | **NOW** (optional) | G7 checklist |
| [`2026-07-19-oob-completion-findings.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-19-oob-completion-findings.md) | **REFERENCE** | OOB findings |
| [`2026-07-26-pr224-mesh-security-finality-report.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-26-pr224-mesh-security-finality-report.md) | **DONE** | #224 finality; integrated in master plan §12 |
| [`phase-7-to-10-roadmap.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/phase-7-to-10-roadmap.md) | **DEFERRED v2** | Skeleton for Phases 8–10+ |

**G7 pre-v2 closure** (rate-limit, React Query): **DONE** per fleet-mesh README.

---

## 8. Hermes / OpenClaw staging plans (orama `docs/plans/`)

| File | Tag | Notes |
| --- | --- | --- |
| [`2026-07-26-hermes-openclaw-staging-review-gate.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-26-hermes-openclaw-staging-review-gate.md) | **DONE** | Review gate |
| [`2026-07-26-hermes-openclaw-staging-execution.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-26-hermes-openclaw-staging-execution.md) | **DONE** | Mac execution complete |
| [`2026-07-26-hermes-openclaw-migration-operator.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-26-hermes-openclaw-migration-operator.md) | **NOW** | Operator Win walkthrough |
| [`2026-07-26-hermes-agent-canonical-staging-and-profile-install.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-26-hermes-agent-canonical-staging-and-profile-install.md) | **DONE** | Profiles + install script |
| Tracker | `.agent/memory/working/HERMES_OPENCLAW_STAGING_2026-07-26.md` (PT) | **IN PROGRESS** | Win live test pending |

---

## 9. Closure ledger cross-reference

Still authoritative for **out-of-scope** items from the 2026-07-22 P3 trace:

[`orama-system/docs/plans/2026-07-22-cross-repo-out-of-scope-closure.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-22-cross-repo-out-of-scope-closure.md)

This master plan **does not re-run** the 29-document companion audit — that remains **DEFERRED v2** per the closure doc itself.

**VISION priority stack** ([`orama-system/VISION.md`](https://github.com/diazMelgarejo/orama-system/blob/main/VISION.md)) — current interpretation:

1. Security/safe defaults → mesh Phase C **DONE**; Phase B **IN PROGRESS**
2. Portable memory (D47) → ongoing invariant
3. v1 finish-now → identity Phase 4 audit, mesh operator verify, Hermes Win smoke (**§4 NOW**)
4. Kernel lean → **DEFERRED v2** (`perpetua-core`)
5. v2 parity tests → **DEFERRED v2**

---

## 10. Operator pre-v2 gate (ordered)

Run before merging **#222** or starting v2 repo bootstrap:

1. **Backup** on every fleet node: `.env.local`, `.local/mesh-secrets.json`, orama `.local/lan-topology.json`.
2. **Pull** both repos to ≥ PT `4f1a9936`, orama `41b77300`.
3. **Install mesh hooks:** `install.sh` (Mac/Linux) / `install.ps1` (Win) on PT and orama.
4. **Verify gossip:** emit/tail with `X-Gossip-Secret`; LM Studio probes green.
5. **Hermes harness:** `install-hermes-harness.ps1` on Win — expect idempotent skip when synced.
6. **Identity Phase 4 audit:** verify all production consumers delegate to
   the shared engine before removing any old list.
7. **TLS regression:** fix stalled-client test if touching TLS surface.
8. **Merge #222** only after steps 1–4 green.
9. **Submodule:** reconcile `vendor/ecc-tools` pointer on PT in a separate
   provenance-reviewed change.

---

## 11. Pickup map (where to start)

| If you are working on… | Start here |
| --- | --- |
| STM / swarm security theory | [`README.md`](README.md) → [`wiki/`](wiki/) |
| Mesh runtime / GOSSIP | Master plan **§12** + [PR #224 finality report](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-26-pr224-mesh-security-finality-report.md) |
| IP expunge / v2 ladder | orama PR **#222** (draft) |
| Identity allowlists | [integrated plan](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-24-unified-identity-audit-integrated-plan.md) Phase 3 |
| Hermes profiles | [execution log](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-26-hermes-openclaw-staging-execution.md) |
| G7 notifications | [fleet-mesh G7 analysis](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/G7-ASYNC-NOTIFICATIONS-ANALYSIS.md) |
| v2 architecture | [`orama-system/docs/v2/README.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/README.md) |
| Adversarial mesh (Phase 10+) | [`docs/v2/43-gossipbus-mesh-transport.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/43-gossipbus-mesh-transport.md) + PT swarm security analysis |

---

## 12. Mesh security finality report (integrated)

> **Source:** [orama `2026-07-26-pr224-mesh-security-finality-report.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-26-pr224-mesh-security-finality-report.md)  
> **Integrated here** so the master plan is self-contained for operators and agents.  
> **Post-merge update:** #224 and PT #287/#288 are on `main` (orama `41b77300`, PT `8b38f8ad`); #222 remains merge-last.

### 12.1 Executive summary

PR #224 delivered **Phase C runtime gates** (P5 swarm HITL + P6 discovery trust) on merged #223 prep (Phase A). The stack is **fail-closed on LAN bind**: mesh secrets, control-plane tokens, discovery handshakes, and swarm approvals must be explicit — no silent bypass when binding to the network.

Cross-repo PT #287 adds **HTTP gossip auth** when `PT_BIND_LAN=1`. Sibling harmonization shares `GOSSIP_SHARED_SECRET` via `ORAMA_SYSTEM_PATH` / `PERPETUA_TOOLS_PATH`.

### 12.2 PR stack status (updated 2026-07-27)

| PR | Branch | Status | Phase | Scope |
| --- | --- | --- | --- | --- |
| **#223** | `cursor/mesh-prep-main-f559` | **Merged** → `main` | **A** Prep | `dotenv_merge`, `ensure_local_mesh_secrets`, `lan_topology_archive`, install hooks |
| **#224** | `cursor/p5-p6-mesh-hardening-f559` | **Merged** → `main` @ `41b77300` | **C** Runtime | P5/P6, Windows parity, `mesh_gate`, trusted install verifier |
| **#287** | `cursor/gossip-lan-mandate-f559` | **Merged** → PT `main` | **C** Runtime | PT gossip auth, `mesh_auth.py`, `install.ps1` |
| **#288** | (in #287) | **Done** | Fix | Adopt `.env.local` secret without silent rotation |
| **#222** | `cursor/hermes-staging-security-hardening-f559` | **Open draft — merge last** | **B** + docs | IP expunge, `docs/v2/50-mesh-security-migration-ladder.md` |

**Never merge #222 before operator backup + mesh verify** — local caches and secrets must exist before tracked IP removal.

### 12.3 Merge order and phase ladder

Execution order is **A → C → B → D** (not alphabetical).

| Phase | Name | Artifact | Scope | Tag |
| --- | --- | --- | --- | --- |
| **A** | Prep | #223 | Local caches, secrets, install hooks | **DONE** |
| **C** | Runtime gates | #224 + PT #287 | GOSSIP gate, discovery trust, swarm approval, PT LAN auth | **DONE** |
| **B** | IP expunge | #222 | Remove real LAN IPs from tracked YAML/JSON | **IN PROGRESS** |
| **D** | Strict cutover | v2 launch | Fail closed without secrets/topology; `perpetua-core` authority | **DEFERRED v2** |

| Step | Action | Status |
| --- | --- | --- |
| 1 | Merge orama #223 | **DONE** |
| 2 | Operator backup on every fleet node | **NOW** |
| 3 | Merge #224 + PT #287 together | **DONE** on `main` |
| 4 | Verify mesh on all nodes | **NOW** |
| 5 | Merge #222 last | **IN PROGRESS** |

### 12.4 Mesh security constellation

Single truth for gossip secret presence; fail-closed at every bind point:

```
mesh_gate.py (GOSSIP in $env OR non-empty .env.local, dotenv last-wins)
  → start.sh / start.ps1 / Invoke-MeshLocalCache.ps1 (LanBind)
  → ensure_local_mesh_secrets.py + dotenv_merge.read_dotenv_key
  → discovery_trust (P6) + swarm_approval (P5) + verify_trusted_install
  → PT mesh_auth when PT_BIND_LAN=1 (X-Gossip-Secret header)
```

| Concern | Unix / Mac | Windows |
| --- | --- | --- |
| Full install | `install.sh` | `platform/windows/install.ps1` |
| Mesh prep | `ensure_local_mesh_secrets.py` + `lan_topology_archive.py` | `Invoke-MeshLocalCache.ps1 -Mode Install` |
| LAN start gate | `start.sh --lan-peer` → `mesh_gate.py` | `start.ps1 -LanPeer` → `Invoke-MeshLocalCache.ps1 -Mode LanBind` |
| RTX harness | N/A | `install-hermes-harness.ps1` |
| Missing mesh PS1 | N/A | **exit 1** (no silent continue) |

### 12.5 Cross-repo contracts

| Env var | Repo | Purpose |
| --- | --- | --- |
| `GOSSIP_SHARED_SECRET` | Both | Shared HMAC for gossip + discovery handshake |
| `PT_BIND_LAN=1` | PT | Fail-closed 503 on gossip without secret |
| `ORAMA_SYSTEM_PATH` | PT | Sibling harmonization → orama `.env.local` |
| `PERPETUA_TOOLS_PATH` | orama | Sibling harmonization → PT `.env.local` |
| `ORAMA_SWARM_STRICT=1` | orama | P5 strict — token + explicit approval |
| `ORAMA_APPROVE_DISCOVERY=1` | orama | One-shot P6 peer approve |

**Gitignored local files:**

| File | Repo | Purpose |
| --- | --- | --- |
| `.env.local` | Both | Harmonized secrets |
| `.local/mesh-secrets.json` | Both | JSON mirror for tooling |
| `.local/mesh.log` | Both | Mesh script audit trail |
| `.local/lan-topology-archive.json` | orama | Pre-IP-expunge topology cache |
| `.local/known-peers.json` | orama | P6 trusted peer IPs |
| `.local/discovery-handshake-pending.json` | orama | P6 pending handshakes |

### 12.6 #288 silent rotation bug (fleet-critical)

**Regression in #287:** When `GOSSIP_SHARED_SECRET` existed only in `.env.local` (no `mesh-secrets.json`), harmonization could **append** a second declaration → dotenv **last wins** → fleet auth silently rotated → **403 storm**.

**Fix (on `main`):**

| Piece | Role |
| --- | --- |
| `read_dotenv_key()` | Read effective (last) non-empty dotenv value |
| `_read_existing_secret()` adoption | Check JSON then `.env.local` before generating |
| `pending.pop(key)` in harmonize | When existing value kept, do not append duplicate |
| JSON bootstrap branch | Backfill `mesh-secrets.json` from env-only secret |

### 12.7 CodeRabbit #224 remediation summary (`97bb307e` → merged)

| Area | After (on `main`) |
| --- | --- |
| Mesh LAN gate | `mesh_gate.py` — non-empty secret in env or dotenv (no file-existence bypass) |
| `start.ps1` | Missing `Invoke-MeshLocalCache.ps1` → **exit 1** |
| P6 discovery | Pending nonce + TTL; session consumed on success; `win_peers[]` gated |
| P5 swarm | Explicit HITL; fingerprint + HMAC token; single-use cache |
| Trusted install | `logging` module; `reanchor_scan` for branch sync |
| Tests | `test_mesh_secrets`, `test_mesh_gate`, `test_discovery_trust`, `test_swarm_approval`, `test_control_plane_auth` — 35 passed at finality |

### 12.8 P5 swarm approval (runtime behavior)

1. `POST /api/swarm/preview` → `issue_approval` → `preview_id` + `approval_token`
2. `POST /api/swarm/launch` with `approved=true` + token → `verify_launch`
3. Grandfather path: legacy callers with `approved` only (no token) when not strict
4. Strict path: `approved` + fingerprint match + valid HMAC + single-use cache consume

### 12.9 P6 discovery trust (runtime behavior)

1. `filter_endpoints_for_trust` — known-peers / archive → trusted
2. Unknown peer → `initiate_handshake` → operator prints nonce + signature CLI ack
3. `discover.py --ack-peer --nonce --signature` → `verify_handshake` (nonce + TTL + HMAC)
4. Success → `remember_peer(ip)`

### 12.10 v1 transition vs v2 authority

| Era | Model |
| --- | --- |
| **v1.x (now)** | Both repos install standalone; co-installed siblings share secrets via path harmonization. Lax by design during transition. |
| **v2 target** | `perpetua-core` = single runtime/state authority; `oramasys` stateless; mesh module centralizes secrets/topology. |

**Deferred hardening (v1 acceptable → v2 cleanup):**

| Item | v1 | v2 |
| --- | --- | --- |
| Atomic JSON write (`tmp` + replace) | Tolerate rare partial writes | Central mesh module |
| Defensive `_load_json` everywhere | Partial (`discovery_trust`) | Full validation |
| `GOSSIP_SHARED_SECRET__PREVIOUS_*` retention | Accumulates on rotation | Drop pattern |
| Windows ACL in `harden_local_file` | chmod on Unix only | ACL path |

### 12.11 Integrative dotenv doctrine

- `harmonize_dotenv_keys` fills **missing or empty** keys only.
- Duplicate keys: update the **last** declaration; comment earlier duplicates.
- Rotation (`--force`): supersede old values as commented lines — **additive, never delete**.
- **#288:** adopt existing `.env.local` values before generating new secrets.

### 12.12 Operator commands (from finality report)

**Unix / Mac (orama):**

```bash
cd "$ORAMA_SYSTEM_PATH"
bash install.sh
python3 scripts/mesh/ensure_local_mesh_secrets.py
./start.sh --lan-peer
python3 scripts/mesh/mesh_gate.py .   # exit 0 = secret configured
```

**Windows (orama):**

```powershell
cd $env:ORAMA_SYSTEM_PATH
powershell -ExecutionPolicy Bypass -File .\platform\windows\install.ps1
.\.venv\Scripts\python.exe scripts\mesh\ensure_local_mesh_secrets.py
powershell -File .\platform\windows\start.ps1 -LanPeer
```

**Perpetua-Tools:**

```powershell
cd $env:PERPETUA_TOOLS_PATH
powershell -ExecutionPolicy Bypass -File .\install.ps1
.\.venv\Scripts\python.exe scripts\mesh\ensure_local_mesh_secrets.py
```

### 12.13 Open operator checklist (mesh finality)

| Step | Tag |
| --- | --- |
| Backup `.env.local` + `.local/mesh-secrets.json` on **all** fleet nodes | **NOW** |
| ~~Merge #224 + PT #287 together~~ | **DONE** |
| Distribute `GOSSIP_SHARED_SECRET` out-of-band if nodes diverged | **NOW** |
| RTX 5080: `install.ps1` → `start.ps1 -LanPeer` smoke test | **NOW** |
| Gossip emit/tail with `X-Gossip-Secret` header | **NOW** |
| Merge #222 **last** after mesh verified | **IN PROGRESS** |

**STM linkage:** Mesh P5/P6 here are **orama control-plane / discovery** runtime gates — distinct from PT STM `evaluate_observation()` P5/P6/P13 machinery, which remains **dormant in production** per §2.3 descope verdict.

**Related (not duplicated here):** fleet-mesh [`README.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/README.md), [`docs/v2/43-gossipbus-mesh-transport.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/43-gossipbus-mesh-transport.md), PT `.agent/memory/working/MESH_SECURITY_MIGRATION_2026-07-26.md`.

---

## 13. Document maintenance

- **Update this file** when a §4 checklist item changes state.
- **Do not** revive `2026-07-25-pending-work-tracker.md` as primary — append a one-line supersede banner instead.
- **Re-verify HEAD** before trusting disposition tags; self-reported doc headers decay fast.

**Last updated:** 2026-07-27 · PT `4f1a9936` · orama `41b77300`
