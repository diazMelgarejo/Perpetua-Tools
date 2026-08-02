# Major Decisions

> Record architectural or workflow choices that would be costly to re-debate.
> Use this template for each entry:

## 2026-08-02: PR-body grant v2 remediation — replay state machine + honest MVP boundary

**Decision:** Close remediation review F1–F7 on paired branches orama #260 / PT #320. HMAC grant uses fixed-order UTF-8 canonical payload bytes; append flow is `reserve` → `gh pr edit` → `mark-applied` → `consume` with `reconcile` for crash recovery. Same-user Keychain HMAC is **escalation control**, not proof of human presence. Human override is `operator-grant-v2` ack file, not `CURSOR_PR_BODY_HUMAN_OVERRIDE_ACK` env exports.

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
