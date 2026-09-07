# ECC for Codex CLI

This supplements the root `AGENTS.md` with Codex-specific guidance.

For repository navigation, surface ownership, and review expectations, follow
the root `AGENTS.md` and the repository's maintained documentation. Treat the
vendored ECC checkout as upstream source material, never as unreviewed runtime
authority.

## Model Recommendations

| Task Type | Recommended Model |
|-----------|------------------|
| Routine coding, tests, formatting | Current fast or standard model selected for the task |
| Complex features, architecture | Current high-reasoning model selected for the task |
| Debugging, refactoring | Current standard or high-reasoning model selected for the task |
| Security review | Current high-reasoning model with independent review |

## Skills Discovery

Skills are auto-loaded from `.agents/skills/`. Each skill contains:

- `SKILL.md` — Detailed instructions and workflow
- `agents/openai.yaml` — Codex interface metadata

Available skills:

- tdd-workflow — Test-driven development with 80%+ coverage
- security-review — Comprehensive security checklist
- coding-standards — Universal coding standards
- frontend-patterns — React/Next.js patterns
- frontend-slides — Viewport-safe HTML presentations and PPTX-to-web conversion
- article-writing — Long-form writing from notes and voice references
- content-engine — Platform-native social content and repurposing
- market-research — Source-attributed market and competitor research
- investor-materials — Decks, memos, models, and one-pagers
- investor-outreach — Personalized investor outreach and follow-ups
- backend-patterns — API design, database, caching
- e2e-testing — Playwright E2E tests
- eval-harness — Eval-driven development
- strategic-compact — Context management
- api-design — REST API design patterns
- verification-loop — Build, test, lint, typecheck, security
- deep-research — Multi-source research with firecrawl and exa MCPs
- exa-search — Neural search via Exa MCP for web, code, and companies
- claude-api — Anthropic Claude API patterns and SDKs
- x-api — X/Twitter API integration for posting, threads, and analytics
- crosspost — Multi-platform content distribution
- fal-ai-media — AI image/video/audio generation via fal.ai
- dmux-workflows — Multi-agent orchestration with dmux

## MCP Servers

Treat the project-local `.codex/config.toml` as the default Codex baseline for ECC. The current
ECC baseline enables GitHub, Context7, Exa, Memory, Playwright, and Sequential Thinking; add
heavier extras in `~/.codex/config.toml` only when a task actually needs them.

ECC's canonical Codex section name is `[mcp_servers.context7]`. The launcher package remains
`@upstash/context7-mcp`; only the TOML section name is normalized for consistency with
`codex mcp list` and the reference config.

### Curated project configuration

`.codex/config.toml` is a reviewed project baseline, not a live vendor-sync
destination. Upstream ECC changes are proposals: inspect them, preserve
project-specific pins and local overlays, then apply only the compatible parts
in a reviewable commit. In particular, do not replace an explicitly reviewed
MCP package version with a floating package name as incidental sync output.

Keep user-level configuration and credentials outside the repository. The
project file may document recommended servers, but it must not overwrite
operator-specific server settings or secrets.

## External Action Boundaries

Treat networked tools as read-only by default. Search, inspect, and draft freely within the
user's requested scope, but require explicit user approval before posting, publishing, pushing,
merging, opening paid jobs, dispatching remote agents, changing third-party resources, or
modifying credentials.

When approval is ambiguous, produce a local plan or draft artifact instead of taking the external
action. Preserve user config and private state unless the user specifically asks for a scoped
change.

## Multi-Agent Support

Codex now supports multi-agent workflows behind the experimental `features.multi_agent` flag.

- Enable it in `.codex/config.toml` with `[features] multi_agent = true`
- Define project-local roles under `[agents.<name>]`
- Point each role at a TOML layer under `.codex/agents/`
- Use `/agent` inside Codex CLI to inspect and steer child agents

Sample role configs in this repo:

- `.codex/agents/explorer.toml` — read-only evidence gathering
- `.codex/agents/reviewer.toml` — correctness/security review
- `.codex/agents/docs-researcher.toml` — API and release-note verification

## Key Differences from Claude Code

| Feature | Claude Code | Codex CLI |
|---------|------------|-----------|
| Hooks | 8+ event types | Version-dependent; verify the installed CLI |
| Context file | CLAUDE.md + AGENTS.md | AGENTS.md only |
| Skills | Skills loaded via plugin | Project `.agents/skills/` plus installed plugins |
| Commands | `/slash` commands | Instruction-based |
| Agents | Subagent Task tool | Multi-agent via `/agent` and `[agents.<name>]` roles |
| Security | Hook-based enforcement | Instructions, sandbox, and explicitly trusted hooks |
| MCP | Full support | Supported via `config.toml` and `codex mcp add` |

## Security Boundaries

Codex hook availability varies by installed version. Treat only explicitly
configured and trusted hooks as defense-in-depth; instructions and the sandbox
remain mandatory controls:

1. Always validate inputs at system boundaries
2. Never hardcode secrets — use environment variables
3. Run `npm audit` / `pip audit` before committing
4. Review `git diff` before every push
5. Use `sandbox_mode = "workspace-write"` in config
