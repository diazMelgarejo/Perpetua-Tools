# Codex CLI v0.142.x dispatch — 2026-06-28

> Gold nuggets from Windows Hermes testdrive + codex fanout fix. Canonical orama card:
> `orama-system/bin/orama-system/references/codex-cli-v142-dispatch.md`

## Flag profiles (sticky)

| Profile | When | Shape |
|---------|------|--------|
| **fanout** | Orchestrators (Hermes, Cursor, CI) | `codex exec -C <repo> -s workspace-write --dangerously-bypass-approvals-and-sandbox` |
| **bounded** | Safer mechanical edits | `codex exec -C <repo> -s workspace-write` |
| **interactive** | TTY / human present | `codex --sandbox danger-full-access --ask-for-approval never -C <repo>` |

## Path contract

- **Never** hardcode absolute host paths (`C:\<user>\…` or `/<user>/…`) in prompts or tracked docs (LINT-006).
- Resolve repo root: `$ORAMA_SYSTEM_PATH` or `git rev-parse --show-toplevel`.
- Resolve Codex: WinGet native before LM Studio npm shim (`ensure-partner-cli-paths.ps1`).
- Pytest paths in prompt: repo-relative (`tests/...`) with `-C` set to repo root.

## Launcher

```text
python bin/orama-system/skills/hermes-harness/scripts/dispatch_codex_partner.py --pytest tests/...
```

`--dry-run` prints resolved codex binary + argv.

## Removed

- `--approval-mode approve-all` (gone in Codex 0.140+)

## Evidence

- Win testdrive: native Codex 0.142.3 PASS; fanout failed on `--approval-mode` not version mismatch.
- Episodic: `AGENT_LEARNINGS.jsonl` 2026-06-28 codex-v142-dispatch entry.
