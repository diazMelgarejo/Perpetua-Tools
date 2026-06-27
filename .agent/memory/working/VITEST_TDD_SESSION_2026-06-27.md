# Vitest / TDD session learnings — 2026-06-27

> Append-only distillation from orama `feat/vitest-tdd-gate-scratch` work (PRs #117/#118).
> Canonical orama evidence: `orama-system/docs/testing/2026-06-26-vite-frontend-tdd-gate.tdd.md`.

## Importance scale

| Rating | Meaning |
|--------|---------|
| **10** | Blocker / security / data-loss / wrong merge — always apply |
| **9** | High — prevents repeat CI or hook failures on macOS |
| **8** | High — branch triage or merge-order mistakes are expensive |
| **7** | Medium-high — test quality / gate completeness |
| **6** | Medium — workflow hygiene, docs, tooling |
| **5** | Low — deferred backlog, nice-to-have |

## Rated learnings (all)

| Imp | ID | Learning |
|-----|-----|----------|
| 9 | `lesson_f8e2a91b4c3d` | macOS `/bin/bash` is 3.2 — **no `mapfile`**. `scripts/git/check_tdd_commit.sh` must use `while IFS= read -r` loops. Symptom: exit 127 `mapfile: command not found`. Ref: orama `bash-32-git-script-portability.md`. |
| 9 | `lesson_e7d1b80a3b2c` | TDD enforcement: `check_tdd_commit.sh` on **commit-msg** — staged `web/src/*.ts(x)` prod requires paired `*.test.ts(x)` in same commit OR `tdd-skip: <reason>`. Install: `bash scripts/git/install-local-hooks.sh`. |
| 8 | `lesson_d6c0a79f2a1b` | RC-1 Vitest gate is **complete on branch** (16 tests / 5 files, CI `web-test`) but **not on `main`** until PR #118 merges. `origin/main` still has zero Vitest deps. |
| 8 | `lesson_c5bfa68e190a` | Post-rewrite branch triage: **dry cherry-pick onto current `main`** — if patch is empty/already absorbed, **delete branch, no PR** (CI/pt71 cluster, routing branches). |
| 8 | `lesson_b4aeb57d0809` | Overlapping CRLF turf PRs (#116, #117, #118) touch `platform/windows/gstack-brain-sync.cmd` — **land #116 first** or coordinate; avoid double-merge EOL fights. |
| 8 | `lesson_a39da46c0708` | Editing `using-git-worktrees/SKILL.md` with literal iCloud/OpenClaw paths triggers **LINT-006 / no-workstation-paths** hook — use `$(git rev-parse --show-toplevel)` in examples. |
| 7 | `lesson_928c935b0607` | Nav smoke pattern: click `Composer` / `Runs` / `Artifacts`, assert **exclusive** panel markers (`View All Runs` absent on composer page; `Swarm Composer` absent on runs page). File: `CommandCenter.test.tsx`. |
| 7 | `lesson_817b824a0506` | Fold exploratory scratch (#117) into integration PR (#118) when scopes overlap; scratch-only PRs pass CI without exercising Vitest if deps absent. |
| 7 | `lesson_706a71390405` | RC-1 minimum met with **state unit tests + nav smokes**; full `CommandCenter.test.tsx` for `:33` fallback optional when `commandCenterState.test.ts` covers logic. |
| 6 | `lesson_f5f94e8a7b6c` | Ship memory in **logical commit batches**: (1) tests, (2) hook/scripts, (3) TDD docs, (4) skill cross-refs — easier review than one blob. |
| 6 | `lesson_e4e83d796a5b` | Living evidence report: append **Progress status** section to `docs/testing/*.tdd.md` before merge so triage survives branch deletion. |
| 6 | `lesson_d3d72c68694a` | `gbrain sync` may block checkpoint on one bad SKILL.md — `gbrain sync --skip-failed` advances after acknowledging; unrelated to Vitest but surfaced same session. |
| 5 | `lesson_c2c61b57583b` | **Playwright E2E deferred** until Vitest gate merges to `main` — documented in `docs/TDD.md` post-gate backlog. |

## Memory writes (this session)

| Layer | Artifact |
|-------|----------|
| Episodic | `episodic/AGENT_LEARNINGS.jsonl` — `vitest-tdd-gate-session-2026-06-27` |
| Lessons | `semantic/lessons.jsonl` + re-render `semantic/LESSONS.md` |
| Domain | `semantic/DOMAIN_KNOWLEDGE.md` — § Vitest/TDD + § Git bash 3.2 row |
| Decisions | `semantic/DECISIONS.md` — Playwright defer + commit-msg TDD hook |
| Working | this file |
