#!/usr/bin/env python3
"""Explicit operator entrypoint for governed Tier-5 pipelines.

The prompt is read from stdin or ``--prompt-file`` so sensitive content is not
placed in shell history/process arguments. The approval record is a local JSON
file and is never persisted by the runner.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys

from orchestrator.tiered_pipeline import (
    PipelineApproval,
    PipelineConfigError,
    PipelinePolicyError,
    execute_tier5_pipeline,
)


def _load_approval(path: Path) -> PipelineApproval:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("approval JSON must be an object")
    expected = {
        "trace_id",
        "human_ref",
        "purpose",
        "recipe_id",
        "allowed_route_tier",
        "max_tokens",
        "max_cost_usd",
        "expires_at",
        "provider_scope",
    }
    if set(payload) != expected:
        missing = sorted(expected - set(payload))
        extra = sorted(set(payload) - expected)
        raise ValueError(f"approval schema mismatch; missing={missing}, extra={extra}")
    provider_scope = payload["provider_scope"]
    if not isinstance(provider_scope, list) or not all(
        isinstance(item, str) for item in provider_scope
    ):
        raise ValueError("provider_scope must be a string list")
    return PipelineApproval(
        trace_id=str(payload["trace_id"]),
        human_ref=str(payload["human_ref"]),
        purpose=str(payload["purpose"]),
        recipe_id=str(payload["recipe_id"]),
        allowed_route_tier=int(payload["allowed_route_tier"]),
        max_tokens=int(payload["max_tokens"]),
        max_cost_usd=float(payload["max_cost_usd"]),
        expires_at=datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00")),
        provider_scope=tuple(provider_scope),
    )


def _read_prompt(path: Path | None) -> str:
    prompt = path.read_text(encoding="utf-8") if path is not None else sys.stdin.read()
    if not prompt.strip():
        raise ValueError("prompt is empty")
    return prompt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an explicitly approved Tier-5 pipeline")
    parser.add_argument("--approval", type=Path, required=True, help="Local approval JSON file")
    parser.add_argument("--recipe", required=True, help="Recipe ID from config/pipelines.yml")
    parser.add_argument("--prompt-file", type=Path, help="Read prompt from UTF-8 file; default stdin")
    parser.add_argument("--task-type", default="reasoning")
    parser.add_argument("--privacy-critical", action="store_true")
    parser.add_argument("--trace", type=Path, help="Optional metadata-only JSONL trace")
    args = parser.parse_args(argv)

    try:
        result = asyncio.run(
            execute_tier5_pipeline(
                _read_prompt(args.prompt_file),
                recipe_id=args.recipe,
                approval=_load_approval(args.approval),
                task_type=args.task_type,
                privacy_critical=args.privacy_critical,
                trace_path=args.trace,
            )
        )
    except (OSError, ValueError, PipelineConfigError, PipelinePolicyError) as exc:
        print(f"tier5 pipeline refused: {exc}", file=sys.stderr)
        return 2

    print(result.output)
    print(
        json.dumps(
            {
                "trace_id": result.trace_id,
                "recipe_id": result.recipe_id,
                "total_tokens": result.total_tokens,
                "cost_usd": result.cost_usd,
            },
            separators=(",", ":"),
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
