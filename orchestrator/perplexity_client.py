from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from dotenv import set_key
from openai import AsyncOpenAI, OpenAI

from orchestrator.key_helper import test_perplexity_key


class PerplexityClient:
    """Validated singleton wrapper around Perplexity via OpenAI-compatible SDK."""

    DEFAULT_MODEL = "sonar-pro"
    BASE_URL = "https://api.perplexity.ai"
    _instance: Optional["PerplexityClient"] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
        validate: bool = False,
        interactive: bool = True,
    ) -> None:
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout

        key = (api_key or os.getenv("PERPLEXITY_API_KEY", "")).strip()
        if validate and key and not test_perplexity_key(key):
            key = ""

        if not key and interactive:
            key = self._prompt_for_key()

        self.api_key = key
        self._sync = OpenAI(api_key=key, base_url=self.base_url, timeout=timeout)
        self._async = AsyncOpenAI(api_key=key, base_url=self.base_url, timeout=timeout)

    @classmethod
    def get(cls, validate: bool = False, interactive: bool = True) -> "PerplexityClient":
        if cls._instance is None:
            cls._instance = cls(validate=validate, interactive=interactive)
        return cls._instance

    def _prompt_for_key(self) -> str:
        print("\n🔑 PERPLEXITY_API_KEY missing/invalid.")
        print("   Get one at: https://www.perplexity.ai/settings/api")
        while True:
            key = input("   Paste API key (starts with pplx-): ").strip()
            if not key.startswith("pplx-"):
                print("   ✗ Expected key prefix 'pplx-'.")
                continue
            if not test_perplexity_key(key):
                print("   ✗ Key validation failed. Try again.")
                continue
            self._save_key(key)
            print("   ✓ Key saved")
            return key

    def _save_key(self, key: str) -> None:
        env_path = Path(".env")
        env_path.touch(exist_ok=True)
        set_key(str(env_path), "PERPLEXITY_API_KEY", key)
        os.environ["PERPLEXITY_API_KEY"] = key

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        stream: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        # Keep legacy signature compatibility while making stream behavior explicit.
        if stream:
            raise ValueError("Use stream() for streaming responses")
        r = self._sync.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )
        return {"choices": [{"message": {"content": r.choices[0].message.content}}]}

    async def chat_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        r = await self._async.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )
        return {"choices": [{"message": {"content": r.choices[0].message.content}}]}

    def stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        stream = self._sync.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
