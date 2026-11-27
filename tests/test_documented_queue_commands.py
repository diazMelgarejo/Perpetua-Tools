"""Every documented `queue` command must parse with the real CLI parser.

Docs drifted from the parser once (missing agent id, then a missing claim fence flag), which only showed
when an agent followed them. This reads the commands out of the docs and parses each one.

The takeover procedure is also run as written: it has to read the stalled claim's stamp and be refused once
that claim has been replaced under the same agent name. The lessons that describe a takeover must agree.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator.coordination import cli
from orchestrator.coordination.task_queue import (
    get_task_claim,
    latest_task_snapshots,
    queue_add,
    queue_claim,
    queue_fail,
)
from orchestrator.gossip_bus import GossipBus

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"PHASE_TRACKING.md": (ROOT / "PHASE_TRACKING.md").read_text(encoding="utf-8"), "cli docstring": cli.__doc__ or ""}
PREFIX = "python3 scripts/agent_coordination.py "
TAKEOVER_HEADING = "## Taking over a claimed task"
# A reserved .invalid name never resolves, so a subprocess cannot reach a local embedding model.
NO_EMBEDDINGS_URL = "http://embeddings.invalid"

sys.path.insert(0, str(ROOT / ".agent" / "memory"))
from render_lessons import render_lessons_as_text  # noqa: E402


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


def _takeover_section() -> str:
    text = SOURCES["PHASE_TRACKING.md"]
    assert TAKEOVER_HEADING in text, "PHASE_TRACKING.md documents no takeover procedure"
    return text.split(TAKEOVER_HEADING, 1)[1].split("\n## ", 1)[0]


def _only_line(section: str, start: str) -> str:
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith(start)]
    assert len(lines) == 1, f"expected one documented command starting {start!r}, found {len(lines)}"
    return lines[0]


def _run(argv: list[str], db_path: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GOSSIP_DB_PATH": db_path, "GOSSIP_PEERS": "", "OLLAMA_BASE_URL": NO_EMBEDDINGS_URL}
    return subprocess.run(
        [sys.executable, *argv], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60, check=False
    )


async def _stalled_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[GossipBus, str]:
    monkeypatch.setattr(GossipBus, "schedule_embedding", lambda *_args: None)
    bus = GossipBus(tmp_path / "takeover.db")
    await bus.init_db()
    await queue_add(bus, "stalled-work", "Phase-1", "NORMAL", "", None)
    task_id = next(iter(await latest_task_snapshots(bus)))
    assert await queue_claim(bus, task_id, "claimant")
    return bus, task_id


def _read_stamp(bus: GossipBus, task_id: str) -> str:
    argv = shlex.split(_only_line(_takeover_section(), "python3 -c ").replace("<task_id>", task_id))
    result = _run(argv[1:], bus.db_path)
    assert result.returncode == 0, result.stderr
    agent_id, stamp = result.stdout.split()
    assert agent_id == "claimant"
    return stamp


def _complete_as_documented(bus: GossipBus, task_id: str, stamp: str) -> subprocess.CompletedProcess[str]:
    line = _only_line(_takeover_section(), PREFIX + "queue complete ")
    for placeholder, value in {
        "<task_id>": task_id,
        "<original_claimant_agent_id>": "claimant",
        "<claimed_at>": stamp,
        "<actor_and_evidence>": "actor and evidence",
    }.items():
        line = line.replace(placeholder, value)
    return _run(shlex.split(line)[1:], bus.db_path)


async def test_documented_takeover_completes_the_claim_it_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bus, task_id = await _stalled_claim(tmp_path, monkeypatch)

    result = _complete_as_documented(bus, task_id, _read_stamp(bus, task_id))

    assert result.returncode == 0, result.stderr
    snapshot = (await latest_task_snapshots(bus))[task_id]
    assert (snapshot["status"], snapshot["fence"]) == ("completed", "claimed_at")


async def test_documented_takeover_cannot_complete_a_same_name_replacement_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bus, task_id = await _stalled_claim(tmp_path, monkeypatch)
    stamp = _read_stamp(bus, task_id)
    await queue_fail(bus, task_id, "claimant", "released", expected_claimed_at=float(stamp))
    replacement = await queue_claim(bus, task_id, "claimant")

    result = _complete_as_documented(bus, task_id, stamp)

    assert result.returncode != 0
    assert "claim changed" in result.stderr
    assert tuple(await get_task_claim(bus, task_id)) == ("claimant", replacement)


def test_takeover_section_never_offers_the_unfenced_opt_out() -> None:
    section = " ".join(_takeover_section().split())
    assert "Never use `--unverified-legacy` for a takeover" in section
    assert "Do not use `queue fail` for a takeover" in section
    assert "leave the claim held" in section
    assert not [c for c in section.split("`") if "queue complete" in c and "--unverified-legacy" in c]


def test_every_active_takeover_lesson_keeps_the_claim_fence() -> None:
    rendered = render_lessons_as_text(str(ROOT / ".agent" / "memory" / "semantic"))
    active = [
        line for line in rendered.splitlines()
        if line.startswith("- ") and not line.startswith("- ~~")
        and "takeover" in line and "--unverified-legacy" in line
    ]
    required = (
        "never for a takeover",
        "queue complete <task_id> <original_claimant_agent_id> --expected-claimed-at <claimed_at>",
        "the original claimant stays the author, you are the actor",
        "publish as yourself",
        "leave the claim held",
        "Do not use queue fail for a takeover",
    )

    assert len(active) >= 4, "a takeover lesson dropped out of active guidance"
    for line in active:
        missing = [phrase for phrase in required if phrase not in line]
        assert not missing, f"{line[-60:]} is missing {missing}"
        assert "or in a takeover" not in line
