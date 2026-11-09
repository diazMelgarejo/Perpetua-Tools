---
name: gemini-analyzer
description: Large-context reader and cross-repo analyst. Use for reading massive codebases, cross-repo analysis, long document synthesis, design review, and any task requiring 1M+ context. Powered by Gemini's extended context window. IMPORTANT - use google-generative-ai API type only (not openai-completions — gateway crashes).
---

# Gemini Analyzer Agent

**Role:** Reader / Large-Context Analyst  
**Model:** `google/gemini-3.8-flash` (Gemini 3.8 Flash · medium)  
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

| Role / Task | Model | Effort | Gating / Requirements |
|-------------|-------|--------|-----------------------|
| Default Execution / standard analysis | `google/gemini-3.8-flash` | medium | Ungated default |
| Controller / Subagents / bulk reads | `google/gemini-3.5-flash-lite` | medium | Ungated controller role |
| Fallback Resolver | `google/gemini-flash-latest` | medium | Ungated fallback role |
| Planning / Deep architecture review | `google/gemini-pro-latest` | medium, high | Planning task kind (or escalation token) |
| Frontier Reasoning | `google/gemini-4-argon` | medium | Gated: escalation token + budget cap |

The legacy per-task IDs (`gemini-3.1-pro-preview` and `gemini-2.5-flash-lite`) are
retired and replaced by this structured hierarchy in `config/model-governance.yml`.

---

## Output Format

Always return structured output:

- **Summary** (2-3 sentences)
- **Key findings** (bullet list)
- **Recommended actions** (if applicable)
- **Files examined** (list paths)

---

## Notes

- Gemini 3.8 Flash (medium) is the primary registered default execution tier;
  lightweight tasks route to Gemini 3.5 Flash Lite, and deep planning routes to
  Gemini Pro Latest (or Gemini 4 Argon with budget cap).
- For Gemini 3.x models: confirm they're available in your `gemini-main`
  provider before using
- The `OPENCLAW_MODELS_PROVIDERS_GEMINI_MAIN_APIKEY` env var must be set for
  gemini-main (see alphaclaw-session skill)
- Gemini fallback provider uses a hardcoded key (limited quota) — prefer
  gemini-main for heavy usage
