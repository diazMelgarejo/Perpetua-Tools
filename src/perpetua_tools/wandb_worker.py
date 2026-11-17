"""Isolated W&B SDK request; only JSON crosses the process boundary."""
import contextlib
import importlib.util
import json
import pathlib
import os
import sys


def _init_tracing() -> None:
    """Initialize the existing optional Weave integration within the child deadline."""
    if not os.getenv("DEEPSEEK_V4_FLASH_WANDB_PROJECT"):
        return
    path = pathlib.Path(__file__).resolve().parents[2] / ".agent/harness/llm.py"
    spec = importlib.util.spec_from_file_location("pt_wandb_tracing_harness", path)
    if spec is None or spec.loader is None:
        return
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Tracing must not corrupt the JSON protocol on stdout.
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            module._maybe_init_wandb_weave_tracing()
    except Exception:
        pass  # Tracing remains optional.


def complete(request: dict) -> dict:
    """Send at most one request and return a minimal, validated protocol object."""
    try:
        _init_tracing()
        import openai
        client = openai.OpenAI(api_key=request['api_key'], base_url=request['base_url'],
                               max_retries=0, timeout=request['timeout'])
    except BaseException:
        return {'kind': 'not_sent'}
    try:
        response = client.chat.completions.create(
            model=request['model'], temperature=request['temperature'],
            max_completion_tokens=request['max_tokens'],
            messages=[{'role': 'system', 'content': request['system']},
                      {'role': 'user', 'content': request['user']}])
        content = response.choices[0].message.content
        tokens = getattr(getattr(response, 'usage', None), 'completion_tokens', None)
        if not isinstance(content, str) or (tokens is not None and
                (not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0)):
            return {'kind': 'unknown'}
        return {'kind': 'success', 'content': content, 'completion_tokens': tokens}
    except openai.APIStatusError as exc:
        status = exc.status_code
        if type(status) is int and 100 <= status <= 599:
            return {'kind': 'status', 'status': status}
        return {'kind': 'unknown'}
    except BaseException:
        return {'kind': 'unknown'}


def main() -> None:
    """Read a private request from stdin and emit only a redacted JSON result."""
    try:
        request = json.load(sys.stdin)
        result = complete(request)
        sys.stdout.write(json.dumps(result, allow_nan=False))
        sys.stdout.flush()
    except BaseException:
        os._exit(1)


if __name__ == '__main__':
    main()
