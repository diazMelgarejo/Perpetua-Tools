# AlphaClaw upstream sync, Apex DMG, CI cron fix (2026-07-31)

**Status:** active session record — cross-repo context for AlphaClaw integration line + PT Gate-2 alignment  
**AlphaClaw PR:** #22 merged; follow-up PR `cursor/cron-platform-tests-f559` → `feature/MacOS-post-install`

---

## Executive summary

One long session covered: (1) reverse-engineering the Apex desktop DMG distribution channel, (2) upstream sync of `chrysb/main` into fork `feature/MacOS-post-install` with garrytan watchdog safe-mode cherry-pick and version bump to `0.9.33.9`, (3) history rewrite after conflict-marker leak in cherry-pick, (4) macOS-only CI failure in new upstream cron test, (5) TDD platform-aware fix, (6) worktree/branch cleanup, and (7) Gate-2 D3 absorption status check.

---

## 1. Apex DMG URL (`updates.alphaclaw.md`)

**Question:** Where does `https://updates.alphaclaw.md/desktop/prod/alphaclaw-mac-latest.dmg` come from?

**Answer:** Marketing CDN alias for **AlphaClaw Apex** — a separate Electron desktop app (`alphaclaw-nexus`), **not** the npm `@chrysb/alphaclaw` / `@diazmelgarejo/alphaclaw` server harness.

| Fact | Detail |
|------|--------|
| Live artifact | v0.1.7 arm64, Cloudflare-hosted |
| Build tool | electron-builder |
| Last publish | 2026-04-26 |
| Source repo | Private `alphaclaw-nexus` — not built from public `chrysb/alphaclaw` CI |
| Backend | `foundry.alphaclaw.workers.dev` (auth, billing, managed deploy) |
| Recoverability | ~95% from `app.asar`; republishing needs new bundle ID + self-hosted fork |

**Agent insight:** Do not conflate Apex desktop distribution with AlphaClaw npm package releases or fork integration branch work. DMG investigation is orthogonal to Gate-2 MCP/agents migration.

---

## 2. Upstream sync PR #22 (merged)

**Branch:** `cursor/chrysb-upstream-sync-f559` → `feature/MacOS-post-install`  
**Final merge tip:** `6c108ad`

```text
merge(upstream): sync chrysb/main into feature/MacOS-post-install (#22)
587b627 chore(release): bump @diazmelgarejo/alphaclaw to 0.9.33.9
f2d9abf feat(watchdog): cherry-pick garrytan safe-mode + openclaw 2026.7.1-2 pin
e8b19b0 merge(upstream): sync chrysb/main into feature/MacOS-post-install
```

**Contents:**
- Reverse-merge `chrysb/main` @ `eb275ae` into fork integration line
- Cherry-pick garrytan `aa84be20`: openclaw `2026.7.1-2`, watchdog safe-mode via `/readyz`, resume channels UI/API
- Version bump `@diazmelgarejo/alphaclaw@0.9.33.9`

**Base branch policy:** AlphaClaw agent PRs target `feature/MacOS-post-install`, not `main`. `main` is upstream mirror only.

---

## 3. Cherry-pick conflict-marker incident

**Mistake:** First cherry-pick attempt left `<<<<<<< HEAD` markers in `vitest.config.js` at commit `72a090d`.

**Fix:** User caught it; history rewritten:
1. Reset to clean base `e8b19b0`
2. Clean cherry-pick → `f2d9abf`
3. Clean version bump → `587b627`
4. Force-push (user-authorized for this branch)

**Lesson:** Always `git diff --cached` / inspect conflicted files **before** `cherry-pick --continue`. Never rely on a follow-up fix commit to sanitize bad history — rewrite if markers shipped.

---

## 4. macOS CI failure (post-merge)

**Run:** GitHub Actions `30608207386` on `feature/MacOS-post-install` after PR #22 merge  
**Failure:** `onboarding-cron.test.js` → `writes ALPHACLAW_ROOT_DIR into the generated system cron file`  
**Platform:** macos-latest only (778/779 pass)

**Root cause chain:**
1. Upstream wright-io PR #107 (`cac34c9`) added `onboarding-cron.test.js`
2. Test called `installHourlyGitSyncCron()` without `platform: "linux"`
3. On darwin, `applySystemCronConfig()` correctly skips `/etc/cron.d/` (EACCES / design)
4. Test expected write to `/etc/cron.d/openclaw-hourly-sync` — never happens on macOS

**Pre-merge proof:** Worktree compare at `6c1206f` (pre) vs `6c108ad` (post) — test file was **new in merge**, not a regression in fork-only code.

**Why system-cron tests passed:** `system-cron.test.js` already used explicit `platform: "linux"` / `"darwin"`.

---

## 5. TDD fix (new PR — post #22)

**Commit:** `b8b1d6e` / cherry-picked as `04f4b38` on `cursor/cron-platform-tests-f559`  
**Branch:** `cursor/cron-platform-tests-f559` from `origin/feature/MacOS-post-install`

**Changes:**

| File | Role |
|------|------|
| `tests/server/fixtures/cron-memory-fs.js` | Shared `createCronMemoryFs` + `seedCronOpenclawDir` |
| `tests/server/onboarding-cron.test.js` | 3-layer platform-aware coverage |
| `tests/server/system-cron.test.js` | Refactored to shared fixture; `ALPHACLAW_ROOT_DIR` assertion on linux |

**Test layers:**
1. `buildManagedCronContent` contract (linux + darwin)
2. `getSystemCronPaths` install backend mapping
3. `installHourlyGitSyncCron` integration (linux → `/etc/cron.d/`; darwin → managed scheduler)

**Result:** 786/786 pass on Node 22.22.3 (was 779 before new cases).

**Docs:** `docs/wiki/04-cron-scheduler.md` § CI failure + test layout; `docs/LESSONS.md` session 2026-07-31.

---

## 6. Cleanup performed

| Action | Detail |
|--------|--------|
| Worktrees removed | 2 temporary AlphaClaw session worktrees (cherry-pick sim, upstream sync) |
| Branches deleted | `cursor/garrytan-safe-mode-f559`, `cursor/deps-npm-onto-feature-f559`, `cursor/attribution-guard-sync-f559` |
| Remote removed | `garrytan` |
| Scratch dirs | 604 temporary AlphaClaw scratch directories removed |
| Kept | `cursor/commit-clean-merge-aware-f559` (9 unique unmerged commits), local `main` (ECC bundle history) |

---

## 7. Local `main` ECC divergence (context only)

Local `main` @ `16bea5e` has fork-only ECC bundle + guards/deps commits.  
`origin/main` @ `eb275ae` is upstream mirror — diverged after merge-base `ba2d2a7`.

ECC = agent harness scaffolding (`.codex/`, `.claude/ecc-tools.json`, skills) — not runtime AlphaClaw product. Per wiki, ECC belongs on integration/contrib branch, not mirror `main`.

---

## 8. Gate-2 D3 absorption status

**Not fully absorbed.** PT has `packages/alphaclaw-mcp` + `packages/local-agents`. AlphaClaw feature branch still has `lib/mcp` + `lib/agents`. Gate-2 retirement deferred — do not delete `lib/mcp`/`lib/agents` until alignment plan gates pass.

---

## Agent reflections (for future sessions)

1. **Merge-then-CI lag:** PR #22 merged before macOS CI exposed the upstream test gap. When merging large upstream syncs, run `npm test` locally **and** check whether new upstream tests assume linux-only paths before declaring done.

2. **Platform blindness is a test smell:** Any test touching `installHourlyGitSyncCron`, `applySystemCronConfig`, or `/etc/cron.d/` without explicit `platform` will flake or fail on `macos-latest`. Copy the `system-cron.test.js` pattern, not ad-hoc `os.platform()` assumptions.

3. **Cherry-pick verification gate:** Treat conflict resolution as a blocking review step. Require BOTH `git diff --name-only --diff-filter=U` (or `git ls-files -u`) returning no paths -- the authoritative index-level check, since rename/delete and add/add conflicts leave no textual markers -- and a supplemental `rg '<<<<<<|>>>>>>|======='` scan of staged file content before continuing, since the index can be clean while a marker was accidentally staged as literal content.

4. **Product topology:** Three distinct surfaces — npm harness (AlphaClaw server), Apex Electron desktop (private nexus repo), OpenClaw gateway (pinned dep). Documentation and investigation scope must name which surface.

5. **PR stacking after merge:** When fix lands after merge, **new branch from integration tip**, not amend/reopen closed PR. Branch name: `cursor/cron-platform-tests-f559`.

---

## Cross-links

| Resource | Path |
|----------|------|
| Cron wiki | AlphaClaw `docs/wiki/04-cron-scheduler.md` |
| Branch roles | AlphaClaw `docs/wiki/01-branch-roles.md` |
| PR base policy | PT `.agent/memory/working/WORKSPACE_PR_BASE_BRANCHES_2026-07-28.md` |
| commit-clean TDD | PT `.agent/memory/working/COMMIT_CLEAN_MERGE_AWARE_TDD_2026-07-29.md` |
| Gate-2 steelman | AlphaClaw `docs/gate2-lib-mcp-deletion-steelman.md` |
