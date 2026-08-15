"""Canonical provider-native transport for governed paid model execution.

The Tier-5 runner owns recipe sequencing and policy gates. This module owns
only the final provider request: it resolves an allowlisted ``ModelTarget``,
obtains a local-only credential, emits the provider's native wire format, and
returns text. It never logs prompts, provider response bodies, or credentials.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
import yaml

from orchestrator.model_registry import ModelRegistry, ModelTarget
from orchestrator.tiered_pipeline import PIPELINE_TIER, PipelineExecutionError

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_PROVIDERS = DEFAULT_CONFIG_DIR / "providers.yml"
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_ALLOWED_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})


class ProviderConfigError(PipelineExecutionError):
    """Raised when provider or model configuration is invalid."""


class ProviderTransportError(PipelineExecutionError):
    """A redacted provider failure suitable for operator-facing responses."""

    def __init__(
        self,
        provider: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        self.request_id = request_id
        self.retryable = retryable
        suffix = f" HTTP {status_code}" if status_code is not None else ""
        retry = "; retryable" if retryable else ""
        correlation = f" (request {request_id})" if request_id else ""
        super().__init__(f"{provider} provider request failed{suffix}{retry}{correlation}")


@dataclass(frozen=True)
class ProviderConfig:
    backend: str
    credential_env: str
    allowed_hosts: frozenset[str]
    documentation_hosts: frozenset[str]
    default_api_path: str
    timeout_seconds: float
    max_attempts: int
    api_version: str | None = None


def _load_provider_configs(path: Path) -> dict[str, ProviderConfig]:
    if not path.is_file():
        raise ProviderConfigError(f"provider config missing: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ProviderConfigError(f"invalid provider config: {exc}") from exc
    rows = raw.get("providers") if isinstance(raw, dict) else None
    if not isinstance(rows, dict) or not rows:
        raise ProviderConfigError("provider config requires a non-empty providers mapping")

    configs: dict[str, ProviderConfig] = {}
    for backend, row in rows.items():
        if not isinstance(backend, str) or not isinstance(row, dict):
            raise ProviderConfigError("provider entries must be named mappings")
        credential_env = str(row.get("credential_env", "")).strip()
        hosts = row.get("allowed_hosts")
        documentation_hosts = row.get("documentation_hosts")
        api_path = str(row.get("default_api_path", "")).strip()
        try:
            timeout_seconds = float(row.get("timeout_seconds", 60))
            max_attempts = int(row.get("max_attempts", 1))
        except (TypeError, ValueError) as exc:
            raise ProviderConfigError(f"provider {backend!r} has invalid timeout/retry settings") from exc
        if (
            not credential_env
            or not isinstance(hosts, list)
            or not all(isinstance(host, str) and host.strip() for host in hosts)
            or not isinstance(documentation_hosts, list)
            or not all(isinstance(host, str) and host.strip() for host in documentation_hosts)
            or not api_path.startswith("/")
            or timeout_seconds <= 0
            or not 1 <= max_attempts <= 3
        ):
            raise ProviderConfigError(f"provider {backend!r} has incomplete or unsafe settings")
        api_version = row.get("api_version")
        configs[backend] = ProviderConfig(
            backend=backend,
            credential_env=credential_env,
            allowed_hosts=frozenset(host.strip().lower() for host in hosts),
            documentation_hosts=frozenset(host.strip().lower() for host in documentation_hosts),
            default_api_path=api_path,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            api_version=str(api_version).strip() if api_version else None,
        )
    return configs


class ProviderTransportRegistry:
    """Resolve configured cloud targets and dispatch through native adapters."""

    def __init__(
        self,
        *,
        config_dir: str | Path | None = None,
        providers_path: str | Path | None = None,
    ) -> None:
        self.config_dir = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
        self._providers = _load_provider_configs(
            Path(providers_path) if providers_path is not None else self.config_dir / "providers.yml"
        )
        registry = ModelRegistry(config_dir=str(self.config_dir))
        self._models = {model.name: model for model in registry.list_models(probe=False)}

    @staticmethod
    def _credential(provider: ProviderConfig) -> str:
        value = os.getenv(provider.credential_env, "").strip()
        if not value:
            raise ProviderConfigError(
                f"provider {provider.backend!r} requires local environment variable {provider.credential_env}"
            )
        return value

    @staticmethod
    def _endpoint(target: ModelTarget, provider: ProviderConfig) -> str:
        parsed = urlparse(target.host)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or hostname not in provider.allowed_hosts:
            raise ProviderConfigError(
                f"provider {provider.backend!r} target host is not allowlisted"
            )
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ProviderConfigError(f"provider {provider.backend!r} target URL is malformed")
        if parsed.port not in (None, 443):
            raise ProviderConfigError(f"provider {provider.backend!r} target port is not allowed")
        api_path = target.api_path or provider.default_api_path
        if not api_path.startswith("/") or "//" in api_path:
            raise ProviderConfigError(f"provider {provider.backend!r} API path is invalid")
        return f"https://{hostname}{api_path}"

    @staticmethod
    def _require_verified_provenance(target: ModelTarget, provider: ProviderConfig) -> None:
        """Reject cloud wire IDs that lack a matching official source record."""
        provenance = target.provenance
        if not isinstance(provenance, Mapping):
            raise ProviderConfigError(f"model {target.name!r} has no verified provider provenance")
        source_model_id = provenance.get("source_model_id")
        source_url = provenance.get("source_url")
        source_kind = provenance.get("kind")
        parsed = urlparse(source_url) if isinstance(source_url, str) else None
        if (
            source_kind != "provider-api"
            or source_model_id != target.api_model
            or parsed is None
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.lower() not in provider.documentation_hosts
        ):
            raise ProviderConfigError(
                f"model {target.name!r} has incomplete or mismatched provider provenance"
            )

    @staticmethod
    def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
        if response is not None:
            try:
                return max(0.0, min(float(response.headers.get("retry-after", "")), 2.0))
            except ValueError:
                pass
        return min(0.25 * (2**attempt), 1.0)

    async def _post(
        self,
        provider: ProviderConfig,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        last_error: ProviderTransportError | None = None
        timeout = httpx.Timeout(provider.timeout_seconds, connect=min(provider.timeout_seconds, 10.0))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            for attempt in range(provider.max_attempts):
                response: httpx.Response | None = None
                try:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    if response.status_code < 400:
                        try:
                            body = response.json()
                        except ValueError as exc:
                            raise ProviderTransportError(provider.backend) from exc
                        if isinstance(body, dict):
                            return body
                        raise ProviderTransportError(provider.backend)
                    request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
                    retryable = response.status_code in _RETRYABLE_STATUS_CODES
                    last_error = ProviderTransportError(
                        provider.backend,
                        status_code=response.status_code,
                        request_id=request_id,
                        retryable=retryable,
                    )
                    if not retryable:
                        raise last_error
                except ProviderTransportError:
                    raise
                except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError):
                    last_error = ProviderTransportError(provider.backend, retryable=True)

                if attempt + 1 < provider.max_attempts:
                    await asyncio.sleep(self._retry_delay(response, attempt))
            assert last_error is not None
            raise last_error

    @staticmethod
    def _openai_payload(target: ModelTarget, prompt: str, max_tokens: int) -> dict[str, Any]:
        return {
            "model": target.api_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        }

    @staticmethod
    def _anthropic_payload(target: ModelTarget, prompt: str, max_tokens: int) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": target.api_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        options = target.provider_options or {}
        output_config = options.get("output_config") if isinstance(options, Mapping) else None
        if output_config is not None:
            if not isinstance(output_config, Mapping):
                raise ProviderConfigError("Anthropic output_config must be a mapping")
            effort = output_config.get("effort")
            if effort not in _ALLOWED_EFFORTS or set(output_config) != {"effort"}:
                raise ProviderConfigError("Anthropic output_config permits only a valid effort")
            payload["output_config"] = {"effort": effort}
        return payload

    @staticmethod
    def _openai_text(payload: Mapping[str, Any], backend: str) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderTransportError(backend) from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderTransportError(backend)
        return content

    @staticmethod
    def _anthropic_text(payload: Mapping[str, Any]) -> str:
        content = payload.get("content")
        if not isinstance(content, list):
            raise ProviderTransportError("anthropic")
        text = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
        )
        if not text.strip():
            raise ProviderTransportError("anthropic")
        return text

    async def dispatch(self, model: str, prompt: str, max_tokens: int, stage: str) -> str:
        """Dispatch one already-gated stage without exposing provider internals."""
        del stage  # Trace attribution remains the runner's responsibility.
        target = self._models.get(model)
        if target is None:
            raise ProviderConfigError(f"unknown model {model!r} in provider transport")
        if target.frugality_tier != PIPELINE_TIER or target.device != "cloud":
            raise ProviderConfigError(f"model {model!r} is not an eligible Tier-5 cloud target")
        provider = self._providers.get(target.backend)
        if provider is None:
            raise ProviderConfigError(f"no provider transport is configured for backend {target.backend!r}")
        self._require_verified_provenance(target, provider)
        credential = self._credential(provider)
        endpoint = self._endpoint(target, provider)
        if target.backend == "bigmodel":
            body = await self._post(
                provider,
                endpoint=endpoint,
                headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
                payload=self._openai_payload(target, prompt, max_tokens),
            )
            return self._openai_text(body, target.backend)
        if target.backend == "anthropic":
            if not provider.api_version:
                raise ProviderConfigError("Anthropic provider requires api_version")
            body = await self._post(
                provider,
                endpoint=endpoint,
                headers={
                    "x-api-key": credential,
                    "anthropic-version": provider.api_version,
                    "content-type": "application/json",
                },
                payload=self._anthropic_payload(target, prompt, max_tokens),
            )
            return self._anthropic_text(body)
        if target.backend == "openrouter":
            # OpenRouter's chat/completions response shape matches OpenAI's
            # (choices[0].message.content), verified against its own API
            # reference. Referer/title headers are optional attribution
            # OpenRouter uses for its public model-ranking page -- never
            # required for the request to succeed, so they're only sent when
            # explicitly configured, never fabricated.
            headers = {"Authorization": f"Bearer {credential}", "Content-Type": "application/json"}
            referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
            title = os.getenv("OPENROUTER_APP_TITLE", "").strip()
            if referer:
                headers["HTTP-Referer"] = referer
            if title:
                headers["X-Title"] = title
            body = await self._post(
                provider,
                endpoint=endpoint,
                headers=headers,
                payload=self._openai_payload(target, prompt, max_tokens),
            )
            return self._openai_text(body, target.backend)
        if target.backend in ("mistral", "deepseek", "groq", "dashscope", "meta_llama"):
            # All four are OpenAI-Chat-Completions-shaped: standard Bearer
            # auth, choices[0].message.content response shape -- verified per
            # backend against each provider's own API reference before adding
            # its config/providers.yml entry.
            body = await self._post(
                provider,
                endpoint=endpoint,
                headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
                payload=self._openai_payload(target, prompt, max_tokens),
            )
            return self._openai_text(body, target.backend)
        raise ProviderConfigError(f"backend {target.backend!r} has no native adapter")
