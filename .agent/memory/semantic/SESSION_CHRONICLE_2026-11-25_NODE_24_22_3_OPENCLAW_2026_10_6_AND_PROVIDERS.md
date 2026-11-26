# Session chronicle 2026-11-25: Node 24.22.3, OpenClaw 2026.10.6, AlphaClaw PR 34 and provider order

Companion to the nine lessons recorded the same day by `learn.py`. This file keeps the sequence and
the results; the
lessons keep the rules. Paths use `~`; nothing here is a credential.

## Done

- **ai-cli-mcp:** upgraded from 2.22.0 to 3.2.0 under Node 24.22.3. Its startup banner was normal:
  it is a stdio MCP
  server and does not print a version.
- **omniroute:** left disabled. Fix-later notes are in `~/.omniroute/NOTES-node-24.22.3-install-fix-later-2026-11-25.md`.
  Cause: npm 11 skipped its install scripts during the nvm package migration; the note lists the
  rebuild steps.
- **Node:** 24.22.3 is the nvm default, 22.22.2 stays, and 24.14.1 carries an
  `OBSOLETE-2026-11-25.txt` marker. The old
  gateway plist pointed at 24.14.1, so that version stayed as the rollback until the cutover.
- **Global openclaw:** upgraded to 2026.10.6, the version the AlphaClaw PR 34 build pins.
- **PR 34 dry run** (Node 24.22.3, pnpm): `pnpm install --frozen-lockfile` and `node --check
  bin/alphaclaw.js` pass, and
  the suite passed 112 test files and 876 tests. The first attempt with `npm ci` failed only because
  the repo uses pnpm.
- **Backups** in `~/claude-config-backups/alphaclaw-openclaw-baseline-20261125/`: the full set is
  kept until the update
  succeeds, plus a 19 MB slim config archive that leaves out `.npm`, `lib/node_modules` and `plugin-runtime-deps`.
  Two obsolete plugin runtimes (openclaw 2026.4.29 and 2026.4.25-beta.1, 920 MB) went to the Trash,
  not deleted.

## Provider findings from OpenClaw 2026.10.6's own docs

- **Google web login is not available.** OpenClaw "does not offer new Gemini CLI OAuth or
  Antigravity OAuth setup".
  Google ended consumer Gemini CLI login on 2026-06-18 and the Antigravity terms prohibit
  third-party tools. The
  supported route is an AI Studio API key, with `google/gemini-3.8-flash` (alias `gemini-flash`) and
  a `thinkingLevel` of
  medium. The operator enters the key.
- **Codex login is supported:** `openclaw models auth login --provider openai`, with `--device-code`
  if the browser
  callback fails. It opens a browser, so the operator does it.
- **ClinePass is not an OpenClaw provider.** It runs through the Cline CLI launcher, which refuses
  paid cycles until total
  output and request count can be bounded.
- **Resulting order (operator ruling 2026-11-25, subject to change):** W&B DeepSeek-V4.1-Flash-1017
  at high as the
  default; then ClinePass via the launcher; then Google by API key; then the authenticated Codex
  login; local Ollama
  `qwen3.5:9b-mlx` stays the generic spawned agent when no provider is requested. Plugins (codex,
  parallel, perplexity,
  brave) come back last, one at a time, and Telegram is restored last.

## Cutover state at the time of writing

- **Root cause of the gateway crash loop** (older than any version change): startup migrations
  refused to finish because
  the shared SQLite state held conflicting plugin-install metadata for codex, parallel and
  perplexity. `doctor --fix
  --non-interactive` hung and changed nothing.
- **Operator approval:** `--accept-risk` and a `loopback` bind in place of the old LAN bind, then a
  fresh state with the
  recovery done later in stages.
- **Done:** the gateway launch agent was unloaded and the old state was renamed to `~/.openclaw.pre-clean-20261125`
  (564 MB, nothing deleted). A non-interactive fresh onboarding was started with loopback bind, port
  18789, token auth, and
  no providers, channels, skills, search or hooks.
- **Result of the fresh onboarding:** openclaw 2026.10.6 gateway running as a launch agent,
  connectivity ok, listening on
  the loopback interface only, IPv4 and IPv6 (no LAN). Only warning: the service uses node from a
  version manager.
- **AlphaClaw installed:** the PR 34 build (`@diazmelgarejo/alphaclaw` 0.9.39-9) was packed from the
  worktree (prepack
  builds the UI, 958 KB, 429 files), proved in a scratch folder (zero dependency problems), then
  installed into the
  `~/.alphaclaw` workspace from `~/.alphaclaw/vendor/` with openclaw 2026.10.6, the same as the
  global one. The old
  `@chrysb/alphaclaw` 0.9.16.9 was removed from the workspace and stays recoverable from the
  verified backup. The
  scout hook blocks running files under `node_modules`, so startup is verified through the real
  launch, not a direct
  call. The orama launcher status shows PT 8000, orama 8001 and Portal 8002 DOWN, as expected until
  it is started.
- **Still to do:** restore in baby steps with a health check after each: core config, agents and
  workspace, the W&B
  default, the fallback providers, plugins, and Telegram last. After success: move the obsolete Node
  24.14.1 to the
  Trash and remove its marker.
- **Not pushed:** the PT lessons and this chronicle are committed locally on top of PT PR 521's tip.
