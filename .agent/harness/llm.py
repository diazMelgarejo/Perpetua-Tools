"""Shared model-call helper. Factored out of conductor so memory/ can reuse."""
import json
import os
import shutil
import subprocess


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


def _call_wandb(system, user, *, temperature, max_tokens, model):
    api_key = os.getenv("DEEPSEEK_V4_FLASH_WANDB", "")
    model = model or os.getenv("AGENT_MODEL", WANDB_DEFAULT_MODEL)
    _maybe_init_wandb_weave_tracing()
    from openai import OpenAI
    c = OpenAI(api_key=api_key, base_url=WANDB_BASE_URL)
    r = c.chat.completions.create(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return r.choices[0].message.content


def _call_minimax(system, user, *, temperature, max_tokens, model):
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


def call_model(system, user, *, temperature=0.3, max_tokens=4096, model=None):
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
