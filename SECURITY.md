# Security Policy - Perpetua-Tools

Companion to the cross-repo posture in
[`orama-system/SECURITY.md`](https://github.com/diazMelgarejo/orama-system/blob/main/SECURITY.md).
This file states the credential and artifact hygiene contract enforced in this repo.

## Reporting

Do not open public issues for vulnerabilities. Report privately to the maintainer
(`cyre <Lawrence@cyre.me>`). Rotate any exposed secret before anything else.

## Credential and Artifact Hygiene

### No Secrets in Source
API keys, OAuth tokens, private keys, service-account files, and credentials must
never be committed. Commit `.env.example`; never commit `.env`.

Enforced: `scripts/review/repo_hygiene.py` scans the staged/tracked tree for secret
patterns (OpenAI `sk-`, Anthropic `sk-ant-`, GitHub `ghp_`/`github_pat_`, Google
`AIza`, AWS `AKIA`, Telegram bot tokens, and `BEGIN … PRIVATE KEY` blocks) and runs
in pre-commit and CI. A match fails the gate.

### Secure Storage
Runtime secrets live in the OS keychain, not in source, settings, or logs. Use the
`openclaw-add-secret` skill (macOS Keychain) to store and propagate endpoint keys;
the gateway Bearer token is never copied into tracked files. Do not store secrets in:
- source files
- config/settings JSON or `package.json`
- logs, captures, or UI artifacts

### Local Environments
Local development reads secrets from `.env`, which is git-ignored. `.env.example`
documents the required keys with empty values and is the only env file committed.

Gemini/Google keys must be read from environment variables such as
`GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `GOOGLE_GENERATIVE_AI_API_KEY`. If two
Gemini accounts are required, use a deliberate secondary variable such as
`GEMINI_API_KEY_2`; do not add typo aliases. Prefer Gemini auth keys or
explicitly restricted keys, restrict them to the Gemini API where applicable,
apply request-origin restrictions when possible, and enable billing/usage alerts.
Never expose Gemini keys in production browser or mobile client code; route
production calls through a backend service.

### Control Plane and MCP Tokens
Control-plane tokens, OmniRoute tokens, MCP bearer headers, and local gateway
tokens are runtime secrets. Keep them in git-ignored local config, OS/editor
secret storage, or process environment only. Do not copy bearer headers into
tracked MCP config, examples, screenshots, issue bodies, logs, or rendered UI.
Model-status and discovery probes must not forward control-plane bearer tokens to
LM Studio, Ollama, discovered LAN hosts, or public model endpoints.

### Artifact Protection
Generated logs, databases, recordings, browser traces, screenshots, hook logs
(`.claude/hooks/.logs/`), and UI-capture artifacts are git-ignored. If an artifact is
needed for debugging, redact it first and attach it to the private ticket only.

### No Workstation Paths
Tracked files (docs included) must use repo-relative references
(`"$(git rev-parse --show-toplevel)"`, `~`, `$REPO_ROOT`) — never a literal
`/Users/<name>/…` path. `repo_hygiene.py` blocks absolute workstation paths so they
cannot doxx the owner in this public repo.

## If a Secret Is Committed
1. Generate and deploy a replacement credential first.
2. Verify the replacement works.
3. Disable or revoke the exposed credential.
4. Audit provider usage, billing, and logs for unauthorized access.
5. Remove the secret from active code.
6. Remove any private tracked file from Git tracking with `git rm --cached`.
7. Treat Git history cleanup as secondary, after rotation.

## Enforcement

- `.gitignore` blocks local secrets, runtime state, `/tasks/`, logs, databases,
  traces, captures, and generated artifacts.
- `scripts/review/repo_hygiene.py` scans tracked files for secret-shaped
  literals, private artifacts, workstation paths, hidden Unicode controls, and
  generated runtime files.
- Local hooks and CI must run the same hygiene gate; provider-side secret
  scanning is a backstop, not the primary control.
