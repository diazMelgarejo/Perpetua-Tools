# Exa.ai Integration

**Canonical API reference:** https://docs.exa.ai/reference/search-api-guide-for-coding-agents

Exa gives orama-system and Perpetua agents real-time web research: library docs, GitHub patterns, ecosystem monitoring. Key integration assets live in `scripts/exa/`.

---

## Setup

```bash
# One-shot bootstrap (installs exa-py, stores key, wires MCP)
bash scripts/exa/setup-exa.sh --key YOUR_EXA_API_KEY

# Or manually store the key in openclaw config:
openclaw config set env.EXA_API_KEY YOUR_KEY

# Or via .env.local (gitignored):
cp .env.local.example .env.local
# edit .env.local — add EXA_API_KEY=...
```

Key resolution order (automatic, no code changes needed):
1. `EXA_API_KEY` env var
2. `~/.openclaw/openclaw.json` → `.env.EXA_API_KEY`
3. macOS Keychain (`openclaw.exa.api_key`)

---

## Python Usage

```python
from scripts.exa.exa_search import search, find_similar, get_contents, answer

# Standard coding-agent search (highlights = token-predictable excerpts)
results = search("exa-py structured output schema", num_results=5)

# Deep synthesis with structured output
results = search(
    "OpenClaw MCP agent routing patterns",
    search_type="deep",
    output_schema={
        "type": "object",
        "required": ["summary", "patterns"],
        "properties": {
            "summary": {"type": "string"},
            "patterns": {"type": "array", "items": {"type": "string"}},
        },
    },
    system_prompt="Prefer GitHub repos and official docs. Collapse duplicate results.",
)
print(results[0]["structured"])   # grounded JSON
print(results[0]["grounding"])    # field-level citations

# Find similar pages to a known URL
similar = find_similar("https://docs.exa.ai", num_results=5)

# Fetch content for known URLs (RSS feeds, stale docs)
fresh = get_contents(["https://example.com/api-ref"], max_age_hours=0)

# Question-first answer with citations
resp = answer("What is the correct Exa highlights API shape?")
print(resp["answer"])
```

---

## CLI

```bash
python3 scripts/exa/exa_search.py "orama system MCP integration"
python3 scripts/exa/exa_search.py --type deep --content text "exa-py 2.16 API changes"
python3 scripts/exa/exa_search.py --find-similar https://docs.exa.ai
python3 scripts/exa/exa_search.py --get-contents https://exa.ai/docs --fresh 0
python3 scripts/exa/exa_search.py --answer "what is Exa autoprompt"
python3 scripts/exa/exa_search.py --json "Claude MCP tool calling" | jq '.[0].url'
```

---

## Search Type Selection

| Type | Use when | Latency |
|------|----------|---------|
| `auto` | Default — most coding-agent queries | ~1 s |
| `fast` | Latency matters, still need relevance | ~450 ms |
| `instant` | Chat, autocomplete, quick lookups | ~250 ms |
| `deep-lite` | Synthesis without full-deep cost | ~4 s |
| `deep` | Research, enrichment, multi-source | 4–15 s |
| `deep-reasoning` | Complex multi-step synthesis | 12–40 s |

**Rule of thumb:** start with `auto`. Add `deep` only when you need synthesis across many sources or `output_schema` quality matters.

---

## Content Modes

| Mode | Config | Use when |
|------|--------|----------|
| `highlights` | default | Token-predictable excerpts — right for most agent loops |
| `text` | `--content text` | Full page content for RAG or deep analysis |
| `summary` | `--content summary` | LLM-written summary per result |

Never combine modes at the start of a project — pick one.

---

## Structured Output Pattern

Add `output_schema` to get grounded JSON back instead of free text. Works on every search type; `deep`/`deep-reasoning` give higher synthesis quality.

```python
results = search(
    "Python async patterns for MCP tool calls",
    search_type="deep-lite",
    output_schema={
        "type": "object",
        "required": ["summary"],
        "properties": {
            "summary": {"type": "string", "description": "Key findings"},
        },
    },
    system_prompt="Prefer official Python docs and well-starred GitHub repos.",
)
```

Schema constraints: max nesting depth 2, max 10 properties. Don't add citation fields — grounding is returned automatically.

---

## Freshness Control (`max_age_hours`)

| Value | Behavior |
|-------|----------|
| omit | Recommended — cache when available, livecrawl as fallback |
| `0` | Always livecrawl (real-time data) |
| `24` | Livecrawl if cache older than 24 h |
| `-1` | Cache only (fastest, historical content) |

---

## MCP Integration (Claude Code / Claude Desktop)

After `setup-exa.sh`, the `exa` MCP server is registered in:
- `~/.claude/claude_desktop_config.json` (restart Claude Desktop)
- `orama-system/.mcp.json`
- `Perpetua-Tools/.mcp.json`

Claude Code CLI tools available as `mcp__claude_ai_Exa__web_search_exa` and `mcp__claude_ai_Exa__web_fetch_exa`.

---

## Common Mistakes to Avoid

| Wrong | Right |
|-------|-------|
| `use_autoprompt=True` | Remove — deprecated |
| `livecrawl="always"` | `max_age_hours=0` |
| `text=True` at search top level | `contents={"highlights": True}` |
| `tokensNum=N` | `contents.text.maxCharacters=N` |
| `includeUrls` / `excludeUrls` | `include_domains` / `exclude_domains` |
| Citation fields in `output_schema` | Omit — grounding is automatic |
| `excludeDomains` + `category="company"` | These categories reject domain filters |
