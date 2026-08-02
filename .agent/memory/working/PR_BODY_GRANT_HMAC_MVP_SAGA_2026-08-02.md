# PR-body grant HMAC MVP — saga chronicle (2026-08-02)

> **Status:** implemented on paired branches (orama canonical, PT mirror)  
> **orama-system:** branch `2026-08-02-pr-body-grant-hmac-mvp` (post-#255 `main`, commit after `525961d6`)  
> **Perpetua-Tools:** branch `2026-08-02-pr-body-grant-hmac-mvp` (tracks PR #320 wave)  
> **Trigger chain:** CodeRabbit `4835288649` on orama #255 → `/autoplan` DONE_WITH_CONCERNS → can-4.md nitpicks on PT #320  
> **Canonical plan:** `orama-system/docs/plans/2026-08-02-pr-body-grant-security-remediation.md`  
> **Research:** `orama-system/bin/orama-system/references/pr-body-human-grant-security-gap-research.md`  
> **v2.1 deferral:** `orama-system/docs/v2/51-security-sentinel-orbit-passkey-mcp.md`

## Executive outcome

We closed the **grant forgery gap** left after orama #255 merged Layer 0 + `operator-grant-v1`.
That v1 path was policy theater: agents with a PTY could run the grant script or write the ack
file directly. MVP replaces it with **operator-grant-v2**: HMAC over a canonical payload that
binds **repo, PR number, action, append-content digest, nonce, and issued-at**; **8h TTL**;
**single-use** via atomic nonce consumption and ack file deletion.

Same-user Keychain HMAC is **escalation control**, not human identity. WebAuthn + MCP approval
stay in v2.1 **security-sentinel** orbit (do not half-implement passkeys in shell scripts).

## Timeline (how we got here)

| When | Event | Why it mattered |
| ---- | ----- | ---------------- |
| 2026-08-01 | Guard-sync epic + PR-body Layer 0 land on PT #319 / orama #255 | Agents blocked from body writes; human override path introduced |
| 2026-08-01 | CodeRabbit waves `4835024659` + `4835288649` on orama #255 | Worktree discovery, fail-closed hooks, grant script v1 |
| 2026-08-02 | orama #255 **merged** to `main` at `525961d6` | Baseline for fresh branch, not old PR tip |
| 2026-08-02 | EXA + Firecrawl deep research on TTY/HITL gap | Proved v1 is forgeable; Vallum HMAC + GoodRoom passkey patterns |
| 2026-08-02 | `/autoplan` on remediation plan (local, no git ops) | Refined: digest binding, nonce replay, append independent verify, BACKUP wire-up |
| 2026-08-02 | can-4.md (CodeRabbit on PT #320) | DRY hooks, restore BACKUP emission, tighten worktree test, `range_for_ref` in pre-push |
| 2026-08-02 | Implementation on `2026-08-02-pr-body-grant-hmac-mvp` | Single worktree consolidation (`/tmp/orama-grant-mvp` → commit → sync to PT) |

## Research that preceded code (read before changing grants)

| Source | What we took |
| ------ | ------------ |
| EXA neural search (6 queries, ~54 sources) | TTY ≠ human; agent shells have PTY; forgeable marker files |
| Firecrawl scrape (15 primary URLs) | OWASP AI Agent Cheat Sheet, Vallum HMAC PR #32, GoodRoom passkey MCP |
| orama `pr-body-human-grant-security-gap-research.md` | Verdict table, trivial bypass recipe, community consensus |
| `/autoplan` eng review | HMAC must bind **content digest**; nonces need atomic consume; append must verify independently |

**Rerun research:** `workflow: firecrawl-deep-research`, topic: PR-body operator grant HMAC,
depth: thorough. Primary file: research doc above.

## Architecture (MVP vs v2.1)

```text
Operator terminal (TTY, not agent/CI)
  → grant-pr-body-human-override.sh <owner/repo> <N> --file|--message
  → pr-body-grant-lib.py mint → ~/.cursor/pr-body-human-override-ack (v2 fields + HMAC)

Agent session
  → beforeShellExecution / beforeMCPExecution
  → pr_body_run_guard() in pr-body-backup-lib.sh
  → pr-body-guard-core.py: verify grant + emit BACKUP|repo|pr on valid append segment
  → pr_body_backup_if_needed() (READ snapshot before risky command)

Operator or agent (with valid grant)
  → append-pr-body.sh: verify grant again → READ→backup→merge→WRITE → consume grant
```

**v2.1 (not in this PR):** `security-sentinel` satellite verifies Ed25519 JWKS proofs; hooks become clients.

## Decision log (binding for this wave)

| ID | Decision | Rationale | Rejected alternative |
| ---- | -------- | --------- | -------------------- |
| D1 | `operator-grant-v2` only; v1 fail-closed | v1 was trivially forgeable | Gradual v1/v2 dual accept |
| D2 | HMAC payload includes `action` + `content-digest` | Stops grant reuse for different append text | Repo/PR bind only (autoplan concern) |
| D3 | Single-use: consume nonce + delete ack after successful append | Replay of copied ack file | TTL-only reuse within 8h |
| D4 | `append-pr-body.sh` calls `pr-body-grant-lib.py verify` | Hook arg parsing alone insufficient | Trust hook ALLOW only |
| D5 | Restore `BACKUP\|repo\|pr` from guard-core for append segments | Hook handlers were dead after hardening; backup still needed | Remove BACKUP handling (CodeRabbit misread) |
| D6 | `pr_body_run_guard(mode, reason, input)` in backup-lib | DRY shell/MCP hooks (can-4) | Duplicate 30-line blocks |
| D7 | Secret: Keychain `openclaw.pr_body_grant.hmac`, fallback `~/.openclaw/secrets/` | Cross-platform per mesh patterns | Env-only secret |
| D8 | Strict TTY: `! -t 0 \|\| ! -t 1` + deny `CURSOR_AGENT` / `CI` | Defense in depth (not sufficient alone) | TTY-only gate |
| D9 | Fresh branch from post-#255 `main`, not old PR tip | #255 already merged | Continue on `2026-07-31-010-*` |
| D10 | orama canonical → `sync-attribution-guard-scripts.sh` → PT | Two-repo invariant | Hand-edit PT only |

## Files touched (canonical orama paths)

| Path | Role |
| ---- | ---- |
| `scripts/cursor/pr-body-grant-lib.py` | Mint, verify, consume; HMAC, nonce store, digest |
| `scripts/cursor/grant-pr-body-human-override.sh` | Operator mint CLI wrapper |
| `scripts/cursor/append-pr-body.sh` | Independent verify + consume after `gh pr edit` |
| `scripts/cursor/hooks/pr-body-guard-core.py` | Segment scan, grant verify, BACKUP emission |
| `scripts/cursor/hooks/pr-body-backup-lib.sh` | `pr_body_run_guard`, `pr_body_backup_if_needed` |
| `scripts/cursor/hooks/before-*-pr-body-guard.sh` | Thin wrappers calling `pr_body_run_guard` |
| `scripts/git/sync-attribution-guard-scripts.sh` | Sync full cursor grant/hook bundle to PT |
| `.githooks/pre-push` | Shared `range_for_ref()` for guard-sync + attribution |
| `tests/test_pr_body_grant_lib.py` | HMAC, digest mismatch, v1 reject, replay |
| `tests/test_pr_body_guard_core.py` | Newline bypass + BACKUP with valid grant |
| `tests/test_check_guard_sync_divergence.py` | Assert `pt-linked` only (worktree path) |

## Operator workflow (copy-paste)

```bash
# 1. Operator terminal (not Cursor agent shell)
cd orama-system   # or PT — same scripts after sync
bash scripts/cursor/grant-pr-body-human-override.sh owner/repo 320 --file follow-up.md

# 2. Same machine, may be agent shell if grant already minted
bash scripts/cursor/append-pr-body.sh owner/repo 320 --file follow-up.md
```

Grant and append must use the **same** `--file` or `--message` (digest binding).

## Verification (run before merge)

```bash
# orama or PT after sync
python3 -m pytest tests/test_pr_body_grant_lib.py tests/test_pr_body_guard_core.py -q
python3 -m pytest tests/test_check_guard_sync_divergence.py::test_linked_worktree_sibling_discovered -q

# Smoke: deny update_pr body
python3 scripts/cursor/hooks/pr-body-guard-core.py manage_pr <<< \
  '{"tool_name":"ManagePullRequest","tool_input":{"action":"update_pr","body":"x"}}'
# expect DENY|OVERRIDE SCOPE...
```

## Tips for future humans and agents

1. **Do not trust TTY for identity.** If the control is “run in operator terminal,” document
   that agents can still satisfy TTY. Cryptographic binding + tool-boundary enforcement is the bar.

2. **Do not remove BACKUP\| handling** when tightening guards. Preflight READ snapshots are the
   last line before a rare authorized append. Dead hook branches mean silent loss of backups.

3. **Grant must match bytes, not intent.** Operator must re-grant if they change the follow-up
   markdown after minting. That is intentional (hashgate-style binding).

4. **Sync direction:** orama canonical for `scripts/cursor/*` grant stack. Commit orama first;
   then `sync-attribution-guard-scripts.sh` to PT. Never blind orama→PT on dirty worktrees.

5. **Worktree consolidation:** Multiple agents used `/tmp/orama-grant-mvp`, `/tmp/orama-pr255`,
   `/tmp/pt-pr320`. Before commit: one clean worktree on the PR branch, `git status` clean,
   single push. Stash/pop caused plan doc conflicts — resolve before commit.

6. **autoplan artifacts** live in `~/.gstack/projects/orama-system/` (test plans, restore points).
   They are not git-tracked; link from plan doc if needed.

7. **v2.1 scope creep guard:** Any WebAuthn, MCP `verify`, or JWKS in orama scripts is wrong repo.
   Extend `docs/v2/51-security-sentinel-orbit-passkey-mcp.md` instead.

## Reflections (agent notes)

The frustrating part of this saga was not the crypto. It was **orphaned hook paths**: security
hardening removed `BACKUP|` emission while shell hooks still parsed it, so backup looked “done”
but never ran. Harmonizing “edge case code” with “default deny” means tracing **every** directive
the hook consumes, not just the DENY paths.

`/autoplan` was valuable for catching **incomplete binding** (digest, nonce) that CodeRabbit
did not spell out. Treat DONE_WITH_CONCERNS as a implementation checklist, not a deferral.

Pairing orama + PT on the **same branch name** (`2026-08-02-pr-body-grant-hmac-mvp`) reduced
drift. PT PR #320 is the integration surface; orama is canonical for scripts.

## Related memory on this branch

- `CODERABBIT_REVIEW_WAVE_4835024659_4835288649_2026-08-01.md` (Batch F added)
- `PR_BODY_COMMENT_ONLY_FRUSTRATION_CHAIN_2026-08-01.md` (Layer 0 context)
- `GUARD_SYNC_EPIC_SAGA_COMPLETION_2026-08-01.md` (prior wave)
- `WORKSPACE.md` (current focus)

## Open follow-ups (not blocking MVP)

- [ ] Open orama PR from `2026-08-02-pr-body-grant-hmac-mvp`; update PT #320 body with orama tip SHA
- [ ] Doctrine pass: hookify + `.cursor/rules` still mention v1 / env override in some places — grep `operator-grant-v1`
- [ ] `check_tdd_commit.sh` unbound `staged[@]` on empty index under `set -u` (macOS bash) — unrelated but blocked one commit attempt
- [ ] security-sentinel repo + perpetua-core plugin slot (v2.1)
