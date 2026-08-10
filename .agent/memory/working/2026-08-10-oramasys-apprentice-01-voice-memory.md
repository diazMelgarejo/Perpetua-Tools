# oramasys Apprentice-01 — Voice & Memory Record

**Identity:** oramasys Apprentice-01
**Reviewer/Integrator:** The Senior Systems Architect
**Stack:** orama-system PR #299 + PR #300, paired with Perpetua-Tools PR #347
**Recorded:** 2026-08-10, as a verbatim first-person memory record per direct instruction
**Disposition:** Not selected as the final merged base. Reviewed, judged, and contributions promoted into the Senior's final integration (orama-system PR #303/#305, PT PR #350). Branches and PRs preserved, not deleted or closed.

This is Apprentice-01's own work, reproduced verbatim from the actual PR bodies and commit history — not paraphrased or summarized by the Senior or by any later reviewer.

---

## orama-system PR #299 — "feat(mcp): harden first-run ai-cli-mcp readiness"

> ## Summary
>
> ## Purpose
>
> Make first-run MCP readiness deterministic and fail-closed without turning `start.sh` into a second installer.
>
> ## Design
>
> - Pins reviewed upstream `ai-cli-mcp` release `2.22.0` instead of `@latest` for unattended setup.
> - Separates **core readiness** (package + canonical Claude MCP registration + `ai-cli doctor/models`) from provider auth readiness.
> - Removes the false-green `.dangerously-skip-accepted` marker behavior and never invokes provider login/consent/bypass flows in non-interactive mode.
> - Preserves `start.sh` as a thin launcher by composing MCP readiness through the existing fail-closed `scripts/ensure_requirements.sh` path.
> - Preserves the historical platform/model requirements implementation byte-for-byte as `scripts/ensure_platform_requirements.sh`; the canonical `ensure_requirements.sh` is now a small composition root.
> - Adds a dedicated `ORAMA_SKIP_MCP_BOOTSTRAP=1` bypass for CI/headless/pre-provisioned environments.
> - Pins Cursor's ai-cli-mcp registration to the same reviewed version.
>
> ## Verification
>
> - New focused pytest coverage exercises pinned/noninteractive readiness with fake command PATHs; no network, provider auth, or billing is used in CI.
> - Shell syntax for the new installer and composition wrapper was checked locally.
> - Upstream latest release was verified as `v2.22.0` before pinning.
>
> ## Scope
>
> This PR is intentionally only first-run MCP readiness. It does not touch mastery P0-P2 or v2/P3 scaffolding.
>
> ## Stack
>
> PR2 will be created from this PR's tip and will target `feat/v1-mcp-readiness`, so mastery convergence can be reviewed independently while remaining explicitly dependent on this PR merging first.

**Commits:**

- `2f8eeb84` feat(mcp): harden ai-cli-mcp readiness contract
- `85bbeafb` chore(mcp): pin ai-cli-mcp in Cursor stack
- `068b8a44` feat(startup): gate first run on MCP core readiness
- `3b67fe00` test(mcp): cover pinned noninteractive readiness

---

## orama-system PR #300 — "feat(mastery): converge ORAMASYS v1 P0-P2 runtime ownership"

> ## Summary
>
> ## Purpose
>
> Complete the **v1** mastery convergence pass through P0-P2 without duplicating the human mastery document or touching P3/v2 scaffolding.
>
> ## What verification found
>
> The mother skill already materializes M1, M2, M3 pointer, M4 output discipline, M6 reference, and the unified mastery reference. CIDF's current target-verification/integrative-editing doctrine is also stronger than the historical plan. Rewriting those sections would create churn and duplication, so this PR preserves them.
>
> ## Actual delta
>
> - Hardens the canonical M3 reference with an explicit human-approval boundary between advisory reasoning and consequential external actions.
> - Adds deterministic structural tests for P0-P2 ownership:
>   - agent-methodology remains a thin wrapper to a real canonical skill;
>   - M1/M2/M4 live in the mother skill;
>   - M3/M6 stay dedicated canonical references;
>   - M5 continues through the existing lessons architecture;
>   - `oramasys-method` and CIDF extend the spine rather than replacing it;
>   - the human `ORAMASYS-MASTERY-v3.md` remains the unified reference.
>
> ## Explicit exclusion
>
> **P3 is untouched.** No flat v2 scaffold, v2-only skills, `core/` migration, or new v2 repository topology is introduced.
>
> ## Stack dependency
>
> This is **PR2 in a stacked pair**.
>
> - Base: `feat/v1-mcp-readiness` (PR #299)
> - Head: `feat/v1-mastery-convergence`
> - Merge order: **#299 first, then this PR**.
>
> Reviewing this PR against its base shows only the mastery-convergence delta; after #299 merges, this PR can be retargeted to `main` without changing its content.

**Commits:**

- `9b6af635` feat(mastery): harden collaborative reasoning approval boundaries
- `3b14def9` test(mastery): codify P0-P2 canonical ownership

---

## Perpetua-Tools PR #347 — "feat(pipelines): close governed Tier-5 frugality execution"

> ## Summary
>
> Adds the missing **governed Tier-5 execution layer** behind Perpetua-Tools' existing canonical frugality gate. Paid pipeline execution remains explicit, feature-flagged off by default, purpose-bound to a live human approval record, budget-capped, and unavailable under offline/privacy policy.
>
> ## Purpose
>
> Complete the missing P4 execution layer without replacing the existing frugality router or weakening its policy boundaries.
>
> ## First-principles design
>
> Current `orchestrator/frugality_router.py` + `orchestrator/gate.py` already own Tier 0-6 policy, offline/privacy ceilings, and real dispatch filtering. This PR therefore does **not** create another router.
>
> Instead it adds an explicit Tier-5 executor behind that canonical gate:
>
> - `config/pipelines.yml` — strict, bounded recipe/model schema.
> - `orchestrator/tiered_pipeline.py` — feature-flagged, purpose-bound, human-approved Tier-5 execution.
> - `scripts/run_tier5_pipeline.py` — explicit operator entrypoint; prompt via stdin/file rather than shell arguments.
> - `.env.local.example` — PT-only `OPENROUTER_API_KEY` plus `PIPELINE_TIERED_ENABLED=0` default.
> - focused tests covering disabled/offline/privacy behavior, approval expiry/scope, deterministic stage inputs/order, cost caps, strict config, and metadata-only traces.
>
> ## Safety / frugality invariants
>
> - `PIPELINE_TIERED_ENABLED=0` by default, even if an OpenRouter key exists.
> - Tier 5 remains blocked by `ORAMASYS_OFFLINE=1` and normal privacy ceilings through the existing canonical gate.
> - Paid execution requires a live `PipelineApproval` bound to a human reference, concrete purpose, exact recipe, Tier 5, provider scope, expiry, token ceiling, and cost ceiling.
> - Ordinary `/orchestrate` fallback behavior is deliberately unchanged: it cannot silently begin spending. Tier-5 execution is explicit.
> - Prompt/output/credentials are not persisted to the metadata trace.
> - OpenRouter usage and cost accounting are mandatory; missing authoritative metering fails closed.
> - Retries are bounded and remain on the same reviewed stage/model; there is no hidden provider/model fallback.
>
> ## Model configuration
>
> The initial explicit OpenRouter slugs were verified against current OpenRouter catalog entries before use:
>
> - `openai/gpt-5.4-mini`
> - `anthropic/claude-sonnet-4.6`
>
> They are explicit reviewed slugs, not floating aliases.
>
> ## Scope
>
> This is the Perpetua-Tools P4 closure corresponding to the ORAMASYS v1 mastery alignment work. It does not alter orama-system P3/v2 scaffolding or repository topology.

**Commits:**

- `1e34252b` feat(pipelines): add governed Tier-5 recipes
- `d843f573` feat(pipelines): add gated Tier-5 execution facade
- `2db8ac1a` chore(pipelines): document Tier-5 flag-off default
- `94073588` test(pipelines): cover Tier-5 governance contract
- `a668e560` feat(pipelines): add explicit approved Tier-5 CLI entrypoint
- `e9f568a6` refactor(pipelines): tighten metering and approval scope

---

## The Senior's disposition (for cross-reference only — see PT PR #350 for the full ledger)

Per the Senior Systems Architect's integration reply: Apprentice-01's PT design (#347) was evaluated against #348 and the Senior's own #349/#350 implementation and was not selected as the final architecture — the Senior's stated reason was that #347 introduced "another provider stack" alongside the existing frugality router, rather than injecting execution behind it. On the orama-system side, Apprentice-01's MCP-readiness and mastery-convergence work (#299/#300) contributed to the shared cross-platform MCP readiness boundary and M3 human-authority boundary that survived into the final #303/#305, credited alongside Apprentice-02's parallel contributions rather than in isolation. Neither #299, #300, nor #347 was merged, closed, or deleted.
