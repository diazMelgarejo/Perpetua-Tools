from __future__ import annotations

from openai import OpenAI

PERPLEXITY_BASE = "https://api.perplexity.ai"


def test_perplexity_key(key: str) -> bool:
    """Validate a Perplexity key with a tiny real Sonar chat call."""
    if not key:
        return False
    try:
        client = OpenAI(api_key=key, base_url=PERPLEXITY_BASE, timeout=8)
        resp = client.chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        return bool(resp.choices)
    except Exception:
        return False
