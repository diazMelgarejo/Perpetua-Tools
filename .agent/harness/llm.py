"""Shared model-call helper. Factored out of conductor so memory/ can reuse."""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time


# MiniMax regional endpoints. Each region exposes OpenAI- and Anthropic-compatible
# base URLs so the portable harness can call MiniMax directly instead of relying
# on undocumented external SDK environment behavior.
MINIMAX_REGIONS = {
    "global_en": {
        "openai_base_url": "https://api.minimax.io/v1",
        "anthropic_base_url": "https://api.minimax.io/anthropic",
    },
    "cn_zh": {
        "openai_base_url": "https://api.minimaxi.com/v1",
        "anthropic_base_url": "https://api.minimaxi.com/anthropic",
    },
}

# Current MiniMax text models. ``MiniMax-M3`` is the default; ``MiniMax-M2.7`` is
# also supported via AGENT_MODEL. Context windows are in tokens.
MINIMAX_MODELS = {
    "MiniMax-M3": {"context_window": 1000000},
    "MiniMax-M2.7": {"context_window": 204800},
}
MINIMAX_DEFAULT_MODEL = "MiniMax-M3"

# PT-local overlay (not a vendored agentic-stack provider): wanDB.ai inference,
# OpenAI-compatible. See bin/orama-system/skills/cline-wandb/SKILL.md § Contract
# for the full provenance -- this is the same route that skill's `cline` CLI
# dispatch uses, added here so llm.py can call it directly.
WANDB_BASE_URL = "https://api.inference.wandb.ai/v1"
WANDB_DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
_WANDB_WEAVE_INITIALIZED = False


def _minimax_region():
    """Resolve the configured MiniMax region and return its base URLs."""
    region = os.getenv("AGENT_MINIMAX_REGION", "global_en").lower()
    if region not in MINIMAX_REGIONS:
        raise ValueError(f"unknown MiniMax region: {region}")
    return region


def llm_available():
    """True iff provider + key are configured. Validation / dream cycle check
    this before making calls so they degrade gracefully offline."""
    provider = os.getenv("AGENT_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "minimax":
        return bool(os.getenv("MINIMAX_API_KEY"))
    if provider == "wandb":
        return bool(os.getenv("DEEPSEEK_V4_FLASH_WANDB"))
    if provider == "claude_cli":
        return shutil.which("claude") is not None
    return False


_CLAUDE_CLI_DEFAULT_TIMEOUT_SEC = 120


def _call_claude_cli(system, user, *, model, timeout_sec=None):
    """Route through the locally-authenticated `claude` CLI instead of the
    `anthropic` SDK -- the SDK only accepts api_key/auth_token/credentials
    and has no path to Claude Pro/Max's subscription-based session auth.
    The CLI, running as this same authenticated connection, does. PT-local
    exclusive overlay; not a vendored agentic-stack provider.

    No max_tokens equivalent exists on this path (`claude --help` has no
    output-length flag) -- the caller's max_tokens is silently unused here,
    unlike every other provider in this file.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("claude CLI not found on PATH")
    # Isolated text-only path: --bare skips hooks/skills/MCP/CLAUDE.md auto-load;
    # --tools "" denies every tool so untrusted user text cannot trigger workspace
    # actions. This helper is a chat-completion stand-in, not an agent session.
    cmd = [
        claude_bin, "-p", user,
        "--system-prompt", system,
        "--output-format", "json",
        "--bare",
        "--tools", "",
    ]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=timeout_sec or _CLAUDE_CLI_DEFAULT_TIMEOUT_SEC,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI exited {proc.returncode}: {proc.stderr.strip()[:500]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude CLI produced non-JSON output: {proc.stdout[:300]!r}") from exc
    if payload.get("is_error"):
        raise RuntimeError(f"claude CLI reported an error: {payload.get('result') or payload}")
    return payload["result"]


def _maybe_init_wandb_weave_tracing():
    """Turn Weave tracing on iff DEEPSEEK_V4_FLASH_WANDB_PROJECT is set --
    this is the on/off switch for the *tracing* layer only. It never touches
    the actual chat-completion request: sending the project as an
    `OpenAI-Project` header or SDK `project=` kwarg breaks auth with a 401
    on an otherwise-valid key (confirmed 2026-08-05, see cline-wandb
    SKILL.md § Contract). Idempotent (init once per process); degrades
    silently if the optional `weave` package isn't installed, matching this
    module's existing "missing SDK -> ImportError surfaces at call time,
    not at import time" pattern for the other providers.
    """
    global _WANDB_WEAVE_INITIALIZED
    project = os.getenv("DEEPSEEK_V4_FLASH_WANDB_PROJECT")
    if not project or _WANDB_WEAVE_INITIALIZED:
        return
    try:
        import weave
        weave.init(project)
    except ImportError:
        pass
    except Exception:
        # Optional tracing must never block the completion request. A failed
        # init is recorded by leaving weave uninitialized for this attempt;
        # the finally-guard still flips so we do not retry every call.
        pass
    finally:
        # Set even on ImportError / init failure: nothing will succeed on a
        # later call inside this same process either, so don't retry every call.
        _WANDB_WEAVE_INITIALIZED = True


PROVIDER_STOP_STATUS = (402, 429)


class ProviderLimitStop(RuntimeError):
    """The provider answered 402 (allowance used up with pay-as-you-go inactive, or spending cap
    reached) or 429 (concurrency limit). Stop the loop; never retry and never activate pay-as-you-go."""

    def __init__(self, status):
        """Record the HTTP ``status`` (402 or 429) that stopped the loop."""
        super().__init__(f"provider limit: HTTP {status}")
        self.status = status


_WANDB_PROVIDER = "wandb-inference"
# One request is allowed this long. The spend reservation is held for the timeout plus a margin, so a
# request that runs to its full timeout is never swept while it is still legitimately in flight.
_WANDB_REQUEST_TIMEOUT_SECONDS = 600.0
_WANDB_HOLD_SECONDS = _WANDB_REQUEST_TIMEOUT_SECONDS + 300.0
_WANDB_SEAT = "agent-harness"
_WANDB_MODE = "call-model"
_SPEND_GATE_MODULE = "pt_spend_gate"


class ProviderSpendRefused(RuntimeError):
    """The shared spend gate refused a paid request BEFORE it was dispatched: a missing or stale operator
    attestation ("attestation-required"), an exhausted budget ("budget-exhausted") or an unusable guard
    ("spend-guard-unavailable"), or unresolved prior spend ("spend-reconciliation-required").
    No new request was sent or reserved. Stop; do not retry."""

    def __init__(self, reason, detail=None):
        """Record the machine-readable ``reason`` and an optional human ``detail``."""
        super().__init__(f"spend refused: {reason}" + (f" ({detail})" if detail else ""))
        self.reason = reason
        self.detail = detail


def _wandb_spend_gate():
    """Build the shared Perpetua-Tools SpendGate for W&B Inference, or refuse.

    The gate lives in this checkout's ``orchestrator/spend_gate.py`` and is loaded by file path, so the
    harness needs no import path setup. Any failure to load it or to open its budget store (missing
    policy, unsafe state directory, broken checkout) fails closed as ProviderSpendRefused: a paid request
    never goes out without the guard.
    """
    try:
        module = sys.modules.get(_SPEND_GATE_MODULE)
        if module is None:
            path = pathlib.Path(__file__).resolve().parents[2] / "orchestrator" / "spend_gate.py"
            spec = importlib.util.spec_from_file_location(_SPEND_GATE_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[_SPEND_GATE_MODULE] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(_SPEND_GATE_MODULE, None)
                raise
        return module.SpendGate(provider=_WANDB_PROVIDER)
    except Exception as exc:
        raise ProviderSpendRefused("spend-guard-unavailable", f"{type(exc).__name__}: {exc}") from exc


def _settle_unknown_quietly(gate, reservation, input_chars, outcome):
    """Charge the full reservation for a request that may have been sent. Never raises: this runs while
    another exception is propagating, and the original failure must not be masked. If accounting itself
    fails, say so on stderr; the durable uncertain hold requires reconciliation."""
    try:
        gate.settle_unknown(reservation, input_chars, outcome, _WANDB_SEAT, _WANDB_MODE)
    except Exception as exc:
        print(f"spend accounting failed for a possibly-sent request: {type(exc).__name__}: {exc}", file=sys.stderr)


class _WandbNotStarted(RuntimeError):
    """The worker could not be started and no request was dispatched."""


def _run_wandb_worker(request: dict, timeout: float) -> dict:
    """Run one isolated completion with a monotonic deadline and bounded cleanup.

    Credentials travel through a private stdin pipe, never command arguments. JSON is
    the only return protocol; provider objects are never deserialized with pickle.
    """
    deadline = time.monotonic() + timeout
    path = pathlib.Path(__file__).resolve().parents[2] / "src" / "perpetua_tools" / "wandb_worker.py"
    try:
        proc = subprocess.Popen([sys.executable, str(path)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise _WandbNotStarted("worker failed to start") from exc
    try:
        payload = json.dumps(request, allow_nan=False).encode("utf-8")
        output, _ = proc.communicate(payload, timeout=max(0, deadline - time.monotonic()))
        if time.monotonic() > deadline or proc.returncode != 0:
            raise RuntimeError("W&B worker failed or exceeded deadline")
        result = json.loads(output)
        if not isinstance(result, dict):
            raise ValueError("invalid worker response")
        return result
    finally:
        try:
            if proc.poll() is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass  # The child exited between poll and kill.
            proc.wait(timeout=1)
        finally:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()


def _call_wandb(system: str, user: str, *, temperature: float, max_tokens: int, model: str) -> str:
    """Perform a guarded completion in a killable worker, settling all uncertain outcomes."""
    model = model or os.getenv("AGENT_MODEL", WANDB_DEFAULT_MODEL)
    input_chars = len(system) + len(user)
    gate = _wandb_spend_gate()
    pre = gate.preflight(input_chars, _WANDB_HOLD_SECONDS, max_tokens=max_tokens)
    if not pre["ok"]:
        raise ProviderSpendRefused(pre["reason"], "; ".join(pre.get("reasons") or []) or pre.get("error"))
    reservation = pre["reservation"]
    request = {"api_key": os.getenv("DEEPSEEK_V4_FLASH_WANDB", ""), "base_url": WANDB_BASE_URL,
               "timeout": _WANDB_REQUEST_TIMEOUT_SECONDS, "system": system, "user": user,
               "model": model, "temperature": temperature, "max_tokens": max_tokens}
    status_handled = False
    try:
        result = _run_wandb_worker(request, _WANDB_REQUEST_TIMEOUT_SECONDS)
        kind = result.get("kind") if isinstance(result, dict) else None
        if result == {"kind": "not_sent"}:
            gate.release(reservation)
            status_handled = True
            raise RuntimeError("W&B worker could not initialize")
        if kind == "status" and set(result) == {"kind", "status"} and type(result["status"]) is int and 100 <= result["status"] <= 599:
            status = result["status"]
            if status < 500:
                gate.release(reservation)
            else:
                _settle_unknown_quietly(gate, reservation, input_chars, f"http-{status}")
            status_handled = True
            if status in PROVIDER_STOP_STATUS:
                raise ProviderLimitStop(status)
            # Reconstruct only the public status, never the provider's potentially sensitive body.
            import httpx
            import openai
            response = httpx.Response(status, request=httpx.Request("POST", WANDB_BASE_URL))
            raise openai.APIStatusError(f"provider returned HTTP {status}", response=response, body=None)
        if (kind != "success" or set(result) != {"kind", "content", "completion_tokens"}
                or not isinstance(result["content"], str)
                or (result["completion_tokens"] is not None and
                    (type(result["completion_tokens"]) is not int or result["completion_tokens"] < 0))):
            raise RuntimeError("invalid or unavailable W&B worker response")
    except _WandbNotStarted:
        gate.release(reservation)
        raise
    except (ProviderLimitStop,):
        raise
    except BaseException as exc:
        # Status errors were already settled above.
        if status_handled:
            raise
        _settle_unknown_quietly(gate, reservation, input_chars, "request-failed")
        raise
    content = result["content"]
    billed = result["completion_tokens"] or 0
    output_chars = max(len(content), billed * gate.policy["projection"]["chars_per_token"])
    try:
        gate.settle(reservation, input_chars, output_chars, "ok", _WANDB_SEAT, _WANDB_MODE)
    except Exception as exc:
        print(f"spend accounting failed after a paid answer: {type(exc).__name__}: {exc}", file=sys.stderr)
        _settle_unknown_quietly(gate, reservation, input_chars, "settle-failed")
    return content


def _call_minimax(system, user, *, temperature, max_tokens, model):
    """One MiniMax chat completion over the configured region and wire (openai or anthropic)."""
    region = _minimax_region()
    base_urls = MINIMAX_REGIONS[region]
    model = model or os.getenv("AGENT_MODEL", MINIMAX_DEFAULT_MODEL)
    if model not in MINIMAX_MODELS:
        raise ValueError(
            f"unknown MiniMax model: {model}. "
            f"Supported: {', '.join(MINIMAX_MODELS)}"
        )
    api_key = os.getenv("MINIMAX_API_KEY", "")
    wire = os.getenv("AGENT_MINIMAX_WIRE", "openai").lower()
    if wire == "anthropic":
        from anthropic import Anthropic
        c = Anthropic(api_key=api_key, base_url=base_urls["anthropic_base_url"])
        r = c.messages.create(
            model=model,
            max_tokens=max_tokens, temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text
    if wire == "openai":
        from openai import OpenAI
        c = OpenAI(api_key=api_key, base_url=base_urls["openai_base_url"])
        r = c.chat.completions.create(
            model=model,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return r.choices[0].message.content
    raise ValueError(f"unknown MiniMax wire: {wire}")


def _check_openai_base_url() -> None:
    """Refuse W&B and malformed custom URLs before the generic OpenAI client is built.

    The guarded W&B route has different credentials and accounting semantics, so callers
    must select it explicitly. Transport identity parsing is owned by endpoint_policy_core.
    """
    base_url = os.getenv("OPENAI_BASE_URL")
    if not base_url:
        return
    name = "pt_harness_endpoint_policy_core"
    module = sys.modules.get(name)
    if module is None:
        path = pathlib.Path(__file__).resolve().parents[2] / "src/utils/endpoint_policy_core.py"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ValueError("endpoint policy unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    identity = module.parse_transport_identity(base_url)
    if identity is None:
        raise ValueError("invalid OPENAI_BASE_URL")
    host = identity.hostname.rstrip(".")
    if "%" in host:
        raise ValueError("encoded OPENAI_BASE_URL hostname is unsupported")
    wandb_host = "api.inference.wandb.ai"
    if host == wandb_host or host.endswith("." + wandb_host):
        raise ProviderSpendRefused("wandb-requires-guarded-provider", "set AGENT_PROVIDER=wandb")


def call_model(system, user, *, temperature=0.3, max_tokens=4096, model=None):
    """Send one chat turn through the provider named by AGENT_PROVIDER. The wandb provider is admitted by the
    shared spend gate (see _call_wandb) before anything is dispatched."""
    provider = os.getenv("AGENT_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        from anthropic import Anthropic
        c = Anthropic()
        r = c.messages.create(
            model=model or os.getenv("AGENT_MODEL", "claude-sonnet-4-5"),
            max_tokens=max_tokens, temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text
    if provider == "openai":
        _check_openai_base_url()
        from openai import OpenAI
        c = OpenAI()
        r = c.chat.completions.create(
            model=model or os.getenv("AGENT_MODEL", "gpt-4o"),
            temperature=temperature,
            max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return r.choices[0].message.content
    if provider == "minimax":
        return _call_minimax(
            system, user,
            temperature=temperature, max_tokens=max_tokens, model=model,
        )
    if provider == "wandb":
        return _call_wandb(
            system, user,
            temperature=temperature, max_tokens=max_tokens, model=model,
        )
    if provider == "claude_cli":
        return _call_claude_cli(system, user, model=model)
    raise ValueError(f"unknown provider: {provider}")
