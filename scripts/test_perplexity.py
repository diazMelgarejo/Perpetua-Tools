#!/usr/bin/env python3
"""test_perplexity.py — quick async smoke test for Perplexity integration.

Run:
    python scripts/test_perplexity.py
"""

from __future__ import annotations

import asyncio

from orchestrator.perplexity_client import PerplexityClient


async def main() -> None:
    # One-time key prompt happens here if missing/invalid.
    client = PerplexityClient.get(validate=True, interactive=True)

    print("\nTesting Perplexity chat_async...\n")
    result = await client.chat_async(
        messages=[
            {
                "role": "user",
                "content": "What are the latest benchmark trends for Qwen coding models? Keep it concise.",
            }
        ],
        model="sonar",
        max_tokens=150,
    )
    print("Result:\n")
    print(result["choices"][0]["message"]["content"])


if __name__ == "__main__":
    asyncio.run(main())
