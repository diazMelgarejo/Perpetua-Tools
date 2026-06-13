# Security Policy — Perpetua-Tools

Companion to the cross-repo posture in
[`../orama-system/docs/SECURITY-POLICY.md`](../orama-system/docs/SECURITY-POLICY.md).
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
1. Rotate the secret immediately.
2. Remove it from active code.
3. Remove the file from Git tracking with `git rm --cached`.
4. Treat Git history cleanup as secondary, after rotation.
