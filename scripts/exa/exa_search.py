#!/usr/bin/env python3
"""
Exa.ai search wrapper for orama-system / Perpetua agents.

Canonical reference: https://docs.exa.ai/reference/search-api-guide-for-coding-agents

Key design choices (per oramasys-method):
- Defaults to type="auto" + contents={"highlights": True} — token-predictable, right for
  most coding-agent workflows without domain restrictions.
- outputSchema / system_prompt are first-class: every search() call can return structured
  grounded JSON when the caller supplies a schema.
- Deprecated params removed: use_autoprompt, livecrawl="always", numSentences,
  highlightsPerUrl, tokensNum — none of these reach the wire.
- max_age_hours maps to the API's maxAgeHours freshness knob.

Key resolution (priority):
  1. EXA_API_KEY env var
  2. ~/.openclaw/openclaw.json  (.env.EXA_API_KEY)
  3. macOS Keychain (openclaw.exa.api_key)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------

def _resolve_api_key() -> str:
    if key := os.environ.get("EXA_API_KEY", ""):
        return key

    openclaw_cfg = Path.home() / ".openclaw" / "openclaw.json"
    if openclaw_cfg.exists():
        try:
            data = json.loads(openclaw_cfg.read_text())
            if key := (data.get("env") or {}).get("EXA_API_KEY", ""):
                return key
        except Exception:
            pass

    try:
        import subprocess
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "openclaw.exa.api_key", "-w"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    raise RuntimeError(
        "EXA_API_KEY not found.\n"
        "Set it with:  openclaw config set env.EXA_API_KEY <key>\n"
        "Or run:       bash scripts/exa/setup-exa.sh --key <key>"
    )


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def exa_client():
    try:
        from exa_py import Exa  # type: ignore[import]
    except ImportError:
        sys.exit("exa-py not installed. Run: pip3 install exa-py")
    return Exa(_resolve_api_key())


# ---------------------------------------------------------------------------
# Search types reference (from docs.exa.ai)
#
#   auto          balanced relevance + speed, smart neural/keyword selection  ~1 s
#   fast          latency-sensitive, good relevance                           ~450 ms
#   instant       chat / voice / autocomplete                                 ~250 ms
#   deep-lite     cheaper synthesis when full deep is overkill                ~4 s
#   deep          research, enrichment, thorough                              4-15 s
#   deep-reasoning complex multi-step synthesis                               12-40 s
# ---------------------------------------------------------------------------

SEARCH_TYPES = ("auto", "fast", "instant", "deep-lite", "deep", "deep-reasoning")


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------

def search(
    query: str,
    *,
    search_type: str = "auto",
    num_results: int = 5,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    content_mode: str = "highlights",      # "highlights" | "text" | "summary"
    max_characters: int | None = None,     # only for content_mode="text"
    max_age_hours: int | None = None,      # freshness: 0=always livecrawl, -1=cache-only
    output_schema: dict | None = None,     # structured grounded output
    system_prompt: str | None = None,      # steering for synthesis + source prefs
    additional_queries: list[str] | None = None,  # deep/deep-lite only
) -> list[dict[str, Any]]:
    """
    Neural/keyword/deep search returning a list of result dicts.

    When output_schema is provided, results[*]["structured"] holds the
    field-level grounded JSON and results[*]["grounding"] holds citations.
    """
    client = exa_client()

    contents: dict[str, Any] = {}
    if content_mode == "highlights":
        contents["highlights"] = True
    elif content_mode == "text":
        cfg: dict[str, Any] = {"verbosity": "compact"}
        if max_characters:
            cfg["maxCharacters"] = max_characters
        contents["text"] = cfg
    elif content_mode == "summary":
        contents["summary"] = True

    if max_age_hours is not None:
        contents["maxAgeHours"] = max_age_hours

    kwargs: dict[str, Any] = {
        "num_results": num_results,
        "type": search_type,
        "contents": contents,
    }
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains
    if output_schema:
        kwargs["output_schema"] = output_schema
    if system_prompt:
        kwargs["system_prompt"] = system_prompt
    if additional_queries:
        kwargs["additional_queries"] = additional_queries

    response = client.search(query, **kwargs)
    results = [_result_to_dict(r) for r in response.results]

    # Attach structured output if present
    if output_schema and hasattr(response, "output") and response.output:
        for r in results:
            r["structured"] = getattr(response.output, "content", None)
            r["grounding"] = getattr(response.output, "grounding", None)

    return results


def find_similar(
    url: str,
    *,
    num_results: int = 5,
    content_mode: str = "highlights",
    max_characters: int | None = None,
    exclude_source_domain: bool = True,
) -> list[dict[str, Any]]:
    """Find pages similar to a given URL."""
    client = exa_client()
    contents: dict[str, Any] = {}
    if content_mode == "highlights":
        contents["highlights"] = True
    elif content_mode == "text":
        cfg: dict[str, Any] = {"verbosity": "compact"}
        if max_characters:
            cfg["maxCharacters"] = max_characters
        contents["text"] = cfg

    response = client.find_similar(
        url,
        num_results=num_results,
        exclude_source_domain=exclude_source_domain,
        contents=contents,
    )
    return [_result_to_dict(r) for r in response.results]


def get_contents(
    urls: list[str],
    *,
    content_mode: str = "highlights",
    max_characters: int | None = None,
    max_age_hours: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch content for URLs you already have (no search step).
    Use this for RSS feeds, known docs, or refreshing stale content.
    """
    client = exa_client()
    kwargs: dict[str, Any] = {}
    if content_mode == "highlights":
        kwargs["highlights"] = True
    elif content_mode == "text":
        text_cfg: dict[str, Any] = {"verbosity": "compact"}
        if max_characters:
            text_cfg["maxCharacters"] = max_characters
        kwargs["text"] = text_cfg
    if max_age_hours is not None:
        kwargs["max_age_hours"] = max_age_hours

    response = client.get_contents(urls, **kwargs)
    return [_result_to_dict(r) for r in response.results]


def answer(query: str, *, system_prompt: str | None = None) -> dict[str, Any]:
    """
    /answer endpoint — grounded answer with citations.
    Best for question-first UIs; prefer search() + output_schema for
    agent pipelines where you need retrieval control.
    """
    client = exa_client()
    kwargs: dict[str, Any] = {}
    if system_prompt:
        kwargs["system_prompt"] = system_prompt
    response = client.answer(query, **kwargs)
    return {
        "answer": getattr(response, "answer", None),
        "citations": [_result_to_dict(r) for r in getattr(response, "citations", [])],
    }


def _result_to_dict(r: Any) -> dict[str, Any]:
    return {
        "id": getattr(r, "id", None),
        "url": getattr(r, "url", None),
        "title": getattr(r, "title", None),
        "score": getattr(r, "score", None),
        "published_date": getattr(r, "published_date", None),
        "author": getattr(r, "author", None),
        "highlights": getattr(r, "highlights", None),
        "text": getattr(r, "text", None),
        "summary": getattr(r, "summary", None),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Exa.ai search CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join([
            "Search types:  auto (default) | fast | instant | deep-lite | deep | deep-reasoning",
            "Content modes: highlights (default) | text | summary",
            "",
            "Examples:",
            "  exa_search.py 'how does OpenClaw route agents'",
            "  exa_search.py --type deep --content text 'exa-py structured output schema'",
            "  exa_search.py --find-similar https://docs.exa.ai",
            "  exa_search.py --answer 'what is Exa autoprompt'",
        ]),
    )
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--type", dest="search_type", default="auto",
                        choices=list(SEARCH_TYPES))
    parser.add_argument("--num", type=int, default=5)
    parser.add_argument("--content", dest="content_mode", default="highlights",
                        choices=["highlights", "text", "summary"])
    parser.add_argument("--max-chars", type=int, default=None,
                        help="Max characters for text mode")
    parser.add_argument("--fresh", type=int, default=None, metavar="HOURS",
                        help="maxAgeHours: 0=always livecrawl, -1=cache-only")
    parser.add_argument("--find-similar", metavar="URL")
    parser.add_argument("--get-contents", nargs="+", metavar="URL")
    parser.add_argument("--answer", action="store_true",
                        help="Use /answer endpoint instead of /search")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.find_similar:
        results = find_similar(args.find_similar, num_results=args.num,
                               content_mode=args.content_mode,
                               max_characters=args.max_chars)
        _print_results(results, args.json)
    elif args.get_contents:
        results = get_contents(args.get_contents, content_mode=args.content_mode,
                               max_characters=args.max_chars, max_age_hours=args.fresh)
        _print_results(results, args.json)
    elif args.answer and args.query:
        resp = answer(args.query)
        if args.json:
            print(json.dumps(resp, indent=2))
        else:
            print(resp.get("answer", ""))
            for c in resp.get("citations", []):
                print(f"  [{c['title']}] {c['url']}")
    elif args.query:
        results = search(
            args.query,
            search_type=args.search_type,
            num_results=args.num,
            content_mode=args.content_mode,
            max_characters=args.max_chars,
            max_age_hours=args.fresh,
        )
        _print_results(results, args.json)
    else:
        parser.print_help()
        sys.exit(1)


def _print_results(results: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(results, indent=2))
        return
    for i, r in enumerate(results, 1):
        print(f"\n{'='*60}")
        print(f"[{i}] {r['title'] or '(no title)'}")
        print(f"    {r['url']}")
        meta = []
        if r.get("score"):
            meta.append(f"score={r['score']:.4f}")
        if r.get("published_date"):
            meta.append(f"date={r['published_date'][:10]}")
        if meta:
            print(f"    {' '.join(meta)}")
        content = r.get("highlights") or r.get("text") or r.get("summary")
        if isinstance(content, list):
            content = " … ".join(content[:2])
        if content:
            print(f"    {str(content)[:300]}...")


if __name__ == "__main__":
    _cli()
