"""Every documented `queue` command must parse with the real CLI parser.

Docs drifted from the parser once (missing agent id, then a missing claim fence flag), which only showed
when an agent followed them. This reads the commands out of the docs and parses each one.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from orchestrator.coordination import cli

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"PHASE_TRACKING.md": (ROOT / "PHASE_TRACKING.md").read_text(encoding="utf-8"), "cli docstring": cli.__doc__ or ""}
PREFIX = "python3 scripts/agent_coordination.py "


def _argv(line: str) -> list[str]:
    """Turn a documented command into a concrete argv: drop optional parts, take the first alternative."""
    command = line.strip()[len(PREFIX):]
    command = re.sub(r"\[[^\]]*\]", "", command)
    command = re.sub(r"\(([^|()]+)\|[^()]*\)", r"\1", command)
    command = re.sub(r"<claimed_at>", "1.5", command)
    command = re.sub(r"<(\w+)>", r"\1", command)
    return shlex.split(command, comments=True)


COMMANDS = [
    (source, line.strip())
    for source, text in SOURCES.items()
    for line in text.splitlines()
    if line.strip().startswith(PREFIX + "queue ")
]


@pytest.mark.parametrize("source,line", COMMANDS, ids=[f"{s}:{_argv(c)[1]}-{i}" for i, (s, c) in enumerate(COMMANDS)])
def test_documented_queue_command_parses(source: str, line: str) -> None:
    cli.build_parser().parse_args(_argv(line))


def test_both_sources_document_fenced_completion_and_failure() -> None:
    for source in SOURCES:
        for verb in ("complete", "fail"):
            lines = [c for s, c in COMMANDS if s == source and f" queue {verb} " in c]
            assert lines, f"{source} documents no `queue {verb}`"
            assert all("--expected-claimed-at" in c for c in lines), f"{source}: `queue {verb}` without the fence"
