# oramasys Apprentice-02 — Voice & Memory Record

<!-- markdownlint-disable MD013 -->

**Identity:** oramasys Apprentice-02
**Reviewer/Integrator:** The Senior Systems Architect
**Stack:** orama-system PR #301 + PR #302, paired with Perpetua-Tools PR #348
**Recorded:** 2026-08-10, as a verbatim first-person memory record per direct instruction
**Disposition:** Not selected as the final merged base. Reviewed, judged, and contributions promoted into the Senior's final integration (orama-system PR #303/#305, PT PR #350). Branches and PRs preserved, not deleted or closed.

This preserves Apprentice-02's original PR-body text and commit history. Embedded heading labels carry a provenance prefix only so this composite record remains unambiguous; no substantive body text was reworded.

---

## orama-system PR #301 — "feat(mcp): harden first-run ai-cli-mcp readiness"

> ## PR #301 Summary
>
> Hardens the existing canonical MCP installer instead of duplicating installation logic in `start.sh`.
>
> - pins `ai-cli-mcp` to reviewed upstream v2.22.0
> - adds `--core-only`, `--verify`, and `--non-interactive`
> - removes the false-green Claude `--dangerously-skip-permissions` acceptance-marker behavior
> - separates core MCP readiness from provider authentication/consent
> - validates upstream Node engine requirements (`>=20.19` on Node 20 or `>=22.12`)
> - verifies `ai-cli doctor`, `ai-cli models`, and Claude MCP registration
> - delegates first-run readiness from the bootstrap path already invoked by `start.sh`
> - adds deterministic fake-PATH tests with no npm network/auth/billing
>
> ## PR #301 Design decision
>
> The hardened plan suggested adding more installer mechanics directly to the launcher. I kept the stronger safety/readiness contract but preserved the existing ORAMASYS/CIDF ownership rule: **one canonical implementation, launcher delegates**. `start.sh` already calls `scripts/bootstrap-environment.sh`, so the bootstrap invokes the canonical installer rather than copying npm/Claude commands into the launcher.
>
> The current launcher intentionally treats cross-cutting bootstrap as fail-soft (`|| true`). This PR preserves that resilience contract: a failed MCP bootstrap is explicit and the external worker lane is unavailable, while base local services can still start. A later hard-gate can call the same installer without changing ownership.
>
> ## PR #301 Safety
>
> No provider login, browser flow, terms acceptance, or permission bypass is executed automatically. Provider presence is not treated as authentication.
>
> ## PR #301 Scope
>
> PR 1 of a stacked pair. PR 2 will target this branch and contain only P0-P2 mastery convergence. **P3 is untouched.**

**Commits:**

- `6a732381` feat(mcp): harden cross-platform first-run readiness

---

## orama-system PR #302 — "docs(mastery): converge P0-P2 runtime ownership and safety"

> ## PR #302 Summary
>
> ## PR #302 Stack
>
> **PR 2 of 2. Base: `feat/mcp-first-run-readiness` (PR #301), not `main`.**
>
> Review this PR as the delta on top of PR #301. It is intentionally dependent on PR #301 merging first; after #301 merges, this PR can be retargeted to `main` without changing its own commits.
>
> ## PR #302 Verified before editing
>
> - P0 is already canonicalized: `.claude/skills/agent-methodology/SKILL.md` is a thin wrapper.
> - M1 Spec Contract, M2 Amplifier Objective Tree, M4 six-part output discipline, and the M3/M6 pointer network are already present in the mother skill.
> - M3 and M6 reference files already exist.
>
> Therefore this PR does **not** rewrite the mother skill or duplicate mastery prose. It applies the hardened plan only where current runtime semantics were genuinely incomplete.
>
> ## PR #302 Changes
>
> - completes M3 with an explicit human-authority boundary for chain research, persistent/always-on agents, swarms, paid execution, credentials, commits/deploys, and external communications
> - makes advisory/research output distinct from privileged or irreversible action
> - forbids agents/consensus from self-authorizing the next privileged step
> - adds deterministic structural tests for P0-P2 ownership and semantic markers
> - adds a guard that the explicitly excluded P3 scaffold surfaces are not materialized
>
> ## PR #302 ORAMASYS/CIDF rationale
>
> This is the smallest verified change that closes the actual gap. Existing canonical text remains in place; pointers stay pointers; CI checks ownership/markers rather than attempting LLM-based semantic judgment.
>
> ## PR #302 Explicit exclusion
>
> **P3 is untouched.** No v2 flat scaffold, new §5c skills, v2 `core/`, or mastery workflow is created.

**Commits:**

- `0b4c8c92` feat(mcp): harden ai-cli-mcp readiness contract
- `0eb2759c` feat(startup): delegate first-run MCP readiness through bootstrap
- `771f16e2` test(mcp): cover noninteractive readiness failure modes
- `61f77051` docs(mastery): complete M3 human authority boundary
- `de862196` test(mastery): codify P0-P2 ownership and P3 exclusion

---

## Perpetua-Tools PR #348 — "feat(p4): add governed default-off Tier-5 pipelines"

> ## PT PR #348 Summary
>
> Closes the missing P4 execution surface without replacing the existing frugality router/gate.
>
> - adds strict `config/pipelines.yml` schema with one bounded two-stage recipe
> - adds `TieredPipelineRunner` that accepts only a router-approved Tier-5 OpenRouter route
> - defaults `PIPELINE_TIERED_ENABLED` to off
> - requires PT-local `OPENROUTER_API_KEY`; key presence never enables execution
> - blocks offline/privacy-critical execution before provider invocation
> - requires a bounded, expiring human approval record binding trace, purpose, recipe, tier, tokens, cost, and provider scope
> - validates stage graph, governed model-class aliases, token caps, cost caps, and deterministic `input_from`
> - injects provider I/O so credentials/model resolution remain in existing PT runtime rather than the pipeline policy file
> - returns redacted bounded stage accounting rather than logging prompts/provider blobs
> - adds no-egress, approval, ordering, and budget tests
>
> ## PT PR #348 Architecture
>
> The existing `orchestrator/frugality_router.py` and `orchestrator/gate.py` remain the policy chokepoint. This runner deliberately cannot choose a route: it rejects anything other than an already-approved `ResolvedRoute(tier=5, backend='openrouter')`.
>
> ## PT PR #348 Safety/defaults
>
> Paid execution is disabled by default. Offline/privacy policy wins over flag/key. Missing/expired/mismatched approval fails before egress. No fallback provider is selected by the runner.
>
> ## PT PR #348 Scope
>
> This is the Perpetua-Tools P4 companion to orama-system PRs #301/#302. It does not touch or redefine ORAMASYS methodology and does not introduce any P3/v2 scaffold.

**Commits:**

- `74ef4664` feat(p4): add bounded Tier-5 pipeline policy
- `9b613db5` feat(p4): add governed Tier-5 pipeline runner
- `dc7b7078` test(p4): enforce deny-before-egress and bounded Tier-5 execution

---

## The Senior's disposition (for cross-reference only — see PT PR #350 for the full ledger)

Per the Senior Systems Architect's integration reply: Apprentice-02's PT design (#348) was evaluated as "a parallel approval abstraction" alongside #347 and the Senior's own #349/#350 and was not selected as the final architecture, even though — like Apprentice-01 — it correctly kept `frugality_router.py`/`gate.py` as the policy chokepoint rather than building a second router. On the orama-system side, Apprentice-02's independent MCP-readiness implementation and its explicit design-decision writeup (preserving the launcher-delegates-to-canonical-installer rule, keeping bootstrap fail-soft) contributed to the shared cross-platform MCP readiness boundary and M3 human-authority boundary in the final #303/#305, credited alongside Apprentice-01's parallel contributions rather than in isolation. Neither #301, #302, nor #348 was merged, closed, or deleted.
