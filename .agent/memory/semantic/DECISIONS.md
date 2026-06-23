# Major Decisions

> Record architectural or workflow choices that would be costly to re-debate.
> Use this template for each entry:

## YYYY-MM-DD: Decision title
**Decision:** _what was chosen_
**Rationale:** _why, in one or two sentences_
**Alternatives considered:** _what else was on the table and why rejected_
**Status:** active | revisited | superseded

## 2026-01-01: Four-layer memory separation
**Decision:** Split memory into working / episodic / semantic / personal rather than one flat folder.
**Rationale:** Each layer has different retention and retrieval needs. Flat memory breaks at ~6 weeks.
**Alternatives considered:** Flat directory (fails at scale), vector store (over-engineered for single user).
**Status:** active

## 2026-06-21: perpetua-core salvage port confirmed complete; push gate is hardware review

**Decision:** `oramasys/perpetua-core` salvage translation RC-1 is done — all 16 tasks committed, 73 tests green across 3 repos (`perpetua-core` 56, `oramasys` 5, `Perpetua-Tools` 12). The only remaining gate before merging `feat/salvage-plugins-rc1` → `perpetua-core` main is user end-to-end hardware review on Mac Ollama (`localhost:11434`) + Win LM Studio (`192.168.254.103:1234`). This is per the Push Policy in PROGRESS.md.

**Rationale:** PROGRESS.md at `oramasys/perpetua-core` HEAD (`56f2a6d`) shows every row `DONE`. All spec invariants verified in code: `PerpetuaState(BaseModel)`, `scratchpad: dict[str, Any]`, Python ≥3.11, engine 102 lines (≤80 soft cap exceeded by compile path — acceptable), `set_entry` + `compile` present, all 6 plugin ports landed (`tool_node`, `routing`, `validator`, `interrupt_guard`, `parallel`, `message`). Hypothesis property tests landed in `tests/property/`. Discovery layer ported verbatim from v1.

**Alternatives considered:** Treat as blocked / in-progress. Rejected — PROGRESS.md explicitly states "DONE march" with commit SHAs for every row.

**Status:** active

**Links:**
- Repo: https://github.com/oramasys/perpetua-core
- Spec: https://github.com/diazMelgarejo/orama-system/blob/main/docs/superpowers/specs/2026-05-17-salvage-translation-design.md
- Plan: `orama-system/docs/superpowers/plans/2026-05-17-salvage-translation-v1-discovery.md`
- PROGRESS.md: https://github.com/oramasys/perpetua-core/blob/feat/salvage-plugins-rc1/PROGRESS.md

## 2026-06-22: v2 repos adopt PyPA src-layout; why oramasys v2 is necessary now

**Decision:** Both v2 Python repos move to src-layout — `src/<package>/`, tests **inside**
`src/tests/`, thin `/bin` executables, minimal root (`README`/`LICENSE`/`pyproject`/`.gitignore`).
Merged to `main` and pushed: `perpetua-core 8c063f4` (62 tests), `oramasys 0f5ba2b` (5 tests).
`agate` left as-is (spec repo, no Python source). This is the structural half of the v2 thesis,
locked in now while the salvage RC-1 tree is small and green.

**Rationale:** v1-legacy (`diazMelgarejo/*`) tangled orchestration/state/policy/runtime in one
cluttered top-level. v2 is a clean-slate **microkernel split** — `perpetua-core` (kernel: state,
LLM/hardware policy, graph engine) ← `oramasys` (graph DSL + FastAPI surface), strict one-way
import boundary; PT stays L2 state authority, orama L3 stateless. Adopting clean structure "from
day one" is exactly the user's stated intent and prevents v2 re-accreting v1's mess. "At this
point" because RC-1 salvage is complete (73 tests across 3 generations); cheapest moment to lock
structure before further growth.

**Alternatives considered:** Flat package-at-root with tests at root (the prior state — rejected,
it is the clutter path v1 took). `tests/` outside `src/` per strict PyPA (rejected — user
explicitly specified tests inside `/src`). Defer restructure to post-merge (rejected — accretion
makes it costlier and contradicts the "from the beginning" intent).

**Status:** active

**Links:**
- Full narrative (intent, the AI interpretation gap, and how it was closed): [`docs/2026-06-22-oramasys-v2-intent-and-interpretation-gap.md`](../../../docs/2026-06-22-oramasys-v2-intent-and-interpretation-gap.md)
- Lessons (rendered): `.agent/memory/semantic/LESSONS.md` ids `2e154f1b55ab`, `d892d844cf60`, `0afc8c5f2778`, `a7374ba4b00d`
- Standards: orama `bin/orama-system/afrp/SKILL.md` (Intent-Verification trigger 3), `.../cidf/SKILL.md` (Target Verification), orama `docs/LESSONS.md` §2026-06-22

## 2026-06-21: Markdown numbered lists in SKILL.md must use explicit numbers, not lazy-1

**Decision:** All numbered steps in SKILL.md `## Procedure` sections must use explicit
sequential numbers (1, 2, 3...), never the Markdown lazy-1 convention (all steps as `1.`).

**Rationale:** Agent runtimes (Hermes, Codex, OpenCode) consume SKILL.md as raw text, not
rendered HTML. When all steps are `1.`, step-tracking and procedure parsing break silently.
Markdown auto-normalization is renderer-side only; raw consumers see the literal `1.`. Bug
introduced by a reformat pass in commit 8101984; fixed in 122d7d7 for 9 files.

**Alternatives considered:** Rely on renderer normalization — rejected because agent runtimes
read raw text. Add a custom Markdown plugin — rejected as over-engineering for a simple convention.

**Status:** active — consider adding a repo_hygiene.py check for all-1 procedure lists.

## 2026-06-23: Nested-branch multi-agent merge: simulate first, ask human, then combine

**Decision:** When merging nested branches produced by independent agents against a
moving main, the mandatory protocol is:
1. `git merge --no-commit --no-ff` both merges in sequence to enumerate ALL conflicts
   before touching any file.
2. Present every conflict to the human with both sides shown — never guess resolution.
3. Wait for explicit human direction (combine/take-ours/take-theirs/build-union).
4. Resolve all conflicts in a single pass using the directed strategy.
5. Push, wait for CI, then perform the official GitHub API merge.
6. Wait 10 minutes between merges for GitHub to recompute mergeable_state.
7. Confirm mergeable_state=clean before the second merge.

**Applied to:** PR #104 (codex/hermes-ecc-harness-skills) → PR #105 (experiment) → main.
11 conflicts resolved with combine-never-replace strategy. 0 content lost.

**Rationale:** Guessing conflict resolution in a multi-agent codebase leads to silent
content loss. The "combine-never-replace" directive from the human was clear and applicable
to all 11 conflicts — each one had a natural union resolution once the two sides were
inspected and compared systematically.

**Status:** active — this is the standard protocol for all multi-agent branch merges.

---

## 2026-06-23: CodeRabbit findings require root-cause analysis, not literal application

**Decision:** Never apply CodeRabbit suggestions literally without first asking
"what is the underlying invariant being violated?" Three categories:
(a) Surface patches — apply directly (duplicate sentences, stale flag names).
(b) Symptom flags — dig to root cause (NEEDS_REVISION→Execute was a symptom;
    root cause: failed final review must re-plan, not re-execute stale work).
(c) Architectural issues — require human judgment (trigger string routing,
    security gate ordering in check_commit_message.sh).

**Applied to:** PRs #104 and #105, 14 total findings, all fixed at root cause.

**Status:** active — applies to all future PR reviews.

---

## 2026-06-23: Version SSoT: src/orama_system/_version.py is the single source

**Decision:** orama-system version is now managed exclusively through
`src/orama_system/_version.py`. Bump procedure: edit that file only, then
`python3 scripts/sync_version.py` (25+ surfaces), then `pytest tests/test_version_docs.py`.
No manual edits to versioned surfaces. Historical docs are excluded intentionally.

**Applied to:** orama-system main, v1.1.0.0 standardized across all canonical surfaces.
**Status:** active.
