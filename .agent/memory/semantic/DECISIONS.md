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
