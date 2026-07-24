# Security Policy - Perpetua-Tools

Companion to the cross-repo posture in
[`orama-system/SECURITY.md`](https://github.com/diazMelgarejo/orama-system/blob/main/SECURITY.md).
This file states the credential and artifact hygiene contract enforced in this repo.

Last updated: 2026-06-28

Runtime security alignment for MAESTRO/OWASP v2 is recorded in
[`docs/adr/ADR-003-maestro-owasp-v2-security-foundation.md`](docs/adr/ADR-003-maestro-owasp-v2-security-foundation.md).

## Reporting

Do not open public issues for vulnerabilities. Report privately to the maintainer
(`cyre <Lawrence@cyre.me>`). Rotate any exposed secret before anything else.

## Scope

This policy covers Perpetua-Tools orchestration code, FastAPI control-plane
routes, worker processes, RAG/memory persistence, package lockfiles, AlphaClaw
MCP packages, local-agent packages, and runtime configuration templates.

Security controls must remain synchronized with the companion orama policy.
If a defense-in-depth rule applies to both repos, update both policies in the
same change or explain why this repo's surface differs.

Local repo-owned threat IDs use the `PT-01`, `PT-02`, ... `PT-09` format.
Do not insert an extra `T` after the repo prefix or use similar local IDs that
visually collide with OWASP Agentic/MCP `T1`-style identifiers.

## Defense-in-Depth Operating Baseline

Security fixes must land as layered controls, not as single-point patches. For
each sensitive surface, require a preventive control, a runtime guard, a
verification gate, and an operator recovery path.

| Surface | Prevent | Runtime guard | Verify |
|---------|---------|---------------|--------|
| Credentials | `.env*` ignored except `.env.example`; no literals in tracked config | OS keychain or process env only; rotate any exposed key | `repo_hygiene.py`, provider secret scanning, billing/usage alerts |
| Control plane | Loopback default; LAN bind requires explicit opt-in | Strong bearer auth on mutating/read-sensitive routes | unauthenticated route tests + no bearer in HTML/logs |
| MCP and workers | readonly default profiles; dangerous workers opt-in only | path boundary roots + log redaction + no tracked bearer headers | profile tests verify final merged config, not only dry-run output |
| Model discovery | trusted host pinning before persistence | strip `Authorization` from LM Studio/Ollama/public probes | tests assert control-plane tokens never reach model endpoints |
| PT config overlay | `HEAD` keeps empty `lan_ip` / loopback host defaults; working-tree discovery cache is local-only | `check_local_runtime_overlay.py` (pre-commit staged + CI tree) | never `git checkout` overlay paths; stash before pull — see [`config/LOCAL-RUNTIME-OVERLAY.md`](config/LOCAL-RUNTIME-OVERLAY.md) and orama [`local-runtime-overlay` skill card](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/using-git-worktrees/references/local-runtime-overlay-reference-card.md) |
| Public health probes | loopback/RFC1918 only on `/health` query params | `validate_model_endpoint_url()` before outbound probes | `tests/test_fastapi_health.py` rejects link-local/metadata targets |
| Runtime bootstrap | redact top-level secrets before HTTP response | POST `/runtime/bootstrap` omits `credentials`/`paths`/`gateway` blobs; `runtime` field uses `redact_runtime_payload()` | `tests/test_runtime_bootstrap_redaction.py` + `redact_runtime_payload()` unit tests |
| Memory and artifacts | redact before persistence; runtime dirs ignored | store only sanitized prompts/results; private tickets for raw artifacts | hygiene blocks databases, traces, screenshots, logs, and `/tasks/` |
| Dependencies | lockfiles are security surfaces; override vulnerable transitives at package-manager root | builds/tests must pass after lock refresh | Dependabot alerts close on the exact target lockfile |

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

As of the official
[Gemini API key guidance](https://ai.google.dev/gemini-api/docs/api-key)
checked on 2026-06-17, unrestricted standard keys are rejected starting
2026-06-19 and all standard-key usage should migrate to authorization keys
before September 2026. Treat these as operational deadlines for every active
Gemini account.

### Control Plane and MCP Tokens
Control-plane tokens, OmniRoute tokens, MCP bearer headers, and local gateway
tokens are runtime secrets. Keep them in git-ignored local config, OS/editor
secret storage, or process environment only. Do not copy bearer headers into
tracked MCP config, examples, screenshots, issue bodies, logs, or rendered UI.
Model-status and discovery probes must not forward control-plane bearer tokens to
LM Studio, Ollama, discovered LAN hosts, or public model endpoints.

### MCP and Worker Least Privilege
AlphaClaw MCP defaults to the readonly profile. Elevated or mutating tools require
explicit operator opt-in through `ALPHACLAW_MCP_PROFILE=elevated`,
`ALPHACLAW_MCP_ENABLE_PROCESS_TOOLS=1`, or
`ALPHACLAW_MCP_ENABLE_MUTATING_TOOLS=1`.

Subprocess worker backends that can run local CLI agents remain disabled unless
`PT_ALLOW_DANGEROUS_CLI_WORKERS=1` is set. Do not enable dangerous workers from
tracked examples, default config, screenshots, or docs snippets.

### Model Discovery and LAN Egress
Production code defaults to loopback. Real LAN IPs live only in git-ignored
local env files or runtime discovery state. Discovery must not persist a newly
observed LM Studio, Ollama, or public model endpoint until the operator has
approved or pinned the host.

Control-plane `Authorization` headers must be stripped from all model-status,
model-list, and health probes to LM Studio, Ollama, discovered LAN endpoints, or
public model APIs.

### Memory and Prompt Artifacts
Prompts, worker results, memory rows, logs, traces, screenshots, recordings, and
browser captures may contain secrets or private data. Redact before persistence
when possible, keep raw artifacts in git-ignored runtime paths only, and attach
raw evidence only to private tickets after review.

### Dependency Integrity
Lockfiles are security surfaces. When Dependabot names a lockfile, fix the
dependency resolution in that exact lockfile and package-manager root. For pnpm
11, security overrides belong in `pnpm-workspace.yaml`, not ignored
`package.json#pnpm` settings.

Run the package's build/test target after any lockfile refresh. For
`packages/alphaclaw-mcp`, `npm test` is the minimum gate.

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
- Package-specific tests must run for the surface touched:
  `npm test` for `packages/alphaclaw-mcp`, local-agent package tests for
  `packages/local-agents`, and focused Python tests for orchestrator changes.
- Full `python3 -m pytest` remains the broad gate when the local dev
  dependencies are installed.

## Multi-PR Landing Order & Append-Only Log Conflicts

When 2+ open PRs touch `.agent/memory/semantic/lessons.jsonl` (the shared
semantic-memory source of truth), its rendered companion `LESSONS.md`, or
another append-only shared log, GitHub's per-PR `mergeable` check only compares
each PR against current `main`. It does not warn that sibling PRs conflict
with each other.

Record and simulate the intended landing order before merging with `git
merge-tree --write-tree --merge-base=<base> <branch1> <branch2>`. The command
leaves the source worktree, index, and branch refs unchanged, but writes a
prospective merge tree object; inspect that result rather than assuming the
open PRs are independently mergeable.

Show both sides of every real conflict and classify it before resolving. Use
**union** only after confirming both sides are complementary, verified
append-only additions with neither duplicate IDs nor contradictory claims; for
JSONL, deduplicate by stable ID while retaining the first recorded entry. Do
not hand-merge rendered `LESSONS.md`: regenerate it through `graduate.py`.
Same-ID conflicts, contradictory records, and every non-append conflict require
an explicit human-directed resolution. Preserve each valid intent using the
appropriate additive, union, superset, synthesize, architecturally-correct, or
API-correct mode; never choose a whole file by branch origin alone.

The working PT policy is the
[Multi-agent merge conflict protocol](.agent/AGENTS.md#multi-agent-merge-conflict-protocol),
which loads the canonical [integrative merge doctrine](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/integrative-merge.md).
For the original landing-order case study and why already-open PRs are merged
rather than blindly rebased, see `orama-system/SECURITY.md` § "Case study:
append-only shared-file conflicts across independent PRs (2026-07-12)".

## Lessons and Action Must Land on the Same Branch (mandatory)

**Never commit `.agent/memory/` lessons about code, a fix, or a decision to a
different branch than the one the actual change lives on — always, no
exceptions.** Lessons describing work that only exists on an unmerged PR
branch must be committed to that same branch, not to `main` or any other
branch, even when the lesson content itself is otherwise accurate and
well-written.

**Why this is a hard rule, not a style preference:** `main`'s tracked memory
is read as a description of what `main` actually contains. A lesson on `main`
that references a file, function, or decision that only exists on an unmerged
branch is a false claim about `main`'s own contents — a reader (human or
agent) following the lesson's own file references finds nothing. This is the
same class of problem the "Multi-PR Landing Order" section above exists to
prevent for shared append-only files in general, applied specifically to the
case where the *branch itself*, not just the merge order, is wrong.

**Concrete incident (2026-07-23):** 5 lessons describing a new
`orchestrator/alphaclaw_tls_proxy.py` module and its wiring into
`alphaclaw_manager.py` were committed and pushed directly to `main`, while
the actual code lived only on an unmerged feature branch
(`security/alphaclaw-tls-proxy-scaffold`). Caught by the operator, not by any
automated check. Corrected by resetting `main` back to its exact pre-mistake
tip (`git push --force-with-lease`, since nothing had landed on top of the
mistaken commits — verified this was true before force-pushing, and force-
pushing `main` still required the operator's explicit authorization per the
"Ask before rewriting" rule this repo already follows for any shared branch
rewrite) and re-committing the same lesson content onto the actual feature
branch, so the lessons and the code they describe travel together and land
in `main` in the same commit when that PR merges.

**The correct sequence, always:**
1. Determine which branch the action being reflected on actually lives on —
   the current working branch for in-progress work, or the branch a PR
   merged from if reflecting after the fact.
2. Stage and graduate the lesson via `learn.py`/`graduate.py` on **that**
   branch, never on `main` or an unrelated branch, unless the action itself
   was *already* merged to `main` at the time the lesson is written.
3. Verify before pushing: does the branch you are about to push memory to
   actually contain the file(s)/decision the lesson references? If not, stop
   — commit to the correct branch instead.
