# Perpetua-Tools — Claude Code Navigation

> Renamed: Perplexity-Tools → Perpetua-Tools (2026-04-20, trademark risk eliminated)
> Package: `@diazmelgarejo/perpetua-tools@0.9.9.9` · Role: Layer 2 — Middleware/Adapters
> GitHub: <https://github.com/diazMelgarejo/Perpetua-Tools>

---

## Meta-rule: Progressive Disclosure (Horse Pulls Cart)

**Documents own content. This file navigates.**
Skills operationalize docs — they don't copy them.
Full cross-repo instructions → [`../../CLAUDE-instru.md`](../../CLAUDE-instru.md)

---

## § 0 — Architectural Contracts

**Source of truth:**
[`../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md`](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md)
§§ 0–2.
**Lockstep:** PT and orama-system CLAUDE.md §0 must stay aligned — any structural change
commits to both repos.

| Topic | Where |
| ----- | ----- |
| Banned terminology (coordinator → orchestrator, etc.) | [Unified Plan § 1](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md) |
| 8 governing principles | [Unified Plan § 1](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md) |
| **Hard requirements** (Mac: Ollama + qwen3.5:9b-nvfp4 + bge-m3; Win: LM Studio) | [Unified Plan § 2](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md) · [`../../CLAUDE-instru.md § 6`](../../CLAUDE-instru.md) |
| **Shared types** (`OrchestrationSession`, `TaskEnvelope`, `WorkerAssignment`, `WorkerResult`, `VerificationResult`) | PT owns them in `orchestrator/contracts.py` — orama imports from PT, never reverse |
| Verifier gate (crystallization blocked without approved VerificationResult) | [Unified Plan § 2](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md) |
| V1 scope (MAESTRO/HITL deferred) | [Unified Plan § 2](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md) |
| AlphaClaw adapter surface | [`docs/adapter-interface-contract.md`](docs/adapter-interface-contract.md) |
| HITL accountability | [`docs/HUMAN-IN-LOOP-ACCOUNTABILITY.md`](docs/HUMAN-IN-LOOP-ACCOUNTABILITY.md) |
| Search frugality rule (gbrain → CRG → Brave → Perplexity → Grok) | [`../orama-system/bin/orama-system/skills/openclaw-skills/references/universal-skill-protocol.md`](../orama-system/bin/orama-system/skills/openclaw-skills/references/universal-skill-protocol.md) § Search Frugality Rule |
| Win coder pool (`$WIN_CODER_ENDPOINTS`, always-utilized before Mac-local) | [`../orama-system/bin/orama-system/skills/openclaw-skills/references/universal-skill-protocol.md`](../orama-system/bin/orama-system/skills/openclaw-skills/references/universal-skill-protocol.md) § Windows Coder Policy |

**Quick invariants:**

- `orchestrator` only — never `coordinator` as its synonym/replacement in public APIs,
  schemas, config, or headings (control-plane scope). A distinct, documented agent persona
  named "Coordinator" — e.g. orama's `relay-cursor` — is not banned; see
  [orama Unified Plan § 1.1 scope note](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md#-1--governing-principles-non-negotiable)
- PT is **runtime/state authority**: job queue, hardware affinity, model routing, GPU
  safety, LAN routing, durable artifacts
- orama is stateless (planning/methodology only); imports shared types from PT, never the reverse
- `@field_validator` (Pydantic V2) — never deprecated `@validator`
- AlphaClaw: CLI + HTTP only — never `require()` or internal imports
- **Mac hard requirements:** Ollama (`localhost:11434`) with `qwen3.5:9b-nvfp4` + `bge-m3`
  — probe on startup; fail closed if absent
- **Win hard requirement:** LM Studio at `$LM_STUDIO_WIN_ENDPOINTS` — fail loudly if unreachable
- **Optional:** LM Studio Mac (secondary fallback only), cloud APIs, all other local models

---

## § 1 — Continuous Learning

Every session: read [`docs/LESSONS.md`](docs/LESSONS.md) at start; append before exit.
Cross-repo companion: [`../orama-system/docs/LESSONS.md`](../orama-system/docs/LESSONS.md)
Instinct path: `.claude/homunculus/instincts/inherited/Perpetua-Tools-instincts.yaml`

---

## § 2 — ECC Post-Merge Workflow

After any ECC Tools PR merges:

```bash
git pull origin main
/instinct-import .claude/homunculus/instincts/inherited/Perpetua-Tools-instincts.yaml
/instinct-status
git add -A && git commit -m "chore(ecc): post-merge instinct import sync" && git push origin main
```

---

## § 3 — Session Resources

| Resource | Purpose |
| -------- | ------- |
| [`SKILL.md`](SKILL.md) | Model selection rules + agent behavioral rules |
| [`docs/LESSONS.md`](docs/LESSONS.md) | Chronological session log |
| [`docs/wiki/README.md`](docs/wiki/README.md) | Wiki index |
| [`docs/adapter-interface-contract.md`](docs/adapter-interface-contract.md) | Living AlphaClaw API surface — update after every upstream merge |
| [`docs/wiki/07-multi-agent-collab.md`](docs/wiki/07-multi-agent-collab.md) | Version registry, scope claims, conflict recovery |
| [`PHASE_TRACKING.md`](PHASE_TRACKING.md) | Phase workflow and distributed task queue CLI reference |
| [`../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md`](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md) | Canonical architecture — PT is L2 in this plan |

---

## § 4 — AutoResearcher

Plugin: `uditgoenka/autoresearch`. Per-session: `/autoresearch`.
Read + write `docs/LESSONS.md` around experiments. GPU guard: check `GPU: BUSY`
in `swarm_state.md` before dispatch.
Full spec: [`docs/wiki/07-multi-agent-collab.md`](docs/wiki/07-multi-agent-collab.md)

---

## § 5 — Three-Repo Architecture

```text
AlphaClaw (L1 — infra, CLI+HTTP only) → Perpetua-Tools (L2 — THIS REPO) → orama-system (L3 — orchestration)
```

**PT owns:** `orchestrator/contracts.py` (shared types), `orchestrator/`, `config/`, `packages/`.
**PT drives AlphaClaw via:** REST endpoints documented in [`docs/adapter-interface-contract.md`](docs/adapter-interface-contract.md).
**orama drives PT via:** `orchestrator/orama_bridge.py`.

MCP server registration (canonical — TypeScript, 14 tools, v0.9.16.9):

```bash
cd packages/alphaclaw-mcp && npm run build && cd ../..
claude mcp add --transport stdio alphaclaw -- node packages/alphaclaw-mcp/build/index.js
```

> Gate 0 JS server (`packages/alphaclaw-adapter/src/mcp/server.js`) has been absorbed and deleted.
> `packages/alphaclaw-mcp` is now the single entry point for ALL AlphaClaw MCP functions.

Full architecture: [`../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md`](../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md)
As-built: [`../orama-system/docs/v2/`](../orama-system/docs/v2/)

---

## § 6 — Git Hygiene

- Commit identity: `cyre <Lawrence@cyre.me>`, `cyre <diazMelgarejo@gmail.com>`, or
  `Codex <codex@openai.com>` — `bash scripts/git/check_identity.sh`
- **Private banned-identity list (gitignored, not on GitHub):**
  `.cursor/private/agent-lesson-git-attribution.md` — sync via
  `bash scripts/cursor/install-user-git-environment.sh`; never copy tokens into tracked docs.
- **Every session:** `bash scripts/git/daily-attribution-guard.sh` (all workspace repos).
  Re-adding forbidden `Co-authored-by` forces another `main` + all-branch rewrite — use
  `commit-clean.sh` and `publish-clean-branch.sh` only.
- Official stack policy (co-author allowlist + hooks):
  [`../orama-system/docs/wiki/08-git-hygiene-and-branching.md`](../orama-system/docs/wiki/08-git-hygiene-and-branching.md#official-commit-identity-policy-2026-05-25);
  install: `bash scripts/git/install-local-hooks.sh`
- Dated branches: `yyyy-mm-dd-NNN-brief-summary`
- Lockstep commits: changes to shared schema fields, exception classes, or policy keys commit
  to **both repos in the same session**
- Never commit `.env`, `.env.local`
- **Local runtime overlay (`config/devices.yml`, `config/models.yml`):** discovery may write
  operator LAN IPs into the working tree as a safe last-known cache — **never `git checkout`/`git
  restore` to discard**; **never commit** those values. Stash before pull if needed; on restore
  use `git -c core.hooksPath=/dev/null stash pop` then
  `bash scripts/git/install-local-hooks.sh`
  ([stash-hooks safeguard](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-history-surgery/references/stash-hooks-safeguard-reference-card.md)).
  Policy: [`config/LOCAL-RUNTIME-OVERLAY.md`](config/LOCAL-RUNTIME-OVERLAY.md); gate:
  `scripts/git/check_local_runtime_overlay.py`; orama skill cards:
  [`local-runtime-overlay`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/using-git-worktrees/references/local-runtime-overlay-reference-card.md),
  [`CLAYGO integrity diff`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/using-git-worktrees/references/fresh-main-integrity-diff-claygo.md)
- **No workstation paths in tracked files** (docs included): use `$OPENCLAW_ROOT`/`~`/`$REPO_ROOT`,
  never literal `/Users/<name>/…` or the `…/claude/OpenClaw` tree. CI enforces via
  `scripts/review/repo_hygiene.py` (same checker as orama) — run it before committing docs with
  shell commands. Rule:
  [`../orama-system/docs/wiki/08-git-hygiene-and-branching.md`](../orama-system/docs/wiki/08-git-hygiene-and-branching.md#portable-paths-in-tracked-files-no-workstation-leaks)
- **No mojibake:** Windows PowerShell/Python can default to cp1252. Before scripts that read/write
  tracked text, force UTF-8 (`[Console]::InputEncoding`, `[Console]::OutputEncoding`,
  `$OutputEncoding`, and Python `encoding="utf-8"`). `scripts/review/repo_hygiene.py` enforces
  LINT-007 using the orama-system escape-only detector pattern.
- **History was rewritten — judging branches:** NEVER use ahead/behind, `rev-list --count`, or
  `merge-base` to decide if a branch is orphaned/divergent (meaningless across a rewrite). Run
  `scripts/git/reanchor_scan.sh . origin/main heads`. Protocol:
  [`AGENTS.md` § History-rewrite](AGENTS.md) · method
  [git-reanchor SKILL.md](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-reanchor/SKILL.md)
  · branch salvage map [LESSONS § 2026-06-05](docs/LESSONS.md).
- **Attribution guards: single source of truth (ZERO fragmentation).** The canonical copies of
  `audit_attribution.sh`, `banned_attribution_lib.sh`, `check_commit_message.sh`,
  `check_identity.sh`, `daily-attribution-guard.sh` live in
  [orama `scripts/git/`](https://github.com/diazMelgarejo/orama-system/tree/main/scripts/git) and
  are **byte-identical here**. NEVER hand-edit a guard in this repo — a stale fork once made PT's
  strict pre-push flag valid mainstream-AI co-authors that orama allows. Edit orama's copy, then
  `bash ../orama-system/scripts/git/sync-attribution-guard-scripts.sh .`.
  `daily-attribution-guard.sh` is self-contained (no wrapper). Org-wide plan:
  [`../orama-system/docs/v2/`](../orama-system/docs/v2/).

---

## § 7 — gstack

gstack v1.37.0.0 at `~/.claude/skills/gstack`.

- ALWAYS use `/browse` for web — NEVER `mcp__claude-in-chrome__*` directly
- `/plan-eng-review` before any Gate 0→1 transition; `/ship` before `npm publish`

---

## GBrain Search Guidance (configured by /sync-gbrain)
<!-- gstack-gbrain-search-guidance:start -->

GBrain is set up and synced on this machine. The agent should prefer gbrain
over Grep when the question is semantic or when you don't know the exact
identifier yet.

**This worktree is pinned to a worktree-scoped code source** via the
`.gbrain-source` file in the repo root (kubectl-style context).
`gbrain code-def`, `code-refs`, `code-callers`, `code-callees`, `search`, and
`query` from anywhere under this worktree route to that source by default —
no `--source` flag needed (gbrain >= 0.41.38.0; on older gbrain the call-graph
commands need `--source "$(cat .gbrain-source)"`). Conductor sibling worktrees
of the same repo each have their own pin and their own indexed pages, so
semantic results match the code on disk here.

Call-graph queries (`code-callers`/`code-callees`) also need the graph to be
built first — run `/sync-gbrain --dream` (or `--full`) if they return
`count: 0`. This only works if this source's gbrain schema pack extracts code
symbols; on a non-code-aware pack `--dream` completes but the graph stays empty
and reports a WARN. `code-def`/`code-refs` need the same extraction.

Two indexed corpora available via the `gbrain` CLI:

- This worktree's code (auto-pinned via `.gbrain-source` → `gstack-code-078b0b90-f6179f`;
  supersedes `gstack-code-ools-27e2b79c-df8a28` (stale @2026-06-05, reindexed 2026-06-17).
- `~/.gstack/` curated memory (registered as `gstack-brain-lawrencecyremelgarejo` source via
  the existing federation pipeline).

Prefer gbrain when:

- "Where is X handled?" / semantic intent, no exact string yet:
    `gbrain search "<terms>"` or `gbrain query "<question>"`
- "Where is symbol Y defined?" / symbol-based code questions:
    `gbrain code-def <symbol>` or `gbrain code-refs <symbol>`
- "What calls Y?" / "What does Y depend on?":
    `gbrain code-callers <symbol>` / `gbrain code-callees <symbol>`
- "What did we decide last time?" / past plans, retros, learnings:
    `gbrain search "<terms>" --source gstack-brain-lawrencecyremelgarejo`

Grep is still right for known exact strings, regex, multiline patterns, and
file globs. Run `/sync-gbrain` after meaningful code changes; for ongoing
auto-sync across all worktrees, run `gbrain autopilot --install` once per
machine — gbrain's daemon handles incremental refresh on a schedule.

Safety: don't run `/sync-gbrain` while `gbrain autopilot` is active — the
orchestrator refuses destructive source ops when it detects a running autopilot
to avoid racing it (#1734). Prefer registering user repos with `gbrain sources
add --path <dir>` (no `--url`): URL-managed sources can auto-reclone, and the
sync code walk for them requires an explicit `--allow-reclone` opt-in.

<!-- gstack-gbrain-search-guidance:end -->

---

## § 8 — Parallel Agents & Git Worktrees

**When to create a worktree:** task requires parallel file writes by multiple agents.
**When to stay on canonical:** read-only, sequential, or single-agent work.

Bootstrapping, port offsets, GPU coordination, and CRG policy are defined in the canonical doc:
→ `orama-system/docs/v2/19-worktree-parallel-agents.md`
→ Real-time skill: `~/.claude/skills/using-git-worktrees/SKILL.md`

**Quick start:**

```bash
orama-system/scripts/worktree-bootstrap.sh <repo-path> <branch> <slug> [gbrain-source]
```

**Hardware (2026-05-24):** 1 Win RTX3080 + Mac Ollama. PT is the inference chokepoint.

---

## § 9 — Dependency Vulnerability Triage: Frugality Rules & Resolution Decisions

**Context:** GitHub flagged 21 Dependabot alerts (4 high, 10 moderate, 7 low)
on `main` (2026-06-17). Triaged and fixed without spending a GitHub token.
This section exists so the next session doesn't re-derive any of this.

### Frugality rule: OSV.dev before GitHub Dependabot Alerts API

The GitHub Dependabot Alerts API requires a token with `security_events`
scope (classic PAT) or "Dependabot alerts: read" (fine-grained PAT) — a
credential escalation. **Use the free, unauthenticated OSV.dev batch API
first:**

```bash
# Python: extract pinned versions from uv.lock, batch-query OSV (PyPI ecosystem)
# npm:    extract from package-lock.json / pnpm-lock.yaml, batch-query OSV (npm ecosystem)
curl -s -X POST https://api.osv.dev/v1/querybatch \
  -H "Content-Type: application/json" \
  -d '{"queries": [{"package": {"name": "<pkg>", "ecosystem": "PyPI"}, "version": "<pinned>"}]}'
```

This queries the **exact pinned version already on disk** — more precise
than a generic CVE feed, and got within 2 of GitHub's count (19 vs 21; the
gap is the GitHub Actions ecosystem, not checked). Zero auth required.
Full method + results: `docs/2026-06-17-dependabot-vulnerability-triage.md`.

### Minimum dependency fix versions (decided 2026-06-17)

| Package | Was | Fixed to | File | Status |
| ------- | --- | -------- | ---- | ------ |
| `starlette` | 1.0.1 | **1.3.1** | `uv.lock` (transitive via `fastapi>=0.46.0`, no ceiling conflict) | Fixed |
| `aiohttp` | 3.14.0 | **3.14.1** | `uv.lock` (direct, `requirements.txt` floor already `>=3.14.0`) | Fixed |
| `hono` | 4.12.23 | **4.12.25** | `packages/local-agents/package.json` + lock (was transitive via `@modelcontextprotocol/sdk`, now pinned direct) | Fixed |
| `js-yaml` | 4.1.1 | 4.2.0 | `vendor/ecc-tools/package-lock.json` | **Out of scope — submodule, see below** |
| `markdown-it` | 14.1.1 | 14.2.0 | `vendor/ecc-tools/package-lock.json` | **Out of scope — submodule, see below** |

**Treat these as the floor going forward** — don't let a future lockfile
regen silently drop below these without re-checking OSV.

### Resolution decision: never vendor-patch a tracked submodule directly

`vendor/ecc-tools` is a git submodule pinned to
`github.com/affaan-m/everything-claude-code` (commit
`928076cc08cbb31e8549cea2883b4f51811de1c8` as of 2026-06-17). When a
vulnerability is found inside a submodule's own lockfile, **the fix is to
bump the submodule's pinned commit once upstream patches it — never edit
files inside the submodule directly.** This follows the zero-fragmentation
doctrine already established in `docs/v2/27-git-governance-zero-fragmentation.md`
and `SECURITY.md`. Document the deferral explicitly in the triage doc and PR
description; do not silently drop the finding.

### Gotcha: multiple npm manifests, easy to fix the wrong one

This repo has 4+ Python/npm dependency manifests
(`packages/alphaclaw-mcp/pnpm-lock.yaml`, `packages/local-agents/package-lock.json`,
`vendor/ecc-tools/package-lock.json` [submodule], plus a nested
`vendor/ecc-tools/.opencode/package-lock.json`). **A package name match across
manifests doesn't mean the same vulnerable version exists in all of them** —
`hono` was already fixed in `alphaclaw-mcp` but stale in `local-agents`.
Always `grep` the *exact* version string in the *specific* file before
patching, and re-verify after with `git diff --stat` to catch wrong-file
edits.

### Gotcha: plain `git clone` does not initialize submodules

`vendor/ecc-tools`, `vendor/Claude-Desktop-LLM`, and `vendor/agentic-stack`
are all submodules (see `.gitmodules`). A plain `git clone` leaves them as
empty directories — files inside (e.g. `vendor/ecc-tools/package-lock.json`)
won't appear until `git submodule update --init <path>`. If a fresh clone
disagrees with an earlier session's findings about what's "in" a vendored
path, this is almost always why — re-init before trusting a negative result.

### Gotcha: working-tree clones can carry stray submodule gitlink noise

If `git status`/`git diff` shows `vendor/ecc-tools` modified with no
intentional edit, it's likely the on-disk submodule's checked-out HEAD
differs from the recorded gitlink (common after a `submodule update --init`
in an earlier session leaves residue across clones). Confirm via
`git diff --submodule=log -- vendor/ecc-tools` — if it says "commits not
present," it's clone noise, not a real change. **Exclude it from `git add`
explicitly** rather than trying to "fix" it; don't let it ride into an
unrelated commit.
