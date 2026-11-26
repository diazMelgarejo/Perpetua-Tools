# Session chronicle 2026-11-26: OpenClaw seats, env keys, codex plugin and the staged restore

Companion to the lessons recorded the same day by `learn.py`. This file keeps the decisions, the
sequence and the open items; the lessons keep the rules. Paths use `~`; nothing here is a credential.
The procedure itself lives in the orama first-run reference
`openclaw-staged-restore-and-recovery.md`; this chronicle is the dated record behind it.

## Decisions (operator rulings)

- **Default model chain:** W&B DeepSeek V4.1 Flash at high effort, then Google Gemini Flash
  (medium), local Ollama, OpenRouter free. Mac LM Studio is manual only, in no chain. Windows LM
  Studio only from the discovery file. W&B is never removed from any agent chain.
- **Seats:** `biafra` (alias MetaResearcher, guardian and companion of `autoresearcher`) and
  `autoresearcher` default to `openai/gpt-6.1-terra` at medium effort, then the default chain.
  Astra and Sol are human-gated: explicit operator approval, never spawned by default, never
  automatic; unattended Codex jobs run Terra. The OpenAI login is per agent for those two seats
  only (`openclaw models auth login --provider openai --agent <id>`), never `main` or the gateway.
- **Seat tools:** deny `exec`, `process`, `browser`, `canvas`, `nodes`, `cron`, `gateway`. A live
  test showed the denial on one seat; the other still reported an exec tool that could not run.
- **Sandbox:** staged. Tool policy now; a dedicated macOS user plus a Seatbelt profile (a draft,
  8 of 8 local cases passed, not yet tested over ssh) only when a seat must run code. No Docker.
- **Gateway sees the OpenAI API key** by design (login-only ruling still holds because no agent
  resolves to it); `main` and all other agents stay on W&B.
- **Env:** `~/.env` is the single source for working keys; the gateway gets custom keys through its
  global env file plus a restart. Aliases by reference replace dead keys (Cline-Google to the
  second Gemini key, Copilot to the GitHub token). The expired GitHub token line was removed.
- **Obsolete node:** 24.14.1 retired after every reference moved to the stable link.

## Sequence and results

1. Codex plugin was installed but failed to load: the data volume was full (ENOSPC). Freed 3.6 GB
   by retiring node 24.14.1 (repointed shell, launch agent, tool links, MCP entries, wrapper script;
   stopped four processes; moved the folder to the Trash; the operator emptied it).
2. Enabled the plugin and set the OpenAI codex runtime. Both seats answered on Terra through the
   codex harness with their own login profile.
3. W&B failed in the gateway (the shell import covers well-known keys only). Global env file plus a
   restart fixed it; a forced W&B run returned in about five seconds.
4. Restored the sourced env files. Old W&B, OpenRouter and Firecrawl keys returned 401 and would
   have shadowed working keys; the dead lines were stripped, originals kept.
5. Full key audit by provider status: working Brave, GitHub, Gemini (two), OpenAI, OpenRouter,
   Telegram, W&B, Firecrawl, Exa; dead Cline-Google, Copilot, expired GitHub; GLM52 was empty
   in shells because of an unquoted dollar sign (quoted now; the provider balance is separate).
6. Two launch agents ran wrapper scripts left in the aside state folder; restored them.
7. Old-versus-new config diff: 408 old settings against 160 new.

## Backup and recovery in one view

Per-stage config backups (mode 600), archives of the old state with checksums, the aside folder,
the as-restored copies of every edited env file. Roll back a stage by restoring its backup and
restarting; roll back the cutover by stopping the service, renaming the failed state, restoring the
aside state and the saved service file. A rollback restores data, not a crash-looping gateway.
Cleanup goes through the Trash, never a recursive force remove.

## Outcome: consolidated pull requests

- Perpetua-Tools draft #523 (this branch, base main) and orama-system draft #531 (base main) are the
  one consolidated PR per repo for the session. AlphaClaw had nothing unpushed.
- PT #522 was closed: merged with main its tree equals main, because the records arrived through #517.
  The review's five findings got inline replies; three were fixed here as superseding lessons and two
  were already superseded in main.
- orama #531 also carries the six steipete/agent-scripts commits (re-applied on main) and a fix that
  pins the installer's third-party clone to one reviewed upstream commit.
- Parked, not published: older review lanes and the keep-never-merge research throwaway; the next
  step is a per-lane review by tree-level diff, not by commit counts.

## Next order (pick up later, one at a time)

1. Restore `agents.defaults.subagents` (orchestrator delegation; add `biafra`).
2. Restore the small `agents.defaults` bootstrap settings.
3. Operator decision on the old `tools.exec` security posture.
4. Review old cron jobs and exec approvals one by one.
5. Web search wiring (Brave, Exa, Firecrawl; Exa into the gateway env file only if needed).
6. Plugins one at a time, then skills by choice, then OpenClaw MCP servers.
7. Channels last, owner allow-list only after the operator confirms.
8. Windows LM Studio only once the discovery file exists.

## Open items

Discovery file not written after the cutover (watcher restored, first cycle pending); service PATH
names a node version; per-call approval for web-search tools unverified; commits unpushed in
Perpetua-Tools, orama and the Codex local commit.
