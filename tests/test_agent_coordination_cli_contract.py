"""Executable contract tests for scripts/agent_coordination.py.

These tests are Phase 0F for the coordination-module consolidation plan: they
freeze the live parser and dispatch surface before logic moves into
orchestrator/coordination/* modules.
See docs/coordination/README.md for canonical documentation.
"""
from __future__ import annotations

import argparse

import pytest

import orchestrator.coordination.cli as facade
import orchestrator.coordination.cli as core_cli


EXPECTED_LEAVES = {
    ("register",),
    ("agents",),
    ("claim",),
    ("release",),
    ("list",),
    ("log",),
    ("handoff", "validate"),
    ("phase", "list"),
    ("phase", "status"),
    ("phase", "start"),
    ("phase", "update"),
    ("phase", "complete"),
    ("phase", "block"),
    ("phase", "unblock"),
    ("workflow", "critical-path"),
    ("queue", "add"),
    ("queue", "list"),
    ("queue", "claim"),
    ("queue", "complete"),
    ("queue", "fail"),
    ("queue", "status"),
    ("heartbeat", "list"),
    ("heartbeat", "check"),
    ("heartbeat", "dashboard"),
    ("heartbeat", "pulse"),
    ("heartbeat", "kill"),
    ("heartbeat", "timeline"),
    ("heartbeat", "cleanup"),
    ("buffer", "status"),
    ("buffer", "drain"),
}


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise AssertionError(f"parser {parser.prog!r} has no subparsers")


def _leaf_paths(parser: argparse.ArgumentParser) -> set[tuple[str, ...]]:
    leaves: set[tuple[str, ...]] = set()

    def walk(current: argparse.ArgumentParser, path: tuple[str, ...]) -> None:
        subcommands = [
            action
            for action in current._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if not subcommands:
            leaves.add(path)
            return
        for subcommand in subcommands:
            for name, child in subcommand.choices.items():
                walk(child, (*path, name))

    walk(parser, ())
    return leaves


def _arg_dests(parser: argparse.ArgumentParser, argv: list[str]) -> set[str]:
    return set(vars(parser.parse_args(argv)))


def test_parser_exposes_exactly_the_30_supported_leaf_commands():
    parser = core_cli.build_parser()

    assert _leaf_paths(parser) == EXPECTED_LEAVES
    assert len(EXPECTED_LEAVES) == 30


@pytest.mark.parametrize(
    ("argv", "expected_dests"),
    [
        (["register", "agent-a", "cli", "model", "notes"], {"cmd", "agent_id", "agent_type", "model", "notes"}),
        (["agents"], {"cmd"}),
        (["claim", "agent-a", "task-a", "notes", "--seq", "1"], {"cmd", "agent_id", "task", "notes", "seq"}),
        (["release", "agent-a", "task-a"], {"cmd", "agent_id", "task"}),
        (["list", "task-a"], {"cmd", "task"}),
        (["log", "agent-a", "message"], {"cmd", "agent_id", "message"}),
        (["handoff", "validate", "handoff.json"], {"cmd", "subcmd", "packet"}),
        (["phase", "list"], {"cmd", "subcmd"}),
        (["phase", "status", "Phase-1"], {"cmd", "subcmd", "phase_name"}),
        (["phase", "start", "Phase-1", "--depends-on", "Phase-0", "--agent", "agent-a"], {"cmd", "subcmd", "phase_name", "depends_on", "agent"}),
        (["phase", "update", "Phase-1", "--tests-passing", "1/2", "--agent", "agent-a"], {"cmd", "subcmd", "phase_name", "tests_passing", "agent"}),
        (["phase", "complete", "Phase-1"], {"cmd", "subcmd", "phase_name"}),
        (["phase", "block", "Phase-1", "--reason", "blocked"], {"cmd", "subcmd", "phase_name", "reason"}),
        (["phase", "unblock", "Phase-1", "--reason", "resolved"], {"cmd", "subcmd", "phase_name", "reason"}),
        (["workflow", "critical-path"], {"cmd", "subcmd"}),
        (["queue", "add", "task-a", "Phase-1", "--priority", "HIGH", "--notes", "notes", "--depends-on", "dep", "--source-ref", "main", "--expected-base-sha", "abc123"], {"cmd", "subcmd", "task_name", "phase", "priority", "notes", "depends_on", "source_ref", "expected_base_sha", "handoff"}),
        (["queue", "list", "--phase", "Phase-1", "--priority", "HIGH", "--agent", "agent-a"], {"cmd", "subcmd", "phase", "priority", "agent"}),
        (["queue", "claim", "task-id", "agent-a"], {"cmd", "subcmd", "task_id", "agent_id"}),
        (["queue", "complete", "task-id", "agent-a", "--notes", "done"], {"cmd", "subcmd", "task_id", "agent_id", "notes"}),
        (["queue", "fail", "task-id", "agent-a", "--notes", "failed"], {"cmd", "subcmd", "task_id", "agent_id", "notes"}),
        (["queue", "status", "--agent", "agent-a"], {"cmd", "subcmd", "agent"}),
        (["heartbeat", "list"], {"cmd", "subcmd"}),
        (["heartbeat", "check", "agent-a"], {"cmd", "subcmd", "agent_id"}),
        (["heartbeat", "dashboard"], {"cmd", "subcmd"}),
        (["heartbeat", "pulse", "agent-a"], {"cmd", "subcmd", "agent_id"}),
        (["heartbeat", "kill", "agent-a", "--reason", "stale"], {"cmd", "subcmd", "agent_id", "reason"}),
        (["heartbeat", "timeline", "agent-a", "--hours", "2"], {"cmd", "subcmd", "agent_id", "hours"}),
        (["heartbeat", "cleanup"], {"cmd", "subcmd"}),
        (["buffer", "status", "--agent", "agent-a"], {"cmd", "subcmd", "agent"}),
        (["buffer", "drain", "agent-a"], {"cmd", "subcmd", "agent_id"}),
    ],
)
def test_parser_leaf_argument_contract(argv, expected_dests):
    parser = core_cli.build_parser()

    assert _arg_dests(parser, argv) == expected_dests


class DummyBus:
    async def init_db(self) -> None:
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("argv", "handler_name"),
    [
        (["register", "agent-a", "cli"], "_register"),
        (["agents"], "_agents"),
        (["claim", "agent-a", "task-a"], "_claim"),
        (["claim", "agent-a", "task-a", "--seq", "1"], "_claim_with_seq"),
        (["release", "agent-a", "task-a"], "_release"),
        (["list"], "_list"),
        (["log", "agent-a", "message"], "_log"),
        (["phase", "list"], "_phase_list"),
        (["phase", "status", "Phase-1"], "_phase_status"),
        (["phase", "start", "Phase-1"], "_phase_start"),
        (["phase", "update", "Phase-1", "--tests-passing", "1/2"], "_phase_update"),
        (["phase", "complete", "Phase-1"], "_phase_complete"),
        (["phase", "block", "Phase-1", "--reason", "blocked"], "_phase_block"),
        (["phase", "unblock", "Phase-1", "--reason", "resolved"], "_phase_unblock"),
        (["workflow", "critical-path"], "_workflow_critical_path"),
        (["queue", "add", "task-a", "Phase-1"], "_queue_add"),
        (["queue", "list"], "_queue_list"),
        (["queue", "claim", "task-id", "agent-a"], "_queue_claim"),
        (["queue", "complete", "task-id", "agent-a"], "_queue_complete"),
        (["queue", "fail", "task-id", "agent-a"], "_queue_fail"),
        (["queue", "status"], "_queue_status"),
        (["heartbeat", "list"], "_heartbeat_list"),
        (["heartbeat", "check", "agent-a"], "_heartbeat_check"),
        (["heartbeat", "dashboard"], "_heartbeat_dashboard"),
        (["heartbeat", "pulse", "agent-a"], "_heartbeat_pulse"),
        (["heartbeat", "kill", "agent-a", "--reason", "stale"], "_heartbeat_kill"),
        (["heartbeat", "timeline", "agent-a"], "_heartbeat_timeline"),
        (["heartbeat", "cleanup"], "_heartbeat_cleanup"),
        (["buffer", "status"], "_buffer_status"),
        (["buffer", "drain", "agent-a"], "_buffer_drain"),
    ],
)
async def test_real_parser_dispatches_each_leaf_to_the_expected_handler(
    monkeypatch, argv, handler_name
):
    calls: list[str] = []

    async def record_call(*_args, **_kwargs):
        calls.append(handler_name)
        return None

    monkeypatch.setattr(core_cli, "canonical_db_path", lambda: ":memory:")
    monkeypatch.setattr(core_cli, "make_gossip_bus", lambda _path: DummyBus())
    monkeypatch.setattr(core_cli, handler_name, record_call)

    args = core_cli.build_parser().parse_args(argv)
    result = await core_cli._amain(args)

    assert result == 0
    assert calls == [handler_name]
