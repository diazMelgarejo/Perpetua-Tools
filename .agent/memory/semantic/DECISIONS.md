# Major Decisions

> Record architectural or workflow choices that would be costly to re-debate.
> Use this template for each entry:

## 2026-08-22: mcp-remote supply-chain pinning — status quo retained over 4 investigated alternatives

**Decision:** Keep `.codex/config.toml`'s `[mcp_servers.exa]` entry at version-pin-only
(`npx -y mcp-remote@0.1.43 https://mcp.exa.ai/mcp`). Do **not** add a scoped `.codex/package.json`
+ lockfile (Option A), vendor `mcp-remote` as a git submodule (Option 1), route it through an
adapted Exa-daemon Unix-socket bridge (Option 2), or hand-roll a checksum-verification wrapper
script (Option 3). Full investigation, comparison table, and mermaid diagrams:
`.agent/memory/working/2026-08-22-mcp-remote-supply-chain-pinning-options-debate.md`.

**Rationale:** Every alternative that actually pins `mcp-remote`'s transitive dependencies
(`open`, `undici`, `express`, `strict-url-sanitise`) requires a manifest+lockfile living
*somewhere* in the repo — there is no variant of deterministic dependency resolution without
one. Option A was implemented, verified working end-to-end, then explicitly rejected by the
operator on two grounds: (1) location — a second npm project inside `.codex/`, a config
directory; (2) footprint — a new lockfile + `node_modules` tree in this repo at all. The three
alternatives explored afterward each collapse into the same requirement or solve a different
problem: submodule-vendoring needs a `pnpm`+`tsup` build toolchain just to reproduce what npm
already publishes pre-built; the Exa-daemon pattern multiplexes processes but pins nothing (its
own backend call is itself unpinned `npx -y exa-mcp-server`) and adds Windows `AF_UNIX`
portability risk; a checksum wrapper only covers the top-level tarball, leaving the transitive
tree unpinned while duplicating lockfile mechanics with less tooling support (no `npm audit`,
no Dependabot). npm's built-in `dist.integrity` verification (TLS + signed sha512 per fetch)
already protects the pinned top-level package — the residual gap is reproducibility, not an
unguarded tampering vector.

**Alternatives considered:** scoped `.codex/package.json` + lockfile with `--no-install`
enforcement (rejected — location + footprint); git submodule vendoring matching
`vendor/agentic-stack` convention (rejected — needs new `pnpm`+`tsup` toolchain for equal
footprint); adapted Exa-daemon Unix-socket bridge (rejected — wrong problem, solves process
sharing not pinning, and its own backend is also unpinned); hand-rolled integrity-checksum
wrapper script (rejected — reinvents `package-lock.json`, worse, and still leaves transitive
deps unpinned).

**Status:** resting state, not a hard close. CodeRabbit offered (twice) to open a GitHub
tracking issue for the full lockfile-backed fix on this PR's review thread — that issue has
**not** been created yet; still awaiting explicit operator go-ahead. If revisited, read the
full working doc first — each option was investigated concretely (upstream tags cloned, daemon
source read in full, npm registry metadata fetched), not just discussed abstractly.

---

## 2026-08-21: SSRF Layer-2 pinned transport, 3-layer architecture & frugal Python path reuse

**Decision:** Land Layer-2 connection-time IP pinning transport (`src/utils/ssrf_pinned_adapter.py`), unit tests (`tests/test_ssrf_pinned_adapter.py`), and endpoint hardening checklists (`docs/plans/2026-08-21-pt-endpoint-hardening-checklists.md`) on `Perpetua-Tools` branch `fix/pt-standards-convergence-20260818` (PR #359), with companion docs updated in `orama-system` on `fix/oramasys-standards-convergence-20260818` (PR #321). (A stray `orama-system` branch, `fix/markdownlint-doc53-ci-20260820`, briefly carried two follow-up commits before being merged into the canonical branch and deleted 2026-08-21 — see the 2026-08-21 CodeRabbit remediation entry below.)
Pre-flight string/IP-literal validation remains Layer 1 SSOT in `src/utils/ssrf_fetch_policy.py`. Layer 2 resolves DNS once, validates all A/AAAA records against Layer 1 policy, dials the pinned IP literal directly via custom connection pool, retains TLS SNI and Host header to original hostname, and mandates manual redirect re-validation (`ssrf_request`).
Frugal Python path reuse strategy: zero external dependencies (`dssrf`, archived `safeurl-python` rejected); dual-try module path resolution (`src.utils.*` / `utils.*`) for robust cross-environment portability without host environment pollution.

**Rationale:** Research in 2025-2026 CVEs (CVE-2026-27826, CVE-2026-27795) proves pre-flight string validation cannot prevent DNS-rebinding TOCTOU or 30x redirect bypasses without transport-level socket pinning and redirect isolation.

**Alternatives considered:** Resolve DNS in pre-flight Layer 1 (rejected — reintroduces TOCTOU gap); adopt third-party denylist packages (rejected — CVE churn and supply chain bloat); combine outbound SSRF with LAN model discovery (rejected — opposite security polarities).

**Status:** active

**Links:**
- Working memory: `.agent/memory/working/SESSION_SYNTHESIS_SSRF_LAYER2_AND_FRUGAL_PYTHON_REUSE_2026-08-21.md`
- Adapter: `src/utils/ssrf_pinned_adapter.py`
- Tests: `tests/test_ssrf_pinned_adapter.py`
- Checklists: `docs/plans/2026-08-21-pt-endpoint-hardening-checklists.md`
- Orama plan: `orama-system:docs/v2/plans/2026-08-20-ssrf-defense-in-depth.md`

## 2026-08-21: PT PR #359 CodeRabbit remediation + orama PR #321 branch consolidation

**Decision:** Fixed all 8 findings from CodeRabbit review #4993577985 on PT PR #359: the nitpick
(`tests/test_ssrf_pinned_adapter.py` `test_hook_endpoint_policy` only tested loopback rejection,
which both the Layer-1 checker and the Layer-2 fallback satisfy — added a `url_checker` assertion
on Layer-1's fail-closed-on-unresolved-hostname behavior, which the fallback lacks), plus 7
actionable comments: a Major-severity gap where `ssrf_request()` trusted any caller-supplied
`requests.Session` without verifying `SSRFPinnedHTTPAdapter` was mounted (`src/utils/ssrf_pinned_adapter.py`,
fixed with `_require_pinned_adapter()`); `orchestrator/connectivity.py` routing local Ollama/LM
Studio/MLX health checks through the same deny-by-default `ssrf_request()` as cloud vendor checks
(split into `_probe` / `_probe_local`); `orchestrator/orama_bridge.py`'s async HTTP fallback using a
bare `httpx.AsyncClient` instead of the sync path's `ssrf_request` (fixed via `asyncio.to_thread`);
two Ruff nitpicks in the test file (S104 suppression, RUF012 mutable class state); a stale repo-scope
claim in the session synthesis working doc; and a Layer-1 checklist doc that under-named its own
module list and vendor allowlist. Also consolidated orama-system PR #321: two parallel agent sessions
had pushed follow-up commits to different branches (the canonical `fix/oramasys-standards-convergence-20260818`
and a stray `fix/markdownlint-doc53-ci-20260820`) — merged via Mode-4-synthesize (per
`oramasys-method`'s `integrative-merge.md`) since both sides had independently reflowed the same
paragraph of `docs/v2/53-maestro-swarm-v2-redesign-critique.md` for MD013 compliance, and the stray
branch's own line-wrap commit had left an orphaned one-word line that the other branch's wrap fixed
cleanly; pushed the synthesized result to the canonical branch, then deleted the stray branch (its
own PR #322 was already closed) both locally and on `origin`.

**Rationale:** Standard PR-review remediation, done as a full batch rather than fixing only the
originally-requested nitpick, since the review had already surfaced the remaining 7 findings and
leaving them open would mean re-deriving the same context in a follow-up session. The branch
consolidation followed the repo's own naming convention (`fix/pt-standards-convergence-20260818` in
PT ⇄ `fix/oramasys-standards-convergence-20260818` in orama-system) rather than leaving two
divergent branches carrying the same PR's follow-up work.

**Alternatives considered:** Fix only the originally-requested nitpick and leave the other 6 review
findings for a later session (rejected — the review had already surfaced them, and per
`lesson_502211a1be56`'s handwaving-costs-more-later doctrine, deferring a known, already-surfaced
finding just relocates the cost); pick one of the two orama-system branches wholesale instead of
synthesizing (rejected — each branch had independently-valid content the other lacked, and the
stray branch's own wrap fix was strictly better for one paragraph).

**Status:** active

**Links:**
- PT PR: https://github.com/diazMelgarejo/Perpetua-Tools/pull/359
- Review: https://github.com/diazMelgarejo/Perpetua-Tools/pull/359#pullrequestreview-4993577985
- Orama PR: https://github.com/diazMelgarejo/orama-system/pull/321
- Adapter fix: `src/utils/ssrf_pinned_adapter.py` (`_require_pinned_adapter`)
- Connectivity split: `orchestrator/connectivity.py` (`_probe` / `_probe_local`)
- Async bridge fix: `orchestrator/orama_bridge.py`
- New lessons: `.agent/memory/semantic/lessons.jsonl` (ids `b65c806e748f`, `f6b92e2bd7f5`, `151e23263250`, `53c89f8a214d`, `99ff520076a7`)

## 2026-08-21: PT PR #359 continued CodeRabbit autofix cycle — CI regressions, a wrong deferral, and 2 open follow-up-issue offers

**Decision:** Continued the same PR #359 remediation round through several more automated CodeRabbit
review cycles. Three distinct outcomes worth recording:

1. **Real CI regressions, not stale notifications.** After the SSRF Layer-2 rewiring
   (`orama_bridge.py`'s async fallback moved from a bare `httpx.AsyncClient` to
   `asyncio.to_thread(ssrf_request, ...)`), `lint-and-test` went red with 7 failures across
   `tests/test_orama_bridge.py`, `tests/test_orama_mcp_client.py`, and my own earlier
   `tests/test_ssrf_pinned_adapter.py::test_hook_endpoint_policy` fix. Initially treated a CI-monitor
   failure notification as referring to a stale/superseded run without checking the actual commit SHA
   the run was against — it was current. Root causes: (a) two tests mocked `orama_bridge.httpx.post`,
   which stopped existing once `import httpx` was removed; (b) five tests mocked `httpx.AsyncClient`,
   which the async fallback stopped calling at all, so the mock silently stopped intercepting and the
   fallback made a REAL SSRF-pinned request to the test's own `localhost` target, which the real
   deny-by-default policy correctly rejected (`AddressDenied: blocked address: ::1`) — a
   security-correct failure that read as an unrelated bug; (c) a dual-import class-identity bug in my
   own test: `hook_endpoint_policy()` resolves `SSRFPolicyError` via `src.utils.ssrf_fetch_policy`
   first in this CI environment, but the test imported the same-named class from `utils.ssrf_fetch_policy`
   — two distinct class objects for the identical class body, so `pytest.raises` never matched. Fixed
   by mirroring hook_endpoint_policy's own dual-try resolution order inside the test.
2. **A wrong out-of-scope deferral, corrected on reviewer pushback.** Initially deferred a
   `.codex/config.toml` unpinned `npx -y mcp-remote` finding as "pre-existing config, not touched by
   this PR's diff" without checking `git log` — CodeRabbit correctly cited commit `1d8b0097` (this
   same PR) as the one that introduced that exact invocation. Corrected: pinned to `mcp-remote@0.1.43`
   (verified against the live npm registry) — a real, meaningful mitigation, but not the full
   lockfile-backed + `--no-install`-enforced fix CodeRabbit originally asked for.
3. **Two genuine remaining gaps, CodeRabbit twice offered to open tracking GitHub issues for —
   awaiting operator decision, not yet created:**
   - A fully lockfile-backed `mcp-remote` dependency (reviewed npm package + lockfile entry + local
     `--no-install` invocation) for `.codex/config.toml`'s exa MCP server, superseding the version-pin
     partial fix above. Thread: `https://github.com/diazMelgarejo/Perpetua-Tools/pull/359#discussion_r3821600945`
     (comment id `3834333361` is CodeRabbit's explicit offer).
   - Edge-case test coverage for the git-stash TDD verification technique recorded in the append-only
     graduated candidate `.agent/memory/candidates/graduated/8466d1718c00.json` — specifically
     covering staged, partially-staged, and untracked production edits during the selective-stash
     workflow, not just the fully-unstaged case. Thread: `https://github.com/diazMelgarejo/Perpetua-Tools/pull/359#discussion_r3826927036`.
   Neither issue has been created — issue creation is public, persistent content and was treated as
   requiring explicit operator sign-off rather than autonomous action from an automated review-reply
   loop, consistent with how PR body edits are gated on this repo (see `lesson_a8f3c2e91d04` /
   PR-body append-only doctrine — analogous reasoning, different surface).

**Rationale:** Records the exact failure mode of the "push once, then CI-monitor reports async" workflow —
a fix commit that *looks* complete based on manual reasoning (no Python interpreter was available in
this session to actually run pytest) can still regress tests it didn't directly touch. Also records
that an automated reviewer's factual pushback on a deferral claim should be independently re-verified
against git history, not just re-asserted or silently accepted.

**Status:** active — 2 follow-up issues pending operator go-ahead

**Links:**
- PT PR: https://github.com/diazMelgarejo/Perpetua-Tools/pull/359
- CI regression fixes: `5743ee42` (tests), `f3e67e84` (`.codex/config.toml` pin correction)
- New lessons: `.agent/memory/semantic/lessons.jsonl` (ids `9e9515189f99`, `c11c64cbcc20`, `b169a367b452`)

## 2026-08-03: PR-body grant can-6 follow-up — scrub_dsstore sync + v2.1+ deferral doctrine

**Decision:** Batch H on paired branches orama #260 / PT #320. Add `scrub_dsstore.sh` to
guard-sync manifest; guard githooks with `-x`; land can-6 grant hardening and tests without
expanding MVP scope. All plan findings **not implemented in MVP v2** (ENG-6 per-PR lock,
ENG-4 fail-closed providers, DX-5 extended crash recovery, WebAuthn/MCP, full doctrine sweep)
are **v2.1+ or later** — security-sentinel orbit, not merge blockers for MVP.

**Rationale:** PT pre-push warned on missing scrub script while hook always invoked it.
CodeRabbit can-6 caught secure-write and test gaps. Reviewers must not treat deferred items as
open MVP bugs.

**Alternatives considered:** Implement ENG-6 lock in MVP (rejected — reconcile covers common
case); fail-closed secret provider in shell (rejected — v2.1 provider interface).

**Status:** active (pending merge of #260 and #320)

**Links:**

- Follow-up: `.agent/memory/working/PR_BODY_GRANT_CAN6_SCRUB_FOLLOWUP_2026-08-03.md`
- Saga: `.agent/memory/working/PR_BODY_GRANT_HMAC_MVP_SAGA_2026-08-02.md` (Batch H)
- Plan deferrals: orama `docs/plans/2026-08-02-pr-body-grant-security-remediation.md`
- v2.1 orbit: orama `docs/v2/51-security-sentinel-orbit-passkey-mcp.md`

## 2026-08-02: PR-body grant v2 remediation — replay state machine + honest MVP boundary

**Decision:** Close remediation review F1–F7 on paired branches orama #260 / PT #320. HMAC grant uses fixed-order UTF-8 canonical payload bytes; append flow is `reserve` → `append-pr-body.sh` (the guarded wrapper, performs the remote `gh pr edit` internally) → `mark-applied` → `consume` with `reconcile` for crash recovery. Same-user Keychain HMAC is **escalation control**, not proof of human presence. Human override is `operator-grant-v2` ack file, not `CURSOR_PR_BODY_HUMAN_OVERRIDE_ACK` env exports.

**Rationale:** v1 plaintext ack and env override were forgeable; consume-before-remote left replay window; plan and memory had to stop claiming “signed human capability.” PT CI failed on ephemeral path literals in saga chronicle — tracked `.agent` memory follows same hygiene as workstation paths.

**Alternatives considered:** Consume nonce before remote edit (rejected — replay risk); WebAuthn in orama scripts (rejected — v2.1 sentinel orbit).

**Status:** active (pending merge of #260 and #320)

**Links:**

- Saga: `.agent/memory/working/PR_BODY_GRANT_HMAC_MVP_SAGA_2026-08-02.md`
- Decisions JSONL: `.agent/memory/working/PR_BODY_GRANT_HMAC_DECISIONS_2026-08-02.jsonl`
- Plan: orama `docs/plans/2026-08-02-pr-body-grant-security-remediation.md`
- CodeRabbit wave: `.agent/memory/working/CODERABBIT_REVIEW_WAVE_4835024659_4835288649_2026-08-01.md` (Batch G)

## 2026-07-29: Periscope modernization — PR #20 over PR #17; never synthetic SHA replay

**Decision:** Close periscope PR #17 without merge. Preserve `cursor/agentsview-modernization-3way-f559` as a permanent bad-example branch. Integrate via PR #20 (`cursor/agentsview-purified-onto-kenn-f559`): original `kenn-io/agentsview` SHAs + 9 Periscope-unique cherry-picks, byte-identical tree to PR #17 tip.

**Rationale:** PR #17 had correct product tree but replayed ~769 upstream commits under synthetic SHAs from ancient merge-base, producing an unreadable 2,169-file / 769-commit PR graph. Purified integration inherits real upstream ancestry and exposes only the fork delta (816 files / 9 commits). Never synthesize SHAs except security expunge (keys, identities, workspaces, paths, doxxing).

**Alternatives considered:** Merge PR #17 as-is (rejected — wrong ancestry, unreviewable graph); delete bad branch after close (rejected — preserve as anti-pattern curriculum).

**Status:** active

**Links:**

- periscope doc: `docs/2026-07-28-AgentsView+Periscope-Fresh.md` addendum on `merged`
- PT memory: `.agent/memory/working/PERISCOPE_MODERNIZATION_PURIFIED_INTEGRATION_2026-07-29.md`
- orama AFRP: `bin/orama-system/afrp/failure-modes.md` §8
- orama CIDF: `bin/orama-system/cidf/references/integrative-editing-examples.md` §10

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

- Repo: <https://github.com/oramasys/perpetua-core>
- Spec: <https://github.com/diazMelgarejo/orama-system/blob/main/docs/superpowers/specs/2026-05-17-salvage-translation-design.md>
- Plan: `orama-system/docs/superpowers/plans/2026-05-17-salvage-translation-v1-discovery.md`
- PROGRESS.md: <https://github.com/oramasys/perpetua-core/blob/feat/salvage-plugins-rc1/PROGRESS.md>

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

## 2026-06-24: Hermes memory sync requires path sanitization before committing

**Decision:** When integrating Hermes-generated memory into tracked .agent/memory/ files, always sanitize absolute workstation paths before committing. Hermes runs on the physical workstation and naturally includes real paths in its memory outputs. These must be converted to relative paths (../../) or env vars ($REPO_ROOT, $OPENCLAW_ROOT) before they enter tracked files.

**Evidence:** 2026-06-23-memory-update-01 contained `<workspace-root>` — this violates LINT-006 and the repo's own anti-doxxing lesson. The uLtrathink spelling anchor was preserved; the absolute path was replaced with env var guidance.

**Status:** active.

---

## 2026-06-24: GitHub 'merged' status does not guarantee content on main branch

**Decision:** After any GitHub PR merge, always verify with `git diff origin/main...origin/<branch>` that the content is actually present. PR #131 was closed as 'merged' on GitHub but its content was not on main — this was discovered during the post-merge sweep.

**Causes:** Force-pushes, squash merges to non-main bases, and GitHub's cached merge state can all produce a 'merged' label on a PR while the target branch has diverged.

**Status:** active — add to pre-session checklist.

---

## 2026-06-24: Optimization priorities for both repos

**L1 (Blocking):** perpetua-core hardware review gate → v0.2.0-alpha → Phase 3
**L2 (Critical):** orama-system store.py TOCTOU lock (atomic O_CREAT|O_EXCL)
**L3 (Systemic):** repo_hygiene.py linter rules — all-1 procedure lists, (deprecated) in triggers, hermes -z in markdown
**L4 (Efficiency):** GitHub Action to auto-detect unresolved PR comments post-merge
**L5 (Architectural):** encode combine-never-replace conflict strategy in AGENTS.md

## 2026-06-24: Duplicate parsers must be eliminated when the canonical upgrades

**Decision:** When `src/utils/hardware_policy.py` (or any canonical module) receives a new capability (alias merging, _normalize_policy), immediately grep for other files implementing the same logic (`_simple_policy_parse`, `_forbidden`, etc.). Duplicate parsers silently diverge — the CLI produces different results than the Python API.

**Evidence:** PT PR #131 — hardware_policy_cli.py had its own copy of _simple_policy_parse that missed alias enforcement added in PR #130. Fixed by delegating to canonical `load_policy()`.

**Status:** active.

---

## 2026-06-24: GitHub Actions outputs are always strings — quote all comparisons

**Decision:** In GitHub Actions YAML, all `steps.<id>.outputs.*` values are strings, regardless of what the Python/bash step writes. Comparisons must be: `!= '0'` (not `!= 0`), and always guard the empty case: `!= '0' && != ''`.

**Evidence:** post-merge-review-sweep.yml had `unresolved_count != '0'` — this is a string comparison in the YAML expression engine; the literal string '0' is never equal to integer 0 via `!=`. Fixed to double-guard.

**Status:** active.

---

## 2026-06-24: Never pass secrets as CLI argv — always use stdin/env/file

**Decision:** Shell commands that pass secrets as positional arguments (e.g. `security add-generic-password -w $secret_value`) expose them in `ps aux`, `/proc/<pid>/cmdline`, shell history, and system audit logs. All secret passing must use: (a) stdin via heredoc/pipe, (b) `os.environ` with gitignored `.env`, or (c) restricted-permission files.

**Evidence:** openclaw-add-secret SKILL.md had `security add-generic-password -w "$secret_value"`. Fixed via `store_keychain_secret.sh` that reads from stdin.

**Status:** active.

---

## 2026-06-24: Knowledge depth must match the consumption point

**Decision:** When promoting a protocol into skills, the content depth at each location must match how that location is consumed:

- Reference doc (loaded on demand) → full detail, code snippets, all edge cases
- SKILL.md section (loaded when doing related work) → quick summary + link to reference
- Step in a checklist (always visible) → 3-5 line trigger + link
- Wiki page (discovery layer) → compact table + invariants block + cross-links

**Evidence:** Multi-agent merge protocol distributed across 4 files (`3ae45b5`, `72d0fbc`) using this pattern. Each file useful at its level without requiring full detail to be loaded.

**Status:** active.

---

## 2026-06-24: Cross-repo Hermes hardware policy — one consumption path, three harnesses

**Decision:** Windows Hermes must consume Perpetua-Tools hardware policy through the same
YAML → `hardware_policy.py` → `hardware_policy_cli.py` chain as Mac/Linux OpenClaw. orama-system
wires harness entrypoints only (`platform/windows/start.ps1 --hardware-policy`, `pt-hardware-policy`
thin skill); it never re-declares NEVER lists or duplicate parsers in markdown.

**Rationale:** Parallel orchestrators each see LM Studio `/v1/models` including LAN-proxied models.
Independent affinity inference causes OOM and double-barrel GPU damage. Platform roles invert on
Windows (`windows_only` allowed at localhost:1234) but the policy file is shared.

**Evidence:** orama-system PR #107; Perpetua-Tools PR #134; plan
`docs/plans/2026-06-24-hermes-windows-hardware-policy-walkthrough.md`.

**Status:** active — merge orama #107 + PT #134 together; live Windows walkthrough deferred.

---

## 2026-06-24: Workspace-agnostic path resolution for cross-repo skills

**Decision:** Skills and thin Hermes wrappers must never hardcode sibling checkout paths like
`../Perpetua-Tools`. Resolution order: env vars (`PERPETUA_TOOLS_ROOT`, `PERPETUA_TOOLS_PATH`,
`PT_HOME`) → `.paths`/`.paths.ps1` → `OPENCLAW_HOME/Perpetua-Tools` → sibling discovery from git
toplevel. Prefer launcher gates over direct CLI paths.

**Evidence:** CodeRabbit PR #107; `workspace-path-resolution.md`; `start.sh`/`start.ps1` parity fix.

**Status:** active.

---

## 2026-06-24: platform/windows scripts live two levels below repo root

**Decision:** `platform/windows/start.ps1` and `install.ps1` set `$RepoRoot` via
`Join-Path $ScriptDir '..\..'`. All repo-root-relative docs use `.\platform\windows\start.ps1` —
there is no `.\windows\` folder at repo root.

**Evidence:** CodeRabbit PR #107; incorrect `$RepoRoot` broke `.paths.ps1` generation.

**Status:** active.

---

## 2026-06-26: AlphaClaw CI fixes (ca5e3f28) stay in L1 — no PT migration

**Decision:** The 2026-06-26 AlphaClaw CI repair (`ca5e3f28` on `feature/MacOS-post-install`) remains entirely in AlphaClaw. Do not copy `bin/alphaclaw.js`, `lib/server/system-cron.js`, or route test fixes into Perpetua-Tools.

**Rationale:** `docs/MIGRATION.md` tri-repo contract: AlphaClaw (L1) owns npm install, macOS binary placement, gateway, and `openclaw.json`. PT (L2) bridges via HTTP+CLI only. Gate 2 PT migration targets are `lib/mcp/` and `lib/agents/` copies only.

**Alternatives considered:** Duplicate fixes into PT `packages/` — rejected (wrong layer, violates strangler-fig HTTP-only rule).

**Status:** active

**Links:** AlphaClaw CI [28086747962](https://github.com/diazMelgarejo/AlphaClaw/actions/runs/28086747962) → [28206351466](https://github.com/diazMelgarejo/AlphaClaw/actions/runs/28206351466); commit `ca5e3f28`

---

## 2026-06-26: agentic-stack submodule at vendor/agentic-stack (like ecc-tools)

**Decision:** Move `packages/agentic-stack` → `vendor/agentic-stack`. Add `scripts/git/agentic-stack-submodule-sync.sh` and `agentic-stack-vendor.md`. PT `.agent/` remains the live customized brain; submodule is upstream reference for install/upgrade per [agentic-stack CHANGELOG](https://github.com/codejunkie99/agentic-stack/blob/master/CHANGELOG.md). orama `start.sh` symlinks `lib/shared/agentic_stack` from `$PT_DIR/vendor/agentic-stack`.

**Rationale:** Parity with `vendor/ecc-tools` formalization — one `vendor/` namespace for external brains, documented bump workflow, CI-friendly `git submodule update --init`.

**Alternatives considered:** Keep `packages/` path — rejected (inconsistent with ecc-tools). Copy `.agent/` from submodule on every clone — rejected (PT memory is customized and must not be overwritten).

**Status:** active

---

## 2026-06-26: discover.py hash vs runtime IP split (PR #108)

**Decision:** `discover.py` uses LAN IPs for `hash_endpoints`, `patch_devices_yml`, and discovery state; runtime `patch_openclaw_json` keeps `localhost` for Windows-local LM Studio. `patch_models_yml` skips loopback `win_ip` (parity with `patch_devices_yml`).

**Rationale:** Mutating `endpoints["win"]` to LAN IP before `patch_openclaw_json()` breaks `lmstudio-win` on Windows hosts. CodeRabbit r3480506247 caught asymmetric loopback handling in `patch_models_yml`.

**Status:** active

---

## 2026-06-26: Agentic-stack union-merge — dry-run first, Gbrain canonical, Brain blocked

**Decision:** After `vendor/agentic-stack` submodule init, run `scripts/git/install-agentic-stack.sh` (idempotent) then `agentic-stack upgrade --dry-run` before harmonizing PT `.agent/`. Union-merge upstream skeleton into project-owned `.agent/` at runtime — never commit blended output into `vendor/`. Block upstream Brain (`brain_bridge.py`, `agentic-stack brain *`) until PT ships dual-backend bridge; Gbrain via gstack is canonical RAG. Future: `agentic-stack gbrain *` mirrors `brain *`.

**Rationale:** Same patch-on-top model as orama `openclaw-skills` (submodule + local extensions). Prevents upgrade from overwriting graduated lessons, gstack hooks, and hardware-policy memory. Documented in [orama doc 41](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/41-agentic-stack-gstack-gbrain-memory-blend.md).

**Harnesses:** Windows — Antigravity CLI/IDE, Hermes, Cursor, Codex, Claude Desktop; Linux/macOS — OpenClaw, Claude CLI/Desktop, Cursor.

**Status:** active

---

## 2026-06-26: xAI Grok `agent` vs Cursor `cursor-agent` — PATH collision

**Decision:** xAI Grok Build ships `~/.grok/bin/agent` (Grok TUI). Cursor ships `cursor-agent`. Never invoke bare `agent` in scripts or skills — always `cursor-agent` for Cursor background agents. Document both binaries in harness SKILL frontmatter.

**Rationale:** xAI chose generic `agent` binary name; operators with both Grok and Cursor hit wrong CLI on PATH. PR #108 `cursor-agent` skill disambiguates.

**Status:** active — lesson `lesson_f4b012e5339e`

---

## 2026-06-26: Windows `.cmd` CRLF enforcement

**Decision:** All tracked `.cmd`/`.bat` files use CRLF. Python writers open `'wb'` and join with `\r\n`. Declare `*.cmd text eol=crlf` in `.gitattributes`.

**Rationale:** PR #108 `gstack-brain-sync.cmd` LF-only incident — cmd.exe silent failure on Hermes Windows.

**Status:** active — lesson `lesson_bcc6a5141f56`

---

## 2026-06-27: Pre-v2 security hardening — Linux tiers ship; Mac/Win E2E gates T5 freeze

**Decision:** Ship all Linux-runnable security tiers (T1–T4) on matching branch `cursor/security-hardening-pre-v2-c4ae` in both repos at version `1.1.1.0`. Block T5 (git tags `v1.1.1`, GitHub release, `oramasys/v2-foundation` branch) until live Mac + Windows 11 E2E passes (`start.sh`, Ollama probes, `LM_STUDIO_WIN_ENDPOINTS`, hardware-policy harness, keychain).

**Rationale:** Cloud VM cannot satisfy Ollama hard-requirements or Win LM Studio LAN topology. Platform schedule table in `orama-system/docs/plans/2026-06-27-security-hardening-pre-v2.md` documents which tiers are 🐧 vs 🍎/🪟.

**Alternatives considered:** Tag freeze from cloud without E2E — rejected (fail-open on real hardware affinity and endpoint probes).

**Status:** active — PRs orama [#113](https://github.com/diazMelgarejo/orama-system/pull/113), PT [#154](https://github.com/diazMelgarejo/Perpetua-Tools/pull/154); lessons `lesson_a0d29898cd65`, `lesson_e45608de48c0`, `lesson_34bb51037fce`, `lesson_1171086a7740`, `lesson_2abff9b4e522`

---

## 2026-06-27: PR descriptions are append-only (integrative-merge)

**Decision:** PR titles and bodies are historical records. Agents MUST NOT replace an existing PR summary with a follow-up job description. New work (CodeRabbit fixes, merge notes, CI status) is appended in a `## Follow-up:` section below the original scope.

**Rationale:** PT #154 incident — full pre-v2 security hardening summary was overwritten with CodeRabbit-only notes, erasing purpose, tier table, hardware policy, integrative merges, and E2E gates. Same additive rule as `LESSONS.md` and oramasys-method `integrative-merge.md`.

**Status:** active — lessons `lesson_3b13ab0a45d4`, `lesson_257a631cbfd3`; episodic gold nuggets `PR154-summary-append-only-gold-nugget`, `PR158-synthesize-mode-gold-nugget`

## 2026-06-27: Branch triage uses tree-twin scan, not merge-base counts

**Decision:** After any suspected `main` rewrite, classify local branches with
`scripts/git/reanchor_scan.sh` + `git cherry -v`, not `git merge-base` failure or
ahead/behind counts alone. Save a markdown catalog
(`.agent/memory/working/BRANCH_CATALOG_COMPLETE_<date>.md`) before rebase, delete, or
history surgery.

**Rationale:** 2026-06-27 triage misclassified `cursor/critical-bug-investigation-0df5`
as unrelated orphan (647 behind); tree-twin showed tip byte-identical to `ad702c5` on
`origin/main` — zero `+` cherry commits. Naive metrics waste rebase effort and risk
destroying branch identity.

**Alternatives considered:** `git rebase origin/main` on all unmerged heads — rejected
for rewrite-boundary branches; flatten to `origin/main` — rejected per git-history-surgery
non-negotiables.

**Status:** active — catalog `.agent/memory/working/BRANCH_CATALOG_COMPLETE_2026-06-27.md`;
skills: orama `git-history-surgery` → `reanchor-after-rewrite.md`, PT `scripts/git/reanchor_scan.sh`

---

## 2026-06-27: TDD commit-msg hook + Playwright defer

**Decision:** Enforce web/src TDD pairing via scripts/git/check_tdd_commit.sh on commit-msg (not pre-commit); defer Playwright E2E until Vitest RC-1 gate merges to orama main.
**Rationale:** Pre-commit lacks commit message for tdd-skip escape hatch. E2E is out of RC-1 minimum; Vitest 16-test gate must land first.
**Alternatives considered:** Pre-commit only (rejected — no tdd-skip); Playwright in same PR (rejected — scope).
**Status:** active

## 2026-07-13: Post-Review Micro-Remediation Pattern promoted to shared doctrine

**Decision:** For post-review remediation on any open PR, follow the 6-phase Post-Review
Micro-Remediation Pattern: Freeze (PR branch only) → Root-cause clustering (fix the
abstraction, not each comment) → Branch discipline (cohesive commits, append not replace
PR narrative) → Integration (safety ref before any reset; ancestry reset over revert
chains; re-evaluate rebase necessity) → Verification (every finding fixed/superseded/
documented, never silent) → Closure (merge only after approval).
**Rationale:** Evolved through trial and error across PT PR #205/#206 (multiple review
rounds, a rogue-commit incident on main, a branch reset, a follow-up review). Generalizes
across code review, git workflow, multi-agent coordination, AutoResearch, and orchestration.
**Alternatives considered:** Ad-hoc per-incident cleanup (rejected — no mechanical
attribution, repeat incidents); revert chains for post-merge fixes (rejected — complicates
reconciliation vs. a single auditable ancestry reset).
**Status:** active — canonical doc `bin/orama-system/references/post-review-micro-remediation.md`; wired into 7 orama skills (agent-methodology,
code-review, git-history-surgery, gstack, skillify, hermes-harness, mcp-orchestration).

---

## 2026-07-13: Git author identity is not a reliable human-vs-agent signal

**Decision:** When investigating "who did this" in git history, do not treat a familiar
git author identity (e.g. `cyre <owner Gmail identity>`) as proof of human
authorship. Autonomous agents (AutoResearcher via `orchestrator/autoresearch_bridge.py`,
and any other agent committing through this stack) inherit whatever git identity is
locally configured — their commits are indistinguishable from human commits by author
field alone.
**Rationale:** `.github/workflows/pr206-final-doc-placeholder-fix.yml` (created and
self-deleted 74 seconds apart, 2026-07-12 21:46-21:47) was initially misattributed to a
benign human self-cleaning process based on its git author identity. Confirmed by the
user: it was created by a rogue AutoResearcher agent run, not a human.
**Alternatives considered:** Trusting git author field as sufficient forensic evidence
(rejected — proven wrong by this incident).
**Status:** active — future "who/why" investigations should cross-check autonomous-agent
activity logs (e.g. AutoResearcher's own state/heartbeat records) alongside git log.

---

## 2026-07-26: OpenClaw MERGE-10 fleet retrofit — retrofit live workspaces, not parallel fleet hub

**Decision:** Materialize Oramasys/Raft multi-agent design by **retrofitting** existing OpenClaw
agent workspaces (17 agents in `openclaw.json`) with integrative merge (append SOUL/GOALS overlays,
preserve oramaclaw blocks). Fleet org metadata lives in **main workspace**
`${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace/docs/oramasys/` (CROSSREF, REGISTRY, personas) —
**not** a separate `~/.openclaw/fleet/` tree. Promotion to `orama-system` bin/agents (PLAN-08) waits
for M3 dry-run pass.

**Rationale:** PLAN-09 fleet hub would duplicate infrastructure and orphan generic OpenClaw
templates. MERGE-10 + EDITED-03 fold keeps stable `openclaw_id`s, adds anti-loss CROSSREF spine,
and gates orama git edits until operator validates Glen→Rourke→Vera chain.

**Alternatives considered:** `~/.openclaw/fleet/` central hub (PLAN-09 — rejected); wholesale SOUL
replace (rejected — integrative merge); Sage as default reviewer for Cole/Penn (rejected post-
Antigravity — Vera universal, Sage optional analyzer).

**Status:** active — executed in operator local OpenClaw state 2026-07-26; orama/PT git promotion pending.

**Links:**

- PT playbook: `.agent/references/openclaw-oramasys-fleet-retrofit-playbook.md`
- Session: `.agent/memory/working/OPENCLAW_MERGE10_FLEET_RETROFIT_2026-07-26.md`
- Plan: `OpenClaw/references/raft-openclaw-MERGE-PLAN-10.md` (sibling workspace, not in PT repo)
- Live hub: `${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace/docs/oramasys/CROSSREF.md`

---

## 2026-08-04: Hermes dispatch — three lanes (L-H1 / L-PT / L-Fleet)

**Decision:** Document and tag all hermes-harness skills and `bin/agents/` staging rows with
exactly one dispatch lane. **L-H1** = native Nous `delegate_task` children (in-session only).
**L-PT** = PT `spawn_hermes_agent()` / `hermes_harness.py` direct `AIAgent` scripts.
**L-Fleet** = `coord_pulse` → `win_job_queue` → `cursor-agent` (Win/Mac fleet fiction).

**Rationale:** EXA/FireCrawl + fleet results + `coord_pulse.ps1` prove Win operators run
L-Fleet, not L-H1. orama `hermes-delegate` and universal-envelope prose falsely implied
native Hermes subagent parity. Grafting OpenClaw recursive-spawn into `hermes-delegate`
without rename would cement the error.

**Alternatives considered:** Single "Hermes subagent" umbrella (rejected — three incompatible
runtimes); renaming only docs without REGISTRY fields (rejected — needs machine-checkable tags).

**Status:** done (pending review) — Wave 0 taxonomy/lane tags complete on orama graft branches;
Wave 1–2 envelope reconciliation also complete (pending review/merge). Chronology invariant:
Wave 0 precedes Wave 1. Not merged/released.

**Links:**

- PT report: `.agent/memory/working/HERMES_GRAFT_DISPATCH_CORRECTIONS_REPORT_2026-08-04.md`
- orama taxonomy: `bin/orama-system/skills/hermes-harness/references/hermes-dispatch-taxonomy.md`
- Graft plan Phase 1.5: `docs/plans/2026-08-03-hermes-openclaw-graft-audit-plan.md`

---

## 2026-08-04: OpenClaw→Hermes graft Wave 0 before JSON envelope (Wave 1)

**Decision:** Graft execution order: **Wave 0** (taxonomy + lane tags + SKIP recursive-spawn →
`hermes-delegate`) then **Wave 1** (JSON envelope on shell entrypoints). Optional
`hermes-native-delegate` command card documents L-H1 only — no PT wrapper pretending to be
`delegate_task`.

**Rationale:** Protocol harmonization without lane clarity repeats the subagent misconstrual
in a more formal JSON schema.

**Status:** done (pending review) — Wave 0 taxonomy/lane tags complete; Wave 1–2 JSON envelope +
`hermes-status` complete on orama `2026-08-05-002-hermes-graft-plan-reference-fix` (local
commits, tests green). Operator review/merge gate open — not merged/released.

---

## 2026-08-04: gbrain autopilot vs `/sync-gbrain` code stage

**Decision:** Keep gbrain autopilot disabled until timeout/embedding/PT-pull failures are
repaired. Manual `/sync-gbrain` for code refresh when autopilot off. Stale lock quarantine,
not delete; LaunchAgent plist preserved.

**Rationale:** Autopilot held global lock while failing on oversized inputs; code stage refused
destructive ops (#1734). PATH must include `~/.bun/bin` for `gstack-gbrain-detect`.

**Status:** active — operator re-enables autopilot after root fixes.

---

## 2026-09-17: oramasys PR #14 review threads closed; three accept-risk items deferred without open threads

**Decision:** Treat [oramasys/oramasys PR #14](https://github.com/oramasys/oramasys/pull/14) review-thread cleanup as complete for GitHub thread tracking: 11 fixed threads resolved, 0 open. The PR remains open/unmerged at tip `e424391fb35c`. Three deferred accept-risk items have **no remaining open threads** and must not be “kept alive” by inventing new review comments:

1. FleetBindingStore ceremony (separate from S-AuthZ `/run` Bearer)
2. raw `uvicorn --host` without `bin/serve` as the policy launcher
3. in-process-only (not distributed) NIP-98 replay

**Rationale:** Thread count is not the same as merge-readiness. Accept-risk items stay in durable memory so a later audit can find them without GitHub’s review UI.

**Status:** recorded (PR still open)

**Links:** `.agent/memory/semantic/ORAMASYS_PR14_REVIEW_THREAD_CLEANUP_2026-09-17.md`

---

## 2026-10-24: Model governance supplements repository routing policy; escalation approval has two regimes

**Decision:** The Alexandria model-governance standard (oramasys/alexandria PR #1) **supplements**
each repository's existing model-routing policy and never supplants it. Downstream edits refresh
outdated model ids in place and graft the standard in as (a) the fallback when the tier logic
cannot decide from verifiable criteria, (b) alternate paths for other harnesses, and (c) the
gates on escalated models. Escalation approval has two regimes, defined only in Alexandria's
[Escalation approval regimes](https://github.com/oramasys/alexandria/blob/docs/mig-pack-ingest-20260925/docs/standards/model-governance.md#escalation-approval-regimes)
section (linked, not restated here). The repository-specific
decision: moving from the interim regime to the enforced one is a repository change (a production
caller plus a control-plane verifier), never a flag, so an agent cannot flip it.

**Scope (what this ruling does and does not change):** The interim approval applies to the
Alexandria standard and to orama-system's documentation and pin (orama-system PR #381). It does
**not** relax Perpetua-Tools: PT's own runtime checker (`proof_is_token` in
`src/perpetua_tools/model_governance.py`) and its pin still require the escalation token, and PT
Opus and Fable launches stay gated by it until PT explicitly adopts the interim regime.

**Rationale:** The first pass of orama-system PR #381 replaced the canonical `model-route`,
`common-performance`, MODE 3 tiering and `cursor-agent` tiers with the Alexandria text, although
the standard is still Proposed and the operator asked only for stale ids to be updated. The first
wording of the transition was circular, because a proof cannot be demanded where nothing can
issue or verify it; two checkable conditions removed the circularity.

**Where recorded:** orama-system PR #381 (pin doc sections "Relationship to existing orama routing
policy" and "Escalation approval regimes"; restored policy files); oramasys/alexandria PR #1
(sections "Relationship to repository routing policies" and "Escalation approval regimes";
`grok-4.6` default refreshed to `grok-4.7`; direct-xAI pin left on `grok-4.6` until the vendor
list confirms `grok-4.7`).

**Open items:**

- Ratify the "Downstream decisions to ratify here" list in the Alexandria standard (effort ceiling,
  planning Opus, role selection); decide when the enforced regime starts.
- Perpetua-Tools is **not yet aligned** with its own pin: `.cursor/commands/model-route.md` still
  names `grok-4.6` as the Cursor default, while `docs/standards/model-governance.md` and
  `config/model-governance.yml` name `grok-4.7` and ban `grok-4.6`. This memory PR does not change
  routing files; a separate stale-id refresh PR (ids only, policy text untouched) should fix it.
  Whether PT adopts the interim approval regime is a separate operator decision.

---

## 2026-11-17: Biafra G3 pin and receipt binding (orama `seat_contracts.py`)

**Decision:** The evaluator digest covers exactly the verifier files given to `evaluator_digest`
(by file name and bytes). `pin_evaluator` writes a one-time pin at run start; re-pinning succeeds
only for the same digest and covers, otherwise "evaluator changed". A reviewed or graduated
Mechanism Card needs a dry-run receipt `trace` that validates and carries the card's digest; a
graduated card also needs `pinned_digest` equal to the card's digest. A receipt `delta` check
against the trace (`metric_after - metric_before`) was added after the orama review (implemented
and tested).

**Rationale:** Closes the three accepted G3 cases in doc 76 (no trace, receipt digest differs,
never pinned). Binding by id alone would let a receipt for `X@1` promote a different card that
reuses the id.

**Alternatives considered:** none recorded beyond the first design, which lacked the `delta`
comparison.

**Status:** decided; the `delta` comparison and unique-temp-file pinning are being implemented.
Reading the pin inside `live_cycle` before launch is a later TODO.

---

## 2026-11-17: Biafra G9 "no card, no promotion" instead of a mandatory input card

**Decision:** Cycles stay usable without a card. A cycle that validated a card adds
`card_id = "<mechanism_id>@<revision>"`. A reviewed or graduated card needs a receipt with
`card_checked: true` and its own `card_id`.

**Rationale:** The outer dry run produces the receipt the card is built from, so a mandatory input
card would break the real flow. Binding at promotion keeps the flow and still ensures a mechanism
is promoted only after a dry run that checked this card.

**Alternatives considered:** a mandatory card on every cycle (rejected, circular).

**Status:** decided by the operator's request to resolve G9 in this change; reversible.

---

## 2026-11-17: One PT-owned SpendGate with a shared atomic CostGuard

**Decision:** `orchestrator/spend_gate.py` is the single spend gate. `CostGuard` keeps settled
spend and live reservations in one private SQLite store per budget file, every operation in
`BEGIN IMMEDIATE`, shared across instances and processes. Reservations carry a declared hold; a
late commit still records the spend. Orama's `spend_guard.py` is a thin forwarder with no ledger.
A missing store beside a `.migrated` legacy file fails closed.

**Rationale:** Per-instance reservation locks do not share a ceiling, and a second ledger in orama
would split the budget. PT is the runtime and state authority.

**Alternatives considered:** keeping a ledger in orama (rejected: orama is stateless).

**Status:** decided and implemented in the PT integration. Spend recorded after migration lives
only in the SQLite store; reverting does not move it back.

---

## 2026-11-17: HTTP outcome mapping on the W&B path (below 500 releases, the rest settle unknown)

**Decision:** An HTTP status below 500 is a definitive provider refusal and releases the
reservation. A 5xx, transport error, timeout, interrupt or malformed response settles the full
reservation via `settle_unknown`. If settling fails after a paid answer, keep the answer and fall
back to `settle_unknown`.

**Rationale:** Unavailable output is not evidence of zero billed output, so unknown outcomes
charge in full. The first design charged every HTTP error; the integrator amended it.

**Alternatives considered:** charge every HTTP error (rejected as over-charging definitive
refusals).

**Status:** decided and implemented.

---

## 2026-11-20: Clarification of the 2026-11-17 HTTP outcome decision

The earlier wording “an HTTP status below 500” is overbroad. The recorded
release rule concerns a provider status error below 500, not all responses
below 500. A successful response is not a refusal; HTTP success alone also
does not establish a valid answer. Settle a valid paid answer and treat an
unavailable or malformed response as unknown. See the additive replacement
`lesson_7ce658f9ed63` for the complete spend guidance. The earlier decision
remains here as historical evidence, not as an unrestricted status rule.

---

## 2026-11-17: Popen and process-group lifecycle with a "sent" flag

**Decision:** The live-cycle launcher starts with `Popen` (`start_new_session=True`) and is awaited
with `communicate`. Only a failed `Popen` releases. After `Popen` succeeds the request counts as
sent, and the `finally` never releases it. On timeout, pipe error or interrupt the whole group is
SIGKILLed before a bounded reap, then the reservation settles unknown. If settling fails after
send, the reservation is left to its declared hold and the error is surfaced. The sandbox never
reaps the leader before signalling the group and checks that an exit probe exists before starting
the child.

**Rationale:** A grandchild holding the pipes must not hang the cycle past `timeout_s`, and a sent
request must never be recorded as zero spend.

**Alternatives considered:** a per-poll `ps` probe (rejected for cost).

**Status:** the Popen and sent-flag design is decided; items 11, 12 and 15 of the orama review fix
are being implemented and are not yet verified.

---

## 2026-11-17: PR-carried memory overrides lesson_94a6ff5363ae for this consolidation

**Decision:** The operator ruled on 2026-11-17 to consolidate every change tonight, memory
included, on the current pull requests (PT #516 and orama #519), and to open no new pull requests.
The memory corrections (`lesson_d4ac6209ce38`, `lesson_7240bbe31030`) and this lane's memory
records therefore ship in PT #516. The "PT memory commits belong on main only" guidance of
accepted `lesson_94a6ff5363ae` was explicitly overridden for this consolidation. That lesson is
not edited.

**Rationale:** The defect was introduced in #516, so the correction belongs with it, and the
operator chose a single consolidated delivery over a separate main-only memory commit.

**Alternatives considered:** a separate main-only memory commit or a new pull request (declined by
the operator).

**Status:** decided by the operator for this work; not a general change to the main-only rule.

---

## 2026-11-23: G6, the outer-seat persona is accepted as written

**Decision:** The operator accepted the Biafra outer-seat persona in orama's
`bin/agents/metaresearch-outer/SOUL.md` as written, including the boundary an agent added: Biafra
questions the work's assumptions and does not diagnose the person. Doc 76 section 15 in orama
records it.

**Rationale:** G6 was an agent-drafted elaboration beyond the operator's wording, held as a draft
until the operator reviewed it. Acceptance is the operator's judgement, and it was given on
2026-11-23.

**Alternatives considered:** accept with edits, or keep the draft (neither chosen).

**Status:** decided by the operator. No code or tests changed.

---

## 2026-11-23: G11, the W&B route is split by role

**Decision:** The operator ruled that the route is split by role. Wanda keeps the OpenAI client and
Weave, and her soul card (Cline CLI forbidden for her W&B route) stands. The Biafra seats use Cline
through `launch_cline_wandb.py`, and only under the shared spend gate. `lesson_8d873e4e2f73` is not
edited or superseded: it stays valid for the Biafra seats.

**Rationale:** The two records bind different consumers, so neither is invalid. The Biafra live
cycle already launches Cline under the shared SpendGate, while the launcher has no gate of its
own; Wanda's path is the OpenAI client. The split matches the code that exists.

**Alternatives considered:** the soul card wins (a superseding lesson, and a change to the live
cycle); the lesson wins (an edit to Wanda's soul card and a spend-gate wrapper for her).

**Status:** decided by the operator. Orama states the scope in Wanda's soul card and in doc 76
section 15. A new Cline caller must go through the shared spend gate.

---

## 2026-11-23: G11 correction, the Biafra Cline route is a designation and not a running route

**Decision:** The 2026-11-23 ruling "G11, the W&B route is split by role" stands. One claim in its
rationale and in `lesson_9bcf2ac7d3ce` is corrected: the Biafra live cycle does not launch Cline
today. `live_cycle()` refuses with `launcher-output-bound-unsupported`, and the legacy path with
`legacy-live-path-disabled` only when armed (when the gate and arm variables are unset,
`run_program()` runs `dry_cycle()` with `called_launcher=False` instead), until the launcher can
bound total output and request count. The
Biafra seats are therefore designated to use Cline under the shared spend gate once that bound
exists. Wanda keeps the OpenAI client, called directly by
`bin/orama-system/skills/wanda-wandb/scripts/wanda_chat.py` in orama-system. That client stays
outside the spend gate and is not an authorized unattended or paid path. Orama doc 76
section 15 holds the canonical wording.

**Rationale:** The original text was written from memory of earlier code and was not re-checked at
the merged head. A test in orama now ties the doc wording to the launcher's refusal.

**Alternatives considered:** editing the merged entry and lesson in place. Rejected: records on
`main` are append-only, and the lesson tool never rewrites a lesson.

**Status:** a correction of one factual claim; the operator's ruling is unchanged. The lesson is
provisional until the launcher bound exists.

---

## 2026-11-23: LAN control-plane leaf validity of 60 days confirmed as current policy

**Decision:** The operator confirmed the 60-day LAN control-plane leaf lifetime as current policy:
renewal agreement v2 (2026-11-17), `LEAF_VALIDITY_DAYS = 60` in
`orchestrator/lan_control_plane_pki.py`, a leaf reissued when under 7 days remain
(`LEAF_MIN_REMAINING_DAYS`), and `not_after` capped at the CA's expiry. Until now it was only an
assumption recorded in the domain-knowledge document
`LAN_PEER_TLS_AUTH_CHAIN_AND_RENEWAL_V2_DOMAIN_KNOWLEDGE_2026-11-17.md` (section 8, policy
lineage). It is the later decision in that lineage and does not invalidate the 2026-10-26 record,
which described the earlier 30-day model and was correct for its date.

**Rationale:** The 2026-11-15 to 11-17 outage showed the cost of the first model, and v2 replaced
it. The trade-off is accepted: a stolen leaf key is usable for up to 60 days instead of 30, and
`lan_control_plane_pki.py` has no CRL or OCSP path, so a compromised leaf that still chains to the
pinned CA stays trusted until it expires. For a compromised leaf the answer is a two-sided CA
migration (new CA and new pin on both peers), not reissue.

**Alternatives considered:** revert to 30 days (set `LEAF_VALIDITY_DAYS` back to 30; the tests
derive their numbers from it; existing leaves stay in service until under 7 days remain unless
`leaf.key` and `leaf.pem` are removed, which forces reissue); leave it as an assumption (declined,
since the operator has now ruled).

**Status:** confirmed by the operator. No code change.

## 2026-11-25: OpenClaw runtime baseline, the stable node link and reproducible install steps

**Decision:** The OpenClaw gateway launch agent never names a node version. A stable link
(`~/.local/share/openclaw-node`) points at the one nvm node that satisfies the engines range (>=24.22.1 <25,
or >=26.12.1) and carries the global openclaw version that AlphaClaw pins; the service file uses the link.
`perpetua_tools.openclaw_runtime` owns it (`--check` read-only, `--apply` repoint and reload only on change).
The dated baseline: node 24.22.3 as the nvm default (22.22.2 kept, 24.14.1 obsolete until the restore succeeds),
openclaw 2026.10.6 globally and inside the AlphaClaw fork build (PR 34, `@diazmelgarejo/alphaclaw` 0.9.39-9,
upstream main 0.9.38-beta.1 already inside), gateway on loopback with token auth.

**Rationale:** The old plist stored the exact node folder twice (binary and openclaw entry), so removing or
upgrading that node left a KeepAlive service crash-looping. The gateway also failed on 2026-11-25 for an older
reason, conflicting plugin-install metadata in the shared SQLite state; a clean state with the old one renamed
aside was the safe cure. The steps are reproducible: PT `scripts/install-openclaw-runtime.sh` (`--check`,
`--plan`, `--apply`, and the opt-in `--fresh-gateway --accept-risk`), a read-only non-fatal Step 8 in the default
AlphaClaw bootstrap, orama first-run step 0.9 that only calls it, and an alert-only launchd watcher.

**Alternatives considered:** reinstall the service after each Node change (the forgotten step); a separate
dedicated node such as Homebrew node@24 (more stable but breaks the one-24.x rule); an auto-repointing watcher
(could move the gateway onto a half-migrated node); rolling back to the old baseline (declined: the old
2026.7.1-beta.5 gateway was itself the failing one).

**Provider order (operator ruling, subject to change):** W&B DeepSeek-V4.1-Flash-1017 at high as the default;
ClinePass through the Cline launcher; Google by AI Studio API key (OpenClaw 2026.10.6 offers no new Google web
login); the authenticated OpenAI Codex login; local Ollama as the generic default. The Google key already exists
in the operator environment and is configured by reference. Plugins and Telegram are restored last.

**Mac LM Studio (operator ruling, supersedes the earlier "last-resort fallback" choice):** a manual choice only,
disabled and absent from the OpenClaw config and from every `fallbacks` list, because a fallback switches on its own
exactly when Ollama is overloaded and would load a second large model on the same Mac, the closed overheat
invariant. Windows LM Studio comes back from the discovery file, never from an old address. The W&B default uses the
canonical `WANDB_API_KEY`, set as a by-reference alias of the PT launcher's `DEEPSEEK_V4_FLASH_WANDB` in the
operator's env file (one source of truth, no second copy of the key).

**Fallback order for the restored OpenClaw models (operator ruling 2026-11-25, subject to change):** W&B
DeepSeek-V4.1-Flash-1017 at high; Google `gemini-3.8-flash` at medium (key by reference); the authenticated OpenAI
Codex login; local Ollama; **OpenRouter free (`openrouter/free`) second to last**; Mac LM Studio last but disabled,
meaning manual only and in no chain. The last active fallback is therefore OpenRouter free. ClinePass runs through the
Cline launcher, not an OpenClaw chain. No chain pairs Ollama with a Mac LM Studio model.

**Working rules:** commit only in durable canonical folders, base on the latest PR tip, no push until told.

**Status:** confirmed by the operator. Implemented on local branches, not pushed: PT PR 521's branch (commits
`753139a0`, `ddcb46d5` and the memory commits) and the orama branch
`2026-11-25-002-openclaw-runtime-steps` (`f8416ec8`) on the PR 530 tip. The staged restore is still to do.

## 2026-11-26: OpenClaw seats, env source of truth and the staged-restore procedure

**Decision:** Seats `biafra` (alias MetaResearcher, guardian and companion of `autoresearcher`) and
`autoresearcher` default to OpenAI Terra at medium effort through the codex harness with a per-agent
login, then the default chain (W&B, Google, Ollama, OpenRouter free). Astra and Sol are human-gated and
never default or automatic. W&B stays in every agent chain. The seats deny exec, process, browser,
canvas, nodes, cron and gateway; a Seatbelt sandbox is a staged draft. One env file is the source of
truth for working keys; the gateway reads custom keys from its own global env file plus a restart.

**Rationale:** Each rule came from a measured failure or a ruling; the sequence, the next order and the
open items are in `SESSION_CHRONICLE_2026-11-26_OPENCLAW_SEATS_ENV_AND_STAGED_RESTORE.md`, and the
procedure and recovery steps in the orama first-run card `openclaw-staged-restore-and-recovery.md`.

**Status:** confirmed by the operator; committed locally, not pushed.


## 2026-11-26: Biafra Cline launcher bounds (G11) and lockstep contract

**Decision:** Enforce fail-closed `max_requests` (positive integer) and `max_total_output` (positive integer tokens/bytes) bounds in `launch_cline_wandb.py` and pass them through `biafra_cycle.py`. `_launcher_boundary_problem()` lifts to `None` ONLY when both bounds are verified active. Wanda's path remains the direct OpenAI client and Weave, outside the spend gate, and her soul card strictly forbids the Cline CLI.

**Rationale:** Fulfills doc 76 §15 and G11 designation requirements, transitioning the Biafra Cline route from designated to bounded-capable without violating Wanda's boundary or arming any live cycle.

**Status:** active on branch `stack/523-biafra-bounds` (stacked on PR #523).


## 2026-11-26: G11 lockstep verification correction, the PT memory contract is not runtime qualification

**Decision:** The preceding launcher-bounds entry remains the intended contract, not an implementation-complete
status. User-authorized takeover verification of Orama branch `stack/531-biafra-bounds` found that its
uncommitted launcher changes validate supplied positive bounds and forward `--max-requests` and
`--max-total-output` to Cline, but still accept missing bounds. `biafra_cycle.py` still returns
`launcher-output-bound-unsupported`, and `launcher_argv()` passes neither bound. Biafra therefore remains
designated and fail-closed, not bounded-capable. Wanda's direct OpenAI-client boundary and Cline prohibition
remain unchanged, and `lesson_8d873e4e2f73` remains valid for the designated Biafra route.

**Rationale:** The prior decision status and lesson rationale said the launcher enforces both bounds and
unblocks the designation. Read-only inspection did not substantiate that claim: forwarding flags is not
proof of enforcement, and the live-cycle boundary has not been lifted. PT memory must record the contract
without presenting unmerged Orama work as integrated or qualifying a live route.

**Status:** corrected additively through `.agent/tools/correct_lesson.py`; Orama enforcement, documentation
and test lockstep, publication order, merge, and operator-gated activation remain unresolved. No Orama files
were changed and no live cycle was armed.


## 2026-11-26: G11 verification update, mandatory bounds are wired but enforcement remains unverified

**Decision:** A later read-only Orama snapshot supersedes the preceding verification snapshot without
rewriting it. The launcher now requires positive `--max-requests` and `--max-total-output` values;
`launcher_argv()` always supplies defaults of one request and 4096 output tokens; and `live_cycle()` checks
the boundary before reservation or launch and forwards the output cap to spend preflight. Nevertheless,
`BOUND_CONTRACT` keeps both capabilities false because Cline 3.0.75 has no verified request-count or
cumulative-output enforcement, so `launcher_boundary_problem()` still returns
`launcher-output-bound-unsupported`. Biafra remains designated and fail-closed, not bounded-capable.

**Rationale:** Mandatory input, cycle wiring, and forwarding are necessary but do not prove that either
cap terminates work. Tests that simulate a supported client by setting both capability flags true are not
qualification of the installed client. Doc 76 still describes the earlier optional/no-wiring state, so the
documentation has not caught up with the code. Wanda's direct OpenAI-client boundary and Cline prohibition
remain unchanged, and `lesson_8d873e4e2f73` remains valid for the designated Biafra route.

**Status:** latest PT lesson correction appended through `.agent/tools/correct_lesson.py`; actual Orama
client enforcement, documentation/test lockstep, publication order, merge, and operator-gated activation
remain unresolved. No Orama files were changed and no live cycle was armed.

---

## 2026-11-26: G11 lesson restored to accepted so recall returns it

**Decision:** `lesson_957217e78f07` (accepted, supersedes `lesson_9bcf2ac7d3ce`) states together: the
Biafra seats are designated to use Cline under the shared spend gate once the launcher enforces both
total output and request count; the route stays fail-closed today (`BOUND_CONTRACT` keeps both
capabilities false, so `live_cycle()` refuses with `launcher-output-bound-unsupported`); Wanda's
boundary is unchanged; `lesson_8d873e4e2f73` stays valid. The earlier rows are preserved.

**Rationale:** `recall.py` uses only the latest row per id and skips rows that are not accepted. The
provisional correction chain, starting with the first correction on 2026-11-23, hid
`lesson_9bcf2ac7d3ce` from structured recall, and the 2026-11-26 rows dropped the shared spend-gate
requirement from the rendered lesson layer. `correct_lesson.py` cannot append an accepted row, so the
tooling path is an accepted superseding lesson through `learn.py --stage-only` and `graduate.py`.
Verified with `recall.py --quiet`: the new lesson is returned first, the retired one is not.

**Alternatives considered:** leave the chain provisional (invisible to recall); edit the existing rows
(forbidden, memory is append-only).

**Status:** done on this pull request. For any later correction of a lesson that must stay recallable,
end the chain with an accepted superseding lesson.

---

## 2026-11-26: lesson_8d873e4e2f73 is retired by a qualified replacement, so recall cannot return it ungated

**Decision:** `lesson_b9279f3676a9` (accepted, supersedes `lesson_8d873e4e2f73`) replaces the
unqualified launcher lesson. It keeps that lesson's `tokenSource` and `updatedAt` rule, the ClinePass
DeepSeek boundary and the identical-prompt probe observation (Cline answered four tasks and was
faster; Wanda matched the format on three and cut one function off, as one observation). It adds that
launching Cline with `launch_cline_wandb.py` is only authorized under the shared spend gate, that the
Biafra route is designated and fail-closed today (`live_cycle()` refuses with
`launcher-output-bound-unsupported`), and that Wanda keeps the direct OpenAI client outside the gate
with a soul card that forbids the Cline CLI for her route.

**Rationale:** `lesson_8d873e4e2f73` told readers to summon Cline with the launcher and had no
spend-gate condition, and the launcher has no gate of its own (`biafra_cycle.py` is what wraps it with
the guard). `recall.py` scores lessons separately, and three narrow queries (the `tokenSource` rule,
the ClinePass boundary, a plain W&B DeepSeek Cline launch) returned it first and without
`lesson_957217e78f07`. After the replacement, the same queries return the qualified lesson first and
the old row renders struck through.

**Relation to the 2026-11-23 ruling:** that ruling said `lesson_8d873e4e2f73` stays valid and is not
superseded, meaning neither it nor Wanda's soul card is invalidated by the other. This entry keeps that
intent: no guidance is lost and neither record is declared wrong. Only the instruction's missing
condition is added, in a replacement row, because an unqualified instruction can be recalled alone.
Earlier rows, including this lesson's, are preserved. Orama doc 76 and `lesson_957217e78f07` still
name the old id; the guidance behind that id is carried unchanged by the replacement.

**Alternatives considered:** a provisional correction (hides the lesson from recall, the failure found
earlier the same day); editing the old row (forbidden, memory is append-only); leaving it as it was
(recall can return the instruction without its gate).

**Status:** done on this pull request.

---

## 2026-11-27: Phase 1B BOUND_CONTRACT closure — launcher-side enforcement and bounded-capable qualification

**Decision:** Close the Phase 1B boundary gate by implementing launcher-side boundary enforcement in `launch_cline_wandb.py` via `run_guarded_cline`: a stream byte/token accountant and request monitor supervise child process execution and terminate fail-closed when either `max_requests` or `max_total_output` is reached. Offline harness tests in `tests/test_launch_cline_wandb.py` prove termination and fail-closed exit codes for both limits. `BOUND_CONTRACT` is flipped to `{"max_requests": True, "max_total_output": True}`, and `_launcher_boundary_problem()` lifts to `None` for valid positive bounds, transitioning the Biafra Cline route from designated to bounded-capable. Invalid, missing, or non-positive bounds continue to refuse fail-closed with `invalid-launcher-bounds`. Wanda's direct OpenAI client route and soul card forbidding Cline CLI remain intact and outside the spend gate. Legacy `run_program` remains fail-closed (`legacy-live-path-disabled`), and no live cycle is armed.

**Rationale:** The installed Cline CLI 3.0.76 lacks native request-count and output-token CLI enforcement. Relying on CLI flags or client-side trust would risk unbounded provider spend. Implementing boundary enforcement directly in the launcher guarantees fail-closed termination at the process boundary, fulfilling doc 76 §15.1 and handoff §9.1 without arming live execution or violating Wanda's boundaries. Accepted superseding lessons (`lesson_f6de5491aae4` superseding `lesson_957217e78f07`, `lesson_8100266e8176` superseding `lesson_b9279f3676a9`, and `lesson_252848a6a160` superseding `lesson_80f7b1d8d9a3`) preserve structured recall.

**Alternatives considered:** Wait for upstream Cline CLI boundary flags (rejected — indefinite blocker); loopback HTTP MITM proxy (rejected — complex TLS interception with questionable certificate trust and failure modes); client-side trust (rejected — violates fail-closed doctrine).

**Status:** active on branch `2026-11-27-001-lane2-bound-contract-pt`.


---

## 2026-11-27: Phase 1B Lockstep alignment with orama-system PR #533 — loopback HTTP accounting proxy

**Decision:** Update lockstep memory records to align with `diazMelgarejo/orama-system` PR #533
commit `6572bfaf74a4c74332fe4c7b5ec30e2f14ef8bb9`: launcher boundary enforcement is implemented in
`launch_cline_wandb.py` via a stdlib loopback HTTP accounting proxy intercepting OpenAI-compatible
requests on the local loopback host (port 0). The proxy counts requests 1:1 at the wire boundary
(resolving stdout/stderr regex undercounting, double-counting, chunk-splitting, and ordinary-text
false termination) and parses real provider `usage.completion_tokens` (injecting
`stream_options: {"include_usage": true}` on SSE streams). Breaching either bound or encountering
missing usage terminates the child fail-closed with exit code 124. Wire-level enforcement and
deterministic harness tests are verified and pushed in `orama-system` PR #533. Accepted superseding
lesson `lesson_c35a277559cc` (superseding `lesson_f6de5491aae4`) preserves append-only memory
integrity. In tandem, the L-1r queue race guard is wired through the worker CLI: `queue claim`
returns and emits `claimed_at`, and `queue complete` / `queue fail` accept `--expected-claimed-at`
to prevent stale workers from completing or failing reclaimed tasks under the same agent name.

**Rationale:** Fulfills lockstep cross-repository synchronization doctrine. An unverified launcher
claim in PT memory without passing wire-level enforcement in `orama-system` violated review
standards (CodeRabbit finding `PRRT_kwDOPz7qg868lCAr`). Aligning PT memory with the exact
`orama-system` PR #533 commit (`6572bfaf`) ensures that all claims are backed by committed,
verified repository artifacts. Similarly, exposing `--expected-claimed-at` in
`orchestrator/coordination/cli.py` seals the worker-facing L-1r race window (CodeRabbit finding
`PRRT_kwDOPz7qg868lCAw`).

**Alternatives considered:** Defer lockstep alignment until post-merge (rejected — leaves unbacked
claim in PR branch); in-place editing of JSONL records (strictly rejected — violates append-only
memory invariant).

**Status:** done on branch `2026-11-27-001-consolidated-pt-bounds-and-queue-l1r`.


---

## 2026-11-27: Final Remediation Lockstep alignment with orama-system PR #533 commit 7ad6c6b9

**Decision:** Update lockstep memory records to align with `diazMelgarejo/orama-system` PR #533
commit `7ad6c6b9afdb36e88793eef3fbc5fbfc2df0da8b` (`7ad6c6b9`): launcher boundary enforcement in
`launch_cline_wandb.py` provides:
1. Pre-forward `POST /chat/completions` request-count gate (path parsed via `urllib.parse.urlsplit`
without query string; non-allowlisted POST routes refused fail-closed with HTTP 403; post-breach
retries rejected with HTTP 429 before forwarding).
2. Serialized pre-forward upstream `max_tokens` / `max_completion_tokens` clamping against
remaining `max_total_output` budget under `chat_gate`, plus post-response `usage.completion_tokens`
accounting (SSE `stream_options.include_usage=True`).
3. Fail-closed exit code `124` (with bounded 5.0s in-flight handler drain and `live_cycle()`
`_settle_unknown` settlement) on bound breach, missing/invalid usage, or upstream 504/502
transport failure.
4. Preserved shared spend-gate requirement for Biafra Cline and Wanda's direct-client boundary verbatim.

Clarification for line 1170 above regarding `orchestrator/coordination/cli.py`: `--expected-claimed-at`
is supported as an optional argument on `queue complete` and `queue fail` to maintain backward
compatibility with existing callers. Calls omitting `--expected-claimed-at` remain unprotected
against same-agent-name reclaims; the CLI change seals the worker-facing race window for callers
that supply their original claim timestamp.

**Rationale:** Addresses CodeRabbit findings `PRRT_kwDOPz7qg868lCAr`, `PRRT_kwDOPz7qg868nC9h`, and
`PRRT_kwDOPz7qg868lCAw`. Clamping forwarded output limits prevents upstream provider over-generation,
while query-string stripping and route allowlisting prevent proxy bypass. Fail-closed exit 124 on
upstream transport failure ensures unverified spend is charged via `_settle_unknown`.

**Alternatives considered:** In-place mutation of graduated memory JSON (rejected — violates
append-only invariant); making `--expected-claimed-at` mandatory on CLI (rejected — breaks
backward compatibility with existing automation and test suites).

**Status:** done on branch `2026-11-27-001-consolidated-pt-bounds-and-queue-l1r`.

---

## 2026-11-27: Enduring Final Lockstep Alignment with orama-system PR #533 commit fffed6a4

**Decision:** Update lockstep memory records and coordination contracts to align with
`diazMelgarejo/orama-system` PR #533 commit `fffed6a46825018f6a9f394b2c777d0bc3ed8aaf` (`fffed6a4`,
incorporating core proxy fix `3caa44b7` and canonical exemplar reference cards):
1. Launcher boundary enforcement in `launch_cline_wandb.py` provides synchronous socket admission
   in `AccountingProxyServer.process_request()` before spawning worker threads, eliminating
   accept-to-dispatch races against early child exits.
2. Two-phase `stop_and_drain(timeout_s=5.0)` marks `_accepting = False`, calls `self.shutdown()` to
   break the socket accept loop, and waits on `_inflight_cond` for in-flight requests to complete.
3. Single fail-closed funnel via `_fail_closed()` and `_read_upstream_response()` ensures all
   transport errors, socket timeouts, and `urllib.error.HTTPError.read()` body reading failures
   terminate fail-closed with exit code `124` and unknown spend settlement (`_settle_unknown`).
4. Factorization into single-responsibility helpers: `_admit_chat_request()`,
   `_prepare_chat_payload()`, `_read_upstream_response()`, and `_account_chat_usage()`.
5. Preserved `queue_claim` return type returning `claim_ts: float` on successful claim, updating
   characterization tests (`test_coordination_manual_cleanup_characterization.py:77` and
   `test_agent_handoff_cli.py:142`) to `assert isinstance(claimed_at, float)` to uphold monotonic
   fencing semantics.
6. Superseded stale `lesson_8100266e8176` (graduated as `lesson_61b35f0ca87d`), `lesson_67887871bd23`
   (graduated as `lesson_aa38395eb32f`), and distilled cross-cycle architectural learnings
   (graduated as `lesson_f7c090a572fc`) via `graduate.py --supersedes` while strictly preserving
   `tokenSource: "manual"`, millisecond UTC `updatedAt`, ClinePass isolation, and Wanda direct-client
   guidance.

**Rationale:** Addresses CodeRabbit findings `PRRT_kwDORtdZEM68lEd4`, `PRRT_kwDOPz7qg868pGcw`,
`PRRT_kwDOPz7qg868lCAr`, `PRRT_kwDOPz7qg868nC9h`, `PRRT_kwDORtdZEM68pFGx`, `PRRT_kwDORtdZEM68pFG1`,
`PRRT_kwDORtdZEM68pFG5`, and nitpick `launch_cline_wandb.py:370`.

**Alternatives considered:** Checked `if not self.server.is_accepting()` inside `_admit_chat_request`
(rejected — causes premature 503 rejection of already-admitted requests draining during shutdown);
returning `None` from `queue_claim` (rejected — drops monotonic fencing timestamp); in-place mutation
of graduated candidate JSONs (rejected — violates append-only memory invariant).

**Status:** done on branch `2026-11-27-001-consolidated-pt-bounds-and-queue-l1r`.

## 2026-11-27 Claim fence identity and persistent high-water mark (supersedes the "monotonic claim_ts" wording of lines 1233-1236)

- `queue_claim` returns `claimed_at`. It is the wall-clock time raised to `nextafter(high_water_mark)` for that
  task via persistent `task_claim_hwm` table inside the claim's `BEGIN IMMEDIATE` transaction and is never deleted.
  Stamps issued for one `task_id` are strictly increasing across release, same-name reclaim, and backward clock steps.
  Evidence: `tests/test_l1r_claim_stamp.py::test_same_name_reclaim_in_one_clock_tick_gets_a_strictly_greater_stamp`,
  `::test_a_clock_that_steps_backwards_never_reissues_a_stamp`.
- The release fence compares `agent_id` and `claimed_at` by equality inside one `BEGIN IMMEDIATE` transaction.
  Evidence: `tests/test_l1r_claim_stamp.py::test_a_stale_worker_holding_the_old_stamp_cannot_release_the_replacement_claim`.
- Claims created before the high-water mark existed are covered once they are released, because release seeds
  the mark from the row it deletes (`_SEED_CLAIM_HWM`).
- `queue complete` and `queue fail` require `--expected-claimed-at` unless `--unverified-legacy` is passed. An
  unverified completion records `fence: "unverified"` and is not protected against a same-name reclaim.
  Evidence: `tests/test_l1r_cleanup_runtime_race.py::test_cli_queue_complete_and_fail_require_fence_flag`,
  `tests/test_l1r_cleanup_runtime_race.py::test_cli_queue_complete_legacy_omitted_flag_preserves_backward_compat`.

## 2026-11-27: OpenClaw defaults get one source of truth owned by Perpetua-Tools

**Decision:** The new OpenClaw defaults (model chain, seats, tool policy, env rules, baseline) move into one
data file under the Perpetua-Tools config, part of the AlphaClaw constellation. Orama-system consumers resolve the
live PT root first, then a generated byte-identical vendored copy, and fail closed only when neither exists. Scripts
emit patches by default so every change goes through the staged restore loop; the mac orchestrator json is generated
from the data; the macOS AlphaClaw patches stay as idempotent no-ops; the Mac LM Studio manual-only stanza stays in
the data file, disabled and in no chain.

**Rationale:** Orama start scripts still wrote old lmstudio-mac and nvfp4 routes on every start. The plan, findings
and phases are in the operator's off-repo plan file; nothing is implemented yet.

**Status:** confirmed by the operator; implementation waits for the operator's go (Phase 0 is read-only).

## 2026-11-27: The portal draft pull requests also carry the shared OpenClaw settings work

**Decision:** The shared OpenClaw model settings work stays inside the portal draft pull requests, Perpetua-Tools
#526 and orama-system #534, including its changes to orama's `start.sh` and setup scripts. The two drafts may have to
merge together.

**Recommendation not taken:** ideally the portal changes and the settings changes would be approved separately, with
the settings work kept on its own branches, so that a problem in one part does not hold up the other. The human
operator decided otherwise.

**Consequence:** a problem in either part, once published, can hold up both. In Perpetua-Tools the settings work
entered the draft by merge `d5a036f8` of `389668b0`. In orama-system it entered by merge `c5491eb1` of `350b5882`,
followed by six settings commits made only on the draft (`d9a30188`, `302cb885`, `2801bdfa`, `650da860`, `d8bb2c6a`,
`ecfb28f5`), so separating it later means moving those commits too.

**Status:** confirmed by the operator. Local only when recorded: nothing from the settings work is pushed, and the
operator has said not to push yet.

## 2026-11-28: Operator rulings on local models, privacy and the OpenClaw defaults

**Decisions:**

- Run strictly one local LLM or inference model at a time on the Mac. Until the cause of the 2026-11-27 UTC freeze is
  known, load no model and run no startup script that warms one; diagnose from reports and logs.
- A personal phone number is never committed to any repository. It is removed from the drafts; earlier history is not
  rewritten.
- The defaults carry the pinned `gemini-main` and `gemini-fallback` providers, with
  `gemini-main/gemini-pro-latest` and `openrouter/google/gemini-4-argon` human-gated.
- The `mac-researcher` seat runs on local Ollama, and Ollama unloads an idle model after five minutes.
- The Windows RTX 5080 `nvfp4` wording stays unchanged until the Gemma diffusion default question is settled; no such
  decision was found in this memory.

**Incident:** a test load of the local Mac model was launched at 2026-11-27 22:57 UTC; the machine stopped responding,
a watchdog panic followed and it rebooted within about three minutes. The crash report names no process, so the link
rests on timing and memory figures.

**Open:** startup and bootstrap scripts still warm the model, and gateway fallback and heartbeat routes can load it;
whether to remove the warm-up is not yet decided.

**Status:** local only when recorded; the operator has said not to push yet.

## 2026-11-28: One barrel, enforced; no model loads without a person's approval

**Decision:** The double-barrel rule is extended to one local model per host, across every engine,
embeddings included. `perpetua_tools.local_model_gate` enforces it from `config/local-model-gate.json`:

- a load needs a person's approval for that model, typed in a terminal, with an expiry;
- when another model holds the host the gate waits five seconds, looks again, then reports busy, and the
  caller runs without a local model (memory search answers from keywords);
- only a person can swap the loaded model; the gate never unloads on its own;
- anything it cannot determine is a refusal, and no test may reach an engine.

Choosing between the two models is not an exception to the one-model rule. It is a narrow exception to
"never unload", and only a person can take it.

**Occurrences that led here:** three loads on 2026-11-28, two of them with no approval. The full record is
`INCIDENT_LOCAL_MODEL_LOADS_2026-11-28.md` beside this file. The doctrine is in orama-system
`docs/v2/17-hardware-policy-enforcement.md`.

**Open:** callers that reach an engine directly (OpenClaw gateway, gbrain, code-review-graph, the
`local-agents` JavaScript client) are not behind the gate; Windows nodes have no probes.

**Status:** local only when recorded; the operator has said not to push yet.

## 2026-11-29: Correction to 'One barrel, enforced' (scope of enforcement)

**Correction:** the 2026-11-28 entry reads as if the gate enforced the rule for every engine and caller. It
enforces it **only for callers that go through it, on macOS only**. Direct callers (listed there as open) and
Windows and Linux hosts are not covered, so loads there stay manual. The rule itself is unchanged. Full coverage
is still open.

**Also changed by the PR 526 review:** the policy now lives at `src/perpetua_tools/local-model-gate.json`, so an
installed package carries it, and a request is sent while the gate is held, so a swap cannot happen under it.
