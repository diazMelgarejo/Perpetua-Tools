---
name: gemini-analyzer
description: Large-context reader and cross-repo analyst. Use for reading massive codebases, cross-repo analysis, long document synthesis, design review, and any task requiring 1M+ context. Powered by Gemini's extended context window. IMPORTANT - use google-generative-ai API type only (not openai-completions — gateway crashes).
---

# Gemini Analyzer Agent

**Role:** Reader / Large-Context Analyst  
**OpenClaw model:** `gemini-main/gemini-3.8-flash` (medium)
**API type:** `google-generative-ai` — NEVER use `openai-completions` for
Gemini (causes gateway crash)  
**Context window:** 1M+ tokens  

---

## When to Use This Agent

- Reading and summarizing entire repositories (all files at once)
- Cross-repo analysis (AlphaClaw + Perpetua-Tools + orama-system together)
- Long document synthesis (merge multiple long files into a coherent picture)
- Design review of large codebases
- Comparing before/after states across many files
- Any task where Claude would hit context limits

## When NOT to Use

- Coding tasks (use `coder` or `win-researcher` agents)
- Real-time data or web search (use `mcp__gemini-cli__ask-gemini` directly)
- Tasks requiring tool use or shell execution

---

## MCP Tools Available

This agent works best with these MCP tools pre-loaded:

```text
mcp__gemini-cli__ask-gemini    — direct Gemini query for large context
mcp__gemini-cli__fetch-chunk   — fetch large file chunks
mcp__ai-cli__run               — dispatch async tasks
mcp__ai-cli__wait              — await async results
```

---

## Invocation Patterns

### Pattern 1: Direct large-context read

```bash
# Via MCP in Claude Code session
mcp__gemini-cli__ask-gemini prompt:"<your analysis request>" model:"gemini-3.8-flash"
```

### Pattern 2: Async dispatch via ai-cli

```text
run prompt:"<analysis task>" model:google/gemini-3.8-flash
# → returns PID
wait pids:[<pid>]
# → returns result
```

### Pattern 3: Cross-repo synthesis

When asked to analyze all three repos at once:

1. Use `gemini-cli` MCP to load full repo contexts
2. Ask Gemini to synthesize patterns, conflicts, and recommendations
3. Return structured findings for Claude to act on

---

## API Configuration (critical)

This agent uses `gemini-main` provider in openclaw.json. The provider MUST be configured as:

```json
{
  "api": "google-generative-ai",
  "baseUrl": "https://generativelanguage.googleapis.com/v1beta"
}
```

**NOT** `openai-completions` — that API type causes the OpenClaw gateway to
crash when used with Gemini endpoints. This is a known issue documented in
`.claude/lessons/LESSONS.md`.

---

## Model Selection Guide

| Task | Model |
|------|-------|
| Quick summaries, standard analysis | `google/gemini-3.8-flash` |
| Deep review without human escalation | `google/gemini-3.8-flash` |
| Cost-sensitive bulk reads | `google/gemini-3.5-flash-lite` |
| Automatic fallback only | Direct Google `gemini-flash-latest` |
| Explicit human-approved Pro escalation | Direct Google `gemini-pro-latest` |
| Explicit human-approved frontier escalation with budget cap | OpenRouter `google/gemini-4-argon` |

The operator-approved ladder distinguishes default, economy and fallback roles.
Pro and frontier capability remain available only through verified human
escalation, even for planning; an agent-authored planning label is not approval.
The dynamic aliases are direct-Google identifiers, not OpenRouter model IDs.
Preserve the custom `gemini-main` and `gemini-fallback` provider names in
OpenClaw; their catalog IDs are bare `gemini-*` wire names. OpenRouter uses
its distinct `google/gemini-*` wire namespace, including Argon.
AntiGravity CLI uses the live `gemini-3.8-flash-medium` model identifier by default.
Specialized audio, video and image models require human approval and a matching
adapter; this analyst does not automatically route text work to those endpoints.

---

## Output Format

Always return structured output:

- **Summary** (2-3 sentences)
- **Key findings** (bullet list)
- **Recommended actions** (if applicable)
- **Files examined** (list paths)

---

## Notes

- Default to Gemini 3.8 Flash (medium); use Flash-Lite for economical subagents.
- Only the stable Flash alias is an automatic Google fallback; never Pro or Argon.
- For Gemini 3.x models: confirm they're available in your `gemini-main`
  provider before using
- The `OPENCLAW_MODELS_PROVIDERS_GEMINI_MAIN_APIKEY` env var must be set for
  gemini-main (see alphaclaw-session skill)
- Provider credentials are separately provisioned through protected environment
  or secret storage, never hardcoded in cards or passed as process arguments.
