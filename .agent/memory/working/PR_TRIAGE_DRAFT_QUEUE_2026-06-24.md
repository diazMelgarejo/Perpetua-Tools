# Draft PR triage session (PT + orama) — 2026-06-24

**Context:** 25+ open draft PRs from cloud-agent batch; operator asked to close noise, rebase Tier 1, line-review Tier 2.

## Method (use every triage pass)

1. **Three-dot** (`origin/main...origin/<branch>`) — what the PR *claims* to add.
2. **Two-dot at tips** (`origin/main` vs `origin/<branch>`) — what would actually merge today.
3. **Cherry-pick onto fresh `main`** — surfaces conflicts when work already landed elsewhere.
4. **Never merge** a branch that is 100+ commits behind unless two-dot net-new is tiny and tested.

```bash
git fetch origin main <branch>
git diff --shortstat origin/main...origin/<branch>    # PR claim
git diff --shortstat origin/main origin/<branch>      # merge reality
git log --oneline origin/main..origin/<branch>        # orphan check after merge
```

## Perpetua-Tools — verdicts

| Tier | PRs | Action |
|------|-----|--------|
| **1 — rebase, review** | #183, #195 | Rebase onto `main`; do not merge until operator review |
| **2 — line review** | #185, (orama #135) | See net-new analysis below |
| **3 — close (duplicate/empty)** | #181–182, #186–189, #192–194, #197 | Close; superseded by `main` |
| **4 — close (orphan)** | #184, #191 | Post-merge orphan; zero unique diff |

**API note:** Cloud agent `gh pr close` fails (`Resource not accessible by integration`) — operator closes Tier 3–4 manually in GitHub UI.

### PT #183 — HTTP-local autoresearch preflight (Tier 1)

- **Branch:** `cursor/review-bridge-http-local-c4ae` @ `495f9c4` (rebased on `main`)
- **Files:** `orchestrator/autoresearch_bridge.py`, `tests/test_autoresearch_bridge.py` (+266)
- **`AUTORESEARCH_PREFLIGHT_MODE`:** `auto` \| `http-local` \| `ssh`
- **Win local:** skip 90s SSH; local `git fetch/reset` + `GET /v1/models`
- **Tests:** `pytest tests/test_autoresearch_bridge.py` — 38/38 on rebased branch
- **Status:** analyzed; not merged per operator

### PT #185 → #198 cherry-pick (only net-new)

**#185 closed** — superseded; remote branch `cursor/critical-bug-investigation-32a0` **deleted**.

**Only net-new fix:** `ModelRegistry._resolve_host` — when `active_tilting` + `backend=ollama`, use hostname from tilted IP but **port 11434**, not LM Studio `:1234`.

- **Follow-up:** PT **#198** `cursor/fix-ollama-port-active-tilting-c4ae` @ `5fc305e` — **ready for review** (cross-links #185)
- **Affected model:** `qwen3-30b-autoresearch-critic` (`config/models.yml`, `win-rtx3080`, ollama)
- **Tests:** `test_active_tilting_ollama_win_uses_model_port_not_lmstudio` — 35/35 `test_hardware_routing.py`

### PT #180 (prior session)

Rebased onto `main`; became **identical to `main`** (mojibake fix already on main). Closed; branch deleted.

## orama-system — verdicts

| Tier | PRs | Action |
|------|-----|--------|
| **1** | #129, #131, #132 | Rebase + review (not merged this session) |
| **2** | #135 | Close — tests/skills already on `main`; merge regresses keychain stdin hardening |
| **3–4** | #130, #133, #134 | Close — post-merge orphans |

### orama #133 — rebase onto `main` (integrative-merge orphan)

- **Pre-rebase three-dot:** 67 files, +5,905
- **Cherry-pick onto `d1d607e`:** conflicts on commit 1 (security overlap with #127)
- **At tips:** **57/67 files identical** to `main`; **10 differ — all regressions** (drops LINT-015, portal co-orchestration routes, truncates LESSONS)
- **Verdict:** close #133; integrative-merge doctrine + T2–T4 hardening already on `main`

### orama #135 — line review vs `main`

- Three-dot looks like +940 lines (tests + openclaw skill step numbers)
- **Reality:** `test_discover_lock.py`, `test_hermes_thin_skills.py`, `test_install_thin_skill_wrappers.py`, `test_repo_hygiene.py` **already on `main`**
- OpenClaw skills on `main` use `store_keychain_secret.sh` (stdin); #135 uses `security -w $token` on argv — **security regression**
- **Verdict:** close #135

## Branch cleanup (prior session)

29 remote branches deleted where `git diff origin/main origin/<branch>` was empty (0 three-dot diff). Keep branches with real remaining diffs.

## Lessons graduated (this session)

Run `python3 .agent/tools/show.py <lesson_id>` for full text.

- `lesson_50e33b4bf1ec` — active_tilting Win Ollama must keep :11434 not lm-studio :1234
- `lesson_5222ac71c9ef` — draft PR triage: two-dot at tips vs three-dot; cherry-pick net-new
- `lesson_30de39cf9ada` — post-merge orphan: rebase/cherry-pick onto main before trusting file counts

## Open follow-ups

| Item | Owner |
|------|-------|
| Merge **#198** (ollama port guard) | operator — **ready for review** |
| Merge **#183** after Win operator review | operator |
| Close Tier 3–4 PRs (15 PT + 3 orama) | operator (GitHub UI) |
| Close **#185** manually if still open (branch deleted) | operator |
| Close **#135**, **#133** | operator |
| Rebase Tier 1 orama **#129**, **#131**, **#132** | next agent pass |

## Local verify

```bash
# Ollama port guard (#198)
pytest tests/test_hardware_routing.py::test_active_tilting_ollama_win_uses_model_port_not_lmstudio -q

# Autoresearch HTTP-local (#183)
pytest tests/test_autoresearch_bridge.py -q
```
