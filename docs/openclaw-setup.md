# openclaw Setup & Troubleshooting

Canonical reference for the openclaw gateway on this machine (Mac M2 Pro, Apple Silicon).

---

## Architecture

```text
LaunchAgent (ai.openclaw.gateway)
    │
    ├── /opt/homebrew/bin/node  → ~/.nvm/versions/node/v24.14.1/bin/node
    ├── dist/index.js  (openclaw global npm install)
    ├── port 18789 (LAN: 0.0.0.0, dashboard: http://<YOUR_LAN_IP>:18789/)
    └── 4 plugins: memory-core, telegram, usage-tracker, whatsapp
```

The AlphaClaw → Perpetua-Tools → orama-system layering means:

- openclaw is the gateway daemon (AlphaClaw layer 1)
- Perpetua-Tools portal and orama API are the consumers (layers 2 + 3)

---

## Channel Status

| Channel | Status | Notes |
| --------- | -------- | ------- |
| Telegram | ✅ Connected | Bot: @a1phaCLawbot (token in `channels.telegram.botToken`) |
| WhatsApp | ⏳ Needs QR pairing | Plugin enabled, Baileys installed — run login once |

### Telegram notes

- Occasional `getMe` fetch timeouts (2500–9994ms) are network jitter, not config errors
- Polling stalls (getUpdates stuck for 400+s) trigger auto-restart; messages are not lost, only delayed

### WhatsApp setup (one-time)

The WhatsApp plugin uses **Baileys** (`@whiskeysockets/baileys` — WhatsApp Web protocol via QR code).

To link your phone:

```bash
# In your terminal (interactive — needs QR code scan)
openclaw channels login --channel whatsapp
```

Scan the displayed QR code with WhatsApp → Linked Devices → Link a Device.

The bot will connect as your personal WhatsApp account. Your number is set as the
command owner.

**Why "whatsapp notification failed" before**: the plugin was in the `plugins.allow` list but the
Baileys runtime hadn't loaded yet because the plugin wasn't in the allowlist. Fixed 2026-05-02:
added `whatsapp` to `plugins.allow`, added `channels.whatsapp` config, Baileys auto-installs on
gateway start.

**Format**: `whatsapp:<YOUR_NUMBER_E164>` (with `+`, E.164 format). The `+` IS required.

---

## Command Owner

Controls who can run privileged commands (`/config`, `/diagnostics`, exec approvals, etc.).

```bash
# Current value
openclaw config get commands.ownerAllowFrom
# → ["whatsapp:<YOUR_NUMBER_E164>"]

# To change (example — telegram user ID)
openclaw config set commands.ownerAllowFrom '["telegram:123456789"]'
```

---

## Plugin Config: usage-tracker

The `usage-tracker` plugin is the AlphaClaw dev build at:
`~/Documents/Terminal xCode/claude/OpenClaw/AlphaClaw/lib/plugin/usage-tracker`

The `llm_output` hook requires explicit access permission. Set via:

```bash
openclaw config set "plugins.entries.usage-tracker.hooks.allowConversationAccess" true
```

This is already applied (as of 2026-05-02).

The `activation.onStartup` key from doctor warnings does **not** exist in the config schema — ignore
it.

---

## Gateway Startup Issues After Update

After `openclaw update`, the following sequence is normal and not a bug:

1. `"Completion cache update failed: ETIMEDOUT"` — completion regeneration subprocess timed out
   during update. Fix: run `openclaw completion --write-state --yes` manually.
2. `"Gateway version mismatch: expected X, running gateway reported unavailable"` — transient during
   restart. Wait 5–10 seconds; gateway starts normally.
3. `"Gateway port 18789 status: free"` — same transient; gateway is mid-restart.

### Regenerate completions manually

```bash
openclaw completion --write-state --yes
```

Files land in `~/.openclaw/completions/` and are sourced by `~/.zshrc`.

---

## Node Path Stability

The LaunchAgent uses `/opt/homebrew/bin/node` after `openclaw doctor --fix`. This is a symlink to
the current NVM v24.14.1 binary:

```text
/opt/homebrew/bin/node → ~/.nvm/versions/node/v24.14.1/bin/node
```

**Risk**: if the user runs `nvm use 22` and then uninstalls v24, the symlink breaks.
**Mitigation**: don't uninstall v24 without updating the symlink. A future improvement would be
installing node via `brew install node` to get a truly stable path.

---

## Key Config Paths

| Setting | Location |
| --------- | --------- |
| Main config | `~/.openclaw/openclaw.json` |
| Gateway plist | `~/Library/LaunchAgents/ai.openclaw.gateway.plist` |
| Service env | `~/.openclaw/service-env/ai.openclaw.gateway.env` |
| Shell completions | `~/.openclaw/completions/openclaw.zsh` |
| Gateway logs | `~/.openclaw/logs/gateway.log` (and `.err.log`) |
| Runtime log | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` |

---

## Useful Commands

```bash
# Status
openclaw gateway status --deep
openclaw channels status --deep
openclaw doctor

# Repair
openclaw doctor --fix
openclaw completion --write-state --yes
openclaw gateway restart

# Debug
openclaw channels logs
tail -f ~/.openclaw/logs/gateway.err.log
```

## Reproducible install: the 2026-11-25 baseline

One script reproduces the runtime, and `--check` (the default) is read-only. A dated operator
baseline, subject to
change when upstream releases move.

```bash
bash scripts/install-openclaw-runtime.sh                 # --check: exits 1 on drift
bash scripts/install-openclaw-runtime.sh --plan  [opts]  # print the exact commands, run nothing
bash scripts/install-openclaw-runtime.sh --apply [opts]  # run them
```

| Step | What it does | Why |
| --- | --- | --- |
| 1 node | nvm node 24.22.3 as the default; keep one 24.x and mark the old one obsolete | AlphaClaw 0.9.38+ and openclaw 2026.10.6 need node >=24.22.1 <25 |
| 2 openclaw | global `openclaw` at the version AlphaClaw pins | global and AlphaClaw stay the same version |
| 3 alphaclaw | the fork build (PR 34 tarball) into `~/.alphaclaw`, old `@chrysb/alphaclaw` removed | the build carries the custom macOS support; the repo uses pnpm, so build it with `pnpm install --frozen-lockfile` then `npm pack` |
| 4 link | `perpetua_tools.openclaw_runtime`: a stable link `~/.local/share/openclaw-node`, and a launch agent that never names a node version | a node removal or upgrade can no longer leave the service crash-looping |
| 5 gateway | opt-in `--fresh-gateway --accept-risk`: rename `~/.openclaw` aside, onboard fresh on loopback with token auth, no providers, channels, skills, search or hooks | a state fault (conflicting plugin metadata) is cured by a clean start, with the old state kept |

The default AlphaClaw bootstrap runs a read-only Step 8 that warns when the service names a node
version; fix it with
`python -m perpetua_tools.openclaw_runtime --apply`. After a Node change, run `openclaw gateway status`.

### Gotchas that cost time on 2026-11-25

- **npm 11 skips install scripts** during `nvm install --reinstall-packages-from`; run every
  migrated global CLI and
  rebuild natives that fail (omniroute stays disabled until rebuilt).
- **launchd `bootout` is asynchronous:** wait for the port to close and retry `bootstrap`; the
  module does both.
- **A service that exits at once and has unhelpful logs:** run the plist's exact command in the
  foreground under a
  timeout. The first non-banner lines name the cause (here, conflicting plugin metadata in the
  shared SQLite state).
- **`openclaw doctor --fix --non-interactive` can hang** on a plugin-index conflict; back up, then
  reinstall plugins one
  at a time or start clean.
- **The scout hook blocks running or listing files under `node_modules`.** Verify a package by its
  metadata and a
  real launch, not by calling the file.

### Staged restore, seats and backup recovery (2026-11-26)

The fresh-install procedure, the staged restore order, the dated provider and seat rulings,
credential handling and the backup and recovery process are one card in orama-system:
`bin/orama-system/references/openclaw-staged-restore-and-recovery.md`. The dated record is
`.agent/memory/semantic/SESSION_CHRONICLE_2026-11-26_OPENCLAW_SEATS_ENV_AND_STAGED_RESTORE.md`.

### OpenClaw defaults: one source of truth (2026-11-27)

The model chain, the two research seats, the seat tool policy, the env rules and the baseline live in
`config/openclaw-defaults.json`: names only, never a key value. `perpetua_tools.openclaw_defaults`
loads and validates it (no Mac LM Studio in any chain, W&B in every chain, human-gated models in no
default, no secret-looking value), renders the config patches the staged restore applies, and reports
drift read-only.

Human-gated, for explicit operator choice only: OpenAI Astra and Sol, `gemini-main/gemini-pro-latest`
and `openrouter/google/gemini-4-argon`. Orama's model rules additionally require an escalation token
for Gemini Pro, and an escalation token and a budget cap for Argon.

Besides the built-in `google` provider, the `gemini-main` and `gemini-fallback` providers each read
their own key variable: `OPENCLAW_MODELS_PROVIDERS_GEMINI_MAIN_APIKEY` and
`OPENCLAW_MODELS_PROVIDERS_GEMINI_FALLBACK_APIKEY`.

```bash
python -m perpetua_tools.openclaw_defaults --validate
python -m perpetua_tools.openclaw_defaults --render-patch --shape entries  # emits only
python -m perpetua_tools.openclaw_defaults --check ~/.openclaw/openclaw.json
python -m perpetua_tools.openclaw_defaults --vendor-copy                   # prints only
```

Consumers in other repositories read the live file first, then a **stamped vendored copy**. The
stamp holds the
source fingerprint, the source date and the copy date. A copy that differs from the live file, is
older than
30 days while the live file is unreachable, or was edited by hand is reported loudly at start-up. A
sync never
runs by itself: it shows the diff and waits for a human to confirm.

### Restore in baby steps (after step 5)

Check the gateway after each stage: 1 core config; 2 agents and workspace; 3 the W&B default; 4
fallback providers;
5 plugins (codex, parallel, perplexity, brave), one at a time; 6 Telegram last, only after the old
instance is
confirmed stopped. Operator provider order (a dated ruling): W&B DeepSeek-V4.1-Flash-1017 at high;
then ClinePass via
the Cline launcher; then Google by AI Studio API key (OpenClaw offers no new Google web login; model
`google/gemini-3.8-flash`, thinking level medium); then the OpenAI Codex login (`openclaw models
auth login --provider
openai`, add `--device-code` if the browser callback fails); local Ollama stays the generic default.
The operator enters
credentials and completes logins; the agent configures routing only.
